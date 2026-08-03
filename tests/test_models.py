"""
Tests for simulation configuration and result data models in pcie_eq.models.

Verifies:
1. Field names, type hints, and default values for all 4 models.
2. Explicit keyword argument construction.
3. Mutable default field isolation across instances.
"""

import typing
import pytest
import numpy as np
from pcie_eq.models import (
    NrzSimulationConfig,
    Pam4SimulationConfig,
    NrzSimulationResult,
    Pam4SimulationResult,
)


def test_nrz_simulation_config_field_contract_and_defaults():
    """Verify NrzSimulationConfig field list, type hints, and default values."""
    hints = typing.get_type_hints(NrzSimulationConfig)
    expected_fields = [
        "symbols",
        "spb",
        "pre_db",
        "de_db",
        "channel_alpha",
        "ctle_gain",
        "ctle_alpha",
        "dfe_taps",
        "sampling_phase",
        "max_traces",
        "eye_ui",
    ]
    assert list(hints.keys()) == expected_fields
    assert hints["dfe_taps"] == list[float]

    cfg = NrzSimulationConfig()
    assert isinstance(cfg.symbols, np.ndarray)
    assert cfg.symbols.size == 0
    assert cfg.spb == 32
    assert cfg.pre_db == 1.5
    assert cfg.de_db == -3.5
    assert cfg.channel_alpha == 0.08
    assert cfg.ctle_gain == 0.0
    assert cfg.ctle_alpha == 0.08
    assert cfg.dfe_taps == [0.0, 0.0, 0.0]
    assert cfg.sampling_phase == 16
    assert cfg.max_traces == 200
    assert cfg.eye_ui == 2


def test_nrz_simulation_config_explicit():
    """Verify NrzSimulationConfig construction with explicit values."""
    syms = np.array([1.0, -1.0, 1.0])
    cfg = NrzSimulationConfig(
        symbols=syms,
        spb=16,
        pre_db=2.0,
        de_db=-6.0,
        channel_alpha=0.12,
        ctle_gain=2.0,
        ctle_alpha=0.05,
        dfe_taps=[0.1, 0.05, -0.02],
        sampling_phase=8,
        max_traces=100,
        eye_ui=1,
    )
    np.testing.assert_array_equal(cfg.symbols, syms)
    assert cfg.spb == 16
    assert cfg.pre_db == 2.0
    assert cfg.de_db == -6.0
    assert cfg.channel_alpha == 0.12
    assert cfg.ctle_gain == 2.0
    assert cfg.ctle_alpha == 0.05
    assert cfg.dfe_taps == [0.1, 0.05, -0.02]
    assert cfg.sampling_phase == 8
    assert cfg.max_traces == 100
    assert cfg.eye_ui == 1


def test_pam4_simulation_config_field_contract_and_defaults():
    """Verify Pam4SimulationConfig field list, type hints, and default values."""
    hints = typing.get_type_hints(Pam4SimulationConfig)
    expected_fields = [
        "symbols",
        "spb",
        "cm2",
        "cm1",
        "cp1",
        "channel_alpha",
        "old_phase",
        "eye_ui",
    ]
    assert list(hints.keys()) == expected_fields

    cfg_default = Pam4SimulationConfig()
    assert isinstance(cfg_default.symbols, np.ndarray)
    assert cfg_default.symbols.size == 0
    assert cfg_default.spb == 32
    assert cfg_default.cm2 == 0.0
    assert cfg_default.cm1 == 0.0
    assert cfg_default.cp1 == 0.0
    assert cfg_default.channel_alpha == 0.08
    assert cfg_default.old_phase == 16
    assert cfg_default.eye_ui == 2

    syms = np.array([1.0, 1 / 3, -1 / 3, -1.0])
    cfg_explicit = Pam4SimulationConfig(
        symbols=syms,
        spb=64,
        cm2=0.042,
        cm1=-0.208,
        cp1=0.0,
        channel_alpha=0.05,
        old_phase=12,
        eye_ui=2,
    )
    np.testing.assert_array_equal(cfg_explicit.symbols, syms)
    assert cfg_explicit.spb == 64
    assert cfg_explicit.cm2 == 0.042
    assert cfg_explicit.cm1 == -0.208
    assert cfg_explicit.cp1 == 0.0
    assert cfg_explicit.channel_alpha == 0.05
    assert cfg_explicit.old_phase == 12


def test_nrz_simulation_result_field_contract_and_defaults():
    """Verify NrzSimulationResult field list, type hints, and default values."""
    hints = typing.get_type_hints(NrzSimulationResult)
    expected_fields = [
        "tx_symbols",
        "tx_wave",
        "ch_wave",
        "ctle_wave",
        "dfe_input_samples",
        "dfe_corrected_samples",
        "dfe_decisions",
        "channel_eye_metrics",
        "ctle_eye_metrics",
        "dfe_eye_metrics",
    ]
    assert list(hints.keys()) == expected_fields
    assert hints["channel_eye_metrics"] == dict[str, float | int]
    assert hints["ctle_eye_metrics"] == dict[str, float | int]
    assert hints["dfe_eye_metrics"] == dict[str, float | int]

    res_default = NrzSimulationResult()
    assert isinstance(res_default.tx_symbols, np.ndarray)
    assert isinstance(res_default.tx_wave, np.ndarray)
    assert isinstance(res_default.ch_wave, np.ndarray)
    assert isinstance(res_default.ctle_wave, np.ndarray)
    assert isinstance(res_default.dfe_input_samples, np.ndarray)
    assert isinstance(res_default.dfe_corrected_samples, np.ndarray)
    assert isinstance(res_default.dfe_decisions, np.ndarray)
    assert res_default.channel_eye_metrics == {}
    assert res_default.ctle_eye_metrics == {}
    assert res_default.dfe_eye_metrics == {}

    wave = np.array([0.0, 1.0, 0.5])
    ch_metrics = {"eye_height": 1.2, "margin_5pct": 0.6}
    ctle_metrics = {"eye_height": 1.8, "margin_5pct": 0.9}
    dfe_metrics = {"eye_height": 1.6, "error_count": 0}
    res_explicit = NrzSimulationResult(
        tx_wave=wave,
        ch_wave=wave,
        channel_eye_metrics=ch_metrics,
        ctle_eye_metrics=ctle_metrics,
        dfe_eye_metrics=dfe_metrics,
    )
    np.testing.assert_array_equal(res_explicit.tx_wave, wave)
    assert res_explicit.channel_eye_metrics == ch_metrics
    assert res_explicit.ctle_eye_metrics == ctle_metrics
    assert res_explicit.dfe_eye_metrics == dfe_metrics


def test_pam4_simulation_result_field_contract_and_defaults():
    """Verify Pam4SimulationResult field list, type hints, and default values."""
    hints = typing.get_type_hints(Pam4SimulationResult)
    expected_fields = [
        "tx_symbols",
        "tx_wave",
        "ch_wave",
        "t_center_phase",
        "t_center_score",
        "pam4_eye_metrics",
    ]
    assert list(hints.keys()) == expected_fields
    assert hints["pam4_eye_metrics"] == dict[str, float]

    res_default = Pam4SimulationResult()
    assert isinstance(res_default.tx_symbols, np.ndarray)
    assert isinstance(res_default.tx_wave, np.ndarray)
    assert isinstance(res_default.ch_wave, np.ndarray)
    assert res_default.t_center_phase == 16
    assert res_default.t_center_score == 0.0
    assert res_default.pam4_eye_metrics == {}

    metrics = {"minimum_eye": 0.6667}
    res_explicit = Pam4SimulationResult(
        t_center_phase=8,
        t_center_score=0.6667,
        pam4_eye_metrics=metrics,
    )
    assert res_explicit.t_center_phase == 8
    assert res_explicit.t_center_score == 0.6667
    assert res_explicit.pam4_eye_metrics == metrics


def test_mutable_default_isolation():
    """Verify mutable default fields (lists, dicts, numpy arrays) are isolated per instance."""
    cfg1 = NrzSimulationConfig()
    cfg2 = NrzSimulationConfig()

    cfg1.dfe_taps.append(0.5)
    assert cfg2.dfe_taps == [0.0, 0.0, 0.0]
    assert cfg1.dfe_taps is not cfg2.dfe_taps
    assert cfg1.symbols is not cfg2.symbols

    res1 = NrzSimulationResult()
    res2 = NrzSimulationResult()

    res1.channel_eye_metrics["eye_height"] = 2.0
    res1.ctle_eye_metrics["eye_height"] = 2.0
    res1.dfe_eye_metrics["eye_height"] = 2.0
    assert res2.channel_eye_metrics == {}
    assert res2.ctle_eye_metrics == {}
    assert res2.dfe_eye_metrics == {}
    assert res1.channel_eye_metrics is not res2.channel_eye_metrics
    assert res1.ctle_eye_metrics is not res2.ctle_eye_metrics
    assert res1.dfe_eye_metrics is not res2.dfe_eye_metrics
    assert res1.tx_wave is not res2.tx_wave

    pam_res1 = Pam4SimulationResult()
    pam_res2 = Pam4SimulationResult()
    pam_res1.pam4_eye_metrics["minimum_eye"] = 0.5
    assert pam_res2.pam4_eye_metrics == {}
    assert pam_res1.pam4_eye_metrics is not pam_res2.pam4_eye_metrics
