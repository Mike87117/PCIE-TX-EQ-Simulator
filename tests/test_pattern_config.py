"""
Unit tests for pcie_eq.pattern_config core module.

Verifies:
1. All 11 pattern types small hardcoded golden cases & PatternResult metadata.
2. Constructor type/range validation & irrelevant-field rejection.
3. Seeded NRZ & PAM4 golden vectors, reproducibility, global RNG equivalence, and seeded RNG isolation.
4. RNG non-consumption for invalid configs and count=0.
5. Exact dtype contracts across random (empty/non-empty), deterministic, PRBS, and user patterns, including Windows int32/int64 checks.
6. PRBS frozen prefixes, resolved default initial state and convention ID.
7. User-defined bits & PAM4 level validation, normalization, and output non-aliasing.
8. Serialization to_dict() / from_dict() canonical keys order, round-trip, and error handling.
"""

import sys
import math
import numpy as np
import pytest

from pcie_eq.pattern_config import (
    PATTERN_CONFIG_CONTRACT_ID,
    PatternConfig,
    PatternResult,
    generate_pattern,
    CANONICAL_KEYS,
)
from pcie_eq.patterns import (
    generate_random_nrz_bits,
    generate_random_pam4_symbols,
)


def test_pattern_config_all_11_types_golden_cases_and_metadata():
    """Verify all 11 pattern types generate expected golden vectors and correct result metadata."""
    test_cases = [
        (
            PatternConfig(pattern_type="nrz_random", count=10, seed=42),
            np.array([0, 1, 0, 0, 0, 1, 0, 0, 0, 1]),
            "nrz", "bits", "seeded", np.dtype("l")
        ),
        (
            PatternConfig(pattern_type="nrz_all_zeros", count=6),
            np.array([0, 0, 0, 0, 0, 0]),
            "nrz", "bits", "none", np.dtype(int)
        ),
        (
            PatternConfig(pattern_type="nrz_all_ones", count=6),
            np.array([1, 1, 1, 1, 1, 1]),
            "nrz", "bits", "none", np.dtype(int)
        ),
        (
            PatternConfig(pattern_type="nrz_alternating", count=6, first_bit=0),
            np.array([0, 1, 0, 1, 0, 1]),
            "nrz", "bits", "none", np.dtype(int)
        ),
        (
            PatternConfig(pattern_type="nrz_long_run", count=10, run_length=3, first_bit=0),
            np.array([0, 0, 0, 1, 1, 1, 0, 0, 0, 1]),
            "nrz", "bits", "none", np.dtype(int)
        ),
        (
            PatternConfig(pattern_type="nrz_single_transition", count=6, transition_index=3, initial_bit=0),
            np.array([0, 0, 0, 1, 1, 1]),
            "nrz", "bits", "none", np.dtype(int)
        ),
        (
            PatternConfig(pattern_type="nrz_single_bit_pulse", count=6, pulse_index=2, baseline_bit=0),
            np.array([0, 0, 1, 0, 0, 0]),
            "nrz", "bits", "none", np.dtype(int)
        ),
        (
            PatternConfig(pattern_type="nrz_prbs", count=16, prbs_order=7),
            np.array([1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0], dtype=np.int8),
            "nrz", "bits", "none", np.int8
        ),
        (
            PatternConfig(pattern_type="nrz_user_bits", count=4, user_values=(0, True, 1, False)),
            np.array([0, 1, 1, 0]),
            "nrz", "bits", "none", np.dtype(int)
        ),
        (
            PatternConfig(pattern_type="pam4_random", count=10, seed=42),
            np.array([1.0 / 3.0, 1.0, -1.0, 1.0 / 3.0, 1.0 / 3.0, 1.0, -1.0, -1.0, 1.0 / 3.0, -1.0 / 3.0]),
            "pam4", "symbols", "seeded", np.float64
        ),
        (
            PatternConfig(pattern_type="pam4_user_symbols", count=4, user_values=(-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0)),
            np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0]),
            "pam4", "symbols", "none", np.float64
        ),
    ]

    for config, expected_values, expected_mod, expected_dom, expected_rng, expected_dtype in test_cases:
        res = generate_pattern(config)
        assert isinstance(res, PatternResult)
        assert res.modulation == expected_mod
        assert res.domain == expected_dom
        assert res.rng_mode == expected_rng
        assert res.values.dtype == expected_dtype
        assert res.values.shape == (config.count,)
        assert res.values.flags.c_contiguous
        if expected_mod == "pam4":
            assert np.allclose(res.values, expected_values)
        else:
            assert np.array_equal(res.values, expected_values)


def test_pattern_config_irrelevant_field_rejection():
    """Verify passing any non-None irrelevant field raises ValueError across all pattern types."""
    # nrz_random allows seed; others irrelevant
    with pytest.raises(ValueError, match="is not applicable"):
        PatternConfig(pattern_type="nrz_random", count=10, run_length=3)
    with pytest.raises(ValueError, match="is not applicable"):
        PatternConfig(pattern_type="nrz_random", count=10, prbs_order=7)

    # nrz_all_zeros allows no optional fields
    with pytest.raises(ValueError, match="is not applicable"):
        PatternConfig(pattern_type="nrz_all_zeros", count=10, seed=42)

    # nrz_prbs allows prbs_order, prbs_initial_state, prbs_convention_id; others irrelevant
    with pytest.raises(ValueError, match="is not applicable"):
        PatternConfig(pattern_type="nrz_prbs", count=10, prbs_order=7, first_bit=0)

    # pam4_user_symbols allows user_values; others irrelevant
    with pytest.raises(ValueError, match="is not applicable"):
        PatternConfig(pattern_type="pam4_user_symbols", count=2, user_values=(-1.0, 1.0), seed=42)


def test_pattern_config_constructor_validation_contracts():
    """Verify strict type and range validations in PatternConfig.__post_init__."""
    # schema_version validation
    with pytest.raises(TypeError):
        PatternConfig(pattern_type="nrz_all_zeros", count=5, schema_version=123)
    with pytest.raises(ValueError, match="Unknown schema_version"):
        PatternConfig(pattern_type="nrz_all_zeros", count=5, schema_version="v2")

    # pattern_type validation
    with pytest.raises(TypeError):
        PatternConfig(pattern_type=123, count=5)
    with pytest.raises(ValueError, match="Unsupported pattern_type"):
        PatternConfig(pattern_type="NRZ_RANDOM", count=5)  # case mismatch
    with pytest.raises(ValueError, match="Unsupported pattern_type"):
        PatternConfig(pattern_type="nrz_random ", count=5)  # trailing space

    # count validation
    for invalid_count in [True, False, 2.5, "10"]:
        with pytest.raises(TypeError):
            PatternConfig(pattern_type="nrz_all_zeros", count=invalid_count)
    with pytest.raises(ValueError):
        PatternConfig(pattern_type="nrz_all_zeros", count=-1)
    with pytest.raises(ValueError, match="requires count > 0"):
        PatternConfig(pattern_type="nrz_single_bit_pulse", count=0, pulse_index=0)

    # seed validation
    for invalid_seed in [True, False, 2.5, "42", (42,)]:
        with pytest.raises(TypeError):
            PatternConfig(pattern_type="nrz_random", count=10, seed=invalid_seed)
    with pytest.raises(ValueError):
        PatternConfig(pattern_type="nrz_random", count=10, seed=-1)
    with pytest.raises(ValueError):
        PatternConfig(pattern_type="nrz_random", count=10, seed=2**32)

    # bit fields (first_bit, initial_bit, baseline_bit) validation
    for invalid_bit in [True, False, 2.5, "0", 2]:
        with pytest.raises((TypeError, ValueError)):
            PatternConfig(pattern_type="nrz_alternating", count=10, first_bit=invalid_bit)

    # run_length validation
    with pytest.raises(ValueError, match="requires run_length"):
        PatternConfig(pattern_type="nrz_long_run", count=10)
    for invalid_rl in [True, 0, -1, 1.5]:
        with pytest.raises((TypeError, ValueError)):
            PatternConfig(pattern_type="nrz_long_run", count=10, run_length=invalid_rl)

    # transition_index validation
    with pytest.raises(ValueError, match="requires transition_index"):
        PatternConfig(pattern_type="nrz_single_transition", count=10)
    for invalid_ti in [-1, 11, 2.5, True]:
        with pytest.raises((TypeError, ValueError)):
            PatternConfig(pattern_type="nrz_single_transition", count=10, transition_index=invalid_ti)

    # pulse_index validation
    with pytest.raises(ValueError, match="requires pulse_index"):
        PatternConfig(pattern_type="nrz_single_bit_pulse", count=10)
    for invalid_pi in [-1, 10, 2.5, True]:
        with pytest.raises((TypeError, ValueError)):
            PatternConfig(pattern_type="nrz_single_bit_pulse", count=10, pulse_index=invalid_pi)

    # prbs validations
    with pytest.raises(ValueError, match="requires prbs_order"):
        PatternConfig(pattern_type="nrz_prbs", count=10)
    for invalid_order in [5, 8, 16, 32, 7.0, True]:
        with pytest.raises((TypeError, ValueError)):
            PatternConfig(pattern_type="nrz_prbs", count=10, prbs_order=invalid_order)

    with pytest.raises(ValueError, match="prbs_initial_state"):
        PatternConfig(pattern_type="nrz_prbs", count=10, prbs_order=7, prbs_initial_state=0)
    with pytest.raises(ValueError, match="prbs_initial_state"):
        PatternConfig(pattern_type="nrz_prbs", count=10, prbs_order=7, prbs_initial_state=128)

    with pytest.raises(ValueError, match="Unknown prbs_convention_id"):
        PatternConfig(pattern_type="nrz_prbs", count=10, prbs_order=7, prbs_convention_id="invalid_id")

    # user_values validations
    with pytest.raises(ValueError, match="requires user_values"):
        PatternConfig(pattern_type="nrz_user_bits", count=2)
    with pytest.raises(TypeError, match="must be tuple"):
        PatternConfig(pattern_type="nrz_user_bits", count=2, user_values=[0, 1])  # list rejected directly
    with pytest.raises(ValueError, match="user_values length"):
        PatternConfig(pattern_type="nrz_user_bits", count=2, user_values=(0, 1, 1))

    # nrz_user_bits float rejection
    with pytest.raises(TypeError, match="must be int or bool, got float"):
        PatternConfig(pattern_type="nrz_user_bits", count=2, user_values=(0.0, 1.0))

    # pam4_user_symbols level & finiteness validation
    with pytest.raises(TypeError):
        PatternConfig(pattern_type="pam4_user_symbols", count=2, user_values=(True, False))
    with pytest.raises(ValueError, match="must be finite"):
        PatternConfig(pattern_type="pam4_user_symbols", count=2, user_values=(1.0, math.nan))
    with pytest.raises(ValueError, match="not a valid PAM4 level"):
        PatternConfig(pattern_type="pam4_user_symbols", count=2, user_values=(1.0, 0.5))


def test_seeded_rng_reproducibility_and_isolation():
    """Verify seeded random pattern generation reproducibility and global RNG isolation."""
    initial_rng = np.random.get_state()
    try:
        cfg = PatternConfig(pattern_type="nrz_random", count=20, seed=12345)
        res1 = generate_pattern(cfg)
        res2 = generate_pattern(cfg)

        assert np.array_equal(res1.values, res2.values)

        diff_cfg = PatternConfig(pattern_type="nrz_random", count=20, seed=54321)
        res_diff = generate_pattern(diff_cfg)
        assert not np.array_equal(res1.values, res_diff.values)

        # Global RNG should not be altered by seeded calls
        final_rng = np.random.get_state()
        assert initial_rng[0] == final_rng[0]
        assert np.array_equal(initial_rng[1], final_rng[1])
        assert initial_rng[2:] == final_rng[2:]
    finally:
        np.random.set_state(initial_rng)


def test_unseeded_global_rng_equivalence():
    """Verify seed=None uses global NumPy RNG identically to direct calls."""
    initial_rng = np.random.get_state()
    try:
        np.random.seed(999)
        ref_bits = generate_random_nrz_bits(50, seed=None)

        np.random.seed(999)
        res = generate_pattern(PatternConfig(pattern_type="nrz_random", count=50, seed=None))
        assert res.rng_mode == "global"
        assert np.array_equal(res.values, ref_bits)
    finally:
        np.random.set_state(initial_rng)


def test_rng_non_consumption_for_invalid_config_and_count_zero():
    """Verify invalid configs and count=0 calls consume zero global RNG state."""
    initial_rng = np.random.get_state()
    try:
        # Invalid config attempt
        with pytest.raises((ValueError, TypeError)):
            PatternConfig(pattern_type="nrz_random", count=10, seed="invalid")

        # Count 0 calls
        generate_pattern(PatternConfig(pattern_type="nrz_random", count=0, seed=None))
        generate_pattern(PatternConfig(pattern_type="pam4_random", count=0, seed=None))

        final_rng = np.random.get_state()
        assert initial_rng[0] == final_rng[0]
        assert np.array_equal(initial_rng[1], final_rng[1])
        assert initial_rng[2:] == final_rng[2:]
    finally:
        np.random.set_state(initial_rng)


def test_random_empty_and_nonempty_dtype_matrix_and_windows_checks():
    """Verify exact dtype matrix for random patterns, including C-long np.dtype('l') and Windows int32/int64 assertions."""
    # Non-empty nrz_random: exact dtype("l")
    res_nonempty = generate_pattern(PatternConfig(pattern_type="nrz_random", count=10, seed=42))
    assert res_nonempty.values.dtype == np.dtype("l")

    # Empty nrz_random: exact dtype(int)
    res_empty = generate_pattern(PatternConfig(pattern_type="nrz_random", count=0, seed=42))
    assert res_empty.values.dtype == np.dtype(int)

    # Windows-specific platform check (64-bit Windows)
    if sys.platform == "win32":
        assert res_nonempty.values.dtype == np.int32
        assert res_empty.values.dtype == np.int64


def test_deterministic_nrz_boundary_cases():
    """Verify boundary cases for single_transition and single_bit_pulse."""
    # transition_index = 0 -> all bits transition immediately (all 1s)
    res_t0 = generate_pattern(PatternConfig(pattern_type="nrz_single_transition", count=4, transition_index=0, initial_bit=0))
    assert np.array_equal(res_t0.values, np.array([1, 1, 1, 1]))

    # transition_index = count -> all bits remain initial_bit (all 0s)
    res_t4 = generate_pattern(PatternConfig(pattern_type="nrz_single_transition", count=4, transition_index=4, initial_bit=0))
    assert np.array_equal(res_t4.values, np.array([0, 0, 0, 0]))

    # pulse at index 0
    res_p0 = generate_pattern(PatternConfig(pattern_type="nrz_single_bit_pulse", count=4, pulse_index=0, baseline_bit=0))
    assert np.array_equal(res_p0.values, np.array([1, 0, 0, 0]))

    # pulse at index count-1
    res_p3 = generate_pattern(PatternConfig(pattern_type="nrz_single_bit_pulse", count=4, pulse_index=3, baseline_bit=0))
    assert np.array_equal(res_p3.values, np.array([0, 0, 0, 1]))


def test_prbs_resolved_defaults_and_frozen_prefixes():
    """Verify PRBS resolved defaults and frozen 64-bit golden prefixes across orders."""
    res_p7 = generate_pattern(PatternConfig(pattern_type="nrz_prbs", count=64, prbs_order=7))
    assert res_p7.resolved_config.prbs_initial_state == 127
    assert res_p7.resolved_config.prbs_convention_id == "pcie_eq-prbs-fibonacci-lsb-v1"
    expected_p7 = np.array([int(c) for c in "1111111000000100000110000101000111100100010110011101010011111010"], dtype=np.int8)
    assert np.array_equal(res_p7.values, expected_p7)


def test_user_defined_values_normalization_and_non_aliasing():
    """Verify user_values normalization (bool -> 0/1) and output array non-aliasing."""
    # nrz_user_bits bool normalization
    cfg_user = PatternConfig(pattern_type="nrz_user_bits", count=4, user_values=(True, False, 1, 0))
    res_user = generate_pattern(cfg_user)
    assert res_user.resolved_config.user_values == (1, 0, 1, 0)
    assert np.array_equal(res_user.values, np.array([1, 0, 1, 0]))
    assert res_user.values.dtype == np.dtype(int)

    # pam4_user_symbols
    pam4_tuple = (-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0)
    cfg_pam4 = PatternConfig(pattern_type="pam4_user_symbols", count=4, user_values=pam4_tuple)
    res_pam4 = generate_pattern(cfg_pam4)
    assert not np.shares_memory(res_pam4.values, pam4_tuple)
    assert res_pam4.values.dtype == np.float64


def test_serialization_canonical_keys_order_and_round_trip():
    """Verify to_dict() canonical keys order, from_dict() parsing, and round-trip consistency."""
    cfg = PatternConfig(pattern_type="nrz_long_run", count=10, run_length=3, first_bit=1)
    d = cfg.to_dict()

    assert list(d.keys()) == CANONICAL_KEYS
    assert d["pattern_type"] == "nrz_long_run"
    assert d["count"] == 10
    assert d["run_length"] == 3
    assert d["first_bit"] == 1

    restored = PatternConfig.from_dict(d)
    assert restored == cfg

    res1 = generate_pattern(cfg)
    res2 = generate_pattern(restored)
    assert np.array_equal(res1.values, res2.values)
    assert res1.resolved_config == res2.resolved_config

    # Mutating dictionary output does not affect original config
    d["count"] = 999
    assert cfg.count == 10


def test_serialization_error_rejection():
    """Verify from_dict rejects non-mapping, missing keys, extra keys, and invalid versions."""
    with pytest.raises(TypeError):
        PatternConfig.from_dict("not_a_dict")

    valid_dict = PatternConfig(pattern_type="nrz_all_zeros", count=5).to_dict()

    # Missing key
    missing_dict = valid_dict.copy()
    del missing_dict["seed"]
    with pytest.raises(ValueError, match="missing keys"):
        PatternConfig.from_dict(missing_dict)

    # Extra key
    extra_dict = valid_dict.copy()
    extra_dict["unknown_extra"] = 123
    with pytest.raises(ValueError, match="extra keys"):
        PatternConfig.from_dict(extra_dict)

    # Unknown schema version
    bad_ver_dict = valid_dict.copy()
    bad_ver_dict["schema_version"] = "pcie_eq-pattern-config-v999"
    with pytest.raises(ValueError, match="Unknown schema_version"):
        PatternConfig.from_dict(bad_ver_dict)


def test_generate_pattern_rejects_non_pattern_config_type():
    """Verify generate_pattern raises TypeError if passed an object that is not a PatternConfig."""
    with pytest.raises(TypeError, match="must be a PatternConfig instance"):
        generate_pattern({"pattern_type": "nrz_all_zeros", "count": 5})
