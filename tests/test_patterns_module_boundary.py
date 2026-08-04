"""
Module boundary tests for pcie_eq.patterns core module.

Verifies:
1. pcie_eq/patterns.py contains no GUI, PyQt, PySide, pyqtgraph, or main.py imports (AST check).
2. All functions exported in __all__ are present in pcie_eq.patterns.
"""

import ast
import pathlib
import pcie_eq.patterns as patterns


def test_patterns_ast_no_forbidden_gui_imports():
    """AST check verifying pcie_eq/patterns.py contains zero GUI or application level imports."""
    patterns_path = pathlib.Path("pcie_eq/patterns.py")
    tree = ast.parse(patterns_path.read_text(encoding="utf-8"))

    forbidden_prefix_or_modules = {
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "pyqtgraph",
        "main",
        "pcie_eq.gui",
    }

    found_forbidden = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in forbidden_prefix_or_modules:
                    if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                        found_forbidden.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for forbidden in forbidden_prefix_or_modules:
                    if node.module == forbidden or node.module.startswith(forbidden + "."):
                        found_forbidden.add(node.module)

    assert not found_forbidden, f"pcie_eq/patterns.py contains forbidden GUI imports: {found_forbidden}"


def test_patterns_all_export_surface():
    """Verify pcie_eq.patterns exports all expected functions in __all__."""
    expected_all = [
        "nrz_bits_to_symbols",
        "generate_random_nrz_bits",
        "generate_random_pam4_symbols",
        "generate_nrz_all_zeros",
        "generate_nrz_all_ones",
        "generate_nrz_alternating",
        "generate_nrz_long_run",
        "generate_nrz_single_transition",
        "generate_nrz_single_bit_pulse",
    ]

    assert patterns.__all__ == expected_all
    for name in expected_all:
        assert hasattr(patterns, name), f"patterns module missing exported function: {name}"
