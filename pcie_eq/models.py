"""Simulation configuration and result data models."""

from dataclasses import dataclass, field
import numpy as np

__all__ = [
    "NrzSimulationConfig",
    "Pam4SimulationConfig",
    "NrzSimulationResult",
    "Pam4SimulationResult",
]


@dataclass
class NrzSimulationConfig:
    """Core parameters for NRZ signal simulation pipeline."""
    symbols: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    spb: int = 32
    cm1: float = 0.0
    cp1: float = 0.0
    pre_db: float = 0.0
    de_db: float = 0.0
    channel_alpha: float = 0.08
    ctle_gain: float = 0.0
    ctle_alpha: float = 0.08
    dfe_taps: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    sampling_phase: int = 0
    max_traces: int = 200
    eye_ui: int = 2


@dataclass
class Pam4SimulationConfig:
    """Core parameters for PAM4 signal simulation pipeline."""
    symbols: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    spb: int = 32
    cm2: float = 0.0
    cm1: float = 0.0
    cp1: float = 0.0
    channel_alpha: float = 0.08
    old_phase: int = 16
    eye_ui: int = 2


@dataclass
class NrzSimulationResult:
    """Outputs produced by NRZ signal simulation pipeline."""
    tx_symbols: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    tx_wave: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    ch_wave: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    ctle_wave: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    dfe_input_samples: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    dfe_corrected_samples: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    dfe_decisions: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    eye_metrics: dict = field(default_factory=dict)


@dataclass
class Pam4SimulationResult:
    """Outputs produced by PAM4 signal simulation pipeline."""
    tx_symbols: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    tx_wave: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    ch_wave: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    t_center_phase: int = 16
    t_center_score: float = 0.0
    pam4_eye_metrics: dict = field(default_factory=dict)
