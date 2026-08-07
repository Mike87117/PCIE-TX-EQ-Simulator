"""
Eye Metrics Baseline Tests for PCIE-TX-EQ-Simulator.

Directly tests pcie_eq.metrics core functions:
- calculate_nrz_eye_metrics()
- calculate_dfe_eye_metrics()
- calc_pam4_eye_openings_at_phase()
- estimate_pam4_common_t_center_phase()
- calculate_pam4_eye_metrics()
- calculate_eye_metrics()

Also includes adapter integration verification for PCIeTxEqSimulator.
"""

import pytest
import numpy as np
from main import PCIeTxEqSimulator, SPB
from pcie_eq.metrics import (
    calc_pam4_eye_openings_at_phase,
    estimate_pam4_common_t_center_phase,
    calculate_pam4_eye_metrics,
    calculate_dfe_eye_metrics,
    calculate_nrz_eye_metrics,
    calculate_eye_metrics,
)


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
    Directly verify calculate_nrz_eye_metrics and calculate_eye_metrics for valid ideal square waveform.
    """
    symbols = np.tile([1.0, -1.0], 50)
    wave = np.repeat(symbols, SPB)

    metrics = calculate_nrz_eye_metrics(wave, eye_ui=2, spb=SPB, sampling_phase=16)

    assert metrics["eye_max"] == 1.0
    assert metrics["eye_min"] == -1.0
    assert metrics["center_spread"] == 2.0
    assert metrics["eye_height"] == 2.0
    assert metrics["margin_5pct"] == 1.0
    assert metrics["error_count"] == 0

    # Also verify calculate_eye_metrics dispatcher
    dispatch_metrics = calculate_eye_metrics(
        wave, is_dfe=False, reference_symbols=symbols, spb=SPB, sampling_phase=16
    )
    assert dispatch_metrics == metrics


def test_nrz_eye_metrics_insufficient_traces_fallback():
    """
    Directly verify calculate_nrz_eye_metrics returns all zeros when waveform is too short.
    """
    short_wave = np.repeat([1.0, -1.0], 5)  # 10 * SPB = 320 samples < 20 * SPB
    metrics = calculate_nrz_eye_metrics(short_wave, eye_ui=2, spb=SPB, sampling_phase=16)

    expected_fallback = {
        "eye_height": 0.0,
        "margin_5pct": 0.0,
        "error_count": 0,
        "eye_max": 0.0,
        "eye_min": 0.0,
        "center_spread": 0.0,
    }
    assert metrics == expected_fallback


def test_nrz_eye_metrics_single_rail_zero_height():
    """
    Directly verify calculate_nrz_eye_metrics returns eye_height=0 when waveform lacks lower or upper samples.
    """
    symbols = np.ones(100)
    wave = np.repeat(symbols, SPB)

    metrics = calculate_nrz_eye_metrics(wave, eye_ui=2, spb=SPB, sampling_phase=16)

    assert metrics["eye_height"] == 0.0
    assert metrics["margin_5pct"] == 0.0


def test_dfe_eye_metrics_normal():
    """
    Directly verify calculate_dfe_eye_metrics with signed margin, 5th percentile, and error count.
    """
    symbols = np.tile([1.0, -1.0], 50)  # 100 symbols
    samples = symbols * 0.8
    decisions = symbols.copy()

    metrics = calculate_dfe_eye_metrics(samples, decisions, symbols, warmup_symbols=20)

    # Symbols after 20-symbol warmup: 80 symbols of signed margin 0.8
    assert metrics["margin_5pct"] == pytest.approx(0.8)
    assert metrics["eye_height"] == pytest.approx(1.6)
    assert metrics["error_count"] == 0
    assert metrics["eye_max"] == pytest.approx(0.8)
    assert metrics["eye_min"] == pytest.approx(-0.8)
    assert metrics["center_spread"] == pytest.approx(1.6)

    # Also verify calculate_eye_metrics dispatcher with DFE mode
    rx_results = {"dfe_corrected_samples": samples, "dfe_decisions": decisions}
    dispatch_metrics = calculate_eye_metrics(
        wave=np.array([]), rx_results=rx_results, is_dfe=True, reference_symbols=symbols
    )
    assert dispatch_metrics == metrics


def test_dfe_eye_metrics_warmup_masking():
    """
    Directly verify first 20 symbols are excluded by calculate_dfe_eye_metrics warmup period.
    """
    symbols = np.tile([1.0, -1.0], 50)  # 100 symbols
    samples = symbols * 0.8
    decisions = symbols.copy()

    # Error at index 5 (inside 20-symbol warmup)
    decisions[5] = -decisions[5]
    # Error at index 25 (after warmup)
    decisions[25] = -decisions[25]

    metrics = calculate_dfe_eye_metrics(samples, decisions, symbols, warmup_symbols=20)

    # Index 5 error is ignored due to warmup, index 25 error is counted
    assert metrics["error_count"] == 1


def test_dfe_eye_metrics_short_data_fallback():
    """
    Directly verify calculate_dfe_eye_metrics returns zero fallback when dataset has <= 20 symbols.
    """
    symbols = np.tile([1.0, -1.0], 8)  # 16 symbols <= 20
    samples = symbols * 0.8
    decisions = symbols.copy()

    metrics = calculate_dfe_eye_metrics(samples, decisions, symbols, warmup_symbols=20)

    expected_fallback = {
        "eye_height": 0.0,
        "margin_5pct": 0.0,
        "error_count": 0,
        "eye_max": 0.0,
        "eye_min": 0.0,
        "center_spread": 0.0,
    }
    assert metrics == expected_fallback


def test_pam4_eye_openings_at_phase_normal():
    """
    Directly verify calc_pam4_eye_openings_at_phase calculates valid openings and percentiles for PAM4.
    """
    pam4_levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])
    symbols = np.tile(pam4_levels, 25)
    wave = np.repeat(symbols, SPB)

    res = calc_pam4_eye_openings_at_phase(wave, symbols, phase=0, spb=SPB)

    assert res["valid"] is True
    assert res["sample_count"] >= 20
    assert res["lower_eye"] == pytest.approx(2.0 / 3.0, abs=1e-3)
    assert res["middle_eye"] == pytest.approx(2.0 / 3.0, abs=1e-3)
    assert res["upper_eye"] == pytest.approx(2.0 / 3.0, abs=1e-3)
    assert res["minimum_eye"] == pytest.approx(2.0 / 3.0, abs=1e-3)
    assert res["center_spread"] == pytest.approx(2.0, abs=1e-3)


def test_pam4_eye_openings_at_phase_invalid_cases():
    """
    Directly verify calc_pam4_eye_openings_at_phase returns invalid on short wave or missing PAM4 bands.
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
    res_short = calc_pam4_eye_openings_at_phase(
        np.ones(100), pam4_symbols=np.array([-1.0, 1.0] * 5), phase=0, spb=SPB
    )
    assert res_short == invalid_template

    # Case 2: Missing PAM4 bands (only 2 levels present instead of 4)
    symbols_2level = np.tile([-1.0, 1.0], 50)
    wave_2level = np.repeat(symbols_2level, SPB)
    res_missing_bands = calc_pam4_eye_openings_at_phase(
        wave_2level, pam4_symbols=symbols_2level, phase=0, spb=SPB
    )
    assert res_missing_bands == invalid_template


def test_pam4_t_center_phase_selection_and_tie_break():
    """
    Directly verify estimate_pam4_common_t_center_phase selects best phase and respects tie-breaking to SPB // 2.
    """
    pam4_levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])
    symbols = np.tile(pam4_levels, 25)
    wave = np.repeat(symbols, SPB)

    best_phase, best_openings = estimate_pam4_common_t_center_phase(
        wave, symbols, old_phase=SPB // 2, spb=SPB
    )
    assert best_phase == SPB // 2
    assert best_openings["valid"] is True


def test_pam4_t_center_hysteresis():
    """
    Directly verify phase update hysteresis in estimate_pam4_common_t_center_phase.
    """
    pam4_levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])
    symbols = np.tile(pam4_levels, 25)
    wave = np.repeat(symbols, SPB)

    # Set old_phase to 10
    best_phase, _ = estimate_pam4_common_t_center_phase(
        wave, symbols, old_phase=10, spb=SPB
    )
    assert best_phase == 10


def test_update_pam4_eye_metrics_invalid_fallback():
    """
    Directly verify calculate_pam4_eye_metrics sets all metrics to 0.0 on invalid waveform.
    """
    best_phase, best_score, metrics = calculate_pam4_eye_metrics(
        np.array([]), pam4_symbols=np.array([]), old_phase=16, spb=SPB
    )

    expected_zero = {
        "upper_eye": 0.0,
        "middle_eye": 0.0,
        "lower_eye": 0.0,
        "minimum_eye": 0.0,
        "center_spread": 0.0,
    }
    assert metrics == expected_zero
    assert best_score == 0.0
    assert best_phase == 16


def test_pam4_t_center_distinct_phase_scores():
    """
    Directly verify estimate_pam4_common_t_center_phase selects phase with distinctly highest minimum_eye.
    """
    pam4_levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])
    symbols = np.tile(pam4_levels, 25)
    wave = np.zeros(len(symbols) * SPB, dtype=float)

    for i in range(len(symbols)):
        start = i * SPB
        end = (i + 1) * SPB
        scales = np.where(np.arange(SPB) == 8, 1.0, 0.5)
        wave[start:end] = symbols[i] * scales

    openings_8 = calc_pam4_eye_openings_at_phase(wave, symbols, phase=8, spb=SPB)
    openings_16 = calc_pam4_eye_openings_at_phase(wave, symbols, phase=16, spb=SPB)
    assert openings_8["minimum_eye"] == pytest.approx(2.0 / 3.0, abs=1e-3)
    assert openings_16["minimum_eye"] == pytest.approx(1.0 / 3.0, abs=1e-3)

    best_phase, best_openings = estimate_pam4_common_t_center_phase(
        wave, symbols, old_phase=16, spb=SPB
    )
    assert best_phase == 8
    assert best_openings["minimum_eye"] == pytest.approx(2.0 / 3.0, abs=1e-3)


def test_pam4_t_center_hysteresis_update_beyond_margin():
    """
    Directly verify estimate_pam4_common_t_center_phase updates phase when score exceeds old score by > 0.002.
    """
    pam4_levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])
    symbols = np.tile(pam4_levels, 25)

    # Waveform 1: Candidate score exceeds old score by 0.0006 <= 0.002
    wave1 = np.zeros(len(symbols) * SPB, dtype=float)
    for i in range(len(symbols)):
        start = i * SPB
        end = (i + 1) * SPB
        scales = np.where(np.arange(SPB) == 8, 1.001, np.where(np.arange(SPB) == 16, 1.0, 0.5))
        wave1[start:end] = symbols[i] * scales

    score1_old = calc_pam4_eye_openings_at_phase(wave1, symbols, phase=16, spb=SPB)["minimum_eye"]
    score1_best = calc_pam4_eye_openings_at_phase(wave1, symbols, phase=8, spb=SPB)["minimum_eye"]
    assert (score1_best - score1_old) <= 0.002
    best_phase1, _ = estimate_pam4_common_t_center_phase(wave1, symbols, old_phase=16, spb=SPB)
    assert best_phase1 == 16  # Hysteresis keeps old phase 16

    # Waveform 2: Candidate score exceeds old score by 0.0066 > 0.002
    wave2 = np.zeros(len(symbols) * SPB, dtype=float)
    for i in range(len(symbols)):
        start = i * SPB
        end = (i + 1) * SPB
        scales = np.where(np.arange(SPB) == 8, 1.010, np.where(np.arange(SPB) == 16, 1.0, 0.5))
        wave2[start:end] = symbols[i] * scales

    score2_old = calc_pam4_eye_openings_at_phase(wave2, symbols, phase=16, spb=SPB)["minimum_eye"]
    score2_best = calc_pam4_eye_openings_at_phase(wave2, symbols, phase=8, spb=SPB)["minimum_eye"]
    assert (score2_best - score2_old) > 0.002
    best_phase2, _ = estimate_pam4_common_t_center_phase(wave2, symbols, old_phase=16, spb=SPB)
    assert best_phase2 == 8  # Hysteresis updates to new phase 8


def test_main_adapter_integration():
    """
    Verify PCIeTxEqSimulator adapter methods in main.py correctly forward to core functions and update self state.
    """
    symbols = np.tile([1.0, -1.0], 50)
    wave = np.repeat(symbols, SPB)

    harness = DummyMetricsHarness(symbols=symbols, rx_view_mode="Waveform")
    harness.update_eye_metrics(wave)

    assert "eye_height" in harness.eye_metrics
    assert harness.eye_metrics["eye_height"] == 2.0

    pam4_levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])
    pam4_syms = np.tile(pam4_levels, 25)
    pam4_wave = np.repeat(pam4_syms, SPB)

    pam4_harness = DummyMetricsHarness(pam4_symbols=pam4_syms, pam4_t_center_phase=16)
    pam4_harness.update_pam4_eye_metrics(pam4_wave)

    assert pam4_harness.pam4_t_center_phase == 16
    assert "minimum_eye" in pam4_harness.pam4_eye_metrics
    assert pam4_harness.pam4_eye_metrics["minimum_eye"] == pytest.approx(2.0 / 3.0, abs=1e-3)
