# Sampling Phase Contract

Contract ID: `pcie_eq-sampling-phase-v1`  
Revision: `1.0`

Related tracking: Issue #97  
Design gate: Issue #68  
Roadmap: Issue #48

## 1. Purpose

This document freezes the project-owned sampling-phase coordinate system used by NRZ receiver sampling, NRZ phase-sensitive eye metrics, NRZ eye rendering alignment, future cursor extraction, and PAM4 common t-center representation.

This contract exists because the pre-contract code used incompatible reference frames:

- NRZ DFE sampled with `symbol_index * spb + sampling_phase`.
- NRZ eye metrics built 2-UI traces at symbol boundaries and sampled `center_idx = seg_len // 2`; with `eye_ui == 2`, that is `trace_start + spb`, which is the next symbol's phase 0 rather than the same symbol-local phase used by DFE.
- NRZ line-eye rendering visually placed x=1 UI at the middle of those symbol-boundary traces.
- PAM4 already used integer candidate phases `0 .. spb - 1`, but with a separate common-t-center resolver and hysteresis algorithm.

Revision 1.0 defines one coordinate representation. It does not claim PCIe receiver compliance and does not implement a CDR, PLL, timing recovery loop, or fractional interpolation.

## 2. Model level and claims

Model level:

`project_owned_discrete_sampling_phase`

Allowed claims:

- deterministic project-owned sampling coordinate;
- consistent integer sample offset representation;
- common reference frame across project NRZ sampling consumers;
- PAM4 may share the representation while retaining a different resolver.

Forbidden claims:

- PCI-SIG reference receiver behavior;
- PCIe compliance sampling point;
- recovered-clock or CDR behavior;
- physical timing accuracy in seconds;
- interpolation-accurate fractional-UI sampling;
- automatic channel/group-delay compensation.

## 3. External supporting evidence

The following external sources support only the design principle that receiver decision timing affects eye/receiver measurements and therefore must be defined explicitly. They are not numerical or compliance oracles for this project.

1. Tektronix, **Anatomy of an Eye Diagram: How to Construct & Trigger**  
   https://www.tek.com/en/documents/application-note/anatomy-eye-diagram

   Relevant principle: a receiver/BERT decision point is placed in time and voltage within the eye, and moving that decision point changes the observed error behavior.

2. Keysight PLTS Help, **Analyzing Data using Eye Diagrams**  
   https://helpfiles.keysight.com/csg/N1930xB/Analyzing/Analyzing_Data_using_Eye_Diagrams.html

   Relevant principle: receiver sample timing is configurable and measurement results for skewed eyes can vary with the selected timing.

3. Keysight FlexDCA Help, **DFE Operator (Taps)**  
   https://helpfiles.keysight.com/scopes/FlexDCA-UG/Content/Topics/Signal-Processing/Signal-Processing-Operators/dfe-1.htm

   Relevant principle: the DFE slicer has a decision point in the symbol interval and timing offset changes that decision point.

These sources justify making sampling timing explicit. The exact coordinate system and algorithms below are project-owned choices.

## 4. Canonical coordinate system

For a waveform with exactly `spb` discrete samples per symbol:

```text
phase = integer sample offset from the first sample of that symbol
```

Valid range:

```text
0 <= phase < spb
```

Normalized reporting value:

```text
phase_ui = phase / spb
```

Examples for `spb = 32`:

```text
phase  0 -> 0.00000 UI
phase 16 -> 0.50000 UI
phase 28 -> 0.87500 UI
phase 31 -> 0.96875 UI
```

`phase == spb` is invalid. It is the next symbol's phase 0, not a valid phase value for the current symbol.

## 5. Exact type and validation contract

For any public sampling-phase validation introduced by Implementation 30B or later:

### `spb`

- exact `int` only;
- `bool` rejected;
- must be strictly positive.

### `phase`

- exact `int` only;
- `bool` rejected;
- must satisfy `0 <= phase < spb`.

Error taxonomy:

- wrong exact type: `TypeError`;
- invalid numeric range/value: `ValueError`.

Forbidden repair behavior:

- no clipping;
- no modulo wrapping;
- no negative-index normalization;
- no floating-to-integer cast;
- no string parsing;
- no schema guessing.

## 6. Domain and units

Revision 1.0 is sample-index-domain only.

The contract does not define:

- seconds;
- sample rate in Hz;
- baud-rate conversion;
- interpolation between samples;
- fractional sample positions.

`phase_ui` is a normalized reporting value only. It does not authorize a fractional-UI sampling implementation.

## 7. Group delay and waveform alignment

No automatic TX, Channel, CTLE, or other group-delay compensation is applied by the sampling coordinate system.

A delay introduced by the project waveform path is intentionally visible in the waveform. If a later phase resolver selects a different integer phase because of that delay, that is a resolved sampling choice, not hidden waveform realignment.

The sampling layer must not silently roll, shift, interpolate, or re-index the waveform to force a preferred phase.

## 8. Canonical symbol sample position

For symbol index `n` and resolved phase `p`:

```text
sample_position(n, p) = n * spb + p
```

This formula is the canonical NRZ decision-point coordinate.

Any consumer claiming to use the same resolved NRZ sampling phase must derive its phase-sensitive sample from this coordinate or an exactly equivalent index expression.

## 9. Warmup semantics

The current project uses a 20-symbol warmup in multiple receiver/metric contexts. Revision 1.0 freezes the phase-sensitive NRZ measurement interpretation as:

```text
warmup_symbols = 20
excluded symbol indices = 0 .. 19
first eligible symbol index = 20
```

Therefore, the first phase-sensitive NRZ sample is:

```text
20 * spb + sampling_phase
```

The warmup count applies to symbol indices, not to eye-trace start coordinates.

A 2-UI rendering trace may begin before the eligible decision point; that does not change which symbol index is considered the measured symbol.

## 10. Authoritative NRZ phase source

Implementation 30B does not add NRZ auto-centering.

For an NRZ simulation run, the authoritative resolved phase is:

```text
NrzSimulationConfig.sampling_phase
```

The existing GUI may continue to supply:

```text
SPB // 2
```

until a separately scoped manual-phase or auto-center feature is designed.

30B must not introduce a second hidden NRZ phase resolver.

## 11. NRZ DFE semantics

DFE input sampling uses the canonical coordinate:

```text
idx = n * spb + sampling_phase
```

The DFE corrected-sample and decision vectors inherit the same phase because they operate from those sampled values.

The DFE feedback equation itself is outside the scope of this contract and must remain numerically unchanged in 30B except for validation required to enforce the frozen sampling coordinate.

## 12. NRZ phase-sensitive eye metric semantics

Channel and CTLE NRZ eye metrics must use the same resolved `sampling_phase` as DFE.

For eligible symbol indices `n >= warmup_symbols`, define:

```text
center_samples = wave[n * spb + sampling_phase]
```

for indices that are within the waveform.

The following metrics are phase-sensitive and must be derived from these `center_samples`:

- `eye_height`;
- `margin_5pct`;
- `center_spread`.

Rail partition:

```text
upper = center_samples[center_samples >= 0]
lower = center_samples[center_samples < 0]
```

If both rails are present:

```text
eye_height = percentile(upper, 5) - percentile(lower, 95)
margin_5pct = eye_height / 2
```

If one rail is absent:

```text
eye_height = 0.0
margin_5pct = 0.0
```

`center_spread` remains:

```text
max(center_samples) - min(center_samples)
```

If no eligible center samples exist, the existing zero-fallback metric structure remains required.

### 12.1 `eye_max` / `eye_min`

`eye_max` and `eye_min` are frozen as 2-UI waveform-envelope diagnostics, not receiver decision-point metrics.

They may continue to be derived from all samples in the rendered/metric 2-UI trace population. They do not participate in phase resolution or future NRZ auto-center scoring.

Implementation 30B must document any numerical delta caused solely by re-centering the trace population around the resolved phase.

### 12.2 `error_count`

For non-DFE NRZ channel/CTLE eye metrics, the current value remains `0` in 30B. This contract does not introduce a slicer/error model for those waveform metrics.

## 13. NRZ 2-UI eye rendering alignment

The rendered line eye must visually center the same resolved phase used by DFE and phase-sensitive metrics.

For symbol index `n` and phase `p`:

```text
center = n * spb + p
trace_start = center - spb
trace_length = 2 * spb
```

Only traces satisfying:

```text
trace_start >= 0
trace_start + trace_length <= len(wave)
```

are eligible for rendering.

For the rendered x-axis:

```text
x = arange(2 * spb) / spb
```

Therefore x=1 UI corresponds to the sample at `center`, which is exactly the same resolved decision point used by phase-sensitive NRZ metrics.

The 2-UI eye is a display window around the decision point. It does not redefine the phase coordinate.

## 14. DFE display relationship

The existing DFE display is a symbol-index scatter of corrected samples rather than a continuous 2-UI line eye.

30B does not need to convert DFE display into a waveform eye. It must preserve that display model while ensuring those corrected samples originated from the same resolved NRZ phase.

## 15. PAM4 relationship

PAM4 shares the same exact phase representation:

```text
exact int
0 <= phase < spb
phase_ui = phase / spb for reporting
```

PAM4 keeps its existing common-t-center resolver and hysteresis behavior during 30B unless independent review discovers an implementation contradiction that must be separately frozen before code changes.

In particular, 30B must not force NRZ and PAM4 to share one phase-resolution algorithm.

Current PAM4 conceptual resolver remains:

- evaluate integer phase candidates;
- score each candidate with PAM4 minimum eye opening;
- deterministic tie handling around the current project center preference;
- apply the existing old-phase hysteresis margin.

The exact PAM4 regression baseline must remain unchanged in 30B.

## 16. Future NRZ auto-center contract

This section freezes the future resolver semantics but does not authorize implementation in 30B.

Candidate set:

```text
0 .. spb - 1
```

Objective for candidate phase `p`:

```text
score(p) = phase-aware NRZ eye_height at p
```

Invalid/no-two-rail candidate:

```text
score(p) = 0.0
```

Selection:

1. choose the candidate with maximum `score`;
2. score comparison uses exact computed project float values; no phase-update hysteresis is defined for NRZ v1;
3. if multiple candidates have equal maximum score, choose the phase with minimum absolute distance to `reference_phase`;
4. if still tied, choose the smaller integer phase.

Default future `reference_phase` when no previous/manual phase exists:

```text
spb // 2
```

The future resolver must return the same exact integer phase representation and must not introduce interpolation under contract v1.

## 17. Delayed waveform semantics

For a no-delay waveform, an analytically known best sample phase may be used as a validation oracle.

For a waveform delayed by a known integer sample offset, the phase-dependent opening must move accordingly within the modulo-one-symbol candidate domain.

The implementation must not automatically compensate the waveform before scoring. The observed shift in best phase is part of the validation evidence that the resolver is measuring the waveform it receives.

## 18. Current baseline inconsistency to preserve as migration evidence

Before 30B changes production behavior, tests must capture representative old behavior from baseline:

```text
main = 6fa7ba4bba1afaecc40590d20780badca9baf5e1
regression baseline = 305 tests
```

The old NRZ waveform metric behavior includes:

```text
seg_len = eye_ui * spb
trace_start = symbol boundary after warmup
center_idx = seg_len // 2
```

For `eye_ui == 2`, `center_idx == spb`, so the sampled center belongs to the next symbol's phase 0.

This old reference frame is not retained as a public legacy mode. It must be documented as an intentionally replaced inconsistent baseline.

## 19. Implementation 30B baseline migration requirements

30B is an explicit intentional baseline-change implementation, not a compatibility-preserving refactor.

It must:

1. preserve representative old NRZ outputs as named migration-golden evidence;
2. add new expected outputs under this contract;
3. identify every intentionally changed NRZ channel/CTLE metric and eye-render alignment;
4. keep TX EQ, Channel math, CTLE math, DFE feedback math, pattern generation, RNG behavior, and unrelated APIs unchanged;
5. not hide expected changes by widening tolerances;
6. preserve PAM4 numerical behavior;
7. keep current GUI controls and layout unless a minimal eye-render alignment change is mechanically necessary;
8. preserve public config names unless a separately approved contract requires otherwise.

## 20. Required validation matrix for 30B

At minimum, production implementation tests must cover all of the following.

### 20.1 Exact validation

- exact int `spb` accepted when positive;
- bool `spb` rejected;
- zero/negative `spb` rejected;
- exact int boundary phases `0` and `spb - 1` accepted;
- bool phase rejected;
- float phase rejected even if integral-valued;
- negative phase rejected;
- `phase == spb` rejected;
- no clipping/wrapping.

### 20.2 Known coordinate cases

For small `spb`, use hardcoded arrays proving:

```text
sample_position(n, p) = n * spb + p
```

including boundary phases.

### 20.3 Warmup

Prove symbol indices 0..19 are excluded and index 20 is the first eligible phase sample.

### 20.4 Ideal no-delay NRZ

Use an ideal known waveform where expected phase-sensitive samples and eye opening are analytically obvious.

### 20.5 Distinct-phase synthetic oracle

Construct a waveform where one integer phase has a hardcoded larger two-rail opening than all others.

This must be independent of the production phase resolver.

### 20.6 Shared NRZ phase

Prove for one run that:

- DFE input samples;
- channel metric center samples;
- CTLE metric center samples;

all correspond to the same configured phase coordinate.

### 20.7 Eye rendering

Prove the displayed 2-UI trace geometry places the resolved sample at x=1 UI.

### 20.8 Delay

Use a known integer-delayed synthetic waveform or project impulse/channel case to prove the phase-dependent best opening shifts without automatic compensation.

### 20.9 Migration golden

Store representative old-baseline outputs from `6fa7ba4...` and the corresponding new outputs. Assertions must distinguish intentional change from unrelated regression.

### 20.10 PAM4 regression

Existing PAM4 phase selection, tie behavior, hysteresis, score, and eye metrics remain unchanged.

### 20.11 General regression

- full pre-30B test suite remains accounted for;
- expected NRZ baseline assertions are deliberately updated, not deleted without replacement;
- `python -c "import main"` passes;
- GUI smoke passes;
- module-boundary tests remain clean.

## 21. Error/repair policy

Sampling-coordinate errors must fail explicitly.

Forbidden:

- silently clipping `phase`;
- silently converting float/string/bool to int;
- substituting `spb // 2` for an invalid explicitly supplied phase;
- wrapping phase modulo `spb`;
- silently shifting waveform alignment;
- falling back from the new phase-sensitive metric to the old `seg_len // 2` reference frame.

## 22. 30B implementation ownership and scope

Production implementation owner: **Gemini**.

Planner / contract owner / independent reviewer / merge gate: **ChatGPT**.

30B must be implemented in a separate branch and Draft PR after this contract is merged.

ChatGPT must not directly implement 30B production code except for an explicitly documented emergency exception approved in the roadmap. The mechanical 29C migration was such an exception and does not change the default responsibility split.

Exact 30B file boundary must be frozen in its implementation issue after contract review. It must not be guessed from this docs PR.

## 23. Non-scope

Revision 1.0 / Implementation 30A does not implement:

- production sampling changes;
- fractional sampling/interpolation;
- NRZ auto-center;
- CDR/PLL;
- PCIe reference receiver;
- cursor extraction;
- DFE adaptation;
- BER/bathtub;
- ChannelConfig GUI selection;
- impulse-channel GUI integration;
- Touchstone;
- measurement waveform import.

## 24. Exit gate

30A is complete only when:

- this exact contract is reviewed and merged;
- changed file boundary is docs-only;
- current `main` drift is rechecked;
- CI / import-main remain clean;
- Issue #97 closes;
- Roadmap #48 records the frozen contract revision and 30B as next production implementation;
- Issue #68 remains open until 30B completes the intentional baseline migration.
