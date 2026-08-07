"""Simplified NRZ receiver equalization core models."""

import numpy as np

from pcie_eq.channel import simple_channel
from pcie_eq.sampling import symbol_sample_index, validate_sampling_phase

__all__ = [
    "apply_ctle",
    "apply_dfe",
    "run_rx_pipeline",
]


def apply_ctle(wave, gain, alpha=0.08):
    """
    Simplified visual CTLE model.
    lowpass = simple_channel(wave)
    high_freq = wave - lowpass
    ctle = wave + gain * high_freq
    """
    if gain <= 0.0:
        return wave
    lowpass = simple_channel(wave, alpha=alpha)
    high_freq = wave - lowpass
    ctle = wave + gain * high_freq
    return ctle


def apply_dfe(ctle_wave, taps, spb, sampling_phase):
    """
    Symbol-rate Decision Feedback Equalizer.
    It uses previous slicer decisions to subtract estimated post-cursor ISI.

    Sign convention:
    corrected_sample[n] = sample[n] - tap1 * decision[n-1]
                                      - tap2 * decision[n-2]
                                      - tap3 * decision[n-3]

    Positive tap subtracts a positive post-cursor contribution when the previous decision is +1.
    Negative tap adds compensation in the opposite direction.

    This is a manual educational DFE model, not adaptive LMS and not PCIe compliance behavior.
    
    NOTE: DFE operates at symbol rate on sampling points. It does not
    generate a real analog waveform.
    """
    validate_sampling_phase(spb, sampling_phase)

    num_symbols = len(ctle_wave) // spb
    samples = np.zeros(num_symbols)
    for i in range(num_symbols):
        idx = symbol_sample_index(i, spb, sampling_phase)
        if idx < len(ctle_wave):
            samples[i] = ctle_wave[idx]
        else:
            samples[i] = ctle_wave[-1]

    decisions = np.zeros(num_symbols)
    corrected_samples = np.zeros(num_symbols)
    
    for i in range(num_symbols):
        feedback = 0.0
        for j, tap in enumerate(taps):
            prev_idx = i - 1 - j
            if prev_idx >= 0:
                feedback += tap * decisions[prev_idx]
                
        val = samples[i] - feedback
        corrected_samples[i] = val
        decisions[i] = 1.0 if val >= 0 else -1.0
        
    return samples, corrected_samples, decisions


def run_rx_pipeline(ch_wave, ctle_gain, ctle_alpha, dfe_taps, spb, sampling_phase):
    ctle_wave = apply_ctle(ch_wave, ctle_gain, alpha=ctle_alpha)
    samples, corrected_samples, decisions = apply_dfe(
        ctle_wave, dfe_taps, spb, sampling_phase
    )
    
    return {
        "ch_wave": ch_wave,
        "ctle_wave": ctle_wave,
        "dfe_input_samples": samples,
        "dfe_corrected_samples": corrected_samples,
        "dfe_decisions": decisions
    }
