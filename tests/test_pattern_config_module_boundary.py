"""
Module boundary tests for pcie_eq.pattern_config core module.

Verifies:
1. pcie_eq/pattern_config.py exports exact __all__ surface in exact order.
2. pcie_eq/pattern_config.py contains zero GUI, PyQt, PySide, pyqtgraph, main, or pipeline imports (AST check).
"""

import ast
import pathlib
import pcie_eq.pattern_config as pattern_config


def test_pattern_config_exact_export_surface():
    """Verify pcie_eq.pattern_config exports exact __all__ in exact required order."""
    expected_all = [
        "PATTERN_CONFIG_CONTRACT_ID",
        "PatternConfig",
        "PatternResult",
        "generate_pattern",
    ]

    assert pattern_config.__all__ == expected_all
    for name in expected_all:
        assert hasattr(pattern_config, name), f"pattern_config module missing exported attribute: {name}"


def test_pattern_config_ast_no_forbidden_gui_or_pipeline_imports():
    """AST check verifying pcie_eq/pattern_config.py contains zero GUI, pipeline, or main level imports."""
    config_path = pathlib.Path("pcie_eq/pattern_config.py")
    tree = ast.parse(config_path.read_text(encoding="utf-8"))

    forbidden_prefix_or_modules = {
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "pyqtgraph",
        "main",
        "pcie_eq.gui",
        "pcie_eq.pipeline",
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

    assert not found_forbidden, f"pcie_eq/pattern_config.py contains forbidden imports: {found_forbidden}"
