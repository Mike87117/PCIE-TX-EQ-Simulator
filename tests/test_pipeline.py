"""
Unit tests for pcie_eq.pipeline simulation APIs.

Verifies:
1. run_nrz_simulation produces NrzSimulationResult item-by-item matched against core APIs.
2. run_pam4_simulation produces Pam4SimulationResult item-by-item matched against core APIs.
3. run_simulation dispatches correctly based on Config type and raises TypeError for unsupported types.
4. PCIeTxEqSimulator GUI instantiation, full_refresh(), and pam4_full_refresh() execute without exceptions.
5. NRZ and PAM4 channel execution delegates exactly once through ChannelConfig/apply_channel.
"""

import sys
import pytest
import numpy as np
from PyQt5.QtWidgets import QApplication

import pcie_eq.pipeline as pipeline_module
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
from pcie_eq.tx_eq import tx_eq_levels, gen6_pam4_fir
from pcie_eq.channel_config import (
    CHANNEL_CONFIG_CONTRACT_ID,
    ChannelConfig,
    apply_channel,
)
from pcie_eq.rx_eq import run_rx_pipeline
from pcie_eq.metrics import (
    calculate_nrz_eye_metrics,
    calculate_dfe_eye_metrics,
    calculate_pam4_eye_metrics,
)


def test_run_nrz_simulation_item_by_item_contract():
    """Verify run_nrz_simulation outputs match item-by-item against individual core API calls."""
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

    # Independent composition through the public channel boundary.
    expected_tx_symbols = tx_eq_levels(config.symbols, config.pre_db, config.de_db)
    expected_tx_wave = np.repeat(expected_tx_symbols, config.spb)
    expected_ch_wave = apply_channel(
        expected_tx_wave,
        ChannelConfig(mode="legacy_lowpass", alpha=config.channel_alpha),
    ).values
    expected_rx = run_rx_pipeline(
        expected_ch_wave,
        ctle_gain=config.ctle_gain,
        ctle_alpha=config.ctle_alpha,
        dfe_taps=config.dfe_taps,
        spb=config.spb,
        sampling_phase=config.sampling_phase,
    )
    expected_channel_metrics = calculate_nrz_eye_metrics(
        expected_ch_wave, eye_ui=config.eye_ui, spb=config.spb, max_traces=config.max_traces
    )
    expected_ctle_metrics = calculate_nrz_eye_metrics(
        expected_rx["ctle_wave"], eye_ui=config.eye_ui, spb=config.spb, max_traces=config.max_traces
    )
    expected_dfe_metrics = calculate_dfe_eye_metrics(
        expected_rx["dfe_corrected_samples"], expected_rx["dfe_decisions"], config.symbols, warmup_symbols=20
    )

    assert isinstance(result, NrzSimulationResult)
    np.testing.assert_array_equal(result.tx_symbols, expected_tx_symbols)
    np.testing.assert_array_equal(result.tx_wave, expected_tx_wave)
    np.testing.assert_array_equal(result.ch_wave, expected_ch_wave)
    np.testing.assert_array_equal(result.ctle_wave, expected_rx["ctle_wave"])
    np.testing.assert_array_equal(result.dfe_input_samples, expected_rx["dfe_input_samples"])
    np.testing.assert_array_equal(result.dfe_corrected_samples, expected_rx["dfe_corrected_samples"])
    np.testing.assert_array_equal(result.dfe_decisions, expected_rx["dfe_decisions"])

    assert result.channel_eye_metrics == expected_channel_metrics
    assert result.ctle_eye_metrics == expected_ctle_metrics
    assert result.dfe_eye_metrics == expected_dfe_metrics


def test_run_pam4_simulation_item_by_item_contract():
    """Verify run_pam4_simulation outputs match item-by-item against individual core API calls."""
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

    # Independent composition through the public channel boundary.
    expected_tx_symbols, _ = gen6_pam4_fir(
        config.symbols, config.cm2, config.cm1, config.cp1
    )
    expected_tx_wave = np.repeat(expected_tx_symbols, config.spb)
    expected_ch_wave = apply_channel(
        expected_tx_wave,
        ChannelConfig(mode="legacy_lowpass", alpha=config.channel_alpha),
    ).values
    expected_phase, expected_score, expected_metrics = calculate_pam4_eye_metrics(
        expected_ch_wave, config.symbols, old_phase=config.old_phase, spb=config.spb
    )

    assert isinstance(result, Pam4SimulationResult)
    np.testing.assert_array_equal(result.tx_symbols, expected_tx_symbols)
    np.testing.assert_array_equal(result.tx_wave, expected_tx_wave)
    np.testing.assert_array_equal(result.ch_wave, expected_ch_wave)

    assert result.t_center_phase == expected_phase
    assert result.t_center_score == pytest.approx(expected_score)
    assert result.pam4_eye_metrics == expected_metrics


def test_nrz_pipeline_delegates_channel_once(monkeypatch):
    """NRZ pipeline must construct the frozen legacy ChannelConfig and delegate exactly once."""
    calls = []

    def spy_apply_channel(wave, channel_config):
        calls.append((wave, channel_config))
        return apply_channel(wave, channel_config)

    monkeypatch.setattr(pipeline_module, "apply_channel", spy_apply_channel)

    config = NrzSimulationConfig(
        symbols=np.tile([1.0, -1.0], 40),
        channel_alpha=0.123,
    )
    result = pipeline_module.run_nrz_simulation(config)

    assert isinstance(result, NrzSimulationResult)
    assert len(calls) == 1
    wave, channel_config = calls[0]
    assert isinstance(wave, np.ndarray)
    assert type(channel_config) is ChannelConfig
    assert channel_config.schema_version == CHANNEL_CONFIG_CONTRACT_ID
    assert channel_config.mode == "legacy_lowpass"
    assert channel_config.alpha == config.channel_alpha
    assert channel_config.impulse_source is None


def test_pam4_pipeline_delegates_channel_once(monkeypatch):
    """PAM4 pipeline must construct the frozen legacy ChannelConfig and delegate exactly once."""
    calls = []

    def spy_apply_channel(wave, channel_config):
        calls.append((wave, channel_config))
        return apply_channel(wave, channel_config)

    monkeypatch.setattr(pipeline_module, "apply_channel", spy_apply_channel)

    levels = np.array([-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0])
    config = Pam4SimulationConfig(
        symbols=np.tile(levels, 20),
        channel_alpha=0.117,
    )
    result = pipeline_module.run_pam4_simulation(config)

    assert isinstance(result, Pam4SimulationResult)
    assert len(calls) == 1
    wave, channel_config = calls[0]
    assert isinstance(wave, np.ndarray)
    assert type(channel_config) is ChannelConfig
    assert channel_config.schema_version == CHANNEL_CONFIG_CONTRACT_ID
    assert channel_config.mode == "legacy_lowpass"
    assert channel_config.alpha == config.channel_alpha
    assert channel_config.impulse_source is None


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


def test_gui_simulator_instantiation_and_refresh():
    """Verify PCIeTxEqSimulator instantiation and full refreshes execute without exceptions."""
    import main

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    win = main.PCIeTxEqSimulator()
    assert win is not None

    win.full_refresh()
    win.pam4_full_refresh()


def test_run_simulation_with_default_empty_configs():
    """
    Verify run_simulation tolerates the dataclass default empty symbol arrays
    and returns structurally valid empty result objects matching all contract requirements.
    """
    # NRZ default empty config
    nrz_cfg = NrzSimulationConfig()
    nrz_res = run_simulation(nrz_cfg)
    assert isinstance(nrz_res, NrzSimulationResult)

    nrz_array_fields = [
        "tx_symbols",
        "tx_wave",
        "ch_wave",
        "ctle_wave",
        "dfe_input_samples",
        "dfe_corrected_samples",
        "dfe_decisions",
    ]
    for name in nrz_array_fields:
        arr = getattr(nrz_res, name)
        assert isinstance(arr, np.ndarray), name
        assert arr.shape == (0,), name
        assert arr.dtype == np.float64, name

    expected_nrz_metric_keys = {
        "eye_height",
        "margin_5pct",
        "error_count",
        "eye_max",
        "eye_min",
        "center_spread",
    }
    for name in ("channel_eye_metrics", "ctle_eye_metrics", "dfe_eye_metrics"):
        metrics = getattr(nrz_res, name)
        assert isinstance(metrics, dict), name
        assert set(metrics.keys()) == expected_nrz_metric_keys, name
        assert metrics["eye_height"] == 0.0, name
        assert metrics["margin_5pct"] == 0.0, name
        assert metrics["error_count"] == 0, name
        assert isinstance(metrics["error_count"], int), name
        assert metrics["eye_max"] == 0.0, name
        assert metrics["eye_min"] == 0.0, name
        assert metrics["center_spread"] == 0.0, name

    # PAM4 default empty config
    pam4_cfg = Pam4SimulationConfig()
    pam4_res = run_simulation(pam4_cfg)
    assert isinstance(pam4_res, Pam4SimulationResult)

    pam4_array_fields = ["tx_symbols", "tx_wave", "ch_wave"]
    for name in pam4_array_fields:
        arr = getattr(pam4_res, name)
        assert isinstance(arr, np.ndarray), name
        assert arr.shape == (0,), name
        assert arr.dtype == np.float64, name

    assert pam4_res.t_center_phase == pam4_cfg.spb // 2
    assert pam4_res.t_center_phase == 16
    assert pam4_res.t_center_score == 0.0

    expected_pam4_metric_keys = {
        "upper_eye",
        "middle_eye",
        "lower_eye",
        "minimum_eye",
        "center_spread",
    }
    assert set(pam4_res.pam4_eye_metrics.keys()) == expected_pam4_metric_keys
    for k, v in pam4_res.pam4_eye_metrics.items():
        assert v == 0.0, k


def test_run_simulation_empty_does_not_disturb_global_rng():
    """Verify the empty-input path stays deterministic and preserves full legacy NumPy global RNG state."""
    before = np.random.get_state()
    try:
        run_simulation(NrzSimulationConfig())
        run_simulation(Pam4SimulationConfig())

        after = np.random.get_state()
        # Generator name
        assert before[0] == after[0]
        # State array
        np.testing.assert_array_equal(before[1], after[1])
        # Position, has_gauss, cached gaussian
        assert before[2] == after[2]
        assert before[3] == after[3]
        assert before[4] == after[4]
    finally:
        np.random.set_state(before)
