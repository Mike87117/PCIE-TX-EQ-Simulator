"""
Module boundary tests for pcie_eq.gui.nrz_tab module.

Verifies:
1. build_nrz_tab function is defined in pcie_eq.gui.nrz_tab.
2. pcie_eq.gui.nrz_tab does not import main.py or pcie_eq.gui.window (AST check).
3. build_nrz_tab correctly attaches all NRZ plots, curves, panels, controls, and sliders to owner instance.
"""

import ast
import sys
import pathlib
import pytest
from PyQt5.QtWidgets import QApplication, QWidget

from pcie_eq.gui.nrz_tab import build_nrz_tab
from pcie_eq.gui.window import PCIeTxEqSimulator


@pytest.fixture(scope="module")
def qapp():
    """Reusable QApplication instance fixture for NRZ tab boundary testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_build_nrz_tab_function_location():
    """Verify build_nrz_tab is defined in pcie_eq.gui.nrz_tab."""
    assert build_nrz_tab.__module__ == "pcie_eq.gui.nrz_tab"


def test_nrz_tab_ast_no_forbidden_imports():
    """AST check verifying pcie_eq/gui/nrz_tab.py contains no imports of main.py or pcie_eq.gui.window."""
    tab_path = pathlib.Path("pcie_eq/gui/nrz_tab.py")
    tree = ast.parse(tab_path.read_text(encoding="utf-8"))

    forbidden_modules = {"main", "pcie_eq.gui.window", "window"}
    found_forbidden = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_modules:
                    found_forbidden.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module in forbidden_modules:
                found_forbidden.add(node.module)

    assert not found_forbidden, f"pcie_eq/gui/nrz_tab.py contains forbidden imports: {found_forbidden}"


def test_build_nrz_tab_attachment(qapp):
    """Verify build_nrz_tab attaches all expected attributes, plots, curves, and controls to PCIeTxEqSimulator."""
    win = PCIeTxEqSimulator()
    try:
        expected_attrs = [
            "wave_plot",
            "eye_plot",
            "tx_curve",
            "ch_curve",
            "rx_curve",
            "eye_curve",
            "status_panel",
            "status_layout",
            "status_items",
            "preset_combo",
            "btn_new_wave",
            "btn_reset_no_eq",
            "btn_reset_channel",
            "btn_reset_all",
            "btn_nrz_detail",
            "slider_cm1",
            "slider_cp1",
            "slider_alpha",
            "rx_view_combo",
            "btn_reset_rx",
            "slider_ctle",
            "slider_dfe1",
            "slider_dfe2",
            "slider_dfe3",
        ]
        for attr in expected_attrs:
            assert hasattr(win, attr), f"PCIeTxEqSimulator missing expected attribute after build_nrz_tab: {attr}"

        assert len(win.status_items) == 8
        assert win.preset_combo.count() == 12  # Custom + 11 presets
        assert win.rx_view_combo.count() == 3
    finally:
        win.close()
