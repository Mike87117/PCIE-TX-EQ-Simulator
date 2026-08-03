"""
Module Boundary Tests for pcie_eq.metrics.

Verifies:
1. Independent importability of pcie_eq.metrics without GUI libraries, main.py, or other pcie_eq modules.
2. AST inspection confirming no forbidden imports (PyQt5, PyQt6, PySide, pyqtgraph, main, ui, pcie_eq.tx_eq, pcie_eq.channel, pcie_eq.rx_eq).
3. Presence of all core functions in pcie_eq.metrics and __all__.
4. Main integration compatibility.
"""

import ast
import inspect
import importlib
import pytest


def test_metrics_independent_import():
    """
    Verify pcie_eq.metrics can be imported independently.
    """
    mod = importlib.import_module("pcie_eq.metrics")
    assert mod is not None


def test_metrics_api_completeness():
    """
    Verify presence of all required metrics functions in pcie_eq.metrics and __all__.
    """
    import pcie_eq.metrics as metrics

    expected_apis = [
        "calc_pam4_eye_openings_at_phase",
        "estimate_pam4_common_t_center_phase",
        "calculate_pam4_eye_metrics",
        "calculate_dfe_eye_metrics",
        "calculate_nrz_eye_metrics",
        "calculate_eye_metrics",
    ]

    for api_name in expected_apis:
        assert hasattr(metrics, api_name), f"pcie_eq.metrics missing attribute '{api_name}'"
        assert api_name in metrics.__all__, f"pcie_eq.metrics.__all__ missing '{api_name}'"


def test_metrics_no_forbidden_imports():
    """
    Inspect pcie_eq.metrics AST to ensure no imports of GUI libraries, main.py, or sibling pcie_eq modules.
    """
    import pcie_eq.metrics as metrics

    source_path = inspect.getfile(metrics)
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
        "pcie_eq.channel",
        "pcie_eq.rx_eq",
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
    assert not forbidden_found, f"pcie_eq.metrics contains forbidden imports: {forbidden_found}"


def test_metrics_only_allowed_imports():
    """
    Verify that pcie_eq.metrics only imports approved dependencies (standard library & numpy).
    """
    import pcie_eq.metrics as metrics

    source_path = inspect.getfile(metrics)
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

    allowed_exact = {"numpy"}
    disallowed = set()

    for mod_name in imported_modules:
        base_mod = mod_name.split(".")[0]
        if mod_name not in allowed_exact:
            spec = importlib.util.find_spec(base_mod)
            assert spec is not None, f"Module '{mod_name}' not found"
            if spec.origin is not None and "stdlib" not in str(spec.origin).lower() and spec.origin != "built-in":
                disallowed.add(mod_name)

    assert not disallowed, f"pcie_eq.metrics contains unapproved non-stdlib imports: {disallowed}"


def test_metrics_main_compatibility():
    """
    Verify that main.py imports and re-exports core metrics functions from pcie_eq.metrics.
    """
    import main
    import pcie_eq.metrics as metrics

    assert (
        main.calc_pam4_eye_openings_at_phase is metrics.calc_pam4_eye_openings_at_phase
    ), "main.calc_pam4_eye_openings_at_phase is not metrics.calc_pam4_eye_openings_at_phase"
    assert (
        main.estimate_pam4_common_t_center_phase is metrics.estimate_pam4_common_t_center_phase
    ), "main.estimate_pam4_common_t_center_phase is not metrics.estimate_pam4_common_t_center_phase"
    assert (
        main.calculate_pam4_eye_metrics is metrics.calculate_pam4_eye_metrics
    ), "main.calculate_pam4_eye_metrics is not metrics.calculate_pam4_eye_metrics"
    assert (
        main.calculate_eye_metrics is metrics.calculate_eye_metrics
    ), "main.calculate_eye_metrics is not metrics.calculate_eye_metrics"
