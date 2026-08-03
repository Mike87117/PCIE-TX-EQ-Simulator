"""
Module boundary tests for pcie_eq.gui package.

Verifies:
1. PCIeTxEqSimulator class is defined in pcie_eq.gui.window module.
2. main.PCIeTxEqSimulator points to the exact same class as pcie_eq.gui.window.PCIeTxEqSimulator.
3. Legacy constant imports (SPB, BIT_COUNT, PAM4_SYMBOL_COUNT) from main.py remain compatible.
4. main.py does not define any large QMainWindow subclass inline (AST check).
"""

import ast
import pathlib
import pytest
from pcie_eq.gui.window import PCIeTxEqSimulator as CorePCIeTxEqSimulator
from pcie_eq.gui.window import SPB as CoreSPB, BIT_COUNT as CoreBIT_COUNT, PAM4_SYMBOL_COUNT as CorePAM4_SYMBOL_COUNT
import pcie_eq.gui as gui_pkg
import main


def test_class_definition_location():
    """Verify PCIeTxEqSimulator is defined in pcie_eq.gui.window and re-exported by pcie_eq.gui."""
    assert CorePCIeTxEqSimulator.__module__ == "pcie_eq.gui.window"
    assert gui_pkg.PCIeTxEqSimulator is CorePCIeTxEqSimulator


def test_main_reexport_identity():
    """Verify main.PCIeTxEqSimulator points to pcie_eq.gui.window.PCIeTxEqSimulator."""
    assert main.PCIeTxEqSimulator is CorePCIeTxEqSimulator


def test_legacy_constants_compatibility():
    """Verify legacy constants imported from main.py match core values."""
    assert main.SPB == CoreSPB == 32
    assert main.BIT_COUNT == CoreBIT_COUNT == 512
    assert main.PAM4_SYMBOL_COUNT == CorePAM4_SYMBOL_COUNT == 512


def test_main_py_no_inline_gui_class():
    """AST check verifying main.py contains no ClassDef for QMainWindow or PCIeTxEqSimulator."""
    main_path = pathlib.Path(main.__file__)
    tree = ast.parse(main_path.read_text(encoding="utf-8"))

    class_defs = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    assert "PCIeTxEqSimulator" not in class_defs, "main.py must not contain inline ClassDef for PCIeTxEqSimulator"
    assert len(class_defs) == 0, f"main.py should contain 0 class definitions, found: {class_defs}"
