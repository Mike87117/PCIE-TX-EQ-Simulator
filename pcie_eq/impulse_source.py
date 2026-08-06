"""
Synthetic and User-defined Impulse Source Core Module for PCIe TX/RX EQ Simulator.

Provides unified GUI-independent ImpulseSourceConfig, ImpulseSourceResult,
and build_impulse APIs for generating discrete impulse sequences.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import math
import numpy as np

IMPULSE_SOURCE_CONTRACT_ID = "pcie_eq-impulse-source-v1"

__all__ = [
    "IMPULSE_SOURCE_CONTRACT_ID",
    "ImpulseSourceConfig",
    "ImpulseSourceResult",
    "build_impulse",
]

SUPPORTED_SOURCE_TYPES = {"single_tap", "exponential_postcursor", "user_defined"}
SUPPORTED_NORMALIZATION = {"none"}
CANONICAL_KEYS = [
    "schema_version",
    "source_type",
    "sample_interval",
    "impulse_zero_index",
    "normalization",
    "length",
    "amplitude",
    "decay_ratio",
    "values",
]


@dataclass(frozen=True)
class ImpulseSourceConfig:
    source_type: str = "single_tap"
    sample_interval: float = 1.0
    impulse_zero_index: int = 0
    normalization: str = "none"
    length: int | None = None
    amplitude: float | None = None
    decay_ratio: float | None = None
    values: tuple[float, ...] | None = None
    schema_version: str = IMPULSE_SOURCE_CONTRACT_ID

    def _validate(self) -> None:
        # 1. schema_version
        if type(self.schema_version) is not str:
            raise TypeError(f"schema_version must be str, got {type(self.schema_version).__name__}")
        if self.schema_version != IMPULSE_SOURCE_CONTRACT_ID:
            raise ValueError(f"Unknown schema_version '{self.schema_version}', expected '{IMPULSE_SOURCE_CONTRACT_ID}'")

        # 2. source_type
        if type(self.source_type) is not str:
            raise TypeError(f"source_type must be str, got {type(self.source_type).__name__}")
        if self.source_type not in SUPPORTED_SOURCE_TYPES:
            raise ValueError(f"Unsupported source_type '{self.source_type}'")

        # 3. sample_interval
        if type(self.sample_interval) not in (int, float):
            raise TypeError(f"sample_interval must be int or float, got {type(self.sample_interval).__name__}")
        flt_sample_interval = float(self.sample_interval)
        if math.isnan(flt_sample_interval) or math.isinf(flt_sample_interval):
            raise ValueError(f"sample_interval must be finite, got {self.sample_interval}")
        if flt_sample_interval <= 0:
            raise ValueError(f"sample_interval must be > 0, got {self.sample_interval}")
        object.__setattr__(self, "sample_interval", flt_sample_interval)

        # 4. normalization
        if type(self.normalization) is not str:
            raise TypeError(f"normalization must be str, got {type(self.normalization).__name__}")
        if self.normalization not in SUPPORTED_NORMALIZATION:
            raise ValueError(f"Unsupported normalization '{self.normalization}'")

        # 5. impulse_zero_index type & non-negative
        if type(self.impulse_zero_index) is not int:
            raise TypeError(f"impulse_zero_index must be int, got {type(self.impulse_zero_index).__name__}")
        if self.impulse_zero_index < 0:
            raise ValueError(f"impulse_zero_index must be >= 0, got {self.impulse_zero_index}")

        # 6. Source-specific field relevance & validation
        if self.source_type == "single_tap":
            if self.decay_ratio is not None:
                raise ValueError("Field 'decay_ratio' is irrelevant for source_type 'single_tap'")
            if self.values is not None:
                raise ValueError("Field 'values' is irrelevant for source_type 'single_tap'")

            # Default length to 1 if None
            if self.length is None:
                object.__setattr__(self, "length", 1)
            if type(self.length) is not int:
                raise TypeError(f"length must be int, got {type(self.length).__name__}")
            if self.length < 1:
                raise ValueError(f"length must be >= 1, got {self.length}")

            # Default amplitude to 1.0 if None
            if self.amplitude is None:
                object.__setattr__(self, "amplitude", 1.0)
            if type(self.amplitude) not in (int, float):
                raise TypeError(f"amplitude must be int or float, got {type(self.amplitude).__name__}")
            flt_amp = float(self.amplitude)
            if math.isnan(flt_amp) or math.isinf(flt_amp):
                raise ValueError(f"amplitude must be finite, got {self.amplitude}")
            object.__setattr__(self, "amplitude", flt_amp)

            resolved_len = self.length

        elif self.source_type == "exponential_postcursor":
            if self.values is not None:
                raise ValueError("Field 'values' is irrelevant for source_type 'exponential_postcursor'")

            # Default length to 1 if None
            if self.length is None:
                object.__setattr__(self, "length", 1)
            if type(self.length) is not int:
                raise TypeError(f"length must be int, got {type(self.length).__name__}")
            if self.length < 1:
                raise ValueError(f"length must be >= 1, got {self.length}")

            # Default amplitude to 1.0 if None
            if self.amplitude is None:
                object.__setattr__(self, "amplitude", 1.0)
            if type(self.amplitude) not in (int, float):
                raise TypeError(f"amplitude must be int or float, got {type(self.amplitude).__name__}")
            flt_amp = float(self.amplitude)
            if math.isnan(flt_amp) or math.isinf(flt_amp):
                raise ValueError(f"amplitude must be finite, got {self.amplitude}")
            object.__setattr__(self, "amplitude", flt_amp)

            if self.decay_ratio is None:
                raise ValueError("Field 'decay_ratio' is required for source_type 'exponential_postcursor'")
            if type(self.decay_ratio) not in (int, float):
                raise TypeError(f"decay_ratio must be int or float, got {type(self.decay_ratio).__name__}")
            flt_decay = float(self.decay_ratio)
            if math.isnan(flt_decay) or math.isinf(flt_decay):
                raise ValueError(f"decay_ratio must be finite, got {self.decay_ratio}")
            if not (0.0 <= flt_decay < 1.0):
                raise ValueError(f"decay_ratio must be in range [0.0, 1.0), got {self.decay_ratio}")
            object.__setattr__(self, "decay_ratio", flt_decay)

            resolved_len = self.length

        elif self.source_type == "user_defined":
            if self.length is not None:
                raise ValueError("Field 'length' is irrelevant for source_type 'user_defined'")
            if self.amplitude is not None:
                raise ValueError("Field 'amplitude' is irrelevant for source_type 'user_defined'")
            if self.decay_ratio is not None:
                raise ValueError("Field 'decay_ratio' is irrelevant for source_type 'user_defined'")

            if self.values is None:
                raise ValueError("Field 'values' is required for source_type 'user_defined'")

            # Canonicalize values to tuple[float, ...]
            if not isinstance(self.values, (list, tuple, np.ndarray)):
                raise TypeError(f"user_defined values must be list, tuple, or 1D ndarray, got {type(self.values).__name__}")

            try:
                arr = np.asarray(self.values)
            except Exception as e:
                raise TypeError(f"Failed to convert user_defined values to ndarray: {e}") from e

            if arr.ndim != 1:
                raise ValueError(f"user_defined values must be 1D, got shape {arr.shape}")
            if arr.dtype.kind not in {"b", "i", "u", "f"}:
                raise TypeError(f"user_defined values dtype must be real numeric (bool, int, uint, float), got {arr.dtype}")
            if arr.size == 0:
                raise ValueError("user_defined values must not be empty")
            if not np.all(np.isfinite(arr)):
                raise ValueError("user_defined values elements must be finite")

            arr_f64 = arr.astype(np.float64)
            if not np.all(np.isfinite(arr_f64)):
                raise ValueError("user_defined values elements must be finite after float64 conversion")

            val_tuple = tuple(float(x) for x in arr_f64)
            object.__setattr__(self, "values", val_tuple)

            resolved_len = len(val_tuple)

        # 7. Zero-index range check against resolved length
        if self.impulse_zero_index >= resolved_len:
            raise ValueError(
                f"impulse_zero_index ({self.impulse_zero_index}) must be < resolved length ({resolved_len})"
            )

    def __post_init__(self) -> None:
        self._validate()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source_type": self.source_type,
            "sample_interval": self.sample_interval,
            "impulse_zero_index": self.impulse_zero_index,
            "normalization": self.normalization,
            "length": self.length,
            "amplitude": self.amplitude,
            "decay_ratio": self.decay_ratio,
            "values": list(self.values) if self.values is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ImpulseSourceConfig":
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
        if schema_version != IMPULSE_SOURCE_CONTRACT_ID:
            raise ValueError(f"Unknown schema_version '{schema_version}', expected '{IMPULSE_SOURCE_CONTRACT_ID}'")

        raw_values = data["values"]
        values_param = tuple(raw_values) if raw_values is not None else None

        return cls(
            schema_version=schema_version,
            source_type=data["source_type"],
            sample_interval=data["sample_interval"],
            impulse_zero_index=data["impulse_zero_index"],
            normalization=data["normalization"],
            length=data["length"],
            amplitude=data["amplitude"],
            decay_ratio=data["decay_ratio"],
            values=values_param,
        )


@dataclass(frozen=True)
class ImpulseSourceResult:
    values: np.ndarray
    resolved_config: ImpulseSourceConfig
    model_level: str


def build_impulse(config: ImpulseSourceConfig) -> ImpulseSourceResult:
    # 1. Require exact config type
    if type(config) is not ImpulseSourceConfig:
        raise TypeError(f"config must be exactly ImpulseSourceConfig, got {type(config).__name__}")

    # 2. Defensively revalidate the original frozen config
    config._validate()

    # 3. Determine exact resolved length
    if config.source_type in ("single_tap", "exponential_postcursor"):
        resolved_len = config.length
    elif config.source_type == "user_defined":
        resolved_len = len(config.values)

    # 4. Rebuild a new exact resolved config
    resolved_config = ImpulseSourceConfig(
        schema_version=config.schema_version,
        source_type=config.source_type,
        sample_interval=config.sample_interval,
        impulse_zero_index=config.impulse_zero_index,
        normalization=config.normalization,
        length=config.length,
        amplitude=config.amplitude,
        decay_ratio=config.decay_ratio,
        values=config.values,
    )

    # 5. Allocate & compute float64 output
    if config.source_type == "single_tap":
        values = np.zeros(resolved_len, dtype=np.float64)
        values[config.impulse_zero_index] = float(config.amplitude)

    elif config.source_type == "exponential_postcursor":
        values = np.zeros(resolved_len, dtype=np.float64)
        z = config.impulse_zero_index
        amp = float(config.amplitude)
        decay = float(config.decay_ratio)
        for n in range(z, resolved_len):
            values[n] = amp * (decay ** (n - z))

    elif config.source_type == "user_defined":
        values = np.array(config.values, dtype=np.float64)

    # 6. Strict final validation
    if type(values) is not np.ndarray:
        raise RuntimeError(f"Generated output is not exact np.ndarray: {type(values)}")
    if values.ndim != 1 or values.shape != (resolved_len,):
        raise RuntimeError(f"Generated output shape mismatch: got {values.shape}, expected ({resolved_len},)")
    if values.dtype != np.float64:
        raise RuntimeError(f"Generated output dtype mismatch: got {values.dtype}, expected float64")
    if not values.flags.c_contiguous:
        raise RuntimeError("Generated output is not C-contiguous")
    if not np.all(np.isfinite(values)):
        raise RuntimeError("Generated output contains non-finite values")

    return ImpulseSourceResult(
        values=values,
        resolved_config=resolved_config,
        model_level="project_owned_discrete_impulse_source",
    )
