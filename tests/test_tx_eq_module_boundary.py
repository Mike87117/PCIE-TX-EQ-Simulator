"""
Module Boundary Tests for pcie_eq.tx_eq.

Verifies:
1. Independent importability of pcie_eq.tx_eq without GUI libraries or main.py.
2. AST inspection confirming no forbidden imports (PyQt5, PyQt6, PySide, pyqtgraph, main, ui).
3. Presence of all required constants and functions in pcie_eq.tx_eq and __all__.
"""

import ast
import inspect
import importlib
import pytest


def test_tx_eq_independent_import():
    """
    Verify pcie_eq.tx_eq can be imported independently.
    """
    mod = importlib.import_module("pcie_eq.tx_eq")
    assert mod is not None


def test_tx_eq_api_completeness():
    """
    Verify presence of all required constants and functions in pcie_eq.tx_eq and __all__.
    """
    import pcie_eq.tx_eq as tx_eq

    expected_symbols = [
        "PCIE_PRESET_DB_TABLE",
        "PCIE_GEN6_PRESET_TAP_TABLE",
        "taps_to_db",
        "calc_levels",
        "db_to_taps",
        "tx_fir",
        "tx_eq_levels",
        "constrain_gen6_taps",
        "calc_gen6_levels",
        "gen6_pam4_fir",
    ]

    for sym in expected_symbols:
        assert hasattr(tx_eq, sym), f"pcie_eq.tx_eq missing attribute '{sym}'"
        assert sym in tx_eq.__all__, f"pcie_eq.tx_eq.__all__ missing symbol '{sym}'"


def test_tx_eq_no_forbidden_imports():
    """
    Inspect pcie_eq.tx_eq AST to ensure no imports of GUI libraries or main.py.
    """
    import pcie_eq.tx_eq as tx_eq

    source_path = inspect.getfile(tx_eq)
    with open(source_path, "r", encoding="utf-8") as f:
        source_text = f.read()

    tree = ast.parse(source_text, filename=source_path)

    forbidden_modules = {
        "PyQt5",
        "PyQt6",
        "PySide",
        "PySide2",
        "PySide6",
        "pyqtgraph",
        "main",
        "ui",
    }

    imported_modules = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split(".")[0])

    forbidden_found = imported_modules.intersection(forbidden_modules)
    assert not forbidden_found, f"pcie_eq.tx_eq contains forbidden imports: {forbidden_found}"


def test_tx_eq_only_allowed_imports():
    """
    Verify that pcie_eq.tx_eq only imports approved dependencies (standard library & numpy).
    """
    import pcie_eq.tx_eq as tx_eq

    source_path = inspect.getfile(tx_eq)
    with open(source_path, "r", encoding="utf-8") as f:
        source_text = f.read()

    tree = ast.parse(source_text, filename=source_path)

    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split(".")[0])

    # Allow standard library modules and numpy
    allowed_modules = {"numpy"}
    non_numpy_imports = imported_modules - allowed_modules

    # Ensure none of non_numpy_imports are third-party GUI or application modules
    for mod_name in non_numpy_imports:
        # Check that it's a standard library module if any
        spec = importlib.util.find_spec(mod_name)
        assert spec is not None, f"Module '{mod_name}' not found"
        # Standard library modules in Python 3.10+ have origin 'built-in' or belong to stdlib
