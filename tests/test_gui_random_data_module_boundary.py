"""
Module boundary tests for pcie_eq.gui.random_data module.

Verifies:
1. pam4_symbols_from_random is defined in pcie_eq.gui.random_data.
2. pcie_eq.gui.window.pam4_symbols_from_random is a re-export.
3. pam4_symbols_from_random returns exact full output sequence under fixed seed with RNG state preservation.
4. pcie_eq/gui/random_data.py contains no imports of main.py or window.py (AST check).
"""

import ast
import pathlib
import numpy as np

from pcie_eq.gui import window, random_data


def test_random_data_function_location_and_reexport():
    """Verify pam4_symbols_from_random module location and backward-compatibility re-export."""
    assert random_data.pam4_symbols_from_random.__module__ == "pcie_eq.gui.random_data"
    assert window.pam4_symbols_from_random is random_data.pam4_symbols_from_random


def test_pam4_symbols_from_random_values():
    """Verify pam4_symbols_from_random produces exact sequence under fixed seed with RNG state preservation."""
    initial_state = np.random.get_state()
    try:
        np.random.seed(42)
        expected_first_10 = np.array([
            1.0 / 3.0, 1.0, -1.0, 1.0 / 3.0, 1.0 / 3.0,
            1.0, -1.0, -1.0, 1.0 / 3.0, -1.0 / 3.0
        ])

        np.random.seed(42)
        symbols = random_data.pam4_symbols_from_random(512)

        np.random.seed(42)
        repeat_symbols = random_data.pam4_symbols_from_random(512)

        assert len(symbols) == 512
        assert np.allclose(symbols[:10], expected_first_10)
        assert np.array_equal(symbols, repeat_symbols)

        valid_levels = {-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0}
        for sym in symbols:
            assert any(np.isclose(sym, v) for v in valid_levels), f"Unexpected PAM4 symbol: {sym}"
    finally:
        np.random.set_state(initial_state)

    final_state = np.random.get_state()
    assert initial_state[0] == final_state[0]
    assert np.array_equal(initial_state[1], final_state[1])
    assert initial_state[2:] == final_state[2:]


def test_random_data_ast_no_forbidden_imports():
    """AST check verifying pcie_eq/gui/random_data.py contains no imports of main.py or window.py."""
    data_path = pathlib.Path("pcie_eq/gui/random_data.py")
    tree = ast.parse(data_path.read_text(encoding="utf-8"))

    forbidden_modules = {"main", "pcie_eq.gui.window", "window"}
    found_forbidden = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_modules:
                    found_forbidden.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module in forbidden_modules:
                found_forbidden.add(node.module)

    assert not found_forbidden, f"pcie_eq/gui/random_data.py contains forbidden imports: {found_forbidden}"
