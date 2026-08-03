"""
Eye Metrics Baseline Tests for PCIE-TX-EQ-Simulator.

Locks in existing pre-refactor behavior of:
- update_eye_metrics() (NRZ line eye metrics & DFE symbol-rate metrics)
- calc_pam4_eye_openings_at_phase()
- estimate_pam4_common_t_center_phase()
- update_pam4_eye_metrics()
"""

import pytest
import numpy as np
from main import PCIeTxEqSimulator, SPB, MAX_EYE_TRACES


class DummyMetricsHarness:
    """
    Lightweight test harness binding PCIeTxEqSimulator metrics methods
    without initializing PyQt5 QApplication or creating GUI windows.
    """
    def __init__(
        self,
        symbols=None,
        pam4_symbols=None,
        rx_view_mode="Waveform",
        pam4_t_center_phase=SPB // 2,
    ):
        self.symbols = symbols if symbols is not None else np.array([])
        self.pam4_symbols = pam4_symbols if pam4_symbols is not None else np.array([])
        self.rx_view_mode = rx_view_mode
        self.pam4_t_center_phase = pam4_t_center_phase
        self.pam4_t_center_score = 0.0
        self.eye_metrics = {}
        self.pam4_eye_metrics = {}

    calc_pam4_eye_openings_at_phase = PCIeTxEqSimulator.calc_pam4_eye_openings_at_phase
    estimate_pam4_common_t_center_phase = PCIeTxEqSimulator.estimate_pam4_common_t_center_phase
    update_pam4_eye_metrics = PCIeTxEqSimulator.update_pam4_eye_metrics
    update_eye_metrics = PCIeTxEqSimulator.update_eye_metrics


def test_nrz_eye_metrics_normal():
    """
    Verify NRZ line eye metrics calculation for a valid ideal square waveform.
    """
    symbols = np.tile([1.0, -1.0], 50)
    # Generate waveform repeating each symbol SPB times
    wave = np.repeat(symbols, SPB)

    harness = DummyMetricsHarness(symbols=symbols, rx_view_mode="Waveform")
    harness.update_eye_metrics(wave)

    metrics = harness.eye_metrics
    assert metrics["eye_max"] == 1.0
    assert metrics["eye_min"] == -1.0
    assert metrics["center_spread"] == 2.0
    assert metrics["eye_height"] == 2.0
    assert metrics["margin_5pct"] == 1.0
    assert metrics["error_count"] == 0


def test_nrz_eye_metrics_insufficient_traces_fallback():
    """
    Verify NRZ eye metrics returns all zeros when waveform is too short for 20 SPB traces.
    """
    short_wave = np.repeat([1.0, -1.0], 5)  # 10 * SPB = 320 samples < 20 * SPB
    harness = DummyMetricsHarness(symbols=np.array([1.0, -1.0] * 5), rx_view_mode="Waveform")
    harness.update_eye_metrics(short_wave)

    expected_fallback = {
        "eye_height": 0.0,
        "margin_5pct": 0.0,
        "error_count": 0,
        "eye_max": 0.0,
        "eye_min": 0.0,
        "center_spread": 0.0,
    }
    assert harness.eye_metrics == expected_fallback


def test_nrz_eye_metrics_single_rail_zero_height():
    """
    Verify NRZ eye metrics returns eye_height=0 when waveform lacks lower or upper samples.
    """
    symbols = np.ones(100)
    wave = np.repeat(symbols, SPB)  # All positive samples

    harness = DummyMetricsHarness(symbols=symbols, rx_view_mode="Waveform")
    harness.update_eye_metrics(wave)

    assert harness.eye_metrics["eye_height"] == 0.0
    assert harness.eye_metrics["margin_5pct"] == 0.0


def test_dfe_eye_metrics_normal():
    """
    Verify DFE symbol-rate metrics calculation with signed margin, 5th percentile, and error count.
    """
    symbols = np.tile([1.0, -1.0], 50)  # 100 symbols
    # Samples with amplitude 0.8
    samples = symbols * 0.8
    decisions = symbols.copy()

    rx_results = {
        "dfe_corrected_samples": samples,
        "dfe_decisions": decisions,
    }

    harness = DummyMetricsHarness(symbols=symbols, rx_view_mode="DFE Sample Margin")
    harness.update_eye_metrics(wave=np.array([]), rx_results=rx_results)

    metrics = harness.eye_metrics
    # Symbols after 20-symbol warmup: 80 symbols of signed margin 0.8
    assert metrics["margin_5pct"] == pytest.approx(0.8)
    assert metrics["eye_height"] == pytest.approx(1.6)
    assert metrics["error_count"] == 0
    assert metrics["eye_max"] == pytest.approx(0.8)
    assert metrics["eye_min"] == pytest.approx(-0.8)
    assert metrics["center_spread"] == pytest.approx(1.6)


def test_dfe_eye_metrics_warmup_masking():
    """
    Verify first 20 symbols are excluded by DFE warmup period.
    """
    symbols = np.tile([1.0, -1.0], 50)  # 100 symbols
    samples = symbols * 0.8
    decisions = symbols.copy()

    # Error at index 5 (inside 20-symbol warmup)
    decisions[5] = -decisions[5]
    # Error at index 25 (after warmup)
    decisions[25] = -decisions[25]

    rx_results = {
        "dfe_corrected_samples": samples,
        "dfe_decisions": decisions,
    }

    harness = DummyMetricsHarness(symbols=symbols, rx_view_mode="DFE Sample Margin")
    harness.update_eye_metrics(wave=np.array([]), rx_results=rx_results)

    # Index 5 error is ignored due to warmup, index 25 error is counted
    assert harness.eye_metrics["error_count"] == 1


def test_dfe_eye_metrics_short_data_fallback():
    """
    Verify DFE metrics returns zero fallback when dataset has <= 20 symbols.
    """
    symbols = np.tile([1.0, -1.0], 8)  # 16 symbols <= 20
    samples = symbols * 0.8
    decisions = symbols.copy()

    rx_results = {
        "dfe_corrected_samples": samples,
        "dfe_decisions": decisions,
    }

    harness = DummyMetricsHarness(symbols=symbols, rx_view_mode="DFE Sample Margin")
    harness.update_eye_metrics(wave=np.array([]), rx_results=rx_results)

    expected_fallback = {
        "eye_height": 0.0,
        "margin_5pct": 0.0,
        "error_count": 0,
        "eye_max": 0.0,
        "eye_min": 0.0,
        "center_spread": 0.0,
    }
    assert harness.eye_metrics == expected_fallback


def test_pam4_eye_openings_at_phase_normal():
    """
    Verify calc_pam4_eye_openings_at_phase calculates valid openings and percentiles for PAM4 signals.
    """
    # 100 symbols with repeating PAM4 levels [-1.0, -1/3, 1/3, 1.0]
    pam4_levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])
    symbols = np.tile(pam4_levels, 25)
    wave = np.repeat(symbols, SPB)

    harness = DummyMetricsHarness(pam4_symbols=symbols)
    res = harness.calc_pam4_eye_openings_at_phase(wave, phase=0)

    assert res["valid"] is True
    assert res["sample_count"] >= 20
    # For ideal PAM4 step levels:
    # lower_eye = -1/3 - (-1) = 2/3 ≈ 0.6667
    # middle_eye = 1/3 - (-1/3) = 2/3 ≈ 0.6667
    # upper_eye = 1 - 1/3 = 2/3 ≈ 0.6667
    assert res["lower_eye"] == pytest.approx(2.0 / 3.0, abs=1e-3)
    assert res["middle_eye"] == pytest.approx(2.0 / 3.0, abs=1e-3)
    assert res["upper_eye"] == pytest.approx(2.0 / 3.0, abs=1e-3)
    assert res["minimum_eye"] == pytest.approx(2.0 / 3.0, abs=1e-3)
    assert res["center_spread"] == pytest.approx(2.0, abs=1e-3)


def test_pam4_eye_openings_at_phase_invalid_cases():
    """
    Verify invalid returns when waveform is too short or missing PAM4 symbol levels.
    """
    invalid_template = {
        "valid": False,
        "upper_eye": 0.0,
        "middle_eye": 0.0,
        "lower_eye": 0.0,
        "minimum_eye": 0.0,
        "center_spread": 0.0,
        "sample_count": 0,
    }

    # Case 1: Short waveform
    harness = DummyMetricsHarness(pam4_symbols=np.array([-1.0, 1.0] * 5))
    res_short = harness.calc_pam4_eye_openings_at_phase(np.ones(100), phase=0)
    assert res_short == invalid_template

    # Case 2: Missing PAM4 bands (only 2 levels present instead of 4)
    symbols_2level = np.tile([-1.0, 1.0], 50)
    wave_2level = np.repeat(symbols_2level, SPB)
    harness_2level = DummyMetricsHarness(pam4_symbols=symbols_2level)
    res_missing_bands = harness_2level.calc_pam4_eye_openings_at_phase(wave_2level, phase=0)
    assert res_missing_bands == invalid_template


def test_pam4_t_center_phase_selection_and_tie_break():
    """
    Verify estimate_pam4_common_t_center_phase selects best phase and respects tie-breaking towards SPB // 2.
    """
    pam4_levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])
    symbols = np.tile(pam4_levels, 25)
    wave = np.repeat(symbols, SPB)

    harness = DummyMetricsHarness(pam4_symbols=symbols, pam4_t_center_phase=SPB // 2)

    best_phase, best_openings = harness.estimate_pam4_common_t_center_phase(wave)
    # For ideal flat symbol segments, phase SPB//2 (16) is tied with all phases and is closest to center
    assert best_phase == SPB // 2
    assert best_openings["valid"] is True


def test_pam4_t_center_hysteresis():
    """
    Verify phase update hysteresis (phase_update_margin = 0.002).
    """
    pam4_levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])
    symbols = np.tile(pam4_levels, 25)
    wave = np.repeat(symbols, SPB)

    # Set old_phase to 10
    harness = DummyMetricsHarness(pam4_symbols=symbols, pam4_t_center_phase=10)

    # For ideal flat wave, score at phase 10 is equal to candidate best phase score (diff <= 0.002)
    # So hysteresis holds and keeps old_phase (10)
    best_phase, _ = harness.estimate_pam4_common_t_center_phase(wave)
    assert best_phase == 10


def test_update_pam4_eye_metrics_invalid_fallback():
    """
    Verify update_pam4_eye_metrics sets all pam4_eye_metrics to 0.0 on invalid waveform.
    """
    harness = DummyMetricsHarness(pam4_symbols=np.array([]))
    harness.update_pam4_eye_metrics(np.array([]))

    expected_zero = {
        "upper_eye": 0.0,
        "middle_eye": 0.0,
        "lower_eye": 0.0,
        "minimum_eye": 0.0,
        "center_spread": 0.0,
    }
    assert harness.pam4_eye_metrics == expected_zero
    assert harness.pam4_t_center_score == 0.0
