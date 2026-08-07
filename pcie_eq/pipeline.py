"""Unified simulation pipeline module."""

import numpy as np
from pcie_eq.models import (
    NrzSimulationConfig,
    Pam4SimulationConfig,
    NrzSimulationResult,
    Pam4SimulationResult,
)
from pcie_eq.tx_eq import tx_eq_levels, gen6_pam4_fir
from pcie_eq.channel_config import ChannelConfig, apply_channel
from pcie_eq.rx_eq import run_rx_pipeline
from pcie_eq.metrics import (
    calculate_nrz_eye_metrics,
    calculate_dfe_eye_metrics,
    calculate_pam4_eye_metrics,
)
from pcie_eq.sampling import validate_sampling_phase

__all__ = [
    "run_nrz_simulation",
    "run_pam4_simulation",
    "run_simulation",
]


def run_nrz_simulation(config: NrzSimulationConfig) -> NrzSimulationResult:
    """Execute the full NRZ simulation pipeline."""
    validate_sampling_phase(config.spb, config.sampling_phase)

    tx_symbols = tx_eq_levels(
        config.symbols, config.pre_db, config.de_db
    )
    tx_wave = np.repeat(tx_symbols, config.spb)
    channel_config = ChannelConfig(mode="legacy_lowpass", alpha=config.channel_alpha)
    ch_wave = apply_channel(tx_wave, channel_config).values

    rx_results = run_rx_pipeline(
        ch_wave,
        ctle_gain=config.ctle_gain,
        ctle_alpha=config.ctle_alpha,
        dfe_taps=config.dfe_taps,
        spb=config.spb,
        sampling_phase=config.sampling_phase,
    )

    ctle_wave = rx_results["ctle_wave"]
    dfe_input_samples = rx_results["dfe_input_samples"]
    dfe_corrected_samples = rx_results["dfe_corrected_samples"]
    dfe_decisions = rx_results["dfe_decisions"]

    channel_eye_metrics = calculate_nrz_eye_metrics(
        ch_wave,
        eye_ui=config.eye_ui,
        spb=config.spb,
        max_traces=config.max_traces,
        sampling_phase=config.sampling_phase,
    )
    ctle_eye_metrics = calculate_nrz_eye_metrics(
        ctle_wave,
        eye_ui=config.eye_ui,
        spb=config.spb,
        max_traces=config.max_traces,
        sampling_phase=config.sampling_phase,
    )
    dfe_eye_metrics = calculate_dfe_eye_metrics(
        dfe_corrected_samples, dfe_decisions, config.symbols, warmup_symbols=20
    )

    return NrzSimulationResult(
        tx_symbols=tx_symbols,
        tx_wave=tx_wave,
        ch_wave=ch_wave,
        ctle_wave=ctle_wave,
        dfe_input_samples=dfe_input_samples,
        dfe_corrected_samples=dfe_corrected_samples,
        dfe_decisions=dfe_decisions,
        channel_eye_metrics=channel_eye_metrics,
        ctle_eye_metrics=ctle_eye_metrics,
        dfe_eye_metrics=dfe_eye_metrics,
    )


def run_pam4_simulation(config: Pam4SimulationConfig) -> Pam4SimulationResult:
    """Execute the full PAM4 simulation pipeline."""
    tx_symbols, _ = gen6_pam4_fir(
        config.symbols,
        config.cm2,
        config.cm1,
        config.cp1,
    )
    tx_wave = np.repeat(tx_symbols, config.spb)
    channel_config = ChannelConfig(mode="legacy_lowpass", alpha=config.channel_alpha)
    ch_wave = apply_channel(tx_wave, channel_config).values

    t_center_phase, t_center_score, pam4_eye_metrics = calculate_pam4_eye_metrics(
        ch_wave, config.symbols, old_phase=config.old_phase, spb=config.spb
    )

    return Pam4SimulationResult(
        tx_symbols=tx_symbols,
        tx_wave=tx_wave,
        ch_wave=ch_wave,
        t_center_phase=t_center_phase,
        t_center_score=t_center_score,
        pam4_eye_metrics=pam4_eye_metrics,
    )


def run_simulation(config):
    """Dispatch simulation pipeline based on Config type."""
    if isinstance(config, NrzSimulationConfig):
        return run_nrz_simulation(config)
    elif isinstance(config, Pam4SimulationConfig):
        return run_pam4_simulation(config)
    else:
        raise TypeError(f"Unsupported simulation config type: {type(config)}")
