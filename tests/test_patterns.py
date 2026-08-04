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
