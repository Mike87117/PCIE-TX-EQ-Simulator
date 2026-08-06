"""
Pattern Configuration Core Module for PCIe TX/RX EQ Simulator.

Provides unified GUI-independent PatternConfig and PatternResult APIs
for requesting and generating NRZ and PAM4 patterns.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import math
import numpy as np

from pcie_eq.patterns import (
    generate_random_nrz_bits,
    generate_random_pam4_symbols,
    generate_nrz_all_zeros,
    generate_nrz_all_ones,
    generate_nrz_alternating,
    generate_nrz_long_run,
    generate_nrz_single_transition,
    generate_nrz_single_bit_pulse,
    generate_prbs_bits,
)

PATTERN_CONFIG_CONTRACT_ID = "pcie_eq-pattern-config-v1"
PRBS_CONVENTION_ID = "pcie_eq-prbs-fibonacci-lsb-v1"

__all__ = [
    "PATTERN_CONFIG_CONTRACT_ID",
    "PatternConfig",
    "PatternResult",
    "generate_pattern",
]

SUPPORTED_PATTERN_TYPES = {
    "nrz_random",
    "nrz_all_zeros",
    "nrz_all_ones",
    "nrz_alternating",
    "nrz_long_run",
    "nrz_single_transition",
    "nrz_single_bit_pulse",
    "nrz_prbs",
    "nrz_user_bits",
    "pam4_random",
    "pam4_user_symbols",
}

CANONICAL_KEYS = [
    "schema_version",
    "pattern_type",
    "count",
    "seed",
    "first_bit",
    "run_length",
    "transition_index",
    "initial_bit",
    "pulse_index",
    "baseline_bit",
    "prbs_order",
    "prbs_initial_state",
    "prbs_convention_id",
    "user_values",
]

ALLOWED_OPTIONAL_FIELDS = {
    "nrz_random": {"seed"},
    "nrz_all_zeros": set(),
    "nrz_all_ones": set(),
    "nrz_alternating": {"first_bit"},
    "nrz_long_run": {"first_bit", "run_length"},
    "nrz_single_transition": {"transition_index", "initial_bit"},
    "nrz_single_bit_pulse": {"pulse_index", "baseline_bit"},
    "nrz_prbs": {"prbs_order", "prbs_initial_state", "prbs_convention_id"},
    "nrz_user_bits": {"user_values"},
    "pam4_random": {"seed"},
    "pam4_user_symbols": {"user_values"},
}

ALL_OPTIONAL_FIELDS = {
    "seed",
    "first_bit",
    "run_length",
    "transition_index",
    "initial_bit",
    "pulse_index",
    "baseline_bit",
    "prbs_order",
    "prbs_initial_state",
    "prbs_convention_id",
    "user_values",
}

CANONICAL_PAM4_LEVELS = (-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0)


@dataclass(frozen=True)
class PatternConfig:
    pattern_type: str
    count: int
    schema_version: str = PATTERN_CONFIG_CONTRACT_ID
    seed: int | None = None
    first_bit: int | None = None
    run_length: int | None = None
    transition_index: int | None = None
    initial_bit: int | None = None
    pulse_index: int | None = None
    baseline_bit: int | None = None
    prbs_order: int | None = None
    prbs_initial_state: int | None = None
    prbs_convention_id: str | None = None
    user_values: tuple[int | float | bool, ...] | None = None

    def _validate(self) -> None:
        if type(self.schema_version) is not str:
            raise TypeError(f"schema_version must be str, got {type(self.schema_version).__name__}")
        if self.schema_version != PATTERN_CONFIG_CONTRACT_ID:
            raise ValueError(f"Unknown schema_version '{self.schema_version}', expected '{PATTERN_CONFIG_CONTRACT_ID}'")

        if type(self.pattern_type) is not str:
            raise TypeError(f"pattern_type must be str, got {type(self.pattern_type).__name__}")
        if self.pattern_type not in SUPPORTED_PATTERN_TYPES:
            raise ValueError(f"Unsupported pattern_type '{self.pattern_type}'")

        if type(self.count) is not int:
            raise TypeError(f"count must be int, got {type(self.count).__name__}")
        if self.count < 0:
            raise ValueError(f"count must be >= 0, got {self.count}")
        if self.pattern_type == "nrz_single_bit_pulse" and self.count == 0:
            raise ValueError("nrz_single_bit_pulse requires count > 0")

        # Irrelevant field rejection
        allowed = ALLOWED_OPTIONAL_FIELDS[self.pattern_type]
        irrelevant = ALL_OPTIONAL_FIELDS - allowed
        for field_name in irrelevant:
            val = getattr(self, field_name)
            if val is not None:
                raise ValueError(f"Field '{field_name}' is not applicable for pattern_type '{self.pattern_type}'")

        # Pattern-specific validations
        if "seed" in allowed and self.seed is not None:
            if type(self.seed) is not int:
                raise TypeError(f"seed must be int or None, got {type(self.seed).__name__}")
            if not (0 <= self.seed <= 2**32 - 1):
                raise ValueError(f"seed must be between 0 and 2**32 - 1, got {self.seed}")

        for bit_field in ("first_bit", "initial_bit", "baseline_bit"):
            if bit_field in allowed:
                val = getattr(self, bit_field)
                if val is not None:
                    if type(val) is not int:
                        raise TypeError(f"{bit_field} must be int (0 or 1), got {type(val).__name__}")
                    if val not in (0, 1):
                        raise ValueError(f"{bit_field} must be 0 or 1, got {val}")

        if "run_length" in allowed:
            if self.run_length is None:
                raise ValueError("nrz_long_run requires run_length")
            if type(self.run_length) is not int:
                raise TypeError(f"run_length must be int, got {type(self.run_length).__name__}")
            if self.run_length < 1:
                raise ValueError(f"run_length must be >= 1, got {self.run_length}")

        if "transition_index" in allowed:
            if self.transition_index is None:
                raise ValueError("nrz_single_transition requires transition_index")
            if type(self.transition_index) is not int:
                raise TypeError(f"transition_index must be int, got {type(self.transition_index).__name__}")
            if not (0 <= self.transition_index <= self.count):
                raise ValueError(f"transition_index must be between 0 and count ({self.count}), got {self.transition_index}")

        if "pulse_index" in allowed:
            if self.pulse_index is None:
                raise ValueError("nrz_single_bit_pulse requires pulse_index")
            if type(self.pulse_index) is not int:
                raise TypeError(f"pulse_index must be int, got {type(self.pulse_index).__name__}")
            if not (0 <= self.pulse_index < self.count):
                raise ValueError(f"pulse_index must be between 0 and count - 1 ({self.count - 1}), got {self.pulse_index}")

        if "prbs_order" in allowed:
            if self.prbs_order is None:
                raise ValueError("nrz_prbs requires prbs_order")
            if type(self.prbs_order) is not int:
                raise TypeError(f"prbs_order must be int, got {type(self.prbs_order).__name__}")
            if self.prbs_order not in {7, 9, 15, 23, 31}:
                raise ValueError(f"prbs_order must be one of {{7, 9, 15, 23, 31}}, got {self.prbs_order}")

            if self.prbs_initial_state is not None:
                if type(self.prbs_initial_state) is not int:
                    raise TypeError(f"prbs_initial_state must be int, got {type(self.prbs_initial_state).__name__}")
                max_state = (1 << self.prbs_order) - 1
                if not (1 <= self.prbs_initial_state <= max_state):
                    raise ValueError(f"prbs_initial_state must be between 1 and {max_state}, got {self.prbs_initial_state}")

            if self.prbs_convention_id is not None:
                if type(self.prbs_convention_id) is not str:
                    raise TypeError(f"prbs_convention_id must be str, got {type(self.prbs_convention_id).__name__}")
                if self.prbs_convention_id != PRBS_CONVENTION_ID:
                    raise ValueError(f"Unknown prbs_convention_id '{self.prbs_convention_id}', expected '{PRBS_CONVENTION_ID}'")

        if "user_values" in allowed:
            if self.user_values is None:
                raise ValueError(f"'{self.pattern_type}' requires user_values")
            if type(self.user_values) is not tuple:
                raise TypeError(f"user_values must be tuple or None, got {type(self.user_values).__name__}")
            if len(self.user_values) != self.count:
                raise ValueError(f"user_values length ({len(self.user_values)}) must equal count ({self.count})")

            if self.pattern_type == "nrz_user_bits":
                for elem in self.user_values:
                    if type(elem) not in (int, bool):
                        raise TypeError(f"nrz_user_bits element must be exact int or bool, got {type(elem).__name__}")
                    if elem not in (0, 1, False, True):
                        raise ValueError(f"nrz_user_bits element must be 0 or 1, got {elem}")

            elif self.pattern_type == "pam4_user_symbols":
                for elem in self.user_values:
                    if type(elem) not in (int, float):
                        raise TypeError(f"pam4_user_symbols element must be exact Python int or float, got {type(elem).__name__}")
                    flt_val = float(elem)
                    if math.isnan(flt_val) or math.isinf(flt_val):
                        raise ValueError(f"pam4_user_symbols element must be finite, got {elem}")
                    if flt_val not in CANONICAL_PAM4_LEVELS:
                        raise ValueError(f"pam4_user_symbols element {elem} is not a valid PAM4 level in {CANONICAL_PAM4_LEVELS}")

    def __post_init__(self) -> None:
        self._validate()

    def to_dict(self) -> dict[str, object]:
        res = {}
        for key in CANONICAL_KEYS:
            val = getattr(self, key)
            if key == "user_values" and val is not None:
                res[key] = list(val)
            else:
                res[key] = val
        return res

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "PatternConfig":
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
        if schema_version != PATTERN_CONFIG_CONTRACT_ID:
            raise ValueError(f"Unknown schema_version '{schema_version}', expected '{PATTERN_CONFIG_CONTRACT_ID}'")

        kwargs = {}
        for key in CANONICAL_KEYS:
            val = data[key]
            if key == "user_values" and val is not None:
                if type(val) is not list:
                    raise TypeError(f"user_values in dict must be a list or None, got {type(val).__name__}")
                kwargs[key] = tuple(val)
            else:
                kwargs[key] = val

        return cls(**kwargs)


@dataclass(frozen=True)
class PatternResult:
    values: np.ndarray
    resolved_config: PatternConfig
    modulation: str
    domain: str
    rng_mode: str


def generate_pattern(config: PatternConfig) -> PatternResult:
    if type(config) is not PatternConfig:
        raise TypeError(f"config must be exactly PatternConfig, got {type(config).__name__}")

    # Defensive re-validation of original PatternConfig instance before any processing or RNG access
    config._validate()

    # Resolve default values for resolved_config
    ptype = config.pattern_type
    first_bit = config.first_bit
    initial_bit = config.initial_bit
    baseline_bit = config.baseline_bit
    prbs_initial_state = config.prbs_initial_state
    prbs_convention_id = config.prbs_convention_id
    user_values = config.user_values

    if ptype in ("nrz_alternating", "nrz_long_run") and first_bit is None:
        first_bit = 0
    if ptype == "nrz_single_transition" and initial_bit is None:
        initial_bit = 0
    if ptype == "nrz_single_bit_pulse" and baseline_bit is None:
        baseline_bit = 0
    if ptype == "nrz_prbs":
        if prbs_initial_state is None:
            prbs_initial_state = (1 << config.prbs_order) - 1
        if prbs_convention_id is None:
            prbs_convention_id = PRBS_CONVENTION_ID
    if ptype == "nrz_user_bits" and user_values is not None:
        user_values = tuple(1 if x is True else (0 if x is False else int(x)) for x in config.user_values)
    if ptype == "pam4_user_symbols" and user_values is not None:
        user_values = tuple(float(x) for x in config.user_values)

    resolved_config = PatternConfig(
        schema_version=config.schema_version,
        pattern_type=ptype,
        count=config.count,
        seed=config.seed,
        first_bit=first_bit,
        run_length=config.run_length,
        transition_index=config.transition_index,
        initial_bit=initial_bit,
        pulse_index=config.pulse_index,
        baseline_bit=baseline_bit,
        prbs_order=config.prbs_order,
        prbs_initial_state=prbs_initial_state,
        prbs_convention_id=prbs_convention_id,
        user_values=user_values,
    )

    # Dispatch to existing generators in pcie_eq.patterns
    if ptype == "nrz_random":
        values = generate_random_nrz_bits(count=config.count, seed=config.seed)
    elif ptype == "nrz_all_zeros":
        values = generate_nrz_all_zeros(count=config.count)
    elif ptype == "nrz_all_ones":
        values = generate_nrz_all_ones(count=config.count)
    elif ptype == "nrz_alternating":
        values = generate_nrz_alternating(count=config.count, first_bit=resolved_config.first_bit)
    elif ptype == "nrz_long_run":
        values = generate_nrz_long_run(count=config.count, run_length=config.run_length, first_bit=resolved_config.first_bit)
    elif ptype == "nrz_single_transition":
        values = generate_nrz_single_transition(count=config.count, transition_index=config.transition_index, initial_bit=resolved_config.initial_bit)
    elif ptype == "nrz_single_bit_pulse":
        values = generate_nrz_single_bit_pulse(count=config.count, pulse_index=config.pulse_index, baseline_bit=resolved_config.baseline_bit)
    elif ptype == "nrz_prbs":
        values = generate_prbs_bits(order=config.prbs_order, count=config.count, initial_state=resolved_config.prbs_initial_state)
    elif ptype == "nrz_user_bits":
        values = np.array(resolved_config.user_values, dtype=int)
    elif ptype == "pam4_random":
        values = generate_random_pam4_symbols(count=config.count, seed=config.seed)
    elif ptype == "pam4_user_symbols":
        values = np.array(resolved_config.user_values, dtype=np.float64)

    # Determine metadata
    modulation = "pam4" if ptype.startswith("pam4_") else "nrz"
    domain = "symbols" if ptype.startswith("pam4_") else "bits"
    if ptype in ("nrz_random", "pam4_random"):
        rng_mode = "seeded" if config.seed is not None else "global"
    else:
        rng_mode = "none"

    # Verify contract on values
    if not isinstance(values, np.ndarray):
        raise RuntimeError(f"Generator output is not np.ndarray: {type(values)}")
    if values.ndim != 1 or values.shape != (config.count,):
        raise RuntimeError(f"Generator output shape mismatch: got {values.shape}, expected ({config.count},)")
    if not values.flags.c_contiguous:
        raise RuntimeError("Generator output is not C-contiguous")

    # Dtype contract checks
    if ptype == "nrz_random":
        expected_dtype = np.dtype("l") if config.count > 0 else np.dtype(int)
        if values.dtype != expected_dtype:
            raise RuntimeError(f"nrz_random dtype mismatch: got {values.dtype}, expected {expected_dtype}")
    elif ptype in ("nrz_all_zeros", "nrz_all_ones", "nrz_alternating", "nrz_long_run", "nrz_single_transition", "nrz_single_bit_pulse", "nrz_user_bits"):
        if values.dtype != np.dtype(int):
            raise RuntimeError(f"{ptype} dtype mismatch: got {values.dtype}, expected {np.dtype(int)}")
    elif ptype == "nrz_prbs":
        if values.dtype != np.int8:
            raise RuntimeError(f"nrz_prbs dtype mismatch: got {values.dtype}, expected int8")
    elif ptype in ("pam4_random", "pam4_user_symbols"):
        if values.dtype != np.float64:
            raise RuntimeError(f"{ptype} dtype mismatch: got {values.dtype}, expected float64")

    # Value domain checks (exact equality for PAM4, no tolerance/rounding)
    if domain == "bits" and values.size > 0:
        for val in values:
            if val not in (0, 1):
                raise RuntimeError(f"NRZ pattern contains invalid bit value: {val}")
    elif domain == "symbols" and values.size > 0:
        for val in values:
            if val not in CANONICAL_PAM4_LEVELS:
                raise RuntimeError(f"PAM4 pattern contains invalid symbol value: {val}")

    return PatternResult(
        values=values,
        resolved_config=resolved_config,
        modulation=modulation,
        domain=domain,
        rng_mode=rng_mode,
    )
