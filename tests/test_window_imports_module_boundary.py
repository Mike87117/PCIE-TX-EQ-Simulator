"""
Module boundary and import surface tests for pcie_eq.gui.window module.

Verifies:
1. window.py import surface matches the strict allowlist (AST check).
2. window.__all__ and re-exported symbol identities remain intact.
3. main.PCIeTxEqSimulator, pcie_eq.gui.PCIeTxEqSimulator, and window.PCIeTxEqSimulator are the exact same class object.
4. PCIeTxEqSimulator MRO remains unchanged.
5. bits and symbols static SHA-256 fingerprints match expected baseline hashes.
"""

import ast
import hashlib
import pathlib
import numpy as np

import main
import pcie_eq.gui
from pcie_eq.gui import window
from pcie_eq.gui.nrz_controller import NrzControllerMixin
from pcie_eq.gui.pam4_controller import Pam4ControllerMixin
from pcie_eq.gui.window_helpers import WindowUiHelpersMixin
from PyQt5.QtWidgets import QMainWindow


EXPECTED_WINDOW_ALL = [
    "BIT_COUNT",
    "SPB",
    "PLOT_BITS",
    "EYE_UI",
    "MAX_EYE_TRACES",
    "REALTIME_EYE_TRACES",
    "REALTIME_EYE_INTERVAL_MS",
    "PAM4_SYMBOL_COUNT",
    "pam4_symbols_from_random",
    "validate_gen6_presets",
    "PCIeTxEqSimulator",
]


def test_window_import_surface_ast_allowlist():
    """AST check verifying pcie_eq/gui/window.py import surface matches the exact allowlist."""
    win_path = pathlib.Path("pcie_eq/gui/window.py")
    tree = ast.parse(win_path.read_text(encoding="utf-8"))

    imports = []
    from_imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, alias.asname))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                from_imports.append((node.module, alias.name))

    # Exact expected imports
    assert imports == [("numpy", "np")]

    expected_from_imports = {
        ("PyQt5.QtWidgets", "QMainWindow"),
        ("pcie_eq.gui.constants", "BIT_COUNT"),
        ("pcie_eq.gui.constants", "SPB"),
        ("pcie_eq.gui.constants", "PLOT_BITS"),
        ("pcie_eq.gui.constants", "EYE_UI"),
        ("pcie_eq.gui.constants", "MAX_EYE_TRACES"),
        ("pcie_eq.gui.constants", "REALTIME_EYE_TRACES"),
        ("pcie_eq.gui.constants", "REALTIME_EYE_INTERVAL_MS"),
        ("pcie_eq.gui.constants", "PAM4_SYMBOL_COUNT"),
        ("pcie_eq.gui.pam4_tab", "build_pam4_tab"),
        ("pcie_eq.gui.nrz_controller", "NrzControllerMixin"),
        ("pcie_eq.gui.pam4_controller", "Pam4ControllerMixin"),
        ("pcie_eq.gui.window_helpers", "WindowUiHelpersMixin"),
        ("pcie_eq.gui.random_data", "pam4_symbols_from_random"),
        ("pcie_eq.gui.preset_debug", "validate_gen6_presets"),
        ("pcie_eq.gui.window_state", "initialize_window_state"),
        ("pcie_eq.gui.window_layout", "build_main_window_ui"),
    }

    assert set(from_imports) == expected_from_imports
    assert len(from_imports) == len(expected_from_imports)


def test_window_all_and_reexport_identities():
    """Verify window.__all__ and re-export symbol identities."""
    assert window.__all__ == EXPECTED_WINDOW_ALL

    for symbol_name in EXPECTED_WINDOW_ALL:
        assert hasattr(window, symbol_name), f"window module missing re-exported symbol: {symbol_name}"


def test_pcie_tx_eq_simulator_class_identity_and_mro():
    """Verify class identity across main, pcie_eq.gui, and window, and verify MRO."""
    assert main.PCIeTxEqSimulator is window.PCIeTxEqSimulator
    assert pcie_eq.gui.PCIeTxEqSimulator is window.PCIeTxEqSimulator

    assert window.PCIeTxEqSimulator.__mro__[:4] == (
        window.PCIeTxEqSimulator,
        NrzControllerMixin,
        Pam4ControllerMixin,
        WindowUiHelpersMixin,
    )
    assert QMainWindow in window.PCIeTxEqSimulator.__mro__


def test_bits_and_symbols_fingerprints():
    """Verify static SHA-256 fingerprints for module-level bits and symbols arrays."""
    bits_sha = hashlib.sha256(np.asarray(window.bits, dtype="<i8").tobytes()).hexdigest()
    expected_bits_sha = "2493782381dbfd8df3986df590e95feeb0fa20afa76105f5d1a2b38a559f5392"
    assert bits_sha == expected_bits_sha, f"bits SHA mismatch: got {bits_sha}, expected {expected_bits_sha}"

    symbols_sha = hashlib.sha256(np.asarray(window.symbols, dtype="<i8").tobytes()).hexdigest()
    expected_symbols_sha = "3ea421d4936ab544f825032d24ee5a164fc656bb66cc362a3c81e208d2c1d091"
    assert symbols_sha == expected_symbols_sha, f"symbols SHA mismatch: got {symbols_sha}, expected {expected_symbols_sha}"
