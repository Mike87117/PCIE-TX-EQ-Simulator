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


def _canonicalize_finite_float(value: object, field_name: str) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"{field_name} must be int or float, got {type(value).__name__}")
    try:
        resolved = float(value)
    except OverflowError as exc:
        raise ValueError(f"{field_name} must remain finite after float conversion") from exc

    if not math.isfinite(resolved):
        raise ValueError(f"{field_name} must be finite, got {value}")

    return resolved


@dataclass(frozen=True)
class ImpulseSourceConfig:
    source_type: str = "single_tap"
    sample_interval: float = 1.0
    impulse_zero_index: int = 0
    normalization: str = "none"
    length: int | None = 1
    amplitude: float | None = 1.0
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
        flt_sample_interval = _canonicalize_finite_float(self.sample_interval, "sample_interval")
        if flt_sample_interval <= 0.0:
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

            if self.length is None:
                raise TypeError("length must be int, got NoneType")
            if type(self.length) is not int:
                raise TypeError(f"length must be int, got {type(self.length).__name__}")
            if self.length < 1:
                raise ValueError(f"length must be >= 1, got {self.length}")

            if self.amplitude is None:
                raise TypeError("amplitude must be int or float, got NoneType")
            flt_amp = _canonicalize_finite_float(self.amplitude, "amplitude")
            object.__setattr__(self, "amplitude", flt_amp)

            resolved_len = self.length

        elif self.source_type == "exponential_postcursor":
            if self.values is not None:
                raise ValueError("Field 'values' is irrelevant for source_type 'exponential_postcursor'")

            if self.length is None:
                raise TypeError("length must be int, got NoneType")
            if type(self.length) is not int:
                raise TypeError(f"length must be int, got {type(self.length).__name__}")
            if self.length < 1:
                raise ValueError(f"length must be >= 1, got {self.length}")

            if self.amplitude is None:
                raise TypeError("amplitude must be int or float, got NoneType")
            flt_amp = _canonicalize_finite_float(self.amplitude, "amplitude")
            object.__setattr__(self, "amplitude", flt_amp)

            if self.decay_ratio is None:
                raise ValueError("Field 'decay_ratio' is required for source_type 'exponential_postcursor'")
            flt_decay = _canonicalize_finite_float(self.decay_ratio, "decay_ratio")
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

            # Dimensionality and type validation
            try:
                arr = np.asarray(self.values)
            except Exception as e:
                raise TypeError(f"Failed to convert user_defined values to ndarray: {e}") from e

            if arr.ndim != 1:
                raise ValueError(f"user_defined values must be 1D, got ndim={arr.ndim}")
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

        return cls(
            schema_version=schema_version,
            source_type=data["source_type"],
            sample_interval=data["sample_interval"],
            impulse_zero_index=data["impulse_zero_index"],
            normalization=data["normalization"],
            length=data["length"],
            amplitude=data["amplitude"],
            decay_ratio=data["decay_ratio"],
            values=data["values"],
        )


@dataclass(frozen=True)
class ImpulseSourceResult:
    values: np.ndarray
    resolved_config: ImpulseSourceConfig
    model_level: str


def _build_values(config: ImpulseSourceConfig, resolved_length: int) -> np.ndarray:
    if config.source_type == "single_tap":
        values = np.zeros(resolved_length, dtype=np.float64)
        values[config.impulse_zero_index] = float(config.amplitude)
        return values
    elif config.source_type == "exponential_postcursor":
        values = np.zeros(resolved_length, dtype=np.float64)
        z = config.impulse_zero_index
        amp = float(config.amplitude)
        decay = float(config.decay_ratio)
        for n in range(z, resolved_length):
            values[n] = amp * (decay ** (n - z))
        return values
    elif config.source_type == "user_defined":
        return np.array(config.values, dtype=np.float64)


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

    # 5. Build values via private helper
    values = _build_values(config, resolved_len)

    # 6. Strict final validation without repair
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
