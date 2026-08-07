"""
Module boundary and plotting contract regression tests for pcie_eq.gui package.

Verifies:
1. PCIeTxEqSimulator class is defined in pcie_eq.gui.window module.
2. main.PCIeTxEqSimulator points to the exact same class as pcie_eq.gui.window.PCIeTxEqSimulator.
3. Legacy constant imports (SPB, BIT_COUNT, PAM4_SYMBOL_COUNT) from main.py remain compatible.
4. main.py does not define any large QMainWindow subclass inline (AST check).
5. Plotting contracts: update_waveform Y-range calculation, NaN-separated single curve eye rendering with 20-symbol warmup skip, and DFE sample plot zero line & scatter behavior.
"""

import ast
import sys
import pathlib
import pytest
import numpy as np
from PyQt5.QtWidgets import QApplication

from pcie_eq.gui.window import PCIeTxEqSimulator as CorePCIeTxEqSimulator
from pcie_eq.gui.window import SPB as CoreSPB, BIT_COUNT as CoreBIT_COUNT, PAM4_SYMBOL_COUNT as CorePAM4_SYMBOL_COUNT, PLOT_BITS
import pcie_eq.gui as gui_pkg
import main


@pytest.fixture(scope="module")
def qapp():
    """Reusable QApplication instance fixture for GUI boundary testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_class_definition_location():
    """Verify PCIeTxEqSimulator is defined in pcie_eq.gui.window and re-exported by pcie_eq.gui."""
    assert CorePCIeTxEqSimulator.__module__ == "pcie_eq.gui.window"
    assert gui_pkg.PCIeTxEqSimulator is CorePCIeTxEqSimulator


def test_main_reexport_identity():
    """Verify main.PCIeTxEqSimulator points to pcie_eq.gui.window.PCIeTxEqSimulator."""
    assert main.PCIeTxEqSimulator is CorePCIeTxEqSimulator


def test_legacy_constants_compatibility():
    """Verify legacy constants imported from main.py match core values."""
    assert main.SPB == CoreSPB == 32
    assert main.BIT_COUNT == CoreBIT_COUNT == 512
    assert main.PAM4_SYMBOL_COUNT == CorePAM4_SYMBOL_COUNT == 512


def test_main_py_no_inline_gui_class():
    """AST check verifying main.py contains no ClassDef for QMainWindow or PCIeTxEqSimulator."""
    main_path = pathlib.Path(main.__file__)
    tree = ast.parse(main_path.read_text(encoding="utf-8"))

    class_defs = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    assert "PCIeTxEqSimulator" not in class_defs, "main.py must not contain inline ClassDef for PCIeTxEqSimulator"
    assert len(class_defs) == 0, f"main.py should contain 0 class definitions, found: {class_defs}"


def test_update_waveform_yrange_contract(qapp):
    """Verify update_waveform calculates Y-range considering TX, Channel, and RX waveforms simultaneously."""
    win = CorePCIeTxEqSimulator()
    try:
        wave_len = PLOT_BITS * CoreSPB * 2
        tx_wave = np.ones(wave_len) * 1.5
        ch_wave = np.ones(wave_len) * 1.0
        rx_wave = np.ones(wave_len) * 2.5

        win.update_waveform(tx_wave, ch_wave, rx_wave)
        yrange = win.wave_plot.viewRange()[1]

        # max(1.3, 1.5, 1.0, 2.5) * 1.1 = 2.75 (with pyqtgraph margin)
        assert yrange[1] >= 2.75
        assert yrange[0] <= -2.75
    finally:
        win.close()


def test_update_eye_line_nan_separation_and_warmup(qapp):
    """Verify update_eye_line uses single curve with NaN separation and phase-centered 2-UI warmup alignment."""
    win = CorePCIeTxEqSimulator()
    try:
        wave = np.tile(np.linspace(0.0, 1.0, CoreSPB * 2), 50)
        sampling_phase = CoreSPB // 2
        win.update_eye_line(wave, sampling_phase, max_traces=10)

        x_data, y_data = win.eye_curve.getData()
        assert x_data is not None and len(x_data) > 0
        assert y_data is not None and len(y_data) > 0

        # Verify NaN separation is present in trace data
        assert np.isnan(x_data).sum() > 0
        assert np.isnan(y_data).sum() > 0

        # Verify first trace data starts at phase-centered coordinate
        first_start = 20 * CoreSPB + sampling_phase - CoreSPB
        assert y_data[0] == pytest.approx(wave[first_start])

        # Verify x=1.0 UI corresponds to index CoreSPB and decision sample
        assert x_data[CoreSPB] == pytest.approx(1.0)
        assert y_data[CoreSPB] == pytest.approx(wave[20 * CoreSPB + sampling_phase])
    finally:
        win.close()


def test_update_dfe_sample_plot_zero_line_and_scatter(qapp):
    """Verify update_dfe_sample_plot displays zero line, scatter plot symbols, and skips 20 warmup symbols."""
    win = CorePCIeTxEqSimulator()
    try:
        rx_results = {
            "dfe_corrected_samples": np.linspace(-1.0, 1.0, 100),
            "dfe_decisions": np.ones(100),
        }
        win.update_dfe_sample_plot(rx_results, max_symbols=50)

        assert hasattr(win, "eye_zero_line")
        assert win.eye_zero_line.isVisible()
        assert win.eye_curve.opts["symbol"] == 'o'
        assert win.eye_curve.opts["symbolSize"] == 6

        x_vals, y_vals = win.eye_curve.getData()
        # Verify symbol index starts at 20 (warmup skip)
        assert x_vals[0] == 20
        assert y_vals[0] == pytest.approx(rx_results["dfe_corrected_samples"][20])
    finally:
        win.close()


def test_nrz_controller_no_hidden_sampling_phase_defaults():
    """
    Verify update_eye, update_eye_line, and update_eye_metrics have no default value for sampling_phase.
    """
    import inspect
    from pcie_eq.gui.nrz_controller import NrzControllerMixin

    for method_name in ("update_eye", "update_eye_line", "update_eye_metrics"):
        method = getattr(NrzControllerMixin, method_name)
        sig = inspect.signature(method)
        assert "sampling_phase" in sig.parameters, f"Method '{method_name}' missing parameter 'sampling_phase'"
        param = sig.parameters["sampling_phase"]
        assert param.default is inspect.Parameter.empty, f"Method '{method_name}' parameter 'sampling_phase' must not have default value"
