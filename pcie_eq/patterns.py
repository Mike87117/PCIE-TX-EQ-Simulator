"""
Pattern Generator Core Module for PCIe TX/RX EQ Simulator.

Provides GUI-independent NRZ bit generation, NRZ symbol conversion,
PAM4 random symbol generation, and deterministic NRZ test patterns.
"""

import numpy as np

__all__ = [
    "nrz_bits_to_symbols",
    "generate_random_nrz_bits",
    "generate_random_pam4_symbols",
    "generate_nrz_all_zeros",
    "generate_nrz_all_ones",
    "generate_nrz_alternating",
    "generate_nrz_long_run",
    "generate_nrz_single_transition",
    "generate_nrz_single_bit_pulse",
]


def _validate_count(count, allow_zero=True):
    """Helper to validate count parameter."""
    if not isinstance(count, int) or isinstance(count, bool):
        raise TypeError(f"count must be an integer, got {type(count).__name__}")
    if count < 0:
        raise ValueError(f"count must be >= 0, got {count}")
    if not allow_zero and count == 0:
        raise ValueError("count must be > 0")


def _validate_bit(bit, name="bit"):
    """Helper to validate 0/1 bit parameter."""
    if isinstance(bit, bool) or not isinstance(bit, int) or bit not in (0, 1):
        raise ValueError(f"{name} must be 0 or 1, got {bit}")


def nrz_bits_to_symbols(bits):
    """
    Convert NRZ bits (0/1) to NRZ symbols (-1.0/+1.0).

    Does not modify input bits array.
    """
    bits_arr = np.asarray(bits)
    if bits_arr.ndim != 1:
        raise ValueError(f"bits must be a 1D array, got shape {bits_arr.shape}")
    if bits_arr.size > 0:
        if not np.issubdtype(bits_arr.dtype, np.integer) and not np.issubdtype(bits_arr.dtype, np.bool_):
            raise ValueError("bits array must contain integer 0 or 1 values")
        if not np.isin(bits_arr, [0, 1]).all():
            raise ValueError("bits array must contain only 0 or 1")
    return np.where(bits_arr == 1, 1.0, -1.0).astype(float)


def generate_random_nrz_bits(count, seed=None):
    """
    Generate random NRZ bits (0/1).

    If seed is None, uses NumPy global RNG.
    If seed is specified, uses an isolated local RNG without mutating global RNG.
    """
    _validate_count(count)
    if count == 0:
        return np.array([], dtype=int)
    if seed is None:
        return np.random.randint(0, 2, count)
    rng = np.random.RandomState(seed)
    return rng.randint(0, 2, count)


def generate_random_pam4_symbols(count, seed=None):
    """
    Generate random PAM4 symbols [-1.0, -1.0/3.0, 1.0/3.0, 1.0].

    If seed is None, uses NumPy global RNG.
    If seed is specified, uses an isolated local RNG without mutating global RNG.
    """
    _validate_count(count)
    levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0], dtype=float)
    if count == 0:
        return np.array([], dtype=float)
    if seed is None:
        indices = np.random.randint(0, 4, count)
        return levels[indices]
    rng = np.random.RandomState(seed)
    indices = rng.randint(0, 4, count)
    return levels[indices]


def generate_nrz_all_zeros(count):
    """Generate all-zero NRZ bits array of length count."""
    _validate_count(count)
    return np.zeros(count, dtype=int)


def generate_nrz_all_ones(count):
    """Generate all-one NRZ bits array of length count."""
    _validate_count(count)
    return np.ones(count, dtype=int)


def generate_nrz_alternating(count, first_bit=0):
    """Generate alternating NRZ bits (e.g. 0, 1, 0, 1...) starting from first_bit."""
    _validate_count(count)
    _validate_bit(first_bit, "first_bit")
    if count == 0:
        return np.array([], dtype=int)
    arr = np.empty(count, dtype=int)
    arr[0::2] = first_bit
    arr[1::2] = 1 - first_bit
    return arr


def generate_nrz_long_run(count, run_length, first_bit=0):
    """Generate NRZ bits with blocks of repeated bits of length run_length."""
    _validate_count(count)
    if not isinstance(run_length, int) or isinstance(run_length, bool):
        raise TypeError(f"run_length must be an integer, got {type(run_length).__name__}")
    if run_length < 1:
        raise ValueError(f"run_length must be >= 1, got {run_length}")
    _validate_bit(first_bit, "first_bit")
    if count == 0:
        return np.array([], dtype=int)
    block_indices = np.arange(count) // run_length
    return ((first_bit + block_indices) % 2).astype(int)


def generate_nrz_single_transition(count, transition_index, initial_bit=0):
    """Generate NRZ bits starting with initial_bit and transitioning to 1 - initial_bit at transition_index."""
    _validate_count(count)
    _validate_bit(initial_bit, "initial_bit")
    if not isinstance(transition_index, int) or isinstance(transition_index, bool):
        raise TypeError(f"transition_index must be an integer, got {type(transition_index).__name__}")
    if transition_index < 0 or transition_index > count:
        raise ValueError(f"transition_index must be between 0 and count ({count}), got {transition_index}")
    arr = np.full(count, initial_bit, dtype=int)
    arr[transition_index:] = 1 - initial_bit
    return arr


def generate_nrz_single_bit_pulse(count, pulse_index, baseline_bit=0):
    """Generate NRZ bits filled with baseline_bit except a single pulse at pulse_index."""
    _validate_count(count, allow_zero=False)
    _validate_bit(baseline_bit, "baseline_bit")
    if not isinstance(pulse_index, int) or isinstance(pulse_index, bool):
        raise TypeError(f"pulse_index must be an integer, got {type(pulse_index).__name__}")
    if pulse_index < 0 or pulse_index >= count:
        raise ValueError(f"pulse_index must be between 0 and {count - 1}, got {pulse_index}")
    arr = np.full(count, baseline_bit, dtype=int)
    arr[pulse_index] = 1 - baseline_bit
    return arr
