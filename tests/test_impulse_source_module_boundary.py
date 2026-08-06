"""
Module boundary tests for pcie_eq.impulse_source core module.

Verifies:
1. pcie_eq/impulse_source.py exports exact __all__ surface in exact required order.
2. pcie_eq/impulse_source.py contains zero GUI, PyQt, PySide, pyqtgraph, main, models, channel, channel_config, impulse_convolution, or pipeline imports (AST check).
3. NumPy scalar values follow scalar dimensionality rejection.
4. Generated impulse outputs own independent storage.
"""

import ast
import pathlib

import numpy as np
import pytest

import pcie_eq.impulse_source as impulse_source


def test_impulse_source_exact_export_surface():
    """Verify pcie_eq.impulse_source exports exact __all__ in exact required order."""
    expected_all = [
        "IMPULSE_SOURCE_CONTRACT_ID",
        "ImpulseSourceConfig",
        "ImpulseSourceResult",
        "build_impulse",
    ]

    assert impulse_source.__all__ == expected_all
    for name in expected_all:
        assert hasattr(impulse_source, name), f"impulse_source module missing exported attribute: {name}"


def test_impulse_source_ast_no_forbidden_imports():
    """AST check verifying pcie_eq/impulse_source.py contains zero GUI, models, channel, pipeline, convolution, or main level imports."""
    config_path = pathlib.Path("pcie_eq/impulse_source.py")
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
        "pcie_eq.models",
        "pcie_eq.channel",
        "pcie_eq.channel_config",
        "pcie_eq.impulse_convolution",
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

    assert not found_forbidden, f"pcie_eq/impulse_source.py contains forbidden imports: {found_forbidden}"


def test_user_defined_numpy_scalars_use_dimensionality_rejection():
    """NumPy scalar inputs are scalars, so they must fail the 1D check with ValueError."""
    numpy_scalars = [
        np.bool_(True),
        np.int64(1),
        np.float64(1.0),
        np.complex128(1.0 + 0.0j),
    ]

    for scalar in numpy_scalars:
        with pytest.raises(ValueError, match="must be 1D"):
            impulse_source.ImpulseSourceConfig(
                source_type="user_defined",
                length=None,
                amplitude=None,
                decay_ratio=None,
                values=scalar,
            )


def test_generated_values_own_storage_and_shared_view_is_rejected(monkeypatch):
    """Normal sources own storage; a C-contiguous shared-memory helper view is rejected."""
    configs = [
        impulse_source.ImpulseSourceConfig(source_type="single_tap", length=2),
        impulse_source.ImpulseSourceConfig(
            source_type="exponential_postcursor",
            length=3,
            decay_ratio=0.5,
        ),
        impulse_source.ImpulseSourceConfig(
            source_type="user_defined",
            length=None,
            amplitude=None,
            decay_ratio=None,
            values=[1.0, 0.5],
        ),
    ]

    for config in configs:
        result = impulse_source.build_impulse(config)
        assert result.values.flags.owndata

    base = np.array([1.0, 2.0], dtype=np.float64)
    shared_view = base[:1]
    assert shared_view.flags.c_contiguous
    assert not shared_view.flags.owndata

    monkeypatch.setattr(
        impulse_source,
        "_build_values",
        lambda config, resolved_length: shared_view,
    )

    with pytest.raises(RuntimeError, match="own independent storage"):
        impulse_source.build_impulse(impulse_source.ImpulseSourceConfig())
