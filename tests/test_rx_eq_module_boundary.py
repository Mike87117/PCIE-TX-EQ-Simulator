"""
Module Boundary Tests for pcie_eq.rx_eq.

Verifies:
1. Independent importability of pcie_eq.rx_eq without GUI libraries, main.py, or tx_eq.
2. AST inspection confirming no forbidden imports (PyQt5, PyQt6, PySide, pyqtgraph, main, ui, pcie_eq.tx_eq).
3. Presence of apply_ctle, apply_dfe, run_rx_pipeline in pcie_eq.rx_eq and __all__.
4. Main integration compatibility (main.apply_ctle is rx_eq.apply_ctle, etc.).
"""

import ast
import inspect
import importlib
import pytest


def test_rx_eq_independent_import():
    """
    Verify pcie_eq.rx_eq can be imported independently.
    """
    mod = importlib.import_module("pcie_eq.rx_eq")
    assert mod is not None


def test_rx_eq_api_completeness():
    """
    Verify presence of apply_ctle, apply_dfe, run_rx_pipeline in pcie_eq.rx_eq and __all__.
    """
    import pcie_eq.rx_eq as rx_eq

    expected_apis = ["apply_ctle", "apply_dfe", "run_rx_pipeline"]

    for api_name in expected_apis:
        assert hasattr(rx_eq, api_name), f"pcie_eq.rx_eq missing attribute '{api_name}'"
        assert api_name in rx_eq.__all__, f"pcie_eq.rx_eq.__all__ missing '{api_name}'"


def test_rx_eq_no_forbidden_imports():
    """
    Inspect pcie_eq.rx_eq AST to ensure no imports of GUI libraries, main.py, or tx_eq.
    """
    import pcie_eq.rx_eq as rx_eq

    source_path = inspect.getfile(rx_eq)
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
        "pcie_eq.tx_eq",
        "QApplication",
        "QWidget",
        "QMainWindow",
    }

    imported_modules = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)

    def is_forbidden(mod_name):
        return any(
            mod_name == forbidden or mod_name.startswith(f"{forbidden}.")
            for forbidden in forbidden_modules
        )

    forbidden_found = {m for m in imported_modules if is_forbidden(m)}
    assert not forbidden_found, f"pcie_eq.rx_eq contains forbidden imports: {forbidden_found}"


def test_rx_eq_only_allowed_imports():
    """
    Verify that pcie_eq.rx_eq only imports approved dependencies (standard library, numpy, pcie_eq.channel).
    """
    import pcie_eq.rx_eq as rx_eq

    source_path = inspect.getfile(rx_eq)
    with open(source_path, "r", encoding="utf-8") as f:
        source_text = f.read()

    tree = ast.parse(source_text, filename=source_path)

    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)

    allowed_exact = {"numpy", "pcie_eq.channel", "pcie_eq.sampling"}
    disallowed = set()

    for mod_name in imported_modules:
        base_mod = mod_name.split(".")[0]
        if mod_name not in allowed_exact:
            spec = importlib.util.find_spec(base_mod)
            assert spec is not None, f"Module '{mod_name}' not found"
            # If not in allowed list and not a stdlib module, report error
            if spec.origin is not None and "stdlib" not in str(spec.origin).lower() and spec.origin != "built-in":
                disallowed.add(mod_name)

    assert not disallowed, f"pcie_eq.rx_eq contains unapproved non-stdlib imports: {disallowed}"


def test_rx_eq_main_compatibility():
    """
    Verify that main.py re-exports the exact same function objects as pcie_eq.rx_eq.
    """
    import main
    import pcie_eq.rx_eq as rx_eq

    assert main.apply_ctle is rx_eq.apply_ctle, "main.apply_ctle is not rx_eq.apply_ctle"
    assert main.apply_dfe is rx_eq.apply_dfe, "main.apply_dfe is not rx_eq.apply_dfe"
    assert main.run_rx_pipeline is rx_eq.run_rx_pipeline, "main.run_rx_pipeline is not rx_eq.run_rx_pipeline"
