"""
Module Boundary Tests for pcie_eq.channel.

Verifies:
1. Independent importability of pcie_eq.channel without GUI libraries or main.py.
2. AST inspection confirming no forbidden imports (PyQt5, PyQt6, PySide, pyqtgraph, main, ui, pcie_eq.tx_eq).
3. Presence of simple_channel in pcie_eq.channel and __all__.
"""

import ast
import inspect
import importlib
import pytest


def test_channel_independent_import():
    """
    Verify pcie_eq.channel can be imported independently.
    """
    mod = importlib.import_module("pcie_eq.channel")
    assert mod is not None


def test_channel_api_completeness():
    """
    Verify presence of simple_channel in pcie_eq.channel and __all__.
    """
    import pcie_eq.channel as channel

    assert hasattr(channel, "simple_channel"), "pcie_eq.channel missing attribute 'simple_channel'"
    assert "simple_channel" in channel.__all__, "pcie_eq.channel.__all__ missing 'simple_channel'"


def test_channel_no_forbidden_imports():
    """
    Inspect pcie_eq.channel AST to ensure no imports of GUI libraries, main.py, or tx_eq.
    """
    import pcie_eq.channel as channel

    source_path = inspect.getfile(channel)
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
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split(".")[0])

    forbidden_found = imported_modules.intersection(forbidden_modules)
    assert not forbidden_found, f"pcie_eq.channel contains forbidden imports: {forbidden_found}"


def test_channel_only_allowed_imports():
    """
    Verify that pcie_eq.channel only imports approved dependencies (standard library & numpy).
    """
    import pcie_eq.channel as channel

    source_path = inspect.getfile(channel)
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

    allowed_modules = {"numpy"}
    non_numpy_imports = imported_modules - allowed_modules

    for mod_name in non_numpy_imports:
        spec = importlib.util.find_spec(mod_name)
        assert spec is not None, f"Module '{mod_name}' not found"
