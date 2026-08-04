"""
Module boundary and state contract tests for pcie_eq.gui.window_state module.

Verifies:
1. initialize_window_state function location, __all__, and allowed imports in window_state.py.
2. pcie_eq/gui/window.py delegates attribute initialization to initialize_window_state (AST check).
3. Order of calls inside PCIeTxEqSimulator.__init__() (AST check).
4. All NRZ and PAM4 default attribute values and metrics dictionaries.
5. bits and symbols are copied (.copy()), not referenced as aliases.
6. cm1_current and cp1_current match db_to_taps(1.5, -3.5).
7. QElapsedTimer instance created and started.
8. pam4_symbols_from_random(PAM4_SYMBOL_COUNT) called exactly once.
"""

import ast
import pathlib
from unittest.mock import patch
import numpy as np
from PyQt5.QtCore import QElapsedTimer

from pcie_eq.tx_eq import db_to_taps
from pcie_eq.gui.constants import SPB, PAM4_SYMBOL_COUNT
from pcie_eq.gui import window, window_state


def test_window_state_function_location_and_all():
    """Verify initialize_window_state location and __all__ export."""
    assert window_state.initialize_window_state.__module__ == "pcie_eq.gui.window_state"
    assert window_state.__all__ == ["initialize_window_state"]


def test_window_state_ast_no_forbidden_imports():
    """AST check verifying pcie_eq/gui/window_state.py contains no forbidden imports."""
    state_path = pathlib.Path("pcie_eq/gui/window_state.py")
    tree = ast.parse(state_path.read_text(encoding="utf-8"))

    allowed_imports = {
        ("PyQt5.QtCore", "QElapsedTimer"),
        ("pcie_eq.tx_eq", "db_to_taps"),
        ("pcie_eq.gui.constants", "SPB"),
        ("pcie_eq.gui.constants", "PAM4_SYMBOL_COUNT"),
        ("pcie_eq.gui.random_data", "pam4_symbols_from_random"),
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert False, f"Forbidden import '{alias.name}' in window_state.py"
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                item = (node.module, alias.name)
                assert item in allowed_imports, f"Forbidden import '{alias.name}' from '{node.module}' in window_state.py"


def test_window_ast_delegates_state_initialization():
    """AST check verifying PCIeTxEqSimulator.__init__() calls initialize_window_state and has no inline attribute assignments."""
    win_path = pathlib.Path("pcie_eq/gui/window.py")
    tree = ast.parse(win_path.read_text(encoding="utf-8"))

    init_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "PCIeTxEqSimulator":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    init_node = item
                    break

    assert init_node is not None, "PCIeTxEqSimulator.__init__ not found"

    # Find function calls inside __init__
    called_names = []
    for stmt in init_node.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            func = stmt.value.func
            if isinstance(func, ast.Name):
                called_names.append(func.id)
            elif isinstance(func, ast.Attribute):
                called_names.append(func.attr)

    assert "initialize_window_state" in called_names, "initialize_window_state not called in __init__"

    # Verify order: setWindowTitle -> resize -> initialize_window_state -> init_ui -> full_refresh -> pam4_full_refresh
    assert called_names == [
        "__init__",
        "setWindowTitle",
        "resize",
        "initialize_window_state",
        "init_ui",
        "full_refresh",
        "pam4_full_refresh",
    ]


def test_initialize_window_state_values_and_copies():
    """Verify default attribute values, dict structures, copy behavior, and QElapsedTimer validity."""
    class DummyWindow:
        pass

    dummy = DummyWindow()
    test_bits = np.array([1, 0, 1, 1, 0], dtype=int)
    test_symbols = np.array([1, -1, 1, 1, -1], dtype=float)

    with patch("pcie_eq.gui.window_state.pam4_symbols_from_random") as mock_rand:
        mock_symbols = np.array([0.33, -0.33, 1.0, -1.0])
        mock_rand.return_value = mock_symbols

        window_state.initialize_window_state(dummy, test_bits, test_symbols)

        mock_rand.assert_called_once_with(PAM4_SYMBOL_COUNT)

    assert dummy.syncing_ui is False
    assert dummy.control_mode == "db"
    assert dummy.current_preset == "Custom"
    assert dummy.channel_alpha_current == 0.08

    assert dummy.pre_db_current == 1.5
    assert dummy.de_db_current == -3.5

    expected_cm1, expected_cp1 = db_to_taps(1.5, -3.5)
    assert dummy.cm1_current == expected_cm1
    assert dummy.cp1_current == expected_cp1

    assert dummy.rx_view_mode == "Channel (Before RX EQ)"
    assert dummy.ctle_boost_current == 0.0
    assert dummy.dfe_tap1_current == 0.0
    assert dummy.dfe_tap2_current == 0.0
    assert dummy.dfe_tap3_current == 0.0

    assert dummy.eye_metrics == {
        "eye_height": 0.0,
        "eye_max": 0.0,
        "eye_min": 0.0,
        "center_spread": 0.0,
    }

    # Verify bits and symbols copies
    assert dummy.bits is not test_bits
    assert np.array_equal(dummy.bits, test_bits)
    assert dummy.symbols is not test_symbols
    assert np.array_equal(dummy.symbols, test_symbols)

    # Verify QElapsedTimer
    assert isinstance(dummy.realtime_eye_timer, QElapsedTimer)
    assert dummy.realtime_eye_timer.isValid()

    # Verify PAM4 attributes
    assert dummy.gen6_preset_current == "Q0"
    assert dummy.pam4_cm2_current == 0.0
    assert dummy.pam4_cm1_current == 0.0
    assert dummy.pam4_cp1_current == 0.0
    assert dummy.pam4_alpha_current == 0.08
    assert dummy.pam4_eye_mode == "raw"
    assert dummy.pam4_t_center_phase == SPB // 2
    assert dummy.pam4_t_center_score == 0.0
    assert np.array_equal(dummy.pam4_symbols, mock_symbols)
    assert dummy.pam4_eye_metrics == {
        "upper_eye": 0.0,
        "middle_eye": 0.0,
        "lower_eye": 0.0,
        "minimum_eye": 0.0,
        "center_spread": 0.0,
    }
