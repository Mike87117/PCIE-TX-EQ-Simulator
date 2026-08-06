"""
Unit tests for pcie_eq.impulse_source core module.

Verifies:
1. Public API surface, dataclass field exact defaults, frozen dataclasses, frozen instance mutation rejections, and exact ImpulseSourceConfig type/subclass check.
2. Common field validations (schema, source_type, sample_interval, normalization variants, zero_index, defensive revalidation).
3. Restricted user_defined container input types: list, tuple, 1D ndarray accepted; range, generator, array.array, memoryview, and explosive __array__/__iter__ providers rejected with TypeError.
4. Deterministic relevance rules, validation order, and irrelevant field rejections without materializing values.
5. OverflowError protection for huge integer conversions across sample_interval, amplitude, and decay_ratio.
6. single_tap mode golden vectors, boundary zero-indices, signed zero, and zero-amplitude behavior.
7. exponential_postcursor mode golden vectors, direct formula comparison, decay_ratio=0, underflow, and ratio range rejections.
8. user_defined mode list/tuple/ndarray/non-contiguous view matrix, bool/int/uint/float16/32/64 to float64, scalar/0D ValueError rejections, and mutation isolation.
9. Decoupled build-time canonical validation: corrupted configs modified via object.__setattr__ fail build_impulse() without repair, preserving corrupted field state and never calling _build_values().
10. Output contract: exact float64 ndarray, C-contiguous, finite, new storage allocation, result mutation isolation, and internal _build_values failure matrix via monkeypatching.
11. Serialization to_dict() / from_dict() canonical 9-key order, new dict/list allocations, mapping validation order, round-trips, and error handling.
"""

import array
from dataclasses import FrozenInstanceError, fields
import math
import numpy as np
import pytest

import pcie_eq.impulse_source as impulse_source
from pcie_eq.impulse_source import (
    IMPULSE_SOURCE_CONTRACT_ID,
    ImpulseSourceConfig,
    ImpulseSourceResult,
    build_impulse,
    CANONICAL_KEYS,
)


def test_impulse_source_exact_defaults_and_signature():
    """Verify ImpulseSourceConfig dataclass field exact default values."""
    default_cfg = ImpulseSourceConfig()
    field_defaults = {f.name: f.default for f in fields(ImpulseSourceConfig)}

    assert field_defaults["source_type"] == "single_tap"
    assert field_defaults["sample_interval"] == 1.0
    assert field_defaults["impulse_zero_index"] == 0
    assert field_defaults["normalization"] == "none"
    assert field_defaults["length"] == 1
    assert field_defaults["amplitude"] == 1.0
    assert field_defaults["decay_ratio"] is None
    assert field_defaults["values"] is None
    assert field_defaults["schema_version"] == IMPULSE_SOURCE_CONTRACT_ID

    assert default_cfg.source_type == "single_tap"
    assert default_cfg.length == 1
    assert default_cfg.amplitude == 1.0


def test_impulse_source_frozen_mutation_and_subclass_rejection():
    """Verify ImpulseSourceConfig and ImpulseSourceResult reject attribute mutations and subclasses."""
    cfg = ImpulseSourceConfig()
    with pytest.raises((FrozenInstanceError, AttributeError)):
        cfg.source_type = "user_defined"

    res = build_impulse(cfg)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        res.model_level = "other"

    class SubConfig(ImpulseSourceConfig):
        pass

    sub_cfg = SubConfig()
    with pytest.raises(TypeError, match="must be exactly ImpulseSourceConfig"):
        build_impulse(sub_cfg)


def test_user_defined_restricted_container_types_and_explosive_rejections():
    """Verify user_defined accepts only list, tuple, 1D ndarray, and rejects range, generator, array.array, memoryview, and explosive providers."""
    # Allowed container types
    cfg_list = ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=[1.0, 2.0])
    cfg_tuple = ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=(1.0, 2.0))
    cfg_arr = ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=np.array([1.0, 2.0]))
    assert build_impulse(cfg_list).values.shape == (2,)
    assert build_impulse(cfg_tuple).values.shape == (2,)
    assert build_impulse(cfg_arr).values.shape == (2,)

    # Disallowed container types must raise TypeError without invoking __array__ or __iter__
    with pytest.raises(TypeError, match="must be a list, tuple, or 1D ndarray"):
        ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=range(3))

    with pytest.raises(TypeError, match="must be a list, tuple, or 1D ndarray"):
        ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=(x for x in [1.0, 2.0]))

    with pytest.raises(TypeError, match="must be a list, tuple, or 1D ndarray"):
        ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=array.array("d", [1.0, 2.0]))

    with pytest.raises(TypeError, match="must be a list, tuple, or 1D ndarray"):
        ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=memoryview(bytes(8)))

    class ExplosiveArrayProvider:
        def __array__(self):
            raise AssertionError("__array__ must not be called")

    class ExplosiveIterable:
        def __iter__(self):
            raise AssertionError("__iter__ must not be called")

    with pytest.raises(TypeError, match="must be a list, tuple, or 1D ndarray"):
        ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=ExplosiveArrayProvider())

    with pytest.raises(TypeError, match="must be a list, tuple, or 1D ndarray"):
        ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=ExplosiveIterable())


def test_explicit_none_rejection_for_synthetic_sources():
    """Verify synthetic sources reject explicit None for length and amplitude with TypeError."""
    with pytest.raises(TypeError, match="length must be int"):
        ImpulseSourceConfig(source_type="single_tap", length=None)

    with pytest.raises(TypeError, match="amplitude must be int or float"):
        ImpulseSourceConfig(source_type="single_tap", amplitude=None)

    with pytest.raises(TypeError, match="length must be int"):
        ImpulseSourceConfig(source_type="exponential_postcursor", decay_ratio=0.5, length=None)

    with pytest.raises(TypeError, match="amplitude must be int or float"):
        ImpulseSourceConfig(source_type="exponential_postcursor", decay_ratio=0.5, amplitude=None)


def test_normalization_variants_rejection():
    """Verify normalization rejects uppercase, whitespace, and non-none strings."""
    for invalid_norm in ["None", "NONE", "none ", " none", "", "peak"]:
        with pytest.raises(ValueError, match="Unsupported normalization"):
            ImpulseSourceConfig(normalization=invalid_norm)


def test_deterministic_relevance_and_validation_order():
    """Verify deterministic relevance validation order without materializing irrelevant values."""
    class Explosive:
        def __array__(self):
            raise RuntimeError("Should not be materialized!")

        def __iter__(self):
            raise RuntimeError("Should not be iterated!")

    # single_tap: decay_ratio is checked before values
    with pytest.raises(ValueError, match="Field 'decay_ratio' is irrelevant"):
        ImpulseSourceConfig(source_type="single_tap", decay_ratio=0.5, values=Explosive())

    # user_defined: length is checked before amplitude/decay_ratio/values conversion
    with pytest.raises(ValueError, match="Field 'length' is irrelevant"):
        ImpulseSourceConfig(
            source_type="user_defined",
            length=5,
            amplitude=None,
            decay_ratio=None,
            values=Explosive(),
        )


def test_overflow_error_protection_for_huge_integers():
    """Verify huge Python integers convert to ValueError without leaking OverflowError."""
    huge_pos = 10**400
    huge_neg = -(10**400)

    # sample_interval overflow
    with pytest.raises(ValueError, match="must remain finite"):
        ImpulseSourceConfig(sample_interval=huge_pos)

    # amplitude overflow
    with pytest.raises(ValueError, match="must remain finite"):
        ImpulseSourceConfig(amplitude=huge_pos)
    with pytest.raises(ValueError, match="must remain finite"):
        ImpulseSourceConfig(amplitude=huge_neg)

    # decay_ratio overflow
    with pytest.raises(ValueError, match="must remain finite"):
        ImpulseSourceConfig(source_type="exponential_postcursor", decay_ratio=huge_pos)


def test_common_field_validations():
    """Verify strict type and range validations on common ImpulseSourceConfig fields."""
    # schema_version validation
    with pytest.raises(TypeError, match="schema_version must be str"):
        ImpulseSourceConfig(schema_version=123)
    with pytest.raises(ValueError, match="Unknown schema_version"):
        ImpulseSourceConfig(schema_version="invalid_ver")

    # source_type validation
    with pytest.raises(TypeError, match="source_type must be str"):
        ImpulseSourceConfig(source_type=123)
    with pytest.raises(ValueError, match="Unsupported source_type"):
        ImpulseSourceConfig(source_type="SINGLE_TAP")

    # sample_interval validation
    cfg_int_dt = ImpulseSourceConfig(sample_interval=2)
    assert cfg_int_dt.sample_interval == 2.0
    assert type(cfg_int_dt.sample_interval) is float

    for invalid_dt in [True, False, np.float64(1.0), np.int32(1), "1.0", (1.0,)]:
        with pytest.raises(TypeError, match="sample_interval must be int or float"):
            ImpulseSourceConfig(sample_interval=invalid_dt)

    with pytest.raises(ValueError, match="sample_interval must be finite"):
        ImpulseSourceConfig(sample_interval=math.nan)
    with pytest.raises(ValueError, match="sample_interval must be > 0"):
        ImpulseSourceConfig(sample_interval=0.0)
    with pytest.raises(ValueError, match="sample_interval must be > 0"):
        ImpulseSourceConfig(sample_interval=-1.0)

    # impulse_zero_index validation
    for invalid_z in [True, False, np.int32(0), np.int64(1), 1.5, "0"]:
        with pytest.raises(TypeError, match="impulse_zero_index must be int"):
            ImpulseSourceConfig(impulse_zero_index=invalid_z)

    with pytest.raises(ValueError, match="impulse_zero_index must be >= 0"):
        ImpulseSourceConfig(impulse_zero_index=-1)


def test_corrupted_config_build_time_rejection_matrix(monkeypatch):
    """Verify build_impulse rejects corrupted frozen configs without repair and without calling _build_values."""
    def fail_if_called(*args, **kwargs):
        raise AssertionError("_build_values must not be called for corrupted config!")

    monkeypatch.setattr(impulse_source, "_build_values", fail_if_called)

    # Common field corruptions
    cfg_dt_int = ImpulseSourceConfig()
    object.__setattr__(cfg_dt_int, "sample_interval", 2)
    with pytest.raises(TypeError, match="sample_interval must be float"):
        build_impulse(cfg_dt_int)
    assert cfg_dt_int.sample_interval == 2
    assert type(cfg_dt_int.sample_interval) is int

    cfg_dt_np = ImpulseSourceConfig()
    object.__setattr__(cfg_dt_np, "sample_interval", np.float64(1.0))
    with pytest.raises(TypeError, match="sample_interval must be float"):
        build_impulse(cfg_dt_np)

    cfg_z_np = ImpulseSourceConfig()
    object.__setattr__(cfg_z_np, "impulse_zero_index", np.int64(0))
    with pytest.raises(TypeError, match="impulse_zero_index must be int"):
        build_impulse(cfg_z_np)

    cfg_z_out = ImpulseSourceConfig()
    object.__setattr__(cfg_z_out, "impulse_zero_index", 5)
    with pytest.raises(ValueError, match="impulse_zero_index"):
        build_impulse(cfg_z_out)

    # single_tap corrupted fields
    cfg_st_len = ImpulseSourceConfig()
    object.__setattr__(cfg_st_len, "length", np.int64(1))
    with pytest.raises(TypeError, match="length must be int"):
        build_impulse(cfg_st_len)

    cfg_st_amp_int = ImpulseSourceConfig()
    object.__setattr__(cfg_st_amp_int, "amplitude", 2)
    with pytest.raises(TypeError, match="amplitude must be float"):
        build_impulse(cfg_st_amp_int)

    cfg_st_amp_np = ImpulseSourceConfig()
    object.__setattr__(cfg_st_amp_np, "amplitude", np.float64(1.0))
    with pytest.raises(TypeError, match="amplitude must be float"):
        build_impulse(cfg_st_amp_np)

    cfg_st_decay = ImpulseSourceConfig()
    object.__setattr__(cfg_st_decay, "decay_ratio", 0.5)
    with pytest.raises(ValueError, match="Field 'decay_ratio' is irrelevant"):
        build_impulse(cfg_st_decay)

    cfg_st_val = ImpulseSourceConfig()
    object.__setattr__(cfg_st_val, "values", (1.0,))
    with pytest.raises(ValueError, match="Field 'values' is irrelevant"):
        build_impulse(cfg_st_val)

    # exponential_postcursor corrupted fields
    cfg_exp = ImpulseSourceConfig(source_type="exponential_postcursor", decay_ratio=0.5)
    cfg_exp_amp_int = ImpulseSourceConfig(source_type="exponential_postcursor", decay_ratio=0.5)
    object.__setattr__(cfg_exp_amp_int, "amplitude", 1)
    with pytest.raises(TypeError, match="amplitude must be float"):
        build_impulse(cfg_exp_amp_int)

    cfg_exp_decay_int = ImpulseSourceConfig(source_type="exponential_postcursor", decay_ratio=0.5)
    object.__setattr__(cfg_exp_decay_int, "decay_ratio", 0)
    with pytest.raises(TypeError, match="decay_ratio must be float"):
        build_impulse(cfg_exp_decay_int)

    cfg_exp_decay_np = ImpulseSourceConfig(source_type="exponential_postcursor", decay_ratio=0.5)
    object.__setattr__(cfg_exp_decay_np, "decay_ratio", np.float64(0.5))
    with pytest.raises(TypeError, match="decay_ratio must be float"):
        build_impulse(cfg_exp_decay_np)

    cfg_exp_val = ImpulseSourceConfig(source_type="exponential_postcursor", decay_ratio=0.5)
    object.__setattr__(cfg_exp_val, "values", (1.0,))
    with pytest.raises(ValueError, match="Field 'values' is irrelevant"):
        build_impulse(cfg_exp_val)

    # user_defined corrupted fields
    cfg_u = ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=[1.0, 2.0])

    cfg_u_list = ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=[1.0, 2.0])
    object.__setattr__(cfg_u_list, "values", [1.0, 2.0])
    with pytest.raises(TypeError, match="values must be tuple"):
        build_impulse(cfg_u_list)

    cfg_u_arr = ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=[1.0, 2.0])
    object.__setattr__(cfg_u_arr, "values", np.array([1.0, 2.0]))
    with pytest.raises(TypeError, match="values must be tuple"):
        build_impulse(cfg_u_arr)

    cfg_u_np_elem = ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=[1.0, 2.0])
    object.__setattr__(cfg_u_np_elem, "values", (np.float64(1.0), np.float64(2.0)))
    with pytest.raises(TypeError, match="element must be float"):
        build_impulse(cfg_u_np_elem)

    cfg_u_len = ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=[1.0, 2.0])
    object.__setattr__(cfg_u_len, "length", 2)
    with pytest.raises(ValueError, match="Field 'length' is irrelevant"):
        build_impulse(cfg_u_len)


def test_single_tap_golden_cases_boundaries_and_amplitude():
    """Verify single_tap golden vectors, zero-index boundaries, signed zero, and zero-amplitude behavior."""
    # 16.1 Default config
    cfg_default = ImpulseSourceConfig()
    res_default = build_impulse(cfg_default)
    assert res_default.values.dtype == np.float64
    assert res_default.values.shape == (1,)
    assert np.array_equal(res_default.values, np.array([1.0]))
    assert res_default.model_level == "project_owned_discrete_impulse_source"

    # 16.2 Hardcoded negative amplitude vector
    cfg_neg = ImpulseSourceConfig(
        source_type="single_tap",
        length=5,
        impulse_zero_index=2,
        amplitude=-0.5,
    )
    res_neg = build_impulse(cfg_neg)
    assert res_neg.values.dtype == np.float64
    assert np.array_equal(res_neg.values, np.array([0.0, 0.0, -0.5, 0.0, 0.0]))

    # Signed zero amplitude check (-0.0)
    cfg_neg_zero = ImpulseSourceConfig(source_type="single_tap", length=3, impulse_zero_index=1, amplitude=-0.0)
    res_nz = build_impulse(cfg_neg_zero)
    assert math.copysign(1.0, res_nz.values[1]) == -1.0

    # 16.3 Boundaries (first and last valid zero index)
    cfg_first = ImpulseSourceConfig(source_type="single_tap", length=4, impulse_zero_index=0, amplitude=2.0)
    assert np.array_equal(build_impulse(cfg_first).values, np.array([2.0, 0.0, 0.0, 0.0]))

    cfg_last = ImpulseSourceConfig(source_type="single_tap", length=4, impulse_zero_index=3, amplitude=2.0)
    assert np.array_equal(build_impulse(cfg_last).values, np.array([0.0, 0.0, 0.0, 2.0]))

    # Zero amplitude produces all-zero impulse
    cfg_zero_amp = ImpulseSourceConfig(source_type="single_tap", length=3, impulse_zero_index=1, amplitude=0.0)
    assert np.array_equal(build_impulse(cfg_zero_amp).values, np.array([0.0, 0.0, 0.0]))

    # Length validations
    for invalid_len in [True, False, np.int32(1), 0, -1]:
        with pytest.raises((TypeError, ValueError)):
            ImpulseSourceConfig(source_type="single_tap", length=invalid_len)


def test_exponential_postcursor_golden_cases_and_edge_cases():
    """Verify exponential_postcursor golden vectors, test-side formula, ratio=0, signed zero, and underflow."""
    # 16.4 Exponential postcursor golden vector
    cfg_exp = ImpulseSourceConfig(
        source_type="exponential_postcursor",
        length=6,
        impulse_zero_index=2,
        amplitude=1.0,
        decay_ratio=0.5,
    )
    res_exp = build_impulse(cfg_exp)
    assert res_exp.values.dtype == np.float64
    assert res_exp.values.shape == (6,)
    assert np.allclose(res_exp.values, np.array([0.0, 0.0, 1.0, 0.5, 0.25, 0.125]))

    # Test-side independent formula check
    def test_side_exponential_formula(length, z, amp, decay):
        out = [0.0] * length
        for n in range(z, length):
            out[n] = amp * (decay ** (n - z))
        return np.array(out, dtype=np.float64)

    cfg_custom_exp = ImpulseSourceConfig(
        source_type="exponential_postcursor",
        length=5,
        impulse_zero_index=1,
        amplitude=-2.0,
        decay_ratio=0.3,
    )
    expected_custom = test_side_exponential_formula(5, 1, -2.0, 0.3)
    assert np.allclose(build_impulse(cfg_custom_exp).values, expected_custom)

    # 16.5 Ratio zero special case
    cfg_zero_ratio = ImpulseSourceConfig(
        source_type="exponential_postcursor",
        length=5,
        impulse_zero_index=1,
        amplitude=-2.0,
        decay_ratio=0.0,
    )
    assert np.array_equal(build_impulse(cfg_zero_ratio).values, np.array([0.0, -2.0, 0.0, 0.0, 0.0]))

    # Amplitude 0.0 -> all-zero
    cfg_exp_zero_amp = ImpulseSourceConfig(
        source_type="exponential_postcursor",
        length=4,
        impulse_zero_index=1,
        amplitude=0.0,
        decay_ratio=0.5,
    )
    assert np.array_equal(build_impulse(cfg_exp_zero_amp).values, np.array([0.0, 0.0, 0.0, 0.0]))

    # Finite underflow accepted
    cfg_underflow = ImpulseSourceConfig(
        source_type="exponential_postcursor",
        length=10,
        impulse_zero_index=0,
        amplitude=1.0,
        decay_ratio=1e-100,
    )
    res_underflow = build_impulse(cfg_underflow)
    assert res_underflow.values[0] == 1.0
    assert res_underflow.values[9] == 0.0

    # Decay ratio boundary rejections
    for invalid_ratio in [-0.1, 1.0, 1.5, math.nan, math.inf]:
        with pytest.raises(ValueError):
            ImpulseSourceConfig(source_type="exponential_postcursor", decay_ratio=invalid_ratio)


def test_user_defined_matrix_scalar_value_error_and_boundaries():
    """Verify user_defined mode rejects scalars/0D with ValueError and handles input matrix & zero-index boundaries."""
    # Scalars and 0-D arrays MUST raise ValueError via dimension check
    with pytest.raises(ValueError, match="must be 1D"):
        ImpulseSourceConfig(
            source_type="user_defined",
            length=None,
            amplitude=None,
            decay_ratio=None,
            values=5.0,
        )

    with pytest.raises(ValueError, match="must be 1D"):
        ImpulseSourceConfig(
            source_type="user_defined",
            length=None,
            amplitude=None,
            decay_ratio=None,
            values=np.array(5.0),
        )

    with pytest.raises(ValueError, match="must be 1D"):
        ImpulseSourceConfig(
            source_type="user_defined",
            length=None,
            amplitude=None,
            decay_ratio=None,
            values=np.array([[1.0, 2.0]]),
        )

    # Acceptance of list, tuple, 1D ndarray, and non-contiguous view
    w_list = [1.0, 2.0, 3.0]
    w_tuple = (1.0, 2.0, 3.0)
    w_arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    w_slice = np.arange(10, dtype=np.float64)[::3]
    assert not w_slice.flags.c_contiguous

    for w_in in [w_list, w_tuple, w_arr, w_slice]:
        cfg_u = ImpulseSourceConfig(
            source_type="user_defined",
            length=None,
            amplitude=None,
            decay_ratio=None,
            values=w_in,
        )
        res_u = build_impulse(cfg_u)
        assert res_u.values.dtype == np.float64
        assert type(cfg_u.values) is tuple
        assert all(type(v) is float for v in cfg_u.values)
        assert res_u.values.flags.c_contiguous

    # First and last valid zero index
    cfg_u_first = ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, impulse_zero_index=0, values=[1, 2, 3])
    assert build_impulse(cfg_u_first).resolved_config.impulse_zero_index == 0

    cfg_u_last = ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, impulse_zero_index=2, values=[1, 2, 3])
    assert build_impulse(cfg_u_last).resolved_config.impulse_zero_index == 2

    # All-zero values accepted
    cfg_u_zeros = ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=[0.0, 0.0])
    assert np.array_equal(build_impulse(cfg_u_zeros).values, np.array([0.0, 0.0]))

    # Inf and overflow rejections
    with pytest.raises(ValueError, match="finite"):
        ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=[1.0, math.inf])

    with pytest.raises(ValueError, match="finite"):
        ImpulseSourceConfig(source_type="user_defined", length=None, amplitude=None, decay_ratio=None, values=[1e308 * 2.0])


def test_sample_interval_metadata_invariance():
    """Verify sample_interval affects only metadata and leaves output tap values unchanged."""
    cfg1 = ImpulseSourceConfig(sample_interval=1.0)
    cfg2 = ImpulseSourceConfig(sample_interval=2.0)

    res1 = build_impulse(cfg1)
    res2 = build_impulse(cfg2)

    assert res1.resolved_config.sample_interval == 1.0
    assert res2.resolved_config.sample_interval == 2.0
    assert np.array_equal(res1.values, res2.values)


def test_output_and_resolved_config_contracts():
    """Verify resolved_config identity/equality and new storage allocation across build calls."""
    cfg = ImpulseSourceConfig()
    res1 = build_impulse(cfg)
    res2 = build_impulse(cfg)

    assert res1.resolved_config == cfg
    assert res1.resolved_config is not cfg
    assert res1.values is not res2.values
    assert not np.shares_memory(res1.values, res2.values)


def test_internal_builder_failure_matrix(monkeypatch):
    """Verify build_impulse raises RuntimeError if internal _build_values produces invalid outputs."""
    cfg = ImpulseSourceConfig()

    # Helper returns list
    monkeypatch.setattr(impulse_source, "_build_values", lambda c, l: [1.0])
    with pytest.raises(RuntimeError, match="not exact np.ndarray"):
        build_impulse(cfg)

    # Helper returns ndarray subclass
    class SubNdArray(np.ndarray):
        pass

    sub_arr = np.array([1.0], dtype=np.float64).view(SubNdArray)
    monkeypatch.setattr(impulse_source, "_build_values", lambda c, l: sub_arr)
    with pytest.raises(RuntimeError, match="not exact np.ndarray"):
        build_impulse(cfg)

    # Helper returns wrong shape
    monkeypatch.setattr(impulse_source, "_build_values", lambda c, l: np.array([1.0, 2.0], dtype=np.float64))
    with pytest.raises(RuntimeError, match="shape mismatch"):
        build_impulse(cfg)

    # Helper returns wrong dtype (float32)
    monkeypatch.setattr(impulse_source, "_build_values", lambda c, l: np.array([1.0], dtype=np.float32))
    with pytest.raises(RuntimeError, match="dtype mismatch"):
        build_impulse(cfg)

    # Helper returns non-C-contiguous view (length=2)
    cfg2 = ImpulseSourceConfig(length=2)
    base_arr = np.array([1.0, 0.0, 2.0, 0.0], dtype=np.float64)
    non_c = base_arr[::2]
    assert not non_c.flags.c_contiguous
    assert non_c.shape == (2,)

    monkeypatch.setattr(impulse_source, "_build_values", lambda c, l: non_c)
    with pytest.raises(RuntimeError, match="not C-contiguous"):
        build_impulse(cfg2)

    # Helper returns NaN
    monkeypatch.setattr(impulse_source, "_build_values", lambda c, l: np.array([math.nan], dtype=np.float64))
    with pytest.raises(RuntimeError, match="non-finite values"):
        build_impulse(cfg)

    # Helper returns Inf
    monkeypatch.setattr(impulse_source, "_build_values", lambda c, l: np.array([math.inf], dtype=np.float64))
    with pytest.raises(RuntimeError, match="non-finite values"):
        build_impulse(cfg)


def test_serialization_isolation_and_from_dict_order():
    """Verify to_dict() new list allocations, dictionary/list mutation isolation, and from_dict() validation order."""
    cfg_user = ImpulseSourceConfig(
        source_type="user_defined",
        length=None,
        amplitude=None,
        decay_ratio=None,
        impulse_zero_index=1,
        values=[1.0, 2.0, 3.0],
    )
    d1 = cfg_user.to_dict()
    d2 = cfg_user.to_dict()

    assert d1 is not d2
    assert list(d1.keys()) == CANONICAL_KEYS
    assert type(d1["values"]) is list
    assert d1["values"] is not d2["values"]

    # Mutating returned list does not affect config or second dict
    d1["values"][0] = 999.0
    assert cfg_user.values == (1.0, 2.0, 3.0)
    assert d2["values"][0] == 1.0

    # from_dict validation order: raw mapping with irrelevant explosive values
    class Explosive:
        def __array__(self):
            raise RuntimeError("Explosive array!")

        def __iter__(self):
            raise RuntimeError("Explosive iter!")

    synthetic_dict = ImpulseSourceConfig().to_dict()
    synthetic_dict["values"] = Explosive()
    with pytest.raises(ValueError, match="Field 'values' is irrelevant"):
        ImpulseSourceConfig.from_dict(synthetic_dict)

    user_dict = cfg_user.to_dict()
    user_dict["length"] = 5
    user_dict["values"] = Explosive()
    with pytest.raises(ValueError, match="Field 'length' is irrelevant"):
        ImpulseSourceConfig.from_dict(user_dict)


def test_serialization_error_rejections():
    """Verify from_dict rejects non-mapping, missing keys, extra keys, non-str version, and unknown version."""
    with pytest.raises(TypeError, match="must be a Mapping"):
        ImpulseSourceConfig.from_dict("not_a_mapping")

    valid_dict = ImpulseSourceConfig().to_dict()

    missing_dict = valid_dict.copy()
    del missing_dict["source_type"]
    with pytest.raises(ValueError, match="missing keys"):
        ImpulseSourceConfig.from_dict(missing_dict)

    extra_dict = valid_dict.copy()
    extra_dict["extra_param"] = 123
    with pytest.raises(ValueError, match="extra keys"):
        ImpulseSourceConfig.from_dict(extra_dict)

    bad_type_dict = valid_dict.copy()
    bad_type_dict["schema_version"] = 12345
    with pytest.raises(TypeError, match="schema_version in dict must be str"):
        ImpulseSourceConfig.from_dict(bad_type_dict)

    bad_ver_dict = valid_dict.copy()
    bad_ver_dict["schema_version"] = "pcie_eq-impulse-source-v999"
    with pytest.raises(ValueError, match="Unknown schema_version"):
        ImpulseSourceConfig.from_dict(bad_ver_dict)
