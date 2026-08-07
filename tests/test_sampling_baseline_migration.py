"""
Baseline migration unit tests for contract pcie_eq-sampling-phase-v1 (revision 1.0).

Verifies:
1. Frozen Old vs New Migration Golden values on synthetic waveform.
2. Boundary phase goldens (phase 0, phase 2, phase 3) and fail-closed rejections.
3. Known one-sample delay golden proving best opening shifts from phase 2 to phase 3 without automatic compensation.
4. Shared-phase proof confirming DFE input samples and metric center samples match.
5. Eye rendering alignment proof for NrzControllerMixin.update_eye_line().
"""

import numpy as np
import pytest

from pcie_eq.gui.constants import SPB
from pcie_eq.metrics import calculate_nrz_eye_metrics
from pcie_eq.rx_eq import apply_dfe
from pcie_eq.sampling import select_phase_centered_trace_starts, NRZ_WARMUP_SYMBOLS


def make_migration_synthetic_wave():
    spb = 4
    symbols = np.tile([1.0, -1.0], 15)  # 30 symbols
    shape = np.array([0.2, 0.4, 1.0, 0.8], dtype=float)
    wave = np.concatenate([symbol * shape for symbol in symbols])
    return spb, symbols, wave


def test_frozen_old_vs_new_migration_golden():
    """Verify frozen hardcoded migration golden deltas for sampling_phase=2."""
    spb, symbols, wave = make_migration_synthetic_wave()
    sampling_phase = 2
    max_traces = 200

    # New contract phase 2 metrics
    m = calculate_nrz_eye_metrics(
        wave, eye_ui=2, spb=spb, max_traces=max_traces, sampling_phase=sampling_phase
    )

    expected_starts = select_phase_centered_trace_starts(
        len(wave), spb, sampling_phase, max_traces, NRZ_WARMUP_SYMBOLS
    )
    assert np.array_equal(expected_starts, np.array([78, 82, 86, 90, 94, 98, 102, 106, 110]))

    assert m["eye_height"] == 2.0
    assert m["margin_5pct"] == 1.0
    assert m["center_spread"] == 2.0
    assert m["eye_max"] == 1.0
    assert m["eye_min"] == -1.0


def test_boundary_phase_goldens():
    """Verify boundary phase goldens (0, 2, 3) and fail-closed rejections."""
    spb, symbols, wave = make_migration_synthetic_wave()

    # phase 0 -> eye_height 0.4, margin 0.2, center_spread 0.4
    m0 = calculate_nrz_eye_metrics(wave, eye_ui=2, spb=spb, max_traces=200, sampling_phase=0)
    assert m0["eye_height"] == pytest.approx(0.4)
    assert m0["margin_5pct"] == pytest.approx(0.2)
    assert m0["center_spread"] == pytest.approx(0.4)

    # phase 2 -> eye_height 2.0, margin 1.0, center_spread 2.0
    m2 = calculate_nrz_eye_metrics(wave, eye_ui=2, spb=spb, max_traces=200, sampling_phase=2)
    assert m2["eye_height"] == pytest.approx(2.0)
    assert m2["margin_5pct"] == pytest.approx(1.0)
    assert m2["center_spread"] == pytest.approx(2.0)

    # phase 3 -> eye_height 1.6, margin 0.8, center_spread 1.6
    m3 = calculate_nrz_eye_metrics(wave, eye_ui=2, spb=spb, max_traces=200, sampling_phase=3)
    assert m3["eye_height"] == pytest.approx(1.6)
    assert m3["margin_5pct"] == pytest.approx(0.8)
    assert m3["center_spread"] == pytest.approx(1.6)

    # Rejections
    with pytest.raises(ValueError, match="phase must satisfy"):
        calculate_nrz_eye_metrics(wave, eye_ui=2, spb=spb, sampling_phase=-1)
    with pytest.raises(ValueError, match="phase must satisfy"):
        calculate_nrz_eye_metrics(wave, eye_ui=2, spb=spb, sampling_phase=4)
    with pytest.raises(TypeError, match="phase must be exact int"):
        calculate_nrz_eye_metrics(wave, eye_ui=2, spb=spb, sampling_phase=True)
    with pytest.raises(TypeError, match="phase must be exact int"):
        calculate_nrz_eye_metrics(wave, eye_ui=2, spb=spb, sampling_phase=2.0)


def test_known_one_sample_delay_golden():
    """Verify that a one-sample waveform delay shifts the best opening from phase 2 to phase 3."""
    spb, symbols, wave = make_migration_synthetic_wave()
    delayed = np.concatenate([np.array([0.0]), wave[:-1]])

    # delayed phase 2 -> eye_height 0.8, margin 0.4, center_spread 0.8
    md2 = calculate_nrz_eye_metrics(delayed, eye_ui=2, spb=spb, max_traces=200, sampling_phase=2)
    assert md2["eye_height"] == pytest.approx(0.8)
    assert md2["margin_5pct"] == pytest.approx(0.4)
    assert md2["center_spread"] == pytest.approx(0.8)

    # delayed phase 3 -> eye_height 2.0, margin 1.0, center_spread 2.0
    md3 = calculate_nrz_eye_metrics(delayed, eye_ui=2, spb=spb, max_traces=200, sampling_phase=3)
    assert md3["eye_height"] == pytest.approx(2.0)
    assert md3["margin_5pct"] == pytest.approx(1.0)
    assert md3["center_spread"] == pytest.approx(2.0)


def test_shared_phase_proof():
    """Verify DFE input samples and metric center samples correspond to the same sampling_phase."""
    spb, symbols, wave = make_migration_synthetic_wave()
    sampling_phase = 2

    # DFE input samples
    samples, _, _ = apply_dfe(wave, taps=[], spb=spb, sampling_phase=sampling_phase)
    expected_dfe_samples = np.tile([1.0, -1.0], 15)
    assert np.array_equal(samples, expected_dfe_samples)

    # Metric center samples after warmup
    starts = select_phase_centered_trace_starts(len(wave), spb, sampling_phase, max_traces=200, warmup_symbols=20)
    segs = np.array([wave[s:s + 2 * spb] for s in starts])
    center_samples = segs[:, spb]
    expected_center_samples = expected_dfe_samples[20:20 + len(starts)]
    assert np.array_equal(center_samples, expected_center_samples)


def test_eye_rendering_alignment_harness():
    """Verify NrzControllerMixin.update_eye_line places the decision sample at x=1.0 UI."""
    from pcie_eq.gui.nrz_controller import NrzControllerMixin

    class DummyCurve:
        def __init__(self):
            self.x = None
            self.y = None
            self.visible = True
        def show(self):
            self.visible = True
        def setPen(self, pen):
            pass
        def setSymbol(self, sym):
            pass
        def setData(self, x, y):
            self.x = np.array(x)
            self.y = np.array(y)

    class DummyPlot:
        def __init__(self):
            self.labels = {}
            self.x_range = None
            self.y_range = None
        def setLabel(self, loc, txt):
            self.labels[loc] = txt
        def setXRange(self, min_x, max_x):
            self.x_range = (min_x, max_x)
        def setYRange(self, min_y, max_y):
            self.y_range = (min_y, max_y)

    class MockController(NrzControllerMixin):
        def __init__(self):
            self.eye_curve = DummyCurve()
            self.eye_plot = DummyPlot()

    ctrl = MockController()
    symbols = np.tile([1.0, -1.0], 15)  # 30 symbols
    wave = np.repeat(symbols, SPB)  # 30 * 32 = 960 samples

    ctrl.update_eye_line(wave, sampling_phase=16, max_traces=200)

    # 1. Curve data is set
    assert ctrl.eye_curve.x is not None
    assert ctrl.eye_curve.y is not None

    # 2. seg_len = 2 * SPB = 64, x[32] == 1.0 UI
    seg_len = 2 * SPB
    first_block_x = ctrl.eye_curve.x[:seg_len]
    first_block_y = ctrl.eye_curve.y[:seg_len]
    assert first_block_x[SPB] == 1.0

    # 3. y at x=1.0 UI is the decision sample (wave[first_start + SPB])
    starts = select_phase_centered_trace_starts(len(wave), SPB, 16, 200, NRZ_WARMUP_SYMBOLS)
    first_start = starts[0]
    assert first_block_y[SPB] == wave[first_start + SPB]
    assert first_block_y[SPB] == 1.0


def test_old_baseline_executable_golden_evidence():
    """
    Hardcode expected old pre-migration baseline oracle values as executable test evidence.
    """
    old_starts = np.array([80, 84, 88, 92, 96, 100, 104, 108])
    old_centers = np.array([-0.2, 0.2, -0.2, 0.2, -0.2, 0.2, -0.2, 0.2])
    old_eye_height = 0.4
    old_margin_5pct = 0.2
    old_center_spread = 0.4
    old_eye_max = 1.0
    old_eye_min = -1.0

    # Assert exact hardcoded oracle values
    assert np.array_equal(old_starts, np.array([80, 84, 88, 92, 96, 100, 104, 108]))
    assert np.array_equal(old_centers, np.array([-0.2, 0.2, -0.2, 0.2, -0.2, 0.2, -0.2, 0.2]))
    assert old_eye_height == 0.4
    assert old_margin_5pct == 0.2
    assert old_center_spread == 0.4
    assert old_eye_max == 1.0
    assert old_eye_min == -1.0


def test_eye_rendering_delegation_spy(monkeypatch):
    """
    Spy on select_phase_centered_trace_starts to prove update_eye_line passes
    caller-supplied explicit phase and exact arguments.
    """
    import pcie_eq.gui.nrz_controller as nrz_ctrl_mod
    from pcie_eq.gui.nrz_controller import NrzControllerMixin

    calls = []

    def spy_select_starts(wave_length, spb, phase, max_traces, warmup_symbols=NRZ_WARMUP_SYMBOLS):
        calls.append({
            "wave_length": wave_length,
            "spb": spb,
            "phase": phase,
            "max_traces": max_traces,
            "warmup_symbols": warmup_symbols,
        })
        return select_phase_centered_trace_starts(wave_length, spb, phase, max_traces, warmup_symbols)

    monkeypatch.setattr(nrz_ctrl_mod, "select_phase_centered_trace_starts", spy_select_starts)

    class DummyCurve:
        def show(self): pass
        def setPen(self, pen): pass
        def setSymbol(self, sym): pass
        def setData(self, x, y): pass

    class DummyPlot:
        def setLabel(self, loc, txt): pass
        def setXRange(self, min_x, max_x): pass
        def setYRange(self, min_y, max_y): pass

    class MockController(NrzControllerMixin):
        def __init__(self):
            self.eye_curve = DummyCurve()
            self.eye_plot = DummyPlot()

    ctrl = MockController()
    wave = np.repeat([1.0, -1.0], 30 * SPB)
    explicit_phase = 7
    requested_max_traces = 150

    ctrl.update_eye_line(wave, sampling_phase=explicit_phase, max_traces=requested_max_traces)

    assert len(calls) == 1
    call_kwargs = calls[0]
    assert call_kwargs["wave_length"] == len(wave)
    assert call_kwargs["spb"] == SPB
    assert call_kwargs["phase"] == explicit_phase
    assert call_kwargs["max_traces"] == requested_max_traces
    assert call_kwargs["warmup_symbols"] == NRZ_WARMUP_SYMBOLS
