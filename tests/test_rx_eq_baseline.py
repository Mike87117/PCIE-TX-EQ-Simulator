"""
RX Equalization Baseline Tests for PCIE-TX-EQ-Simulator.

Locks in existing pre-refactor behavior of:
- apply_ctle()
- apply_dfe()
- run_rx_pipeline()
"""

import pytest
import numpy as np
from pcie_eq.channel import simple_channel
from pcie_eq.rx_eq import (
    apply_ctle,
    apply_dfe,
    run_rx_pipeline,
)


def test_ctle_gain_zero_identity():
    """
    Verify apply_ctle with gain=0 returns original waveform unchanged.
    Also verify input waveform is not modified in place.
    """
    wave = np.array([0.5, 1.0, 0.8, -0.2, -1.0], dtype=float)
    wave_copy = wave.copy()

    ctle_wave = apply_ctle(wave, gain=0.0, alpha=0.08)

    assert ctle_wave is wave
    assert len(ctle_wave) == len(wave)
    np.testing.assert_array_equal(wave, wave_copy)
    np.testing.assert_allclose(ctle_wave, wave, rtol=1e-7, atol=1e-7)


def test_ctle_gain_positive_golden():
    """
    Verify apply_ctle mathematical behavior for positive gain.

    Formula:
    lowpass = simple_channel(wave, alpha)
    high_freq = wave - lowpass
    ctle = wave + gain * high_freq
    """
    wave = np.array([1.0, 0.5, 0.0, -0.5, -1.0], dtype=float)
    wave_copy = wave.copy()
    gain = 2.0
    alpha = 0.5

    ctle_wave = apply_ctle(wave, gain=gain, alpha=alpha)

    assert len(ctle_wave) == len(wave)
    np.testing.assert_array_equal(wave, wave_copy)

    lowpass_exp = simple_channel(wave, alpha=alpha)
    high_freq_exp = wave - lowpass_exp
    expected_ctle = wave + gain * high_freq_exp

    np.testing.assert_allclose(ctle_wave, expected_ctle, rtol=1e-6, atol=1e-6)


def test_dfe_zero_taps_identity():
    """
    Verify apply_dfe with zero taps (taps=[0.0, 0.0, 0.0]) produces
    corrected_samples identical to input sampled values.
    Verify decisions are strictly +1.0 or -1.0.
    """
    spb = 4
    sampling_phase = 1
    # Create 4 symbols of 4 samples each
    # Sampled points at index 1, 5, 9, 13 will be: 0.8, -0.5, 1.2, -0.1
    ctle_wave = np.array([
        0.0, 0.8, 0.5, 0.2,
        0.0, -0.5, -0.2, 0.1,
        0.0, 1.2, 0.9, 0.4,
        0.0, -0.1, -0.05, 0.0
    ], dtype=float)

    taps = [0.0, 0.0, 0.0]
    samples, corrected_samples, decisions = apply_dfe(
        ctle_wave, taps, spb=spb, sampling_phase=sampling_phase
    )

    expected_samples = np.array([0.8, -0.5, 1.2, -0.1], dtype=float)
    expected_decisions = np.array([1.0, -1.0, 1.0, -1.0], dtype=float)

    assert len(samples) == 4
    assert len(corrected_samples) == 4
    assert len(decisions) == 4

    np.testing.assert_allclose(samples, expected_samples, rtol=1e-7, atol=1e-7)
    np.testing.assert_allclose(corrected_samples, expected_samples, rtol=1e-7, atol=1e-7)
    np.testing.assert_array_equal(decisions, expected_decisions)

    # Decisions must be strictly -1 or +1
    for d in decisions:
        assert d in (-1.0, 1.0)


def test_dfe_sign_convention_and_feedback():
    """
    Verify DFE feedback sign convention:
    val = samples[i] - feedback
    feedback = sum(tap * decisions[prev_idx])

    If samples[0] = +1.0 -> decision[0] = +1.0
    If samples[1] = +0.4 (suffering post-cursor ISI of +0.3)
    With tap1 = +0.3:
      feedback = 0.3 * decision[0] = +0.3
      val = 0.4 - 0.3 = 0.1 -> corrected_samples[1] = 0.1, decision[1] = +1.0

    If DFE sign convention were inverted (+ feedback), val would be 0.4 + 0.3 = 0.7.
    This test verifies the subtractive feedback behavior (subtraction of post-cursor ISI).
    """
    spb = 1
    sampling_phase = 0
    ctle_wave = np.array([1.0, 0.4, -0.2], dtype=float)
    taps = [0.3, 0.1, 0.0]

    samples, corrected_samples, decisions = apply_dfe(
        ctle_wave, taps, spb=spb, sampling_phase=sampling_phase
    )

    # Symbol 0: sample = 1.0, feedback = 0.0 -> val = 1.0, decision = +1.0
    # Symbol 1: sample = 0.4, feedback = 0.3 * (+1.0) = 0.3 -> val = 0.4 - 0.3 = 0.1, decision = +1.0
    # Symbol 2: sample = -0.2, feedback = 0.3 * decision[1] + 0.1 * decision[0]
    #                                  = 0.3 * (1.0) + 0.1 * (1.0) = 0.4
    #                        -> val = -0.2 - 0.4 = -0.6, decision = -1.0

    expected_corrected = np.array([1.0, 0.1, -0.6], dtype=float)
    expected_decisions = np.array([1.0, 1.0, -1.0], dtype=float)

    np.testing.assert_allclose(samples, ctle_wave, rtol=1e-7, atol=1e-7)
    np.testing.assert_allclose(corrected_samples, expected_corrected, rtol=1e-6, atol=1e-6)
    np.testing.assert_array_equal(decisions, expected_decisions)


def test_run_rx_pipeline_integrity():
    """
    Verify run_rx_pipeline returns all expected dictionary keys,
    correct output array lengths, and does not mutate input waveform.
    """
    ch_wave = np.array([0.1, 0.5, 0.9, 0.4, -0.2, -0.8, -0.5, 0.0] * 4, dtype=float)
    ch_wave_copy = ch_wave.copy()

    ctle_gain = 1.5
    ctle_alpha = 0.1
    dfe_taps = [0.1, 0.05, 0.0]
    spb = 4
    sampling_phase = 2

    pipeline_res = run_rx_pipeline(
        ch_wave=ch_wave,
        ctle_gain=ctle_gain,
        ctle_alpha=ctle_alpha,
        dfe_taps=dfe_taps,
        spb=spb,
        sampling_phase=sampling_phase,
    )

    # Check required dictionary keys
    expected_keys = {
        "ch_wave",
        "ctle_wave",
        "dfe_input_samples",
        "dfe_corrected_samples",
        "dfe_decisions",
    }
    assert expected_keys.issubset(pipeline_res.keys())

    # Check input wave not modified
    np.testing.assert_array_equal(ch_wave, ch_wave_copy)

    # Check lengths
    num_symbols = len(ch_wave) // spb  # 32 // 4 = 8
    assert len(pipeline_res["ch_wave"]) == 32
    assert len(pipeline_res["ctle_wave"]) == 32
    assert len(pipeline_res["dfe_input_samples"]) == num_symbols
    assert len(pipeline_res["dfe_corrected_samples"]) == num_symbols
    assert len(pipeline_res["dfe_decisions"]) == num_symbols


def test_rx_eq_identity_and_edge_cases():
    """
    Verify CTLE gain <= 0 identity, DFE val == 0 decision = +1.0, and pipeline object identity.
    """
    ch_wave = np.array([0.0, 0.0, 0.0, 0.0], dtype=float)
    res_zero = run_rx_pipeline(ch_wave, ctle_gain=0.0, ctle_alpha=0.08, dfe_taps=[0.0], spb=1, sampling_phase=0)

    assert res_zero["ch_wave"] is ch_wave
    assert res_zero["ctle_wave"] is ch_wave

    # Verify DFE decision when val == 0 is +1.0
    _, _, decisions = apply_dfe(np.array([0.0]), taps=[0.0], spb=1, sampling_phase=0)
    assert decisions[0] == 1.0

