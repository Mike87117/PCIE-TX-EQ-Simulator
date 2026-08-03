"""
Module Boundary Tests for pcie_eq.models.

Verifies:
1. Independent importability of pcie_eq.models without GUI libraries or main.py.
2. AST inspection confirming no forbidden imports (PyQt5, PyQt6, PySide, pyqtgraph, main, ui).
3. Presence of all 4 data model classes in pcie_eq.models and __all__.
"""

import ast
import inspect
import importlib
import pytest


def test_models_independent_import():
    """
    Verify pcie_eq.models can be imported independently.
    """
    mod = importlib.import_module("pcie_eq.models")
    assert mod is not None


def test_models_api_completeness():
    """
    Verify presence of all 4 dataclasses in pcie_eq.models and __all__.
    """
    import pcie_eq.models as models

    expected_models = [
        "NrzSimulationConfig",
        "Pam4SimulationConfig",
        "NrzSimulationResult",
        "Pam4SimulationResult",
    ]

    for model_name in expected_models:
        assert hasattr(models, model_name), f"pcie_eq.models missing attribute '{model_name}'"
        assert model_name in models.__all__, f"pcie_eq.models.__all__ missing '{model_name}'"


def test_models_no_forbidden_imports():
    """
    Inspect pcie_eq.models AST to ensure no imports of GUI libraries or main.py.
    """
    import pcie_eq.models as models

    source_path = inspect.getfile(models)
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
    assert not forbidden_found, f"pcie_eq.models contains forbidden imports: {forbidden_found}"


def test_models_only_allowed_imports():
    """
    Verify that pcie_eq.models only imports approved dependencies (dataclasses, numpy, stdlib).
    """
    import pcie_eq.models as models

    source_path = inspect.getfile(models)
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

    allowed_exact = {"numpy", "dataclasses"}
    disallowed = set()

    for mod_name in imported_modules:
        base_mod = mod_name.split(".")[0]
        if mod_name not in allowed_exact:
            spec = importlib.util.find_spec(base_mod)
            assert spec is not None, f"Module '{mod_name}' not found"
            if spec.origin is not None and "stdlib" not in str(spec.origin).lower() and spec.origin != "built-in":
                disallowed.add(mod_name)

    assert not disallowed, f"pcie_eq.models contains unapproved non-stdlib imports: {disallowed}"
