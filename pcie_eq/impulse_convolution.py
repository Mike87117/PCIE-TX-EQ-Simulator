"""
Impulse Response Convolution Core Module for PCIe TX/RX EQ Simulator.

Provides unified GUI-independent ImpulseConvolutionConfig, ImpulseConvolutionResult,
and convolve_impulse APIs for discrete linear convolution.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import numpy as np

IMPULSE_CONVOLUTION_CONTRACT_ID = "pcie_eq-impulse-convolution-v1"

__all__ = [
    "IMPULSE_CONVOLUTION_CONTRACT_ID",
    "ImpulseConvolutionConfig",
    "ImpulseConvolutionResult",
    "convolve_impulse",
]

SUPPORTED_MODES = {"full", "same", "valid"}
CANONICAL_KEYS = ["schema_version", "mode", "impulse_zero_index"]


@dataclass(frozen=True)
class ImpulseConvolutionConfig:
    mode: str = "full"
    impulse_zero_index: int = 0
    schema_version: str = IMPULSE_CONVOLUTION_CONTRACT_ID

    def _validate(self) -> None:
        if type(self.schema_version) is not str:
            raise TypeError(f"schema_version must be str, got {type(self.schema_version).__name__}")
        if self.schema_version != IMPULSE_CONVOLUTION_CONTRACT_ID:
            raise ValueError(f"Unknown schema_version '{self.schema_version}', expected '{IMPULSE_CONVOLUTION_CONTRACT_ID}'")

        if type(self.mode) is not str:
            raise TypeError(f"mode must be str, got {type(self.mode).__name__}")
        if self.mode not in SUPPORTED_MODES:
            raise ValueError(f"Unsupported mode '{self.mode}'")

        if type(self.impulse_zero_index) is not int:
            raise TypeError(f"impulse_zero_index must be int, got {type(self.impulse_zero_index).__name__}")
        if self.impulse_zero_index < 0:
            raise ValueError(f"impulse_zero_index must be >= 0, got {self.impulse_zero_index}")

    def __post_init__(self) -> None:
        self._validate()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "impulse_zero_index": self.impulse_zero_index,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ImpulseConvolutionConfig":
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
        if schema_version != IMPULSE_CONVOLUTION_CONTRACT_ID:
            raise ValueError(f"Unknown schema_version '{schema_version}', expected '{IMPULSE_CONVOLUTION_CONTRACT_ID}'")

        return cls(
            schema_version=schema_version,
            mode=data["mode"],
            impulse_zero_index=data["impulse_zero_index"],
        )


@dataclass(frozen=True)
class ImpulseConvolutionResult:
    values: np.ndarray
    resolved_config: ImpulseConvolutionConfig
    output_start_index: int
    model_level: str


def convolve_impulse(
    wave,
    impulse,
    config: ImpulseConvolutionConfig,
) -> ImpulseConvolutionResult:
    # 1. Exact config type check
    if type(config) is not ImpulseConvolutionConfig:
        raise TypeError(f"config must be exactly ImpulseConvolutionConfig, got {type(config).__name__}")

    # 2. Defensive re-validation of original config before either input conversion
    config._validate()

    # 3. Wave input conversion & validation (FIRST)
    try:
        wave_arr = np.asarray(wave)
    except Exception as e:
        raise TypeError(f"Failed to convert wave input to ndarray: {e}") from e

    if wave_arr.ndim != 1:
        raise ValueError(f"wave input must be 1D, got shape {wave_arr.shape}")

    if wave_arr.dtype.kind not in {"b", "i", "u", "f"}:
        raise TypeError(f"wave input dtype must be real numeric (bool, int, uint, float), got {wave_arr.dtype}")

    if wave_arr.size > 0 and not np.all(np.isfinite(wave_arr)):
        raise ValueError("wave input elements must be finite")

    # 4. Impulse input conversion & validation (SECOND)
    try:
        impulse_arr = np.asarray(impulse)
    except Exception as e:
        raise TypeError(f"Failed to convert impulse input to ndarray: {e}") from e

    if impulse_arr.ndim != 1:
        raise ValueError(f"impulse input must be 1D, got shape {impulse_arr.shape}")

    if impulse_arr.dtype.kind not in {"b", "i", "u", "f"}:
        raise TypeError(f"impulse input dtype must be real numeric (bool, int, uint, float), got {impulse_arr.dtype}")

    if impulse_arr.size == 0:
        raise ValueError("impulse input must not be empty")

    if not np.all(np.isfinite(impulse_arr)):
        raise ValueError("impulse input elements must be finite")

    if not (0 <= config.impulse_zero_index < len(impulse_arr)):
        raise ValueError(f"impulse_zero_index ({config.impulse_zero_index}) must be < len(impulse) ({len(impulse_arr)})")

    # 5. Dtype resolution
    promoted = np.result_type(wave_arr.dtype, impulse_arr.dtype)
    expected_dtype = promoted if promoted.kind == "f" else np.dtype(np.float64)

    # 6. Resolved config
    resolved_config = ImpulseConvolutionConfig(
        schema_version=config.schema_version,
        mode=config.mode,
        impulse_zero_index=config.impulse_zero_index,
    )

    # 7. Empty wave path (return without calling np.convolve)
    if wave_arr.size == 0:
        empty_values = np.array([], dtype=expected_dtype)
        return ImpulseConvolutionResult(
            values=empty_values,
            resolved_config=resolved_config,
            output_start_index=0,
            model_level="discrete_linear_convolution",
        )

    # 8. Valid mode N < M check
    N = len(wave_arr)
    M = len(impulse_arr)
    z = config.impulse_zero_index

    if config.mode == "valid" and N < M:
        raise ValueError(f"valid mode requires len(wave) ({N}) >= len(impulse) ({M})")

    # 9. Working array conversion & Production convolution with mode="full" ONLY
    wave_work = wave_arr.astype(expected_dtype, copy=False)
    impulse_work = impulse_arr.astype(expected_dtype, copy=False)

    full_result = np.convolve(wave_work, impulse_work, mode="full")

    # 10. Raw full helper output validation
    if type(full_result) is not np.ndarray:
        raise RuntimeError(f"Convolution helper output is not exact np.ndarray: {type(full_result)}")
    if full_result.ndim != 1 or full_result.shape != (N + M - 1,):
        raise RuntimeError(f"Convolution helper output shape mismatch: got {full_result.shape}, expected ({N + M - 1},)")
    if full_result.dtype != expected_dtype:
        raise RuntimeError(f"Convolution helper output dtype mismatch: got {full_result.dtype}, expected {expected_dtype}")
    if not full_result.flags.c_contiguous:
        raise RuntimeError("Convolution helper output is not C-contiguous")
    if not np.all(np.isfinite(full_result)):
        raise RuntimeError("Convolution helper output contains non-finite values")
    if (
        full_result is wave_work
        or full_result is impulse_work
        or full_result is wave_arr
        or full_result is impulse_arr
    ):
        raise RuntimeError("Convolution helper output aliases input object")
    if (
        np.shares_memory(full_result, wave_work)
        or np.shares_memory(full_result, impulse_work)
        or np.shares_memory(full_result, wave_arr)
        or np.shares_memory(full_result, impulse_arr)
    ):
        raise RuntimeError("Convolution helper output shares memory with working input")

    # 11. Slicing & Alignment according to exact project mode semantics
    if config.mode == "full":
        values = full_result
        output_start_index = -z
    elif config.mode == "same":
        values = np.array(full_result[z : z + N], copy=True)
        output_start_index = 0
    elif config.mode == "valid":
        values = np.array(full_result[M - 1 : N], copy=True)
        output_start_index = M - 1 - z

    # 12. Final output validation
    if type(values) is not np.ndarray:
        raise RuntimeError(f"Final output is not exact np.ndarray: {type(values)}")
    if values.ndim != 1:
        raise RuntimeError(f"Final output is not 1D: shape {values.shape}")

    expected_len = (N + M - 1) if config.mode == "full" else (N if config.mode == "same" else (N - M + 1))
    if values.shape != (expected_len,):
        raise RuntimeError(f"Final output shape mismatch: got {values.shape}, expected ({expected_len},)")
    if values.dtype != expected_dtype:
        raise RuntimeError(f"Final output dtype mismatch: got {values.dtype}, expected {expected_dtype}")
    if not values.flags.c_contiguous:
        raise RuntimeError("Final output is not C-contiguous")
    if values is wave_arr or values is impulse_arr:
        raise RuntimeError("Final output aliases input object")
    if np.shares_memory(values, wave_arr) or np.shares_memory(values, impulse_arr):
        raise RuntimeError("Final output shares memory with input")
    if not np.all(np.isfinite(values)):
        raise RuntimeError("Final output contains non-finite values")

    return ImpulseConvolutionResult(
        values=values,
        resolved_config=resolved_config,
        output_start_index=output_start_index,
        model_level="discrete_linear_convolution",
    )
