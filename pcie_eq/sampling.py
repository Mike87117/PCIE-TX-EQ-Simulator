"""
Sampling Phase Core Module for PCIe TX/RX EQ Simulator.

Provides pure sampling coordinate validation, decision-point index mapping,
and phase-centered 2-UI trace-start population selection according to contract
pcie_eq-sampling-phase-v1 (revision 1.0).
"""

import numpy as np

SAMPLING_PHASE_CONTRACT_ID = "pcie_eq-sampling-phase-v1"
NRZ_WARMUP_SYMBOLS = 20

__all__ = [
    "SAMPLING_PHASE_CONTRACT_ID",
    "NRZ_WARMUP_SYMBOLS",
    "validate_sampling_phase",
    "symbol_sample_index",
    "select_phase_centered_trace_starts",
]


def validate_sampling_phase(spb: int, phase: int) -> None:
    """Validate spb and sampling phase according to pcie_eq-sampling-phase-v1.

    Validation order:
    1. spb exact int (bool rejected with TypeError)
    2. spb > 0 (otherwise ValueError)
    3. phase exact int (bool rejected with TypeError)
    4. 0 <= phase < spb (otherwise ValueError)
    """
    if type(spb) is not int:
        raise TypeError(f"spb must be exact int, got {type(spb).__name__}")
    if spb <= 0:
        raise ValueError(f"spb must be > 0, got {spb}")

    if type(phase) is not int:
        raise TypeError(f"phase must be exact int, got {type(phase).__name__}")
    if not (0 <= phase < spb):
        raise ValueError(f"phase must satisfy 0 <= phase < spb ({spb}), got {phase}")


def symbol_sample_index(symbol_index: int, spb: int, phase: int) -> int:
    """Calculate the canonical sample index for a given symbol index and phase.

    Validation order:
    1. Validate spb and phase via validate_sampling_phase()
    2. symbol_index exact int (bool rejected with TypeError)
    3. symbol_index >= 0 (otherwise ValueError)

    Returns:
        int: symbol_index * spb + phase
    """
    validate_sampling_phase(spb, phase)

    if type(symbol_index) is not int:
        raise TypeError(f"symbol_index must be exact int, got {type(symbol_index).__name__}")
    if symbol_index < 0:
        raise ValueError(f"symbol_index must be >= 0, got {symbol_index}")

    return int(symbol_index * spb + phase)


def select_phase_centered_trace_starts(
    wave_length: int,
    spb: int,
    phase: int,
    max_traces: int,
    warmup_symbols: int = NRZ_WARMUP_SYMBOLS,
) -> np.ndarray:
    """Select the phase-centered 2-UI trace-start sample indices.

    Validation order:
    1. Validate spb / phase via validate_sampling_phase()
    2. wave_length exact int (bool rejected with TypeError); require wave_length >= 0
    3. max_traces exact int (bool rejected with TypeError); require max_traces > 0
    4. warmup_symbols exact int (bool rejected with TypeError); require warmup_symbols >= 0

    Returns:
        np.ndarray: 1D array of dtype int containing selected trace-start indices.
    """
    validate_sampling_phase(spb, phase)

    if type(wave_length) is not int:
        raise TypeError(f"wave_length must be exact int, got {type(wave_length).__name__}")
    if wave_length < 0:
        raise ValueError(f"wave_length must be >= 0, got {wave_length}")

    if type(max_traces) is not int:
        raise TypeError(f"max_traces must be exact int, got {type(max_traces).__name__}")
    if max_traces <= 0:
        raise ValueError(f"max_traces must be > 0, got {max_traces}")

    if type(warmup_symbols) is not int:
        raise TypeError(f"warmup_symbols must be exact int, got {type(warmup_symbols).__name__}")
    if warmup_symbols < 0:
        raise ValueError(f"warmup_symbols must be >= 0, got {warmup_symbols}")

    trace_length = 2 * spb
    eligible_starts: list[int] = []

    n = warmup_symbols
    while True:
        center = n * spb + phase
        trace_start = center - spb
        if trace_start < 0:
            n += 1
            continue
        if trace_start + trace_length > wave_length:
            break

        eligible_starts.append(trace_start)
        n += 1

    count = len(eligible_starts)
    if count == 0:
        return np.array([], dtype=int)

    arr = np.array(eligible_starts, dtype=int)

    if count > max_traces:
        idx = np.linspace(0, count - 1, max_traces, dtype=int)
        selected = arr[idx]
        return np.array(selected, copy=True, dtype=int)
    else:
        return arr
