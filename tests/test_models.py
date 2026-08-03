"""
Tests for simulation configuration and result data models in pcie_eq.models.

Verifies:
1. Default instantiation values for all 4 models.
2. Explicit keyword argument construction.
3. Mutable default field isolation across instances.
"""

import pytest
import numpy as np
from pcie_eq.models import (
    NrzSimulationConfig,
    Pam4SimulationConfig,
    NrzSimulationResult,
    Pam4SimulationResult,
)


def test_nrz_simulation_config_defaults():
    """Verify default values of NrzSimulationConfig."""
    cfg = NrzSimulationConfig()
    assert isinstance(cfg.symbols, np.ndarray)
    assert cfg.symbols.size == 0
    assert cfg.spb == 32
    assert cfg.cm1 == 0.0
    assert cfg.cp1 == 0.0
    assert cfg.pre_db == 0.0
    assert cfg.de_db == 0.0
    assert cfg.channel_alpha == 0.08
    assert cfg.ctle_gain == 0.0
    assert cfg.ctle_alpha == 0.08
    assert cfg.dfe_taps == [0.0, 0.0, 0.0]
    assert cfg.sampling_phase == 0
    assert cfg.max_traces == 200
    assert cfg.eye_ui == 2


def test_nrz_simulation_config_explicit():
    """Verify NrzSimulationConfig construction with explicit values."""
    syms = np.array([1.0, -1.0, 1.0])
    cfg = NrzSimulationConfig(
        symbols=syms,
        spb=16,
        cm1=-0.1,
        cp1=-0.2,
        pre_db=1.5,
        de_db=-3.5,
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
    assert cfg.cm1 == -0.1
    assert cfg.cp1 == -0.2
    assert cfg.pre_db == 1.5
    assert cfg.de_db == -3.5
    assert cfg.channel_alpha == 0.12
    assert cfg.ctle_gain == 2.0
    assert cfg.ctle_alpha == 0.05
    assert cfg.dfe_taps == [0.1, 0.05, -0.02]
    assert cfg.sampling_phase == 8
    assert cfg.max_traces == 100
    assert cfg.eye_ui == 1


def test_pam4_simulation_config_defaults_and_explicit():
    """Verify Pam4SimulationConfig defaults and explicit construction."""
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


def test_nrz_simulation_result_defaults_and_explicit():
    """Verify NrzSimulationResult defaults and explicit construction."""
    res_default = NrzSimulationResult()
    assert isinstance(res_default.tx_symbols, np.ndarray)
    assert isinstance(res_default.tx_wave, np.ndarray)
    assert isinstance(res_default.ch_wave, np.ndarray)
    assert isinstance(res_default.ctle_wave, np.ndarray)
    assert isinstance(res_default.dfe_input_samples, np.ndarray)
    assert isinstance(res_default.dfe_corrected_samples, np.ndarray)
    assert isinstance(res_default.dfe_decisions, np.ndarray)
    assert res_default.eye_metrics == {}

    wave = np.array([0.0, 1.0, 0.5])
    metrics = {"eye_height": 1.5, "margin_5pct": 0.75}
    res_explicit = NrzSimulationResult(
        tx_wave=wave,
        ch_wave=wave,
        eye_metrics=metrics,
    )
    np.testing.assert_array_equal(res_explicit.tx_wave, wave)
    assert res_explicit.eye_metrics == metrics


def test_pam4_simulation_result_defaults_and_explicit():
    """Verify Pam4SimulationResult defaults and explicit construction."""
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

    res1.eye_metrics["eye_height"] = 2.0
    assert res2.eye_metrics == {}
    assert res1.eye_metrics is not res2.eye_metrics
    assert res1.tx_wave is not res2.tx_wave

    pam_res1 = Pam4SimulationResult()
    pam_res2 = Pam4SimulationResult()
    pam_res1.pam4_eye_metrics["minimum_eye"] = 0.5
    assert pam_res2.pam4_eye_metrics == {}
    assert pam_res1.pam4_eye_metrics is not pam_res2.pam4_eye_metrics
