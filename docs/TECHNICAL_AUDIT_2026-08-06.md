# Technical Audit — 2026-08-06

> Status: Active planning evidence  
> Repository: `Mike87117/PCIE-TX-EQ-Simulator`  
> Production baseline: `c4fd8c8191919c30d8e28383d94804fe3e68db25` / 192 tests  
> Contract correction baseline: `acbce101562521f3bbaff24ff48887dacb98de87`  
> Related Roadmap Issue: #48  
> Tracking Issue: #69

---

## 1. Purpose

This audit records implementation blockers, phase-entry gates, baseline-migration requirements, and verified technical debt discovered after the original Roadmap feasibility review.

It does not authorize code changes by itself. Each code change still requires an Implementation Issue, exact file boundary, independent validation, CI, and Merge Gate.

Where benchmark values are identified as **user-provided**, they are planning evidence and have not yet been promoted to CI performance or numerical golden tests.

---

## 2. Immediate Contract Blocker — Resolved

The original Pattern Configuration Contract incorrectly required all general NRZ output to use exact `numpy.dtype(int)`.

Existing `generate_random_nrz_bits()` has two different dtype branches:

```text
count == 0:
    numpy.dtype(int)

count > 0:
    numpy.dtype("l") / legacy C-long
```

On current 64-bit Windows and NumPy 2.4.x, these are normally `int64` and `int32`, respectively.

Contract revision 1.1 now freezes the actual compatibility behavior:

| Pattern group | Exact dtype contract |
|---|---|
| `nrz_random`, `count > 0` | `numpy.dtype("l")` |
| `nrz_random`, `count == 0` | `numpy.dtype(int)` |
| Deterministic NRZ and `nrz_user_bits` | `numpy.dtype(int)` |
| `nrz_prbs` | `numpy.int8` |
| PAM4 random and user symbols | `numpy.float64` |

The Pattern Configuration aggregator must not cast existing helper output.

Evidence:

```text
Issue #64
PR #65
Contract merge acbce101562521f3bbaff24ff48887dacb98de87
CI 192 passed
```

Implementation 25 / Issue #60 is unblocked and must use Contract revision 1.1.

---

## 3. Confirmed High-Priority Bugs

### 3.1 `simple_channel()` integer truncation and empty crash

Tracking: Issue #66.

Current implementation uses:

```python
out = np.zeros_like(wave)
out[0] = wave[0]
```

Consequences:

- Integer input silently truncates recursive floating-point updates.
- Empty input raises `IndexError`.
- The current public helper is unsafe as the future `legacy_lowpass` Channel mode.

Required before ChannelConfig:

- Explicit numeric input contract.
- Exact float output dtype.
- Empty input policy.
- Input immutability and non-aliasing.
- Existing float-waveform numerical baseline preservation.

### 3.2 Unified pipeline defaults crash

Tracking: Issue #67.

Both simulation config dataclasses can be created with their defaults, but the unified pipeline crashes:

```text
NrzSimulationConfig()  -> simple_channel empty IndexError
Pam4SimulationConfig() -> np.pad(mode="edge") empty ValueError
```

A public config default cannot remain constructible while failing later through unrelated low-level exceptions.

A docs-first decision must choose one exact policy:

1. Empty input is valid and produces a fully defined empty result; or
2. Empty input is rejected at the config or pipeline boundary with a stable public error.

### 3.3 NRZ sampling semantics are inconsistent

Tracking: Issue #68.

Current code uses different phase definitions:

```text
DFE sampling:       0.50 UI
NRZ eye metric:     1.00 UI within a 2 UI trace
User-measured max:  about 0.88 UI
```

User-provided measurements:

```text
0.50 UI  opening = 1.0307
0.88 UI  opening = 1.6436
1.00 UI  opening = 1.4248
```

The exact measured values still require an independent reproducible test, but repository code already confirms that DFE and NRZ eye metrics use different sampling points.

This blocks a coherent definition for Cursor Analysis and Phase 3 sampling.

---

## 4. Phase 2 Assessment

### Step 2.4 — Channel Interface / ChannelConfig

Feasible, but entry is conditional on Issue #66 and an exact identity/copy contract.

The future modes remain reasonable:

```text
none
legacy_lowpass
impulse_response
```

Required decisions include input shape, output dtype, sample interval, normalization, empty input, error behavior, and copy/alias semantics.

### Step 2.5 — Impulse Response Convolution

Feasible.

No mathematical blocker exists, but implementation must first freeze:

- `full` / `same` / `valid` policy.
- Sample interval compatibility.
- Output length.
- Time-zero and main-cursor alignment.
- Normalization.
- Truncation and padding.

Validation can use delta impulses, shifted impulses, short analytical convolution cases, and energy/scale checks.

### Step 2.6 — Synthetic / User-defined Impulse

Feasible.

Required contract:

- Numeric input type and dimension.
- Finite values.
- Sample interval.
- Time-zero index.
- Normalization mode.
- Copy and immutability policy.
- Empty and all-zero impulse behavior.

### Step 2.7 — Pulse / Cursor Analysis

The cursor mathematics is feasible, but implementation is **Conditional** until Issue #68 freezes sampling phase, time reference, group-delay handling, and baseline migration.

### Step 2.8 — Pattern / Channel GUI Integration

Conditional on stable PatternConfig, ChannelConfig, convolution, cursor result, and explicit GUI baseline-change decisions.

A known future conflict already exists:

- `nrz_bits_to_symbols()` returns `float64`.
- Current GUI uses `2 * bits - 1`, preserving the integer dtype of `bits`.

Using the public converter in the GUI would intentionally change existing symbol dtype and raw-byte fingerprints. That must be handled by a dedicated baseline-change gate, not disguised as mechanical integration.

### Step 2.9 — Channel Views

Status: **Conditional**.

The GUI view is easy to draw, but the underlying source-of-truth is not yet complete. Entry requires:

- Stable ChannelConfig.
- Frequency-grid and interpolation rules.
- Reference impedance and insertion-loss definitions where applicable.
- Normalization and units.
- Core-generated view data; GUI must not recompute the model.

### Step 2.10 — Touchstone

Status: **Conditional**.

- `.s2p` single-ended teaching path is feasible.
- S-parameter-to-impulse conversion requires frequency spacing, DC extrapolation, windowing, reference impedance, and interpolation contracts.
- `.s4p`, mixed mode, and `SDD21` remain conditional on port ordering, wave definition, and validated sample files.

---

## 5. Phase 3 — NRZ Sampling & RXEQ

The existing Roadmap status `Conditional` remains correct.

A new mandatory entry gate is added:

> Any phase sweep, auto-center, or sampling-semantic change must use an explicit baseline-change PR.

That PR must:

1. Preserve old numerical evidence.
2. Define the new authoritative phase reference.
3. Enumerate expected metric and GUI changes.
4. Compare old and new results directly.
5. Update golden tests intentionally rather than loosening tolerances.

`Existing Behavior Compatibility` does not mean all old numbers must remain forever. It may be satisfied by a reviewed and documented intentional baseline migration.

No generic teaching receiver may be labelled as PCIe generation-specific compliance behavior without the required specification or reference receiver evidence.

---

## 6. Phase 4 — PAM4 RXEQ

Status remains `Conditional`, but workload classification must be corrected.

Current PAM4 pipeline is:

```text
TX FIR -> simplified channel -> PAM4 eye metrics
```

It currently has no PAM4 RX stage:

- No CTLE.
- No RX FFE.
- No slicer thresholds.
- No symbol decisions.
- No DFE.
- No deterministic SER path.

Therefore generic PAM4 RXEQ is a greenfield receiver architecture, not a small incremental extension after Phase 3.

A staged delivery should start with shared sampling/result contracts, then slicers and decisions, followed by manual equalizers. PCIe-specific adaptation remains separately conditional.

---

## 7. Phase 5 — Statistical Metrics

### Part A — Deterministic / Seeded Impairments

Feasible with formula, units, distribution, seed policy, and independent statistical checks.

### Part B — BER / Bathtub

Conditional and analytically constrained.

User-provided benchmark:

```text
Current pipeline: about 6.32 ms / 512 symbols

Target BER  Approximate brute-force workload
1e-6        about 1e8 bits / 0.014 day
1e-9        about 1e11 bits / 14 days
1e-12       about 1e14 bits / 1.4e4 days
```

These values are planning evidence, not CI golden values. They reinforce the existing conclusion: very low BER cannot be inferred from a short direct Monte Carlo run.

Required path:

- Validated statistical or analytical method.
- Explicit assumptions and confidence limits.
- Empirical error rate must report sample count.
- Raw PAM4 SER/BER must not be described as PCIe post-FEC link reliability.

---

## 8. Phase 6 — Reproducibility

The infrastructure is feasible, but current results are not always pure functions of a visible config.

Two hidden/history-dependent sources are confirmed:

### Process-global RNG initialization

`window.py` calls `np.random.seed(7)` during module import.

This is a process-wide side effect. Scenario/Experiment code must not rely on importing the GUI to establish a hidden random state.

### PAM4 `old_phase` hysteresis

PAM4 phase selection may retain a previous phase when a new score does not exceed the previous score by the configured margin.

Therefore output can depend on historical path through `old_phase`.

Before Scenario round-trip claims are allowed, the design must either:

- Include all required prior state in the resolved Scenario/Run config; or
- Remove hidden path dependence from the pure experiment path.

Round-trip serialization alone is insufficient if it omits state that affects the result.

---

## 9. Phase 7 — Sweep

The algorithmic work is feasible.

User-provided benchmark:

```text
20 x 20 NRZ sweep:  about 2.5 s
20 x 20 PAM4 sweep: about 5.3 s
```

This suggests current performance is not a blocker for modest deterministic grids. The result is not yet a CI performance guarantee.

The phase still requires:

- Stable objectives.
- Scenario/Experiment identity.
- Progress and cancellation.
- Invalid-result handling.
- Clear statement that the result is a simulated optimum within the configured search space.

---

## 10. Remaining Product Bugs and Technical Debt

### Preset 10 requested/resolved mismatch

Current preset table requests `-9.5 dB` de-emphasis, but `db_to_taps()` clips the corresponding post-cursor magnitude at `0.3`, producing approximately `-7.96 dB`.

A product decision is required:

- Change the table label/value.
- Change the constraint.
- Display requested and resolved values separately.
- Explicitly mark the table as approximate.

The mismatch must not remain silent.

### C-1 slider dead zone

The slider can reach approximately `-0.30`, while the dB conversion path saturates near the tap corresponding to 6 dB preshoot. Beyond that point, displayed tap values can change while the waveform does not.

The future fix must choose one clear UX:

- Reduce the slider range.
- Remove the intermediate saturation where technically justified.
- Display saturation/clamping explicitly.

### CTLE identity aliasing

`apply_ctle(gain <= 0)` returns the original input object.

No future `none` or identity Channel/RX mode may copy this behavior accidentally. Copy-versus-alias must be an explicit contract.

### Dead code candidates

Mechanical cleanup candidates include:

- Unused `is_first_after_transition`.
- Overwritten `eye_height` local value.
- Currently unreachable Gen6 sum-scaling branch under per-tap clipping.
- Unused or overwritten PAM4 controller locals.
- Refactor leftovers only kept alive by boundary tests.

Dead-code cleanup must remain separate from numerical or behavioral changes.

---

## 11. Current Execution Order

The current approved implementation remains:

```text
Implementation 25 / Issue #60
Pattern Configuration Core
Contract revision 1.1
```

After Implementation 25, the next planning work is not immediately ChannelConfig code. The required sequence is:

```text
Issue #66 evidence gate and bug fix
-> Channel Interface / ChannelConfig docs-first contract
-> ChannelConfig pure core
-> Impulse Convolution
-> Synthetic/User Impulse
-> Issue #68 sampling contract and baseline migration
-> Cursor Analysis
```

Issue #67 must be resolved before the unified pipeline becomes the public boundary for Scenario or batch execution.

---

## 12. Merge Gate Additions

For intentional numerical changes, `Existing Behavior Compatibility` must be interpreted as one of:

1. Existing behavior is unchanged and validated; or
2. Existing behavior changes through an explicit baseline-migration PR containing old/new evidence, rationale, affected surfaces, and updated golden tests.

The following are prohibited:

- Updating expected values without explaining the model change.
- Relaxing tolerance to hide a phase or alignment error.
- Casting output solely to satisfy a mistaken contract.
- Treating user-provided benchmark numbers as compliance claims.
- Calling a greenfield PAM4 receiver a small extension of the current PAM4 pipeline.
