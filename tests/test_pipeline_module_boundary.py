"""
Module Boundary Tests for pcie_eq.pipeline.

Verifies:
1. Independent importability of pcie_eq.pipeline without GUI libraries or main.py.
2. AST inspection confirming no forbidden imports (PyQt5, PyQt6, PySide, pyqtgraph, main, ui).
3. Presence of all 3 pipeline APIs in pcie_eq.pipeline and __all__.
"""

import ast
import inspect
import importlib
import pytest


def test_pipeline_independent_import():
    """
    Verify pcie_eq.pipeline can be imported independently.
    """
    mod = importlib.import_module("pcie_eq.pipeline")
    assert mod is not None


def test_pipeline_api_completeness():
    """
    Verify presence of all 3 pipeline functions in pcie_eq.pipeline and __all__.
    """
    import pcie_eq.pipeline as pipeline

    expected_apis = [
        "run_nrz_simulation",
        "run_pam4_simulation",
        "run_simulation",
    ]

    for api_name in expected_apis:
        assert hasattr(pipeline, api_name), f"pcie_eq.pipeline missing attribute '{api_name}'"
        assert api_name in pipeline.__all__, f"pcie_eq.pipeline.__all__ missing '{api_name}'"


def test_pipeline_no_forbidden_imports():
    """
    Inspect pcie_eq.pipeline AST to ensure no imports of GUI libraries or main.py.
    """
    import pcie_eq.pipeline as pipeline

    source_path = inspect.getfile(pipeline)
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
    assert not forbidden_found, f"pcie_eq.pipeline contains forbidden imports: {forbidden_found}"


def test_pipeline_only_allowed_imports():
    """
    Verify that pcie_eq.pipeline only imports approved dependencies (pcie_eq.*, numpy, stdlib).
    """
    import pcie_eq.pipeline as pipeline

    source_path = inspect.getfile(pipeline)
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

    allowed_prefixes = {"numpy", "pcie_eq"}
    disallowed = set()

    for mod_name in imported_modules:
        base_mod = mod_name.split(".")[0]
        if base_mod not in allowed_prefixes:
            spec = importlib.util.find_spec(base_mod)
            assert spec is not None, f"Module '{mod_name}' not found"
            if spec.origin is not None and "stdlib" not in str(spec.origin).lower() and spec.origin != "built-in":
                disallowed.add(mod_name)

    assert not disallowed, f"pcie_eq.pipeline contains unapproved non-stdlib imports: {disallowed}"
