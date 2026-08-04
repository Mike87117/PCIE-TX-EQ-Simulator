"""
Module boundary and contract tests for pcie_eq.gui.window_helpers module.

Verifies:
1. WindowUiHelpersMixin module location, inheritance from object, and no __init__ definition.
2. Helper methods presence in WindowUiHelpersMixin.__dict__.
3. pcie_eq/gui/window.py does not inline-define the 4 helper methods (AST check).
4. pcie_eq/gui/window_helpers.py contains no forbidden imports (AST check).
5. PCIeTxEqSimulator MRO leading prefix includes WindowUiHelpersMixin before QMainWindow.
6. make_slider contract (layout, widths, orientation, alignment, keys).
7. ui_sync contract (re-entrancy, yielding, exception safety).
8. Silent setter methods contract (signal blocking during update, unblocking afterwards).
"""

import ast
import pathlib
import pytest
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QSlider, QLineEdit
from PyQt5.QtCore import Qt

from pcie_eq.gui.nrz_controller import NrzControllerMixin
from pcie_eq.gui.pam4_controller import Pam4ControllerMixin
from pcie_eq.gui.window_helpers import WindowUiHelpersMixin
from pcie_eq.gui.window import PCIeTxEqSimulator

HELPER_METHODS = [
    "make_slider",
    "ui_sync",
    "set_slider_value_silent",
    "set_edit_text_silent",
]


@pytest.fixture(scope="module")
def qapp():
    """Shared QApplication fixture for Qt widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_window_helpers_mixin_properties():
    """Verify WindowUiHelpersMixin location, base class, and lack of __init__."""
    assert WindowUiHelpersMixin.__module__ == "pcie_eq.gui.window_helpers"
    assert WindowUiHelpersMixin.__bases__ == (object,)
    assert "__init__" not in WindowUiHelpersMixin.__dict__


def test_window_helpers_methods_presence():
    """Verify all 4 helper methods are defined directly in WindowUiHelpersMixin.__dict__."""
    for method in HELPER_METHODS:
        assert method in WindowUiHelpersMixin.__dict__, f"{method} not found in WindowUiHelpersMixin.__dict__"


def test_window_no_inline_helpers_ast():
    """AST check confirming window.py's PCIeTxEqSimulator class body does not inline-define helper methods."""
    win_path = pathlib.Path("pcie_eq/gui/window.py")
    tree = ast.parse(win_path.read_text(encoding="utf-8"))

    class_methods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "PCIeTxEqSimulator":
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    class_methods.add(item.name)

    inlined_helpers = set(HELPER_METHODS).intersection(class_methods)
    assert not inlined_helpers, f"PCIeTxEqSimulator in window.py still inline-defines helpers: {inlined_helpers}"


def test_window_helpers_ast_no_forbidden_imports():
    """AST check verifying pcie_eq/gui/window_helpers.py contains no forbidden imports."""
    helpers_path = pathlib.Path("pcie_eq/gui/window_helpers.py")
    tree = ast.parse(helpers_path.read_text(encoding="utf-8"))

    forbidden_modules = {
        "main",
        "window",
        "pcie_eq.gui.window",
        "pcie_eq.gui.nrz_controller",
        "pcie_eq.gui.pam4_controller",
        "pcie_eq.tx_eq",
        "pcie_eq.rx_eq",
        "pcie_eq.channel",
        "pcie_eq.metrics",
        "pcie_eq.models",
        "pcie_eq.pipeline",
    }
    found_forbidden = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_modules:
                    found_forbidden.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module in forbidden_modules:
                found_forbidden.add(node.module)

    assert not found_forbidden, f"pcie_eq/gui/window_helpers.py contains forbidden imports: {found_forbidden}"


def test_pcietxeqsimulator_mro():
    """Verify PCIeTxEqSimulator MRO leading prefix and WindowUiHelpersMixin position."""
    assert PCIeTxEqSimulator.__mro__[:4] == (
        PCIeTxEqSimulator,
        NrzControllerMixin,
        Pam4ControllerMixin,
        WindowUiHelpersMixin,
    )
    assert QMainWindow in PCIeTxEqSimulator.__mro__
    assert PCIeTxEqSimulator.__mro__.index(WindowUiHelpersMixin) < PCIeTxEqSimulator.__mro__.index(QMainWindow)


def test_make_slider_contract(qapp):
    """Verify make_slider constructs layout, widgets, properties, and dictionary correctly."""
    class DummyHost(WindowUiHelpersMixin):
        pass

    host = DummyHost()
    res = host.make_slider("Test Parameter", -300, 300, 150)

    assert set(res.keys()) == {"layout", "slider", "edit"}

    slider = res["slider"]
    assert slider.minimum() == -300
    assert slider.maximum() == 300
    assert slider.value() == 150
    assert slider.orientation() == Qt.Horizontal

    edit = res["edit"]
    assert int(edit.alignment()) & int(Qt.AlignRight)

    layout = res["layout"]
    assert layout.count() == 3

    label = layout.itemAt(0).widget()
    assert isinstance(label, QLabel)
    assert label.text() == "Test Parameter"
    assert label.minimumWidth() == 120
    assert label.maximumWidth() == 120

    assert layout.itemAt(1).widget() is slider

    assert layout.itemAt(2).widget() is edit
    assert edit.minimumWidth() == 80
    assert edit.maximumWidth() == 80


def test_ui_sync_contract():
    """Verify ui_sync context manager behavior under outer, nested, and exception conditions."""
    class DummyHost(WindowUiHelpersMixin):
        def __init__(self):
            self.syncing_ui = False

    host = DummyHost()
    assert not host.syncing_ui

    with host.ui_sync() as active1:
        assert active1 is True
        assert host.syncing_ui is True

        with host.ui_sync() as active2:
            assert active2 is False
            assert host.syncing_ui is True

        assert host.syncing_ui is True

    assert host.syncing_ui is False

    # Test exception safety
    with pytest.raises(RuntimeError):
        with host.ui_sync() as active:
            assert active is True
            assert host.syncing_ui is True
            raise RuntimeError("Simulated error inside ui_sync")

    assert host.syncing_ui is False


def test_silent_setter_contract(qapp):
    """Verify silent setter methods update widget state without firing signals."""
    class DummyHost(WindowUiHelpersMixin):
        pass

    host = DummyHost()
    slider = QSlider(Qt.Horizontal)
    slider.setMinimum(0)
    slider.setMaximum(100)
    slider.setValue(10)

    slider_signals = []
    slider.valueChanged.connect(lambda val: slider_signals.append(val))

    host.set_slider_value_silent(slider, 75)
    assert slider.value() == 75
    assert len(slider_signals) == 0
    assert not slider.signalsBlocked()

    edit = QLineEdit()
    edit.setText("initial")
    edit_signals = []
    edit.textChanged.connect(lambda text: edit_signals.append(text))

    host.set_edit_text_silent(edit, "updated")
    assert edit.text() == "updated"
    assert len(edit_signals) == 0
    assert not edit.signalsBlocked()
