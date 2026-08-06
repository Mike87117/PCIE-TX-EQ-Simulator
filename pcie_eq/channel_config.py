"""
Channel Configuration Core Module for PCIe TX/RX EQ Simulator.

Provides unified GUI-independent ChannelConfig and ChannelResult APIs
for requesting and applying channel models to waveforms.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import math
import numpy as np

from pcie_eq.channel import simple_channel

CHANNEL_CONFIG_CONTRACT_ID = "pcie_eq-channel-config-v1"

__all__ = [
    "CHANNEL_CONFIG_CONTRACT_ID",
    "ChannelConfig",
    "ChannelResult",
    "apply_channel",
]

SUPPORTED_MODES = {"none", "legacy_lowpass"}
CANONICAL_KEYS = ["schema_version", "mode", "alpha"]


@dataclass(frozen=True)
class ChannelConfig:
    mode: str
    schema_version: str = CHANNEL_CONFIG_CONTRACT_ID
    alpha: int | float | None = None

    def _validate(self) -> None:
        if type(self.schema_version) is not str:
            raise TypeError(f"schema_version must be str, got {type(self.schema_version).__name__}")
        if self.schema_version != CHANNEL_CONFIG_CONTRACT_ID:
            raise ValueError(f"Unknown schema_version '{self.schema_version}', expected '{CHANNEL_CONFIG_CONTRACT_ID}'")

        if type(self.mode) is not str:
            raise TypeError(f"mode must be str, got {type(self.mode).__name__}")
        if self.mode not in SUPPORTED_MODES:
            raise ValueError(f"Unsupported mode '{self.mode}'")

        if self.mode == "none":
            if self.alpha is not None:
                raise ValueError("Field 'alpha' is not applicable for mode 'none'")
        elif self.mode == "legacy_lowpass":
            if self.alpha is not None:
                if type(self.alpha) not in (int, float):
                    raise TypeError(f"alpha must be int, float, or None, got {type(self.alpha).__name__}")
                flt_alpha = float(self.alpha)
                if math.isnan(flt_alpha) or math.isinf(flt_alpha):
                    raise ValueError(f"alpha must be finite, got {self.alpha}")

    def __post_init__(self) -> None:
        self._validate()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "alpha": self.alpha,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ChannelConfig":
        if not isinstance(data, Mapping):
            raise TypeError(f"data must be a Mapping, got {type(data).__name__}")

        data_keys = set(data.keys())
        expected_keys = set(CANONICAL_KEYS)
        if data_keys != expected_keys:
            missing = expected_keys - data_keys
            extra = data_keys - expected_keys
            msg_parts = []
            if missing:
                msg_parts.append(f"missing keys: {sorted(missing)}")
            if extra:
                msg_parts.append(f"extra keys: {sorted(extra)}")
            raise ValueError(f"Invalid dictionary keys ({', '.join(msg_parts)})")

        schema_version = data["schema_version"]
        if type(schema_version) is not str:
            raise TypeError(f"schema_version in dict must be str, got {type(schema_version).__name__}")
        if schema_version != CHANNEL_CONFIG_CONTRACT_ID:
            raise ValueError(f"Unknown schema_version '{schema_version}', expected '{CHANNEL_CONFIG_CONTRACT_ID}'")

        return cls(
            schema_version=schema_version,
            mode=data["mode"],
            alpha=data["alpha"],
        )


@dataclass(frozen=True)
class ChannelResult:
    values: np.ndarray
    resolved_config: ChannelConfig
    model_level: str


def apply_channel(wave, config: ChannelConfig) -> ChannelResult:
    if type(config) is not ChannelConfig:
        raise TypeError(f"config must be exactly ChannelConfig, got {type(config).__name__}")

    # Defensive re-validation of original config before wave materialization or processing
    config._validate()

    # Materialize and validate wave input
    try:
        arr = np.asarray(wave)
    except Exception as e:
        raise TypeError(f"Failed to convert wave input to ndarray: {e}") from e

    if arr.ndim != 1:
        raise ValueError(f"wave input must be 1D, got shape {arr.shape}")

    if arr.dtype.kind not in {"b", "i", "u", "f"}:
        raise TypeError(f"wave input dtype must be real numeric (bool, int, uint, float), got {arr.dtype}")

    if arr.size > 0 and not np.all(np.isfinite(arr)):
        raise ValueError("wave input elements must be finite")

    # Default resolution and resolved_config creation
    if config.mode == "none":
        resolved_alpha = None
        model_level = "identity"
    elif config.mode == "legacy_lowpass":
        resolved_alpha = float(config.alpha) if config.alpha is not None else 0.08
        model_level = "teaching_approximation"

    resolved_config = ChannelConfig(
        schema_version=config.schema_version,
        mode=config.mode,
        alpha=resolved_alpha,
    )

    # Computation / Delegation
    if config.mode == "none":
        values = np.array(arr, copy=True)
        if not values.flags.c_contiguous:
            values = np.ascontiguousarray(values)
    elif config.mode == "legacy_lowpass":
        values = simple_channel(wave, alpha=resolved_alpha)

    # Output verification against frozen contract (exact type check, no subclass)
    if type(values) is not np.ndarray:
        raise RuntimeError(f"Channel output is not exact np.ndarray: {type(values)}")
    if values.ndim != 1 or values.shape != (len(arr),):
        raise RuntimeError(f"Channel output shape mismatch: got {values.shape}, expected ({len(arr)},)")
    if not values.flags.c_contiguous:
        raise RuntimeError("Channel output is not C-contiguous")
    if values is arr or np.shares_memory(values, arr):
        raise RuntimeError("Channel output memory aliases caller input")
    if values.size > 0 and not np.all(np.isfinite(values)):
        raise RuntimeError("Channel output contains non-finite values")

    # Dtype contract check
    if config.mode == "none":
        if values.dtype != arr.dtype:
            raise RuntimeError(f"none mode dtype mismatch: got {values.dtype}, expected {arr.dtype}")
    elif config.mode == "legacy_lowpass":
        if arr.dtype.kind == "f":
            if values.dtype != arr.dtype:
                raise RuntimeError(f"legacy_lowpass mode float dtype mismatch: got {values.dtype}, expected {arr.dtype}")
        elif arr.dtype.kind in {"b", "i", "u"}:
            if values.dtype != np.float64:
                raise RuntimeError(f"legacy_lowpass mode integer/bool dtype mismatch: got {values.dtype}, expected float64")

    return ChannelResult(
        values=values,
        resolved_config=resolved_config,
        model_level=model_level,
    )
