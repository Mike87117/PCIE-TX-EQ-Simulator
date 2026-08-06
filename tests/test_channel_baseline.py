"""
Channel Baseline Tests for PCIE-TX-EQ-Simulator.

Locks in existing pre-refactor behavior of:
- simple_channel(wave, alpha=0.08)
"""

import numpy as np
from pcie_eq.channel import simple_channel


def test_channel_alpha_1_identity():
    """
    Verify simple_channel with alpha=1 returns identical wave.
    Also verify output length and that input array is unmodified.
    """
    wave = np.array([0.0, 1.0, 0.5, -0.5, -1.0, 0.0], dtype=float)
    wave_copy = wave.copy()

    out = simple_channel(wave, alpha=1.0)

    assert len(out) == len(wave)
    np.testing.assert_array_equal(wave, wave_copy)
    np.testing.assert_allclose(out, wave, rtol=1e-7, atol=1e-7)


def test_channel_step_response_golden():
    """
    Verify step response for a step input [0, 0, 0, 1, 1, 1, 1, 1] with alpha=0.5.

    Formula: out[0] = wave[0]
             out[i] = out[i-1] + alpha * (wave[i] - out[i-1])

    i=0: out[0] = 0.0
    i=1: out[1] = 0.0
    i=2: out[2] = 0.0
    i=3: out[3] = 0 + 0.5 * (1 - 0) = 0.5
    i=4: out[4] = 0.5 + 0.5 * (1 - 0.5) = 0.75
    i=5: out[5] = 0.75 + 0.5 * (1 - 0.75) = 0.875
    i=6: out[6] = 0.875 + 0.5 * (1 - 0.875) = 0.9375
    i=7: out[7] = 0.9375 + 0.5 * (1 - 0.9375) = 0.96875
    """
    wave = np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=float)
    wave_copy = wave.copy()

    out = simple_channel(wave, alpha=0.5)

    assert len(out) == len(wave)
    np.testing.assert_array_equal(wave, wave_copy)

    expected = np.array([0.0, 0.0, 0.0, 0.5, 0.75, 0.875, 0.9375, 0.96875], dtype=float)
    np.testing.assert_allclose(out, expected, rtol=1e-6, atol=1e-6)


def test_channel_impulse_response_golden():
    """
    Verify impulse response for impulse input [1.0, 0.0, 0.0, 0.0, 0.0] with alpha=0.2.

    i=0: out[0] = 1.0
    i=1: out[1] = 1.0 + 0.2 * (0 - 1.0) = 0.8
    i=2: out[2] = 0.8 + 0.2 * (0 - 0.8) = 0.64
    i=3: out[3] = 0.64 + 0.2 * (0 - 0.64) = 0.512
    i=4: out[4] = 0.512 + 0.2 * (0 - 0.512) = 0.4096
    """
    wave = np.array([1.0, 0.0, 0.0, 0.0, 0.0], dtype=float)
    out = simple_channel(wave, alpha=0.2)

    expected = np.array([1.0, 0.8, 0.64, 0.512, 0.4096], dtype=float)
    np.testing.assert_allclose(out, expected, rtol=1e-6, atol=1e-6)


def test_channel_negative_alpha_golden():
    """
    Explicitly test simple_channel with negative alpha (e.g. alpha = -0.5).

    Formula: out[0] = wave[0]
             out[i] = out[i-1] + alpha * (wave[i] - out[i-1])

    With wave = [1.0, 2.0, 3.0] and alpha = -0.5:
    i=0: out[0] = 1.0
    i=1: out[1] = 1.0 + (-0.5) * (2.0 - 1.0) = 0.5
    i=2: out[2] = 0.5 + (-0.5) * (3.0 - 0.5) = -0.75
    """
    wave = np.array([1.0, 2.0, 3.0], dtype=float)
    wave_copy = wave.copy()

    out = simple_channel(wave, alpha=-0.5)

    assert len(out) == len(wave)
    np.testing.assert_array_equal(wave, wave_copy)

    expected = np.array([1.0, 0.5, -0.75], dtype=float)
    np.testing.assert_allclose(out, expected, rtol=1e-7, atol=1e-7)


def test_channel_empty_array_behavior():
    """
    Verify empty input returns an empty float array instead of raising.

    Baseline change: this previously raised IndexError from out[0] = wave[0].
    The pipeline dataclasses default to empty symbol arrays, so the crash was
    reachable from run_simulation(NrzSimulationConfig()).
    """
    empty_wave = np.array([], dtype=float)
    out = simple_channel(empty_wave, alpha=0.08)

    assert isinstance(out, np.ndarray)
    assert out.shape == (0,)
    assert out.dtype == np.float64


def test_channel_integer_input_is_not_truncated():
    """
    Verify integer input is evaluated in floating point.

    Previously out = np.zeros_like(wave) inherited the integer dtype, so
    alpha * (wave[i] - out[i-1]) was truncated toward zero on every sample and
    a 0/1 bit stream collapsed to all zeros.

    wave = [0, 1, 1, 0], alpha = 0.5:
    i=0: out[0] = 0.0
    i=1: out[1] = 0.0 + 0.5 * (1 - 0.0)  = 0.5
    i=2: out[2] = 0.5 + 0.5 * (1 - 0.5)  = 0.75
    i=3: out[3] = 0.75 + 0.5 * (0 - 0.75) = 0.375
    """
    wave = np.array([0, 1, 1, 0], dtype=int)
    wave_copy = wave.copy()

    out = simple_channel(wave, alpha=0.5)

    np.testing.assert_array_equal(wave, wave_copy)
    assert np.issubdtype(out.dtype, np.floating)

    expected = np.array([0.0, 0.5, 0.75, 0.375], dtype=float)
    np.testing.assert_allclose(out, expected, rtol=1e-7, atol=1e-7)
    assert not np.all(out == 0), "integer input must not collapse to all zeros"


def test_channel_float_dtype_is_preserved():
    """
    Verify existing floating input keeps its own dtype.

    Only non-floating input is promoted, so float64 pipeline waveforms are
    bit-exact against the previous implementation.
    """
    wave64 = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    assert simple_channel(wave64, alpha=0.5).dtype == np.float64

    wave32 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert simple_channel(wave32, alpha=0.5).dtype == np.float32


def test_channel_accepts_sequence_input():
    """
    Verify a plain Python sequence is accepted and evaluated in floating point.
    """
    out = simple_channel([0, 1, 1, 0], alpha=0.5)

    assert isinstance(out, np.ndarray)
    np.testing.assert_allclose(
        out, np.array([0.0, 0.5, 0.75, 0.375]), rtol=1e-7, atol=1e-7
    )


def test_channel_edge_case_alphas():
    """
    Document current behavior for edge case / illegal alpha values.

    - alpha = 0.0: out[i] remains constant out[0] = wave[0] for all i.
    - alpha > 1.0 (e.g. 2.0): out[i] overshoots/oscillates.
    """
    wave = np.array([1.0, 2.0, 3.0, 4.0], dtype=float)

    # alpha = 0.0: output freezes at initial element
    out_zero = simple_channel(wave, alpha=0.0)
    np.testing.assert_allclose(out_zero, np.array([1.0, 1.0, 1.0, 1.0]), rtol=1e-7, atol=1e-7)

    # alpha = 2.0: overshoots
    # i=0: 1.0
    # i=1: 1.0 + 2.0*(2.0 - 1.0) = 3.0
    # i=2: 3.0 + 2.0*(3.0 - 3.0) = 3.0
    # i=3: 3.0 + 2.0*(4.0 - 3.0) = 5.0
    out_two = simple_channel(wave, alpha=2.0)
    np.testing.assert_allclose(out_two, np.array([1.0, 3.0, 3.0, 5.0]), rtol=1e-7, atol=1e-7)
