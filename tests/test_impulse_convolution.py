"""
Unit tests for pcie_eq.impulse_convolution core module.

Verifies:
1. Public API surface, frozen dataclasses, frozen instance mutation rejections, and exact ImpulseConvolutionConfig type/subclass check.
2. Configuration validation, defensive re-validation, zero-index range check, and fixed validation order (config -> wave -> impulse).
3. Wave and impulse input validation: list/tuple/ndarray, scalar/2D/complex/string/object/NaN/Inf rejection, empty impulse rejection, and empty wave acceptance.
4. Mathematical golden cases (full, same, valid, delta alignment, integer promotion, single-tap, all-zero, non-centered zero-index, M > N same mode, mixed signed/unsigned).
5. Exact dtype contract across float/int/bool combinations and comprehensive empty wave matrix for all modes.
6. Helper contract failures and mode="full" only verification via monkeypatching (working & caller memory aliasing, final output ownership isolation).
7. Serialization to_dict() / from_dict() canonical 3-key order, new dictionary allocation per call, input & resolved config round-trips, and error handling.
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

    # Tuple wave & tuple impulse acceptance
    res_tuples = convolve_impulse((1.0, 2.0), (1.0,), cfg)
    assert np.array_equal(res_tuples.values, np.array([1.0, 2.0]))

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

    with pytest.raises(TypeError, match="real numeric"):
        convolve_impulse(np.array([object()]), [1.0], cfg)
    with pytest.raises(TypeError, match="real numeric"):
        convolve_impulse([1.0], np.array([object()]), cfg)

    # NaN / Inf rejection
    with pytest.raises(ValueError, match="wave input elements must be finite"):
        convolve_impulse([1.0, math.nan], [1.0], cfg)
    with pytest.raises(ValueError, match="impulse input elements must be finite"):
        convolve_impulse([1.0], [1.0, math.inf], cfg)

    # Empty impulse rejection
    with pytest.raises(ValueError, match="impulse input must not be empty"):
        convolve_impulse([1.0], [], cfg)

    # Impulse zero index >= len(impulse) rejection
    with pytest.raises(ValueError, match=r"impulse_zero_index \(2\) must be < len\(impulse\) \(2\)"):
        convolve_impulse([1.0], [1.0, 0.5], ImpulseConvolutionConfig(impulse_zero_index=2))


def test_empty_wave_comprehensive_dtype_matrix():
    """Verify empty wave input returns shape (0,) empty array with start_index 0 without calling np.convolve across all modes and dtypes."""
    empty_waves = [
        np.array([], dtype=np.bool_),
        np.array([], dtype=np.int8),
        np.array([], dtype=np.int16),
        np.array([], dtype=np.int32),
        np.array([], dtype=np.int64),
        np.array([], dtype=np.uint8),
        np.array([], dtype=np.uint16),
        np.array([], dtype=np.uint32),
        np.array([], dtype=np.uint64),
        np.array([], dtype=np.float16),
        np.array([], dtype=np.float32),
        np.array([], dtype=np.float64),
        [],
        (),
    ]

    impulse_f32 = np.array([0.5, 1.0], dtype=np.float32)

    for mode in ["full", "same", "valid"]:
        cfg = ImpulseConvolutionConfig(mode=mode, impulse_zero_index=0)
        for empty_w in empty_waves:
            res = convolve_impulse(empty_w, impulse_f32, cfg)

            assert res.values.shape == (0,)
            assert res.output_start_index == 0
            assert res.model_level == "discrete_linear_convolution"

            # Check expected dtype
            w_dt = np.asarray(empty_w).dtype
            promoted = np.result_type(w_dt, impulse_f32.dtype)
            expected_dt = promoted if promoted.kind == "f" else np.dtype(np.float64)
            assert res.values.dtype == expected_dt


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


def test_mathematical_edge_cases():
    """Verify single-tap impulse, all-zero impulse, non-centered zero-index, M > N same mode, and mixed signed/unsigned."""
    # Single-tap impulse
    w = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    h_single = np.array([2.0], dtype=np.float64)
    res_single_full = convolve_impulse(w, h_single, ImpulseConvolutionConfig(mode="full", impulse_zero_index=0))
    assert np.allclose(res_single_full.values, [2.0, 4.0, 6.0])
    assert res_single_full.output_start_index == 0

    res_single_same = convolve_impulse(w, h_single, ImpulseConvolutionConfig(mode="same", impulse_zero_index=0))
    assert np.allclose(res_single_same.values, [2.0, 4.0, 6.0])

    res_single_valid = convolve_impulse(w, h_single, ImpulseConvolutionConfig(mode="valid", impulse_zero_index=0))
    assert np.allclose(res_single_valid.values, [2.0, 4.0, 6.0])

    # All-zero impulse
    h_zeros = np.array([0.0, 0.0], dtype=np.float64)
    res_zeros = convolve_impulse(w, h_zeros, ImpulseConvolutionConfig(mode="full", impulse_zero_index=0))
    assert np.allclose(res_zeros.values, [0.0, 0.0, 0.0, 0.0])
    assert res_zeros.values.dtype == np.float64

    # Non-centered impulse_zero_index (z = 2)
    h_noncentered = np.array([0.1, 0.2, 1.0, 0.3], dtype=np.float64)
    res_nc_full = convolve_impulse(w, h_noncentered, ImpulseConvolutionConfig(mode="full", impulse_zero_index=2))
    assert res_nc_full.output_start_index == -2

    res_nc_same = convolve_impulse(w, h_noncentered, ImpulseConvolutionConfig(mode="same", impulse_zero_index=2))
    assert res_nc_same.output_start_index == 0

    # same mode with impulse longer than wave (M = 4 > N = 2)
    w_short = np.array([1.0, 2.0], dtype=np.float64)
    h_long = np.array([0.5, 1.0, 0.5, 0.25], dtype=np.float64)
    res_long_same = convolve_impulse(w_short, h_long, ImpulseConvolutionConfig(mode="same", impulse_zero_index=1))
    full_oracle = np.convolve(w_short, h_long, mode="full")
    assert res_long_same.values.shape == (2,)
    assert np.allclose(res_long_same.values, full_oracle[1:3])
    assert res_long_same.output_start_index == 0

    # Signed + unsigned mixed dtype -> float64
    w_signed = np.array([1, 2], dtype=np.int16)
    h_unsigned = np.array([1, 1], dtype=np.uint8)
    res_mixed = convolve_impulse(w_signed, h_unsigned, ImpulseConvolutionConfig(mode="full", impulse_zero_index=0))
    assert res_mixed.values.dtype == np.float64
    assert np.allclose(res_mixed.values, [1.0, 3.0, 2.0])


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


def test_helper_ownership_failures_and_mode_full_only_check(monkeypatch):
    """Verify production calls np.convolve with mode='full' ONLY, and raises RuntimeError on working/caller memory aliasing."""
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

    # Test working and caller array memory aliasing rejection
    cfg_full = ImpulseConvolutionConfig(mode="full", impulse_zero_index=0)

    # 1. Helper returns wave_work object (using integer input promoted to float64 working buffer: len=3 wave, len=1 impulse)
    w_int3 = np.array([1, 2, 3], dtype=np.int32)
    h_int1 = np.array([1], dtype=np.int32)

    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": w)
    with pytest.raises(RuntimeError, match="Convolution helper output aliases input object"):
        convolve_impulse(w_int3, h_int1, cfg_full)

    # 2. Helper returns wave_work.view()
    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": w.view())
    with pytest.raises(RuntimeError, match="Convolution helper output shares memory with working input"):
        convolve_impulse(w_int3, h_int1, cfg_full)

    # 3. Helper returns impulse_work object (len=1 wave, len=3 impulse)
    w_int1 = np.array([1], dtype=np.int32)
    h_int3 = np.array([1, 2, 3], dtype=np.int32)

    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": h)
    with pytest.raises(RuntimeError, match="Convolution helper output aliases input object"):
        convolve_impulse(w_int1, h_int3, cfg_full)

    # 4. Helper returns impulse_work.view()
    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": h.view())
    with pytest.raises(RuntimeError, match="Convolution helper output shares memory with working input"):
        convolve_impulse(w_int1, h_int3, cfg_full)

    # 5. Helper returns caller wave object (float64 wave so wave_work IS caller_wave)
    w_f64_3 = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    h_f64_1 = np.array([1.0], dtype=np.float64)

    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": w_f64_3)
    with pytest.raises(RuntimeError, match="Convolution helper output aliases input object"):
        convolve_impulse(w_f64_3, h_f64_1, cfg_full)

    # 6. Helper returns caller wave view
    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": w_f64_3.view())
    with pytest.raises(RuntimeError, match="Convolution helper output shares memory with working input"):
        convolve_impulse(w_f64_3, h_f64_1, cfg_full)

    # 7. Helper returns caller impulse object
    w_f64_1 = np.array([1.0], dtype=np.float64)
    h_f64_3 = np.array([1.0, 2.0, 3.0], dtype=np.float64)

    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": h_f64_3)
    with pytest.raises(RuntimeError, match="Convolution helper output aliases input object"):
        convolve_impulse(w_f64_1, h_f64_3, cfg_full)

    # 8. Helper returns caller impulse view
    monkeypatch.setattr(np, "convolve", lambda w, h, mode="full": h_f64_3.view())
    with pytest.raises(RuntimeError, match="Convolution helper output shares memory with working input"):
        convolve_impulse(w_f64_1, h_f64_3, cfg_full)


def test_final_output_ownership_and_slice_isolation(monkeypatch):
    """Verify same and valid modes produce new slice copies isolated from raw full helper output, while full mode may return raw output."""
    raw_saved = {}

    def monkey_save(w, h, mode="full"):
        raw = orig_convolve(w, h, mode=mode)
        raw_saved["raw"] = raw
        return raw

    orig_convolve = np.convolve
    monkeypatch.setattr(np, "convolve", monkey_save)

    w = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    h = np.array([0.5, 1.0, 0.25], dtype=np.float64)

    # full mode: values may be validated raw helper output
    res_full = convolve_impulse(w, h, ImpulseConvolutionConfig(mode="full", impulse_zero_index=1))
    raw_full = raw_saved["raw"]
    assert res_full.values is raw_full

    # same mode: values MUST NOT share memory with raw helper output
    res_same = convolve_impulse(w, h, ImpulseConvolutionConfig(mode="same", impulse_zero_index=1))
    raw_same = raw_saved["raw"]
    assert not np.shares_memory(res_same.values, raw_same)
    assert res_same.values is not raw_same

    # valid mode: values MUST NOT share memory with raw helper output
    res_valid = convolve_impulse(w, h, ImpulseConvolutionConfig(mode="valid", impulse_zero_index=1))
    raw_valid = raw_saved["raw"]
    assert not np.shares_memory(res_valid.values, raw_valid)
    assert res_valid.values is not raw_valid


def test_serialization_canonical_keys_order_and_round_trip():
    """Verify to_dict() returns new dict per call, 3-key canonical order, and input & resolved config round-trips."""
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

    # Resolved config round-trip
    res = convolve_impulse([1.0, 2.0], [1.0], ImpulseConvolutionConfig(mode="same", impulse_zero_index=0))
    resolved_cfg = res.resolved_config
    serialized_resolved = resolved_cfg.to_dict()
    restored_resolved = ImpulseConvolutionConfig.from_dict(serialized_resolved)

    assert restored_resolved == resolved_cfg
    assert restored_resolved is not resolved_cfg


def test_serialization_error_rejections():
    """Verify from_dict rejects non-mapping, missing keys, extra keys, non-str version, and unknown version."""
    with pytest.raises(TypeError, match="must be a Mapping"):
        ImpulseConvolutionConfig.from_dict("not_a_mapping")

    valid_dict = ImpulseConvolutionConfig(mode="full").to_dict()

    missing_dict = valid_dict.copy()
    del missing_dict["impulse_zero_index"]
    with pytest.raises(ValueError, match="missing keys"):
        ImpulseConvolutionConfig.from_dict(missing_dict)

    extra_dict = valid_dict.copy()
    extra_dict["extra_param"] = 123
    with pytest.raises(ValueError, match="extra keys"):
        ImpulseConvolutionConfig.from_dict(extra_dict)

    bad_type_dict = valid_dict.copy()
    bad_type_dict["schema_version"] = 12345
    with pytest.raises(TypeError, match="schema_version in dict must be str"):
        ImpulseConvolutionConfig.from_dict(bad_type_dict)

    bad_ver_dict = valid_dict.copy()
    bad_ver_dict["schema_version"] = "pcie_eq-impulse-convolution-v999"
    with pytest.raises(ValueError, match="Unknown schema_version"):
        ImpulseConvolutionConfig.from_dict(bad_ver_dict)
