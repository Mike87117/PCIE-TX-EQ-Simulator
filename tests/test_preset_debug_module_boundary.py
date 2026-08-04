"""
Module boundary tests for pcie_eq.gui.preset_debug module.

Verifies:
1. validate_gen6_presets is defined in pcie_eq.gui.preset_debug.
2. window.validate_gen6_presets is a re-export of preset_debug.validate_gen6_presets.
3. window.py does not inline-define validate_gen6_presets (AST check).
4. preset_debug.py contains no forbidden imports (AST check).
5. Output of validate_gen6_presets() matches line count and exact SHA-256 fingerprint.
"""

import ast
import io
import sys
import hashlib
import pathlib

from pcie_eq.gui import window, preset_debug


def test_preset_debug_location_and_reexport():
    """Verify validate_gen6_presets module location and backward-compatibility re-export."""
    assert preset_debug.validate_gen6_presets.__module__ == "pcie_eq.gui.preset_debug"
    assert window.validate_gen6_presets is preset_debug.validate_gen6_presets


def test_window_no_inline_validate_gen6_presets_ast():
    """AST check confirming window.py does not inline-define validate_gen6_presets."""
    win_path = pathlib.Path("pcie_eq/gui/window.py")
    tree = ast.parse(win_path.read_text(encoding="utf-8"))

    found_functions = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found_functions.add(node.name)

    assert "validate_gen6_presets" not in found_functions, "window.py still inline-defines validate_gen6_presets"


def test_preset_debug_ast_no_forbidden_imports():
    """AST check verifying pcie_eq/gui/preset_debug.py contains no forbidden imports."""
    debug_path = pathlib.Path("pcie_eq/gui/preset_debug.py")
    tree = ast.parse(debug_path.read_text(encoding="utf-8"))

    allowed_from_imports = {("pcie_eq.tx_eq", "PCIE_GEN6_PRESET_TAP_TABLE"), ("pcie_eq.tx_eq", "calc_gen6_levels")}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                pytest_fail_msg = f"Forbidden import '{alias.name}' in preset_debug.py"
                assert False, pytest_fail_msg
        elif isinstance(node, ast.ImportFrom):
            assert node.module == "pcie_eq.tx_eq", f"Forbidden import from '{node.module}' in preset_debug.py"
            for alias in node.names:
                assert (node.module, alias.name) in allowed_from_imports, (
                    f"Forbidden import '{alias.name}' from '{node.module}' in preset_debug.py"
                )


def test_validate_gen6_presets_output_fingerprint():
    """Verify validate_gen6_presets output has 12 lines and matches static SHA-256 fingerprint."""
    buf = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = buf
        preset_debug.validate_gen6_presets()
    finally:
        sys.stdout = old_stdout

    output = buf.getvalue()
    output = output.replace("\r\n", "\n")

    lines = output.strip().split("\n")
    assert len(lines) == 12, f"Expected 12 lines, got {len(lines)}"

    digest = hashlib.sha256(output.encode("utf-8")).hexdigest()
    expected_digest = "fbba0b4bdab65623a680bf561f05ed0c15b30438638230a827760bf1b95c5c14"
    assert digest == expected_digest, f"SHA-256 mismatch: got {digest}, expected {expected_digest}"
