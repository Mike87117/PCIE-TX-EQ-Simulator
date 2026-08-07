"""
Unit tests for pcie_eq.sampling core module according to pcie_eq-sampling-phase-v1.

Verifies:
1. validate_sampling_phase type and range validation matrix (spb, phase, bool/float rejections).
2. symbol_sample_index validation, type/range matrix, and hardcoded golden values.
3. select_phase_centered_trace_starts type/range validation, output contract (1D, int, C-contiguous, fresh allocation).
4. Hardcoded Golden cases A, B, C, D, E, F from Contract Addendum.
5. Determinism and call-to-call independence.
"""

import numpy as np
import pytest

from pcie_eq.sampling import (
    SAMPLING_PHASE_CONTRACT_ID,
    NRZ_WARMUP_SYMBOLS,
    symbol_sample_index,
    validate_sampling_phase,
    select_phase_centered_trace_starts,
)


def test_validate_sampling_phase_matrix():
    """Verify validate_sampling_phase accepts exact positive int spb and 0 <= phase < spb."""
    # Valid calls
    assert validate_sampling_phase(4, 0) is None
    assert validate_sampling_phase(4, 3) is None
    assert validate_sampling_phase(32, 16) is None
    assert validate_sampling_phase(1, 0) is None

    # spb type rejections (TypeError)
    with pytest.raises(TypeError, match="spb must be exact int"):
        validate_sampling_phase(True, 0)
    with pytest.raises(TypeError, match="spb must be exact int"):
        validate_sampling_phase(False, 0)
    with pytest.raises(TypeError, match="spb must be exact int"):
        validate_sampling_phase(4.0, 0)
    with pytest.raises(TypeError, match="spb must be exact int"):
        validate_sampling_phase("4", 0)

    # spb range rejections (ValueError)
    with pytest.raises(ValueError, match="spb must be > 0"):
        validate_sampling_phase(0, 0)
    with pytest.raises(ValueError, match="spb must be > 0"):
        validate_sampling_phase(-1, 0)

    # phase type rejections (TypeError)
    with pytest.raises(TypeError, match="phase must be exact int"):
        validate_sampling_phase(4, True)
    with pytest.raises(TypeError, match="phase must be exact int"):
        validate_sampling_phase(4, False)
    with pytest.raises(TypeError, match="phase must be exact int"):
        validate_sampling_phase(4, 2.0)
    with pytest.raises(TypeError, match="phase must be exact int"):
        validate_sampling_phase(4, "2")

    # phase range rejections (ValueError)
    with pytest.raises(ValueError, match="phase must satisfy"):
        validate_sampling_phase(4, -1)
    with pytest.raises(ValueError, match="phase must satisfy"):
        validate_sampling_phase(4, 4)
    with pytest.raises(ValueError, match="phase must satisfy"):
        validate_sampling_phase(4, 5)


def test_symbol_sample_index_hardcoded_goldens_and_validation():
    """Verify symbol_sample_index matches hardcoded contract addendum goldens and validates inputs."""
    # Hardcoded contract addendum goldens
    assert symbol_sample_index(0, 32, 0) == 0
    assert symbol_sample_index(0, 32, 16) == 16
    assert symbol_sample_index(3, 32, 16) == 112
    assert symbol_sample_index(5, 4, 3) == 23

    # Exact return type is Python int
    res = symbol_sample_index(5, 4, 3)
    assert type(res) is int

    # symbol_index type rejections (TypeError)
    with pytest.raises(TypeError, match="symbol_index must be exact int"):
        symbol_sample_index(True, 32, 0)
    with pytest.raises(TypeError, match="symbol_index must be exact int"):
        symbol_sample_index(False, 32, 0)
    with pytest.raises(TypeError, match="symbol_index must be exact int"):
        symbol_sample_index(1.5, 32, 0)
    with pytest.raises(TypeError, match="symbol_index must be exact int"):
        symbol_sample_index("1", 32, 0)

    # symbol_index range rejections (ValueError)
    with pytest.raises(ValueError, match="symbol_index must be >= 0"):
        symbol_sample_index(-1, 32, 0)

    # Delegates spb/phase validation
    with pytest.raises(TypeError, match="spb must be exact int"):
        symbol_sample_index(0, 32.0, 0)
    with pytest.raises(ValueError, match="phase must satisfy"):
        symbol_sample_index(0, 32, 32)


def test_select_phase_centered_trace_starts_golden_a():
    """Verify Golden A: canonical SPB=4, phase=2, warmup=2, wave_length=40."""
    res = select_phase_centered_trace_starts(
        wave_length=40,
        spb=4,
        phase=2,
        max_traces=100,
        warmup_symbols=2,
    )
    expected = np.array([6, 10, 14, 18, 22, 26, 30], dtype=int)
    assert type(res) is np.ndarray
    assert res.dtype == np.dtype(int)
    assert res.shape == expected.shape
    assert res.flags.c_contiguous
    assert np.array_equal(res, expected)


def test_select_phase_centered_trace_starts_golden_b():
    """Verify Golden B: phase boundary 0, SPB=4, warmup=2, wave_length=24."""
    res = select_phase_centered_trace_starts(
        wave_length=24,
        spb=4,
        phase=0,
        max_traces=100,
        warmup_symbols=2,
    )
    expected = np.array([4, 8, 12, 16], dtype=int)
    assert np.array_equal(res, expected)


def test_select_phase_centered_trace_starts_golden_c():
    """Verify Golden C: phase boundary spb-1 (3), SPB=4, warmup=2, wave_length=24."""
    res = select_phase_centered_trace_starts(
        wave_length=24,
        spb=4,
        phase=3,
        max_traces=100,
        warmup_symbols=2,
    )
    expected = np.array([7, 11, 15], dtype=int)
    assert np.array_equal(res, expected)


def test_select_phase_centered_trace_starts_golden_d():
    """Verify Golden D: max_traces=3 subsampling on Golden A candidate population."""
    res = select_phase_centered_trace_starts(
        wave_length=40,
        spb=4,
        phase=2,
        max_traces=3,
        warmup_symbols=2,
    )
    expected = np.array([6, 18, 30], dtype=int)
    assert np.array_equal(res, expected)


def test_select_phase_centered_trace_starts_golden_e():
    """Verify Golden E: too short / empty returns exact empty int array with shape (0,)."""
    res = select_phase_centered_trace_starts(
        wave_length=7,
        spb=4,
        phase=2,
        max_traces=100,
        warmup_symbols=0,
    )
    expected = np.array([], dtype=int)
    assert type(res) is np.ndarray
    assert res.dtype == np.dtype(int)
    assert res.shape == (0,)
    assert res.flags.c_contiguous
    assert np.array_equal(res, expected)


def test_select_phase_centered_trace_starts_golden_f():
    """Verify Golden F: non-multiple wave_length=23 rejects start 18 (18+8 > 23)."""
    res = select_phase_centered_trace_starts(
        wave_length=23,
        spb=4,
        phase=2,
        max_traces=100,
        warmup_symbols=2,
    )
    expected = np.array([6, 10, 14], dtype=int)
    assert np.array_equal(res, expected)


def test_select_phase_centered_trace_starts_type_and_range_validation():
    """Verify type and range validation order for wave_length, max_traces, warmup_symbols."""
    # wave_length validation
    with pytest.raises(TypeError, match="wave_length must be exact int"):
        select_phase_centered_trace_starts(True, 4, 0, 100)
    with pytest.raises(TypeError, match="wave_length must be exact int"):
        select_phase_centered_trace_starts(40.0, 4, 0, 100)
    with pytest.raises(ValueError, match="wave_length must be >= 0"):
        select_phase_centered_trace_starts(-1, 4, 0, 100)

    # max_traces validation
    with pytest.raises(TypeError, match="max_traces must be exact int"):
        select_phase_centered_trace_starts(40, 4, 0, True)
    with pytest.raises(TypeError, match="max_traces must be exact int"):
        select_phase_centered_trace_starts(40, 4, 0, 10.0)
    with pytest.raises(ValueError, match="max_traces must be > 0"):
        select_phase_centered_trace_starts(40, 4, 0, 0)
    with pytest.raises(ValueError, match="max_traces must be > 0"):
        select_phase_centered_trace_starts(40, 4, 0, -10)

    # warmup_symbols validation
    with pytest.raises(TypeError, match="warmup_symbols must be exact int"):
        select_phase_centered_trace_starts(40, 4, 0, 100, warmup_symbols=True)
    with pytest.raises(TypeError, match="warmup_symbols must be exact int"):
        select_phase_centered_trace_starts(40, 4, 0, 100, warmup_symbols=2.0)
    with pytest.raises(ValueError, match="warmup_symbols must be >= 0"):
        select_phase_centered_trace_starts(40, 4, 0, 100, warmup_symbols=-1)


def test_select_phase_centered_trace_starts_allocation_isolation():
    """Verify repeat calls produce fresh independent numpy.ndarray allocations."""
    res1 = select_phase_centered_trace_starts(40, 4, 2, 100, 2)
    res2 = select_phase_centered_trace_starts(40, 4, 2, 100, 2)

    assert res1 is not res2
    assert not np.shares_memory(res1, res2)

    res1[0] = 999
    assert res2[0] == 6
