"""
Module boundary tests for pcie_eq.gui.pam4_controller module.

Verifies:
1. Pam4ControllerMixin class is defined in pcie_eq.gui.pam4_controller.
2. Pam4ControllerMixin does not inherit from Qt classes.
3. PCIeTxEqSimulator inherits from NrzControllerMixin and Pam4ControllerMixin.
4. pcie_eq/gui/pam4_controller.py does not import main.py or pcie_eq.gui.window (AST check).
5. All 21 PAM4 controller methods are properly defined on Pam4ControllerMixin.
6. PCIeTxEqSimulator in pcie_eq/gui/window.py does not inline-define the 21 PAM4 methods (AST check).
"""

import ast
import pathlib
from PyQt5.QtWidgets import QMainWindow

from pcie_eq.gui.nrz_controller import NrzControllerMixin
from pcie_eq.gui.pam4_controller import Pam4ControllerMixin
from pcie_eq.gui.window import PCIeTxEqSimulator

PAM4_METHODS = [
    "pam4_sync_ui_from_state",
    "apply_gen6_preset",
    "on_gen6_preset_change",
    "set_gen6_custom_preset",
    "on_pam4_slider_change",
    "on_pam4_edit_change",
    "on_pam4_generate_new_waveform",
    "on_pam4_reset_eq",
    "on_pam4_reset_channel",
    "on_pam4_eye_mode_change",
    "on_toggle_pam4_detail",
    "pam4_full_refresh",
    "pam4_redraw_all",
    "update_pam4_waveform",
    "update_pam4_eye",
    "update_pam4_eye_raw",
    "update_pam4_eye_centered",
    "calc_pam4_eye_openings_at_phase",
    "estimate_pam4_common_t_center_phase",
    "update_pam4_eye_metrics",
    "update_pam4_info",
]


def test_pam4_controller_mixin_location_and_inheritance():
    """Verify Pam4ControllerMixin module location and class hierarchy."""
    assert Pam4ControllerMixin.__module__ == "pcie_eq.gui.pam4_controller"
    assert Pam4ControllerMixin.__bases__ == (object,)
    assert issubclass(PCIeTxEqSimulator, NrzControllerMixin)
    assert issubclass(PCIeTxEqSimulator, Pam4ControllerMixin)
    assert issubclass(PCIeTxEqSimulator, QMainWindow)
    assert PCIeTxEqSimulator.__mro__ == (
        PCIeTxEqSimulator,
        NrzControllerMixin,
        Pam4ControllerMixin,
        QMainWindow,
        object,
    ) or issubclass(PCIeTxEqSimulator, (NrzControllerMixin, Pam4ControllerMixin, QMainWindow))


def test_pam4_controller_ast_no_forbidden_imports():
    """AST check verifying pcie_eq/gui/pam4_controller.py contains no imports of main.py or pcie_eq.gui.window."""
    ctrl_path = pathlib.Path("pcie_eq/gui/pam4_controller.py")
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

    assert not found_forbidden, f"pcie_eq/gui/pam4_controller.py contains forbidden imports: {found_forbidden}"


def test_pam4_controller_methods_presence():
    """Verify all 21 PAM4 controller methods are defined on Pam4ControllerMixin."""
    for method in PAM4_METHODS:
        assert hasattr(Pam4ControllerMixin, method), f"Pam4ControllerMixin missing expected method: {method}"


def test_window_no_inline_pam4_methods():
    """AST check confirming window.py's PCIeTxEqSimulator class body does not inline-define PAM4 methods."""
    win_path = pathlib.Path("pcie_eq/gui/window.py")
    tree = ast.parse(win_path.read_text(encoding="utf-8"))

    class_methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "PCIeTxEqSimulator":
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    class_methods.add(item.name)

    inlined_pam4 = set(PAM4_METHODS).intersection(class_methods)
    assert not inlined_pam4, f"PCIeTxEqSimulator in window.py still inline-defines PAM4 methods: {inlined_pam4}"
