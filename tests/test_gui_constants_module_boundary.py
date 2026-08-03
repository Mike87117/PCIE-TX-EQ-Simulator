"""
Module boundary tests for pcie_eq.gui.constants module.

Verifies:
1. Constants are defined in pcie_eq.gui.constants module.
2. main.py and pcie_eq.gui.window re-export identical constant values.
3. pcie_eq/gui/constants.py has zero imports of PyQt, pyqtgraph, main, or window (AST check).
"""

import ast
import pathlib
import pcie_eq.gui.constants as gui_constants
import pcie_eq.gui.window as gui_window
import main


def test_constants_values_and_locations():
    """Verify all 8 GUI constants are defined in pcie_eq.gui.constants with expected values."""
    assert gui_constants.BIT_COUNT == 512
    assert gui_constants.SPB == 32
    assert gui_constants.PLOT_BITS == 64
    assert gui_constants.EYE_UI == 2
    assert gui_constants.MAX_EYE_TRACES == 200
    assert gui_constants.REALTIME_EYE_TRACES == 60
    assert gui_constants.REALTIME_EYE_INTERVAL_MS == 50
    assert gui_constants.PAM4_SYMBOL_COUNT == 512


def test_window_and_main_reexports_identity():
    """Verify window.py and main.py re-export constants with identical values."""
    assert gui_window.BIT_COUNT == gui_constants.BIT_COUNT == main.BIT_COUNT
    assert gui_window.SPB == gui_constants.SPB == main.SPB
    assert gui_window.PAM4_SYMBOL_COUNT == gui_constants.PAM4_SYMBOL_COUNT == main.PAM4_SYMBOL_COUNT
    assert gui_window.PLOT_BITS == gui_constants.PLOT_BITS
    assert gui_window.EYE_UI == gui_constants.EYE_UI
    assert gui_window.MAX_EYE_TRACES == gui_constants.MAX_EYE_TRACES
    assert gui_window.REALTIME_EYE_TRACES == gui_constants.REALTIME_EYE_TRACES
    assert gui_window.REALTIME_EYE_INTERVAL_MS == gui_constants.REALTIME_EYE_INTERVAL_MS


def test_constants_ast_zero_gui_or_window_imports():
    """AST check verifying pcie_eq/gui/constants.py contains 0 imports of PyQt, pyqtgraph, main, or window."""
    const_path = pathlib.Path("pcie_eq/gui/constants.py")
    tree = ast.parse(const_path.read_text(encoding="utf-8"))

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    assert len(imports) == 0, f"pcie_eq/gui/constants.py must contain zero imports, found: {imports}"
