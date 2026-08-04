"""
Module boundary tests for pcie_eq.gui.nrz_controller module.

Verifies:
1. NrzControllerMixin class is defined in pcie_eq.gui.nrz_controller.
2. NrzControllerMixin does not inherit from Qt classes.
3. PCIeTxEqSimulator inherits from NrzControllerMixin.
4. pcie_eq/gui/nrz_controller.py does not import main.py or pcie_eq.gui.window (AST check).
5. NRZ controller methods are properly defined on NrzControllerMixin.
"""

import ast
import pathlib
from pcie_eq.gui.nrz_controller import NrzControllerMixin
from pcie_eq.gui.window import PCIeTxEqSimulator


def test_nrz_controller_mixin_location_and_inheritance():
    """Verify NrzControllerMixin module location and that it does not inherit from Qt classes."""
    assert NrzControllerMixin.__module__ == "pcie_eq.gui.nrz_controller"
    assert NrzControllerMixin.__bases__ == (object,)
    assert issubclass(PCIeTxEqSimulator, NrzControllerMixin)


def test_nrz_controller_ast_no_forbidden_imports():
    """AST check verifying pcie_eq/gui/nrz_controller.py contains no imports of main.py or pcie_eq.gui.window."""
    ctrl_path = pathlib.Path("pcie_eq/gui/nrz_controller.py")
    tree = ast.parse(ctrl_path.read_text(encoding="utf-8"))

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

    assert not found_forbidden, f"pcie_eq/gui/nrz_controller.py contains forbidden imports: {found_forbidden}"


def test_nrz_controller_methods_presence():
    """Verify key NRZ controller methods are defined on NrzControllerMixin."""
    expected_methods = [
        "set_preset_combo_silent",
        "sync_ui_from_state",
        "enforce_tap_constraint",
        "set_custom_preset",
        "apply_preset",
        "on_preset_change",
        "on_edit_change",
        "on_tap_slider_change",
        "on_alpha_slider_change",
        "is_any_slider_down",
        "on_slider_released",
        "on_rx_slider_change",
        "on_rx_edit_change",
        "on_rx_view_change",
        "on_reset_rx",
        "on_generate_new_waveform",
        "on_reset_no_eq",
        "on_reset_channel",
        "on_reset_all",
        "on_toggle_nrz_detail",
        "get_target_rx_wave",
        "update_eye_title",
        "should_update_realtime_eye",
        "update_nrz_realtime",
        "redraw_all",
        "full_refresh",
        "update_waveform",
        "update_eye",
        "update_eye_line",
        "update_dfe_sample_plot",
        "update_eye_metrics",
        "update_info",
    ]
    for method in expected_methods:
        assert hasattr(NrzControllerMixin, method), f"NrzControllerMixin missing expected method: {method}"
