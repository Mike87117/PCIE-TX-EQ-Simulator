"""
Unit tests for pcie_eq.pipeline simulation APIs.

Verifies:
1. run_nrz_simulation produces valid NrzSimulationResult with 3 sets of metrics.
2. run_pam4_simulation produces valid Pam4SimulationResult with t_center phase/score and eye metrics.
3. run_simulation dispatches correctly based on Config type and raises TypeError for unsupported types.
"""

import pytest
import numpy as np
from pcie_eq.models import (
    NrzSimulationConfig,
    Pam4SimulationConfig,
    NrzSimulationResult,
    Pam4SimulationResult,
)
from pcie_eq.pipeline import (
    run_nrz_simulation,
    run_pam4_simulation,
    run_simulation,
)


def test_run_nrz_simulation_basic():
    """Verify run_nrz_simulation executes full pipeline and produces expected NrzSimulationResult."""
    symbols = np.tile([1.0, -1.0], 50)
    config = NrzSimulationConfig(
        symbols=symbols,
        spb=32,
        pre_db=1.5,
        de_db=-3.5,
        channel_alpha=0.08,
        ctle_gain=1.0,
        ctle_alpha=0.08,
        dfe_taps=[0.05, -0.02, 0.01],
        sampling_phase=16,
        max_traces=200,
        eye_ui=2,
    )

    result = run_nrz_simulation(config)

    assert isinstance(result, NrzSimulationResult)
    assert len(result.tx_symbols) == len(symbols)
    assert len(result.tx_wave) == len(symbols) * 32
    assert len(result.ch_wave) == len(symbols) * 32
    assert len(result.ctle_wave) == len(symbols) * 32
    assert len(result.dfe_input_samples) == len(symbols)
    assert len(result.dfe_corrected_samples) == len(symbols)
    assert len(result.dfe_decisions) == len(symbols)

    assert "eye_height" in result.channel_eye_metrics
    assert "eye_height" in result.ctle_eye_metrics
    assert "margin_5pct" in result.dfe_eye_metrics
    assert result.dfe_eye_metrics["error_count"] == 0


def test_run_pam4_simulation_basic():
    """Verify run_pam4_simulation executes full pipeline and produces expected Pam4SimulationResult."""
    pam4_levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])
    symbols = np.tile(pam4_levels, 25)
    config = Pam4SimulationConfig(
        symbols=symbols,
        spb=32,
        cm2=0.0,
        cm1=-0.1,
        cp1=0.0,
        channel_alpha=0.08,
        old_phase=16,
        eye_ui=2,
    )

    result = run_pam4_simulation(config)

    assert isinstance(result, Pam4SimulationResult)
    assert len(result.tx_symbols) == len(symbols)
    assert len(result.tx_wave) == len(symbols) * 32
    assert len(result.ch_wave) == len(symbols) * 32
    assert 0 <= result.t_center_phase < 32
    assert result.t_center_score > 0.0
    assert "minimum_eye" in result.pam4_eye_metrics


def test_run_simulation_dispatcher():
    """Verify run_simulation dispatches Nrz and Pam4 configs and rejects invalid types."""
    nrz_config = NrzSimulationConfig(symbols=np.tile([1.0, -1.0], 20))
    nrz_res = run_simulation(nrz_config)
    assert isinstance(nrz_res, NrzSimulationResult)

    pam4_levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])
    pam4_config = Pam4SimulationConfig(symbols=np.tile(pam4_levels, 10))
    pam4_res = run_simulation(pam4_config)
    assert isinstance(pam4_res, Pam4SimulationResult)

    with pytest.raises(TypeError, match="Unsupported simulation config type"):
        run_simulation("not_a_config_object")
