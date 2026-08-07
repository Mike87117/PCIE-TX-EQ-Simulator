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
from pcie_eq.impulse_convolution import (
    ImpulseConvolutionConfig,
    ImpulseConvolutionResult,
    convolve_impulse,
)
from pcie_eq.impulse_source import (
    ImpulseSourceConfig,
    ImpulseSourceResult,
    build_impulse,
    _validate_canonical_config as _validate_canonical_source_config,
)

CHANNEL_CONFIG_CONTRACT_ID = "pcie_eq-channel-config-v2"
LEGACY_CHANNEL_CONFIG_CONTRACT_ID = "pcie_eq-channel-config-v1"

__all__ = [
    "CHANNEL_CONFIG_CONTRACT_ID",
    "LEGACY_CHANNEL_CONFIG_CONTRACT_ID",
    "ChannelConfig",
    "ChannelResult",
    "apply_channel",
]

SUPPORTED_SCHEMAS = {CHANNEL_CONFIG_CONTRACT_ID, LEGACY_CHANNEL_CONFIG_CONTRACT_ID}
V1_MODES = {"none", "legacy_lowpass"}
V2_MODES = {"none", "legacy_lowpass", "impulse_response"}

V1_CANONICAL_KEYS = ["schema_version", "mode", "alpha"]
V2_CANONICAL_KEYS = ["schema_version", "mode", "alpha", "impulse_source"]


@dataclass(frozen=True)
class ChannelConfig:
    mode: str
    schema_version: str = CHANNEL_CONFIG_CONTRACT_ID
    alpha: int | float | None = None
    impulse_source: ImpulseSourceConfig | None = None

    def _validate(self) -> None:
        # 1. schema_version
        if type(self.schema_version) is not str:
            raise TypeError(f"schema_version must be str, got {type(self.schema_version).__name__}")
        if self.schema_version not in SUPPORTED_SCHEMAS:
            raise ValueError(
                f"Unknown schema_version '{self.schema_version}', expected one of {sorted(SUPPORTED_SCHEMAS)}"
            )

        # 2. mode
        if type(self.mode) is not str:
            raise TypeError(f"mode must be str, got {type(self.mode).__name__}")

        if self.schema_version == LEGACY_CHANNEL_CONFIG_CONTRACT_ID:
            if self.mode not in V1_MODES:
                raise ValueError(
                    f"Unsupported mode '{self.mode}' for schema '{LEGACY_CHANNEL_CONFIG_CONTRACT_ID}'"
                )
        elif self.schema_version == CHANNEL_CONFIG_CONTRACT_ID:
            if self.mode not in V2_MODES:
                raise ValueError(
                    f"Unsupported mode '{self.mode}' for schema '{CHANNEL_CONFIG_CONTRACT_ID}'"
                )

        # 3. Mode-specific field relevance & validation
        if self.mode == "none":
            if self.alpha is not None:
                raise ValueError("Field 'alpha' is not applicable for mode 'none'")
            if self.impulse_source is not None:
                raise ValueError("Field 'impulse_source' is not applicable for mode 'none'")

        elif self.mode == "legacy_lowpass":
            if self.impulse_source is not None:
                raise ValueError("Field 'impulse_source' is not applicable for mode 'legacy_lowpass'")
            if self.alpha is not None:
                if type(self.alpha) not in (int, float):
                    raise TypeError(f"alpha must be int, float, or None, got {type(self.alpha).__name__}")
                flt_alpha = float(self.alpha)
                if math.isnan(flt_alpha) or math.isinf(flt_alpha):
                    raise ValueError(f"alpha must be finite, got {self.alpha}")

        elif self.mode == "impulse_response":
            if self.alpha is not None:
                raise ValueError("Field 'alpha' is not applicable for mode 'impulse_response'")
            if self.impulse_source is None:
                raise ValueError("Field 'impulse_source' is required for mode 'impulse_response'")
            if type(self.impulse_source) is not ImpulseSourceConfig:
                raise TypeError(
                    f"impulse_source must be exactly ImpulseSourceConfig, got {type(self.impulse_source).__name__}"
                )

            # Defensively re-validate nested frozen source config without repair
            _validate_canonical_source_config(self.impulse_source)

            # Integration v1 requires sample_interval == 1.0
            if self.impulse_source.sample_interval != 1.0:
                raise ValueError(
                    f"Integration v1 accepts only sample_interval == 1.0, got {self.impulse_source.sample_interval}"
                )

    def __post_init__(self) -> None:
        self._validate()

    def to_dict(self) -> dict[str, object]:
        if self.schema_version == LEGACY_CHANNEL_CONFIG_CONTRACT_ID:
            return {
                "schema_version": self.schema_version,
                "mode": self.mode,
                "alpha": self.alpha,
            }
        else:
            return {
                "schema_version": self.schema_version,
                "mode": self.mode,
                "alpha": self.alpha,
                "impulse_source": self.impulse_source.to_dict() if self.impulse_source is not None else None,
            }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ChannelConfig":
        if not isinstance(data, Mapping):
            raise TypeError(f"data must be a Mapping, got {type(data).__name__}")

        if "schema_version" not in data:
            raise ValueError("missing keys: ['schema_version']")

        schema_version = data["schema_version"]
        if type(schema_version) is not str:
            raise TypeError(f"schema_version in dict must be str, got {type(schema_version).__name__}")
        if schema_version not in SUPPORTED_SCHEMAS:
            raise ValueError(
                f"Unknown schema_version '{schema_version}', expected one of {sorted(SUPPORTED_SCHEMAS)}"
            )

        data_keys = set(data.keys())
        if schema_version == LEGACY_CHANNEL_CONFIG_CONTRACT_ID:
            expected_keys = set(V1_CANONICAL_KEYS)
        else:
            expected_keys = set(V2_CANONICAL_KEYS)

        if data_keys != expected_keys:
            missing = expected_keys - data_keys
            extra = data_keys - expected_keys
            msg_parts = []
            if missing:
                msg_parts.append(f"missing keys: {sorted(missing)}")
            if extra:
                msg_parts.append(f"extra keys: {sorted(extra)}")
            raise ValueError(f"Invalid dictionary keys ({', '.join(msg_parts)})")

        if schema_version == LEGACY_CHANNEL_CONFIG_CONTRACT_ID:
            impulse_source = None
        else:
            raw_source = data["impulse_source"]
            if raw_source is None:
                impulse_source = None
            else:
                impulse_source = ImpulseSourceConfig.from_dict(raw_source)

        return cls(
            schema_version=schema_version,
            mode=data["mode"],
            alpha=data["alpha"],
            impulse_source=impulse_source,
        )


@dataclass(frozen=True)
class ChannelResult:
    values: np.ndarray
    resolved_config: ChannelConfig
    model_level: str


def apply_channel(wave, config: ChannelConfig) -> ChannelResult:
    # 1. Require exact ChannelConfig type
    if type(config) is not ChannelConfig:
        raise TypeError(f"config must be exactly ChannelConfig, got {type(config).__name__}")

    # 2-5. Defensive re-validation of config (schema, mode, relevance, nested source, sample_interval)
    config._validate()

    # 6. Materialize and validate wave input
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

    # 7-8. Mode dispatch
    if config.mode == "none":
        resolved_alpha = None
        resolved_source = None
        model_level = "identity"
        values = np.array(arr, copy=True)
        if not values.flags.c_contiguous:
            values = np.ascontiguousarray(values)

    elif config.mode == "legacy_lowpass":
        resolved_alpha = float(config.alpha) if config.alpha is not None else 0.08
        resolved_source = None
        model_level = "teaching_approximation"
        values = simple_channel(wave, alpha=resolved_alpha)

    elif config.mode == "impulse_response":
        resolved_alpha = None
        model_level = "project_owned_discrete_impulse_channel"

        # Step 8: Call build_impulse exactly once
        source_result = build_impulse(config.impulse_source)

        # Step 9: Validate exact ImpulseSourceResult child boundary
        if type(source_result) is not ImpulseSourceResult:
            raise RuntimeError(f"source result is not ImpulseSourceResult: {type(source_result)}")
        if type(source_result.resolved_config) is not ImpulseSourceConfig:
            raise RuntimeError(f"source resolved_config is not ImpulseSourceConfig: {type(source_result.resolved_config)}")
        if source_result.model_level != "project_owned_discrete_impulse_source":
            raise RuntimeError(f"source model_level mismatch: got '{source_result.model_level}'")
        if type(source_result.values) is not np.ndarray:
            raise RuntimeError(f"source values is not exact np.ndarray: {type(source_result.values)}")
        if source_result.values.dtype != np.float64:
            raise RuntimeError(f"source values dtype mismatch: got {source_result.values.dtype}")
        if source_result.values.ndim != 1:
            raise RuntimeError(f"source values is not 1D: shape {source_result.values.shape}")
        if not source_result.values.flags.c_contiguous:
            raise RuntimeError("source values is not C-contiguous")
        if not np.all(np.isfinite(source_result.values)):
            raise RuntimeError("source values contains non-finite elements")
        if source_result.resolved_config.sample_interval != 1.0:
            raise RuntimeError(f"source resolved sample_interval mismatch: {source_result.resolved_config.sample_interval}")

        # Check source length against resolved_config
        if source_result.resolved_config.source_type in ("single_tap", "exponential_postcursor"):
            expected_src_len = source_result.resolved_config.length
        elif source_result.resolved_config.source_type == "user_defined":
            expected_src_len = len(source_result.resolved_config.values)

        if source_result.values.shape != (expected_src_len,):
            raise RuntimeError(f"source values shape mismatch: got {source_result.values.shape}, expected ({expected_src_len},)")

        resolved_source = source_result.resolved_config

        # Step 10: Derive convolution config
        conv_config = ImpulseConvolutionConfig(
            mode="same",
            impulse_zero_index=resolved_source.impulse_zero_index,
        )

        # Step 11: Call convolve_impulse exactly once
        conv_result = convolve_impulse(wave, source_result.values, conv_config)

        # Step 12: Validate exact ImpulseConvolutionResult child boundary
        if type(conv_result) is not ImpulseConvolutionResult:
            raise RuntimeError(f"convolution result is not ImpulseConvolutionResult: {type(conv_result)}")
        if type(conv_result.resolved_config) is not ImpulseConvolutionConfig:
            raise RuntimeError(f"convolution resolved_config is not ImpulseConvolutionConfig: {type(conv_result.resolved_config)}")
        if conv_result.resolved_config.mode != "same":
            raise RuntimeError(f"convolution mode mismatch: got '{conv_result.resolved_config.mode}'")
        if conv_result.resolved_config.impulse_zero_index != resolved_source.impulse_zero_index:
            raise RuntimeError(
                f"convolution impulse_zero_index mismatch: got {conv_result.resolved_config.impulse_zero_index}, expected {resolved_source.impulse_zero_index}"
            )
        if conv_result.output_start_index != 0:
            raise RuntimeError(f"convolution output_start_index mismatch: got {conv_result.output_start_index}, expected 0")
        if conv_result.model_level != "discrete_linear_convolution":
            raise RuntimeError(f"convolution model_level mismatch: got '{conv_result.model_level}'")
        if type(conv_result.values) is not np.ndarray:
            raise RuntimeError(f"convolution values is not exact np.ndarray: {type(conv_result.values)}")
        if conv_result.values.dtype != np.float64:
            raise RuntimeError(f"convolution values dtype mismatch: got {conv_result.values.dtype}")
        if conv_result.values.ndim != 1 or conv_result.values.shape != (len(arr),):
            raise RuntimeError(f"convolution values shape mismatch: got {conv_result.values.shape}, expected ({len(arr)},)")
        if not conv_result.values.flags.c_contiguous:
            raise RuntimeError("convolution values is not C-contiguous")
        if conv_result.values.size > 0 and not np.all(np.isfinite(conv_result.values)):
            raise RuntimeError("convolution values contains non-finite elements")
        if conv_result.values is arr or np.shares_memory(conv_result.values, arr):
            raise RuntimeError("convolution values memory aliases caller wave")
        if conv_result.values is source_result.values or np.shares_memory(conv_result.values, source_result.values):
            raise RuntimeError("convolution values memory aliases source values")

        values = conv_result.values

    # Step 13: Build resolved ChannelConfig
    resolved_config = ChannelConfig(
        schema_version=config.schema_version,
        mode=config.mode,
        alpha=resolved_alpha,
        impulse_source=resolved_source,
    )

    # Step 14: Final output verification
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
    elif config.mode == "impulse_response":
        if values.dtype != np.float64:
            raise RuntimeError(f"impulse_response mode dtype mismatch: got {values.dtype}, expected float64")

    return ChannelResult(
        values=values,
        resolved_config=resolved_config,
        model_level=model_level,
    )
