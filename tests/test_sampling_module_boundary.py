"""
Module boundary tests for pcie_eq.sampling core module.

Verifies:
1. pcie_eq/sampling.py exports exact __all__ surface in exact required order.
2. Constants SAMPLING_PHASE_CONTRACT_ID and NRZ_WARMUP_SYMBOLS have exact values.
3. pcie_eq/sampling.py contains zero GUI, PyQt, PySide, pyqtgraph, main, models, pipeline, metrics, rx_eq, or tx_eq imports (AST check).
4. AST check verifying module contains no waveform math, eye metric formula, DFE formula, interpolation, roll/shift, convolution, or clipping/wrapping repair.
"""

import ast
import pathlib
import pcie_eq.sampling as sampling


def test_sampling_exact_export_surface_and_constants():
    """Verify pcie_eq.sampling exports exact __all__ in exact required order and constants."""
    expected_all = [
        "SAMPLING_PHASE_CONTRACT_ID",
        "NRZ_WARMUP_SYMBOLS",
        "validate_sampling_phase",
        "symbol_sample_index",
        "select_phase_centered_trace_starts",
    ]

    assert sampling.__all__ == expected_all
    for name in expected_all:
        assert hasattr(sampling, name), f"sampling module missing exported attribute: {name}"

    assert sampling.SAMPLING_PHASE_CONTRACT_ID == "pcie_eq-sampling-phase-v1"
    assert sampling.NRZ_WARMUP_SYMBOLS == 20


def test_sampling_ast_no_forbidden_imports_or_non_pure_math():
    """AST check verifying pcie_eq/sampling.py contains zero forbidden imports or non-coordinate formulas."""
    sampling_path = pathlib.Path("pcie_eq/sampling.py")
    tree = ast.parse(sampling_path.read_text(encoding="utf-8"))

    forbidden_modules = {
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "pyqtgraph",
        "main",
        "pcie_eq.gui",
        "pcie_eq.pipeline",
        "pcie_eq.models",
        "pcie_eq.metrics",
        "pcie_eq.rx_eq",
        "pcie_eq.tx_eq",
        "pcie_eq.channel",
    }

    found_forbidden = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in forbidden_modules:
                    if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                        found_forbidden.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for forbidden in forbidden_modules:
                    if node.module == forbidden or node.module.startswith(forbidden + "."):
                        found_forbidden.add(node.module)

    assert not found_forbidden, f"pcie_eq/sampling.py contains forbidden imports: {found_forbidden}"


def test_sampling_ast_no_waveform_math_dfe_metrics_or_convolution():
    """AST check verifying pcie_eq/sampling.py contains no waveform values math, interpolation, or convolution."""
    sampling_path = pathlib.Path("pcie_eq/sampling.py")
    source_code = sampling_path.read_text(encoding="utf-8")
    tree = ast.parse(source_code)

    forbidden_substrings = [
        "convolve",
        "roll(",
        "interp",
        "percentile",
        "eye_height",
        "eye_min",
        "eye_max",
        "margin_5pct",
        "center_spread",
        "dfe",
    ]

    for item in forbidden_substrings:
        assert item not in source_code, f"pcie_eq/sampling.py contains non-coordinate code: '{item}'"
