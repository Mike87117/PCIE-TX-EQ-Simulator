"""
Unit tests for pcie_eq.impulse_convolution core module.

Verifies:
1. Public API surface, frozen dataclasses, frozen instance mutation rejections, and exact ImpulseConvolutionConfig type/subclass check.
2. Configuration validation, defensive re-validation, zero-index range check, and fixed validation order (config -> wave -> impulse).
3. Wave and impulse input validation: list/tuple/ndarray, scalar/2D/complex/string/NaN/Inf rejection, empty impulse rejection, and empty wave acceptance.
4. Mathematical golden cases (full, same, valid, delta alignment, integer promotion) & independent direct summation oracle.
5. Exact dtype contract across float/int/bool combinations and empty wave matrix.
6. Helper contract failures and mode="full" only verification via monkeypatching.
7. Serialization to_dict() / from_dict() canonical 3-key order, new dictionary allocation per call, round-trip, and error handling.
"""

from dataclasses import FrozenInstanceError
import math
import numpy as np
import pytest

import pcie_eq.impulse_convolution as impulse_convolution
from pcie_eq.impulse_convolution import (
    IMPULSE_CONVOLUTION_CONTRACT_ID,
    ImpulseConvolutionConfig,
    ImpulseConvolutionResult,
    convolve_impulse,
    CANONICAL_KEYS,
)


def test_impulse_convolution_frozen_mutation_and_subclass_rejection():
    """Verify ImpulseConvolutionConfig and ImpulseConvolutionResult reject mutations and subclasses."""
    cfg = ImpulseConvolutionConfig(mode="full")
    with pytest.raises((FrozenInstanceError, AttributeError)):
        cfg.mode = "same"

    res = convolve_impulse([1.0], [1.0], cfg)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        res.output_start_index = 999

    class SubConfig(ImpulseConvolutionConfig):
        pass

    sub_cfg = SubConfig(mode="full")
    with pytest.raises(TypeError, match="must be exactly ImpulseConvolutionConfig"):
        convolve_impulse([1.0], [1.0], sub_cfg)


def test_validation_and_input_evaluation_order():
    """Verify validation order: config re-validation -> wave conversion -> impulse conversion."""
    class Explosive:
        def __array__(self):
            raise RuntimeError("Should not be converted!")

    # Corrupted config fails before wave conversion
    corrupted_cfg = ImpulseConvolutionConfig(mode="full")
    object.__setattr__(corrupted_cfg, "mode", "invalid_mode")
    with pytest.raises(ValueError, match="Unsupported mode"):
        convolve_impulse(Explosive(), Explosive(), corrupted_cfg)

    # Wave error fails before impulse conversion
    valid_cfg = ImpulseConvolutionConfig(mode="full")
    with pytest.raises(ValueError, match="wave input must be 1D"):
        convolve_impulse(np.array([[1.0]]), Explosive(), valid_cfg)


def test_config_field_validations():
    """Verify strict type and range validations on ImpulseConvolutionConfig fields."""
    # schema_version validation
    with pytest.raises(TypeError, match="schema_version must be str"):
        ImpulseConvolutionConfig(schema_version=123)
    with pytest.raises(ValueError, match="Unknown schema_version"):
        ImpulseConvolutionConfig(schema_version="invalid_ver")

    # mode validation
    with pytest.raises(TypeError, match="mode must be str"):
        ImpulseConvolutionConfig(mode=123)
    with pytest.raises(ValueError, match="Unsupported mode"):
        ImpulseConvolutionConfig(mode="FULL")
    with pytest.raises(ValueError, match="Unsupported mode"):
        ImpulseConvolutionConfig(mode="full ")

    # impulse_zero_index validation (must be exact int, not bool or numpy int)
    for invalid_z in [True, False, np.int32(0), np.int64(1), 1.5, "0"]:
        with pytest.raises(TypeError, match="impulse_zero_index must be int"):
            ImpulseConvolutionConfig(impulse_zero_index=invalid_z)

    with pytest.raises(ValueError, match="impulse_zero_index must be >= 0"):
        ImpulseConvolutionConfig(impulse_zero_index=-1)


def test_wave_and_impulse_input_validations():
    """Verify wave and impulse input type, shape, dtype, finiteness, and zero-index range validations."""
    cfg = ImpulseConvolutionConfig(mode="full")

    # Scalar & 2D rejection for wave & impulse
    with pytest.raises(ValueError, match="wave input must be 1D"):
        convolve_impulse(5.0, [1.0], cfg)
    with pytest.raises(ValueError, match="impulse input must be 1D"):
        convolve_impulse([1.0], 5.0, cfg)

    with pytest.raises(ValueError, match="wave input must be 1D"):
        convolve_impulse(np.array([[1.0]]), [1.0], cfg)
    with pytest.raises(ValueError, match="impulse input must be 1D"):
        convolve_impulse([1.0], np.array([[1.0]]), cfg)

    # Complex, string, object rejection
    with pytest.raises(TypeError, match="real numeric"):
        convolve_impulse(np.array([1 + 1j]), [1.0], cfg)
    with pytest.raises(TypeError, match="real numeric"):
        convolve_impulse([1.0], np.array([1 + 1j]), cfg)

    with pytest.raises(TypeError, match="real numeric"):
        convolve_impulse(np.array(["1.0"]), [1.0], cfg)
    with pytest.raises(TypeError, match="real numeric"):
        convolve_impulse([1.0], np.array(["1.0"]), cfg)

    # NaN / Inf rejection
    with pytest.raises(ValueError, match="wave input elements must be finite"):
        convolve_impulse([1.0, math.nan], [1.0], cfg)
    with pytest.raises(ValueError, match="impulse input elements must be finite"):
        convolve_impulse([1.0], [1.0, math.inf], cfg)

    # Empty impulse rejection
    with pytest.raises(ValueError, match="impulse input must not be empty"):
        convolve_impulse([1.0], [], cfg)

    # Impulse zero index >= len(impulse) rejection
    with pytest.raises(ValueError, match="impulse_zero_index .* must be < len"):
        convolve_impulse([1.0], [1.0, 0.5], ImpulseConvolutionConfig(impulse_zero_index=2))


def test_empty_wave_acceptance_across_modes():
    """Verify empty wave input returns shape (0,) empty array with start_index 0 without calling np.convolve."""
    impulse = [0.5, 1.0, 0.25]
    impulse_f32 = np.array(impulse, dtype=np.float32)
    empty_wave_f32 = np.array([], dtype=np.float32)

    for mode in ["full", "same", "valid"]:
        cfg = ImpulseConvolutionConfig(mode=mode, impulse_zero_index=1)
        res = convolve_impulse(empty_wave_f32, impulse_f32, cfg)

        assert res.values.shape == (0,)
        assert res.values.dtype == np.float32
        assert res.output_start_index == 0
        assert res.model_level == "discrete_linear_convolution"


def test_golden_cases_full_same_valid_and_alignment():
    """Verify Section 14 canonical golden vectors and output start indices."""
    wave = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    impulse = np.array([0.5, 1.0, 0.25], dtype=np.float64)
    z = 1

    # 14.1 Full
    cfg_full = ImpulseConvolutionConfig(mode="full", impulse_zero_index=z)
    res_full = convolve_impulse(wave, impulse, cfg_full)
    assert res_full.values.dtype == np.float64
    assert res_full.values.shape == (6,)
    assert res_full.output_start_index == -1
    assert np.allclose(res_full.values, np.array([0.5, 2.0, 3.75, 5.5, 4.75, 1.0]))

    # 14.2 Same
    cfg_same = ImpulseConvolutionConfig(mode="same", impulse_zero_index=z)
    res_same = convolve_impulse(wave, impulse, cfg_same)
    assert res_same.values.dtype == np.float64
    assert res_same.values.shape == (4,)
    assert res_same.output_start_index == 0
    assert np.allclose(res_same.values, np.array([2.0, 3.75, 5.5, 4.75]))

    # 14.3 Valid
    cfg_valid = ImpulseConvolutionConfig(mode="valid", impulse_zero_index=z)
    res_valid = convolve_impulse(wave, impulse, cfg_valid)
    assert res_valid.values.dtype == np.float64
    assert res_valid.values.shape == (2,)
    assert res_valid.output_start_index == 1
    assert np.allclose(res_valid.values, np.array([3.75, 5.5]))

    # 14.4 Delta Alignment
    delta_impulse = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    res_delta = convolve_impulse(wave, delta_impulse, ImpulseConvolutionConfig(mode="same", impulse_zero_index=1))
    assert res_delta.output_start_index == 0
    assert np.array_equal(res_delta.values, wave)

    # 14.5 Integer Promotion
    wave_int = np.array([1, 2, 3], dtype=np.int16)
    impulse_int = np.array([1, 1], dtype=np.int8)
    res_int = convolve_impulse(wave_int, impulse_int, ImpulseConvolutionConfig(mode="full", impulse_zero_index=0))
    assert res_int.values.dtype == np.float64
    assert np.allclose(res_int.values, np.array([1.0, 3.0, 5.0, 3.0]))


def test_independent_direct_summation_oracle():
    """Verify convolve_impulse against test-side independent direct summation formulation."""
    def test_side_direct_convolve(w, h):
        N, M = len(w), len(h)
        out = []
        for j in range(N + M - 1):
            s = 0.0
            for k in range(max(0, j - M + 1), min(N, j + 1)):
                s += float(w[k]) * float(h[j - k])
            out.append(s)
        return np.array(out, dtype=np.float64)

    w = np.array([0.5, -1.0, 2.0, 0.0, -0.5], dtype=np.float64)
    h = np.array([1.0, -0.5, 0.25], dtype=np.float64)

    expected_full = test_side_direct_convolve(w, h)
    res = convolve_impulse(w, h, ImpulseConvolutionConfig(mode="full", impulse_zero_index=0))
    assert np.allclose(res.values, expected_full)


def test_valid_mode_length_rejection():
    """Verify valid mode raises ValueError when len(wave) < len(impulse)."""
    wave_short = [1.0, 2.0]
    impulse_long = [0.5, 1.0, 0.25]
    cfg_valid = ImpulseConvolutionConfig(mode="valid", impulse_zero_index=0)
    with pytest.raises(ValueError, match=r"valid mode requires len\(wave\) .* >= len\(impulse\)"):
        convolve_impulse(wave_short, impulse_long, cfg_valid)


def test_non_contiguous_input_views_and_non_aliasing():
    """Verify non-contiguous input views produce independent C-contiguous output without aliasing."""
    wave_full = np.arange(10, dtype=np.float64)
    impulse_full = np.array([1.0, 0.5, 0.25, 0.125], dtype=np.float64)

    wave_view = wave_full[::2]
    impulse_view = impulse_full[::2]
    assert not wave_view.flags.c_contiguous
    assert not impulse_view.flags.c_contiguous

    res = convolve_impulse(wave_view, impulse_view, ImpulseConvolutionConfig(mode="full", impulse_zero_index=0))
    assert res.values.flags.c_contiguous
    assert not np.shares_memory(res.values, wave_full)
    assert not np.shares_memory(res.values, impulse_full)


def test_dtype_promotion_matrix():
    """Verify promotion matrix for floating and integer/bool combinations."""
    cfg = ImpulseConvolutionConfig(mode="full")

    # bool + bool -> float64
    res_b = convolve_impulse([True, False], [True], cfg)
    assert res_b.values.dtype == np.float64

    # float16 + float16 -> float16
    res_f16 = convolve_impulse(np.array([1.0], dtype=np.float16), np.array([1.0], dtype=np.float16), cfg)
    assert res_f16.values.dtype == np.float16

    # float32 + float32 -> float32
    res_f32 = convolve_impulse(np.array([1.0], dtype=np.float32), np.array([1.0], dtype=np.float32), cfg)
    assert res_f32.values.dtype == np.float32

    # float32 + float64 -> float64
    res_f32_f64 = convolve_impulse(np.array([1.0], dtype=np.float32), np.array([1.0], dtype=np.float64), cfg)
    assert res_f32_f64.values.dtype == np.float64

    # float32 + int16 -> float32
    res_f32_i16 = convolve_impulse(np.array([1.0], dtype=np.float32), np.array([1], dtype=np.int16), cfg)
    assert res_f32_i16.values.dtype == np.float32


def test_helper_contract_failures_and_mode_full_only_check(monkeypatch):
    """Verify production calls np.convolve with mode='full' ONLY, skips on empty wave, and raises RuntimeError on helper contract failures."""
    calls = []
    orig_convolve = np.convolve

    def tracked_convolve(w, h, mode="full"):
        calls.append(mode)
        return orig_convolve(w, h, mode=mode)

    monkeypatch.setattr(np, "convolve", tracked_convolve)

    cfg_same = ImpulseConvolutionConfig(mode="same", impulse_zero_index=0)
    convolve_impulse([1.0, 2.0], [1.0], cfg_same)
    assert calls == ["full"]

    # Empty wave skips np.convolve
    calls.clear()
    convolve_impulse([], [1.0], cfg_same)
    assert calls == []

    # RuntimeError checks for bad helper outputs
    cfg_full = ImpulseConvolutionConfig(mode="full")
    wave = [1.0, 2.0]
    impulse = [1.0]

    # Non-ndarray helper output
    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": [1.0, 2.0])
    with pytest.raises(RuntimeError, match="not exact np.ndarray"):
        convolve_impulse(wave, impulse, cfg_full)

    # Subclass helper output
    class SubNdArray(np.ndarray):
        pass

    sub_out = np.array([1.0, 2.0], dtype=np.float64).view(SubNdArray)
    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": sub_out)
    with pytest.raises(RuntimeError, match="not exact np.ndarray"):
        convolve_impulse(wave, impulse, cfg_full)

    # Bad shape helper output
    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": np.array([1.0]))
    with pytest.raises(RuntimeError, match="shape mismatch"):
        convolve_impulse(wave, impulse, cfg_full)

    # Bad dtype helper output
    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": np.array([1, 2], dtype=np.int32))
    with pytest.raises(RuntimeError, match="dtype mismatch"):
        convolve_impulse(wave, impulse, cfg_full)

    # Non-contiguous helper output
    non_c = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)[:, 0]
    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": non_c)
    with pytest.raises(RuntimeError, match="not C-contiguous"):
        convolve_impulse(wave, impulse, cfg_full)

    # Non-finite helper output
    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": np.array([1.0, math.nan], dtype=np.float64))
    with pytest.raises(RuntimeError, match="non-finite values"):
        convolve_impulse(wave, impulse, cfg_full)


def test_serialization_canonical_keys_order_and_round_trip():
    """Verify to_dict() returns new dict per call, 3-key canonical order, and round-trip consistency."""
    cfg = ImpulseConvolutionConfig(mode="same", impulse_zero_index=2)
    d1 = cfg.to_dict()
    d2 = cfg.to_dict()

    assert d1 is not d2
    assert list(d1.keys()) == CANONICAL_KEYS
    assert d1 == {
        "schema_version": IMPULSE_CONVOLUTION_CONTRACT_ID,
        "mode": "same",
        "impulse_zero_index": 2,
    }

    d1["mode"] = "modified"
    assert cfg.to_dict()["mode"] == "same"

    restored = ImpulseConvolutionConfig.from_dict(d2)
    assert restored == cfg


def test_serialization_error_rejections():
    """Verify from_dict rejects non-mapping, missing keys, extra keys, non-str version, and unknown version."""
    with pytest.raises(TypeError, match="must be a Mapping"):
        ImpulseConvolutionConfig.from_dict("not_a_mapping")

    valid_dict = ImpulseConvolutionConfig(mode="full").to_dict()

    # Missing key
    missing_dict = valid_dict.copy()
    del missing_dict["impulse_zero_index"]
    with pytest.raises(ValueError, match="missing keys"):
        ImpulseConvolutionConfig.from_dict(missing_dict)

    # Extra key
    extra_dict = valid_dict.copy()
    extra_dict["extra_param"] = 123
    with pytest.raises(ValueError, match="extra keys"):
        ImpulseConvolutionConfig.from_dict(extra_dict)

    # Non-string schema_version
    bad_type_dict = valid_dict.copy()
    bad_type_dict["schema_version"] = 12345
    with pytest.raises(TypeError, match="schema_version in dict must be str"):
        ImpulseConvolutionConfig.from_dict(bad_type_dict)

    # Unknown schema_version
    bad_ver_dict = valid_dict.copy()
    bad_ver_dict["schema_version"] = "pcie_eq-impulse-convolution-v999"
    with pytest.raises(ValueError, match="Unknown schema_version"):
        ImpulseConvolutionConfig.from_dict(bad_ver_dict)
