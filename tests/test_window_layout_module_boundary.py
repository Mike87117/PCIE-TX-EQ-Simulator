"""
Module boundary and UI composition contract tests for pcie_eq.gui.window_layout module.

Verifies:
1. build_main_window_ui location, __all__, and allowed imports in window_layout.py.
2. pcie_eq/gui/window.py init_ui() delegates to build_main_window_ui(self) (AST check).
3. init_pam4_tab() remains in window.py calling build_pam4_tab(self) (AST check).
4. Top-level window tab count, titles, widget identities, and central widget.
5. Execution sequence: build_nrz_tab -> init_pam4_tab -> setCentralWidget.
"""

import ast
import pathlib
from unittest.mock import MagicMock, patch
import pytest
from PyQt5.QtWidgets import QApplication, QMainWindow

from pcie_eq.gui import window, window_layout
from pcie_eq.gui.window_layout import build_main_window_ui


@pytest.fixture(scope="module")
def qapp():
    """Shared QApplication fixture for Qt widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_window_layout_function_location_and_all():
    """Verify build_main_window_ui location and __all__ export."""
    assert window_layout.build_main_window_ui.__module__ == "pcie_eq.gui.window_layout"
    assert window_layout.__all__ == ["build_main_window_ui"]


def test_window_layout_ast_no_forbidden_imports():
    """AST check verifying pcie_eq/gui/window_layout.py contains no forbidden imports."""
    layout_path = pathlib.Path("pcie_eq/gui/window_layout.py")
    tree = ast.parse(layout_path.read_text(encoding="utf-8"))

    allowed_imports = {
        ("PyQt5.QtWidgets", "QWidget"),
        ("PyQt5.QtWidgets", "QVBoxLayout"),
        ("PyQt5.QtWidgets", "QTabWidget"),
        ("pcie_eq.gui.nrz_tab", "build_nrz_tab"),
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert False, f"Forbidden import '{alias.name}' in window_layout.py"
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                item = (node.module, alias.name)
                assert item in allowed_imports, f"Forbidden import '{alias.name}' from '{node.module}' in window_layout.py"


def test_window_ast_init_ui_and_pam4_tab_delegation():
    """AST check confirming init_ui() delegates to build_main_window_ui and init_pam4_tab remains."""
    win_path = pathlib.Path("pcie_eq/gui/window.py")
    tree = ast.parse(win_path.read_text(encoding="utf-8"))

    init_ui_node = None
    init_pam4_tab_node = None

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "PCIeTxEqSimulator":
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    if item.name == "init_ui":
                        init_ui_node = item
                    elif item.name == "init_pam4_tab":
                        init_pam4_tab_node = item

    assert init_ui_node is not None, "init_ui method not found in window.py"
    assert init_pam4_tab_node is not None, "init_pam4_tab method not found in window.py"

    # Verify init_ui body is just build_main_window_ui(self)
    assert len(init_ui_node.body) == 1
    assert isinstance(init_ui_node.body[0], ast.Expr)
    assert isinstance(init_ui_node.body[0].value, ast.Call)
    init_ui_call = init_ui_node.body[0].value
    assert isinstance(init_ui_call.func, ast.Name)
    assert init_ui_call.func.id == "build_main_window_ui"
    assert len(init_ui_call.args) == 1
    assert isinstance(init_ui_call.args[0], ast.Name)
    assert init_ui_call.args[0].id == "self"
    assert len(init_ui_call.keywords) == 0

    # Verify init_pam4_tab body calls build_pam4_tab(self)
    assert len(init_pam4_tab_node.body) == 1
    assert isinstance(init_pam4_tab_node.body[0], ast.Expr)
    assert isinstance(init_pam4_tab_node.body[0].value, ast.Call)
    pam4_call = init_pam4_tab_node.body[0].value
    assert isinstance(pam4_call.func, ast.Name)
    assert pam4_call.func.id == "build_pam4_tab"
    assert len(pam4_call.args) == 1
    assert isinstance(pam4_call.args[0], ast.Name)
    assert pam4_call.args[0].id == "self"
    assert len(pam4_call.keywords) == 0


def test_window_layout_composition_contracts(qapp):
    """Verify tabs count, titles, widget identities, and central widget on PCIeTxEqSimulator."""
    win = window.PCIeTxEqSimulator()

    assert hasattr(win, "tabs")
    assert hasattr(win, "nrz_tab")
    assert hasattr(win, "pam4_tab")

    assert win.tabs.count() == 2
    assert win.tabs.tabText(0) == "PCIe Gen1~5 NRZ TX EQ"
    assert win.tabs.tabText(1) == "PCIe Gen6 PAM4 TX EQ"

    assert win.tabs.widget(0) is win.nrz_tab
    assert win.tabs.widget(1) is win.pam4_tab

    central = win.centralWidget()
    assert central is not None
    assert central.layout() is not None
    assert central.layout().itemAt(0).widget() is win.tabs


def test_build_main_window_ui_execution_sequence(qapp):
    """Verify execution sequence inside build_main_window_ui: build_nrz_tab -> init_pam4_tab -> setCentralWidget."""
    class DummyWindow(QMainWindow):
        def init_pam4_tab(self):
            pass

    mock_win = MagicMock(spec=DummyWindow)
    sequence = []

    def mock_init_pam4():
        sequence.append("init_pam4_tab")

    def mock_set_central(widget):
        sequence.append("setCentralWidget")

    mock_win.init_pam4_tab.side_effect = mock_init_pam4
    mock_win.setCentralWidget.side_effect = mock_set_central

    with patch("pcie_eq.gui.window_layout.build_nrz_tab") as mock_nrz:
        mock_nrz.side_effect = lambda w: sequence.append("build_nrz_tab")

        build_main_window_ui(mock_win)

    assert sequence == ["build_nrz_tab", "init_pam4_tab", "setCentralWidget"]
