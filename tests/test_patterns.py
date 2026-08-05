"""
Unit tests for pcie_eq.patterns core module.

Verifies:
1. Hardcoded expected vectors for fixed NRZ pattern generators:
   - All 0s / All 1s
   - Alternating (first_bit=0, first_bit=1)
   - Long run (count=10, run_length=3, first_bit=0 and first_bit=1)
   - Single transition (initial_bit=0 and initial_bit=1)
   - Single-bit pulse (baseline_bit=0 and baseline_bit=1)
2. Edge cases: count=0 returning empty 1D arrays with correct dtypes.
3. Validation contracts (TypeError for non-integers, ValueError for negative counts,
   invalid bit arguments, or out-of-bound indices).
4. nrz_bits_to_symbols conversion: output values in {-1.0, 1.0}, float64 dtype, input array immutability.
5. Random pattern generators (NRZ & PAM4):
   - Hardcoded golden vectors for fixed seeds.
   - Reproducibility across identical seeds.
   - Different sequences produced by different seeds.
   - Seeded calls preserve global NumPy RNG state.
   - seed=None equivalence to legacy np.random.randint calls.
6. GUI compatibility & static fingerprint baseline consistency.
"""

import hashlib
import numpy as np
import pytest

from pcie_eq.patterns import (
    nrz_bits_to_symbols,
    generate_random_nrz_bits,
    generate_random_pam4_symbols,
    generate_nrz_all_zeros,
    generate_nrz_all_ones,
    generate_nrz_alternating,
    generate_nrz_long_run,
    generate_nrz_single_transition,
    generate_nrz_single_bit_pulse,
    generate_prbs_bits,
)


def test_nrz_bits_to_symbols_conversion_and_immutability():
    """Verify nrz_bits_to_symbols converts 0/1 bits to -1.0/+1.0 float64 and leaves input intact."""
    bits_orig = np.array([0, 1, 0, 0, 1, 1], dtype=int)
    bits_copy = bits_orig.copy()

    symbols = nrz_bits_to_symbols(bits_orig)

    assert symbols.dtype == np.float64
    assert np.array_equal(symbols, np.array([-1.0, 1.0, -1.0, -1.0, 1.0, 1.0]))
    assert np.array_equal(bits_orig, bits_copy), "Input bits array was modified in-place"


def test_nrz_bits_to_symbols_validation():
    """Verify nrz_bits_to_symbols rejects invalid inputs."""
    with pytest.raises(ValueError, match="1D array"):
        nrz_bits_to_symbols(np.array([[0, 1], [1, 0]]))

    with pytest.raises(ValueError, match="contain only 0 or 1"):
        nrz_bits_to_symbols(np.array([0, 1, 2]))

    with pytest.raises(ValueError, match="contain only 0 or 1"):
        nrz_bits_to_symbols(np.array([-1, 0, 1]))


def test_fixed_patterns_all_zeros_and_ones():
    """Verify all_zeros and all_ones fixed pattern output vectors."""
    zeros = generate_nrz_all_zeros(6)
    assert np.array_equal(zeros, np.array([0, 0, 0, 0, 0, 0]))
    assert np.issubdtype(zeros.dtype, np.integer)

    ones = generate_nrz_all_ones(6)
    assert np.array_equal(ones, np.array([1, 1, 1, 1, 1, 1]))
    assert np.issubdtype(ones.dtype, np.integer)


def test_fixed_pattern_alternating():
    """Verify alternating pattern with first_bit=0 and first_bit=1."""
    alt0 = generate_nrz_alternating(6, first_bit=0)
    assert np.array_equal(alt0, np.array([0, 1, 0, 1, 0, 1]))

    alt1 = generate_nrz_alternating(6, first_bit=1)
    assert np.array_equal(alt1, np.array([1, 0, 1, 0, 1, 0]))


def test_fixed_pattern_long_run():
    """Verify long run pattern with specified run lengths and first_bit."""
    lr0 = generate_nrz_long_run(count=10, run_length=3, first_bit=0)
    assert np.array_equal(lr0, np.array([0, 0, 0, 1, 1, 1, 0, 0, 0, 1]))

    lr1 = generate_nrz_long_run(count=10, run_length=3, first_bit=1)
    assert np.array_equal(lr1, np.array([1, 1, 1, 0, 0, 0, 1, 1, 1, 0]))


def test_fixed_pattern_single_transition():
    """Verify single transition pattern with initial_bit=0 and initial_bit=1."""
    st0 = generate_nrz_single_transition(count=6, transition_index=3, initial_bit=0)
    assert np.array_equal(st0, np.array([0, 0, 0, 1, 1, 1]))

    st1 = generate_nrz_single_transition(count=6, transition_index=2, initial_bit=1)
    assert np.array_equal(st1, np.array([1, 1, 0, 0, 0, 0]))

    # Boundary transition indices
    st_start = generate_nrz_single_transition(count=4, transition_index=0, initial_bit=0)
    assert np.array_equal(st_start, np.array([1, 1, 1, 1]))

    st_end = generate_nrz_single_transition(count=4, transition_index=4, initial_bit=0)
    assert np.array_equal(st_end, np.array([0, 0, 0, 0]))


def test_fixed_pattern_single_bit_pulse():
    """Verify single-bit pulse pattern with baseline_bit=0 and baseline_bit=1."""
    pulse0 = generate_nrz_single_bit_pulse(count=6, pulse_index=2, baseline_bit=0)
    assert np.array_equal(pulse0, np.array([0, 0, 1, 0, 0, 0]))

    pulse1 = generate_nrz_single_bit_pulse(count=6, pulse_index=4, baseline_bit=1)
    assert np.array_equal(pulse1, np.array([1, 1, 1, 1, 0, 1]))


def test_pattern_generators_count_zero():
    """Verify count=0 behavior returning empty arrays with expected dtypes across all pattern generators."""
    generators_int = [
        generate_random_nrz_bits,
        generate_nrz_all_zeros,
        generate_nrz_all_ones,
        generate_nrz_alternating,
        lambda c: generate_nrz_long_run(c, run_length=2),
        lambda c: generate_nrz_single_transition(c, transition_index=0),
    ]

    for gen in generators_int:
        res = gen(0)
        assert isinstance(res, np.ndarray)
        assert res.size == 0
        assert res.ndim == 1
        assert np.issubdtype(res.dtype, np.integer)

    # PAM4 symbol generator count=0
    pam4_empty = generate_random_pam4_symbols(0)
    assert isinstance(pam4_empty, np.ndarray)
    assert pam4_empty.size == 0
    assert pam4_empty.ndim == 1
    assert pam4_empty.dtype == np.float64


def test_validation_contracts():
    """Verify type and value error assertions across generator functions."""
    # count non-integer or negative
    for invalid_count in ["10", 3.5, True, False]:
        with pytest.raises(TypeError):
            generate_random_nrz_bits(invalid_count)
        with pytest.raises(TypeError):
            generate_random_pam4_symbols(invalid_count)
        with pytest.raises(TypeError):
            generate_nrz_all_zeros(invalid_count)

    with pytest.raises(ValueError):
        generate_random_nrz_bits(-1)
    with pytest.raises(ValueError):
        generate_random_pam4_symbols(-5)

    # pulse pattern requires count > 0
    with pytest.raises(ValueError):
        generate_nrz_single_bit_pulse(0, pulse_index=0)

    # invalid bit values
    for invalid_bit in [-1, 2, 0.5, "0", True]:
        with pytest.raises(ValueError):
            generate_nrz_alternating(5, first_bit=invalid_bit)
        with pytest.raises(ValueError):
            generate_nrz_single_transition(5, transition_index=2, initial_bit=invalid_bit)
        with pytest.raises(ValueError):
            generate_nrz_single_bit_pulse(5, pulse_index=2, baseline_bit=invalid_bit)

    # invalid run_length
    with pytest.raises(TypeError):
        generate_nrz_long_run(10, run_length="2")
    with pytest.raises(TypeError):
        generate_nrz_long_run(10, run_length=2.5)
    with pytest.raises(TypeError):
        generate_nrz_long_run(10, run_length=True)
    with pytest.raises(ValueError):
        generate_nrz_long_run(10, run_length=0)

    # invalid transition_index
    with pytest.raises(TypeError):
        generate_nrz_single_transition(10, transition_index="3")
    with pytest.raises(ValueError):
        generate_nrz_single_transition(10, transition_index=-1)
    with pytest.raises(ValueError):
        generate_nrz_single_transition(10, transition_index=11)

    # invalid pulse_index
    with pytest.raises(TypeError):
        generate_nrz_single_bit_pulse(10, pulse_index="3")
    with pytest.raises(ValueError):
        generate_nrz_single_bit_pulse(10, pulse_index=-1)
    with pytest.raises(ValueError):
        generate_nrz_single_bit_pulse(10, pulse_index=10)


def test_seeded_random_generation_golden_vectors_and_isolation():
    """Verify seeded random generation against hardcoded golden vectors, seed reproducibility, and global RNG isolation."""
    initial_state = np.random.get_state()
    try:
        # NRZ Seeded golden vector (seed=42, count=10)
        nrz_seq1 = generate_random_nrz_bits(10, seed=42)
        nrz_seq2 = generate_random_nrz_bits(10, seed=42)
        expected_nrz_42 = np.array([0, 1, 0, 0, 0, 1, 0, 0, 0, 1])

        assert np.array_equal(nrz_seq1, expected_nrz_42)
        assert np.array_equal(nrz_seq1, nrz_seq2)

        # Different seed produces different sequence
        nrz_seq_diff = generate_random_nrz_bits(10, seed=123)
        assert not np.array_equal(nrz_seq1, nrz_seq_diff)

        # PAM4 Seeded golden vector (seed=42, count=10)
        pam4_seq1 = generate_random_pam4_symbols(10, seed=42)
        pam4_seq2 = generate_random_pam4_symbols(10, seed=42)
        expected_pam4_42 = np.array([
            1.0 / 3.0, 1.0, -1.0, 1.0 / 3.0, 1.0 / 3.0,
            1.0, -1.0, -1.0, 1.0 / 3.0, -1.0 / 3.0
        ])

        assert np.allclose(pam4_seq1, expected_pam4_42)
        assert np.array_equal(pam4_seq1, pam4_seq2)

        pam4_seq_diff = generate_random_pam4_symbols(10, seed=123)
        assert not np.allclose(pam4_seq1, pam4_seq_diff)

        # Verify global RNG state was not mutated by seeded calls
        final_state = np.random.get_state()
        assert initial_state[0] == final_state[0]
        assert np.array_equal(initial_state[1], final_state[1])
        assert initial_state[2:] == final_state[2:]
    finally:
        np.random.set_state(initial_state)


def test_unseeded_global_rng_equivalence():
    """Verify seed=None equivalence to direct np.random.randint calls."""
    initial_state = np.random.get_state()
    try:
        np.random.seed(99)
        ref_nrz = np.random.randint(0, 2, 50)

        np.random.seed(99)
        gen_nrz = generate_random_nrz_bits(50, seed=None)

        assert np.array_equal(ref_nrz, gen_nrz)

        levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0], dtype=float)
        np.random.seed(99)
        ref_pam4 = levels[np.random.randint(0, 4, 50)]

        np.random.seed(99)
        gen_pam4 = generate_random_pam4_symbols(50, seed=None)

        assert np.array_equal(ref_pam4, gen_pam4)
    finally:
        np.random.set_state(initial_state)


import sys
from PyQt5.QtWidgets import QApplication
from pcie_eq.gui.constants import BIT_COUNT
from main import PCIeTxEqSimulator


@pytest.fixture(scope="module")
def qapp():
    """Reusable QApplication instance fixture for GUI testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_gui_window_bits_and_symbols_fingerprints():
    """Verify window.bits and window.symbols static raw-byte fingerprints and integer dtype contracts match baseline."""
    from pcie_eq.gui import window

    assert window.bits.ndim == 1
    assert window.symbols.ndim == 1
    assert np.issubdtype(window.bits.dtype, np.integer)
    assert np.issubdtype(window.symbols.dtype, np.integer)
    assert window.symbols.dtype == window.bits.dtype
    assert np.array_equal(window.symbols, 2 * window.bits - 1)

    bits_bytes = np.ascontiguousarray(window.bits).tobytes()
    bits_digest = hashlib.sha256(bits_bytes).hexdigest()
    if window.bits.dtype == np.int32:
        expected_bits_sha = "aac8c321ab4dc0aa718baa06e8c2d4ba106110ca10b265decb78637cf3195285"
    else:
        expected_bits_sha = "2493782381dbfd8df3986df590e95feeb0fa20afa76105f5d1a2b38a559f5392"
    assert bits_digest == expected_bits_sha, f"bits SHA mismatch: got {bits_digest}, expected {expected_bits_sha}"

    symbols_bytes = np.ascontiguousarray(window.symbols).tobytes()
    symbols_digest = hashlib.sha256(symbols_bytes).hexdigest()
    if window.symbols.dtype == np.int32:
        expected_symbols_sha = "35d846fbff0bdf1e22005844f6a5e08ace72e2be951bbd439745e064464ebb1a"
    else:
        expected_symbols_sha = "3ea421d4936ab544f825032d24ee5a164fc656bb66cc362a3c81e208d2c1d091"
    assert symbols_digest == expected_symbols_sha, f"symbols SHA mismatch: got {symbols_digest}, expected {expected_symbols_sha}"


def test_gui_on_generate_new_waveform_dtype_and_state_contracts(qapp):
    """Verify on_generate_new_waveform maintains integer bits/symbols dtype, array shapes, and equivalent conversion."""
    win = PCIeTxEqSimulator()
    try:
        win.on_generate_new_waveform()

        assert win.bits.ndim == 1
        assert win.symbols.ndim == 1
        assert win.bits.shape == (BIT_COUNT,)
        assert win.symbols.shape == (BIT_COUNT,)

        assert np.issubdtype(win.bits.dtype, np.integer)
        assert np.issubdtype(win.symbols.dtype, np.integer)
        assert win.symbols.dtype == win.bits.dtype
        assert np.array_equal(win.symbols, 2 * win.bits - 1)
    finally:
        win.close()


# --- PRBS Generator Core Tests (Implementation 23 / Issue #54) ---

GOLDEN_ALL_ONES_64 = {
    7: np.array([int(c) for c in "1111111000000100000110000101000111100100010110011101010011111010"], dtype=np.int8),
    9: np.array([int(c) for c in "1111111110000011110111110001011100110010000010010100111011010001"], dtype=np.int8),
    15: np.array([int(c) for c in "1111111111111110000000000000010000000000000110000000000001010000"], dtype=np.int8),
    23: np.array([int(c) for c in "1111111111111111111111100000000000000000011111000000000000011111"], dtype=np.int8),
    31: np.array([int(c) for c in "1111111111111111111111111111111000000000000000000000000000011100"], dtype=np.int8),
}

GOLDEN_INIT_1_32 = {
    7: np.array([int(c) for c in "10000001000001100001010001111001"], dtype=np.int8),
    9: np.array([int(c) for c in "10000000010000100011000010011100"], dtype=np.int8),
    15: np.array([int(c) for c in "10000000000000010000000000000110"], dtype=np.int8),
    23: np.array([int(c) for c in "10000000000000000000000100000000"], dtype=np.int8),
    31: np.array([int(c) for c in "10000000000000000000000000000001"], dtype=np.int8),
}


def test_prbs_frozen_golden_vectors_all_ones():
    """Verify default all-ones initial state 64-bit Golden prefixes across PRBS7/9/15/23/31."""
    for order, expected in GOLDEN_ALL_ONES_64.items():
        actual = generate_prbs_bits(order, 64)
        assert actual.dtype == np.int8
        assert np.array_equal(actual, expected), f"PRBS{order} all-ones golden prefix mismatch"


def test_prbs_frozen_golden_vectors_initial_state_1():
    """Verify initial_state=1 32-bit Golden prefixes across PRBS7/9/15/23/31."""
    for order, expected in GOLDEN_INIT_1_32.items():
        actual = generate_prbs_bits(order, 32, initial_state=1)
        assert actual.dtype == np.int8
        assert np.array_equal(actual, expected), f"PRBS{order} initial_state=1 golden prefix mismatch"


def test_prbs_output_contract_shape_dtype_values():
    """Verify output contract for PRBS generator: np.int8, shape (count,), values in {0, 1}."""
    for order in (7, 9, 15, 23, 31):
        bits = generate_prbs_bits(order, 100)
        assert isinstance(bits, np.ndarray)
        assert bits.shape == (100,)
        assert bits.dtype == np.int8
        assert set(bits).issubset({0, 1})


def test_prbs_count_zero_and_validation():
    """Verify count=0 returns empty np.int8 array, and invalid order/state are validated even when count=0."""
    empty = generate_prbs_bits(7, 0)
    assert isinstance(empty, np.ndarray)
    assert empty.shape == (0,)
    assert empty.dtype == np.int8

    # Must validate order and initial_state even if count=0
    with pytest.raises(ValueError):
        generate_prbs_bits(8, 0)
    with pytest.raises(TypeError):
        generate_prbs_bits(True, 0)
    with pytest.raises(ValueError):
        generate_prbs_bits(7, 0, initial_state=0)
    with pytest.raises(ValueError):
        generate_prbs_bits(7, 0, initial_state=128)
    with pytest.raises(TypeError):
        generate_prbs_bits(7, 0, initial_state="invalid")


def test_prbs_validation_contracts():
    """Verify type and value validation contracts for order, count, and initial_state."""
    # order validation
    for invalid_order in [True, False, 3.14, "7", None]:
        with pytest.raises(TypeError):
            generate_prbs_bits(invalid_order, 10)
    for invalid_order in [0, 5, 8, 16, 32, -7]:
        with pytest.raises(ValueError):
            generate_prbs_bits(invalid_order, 10)

    # count validation
    for invalid_count in [True, False, 2.5, "10"]:
        with pytest.raises(TypeError):
            generate_prbs_bits(7, invalid_count)
    with pytest.raises(ValueError):
        generate_prbs_bits(7, -1)

    # initial_state validation
    for invalid_state in [True, False, 1.5, "1"]:
        with pytest.raises(TypeError):
            generate_prbs_bits(7, 10, initial_state=invalid_state)
    for invalid_state in [0, -1, 128]:
        with pytest.raises(ValueError):
            generate_prbs_bits(7, 10, initial_state=invalid_state)

    # Valid initial_state boundary: 1 and (1 << order) - 1
    generate_prbs_bits(7, 5, initial_state=1)
    generate_prbs_bits(7, 5, initial_state=127)


def test_prbs_rng_isolation():
    """Verify calling generate_prbs_bits does not alter NumPy global RNG state."""
    initial_rng_state = np.random.get_state()
    try:
        generate_prbs_bits(7, 100)
        generate_prbs_bits(15, 500, initial_state=42)
        generate_prbs_bits(31, 1000)

        final_rng_state = np.random.get_state()
        assert initial_rng_state[0] == final_rng_state[0]
        assert np.array_equal(initial_rng_state[1], final_rng_state[1])
        assert initial_rng_state[2:] == final_rng_state[2:]
    finally:
        np.random.set_state(initial_rng_state)


def test_prbs_repeatability_and_initial_states():
    """Verify bit-exact repeatability and sequence divergence for different initial states."""
    seq1 = generate_prbs_bits(7, 100, initial_state=42)
    seq2 = generate_prbs_bits(7, 100, initial_state=42)
    assert np.array_equal(seq1, seq2)

    seq_diff = generate_prbs_bits(7, 100, initial_state=43)
    assert not np.array_equal(seq1, seq_diff)


def _independent_lfsr_step(state_tuple, order):
    """Independent bit-array LFSR reference step for test validation."""
    tap_map = {7: 6, 9: 5, 15: 14, 23: 18, 31: 28}
    k = tap_map[order]
    shift_pos = order - k
    output_bit = state_tuple[0]
    feedback = state_tuple[0] ^ state_tuple[shift_pos]
    next_state = state_tuple[1:] + (feedback,)
    return output_bit, next_state


def test_prbs_full_period_traversal():
    """Verify full period traversal (2^n - 1) for PRBS7, PRBS9, and PRBS15."""
    for order in (7, 9, 15):
        period = (1 << order) - 1
        gen_bits = generate_prbs_bits(order, period + 1)

        # Build reference sequence and track state uniqueness
        ref_bits = np.empty(period + 1, dtype=np.int8)
        state_tuple = (1,) * order
        visited_states = set()

        for i in range(period):
            assert state_tuple not in visited_states, f"PRBS{order} repeated state prematurely at step {i}"
            assert state_tuple != (0,) * order, f"PRBS{order} entered all-zero state at step {i}"
            visited_states.add(state_tuple)

            out_bit, state_tuple = _independent_lfsr_step(state_tuple, order)
            ref_bits[i] = out_bit

        # After period steps, state must return to initial state (all ones)
        assert state_tuple == (1,) * order, f"PRBS{order} state did not return to initial state after period {period}"
        out_bit, _ = _independent_lfsr_step(state_tuple, order)
        ref_bits[period] = out_bit

        assert len(visited_states) == period, f"PRBS{order} did not cover all 2^n - 1 states"
        assert np.array_equal(gen_bits, ref_bits), f"PRBS{order} sequence mismatch with independent test reference"
        assert gen_bits[period] == gen_bits[0], f"PRBS{order} bit at period index does not equal initial bit"


def test_prbs23_31_spot_checks_and_prefix_consistency():
    """Verify spot checks, long prefix repeatability, and prefix slice consistency for PRBS23 and PRBS31."""
    for order in (23, 31):
        # Long prefix repeatability
        s1 = generate_prbs_bits(order, 5000)
        s2 = generate_prbs_bits(order, 5000)
        assert np.array_equal(s1, s2)

        # Prefix slice consistency: generate(count=a+b)[:a] == generate(count=a)
        a, b = 2000, 3000
        full_seq = generate_prbs_bits(order, a + b, initial_state=12345)
        prefix_seq = generate_prbs_bits(order, a, initial_state=12345)
        assert np.array_equal(full_seq[:a], prefix_seq)
