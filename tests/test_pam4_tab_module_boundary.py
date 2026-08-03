"""
Module boundary tests for pcie_eq.gui.pam4_tab module.

Verifies:
1. build_pam4_tab function is defined in pcie_eq.gui.pam4_tab.
2. pcie_eq.gui.pam4_tab does not import main.py or pcie_eq.gui.window (AST check).
3. build_pam4_tab correctly attaches all PAM4 plots, curves, panels, controls, and sliders to owner instance.
"""

import ast
import sys
import pathlib
import pytest
from PyQt5.QtWidgets import QApplication

from pcie_eq.gui.pam4_tab import build_pam4_tab
from pcie_eq.gui.window import PCIeTxEqSimulator


@pytest.fixture(scope="module")
def qapp():
    """Reusable QApplication instance fixture for PAM4 tab boundary testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_build_pam4_tab_function_location():
    """Verify build_pam4_tab is defined in pcie_eq.gui.pam4_tab."""
    assert build_pam4_tab.__module__ == "pcie_eq.gui.pam4_tab"


def test_pam4_tab_ast_no_forbidden_imports():
    """AST check verifying pcie_eq/gui/pam4_tab.py contains no imports of main.py or pcie_eq.gui.window."""
    tab_path = pathlib.Path("pcie_eq/gui/pam4_tab.py")
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

    assert not found_forbidden, f"pcie_eq/gui/pam4_tab.py contains forbidden imports: {found_forbidden}"


def test_build_pam4_tab_attachment(qapp):
    """Verify build_pam4_tab attaches all expected attributes, plots, curves, and controls to PCIeTxEqSimulator."""
    win = PCIeTxEqSimulator()
    try:
        expected_attrs = [
            "pam4_wave_plot",
            "pam4_eye_plot",
            "pam4_tx_curve",
            "pam4_ch_curve",
            "pam4_eye_curve",
            "pam4_status_panel",
            "pam4_status_layout",
            "pam4_status_items",
            "gen6_preset_combo",
            "pam4_eye_mode_combo",
            "btn_pam4_new_wave",
            "btn_pam4_reset_eq",
            "btn_pam4_reset_channel",
            "btn_pam4_detail",
            "pam4_slider_cm2",
            "pam4_slider_cm1",
            "pam4_slider_cp1",
            "pam4_slider_alpha",
        ]
        for attr in expected_attrs:
            assert hasattr(win, attr), f"PCIeTxEqSimulator missing expected attribute after build_pam4_tab: {attr}"

        assert len(win.pam4_status_items) == 8
        assert win.gen6_preset_combo.count() == 11  # Custom + Q0..Q9
        assert win.pam4_eye_mode_combo.count() == 2  # Raw Eye + Common t_center Eye
    finally:
        win.close()
