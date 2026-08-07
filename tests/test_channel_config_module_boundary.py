"""
Module boundary and frozen-contract guard tests for pcie_eq.channel_config.

Verifies:
1. pcie_eq/channel_config.py exports exact __all__ surface in exact required order.
2. pcie_eq/channel_config.py contains zero GUI, PyQt, PySide, pyqtgraph, main, models, or pipeline imports (AST check).
3. Round-3 Merge Gate guards: pre-wave defensive source snapshot, serialization relevance order, and complete schema/mode relevance matrix.
"""

import ast
import pathlib

import numpy as np
import pytest

import pcie_eq.channel_config as channel_config
from pcie_eq.channel_config import (
    CHANNEL_CONFIG_CONTRACT_ID,
    LEGACY_CHANNEL_CONFIG_CONTRACT_ID,
    ChannelConfig,
    apply_channel,
)
from pcie_eq.impulse_source import ImpulseSourceConfig


def test_channel_config_exact_export_surface():
    """Verify pcie_eq.channel_config exports exact __all__ in exact required order."""
    expected_all = [
        "CHANNEL_CONFIG_CONTRACT_ID",
        "LEGACY_CHANNEL_CONFIG_CONTRACT_ID",
        "ChannelConfig",
        "ChannelResult",
        "apply_channel",
    ]

    assert channel_config.__all__ == expected_all
    for name in expected_all:
        assert hasattr(channel_config, name), f"channel_config module missing exported attribute: {name}"

    assert channel_config.CHANNEL_CONFIG_CONTRACT_ID == "pcie_eq-channel-config-v2"
    assert channel_config.LEGACY_CHANNEL_CONFIG_CONTRACT_ID == "pcie_eq-channel-config-v1"


def test_channel_config_ast_no_forbidden_gui_models_or_pipeline_imports():
    """AST check verifying pcie_eq/channel_config.py contains zero GUI, models, pipeline, or main level imports."""
    config_path = pathlib.Path("pcie_eq/channel_config.py")
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

    assert not found_forbidden, f"pcie_eq/channel_config.py contains forbidden imports: {found_forbidden}"


def test_impulse_defensive_snapshot_is_captured_before_wave_materialization(monkeypatch):
    """Wave materialization must not be able to alter the source later delegated to build_impulse()."""
    caller_source = ImpulseSourceConfig(length=3, impulse_zero_index=0, amplitude=2.0)
    cfg = ChannelConfig(mode="impulse_response", impulse_source=caller_source)

    build_sources = []
    original_build = channel_config.build_impulse

    def tracking_build(source):
        build_sources.append(source)
        return original_build(source)

    monkeypatch.setattr(channel_config, "build_impulse", tracking_build)

    class MutatingWave:
        def __array__(self, dtype=None, copy=None):
            object.__setattr__(caller_source, "amplitude", 999.0)
            values = np.array([1.0, 0.0], dtype=np.float64)
            if dtype is not None:
                values = values.astype(dtype, copy=False)
            return values

    result = apply_channel(MutatingWave(), cfg)

    assert caller_source.amplitude == 999.0
    assert len(build_sources) == 1
    assert build_sources[0] is not caller_source
    assert build_sources[0].amplitude == 2.0
    assert result.resolved_config.impulse_source is not caller_source
    assert result.resolved_config.impulse_source.amplitude == 2.0
    assert np.array_equal(result.values, np.array([2.0, 0.0], dtype=np.float64))


def test_from_dict_impulse_alpha_rejected_before_nested_source_parsing():
    """Irrelevant impulse alpha must win before malformed nested source parsing is attempted."""
    data = {
        "schema_version": CHANNEL_CONFIG_CONTRACT_ID,
        "mode": "impulse_response",
        "alpha": 0.08,
        "impulse_source": "this would fail nested source parsing",
    }

    with pytest.raises(ValueError, match="Field 'alpha' is not applicable for mode 'impulse_response'"):
        ChannelConfig.from_dict(data)


def test_channel_config_complete_schema_mode_relevance_matrix():
    """Explicitly cover alpha/impulse_source relevance for every supported schema/mode."""
    source = ImpulseSourceConfig()

    for schema in (LEGACY_CHANNEL_CONFIG_CONTRACT_ID, CHANNEL_CONFIG_CONTRACT_ID):
        none_cfg = ChannelConfig(mode="none", schema_version=schema)
        assert none_cfg.alpha is None
        assert none_cfg.impulse_source is None

        with pytest.raises(ValueError, match="alpha.*not applicable"):
            ChannelConfig(mode="none", schema_version=schema, alpha=0.08)
        with pytest.raises(ValueError, match="impulse_source.*not applicable"):
            ChannelConfig(mode="none", schema_version=schema, impulse_source=source)

        lowpass_cfg = ChannelConfig(mode="legacy_lowpass", schema_version=schema, alpha=0.08)
        assert lowpass_cfg.alpha == 0.08
        assert lowpass_cfg.impulse_source is None

        with pytest.raises(ValueError, match="impulse_source.*not applicable"):
            ChannelConfig(mode="legacy_lowpass", schema_version=schema, impulse_source=source)

    impulse_cfg = ChannelConfig(
        mode="impulse_response",
        schema_version=CHANNEL_CONFIG_CONTRACT_ID,
        impulse_source=source,
    )
    assert impulse_cfg.alpha is None
    assert impulse_cfg.impulse_source is source

    with pytest.raises(ValueError, match="alpha.*not applicable"):
        ChannelConfig(
            mode="impulse_response",
            schema_version=CHANNEL_CONFIG_CONTRACT_ID,
            alpha=0.08,
            impulse_source=source,
        )
    with pytest.raises(ValueError, match="impulse_source.*required"):
        ChannelConfig(mode="impulse_response", schema_version=CHANNEL_CONFIG_CONTRACT_ID)
    with pytest.raises(ValueError, match="Unsupported mode 'impulse_response'"):
        ChannelConfig(
            mode="impulse_response",
            schema_version=LEGACY_CHANNEL_CONFIG_CONTRACT_ID,
            impulse_source=source,
        )
