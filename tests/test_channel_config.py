"""
Unit tests for pcie_eq.channel_config core module.

Verifies:
1. Public API surface, frozen dataclasses, and exact ChannelConfig type/subclass check.
2. Constructor & defensive re-validation for schema, mode, and alpha applicability/range.
3. Wave input validation: list/tuple/ndarray, scalar/2D/complex/string/NaN/Inf rejection.
4. none mode: identity copy, exact dtype matrix preservation, non-aliasing, and non-contiguous slice handling.
5. legacy_lowpass mode: default & explicit alpha golden cases, float preservation, int/bool promotion to float64, empty matrix, and direct simple_channel equivalence.
6. Helper contract failures via monkeypatch (type, shape, dtype, contiguity, alias, non-finite).
7. Serialization to_dict() / from_dict() canonical 3-key order, round-trip, and error handling.
"""

import math
import numpy as np
import pytest

import pcie_eq.channel_config as channel_config
from pcie_eq.channel_config import (
    CHANNEL_CONFIG_CONTRACT_ID,
    ChannelConfig,
    ChannelResult,
    apply_channel,
    CANONICAL_KEYS,
)
from pcie_eq.channel import simple_channel


def test_channel_config_subclass_rejection():
    """Verify apply_channel rejects ChannelConfig subclasses with TypeError."""
    class SubChannelConfig(ChannelConfig):
        pass

    sub_cfg = SubChannelConfig(mode="none")
    with pytest.raises(TypeError, match="must be exactly ChannelConfig, got SubChannelConfig"):
        apply_channel(np.array([1.0, 0.0]), sub_cfg)


def test_channel_config_constructor_and_defensive_validation():
    """Verify ChannelConfig constructor and defensive re-validation contracts."""
    # schema_version validation
    with pytest.raises(TypeError, match="schema_version must be str"):
        ChannelConfig(mode="none", schema_version=123)
    with pytest.raises(ValueError, match="Unknown schema_version"):
        ChannelConfig(mode="none", schema_version="invalid_ver")

    # mode validation
    with pytest.raises(TypeError, match="mode must be str"):
        ChannelConfig(mode=123)
    with pytest.raises(ValueError, match="Unsupported mode"):
        ChannelConfig(mode="NONE")  # case mismatch
    with pytest.raises(ValueError, match="Unsupported mode"):
        ChannelConfig(mode="none ")  # whitespace variant

    # alpha applicability for mode none
    with pytest.raises(ValueError, match="not applicable for mode 'none'"):
        ChannelConfig(mode="none", alpha=0.08)

    # alpha validation for legacy_lowpass
    for invalid_alpha in [True, False, np.float64(0.08), "0.08", (0.08,)]:
        with pytest.raises(TypeError, match="alpha must be int, float, or None"):
            ChannelConfig(mode="legacy_lowpass", alpha=invalid_alpha)

    with pytest.raises(ValueError, match="alpha must be finite"):
        ChannelConfig(mode="legacy_lowpass", alpha=math.nan)
    with pytest.raises(ValueError, match="alpha must be finite"):
        ChannelConfig(mode="legacy_lowpass", alpha=math.inf)

    # Valid alphas (int, float, negative, zero, >1)
    cfg_zero = ChannelConfig(mode="legacy_lowpass", alpha=0)
    assert cfg_zero.alpha == 0
    cfg_neg = ChannelConfig(mode="legacy_lowpass", alpha=-0.5)
    assert cfg_neg.alpha == -0.5
    cfg_large = ChannelConfig(mode="legacy_lowpass", alpha=1.5)
    assert cfg_large.alpha == 1.5

    # Defensive re-validation on corrupted frozen config
    cfg_corrupt = ChannelConfig(mode="none")
    object.__setattr__(cfg_corrupt, "mode", "invalid_mode")
    with pytest.raises(ValueError, match="Unsupported mode"):
        apply_channel(np.array([1.0]), cfg_corrupt)


def test_wave_input_validation():
    """Verify apply_channel wave input type, dimension, dtype, and finiteness validation."""
    cfg = ChannelConfig(mode="none")

    # Valid Python list & tuple
    res_list = apply_channel([1.0, 0.0], cfg)
    assert np.array_equal(res_list.values, np.array([1.0, 0.0]))
    res_tuple = apply_channel((1, 0), cfg)
    assert np.array_equal(res_tuple.values, np.array([1, 0]))

    # Invalid dimension: scalar or 2D
    with pytest.raises(ValueError, match="must be 1D"):
        apply_channel(5.0, cfg)
    with pytest.raises(ValueError, match="must be 1D"):
        apply_channel(np.array([[1.0, 0.0], [0.0, 1.0]]), cfg)

    # Invalid dtype: complex, string, object
    with pytest.raises(TypeError, match="real numeric"):
        apply_channel(np.array([1 + 2j, 3 + 4j]), cfg)
    with pytest.raises(TypeError, match="real numeric"):
        apply_channel(np.array(["1.0", "2.0"]), cfg)
    with pytest.raises(TypeError, match="real numeric"):
        apply_channel(np.array([object(), object()]), cfg)

    # Non-finite elements (NaN / Inf)
    with pytest.raises(ValueError, match="must be finite"):
        apply_channel(np.array([1.0, math.nan]), cfg)
    with pytest.raises(ValueError, match="must be finite"):
        apply_channel(np.array([1.0, math.inf]), cfg)


def test_none_mode_identity_copy_and_dtype_matrix():
    """Verify none mode produces non-aliasing C-contiguous identity copy across all dtypes."""
    cfg = ChannelConfig(mode="none")

    dtypes = [
        np.dtype("bool"),
        np.dtype("int8"),
        np.dtype("int16"),
        np.dtype("int32"),
        np.dtype("int64"),
        np.dtype("uint8"),
        np.dtype("uint16"),
        np.dtype("uint32"),
        np.dtype("uint64"),
        np.dtype("float16"),
        np.dtype("float32"),
        np.dtype("float64"),
    ]

    for dt in dtypes:
        wave = np.array([0, 1, 0, 1], dtype=dt)
        res = apply_channel(wave, cfg)

        assert res.model_level == "identity"
        assert res.resolved_config.alpha is None
        assert res.values.dtype == dt
        assert res.values.shape == wave.shape
        assert res.values.flags.c_contiguous
        assert not np.shares_memory(res.values, wave)
        assert np.array_equal(res.values, wave)

    # Non-contiguous input slice
    wave_base = np.arange(10, dtype=np.float64)
    wave_slice = wave_base[::2]
    assert not wave_slice.flags.c_contiguous

    res_slice = apply_channel(wave_slice, cfg)
    assert res_slice.values.flags.c_contiguous
    assert res_slice.values.dtype == np.float64
    assert not np.shares_memory(res_slice.values, wave_base)
    assert np.array_equal(res_slice.values, wave_slice)


def test_legacy_lowpass_golden_cases_and_equivalence():
    """Verify legacy_lowpass default/explicit alpha golden cases and direct simple_channel equivalence."""
    # Golden case 1: float64 default alpha (0.08)
    wave1 = np.array([0.0, 1.0, 1.0, 0.0], dtype=np.float64)
    cfg1 = ChannelConfig(mode="legacy_lowpass")
    res1 = apply_channel(wave1, cfg1)

    assert res1.model_level == "teaching_approximation"
    assert res1.resolved_config.alpha == 0.08
    assert res1.values.dtype == np.float64
    expected1 = np.array([0.0, 0.08, 0.1536, 0.141312], dtype=np.float64)
    assert np.allclose(res1.values, expected1)

    # Golden case 2: int64 explicit alpha 0.5 (promotes to float64)
    wave2 = np.array([0, 1, 1, 0], dtype=np.int64)
    cfg2 = ChannelConfig(mode="legacy_lowpass", alpha=0.5)
    res2 = apply_channel(wave2, cfg2)

    assert res2.resolved_config.alpha == 0.5
    assert res2.values.dtype == np.float64
    expected2 = np.array([0.0, 0.5, 0.75, 0.375], dtype=np.float64)
    assert np.allclose(res2.values, expected2)

    # Direct simple_channel equivalence across floats and ints
    for test_wave in [wave1, wave2, np.array([1, 0, -1, 1], dtype=np.int16), np.array([0.5, -0.5], dtype=np.float32)]:
        direct_out = simple_channel(test_wave, alpha=0.08)
        res_equiv = apply_channel(test_wave, cfg1)
        assert res_equiv.values.dtype == direct_out.dtype
        assert np.array_equal(res_equiv.values, direct_out)


def test_legacy_lowpass_empty_inputs_dtype_matrix():
    """Verify empty input handling in legacy_lowpass preserves float dtypes and promotes int/bool to float64."""
    cfg = ChannelConfig(mode="legacy_lowpass")

    # Empty float32 -> empty float32
    empty_f32 = np.array([], dtype=np.float32)
    res_f32 = apply_channel(empty_f32, cfg)
    assert res_f32.values.dtype == np.float32
    assert res_f32.values.shape == (0,)

    # Empty int32 -> empty float64
    empty_i32 = np.array([], dtype=np.int32)
    res_i32 = apply_channel(empty_i32, cfg)
    assert res_i32.values.dtype == np.float64
    assert res_i32.values.shape == (0,)

    # Empty Python list [] -> empty float64
    res_list = apply_channel([], cfg)
    assert res_list.values.dtype == np.float64
    assert res_list.values.shape == (0,)


def test_helper_contract_failures_raise_runtime_error(monkeypatch):
    """Verify apply_channel raises RuntimeError if simple_channel output breaks contract."""
    cfg = ChannelConfig(mode="legacy_lowpass")
    wave = np.array([1.0, 0.0], dtype=np.float64)

    # Helper returns non-ndarray
    monkeypatch.setattr(channel_config, "simple_channel", lambda w, alpha: [1.0, 0.0])
    with pytest.raises(RuntimeError, match="not np.ndarray"):
        apply_channel(wave, cfg)

    # Helper returns bad shape
    monkeypatch.setattr(channel_config, "simple_channel", lambda w, alpha: np.array([1.0]))
    with pytest.raises(RuntimeError, match="shape mismatch"):
        apply_channel(wave, cfg)

    # Helper returns bad dtype
    monkeypatch.setattr(channel_config, "simple_channel", lambda w, alpha: np.array([1, 0], dtype=np.int32))
    with pytest.raises(RuntimeError, match="dtype mismatch"):
        apply_channel(wave, cfg)

    # Helper returns non-C-contiguous output
    non_c = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float64)[:, 0]
    monkeypatch.setattr(channel_config, "simple_channel", lambda w, alpha: non_c)
    with pytest.raises(RuntimeError, match="not C-contiguous"):
        apply_channel(wave, cfg)

    # Helper returns aliased memory
    monkeypatch.setattr(channel_config, "simple_channel", lambda w, alpha: wave)
    with pytest.raises(RuntimeError, match="memory aliases"):
        apply_channel(wave, cfg)

    # Helper returns non-finite values
    monkeypatch.setattr(channel_config, "simple_channel", lambda w, alpha: np.array([1.0, math.nan], dtype=np.float64))
    with pytest.raises(RuntimeError, match="non-finite values"):
        apply_channel(wave, cfg)


def test_serialization_canonical_keys_and_round_trip():
    """Verify to_dict() 3-key canonical order, from_dict() parsing, and round-trip consistency."""
    cfg_none = ChannelConfig(mode="none")
    d_none = cfg_none.to_dict()
    assert list(d_none.keys()) == CANONICAL_KEYS
    assert d_none == {"schema_version": CHANNEL_CONFIG_CONTRACT_ID, "mode": "none", "alpha": None}
    assert ChannelConfig.from_dict(d_none) == cfg_none

    cfg_lp = ChannelConfig(mode="legacy_lowpass", alpha=0.12)
    d_lp = cfg_lp.to_dict()
    assert list(d_lp.keys()) == CANONICAL_KEYS
    assert d_lp == {"schema_version": CHANNEL_CONFIG_CONTRACT_ID, "mode": "legacy_lowpass", "alpha": 0.12}
    assert ChannelConfig.from_dict(d_lp) == cfg_lp

    # Resolved config round-trip
    wave = np.array([1.0, 0.0])
    res = apply_channel(wave, ChannelConfig(mode="legacy_lowpass"))
    resolved = res.resolved_config
    assert resolved.alpha == 0.08
    assert ChannelConfig.from_dict(resolved.to_dict()) == resolved


def test_serialization_error_rejections():
    """Verify from_dict rejects non-mapping, missing keys, extra keys, and invalid schema_version."""
    with pytest.raises(TypeError, match="must be a Mapping"):
        ChannelConfig.from_dict("not_a_mapping")

    valid_dict = ChannelConfig(mode="none").to_dict()

    # Missing key
    missing_dict = valid_dict.copy()
    del missing_dict["alpha"]
    with pytest.raises(ValueError, match="missing keys"):
        ChannelConfig.from_dict(missing_dict)

    # Extra key
    extra_dict = valid_dict.copy()
    extra_dict["extra_param"] = 123
    with pytest.raises(ValueError, match="extra keys"):
        ChannelConfig.from_dict(extra_dict)

    # Non-string schema_version
    bad_type_dict = valid_dict.copy()
    bad_type_dict["schema_version"] = 12345
    with pytest.raises(TypeError, match="schema_version in dict must be str"):
        ChannelConfig.from_dict(bad_type_dict)

    # Unknown schema_version
    bad_ver_dict = valid_dict.copy()
    bad_ver_dict["schema_version"] = "pcie_eq-channel-config-v999"
    with pytest.raises(ValueError, match="Unknown schema_version"):
        ChannelConfig.from_dict(bad_ver_dict)
