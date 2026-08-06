"""
Unit tests for pcie_eq.channel_config core module.

Verifies:
1. Public API surface, frozen dataclasses, frozen instance mutation rejections, and exact ChannelConfig type/subclass check.
2. Constructor & defensive re-validation for schema, mode, and alpha applicability/range before wave materialization.
3. Wave input validation: list/tuple/ndarray, scalar/2D/complex/string/NaN/Inf rejection.
4. none mode: identity copy, exact dtype matrix preservation (empty/non-empty), non-aliasing, and non-contiguous slice handling.
5. legacy_lowpass mode: default & explicit alpha golden cases, float preservation, int/uint/bool/tuple promotion to float64, empty matrix, and direct simple_channel equivalence.
6. Helper contract failures via monkeypatch (type, subclass, shape, dtype, contiguity, alias/caller return, non-finite).
7. Serialization to_dict() / from_dict() canonical 3-key order, new dictionary allocation per call, round-trip, and error handling.
"""

from dataclasses import FrozenInstanceError
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


def test_channel_config_and_result_frozen_mutation_rejection():
    """Verify ChannelConfig and ChannelResult instances reject attribute mutations."""
    cfg = ChannelConfig(mode="none")
    with pytest.raises((FrozenInstanceError, AttributeError)):
        cfg.mode = "legacy_lowpass"

    res = apply_channel(np.array([1.0, 0.0]), cfg)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        res.model_level = "other"


def test_channel_config_subclass_rejection():
    """Verify apply_channel rejects ChannelConfig subclasses with TypeError."""
    class SubChannelConfig(ChannelConfig):
        pass

    sub_cfg = SubChannelConfig(mode="none")
    with pytest.raises(TypeError, match="must be exactly ChannelConfig, got SubChannelConfig"):
        apply_channel(np.array([1.0, 0.0]), sub_cfg)


def test_config_validation_occurs_before_wave_materialization():
    """Verify corrupted config validation fails prior to attempting wave materialization."""
    class ExplosiveWave:
        def __array__(self):
            raise RuntimeError("Wave should not be materialized!")

    corrupted_cfg = ChannelConfig(mode="none")
    object.__setattr__(corrupted_cfg, "mode", "invalid_mode")

    with pytest.raises(ValueError, match="Unsupported mode"):
        apply_channel(ExplosiveWave(), corrupted_cfg)


def test_numpy_scalar_alpha_rejection():
    """Verify NumPy scalar alphas (int32, float32, float64) are rejected with TypeError."""
    with pytest.raises(TypeError, match="alpha must be int, float, or None"):
        ChannelConfig(mode="legacy_lowpass", alpha=np.int32(1))

    with pytest.raises(TypeError, match="alpha must be int, float, or None"):
        ChannelConfig(mode="legacy_lowpass", alpha=np.float32(0.08))

    with pytest.raises(TypeError, match="alpha must be int, float, or None"):
        ChannelConfig(mode="legacy_lowpass", alpha=np.float64(0.08))


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
        ChannelConfig(mode="NONE")
    with pytest.raises(ValueError, match="Unsupported mode"):
        ChannelConfig(mode="none ")

    # alpha applicability for mode none
    with pytest.raises(ValueError, match="not applicable for mode 'none'"):
        ChannelConfig(mode="none", alpha=0.08)

    # alpha validation for legacy_lowpass
    for invalid_alpha in [True, False, "0.08", (0.08,)]:
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
    """Verify none mode produces non-aliasing C-contiguous identity copy across all dtypes (including empty cases)."""
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
        # Non-empty case
        wave = np.array([0, 1, 0, 1], dtype=dt)
        res = apply_channel(wave, cfg)
        assert res.model_level == "identity"
        assert res.resolved_config.alpha is None
        assert res.values.dtype == dt
        assert res.values.shape == wave.shape
        assert res.values.flags.c_contiguous
        assert res.values is not wave
        assert not np.shares_memory(res.values, wave)
        assert np.array_equal(res.values, wave)

        # Empty case
        empty_wave = np.array([], dtype=dt)
        res_empty = apply_channel(empty_wave, cfg)
        assert res_empty.values.dtype == dt
        assert res_empty.values.shape == (0,)
        assert res_empty.values is not empty_wave
        assert not np.shares_memory(res_empty.values, empty_wave)

    # Empty list [] & tuple () for none mode
    res_empty_list = apply_channel([], cfg)
    assert res_empty_list.values.shape == (0,)
    res_empty_tuple = apply_channel((), cfg)
    assert res_empty_tuple.values.shape == (0,)

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


def test_legacy_lowpass_empty_inputs_dtype_matrix_cases():
    """Verify empty input handling in legacy_lowpass preserves float dtypes and promotes int/uint/bool/tuple to float64."""
    cfg = ChannelConfig(mode="legacy_lowpass")

    # Empty float32 -> empty float32
    empty_f32 = np.array([], dtype=np.float32)
    res_f32 = apply_channel(empty_f32, cfg)
    assert res_f32.values.dtype == np.float32
    assert res_f32.values.shape == (0,)

    # Empty float64 -> empty float64
    empty_f64 = np.array([], dtype=np.float64)
    res_f64 = apply_channel(empty_f64, cfg)
    assert res_f64.values.dtype == np.float64
    assert res_f64.values.shape == (0,)

    # Empty bool -> empty float64
    empty_bool = np.array([], dtype=np.bool_)
    res_bool = apply_channel(empty_bool, cfg)
    assert res_bool.values.dtype == np.float64
    assert res_bool.values.shape == (0,)

    # Empty uint8 -> empty float64
    empty_u8 = np.array([], dtype=np.uint8)
    res_u8 = apply_channel(empty_u8, cfg)
    assert res_u8.values.dtype == np.float64
    assert res_u8.values.shape == (0,)

    # Empty tuple () -> empty float64
    res_tuple = apply_channel((), cfg)
    assert res_tuple.values.dtype == np.float64
    assert res_tuple.values.shape == (0,)


def test_helper_contract_failures_raise_runtime_error(monkeypatch):
    """Verify apply_channel raises RuntimeError if simple_channel output breaks contract (including subclass and caller alias)."""
    cfg = ChannelConfig(mode="legacy_lowpass")
    wave = np.array([1.0, 0.0], dtype=np.float64)

    # Helper returns non-ndarray
    monkeypatch.setattr(channel_config, "simple_channel", lambda w, alpha: [1.0, 0.0])
    with pytest.raises(RuntimeError, match="not exact np.ndarray"):
        apply_channel(wave, cfg)

    # Helper returns ndarray subclass
    class SubNdArray(np.ndarray):
        pass

    sub_arr = np.array([1.0, 0.0], dtype=np.float64).view(SubNdArray)
    monkeypatch.setattr(channel_config, "simple_channel", lambda w, alpha: sub_arr)
    with pytest.raises(RuntimeError, match="not exact np.ndarray"):
        apply_channel(wave, cfg)

    # Helper returns caller object for empty array (values is arr)
    empty_wave = np.array([], dtype=np.float64)
    monkeypatch.setattr(channel_config, "simple_channel", lambda w, alpha: empty_wave)
    with pytest.raises(RuntimeError, match="memory aliases caller input"):
        apply_channel(empty_wave, cfg)

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

    # Helper returns aliased memory (shares_memory)
    monkeypatch.setattr(channel_config, "simple_channel", lambda w, alpha: wave)
    with pytest.raises(RuntimeError, match="memory aliases caller input"):
        apply_channel(wave, cfg)

    # Helper returns non-finite values
    monkeypatch.setattr(channel_config, "simple_channel", lambda w, alpha: np.array([1.0, math.nan], dtype=np.float64))
    with pytest.raises(RuntimeError, match="non-finite values"):
        apply_channel(wave, cfg)


def test_serialization_canonical_keys_and_to_dict_allocation_isolation():
    """Verify to_dict() returns a new dictionary per call, 3-key canonical order, and round-trip consistency."""
    cfg_none = ChannelConfig(mode="none")
    d1 = cfg_none.to_dict()
    d2 = cfg_none.to_dict()

    assert d1 is not d2
    assert list(d1.keys()) == CANONICAL_KEYS
    assert d1 == {"schema_version": CHANNEL_CONFIG_CONTRACT_ID, "mode": "none", "alpha": None}

    d1["mode"] = "modified_mode"
    assert cfg_none.to_dict()["mode"] == "none"

    assert ChannelConfig.from_dict(d2) == cfg_none

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

    missing_dict = valid_dict.copy()
    del missing_dict["alpha"]
    with pytest.raises(ValueError, match="missing keys"):
        ChannelConfig.from_dict(missing_dict)

    extra_dict = valid_dict.copy()
    extra_dict["extra_param"] = 123
    with pytest.raises(ValueError, match="extra keys"):
        ChannelConfig.from_dict(extra_dict)

    bad_type_dict = valid_dict.copy()
    bad_type_dict["schema_version"] = 12345
    with pytest.raises(TypeError, match="schema_version in dict must be str"):
        ChannelConfig.from_dict(bad_type_dict)

    bad_ver_dict = valid_dict.copy()
    bad_ver_dict["schema_version"] = "pcie_eq-channel-config-v999"
    with pytest.raises(ValueError, match="Unknown schema_version"):
        ChannelConfig.from_dict(bad_ver_dict)
