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
9. Strict PatternConfig subclass rejection, defensive config re-validation, NumPy scalar user values rejection, and helper RuntimeError checks.
"""

import sys
import math
import numpy as np
import pytest

import pcie_eq.pattern_config as pattern_config
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


def test_pattern_config_subclass_rejection():
    """Verify generate_pattern rejects PatternConfig subclasses with TypeError."""
    class SubPatternConfig(PatternConfig):
        pass

    sub_cfg = SubPatternConfig(pattern_type="nrz_all_zeros", count=5)
    with pytest.raises(TypeError, match="must be exactly PatternConfig, got SubPatternConfig"):
        generate_pattern(sub_cfg)


def test_corrupted_frozen_config_defensive_validation():
    """Verify generate_pattern re-validates corrupted frozen configs modified via object.__setattr__."""
    cfg = PatternConfig(pattern_type="nrz_all_zeros", count=5)
    object.__setattr__(cfg, "count", -10)
    with pytest.raises(ValueError, match="count must be >= 0"):
        generate_pattern(cfg)

    cfg2 = PatternConfig(pattern_type="nrz_all_zeros", count=5)
    object.__setattr__(cfg2, "pattern_type", "corrupted_type")
    with pytest.raises(ValueError, match="Unsupported pattern_type"):
        generate_pattern(cfg2)


def test_validation_occurs_before_rng_consumption():
    """Verify defensive validation occurs prior to RNG consumption for corrupted random configs."""
    initial_rng = np.random.get_state()
    try:
        cfg = PatternConfig(pattern_type="nrz_random", count=10, seed=None)
        object.__setattr__(cfg, "seed", -999)

        with pytest.raises(ValueError, match=r"seed must be between 0 and 2\*\*32 - 1"):
            generate_pattern(cfg)

        final_rng = np.random.get_state()
        assert initial_rng[0] == final_rng[0]
        assert np.array_equal(initial_rng[1], final_rng[1])
        assert initial_rng[2:] == final_rng[2:]
    finally:
        np.random.set_state(initial_rng)


def test_from_dict_non_string_schema_version():
    """Verify PatternConfig.from_dict raises TypeError when schema_version is not a str."""
    valid_dict = PatternConfig(pattern_type="nrz_all_zeros", count=5).to_dict()
    valid_dict["schema_version"] = 12345
    with pytest.raises(TypeError, match="schema_version in dict must be str"):
        PatternConfig.from_dict(valid_dict)


def test_numpy_scalar_pam4_user_values_rejection():
    """Verify NumPy scalars (np.float32, np.float64, np.int64) in PAM4 user_values are rejected."""
    with pytest.raises(TypeError, match="element must be exact Python int or float"):
        PatternConfig(pattern_type="pam4_user_symbols", count=2, user_values=(np.float64(-1.0), np.float64(1.0)))

    with pytest.raises(TypeError, match="element must be exact Python int or float"):
        PatternConfig(pattern_type="pam4_user_symbols", count=2, user_values=(np.float32(-1.0), 1.0))


def test_helper_bad_shape_raises_runtime_error(monkeypatch):
    """Verify generate_pattern raises RuntimeError if helper returns invalid shape."""
    monkeypatch.setattr(pattern_config, "generate_nrz_all_zeros", lambda count: np.zeros((count, 2), dtype=int))
    with pytest.raises(RuntimeError, match="Generator output shape mismatch"):
        generate_pattern(PatternConfig(pattern_type="nrz_all_zeros", count=5))


def test_helper_bad_dtype_raises_runtime_error(monkeypatch):
    """Verify generate_pattern raises RuntimeError if helper returns unexpected dtype."""
    monkeypatch.setattr(pattern_config, "generate_nrz_all_zeros", lambda count: np.zeros(count, dtype=np.float64))
    with pytest.raises(RuntimeError, match="dtype mismatch"):
        generate_pattern(PatternConfig(pattern_type="nrz_all_zeros", count=5))


def test_helper_invalid_nrz_domain_raises_runtime_error(monkeypatch):
    """Verify generate_pattern raises RuntimeError if NRZ helper output contains values outside {0, 1}."""
    monkeypatch.setattr(pattern_config, "generate_nrz_all_zeros", lambda count: np.array([0, 1, 2, 0, 1], dtype=int))
    with pytest.raises(RuntimeError, match="NRZ pattern contains invalid bit value"):
        generate_pattern(PatternConfig(pattern_type="nrz_all_zeros", count=5))


def test_helper_slightly_off_level_pam4_domain_raises_runtime_error(monkeypatch):
    """Verify generate_pattern raises RuntimeError if PAM4 helper output contains slightly off-level symbols (exact equality check)."""
    off_level_symbols = np.array([-1.0, -0.333, 1.0 / 3.0, 1.0], dtype=np.float64)
    monkeypatch.setattr(pattern_config, "generate_random_pam4_symbols", lambda count, seed: off_level_symbols)
    with pytest.raises(RuntimeError, match="PAM4 pattern contains invalid symbol value"):
        generate_pattern(PatternConfig(pattern_type="pam4_random", count=4, seed=42))


def test_all_11_input_configs_serialization_round_trip():
    """Verify to_dict() and from_dict() round-trip for input PatternConfig across all 11 pattern types."""
    configs = [
        PatternConfig(pattern_type="nrz_random", count=10, seed=42),
        PatternConfig(pattern_type="nrz_all_zeros", count=6),
        PatternConfig(pattern_type="nrz_all_ones", count=6),
        PatternConfig(pattern_type="nrz_alternating", count=6, first_bit=1),
        PatternConfig(pattern_type="nrz_long_run", count=10, run_length=4, first_bit=0),
        PatternConfig(pattern_type="nrz_single_transition", count=6, transition_index=2, initial_bit=1),
        PatternConfig(pattern_type="nrz_single_bit_pulse", count=6, pulse_index=3, baseline_bit=0),
        PatternConfig(pattern_type="nrz_prbs", count=16, prbs_order=9, prbs_initial_state=511, prbs_convention_id="pcie_eq-prbs-fibonacci-lsb-v1"),
        PatternConfig(pattern_type="nrz_user_bits", count=4, user_values=(1, 0, 1, 0)),
        PatternConfig(pattern_type="pam4_random", count=10, seed=42),
        PatternConfig(pattern_type="pam4_user_symbols", count=4, user_values=(-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0)),
    ]

    for cfg in configs:
        d = cfg.to_dict()
        restored = PatternConfig.from_dict(d)
        assert restored == cfg


def test_all_11_resolved_configs_serialization_round_trip():
    """Verify to_dict() and from_dict() round-trip for resolved_config across all 11 pattern types."""
    input_configs = [
        PatternConfig(pattern_type="nrz_random", count=10, seed=42),
        PatternConfig(pattern_type="nrz_all_zeros", count=6),
        PatternConfig(pattern_type="nrz_all_ones", count=6),
        PatternConfig(pattern_type="nrz_alternating", count=6),
        PatternConfig(pattern_type="nrz_long_run", count=10, run_length=3),
        PatternConfig(pattern_type="nrz_single_transition", count=6, transition_index=2),
        PatternConfig(pattern_type="nrz_single_bit_pulse", count=6, pulse_index=3),
        PatternConfig(pattern_type="nrz_prbs", count=16, prbs_order=7),
        PatternConfig(pattern_type="nrz_user_bits", count=4, user_values=(True, False, 1, 0)),
        PatternConfig(pattern_type="pam4_random", count=10, seed=42),
        PatternConfig(pattern_type="pam4_user_symbols", count=4, user_values=(-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0)),
    ]

    for input_cfg in input_configs:
        res = generate_pattern(input_cfg)
        resolved_cfg = res.resolved_config
        d = resolved_cfg.to_dict()
        restored = PatternConfig.from_dict(d)
        assert restored == resolved_cfg


def test_prbs_custom_state_frozen_prefix():
    """Verify PRBS custom initial state prefix generation."""
    res = generate_pattern(PatternConfig(pattern_type="nrz_prbs", count=32, prbs_order=7, prbs_initial_state=1))
    expected_bits = np.array([int(c) for c in "10000001000001100001010001111001"], dtype=np.int8)
    assert np.array_equal(res.values, expected_bits)


def test_pam4_seeded_rng_isolation():
    """Verify seeded PAM4 random generation isolates global RNG."""
    initial_rng = np.random.get_state()
    try:
        cfg = PatternConfig(pattern_type="pam4_random", count=20, seed=999)
        res1 = generate_pattern(cfg)
        res2 = generate_pattern(cfg)
        assert np.array_equal(res1.values, res2.values)

        final_rng = np.random.get_state()
        assert initial_rng[0] == final_rng[0]
        assert np.array_equal(initial_rng[1], final_rng[1])
        assert initial_rng[2:] == final_rng[2:]
    finally:
        np.random.set_state(initial_rng)


def test_pam4_unseeded_global_rng_equivalence():
    """Verify seed=None for pam4_random uses global NumPy RNG identically to direct call."""
    initial_rng = np.random.get_state()
    try:
        np.random.seed(777)
        ref_symbols = generate_random_pam4_symbols(20, seed=None)

        np.random.seed(777)
        res = generate_pattern(PatternConfig(pattern_type="pam4_random", count=20, seed=None))
        assert res.rng_mode == "global"
        assert np.array_equal(res.values, ref_symbols)
    finally:
        np.random.set_state(initial_rng)


def test_serialized_user_values_list_copy_isolation():
    """Verify mutating the user_values list from to_dict() does not mutate original config."""
    cfg = PatternConfig(pattern_type="nrz_user_bits", count=3, user_values=(1, 0, 1))
    d = cfg.to_dict()
    assert d["user_values"] == [1, 0, 1]

    d["user_values"].append(999)
    assert cfg.user_values == (1, 0, 1)


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
    with pytest.raises(ValueError, match="is not applicable"):
        PatternConfig(pattern_type="nrz_random", count=10, run_length=3)
    with pytest.raises(ValueError, match="is not applicable"):
        PatternConfig(pattern_type="nrz_random", count=10, prbs_order=7)
    with pytest.raises(ValueError, match="is not applicable"):
        PatternConfig(pattern_type="nrz_all_zeros", count=10, seed=42)
    with pytest.raises(ValueError, match="is not applicable"):
        PatternConfig(pattern_type="nrz_prbs", count=10, prbs_order=7, first_bit=0)
    with pytest.raises(ValueError, match="is not applicable"):
        PatternConfig(pattern_type="pam4_user_symbols", count=2, user_values=(-1.0, 1.0), seed=42)


def test_pattern_config_constructor_validation_contracts():
    """Verify strict type and range validations in PatternConfig.__post_init__."""
    with pytest.raises(TypeError):
        PatternConfig(pattern_type="nrz_all_zeros", count=5, schema_version=123)
    with pytest.raises(ValueError, match="Unknown schema_version"):
        PatternConfig(pattern_type="nrz_all_zeros", count=5, schema_version="v2")

    with pytest.raises(TypeError):
        PatternConfig(pattern_type=123, count=5)
    with pytest.raises(ValueError, match="Unsupported pattern_type"):
        PatternConfig(pattern_type="NRZ_RANDOM", count=5)
    with pytest.raises(ValueError, match="Unsupported pattern_type"):
        PatternConfig(pattern_type="nrz_random ", count=5)

    for invalid_count in [True, False, 2.5, "10"]:
        with pytest.raises(TypeError):
            PatternConfig(pattern_type="nrz_all_zeros", count=invalid_count)
    with pytest.raises(ValueError):
        PatternConfig(pattern_type="nrz_all_zeros", count=-1)
    with pytest.raises(ValueError, match="requires count > 0"):
        PatternConfig(pattern_type="nrz_single_bit_pulse", count=0, pulse_index=0)

    for invalid_seed in [True, False, 2.5, "42", (42,)]:
        with pytest.raises(TypeError):
            PatternConfig(pattern_type="nrz_random", count=10, seed=invalid_seed)
    with pytest.raises(ValueError):
        PatternConfig(pattern_type="nrz_random", count=10, seed=-1)
    with pytest.raises(ValueError):
        PatternConfig(pattern_type="nrz_random", count=10, seed=2**32)

    for invalid_bit in [True, False, 2.5, "0", 2]:
        with pytest.raises((TypeError, ValueError)):
            PatternConfig(pattern_type="nrz_alternating", count=10, first_bit=invalid_bit)

    with pytest.raises(ValueError, match="requires run_length"):
        PatternConfig(pattern_type="nrz_long_run", count=10)
    for invalid_rl in [True, 0, -1, 1.5]:
        with pytest.raises((TypeError, ValueError)):
            PatternConfig(pattern_type="nrz_long_run", count=10, run_length=invalid_rl)

    with pytest.raises(ValueError, match="requires transition_index"):
        PatternConfig(pattern_type="nrz_single_transition", count=10)
    for invalid_ti in [-1, 11, 2.5, True]:
        with pytest.raises((TypeError, ValueError)):
            PatternConfig(pattern_type="nrz_single_transition", count=10, transition_index=invalid_ti)

    with pytest.raises(ValueError, match="requires pulse_index"):
        PatternConfig(pattern_type="nrz_single_bit_pulse", count=10)
    for invalid_pi in [-1, 10, 2.5, True]:
        with pytest.raises((TypeError, ValueError)):
            PatternConfig(pattern_type="nrz_single_bit_pulse", count=10, pulse_index=invalid_pi)

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

    with pytest.raises(ValueError, match="requires user_values"):
        PatternConfig(pattern_type="nrz_user_bits", count=2)
    with pytest.raises(TypeError, match="must be tuple"):
        PatternConfig(pattern_type="nrz_user_bits", count=2, user_values=[0, 1])
    with pytest.raises(ValueError, match="user_values length"):
        PatternConfig(pattern_type="nrz_user_bits", count=2, user_values=(0, 1, 1))

    with pytest.raises(TypeError, match="must be exact int or bool"):
        PatternConfig(pattern_type="nrz_user_bits", count=2, user_values=(0.0, 1.0))

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
        with pytest.raises((ValueError, TypeError)):
            PatternConfig(pattern_type="nrz_random", count=10, seed="invalid")

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
    res_nonempty = generate_pattern(PatternConfig(pattern_type="nrz_random", count=10, seed=42))
    assert res_nonempty.values.dtype == np.dtype("l")

    res_empty = generate_pattern(PatternConfig(pattern_type="nrz_random", count=0, seed=42))
    assert res_empty.values.dtype == np.dtype(int)

    if sys.platform == "win32":
        assert res_nonempty.values.dtype == np.int32
        assert res_empty.values.dtype == np.int64


def test_deterministic_nrz_boundary_cases():
    """Verify boundary cases for single_transition and single_bit_pulse."""
    res_t0 = generate_pattern(PatternConfig(pattern_type="nrz_single_transition", count=4, transition_index=0, initial_bit=0))
    assert np.array_equal(res_t0.values, np.array([1, 1, 1, 1]))

    res_t4 = generate_pattern(PatternConfig(pattern_type="nrz_single_transition", count=4, transition_index=4, initial_bit=0))
    assert np.array_equal(res_t4.values, np.array([0, 0, 0, 0]))

    res_p0 = generate_pattern(PatternConfig(pattern_type="nrz_single_bit_pulse", count=4, pulse_index=0, baseline_bit=0))
    assert np.array_equal(res_p0.values, np.array([1, 0, 0, 0]))

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
    cfg_user = PatternConfig(pattern_type="nrz_user_bits", count=4, user_values=(True, False, 1, 0))
    res_user = generate_pattern(cfg_user)
    assert res_user.resolved_config.user_values == (1, 0, 1, 0)
    assert np.array_equal(res_user.values, np.array([1, 0, 1, 0]))
    assert res_user.values.dtype == np.dtype(int)

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

    d["count"] = 999
    assert cfg.count == 10


def test_serialization_error_rejection():
    """Verify from_dict rejects non-mapping, missing keys, extra keys, and invalid versions."""
    with pytest.raises(TypeError):
        PatternConfig.from_dict("not_a_dict")

    valid_dict = PatternConfig(pattern_type="nrz_all_zeros", count=5).to_dict()

    missing_dict = valid_dict.copy()
    del missing_dict["seed"]
    with pytest.raises(ValueError, match="missing keys"):
        PatternConfig.from_dict(missing_dict)

    extra_dict = valid_dict.copy()
    extra_dict["unknown_extra"] = 123
    with pytest.raises(ValueError, match="extra keys"):
        PatternConfig.from_dict(extra_dict)

    bad_ver_dict = valid_dict.copy()
    bad_ver_dict["schema_version"] = "pcie_eq-pattern-config-v999"
    with pytest.raises(ValueError, match="Unknown schema_version"):
        PatternConfig.from_dict(bad_ver_dict)
