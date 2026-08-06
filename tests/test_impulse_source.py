"""
Unit tests for pcie_eq.impulse_source core module.

Verifies:
1. Public API surface, frozen dataclasses, frozen instance mutation rejections, and exact ImpulseSourceConfig type/subclass check.
2. Common field validations (schema, source_type, sample_interval, normalization, zero_index, defensive revalidation).
3. Source-specific relevance rules, validation order, and irrelevant field rejections.
4. single_tap mode golden vectors, boundary zero-indices, and zero-amplitude behavior.
5. exponential_postcursor mode golden vectors, direct formula comparison, decay_ratio=0, and ratio range rejections.
6. user_defined mode list/tuple/ndarray/non-contiguous view matrix, bool/int/uint/float16/32/64 to float64, and mutation isolation.
7. Output contract: exact float64 ndarray, C-contiguous, finite, new storage allocation, and result mutation isolation.
8. Serialization to_dict() / from_dict() canonical 9-key order, new dict/list allocations, round-trips, and error handling.
"""

from dataclasses import FrozenInstanceError
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


def test_validation_and_relevance_order():
    """Verify validation order and defensive re-validation before allocation or wave conversion."""
    class Explosive:
        def __array__(self):
            raise RuntimeError("Should not be converted!")

    # Corrupted config fails defensive re-validation before allocation
    corrupted_cfg = ImpulseSourceConfig()
    object.__setattr__(corrupted_cfg, "source_type", "invalid_source")
    with pytest.raises(ValueError, match="Unsupported source_type"):
        build_impulse(corrupted_cfg)

    # Synthetic source rejects irrelevant values without materializing it
    with pytest.raises(ValueError, match="Field 'values' is irrelevant"):
        ImpulseSourceConfig(source_type="single_tap", values=Explosive())

    # User-defined source rejects irrelevant length before values conversion
    with pytest.raises(ValueError, match="Field 'length' is irrelevant"):
        ImpulseSourceConfig(source_type="user_defined", length=5, values=Explosive())


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
    with pytest.raises(ValueError, match="Unsupported source_type"):
        ImpulseSourceConfig(source_type="single_tap ")

    # sample_interval validation (int/float accepted, bool/numpy scalar/non-finite/<=0 rejected)
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

    # normalization validation
    with pytest.raises(TypeError, match="normalization must be str"):
        ImpulseSourceConfig(normalization=123)
    with pytest.raises(ValueError, match="Unsupported normalization"):
        ImpulseSourceConfig(normalization="peak")

    # impulse_zero_index validation (int accepted, bool/numpy scalar/negative rejected)
    for invalid_z in [True, False, np.int32(0), np.int64(1), 1.5, "0"]:
        with pytest.raises(TypeError, match="impulse_zero_index must be int"):
            ImpulseSourceConfig(impulse_zero_index=invalid_z)

    with pytest.raises(ValueError, match="impulse_zero_index must be >= 0"):
        ImpulseSourceConfig(impulse_zero_index=-1)


def test_relevance_rejections_for_all_sources():
    """Verify irrelevant fields trigger ValueError for each source type."""
    # single_tap irrelevant fields
    with pytest.raises(ValueError, match="Field 'decay_ratio' is irrelevant"):
        ImpulseSourceConfig(source_type="single_tap", decay_ratio=0.5)
    with pytest.raises(ValueError, match="Field 'values' is irrelevant"):
        ImpulseSourceConfig(source_type="single_tap", values=[1.0])

    # exponential_postcursor irrelevant field
    with pytest.raises(ValueError, match="Field 'values' is irrelevant"):
        ImpulseSourceConfig(source_type="exponential_postcursor", decay_ratio=0.5, values=[1.0])

    # user_defined irrelevant fields
    with pytest.raises(ValueError, match="Field 'length' is irrelevant"):
        ImpulseSourceConfig(source_type="user_defined", length=5, values=[1.0])
    with pytest.raises(ValueError, match="Field 'amplitude' is irrelevant"):
        ImpulseSourceConfig(source_type="user_defined", amplitude=1.0, values=[1.0])
    with pytest.raises(ValueError, match="Field 'decay_ratio' is irrelevant"):
        ImpulseSourceConfig(source_type="user_defined", decay_ratio=0.5, values=[1.0])


def test_single_tap_golden_cases_and_boundaries():
    """Verify single_tap golden vectors, zero-index boundaries, and amplitude cases."""
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

    # 16.3 Boundaries (first and last valid zero index)
    cfg_first = ImpulseSourceConfig(source_type="single_tap", length=4, impulse_zero_index=0, amplitude=2.0)
    assert np.array_equal(build_impulse(cfg_first).values, np.array([2.0, 0.0, 0.0, 0.0]))

    cfg_last = ImpulseSourceConfig(source_type="single_tap", length=4, impulse_zero_index=3, amplitude=2.0)
    assert np.array_equal(build_impulse(cfg_last).values, np.array([0.0, 0.0, 0.0, 2.0]))

    # Zero amplitude produces all-zero impulse
    cfg_zero_amp = ImpulseSourceConfig(source_type="single_tap", length=3, impulse_zero_index=1, amplitude=0.0)
    assert np.array_equal(build_impulse(cfg_zero_amp).values, np.array([0.0, 0.0, 0.0]))

    # Length validations (bool, numpy scalar, 0, negative)
    for invalid_len in [True, False, np.int32(1), 0, -1]:
        with pytest.raises((TypeError, ValueError)):
            ImpulseSourceConfig(source_type="single_tap", length=invalid_len)


def test_exponential_postcursor_golden_cases_and_range_rejections():
    """Verify exponential_postcursor golden vectors, test-side formula, ratio=0, and ratio range rejections."""
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

    # Decay ratio boundary rejections (< 0.0, >= 1.0, NaN, Inf)
    for invalid_ratio in [-0.1, 1.0, 1.5, math.nan, math.inf]:
        with pytest.raises(ValueError):
            ImpulseSourceConfig(source_type="exponential_postcursor", decay_ratio=invalid_ratio)


def test_user_defined_matrix_canonicalization_and_rejections():
    """Verify user_defined mode input sequence types, dtype conversion matrix, and scalar/invalid rejections."""
    # List, tuple, 1D ndarray, and non-contiguous view acceptance
    w_list = [1.0, 2.0, 3.0]
    w_tuple = (1.0, 2.0, 3.0)
    w_arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    w_slice = np.arange(10, dtype=np.float64)[::3]
    assert not w_slice.flags.c_contiguous

    for w_in in [w_list, w_tuple, w_arr, w_slice]:
        cfg_u = ImpulseSourceConfig(source_type="user_defined", values=w_in)
        res_u = build_impulse(cfg_u)
        assert res_u.values.dtype == np.float64
        assert type(cfg_u.values) is tuple
        assert all(type(v) is float for v in cfg_u.values)
        assert res_u.values.flags.c_contiguous

    # Dtype promotion matrix -> float64
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
        sample_vals = np.array([0, 1, 0], dtype=dt)
        cfg_dt = ImpulseSourceConfig(source_type="user_defined", values=sample_vals)
        res_dt = build_impulse(cfg_dt)
        assert res_dt.values.dtype == np.float64
        assert res_dt.values.shape == (3,)

    # Scalar, 2D, complex, string, object, empty, NaN, Inf rejections
    with pytest.raises(TypeError):
        ImpulseSourceConfig(source_type="user_defined", values=5.0)

    with pytest.raises(ValueError, match="must be 1D"):
        ImpulseSourceConfig(source_type="user_defined", values=np.array([[1.0, 2.0]]))

    with pytest.raises(TypeError, match="real numeric"):
        ImpulseSourceConfig(source_type="user_defined", values=[1 + 1j])

    with pytest.raises(TypeError, match="real numeric"):
        ImpulseSourceConfig(source_type="user_defined", values=["1.0"])

    with pytest.raises(TypeError, match="real numeric"):
        ImpulseSourceConfig(source_type="user_defined", values=[object()])

    with pytest.raises(ValueError, match="must not be empty"):
        ImpulseSourceConfig(source_type="user_defined", values=[])

    with pytest.raises(ValueError, match="finite"):
        ImpulseSourceConfig(source_type="user_defined", values=[1.0, math.nan])


def test_input_mutation_isolation_and_output_storage_independence():
    """Verify caller input list/ndarray mutations do not alter config, and builds create new independent storage."""
    # List mutation isolation
    src_list = [1.0, 2.0, 3.0]
    cfg = ImpulseSourceConfig(source_type="user_defined", values=src_list)
    src_list[0] = 999.0
    assert cfg.values == (1.0, 2.0, 3.0)

    # Ndarray mutation isolation
    src_arr = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    cfg_arr = ImpulseSourceConfig(source_type="user_defined", values=src_arr)
    src_arr[0] = 999.0
    assert cfg_arr.values == (1.0, 2.0, 3.0)

    # Multiple build calls create new independent storage
    res1 = build_impulse(cfg)
    res2 = build_impulse(cfg)

    assert res1.values is not res2.values
    assert not np.shares_memory(res1.values, res2.values)

    # Result mutation isolation
    res1.values[0] = 777.0
    assert build_impulse(cfg).values[0] == 1.0
    assert cfg.values[0] == 1.0


def test_serialization_canonical_nine_keys_and_round_trip():
    """Verify to_dict() returns new dict with 9 canonical keys in order, and round-trips synthetic and user-defined configs."""
    # Synthetic round-trip
    cfg_exp = ImpulseSourceConfig(
        source_type="exponential_postcursor",
        length=5,
        impulse_zero_index=1,
        amplitude=-2.0,
        decay_ratio=0.4,
    )
    d_exp1 = cfg_exp.to_dict()
    d_exp2 = cfg_exp.to_dict()

    assert d_exp1 is not d_exp2
    assert list(d_exp1.keys()) == CANONICAL_KEYS
    assert d_exp1["values"] is None

    restored_exp = ImpulseSourceConfig.from_dict(d_exp2)
    assert restored_exp == cfg_exp
    assert restored_exp is not cfg_exp

    # User-defined round-trip
    cfg_user = ImpulseSourceConfig(
        source_type="user_defined",
        impulse_zero_index=1,
        values=[1.0, 2.0, 3.0],
    )
    d_user1 = cfg_user.to_dict()
    d_user2 = cfg_user.to_dict()

    assert d_user1 is not d_user2
    assert list(d_user1.keys()) == CANONICAL_KEYS
    assert type(d_user1["values"]) is list
    assert d_user1["values"] == [1.0, 2.0, 3.0]

    # Mutating returned dictionary values list does not mutate config
    d_user1["values"][0] = 999.0
    assert cfg_user.values == (1.0, 2.0, 3.0)

    restored_user = ImpulseSourceConfig.from_dict(d_user2)
    assert restored_user == cfg_user
    assert restored_user is not cfg_user
    assert type(restored_user.values) is tuple
    assert all(type(v) is float for v in restored_user.values)

    # Resolved config round-trip
    res_user = build_impulse(cfg_user)
    restored_resolved = ImpulseSourceConfig.from_dict(res_user.resolved_config.to_dict())
    assert restored_resolved == res_user.resolved_config
    assert restored_resolved is not res_user.resolved_config


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
