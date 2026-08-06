# Synthetic and User-defined Impulse Source Contract

> Contract ID：`pcie_eq-impulse-source-v1`  
> Contract revision：`1.0`  
> 文件狀態：Proposed implementation contract；合併後 Frozen  
> 適用 Repository：`Mike87117/PCIE-TX-EQ-Simulator`  
> Production baseline：`f88344f06b7f279b6117d699a9e3e3faa5a72939`／262 tests  
> Related Roadmap：Issue #48  
> Tracking Issue：Issue #82

---

## 1. 目的與邊界

本文件定義 GUI-independent deterministic discrete impulse source v1，使測試、教學與未來 Channel adapter 能以單一、可序列化、可驗證的 boundary 建立 synthetic 或 user-defined impulse values。

本 Contract 只建立 impulse source，不執行 waveform convolution，不修改 ChannelConfig，也不定義實際 cable、PCB、connector、S-parameter 或 PCIe Reference Channel。

文件合併後，production implementation 只能依本文件修改 pure code 與 tests。若 NumPy behavior、existing repository boundary 或 validation evidence 與本文件衝突，必須停止並由 Planner／Reviewer 另開 docs-only PR；不得自行修改 source taxonomy、formula、dtype、metadata、normalization、serialization 或 claims。

### 1.1 模型等級

```text
project-owned discrete impulse source / deterministic teaching primitive
```

### 1.2 Allowed claims

- Deterministic discrete impulse source。
- Explicit sample-step metadata and lag-zero index。
- Exact synthetic formula and user-defined tap preservation after float64 canonicalization。
- Exact shape、dtype、copy、empty、all-zero and serialization behavior。

### 1.3 Forbidden claims

- PCIe-compliant channel、PCI-SIG Reference Channel 或 compliance impulse。
- Physical insertion loss、trace length、connector／via loss 或 S-parameter behavior。
- Sample interval 必然代表 seconds、UI、Hz、baud 或 physical distance。
- Synthetic source 已與真實硬體 correlation。
- User-defined values 已經 normalized、validated as physical、causal 或 passive。
- Frequency-domain synthesis、continuous-time impulse 或 automatic resampling。

---

## 2. Evidence Registry

| Evidence | Access | Contract relevance |
|---|---|---|
| `docs/TECHNICAL_AUDIT_2026-08-06.md` | Repository | Step 2.6 requires numeric input、finite values、sample interval、time-zero、normalization、copy、empty and all-zero policy |
| `docs/IMPULSE_RESPONSE_CONVOLUTION_CONTRACT.md` | Repository | Existing convolution uses explicit `impulse_zero_index` and sample-index-domain semantics |
| `pcie_eq/impulse_convolution.py` | Repository | Future source result must provide values and zero-index metadata without duplicating convolution |
| NumPy array／dtype／finiteness behavior pinned by repository CI | Dependency evidence | Exact float64 output、C-contiguity and finite validation |

### 2.1 Independent validation strategy

- Hardcoded single-tap vectors。
- Hardcoded exponential-postcursor vectors。
- Test-side direct formula for additional exponential cases。
- User-defined canonicalization、copy and mutation-isolation tests。
- Sample interval、zero-index、all-zero and serialization golden cases。
- AST/module-boundary validation。

---

## 3. Frozen Scope

V1 supports exactly：

```text
single_tap
exponential_postcursor
user_defined
```

V1 excludes：

```text
Gaussian impulse
raised-cosine or pulse-shaping impulse
frequency-domain synthesis
FFT or inverse FFT
Touchstone / S-parameters
measurement waveform import
noise or jitter
random impulse generation
resampling or interpolation
normalization other than none
ChannelConfig impulse_response integration
waveform convolution
cursor extraction
GUI or pipeline integration
```

V1 does not modify `pcie_eq.impulse_convolution`、`pcie_eq.channel_config`、models、pipeline or GUI。

---

## 4. Frozen Public API

Production implementation adds：

```text
pcie_eq/impulse_source.py
```

```python
IMPULSE_SOURCE_CONTRACT_ID = "pcie_eq-impulse-source-v1"

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

    def __post_init__(self) -> None: ...
    def to_dict(self) -> dict[str, object]: ...

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ImpulseSourceConfig": ...

@dataclass(frozen=True)
class ImpulseSourceResult:
    values: numpy.ndarray
    resolved_config: ImpulseSourceConfig
    model_level: str


def build_impulse(config: ImpulseSourceConfig) -> ImpulseSourceResult: ...
```

Exact `__all__` order：

```python
[
    "IMPULSE_SOURCE_CONTRACT_ID",
    "ImpulseSourceConfig",
    "ImpulseSourceResult",
    "build_impulse",
]
```

V1 provides no subclass hierarchy、plugin registry、async API、random generator or hidden source defaults beyond the dataclass defaults shown above。

---

## 5. Common Configuration Fields

### 5.1 `schema_version`

- Exact Python `str` only。
- Exact value：`pcie_eq-impulse-source-v1`。
- Non-string：`TypeError`。
- Unknown string：`ValueError`。
- No fallback、alias or migration guessing。

### 5.2 `source_type`

- Exact Python `str` only。
- Case-sensitive exact strings：

```text
single_tap
exponential_postcursor
user_defined
```

- Unsupported、empty、case mismatch or whitespace variant：`ValueError`。
- No trim、case conversion or alias。

### 5.3 `sample_interval`

Accepted input type：

```text
exact Python int or exact Python float
```

Rules：

- `bool` and NumPy scalar types are rejected with `TypeError`。
- Must be finite and strictly `> 0`；otherwise `ValueError`。
- Constructor canonicalizes accepted values to exact Python `float` using `float(value)`。
- Conversion result must remain finite and `> 0`。
- `1` and `1.0` therefore resolve identically to `1.0`。
- No unit conversion occurs。

Meaning：

- It is metadata describing one common discrete sample step。
- V1 does not claim seconds、UI、Hz or any physical unit。
- It does not change generated tap values。
- It is not multiplied into amplitude or convolution output。
- It does not trigger resampling or interpolation。

### 5.4 `impulse_zero_index`

- Exact Python `int` only。
- `bool` and NumPy integer scalars：`TypeError`。
- Must be `>= 0`；negative：`ValueError`。
- Must be `< resolved impulse length`；otherwise `ValueError`。
- It explicitly identifies the tap representing lag 0。
- The implementation must not infer zero index from argmax、first nonzero、center index or any heuristic。

### 5.5 `normalization`

- Exact Python `str` only。
- V1 accepts only exact `none`。
- Any other string、case variant or whitespace variant：`ValueError`。
- No peak、sum、sum-absolute、energy、RMS or area normalization occurs。
- This field is retained in the frozen schema to make the absence of normalization explicit and serializable。

---

## 6. Numeric Scalar Canonicalization

The following fields use the numeric scalar rule when relevant：

```text
amplitude
decay_ratio
```

Accepted input type：

```text
exact Python int or exact Python float
```

Rules：

- `bool` and NumPy scalar types are rejected with `TypeError`。
- Input must be finite；otherwise `ValueError`。
- Constructor canonicalizes to exact Python `float`。
- Conversion result must remain finite；otherwise `ValueError`。
- Negative zero is allowed and preserved according to Python float semantics。
- No clipping、rounding policy、unit scaling or tolerance correction is applied。

---

## 7. Source-specific Relevance Contract

Fields irrelevant to a selected source must be exact `None`。The constructor must reject irrelevant non-`None` fields instead of silently ignoring them。

### 7.1 `single_tap`

Required relevant fields：

```text
length: exact Python int >= 1
amplitude: numeric scalar canonicalized to Python float
```

Required irrelevant fields：

```text
decay_ratio is None
values is None
```

Additional rules：

- `impulse_zero_index < length`。
- `length` rejects bool and NumPy integer scalars。
- Negative or zero length：`ValueError`。
- Negative、positive and zero amplitude are all valid。

Formula：

```text
values = zeros(length, dtype=float64)
values[impulse_zero_index] = amplitude
```

This source is a single located tap。Amplitude `0.0` intentionally produces an all-zero impulse and is not automatically corrected。

### 7.2 `exponential_postcursor`

Required relevant fields：

```text
length: exact Python int >= 1
amplitude: numeric scalar canonicalized to Python float
decay_ratio: numeric scalar canonicalized to Python float
```

Required irrelevant field：

```text
values is None
```

Additional rules：

- `impulse_zero_index < length`。
- `0.0 <= decay_ratio < 1.0`。
- Ratio below zero or greater than／equal to one：`ValueError`。
- Negative、positive and zero amplitude are all valid。

Formula for output index `n`：

```text
if n < impulse_zero_index:
    values[n] = 0.0
else:
    values[n] = amplitude * decay_ratio ** (n - impulse_zero_index)
```

Special cases：

- `decay_ratio == 0.0` leaves only the zero-index tap nonzero when amplitude is nonzero。
- `amplitude == 0.0` produces an all-zero impulse。
- Underflow to exact zero at a distant postcursor is allowed。
- No precursor is synthesized；precursor behavior belongs to `user_defined` in V1。

### 7.3 `user_defined`

Required relevant field：

```text
values: non-empty 1D real numeric array-like
```

Required irrelevant fields：

```text
length is None
amplitude is None
decay_ratio is None
```

Accepted constructor input for `values`：

- Python list。
- Python tuple。
- 1D NumPy ndarray。
- Non-contiguous 1D NumPy ndarray view。
- Boolean、signed integer、unsigned integer and floating dtype。

Rejected constructor input：

- Scalar or `ndim != 1`：`ValueError`。
- Complex、string、object or other non-real-numeric dtype：`TypeError`。
- Empty sequence：`ValueError`。
- Any NaN／Inf before conversion：`ValueError`。
- Any NaN／Inf after float64 conversion：`ValueError`。

Canonicalization：

1. Materialize with `numpy.asarray(values)`。
2. Validate one-dimensional real numeric non-empty finite input。
3. Convert into a new exact `numpy.float64` array。
4. Revalidate finiteness after conversion。
5. Store an immutable canonical `tuple[float, ...]` of Python floats in the frozen config。

Consequences：

- Caller list／ndarray mutations after construction cannot alter the config。
- Input integer precision beyond float64 representation is not guaranteed；V1 guarantees the canonical float64 result, not integer bit-exact preservation。
- Signed zero and finite float64 values follow NumPy／Python float conversion behavior。
- All-zero values are valid。
- Resolved impulse length is `len(config.values)`；the `length` field remains `None` for this source。
- `impulse_zero_index < len(config.values)`。

---

## 8. Constructor Validation and Canonicalization Order

`ImpulseSourceConfig.__post_init__()` uses this conceptual order：

1. Validate exact schema type and value。
2. Validate exact source type。
3. Validate and canonicalize sample interval。
4. Validate exact normalization。
5. Validate zero-index exact type and nonnegative value。
6. Validate source-specific field relevance before touching an irrelevant `values` object。
7. Validate and canonicalize relevant scalar fields。
8. For `user_defined` only，materialize、validate and canonicalize values。
9. Validate zero index against resolved length。
10. Store only canonical immutable field values through frozen-dataclass-safe assignment。

When source type is not `user_defined`，a non-`None` `values` field is rejected as irrelevant without array conversion。

When source type is `user_defined`，`length`、`amplitude` or `decay_ratio` non-`None` is rejected before values conversion。

---

## 9. `build_impulse()` Validation and Dispatch Order

`build_impulse(config)` uses this order：

1. Require exact config type：`type(config) is ImpulseSourceConfig`；subclass or other type → `TypeError`。
2. Defensively revalidate the original frozen config and all source-specific relevance rules。
3. Rebuild a new exact resolved config from canonical field values。
4. Determine exact resolved length。
5. Allocate／construct a new float64 output according to the exact source formula。
6. Validate final output contract。
7. Return frozen result。

A corrupted frozen config must fail before output allocation or formula evaluation。

The production implementation must not call convolution、FFT、interpolation or any channel helper。

---

## 10. Sample Interval and Time-zero Semantics

### 10.1 Sample interval

- `sample_interval` is positive finite metadata carried by the source config。
- All taps within one result use the same step。
- V1 does not define a physical unit。
- V1 does not compare this interval with waveform metadata because no Channel adapter is included。
- Future integration must validate source and waveform interval compatibility before convolution。
- No tolerance comparison is frozen in this contract。

### 10.2 Time zero

Let：

```text
z = impulse_zero_index
```

Then：

```text
values[z] corresponds to lag 0
values[z - 1] corresponds to one negative sample step, when present
values[z + 1] corresponds to one positive sample step, when present
```

This is index metadata only。No seconds／UI conversion occurs。

---

## 11. Dtype Contract

All result values use exact：

```python
numpy.dtype(numpy.float64)
```

Rules：

- Synthetic values are allocated directly as float64。
- User-defined bool／integer／float16／float32／float64 inputs all canonicalize to float64。
- No dtype-preservation claim is made for user input。
- Complex input is rejected before conversion。
- No post-build cast may hide an incorrectly produced dtype；the final validator must reject a non-float64 internal result with `RuntimeError`。

Config metadata scalar fields are canonical exact Python types：

```text
sample_interval: float
impulse_zero_index: int
normalization: str
length: int or None
amplitude: float or None
decay_ratio: float or None
values: tuple[float, ...] or None
schema_version: str
source_type: str
```

---

## 12. Output Contract

`build_impulse()` returns exact `ImpulseSourceResult` with：

```text
values: exact numpy.ndarray
resolved_config: new exact valid ImpulseSourceConfig
model_level: "project_owned_discrete_impulse_source"
```

### 12.1 Values requirements

- Exact `numpy.ndarray`；ndarray subclass is invalid。
- One-dimensional。
- Shape exact `(resolved_length,)`。
- Exact `numpy.float64` dtype。
- C-contiguous。
- Finite。
- Newly allocated independent storage。
- Never the same object as any constructor input ndarray。
- Never shares memory with any constructor input ndarray。
- Mutation of result values cannot alter the config、canonical values tuple or caller input。

### 12.2 Internal failure policy

If an internal builder produces wrong exact type、shape、dtype、layout、finiteness or ownership，`build_impulse()` raises `RuntimeError`。

No silent cast、copy、reshape、normalization or repair is allowed after internal output construction。

Creating the required new float64 array according to the source formula is normal construction，not a repair path。

### 12.3 Frozen result

`ImpulseSourceResult` is frozen but its ndarray contents remain mutable。Changing `result.values` is allowed and must not affect `resolved_config` or any future newly built result。

---

## 13. Empty and All-zero Policy

### 13.1 Empty

Empty impulse is invalid for every source type：

- Synthetic `length < 1`：`ValueError`。
- User-defined empty values：`ValueError`。
- Zero index cannot be validated against an empty length and no empty result is returned。

### 13.2 All zero

All-zero impulse is valid：

- `single_tap` with amplitude `0.0`。
- `exponential_postcursor` with amplitude `0.0`。
- `user_defined` with all canonical values equal to zero。

The implementation must not：

- Insert a nonzero main cursor。
- Normalize the result。
- Reject it as physically invalid。
- Change zero index。

---

## 14. Normalization Policy

V1 normalization is exactly：

```text
none
```

Therefore：

- Single-tap amplitude is used directly。
- Exponential amplitude is used directly at zero index。
- User-defined values are used directly after float64 canonicalization。
- No sum、peak、energy、area or sample-interval scaling occurs。
- No all-zero special normalization path exists。

Any future normalization requires a contract revision or new schema version。

---

## 15. Serialization

Canonical dictionary exact keys and order：

```text
schema_version
source_type
sample_interval
impulse_zero_index
normalization
length
amplitude
decay_ratio
values
```

### 15.1 `to_dict()`

- Returns a new dictionary on every call。
- Contains exactly the nine canonical keys in specified order。
- Uses only JSON-safe string、integer、float、list and `None` values。
- `values` is a newly allocated list of Python floats or `None`。
- Mutating returned dictionary or values list cannot alter the config。

### 15.2 `from_dict()`

- Input must be `collections.abc.Mapping`；otherwise `TypeError`。
- Key set must exactly match canonical set。
- Missing／extra keys：`ValueError` and message lists affected keys。
- Wrong schema type：`TypeError`。
- Unknown schema string：`ValueError`。
- Semantic validation、relevance validation and canonicalization occur through constructor。
- No aliases、camelCase、nested parameters or migration guessing。

### 15.3 Round-trip

Input and resolved configs must satisfy：

```python
restored = ImpulseSourceConfig.from_dict(config.to_dict())
assert restored == config
assert restored is not config
```

For user-defined config：

```python
assert type(restored.values) is tuple
assert all(type(value) is float for value in restored.values)
```

---

## 16. Canonical Golden Cases

### 16.1 Default config

```python
config = ImpulseSourceConfig()
```

Resolved：

```text
source_type = single_tap
sample_interval = 1.0
impulse_zero_index = 0
normalization = none
length = 1
amplitude = 1.0
values = [1.0]
dtype = float64
```

### 16.2 Single tap

```text
source_type = single_tap
length = 5
impulse_zero_index = 2
amplitude = -0.5
```

Expected：

```text
values = [0.0, 0.0, -0.5, 0.0, 0.0]
shape = (5,)
dtype = float64
```

### 16.3 Single tap at boundaries

```text
length = 4, zero_index = 0, amplitude = 2.0
values = [2.0, 0.0, 0.0, 0.0]

length = 4, zero_index = 3, amplitude = 2.0
values = [0.0, 0.0, 0.0, 2.0]
```

### 16.4 Exponential postcursor

```text
source_type = exponential_postcursor
length = 6
impulse_zero_index = 2
amplitude = 1.0
decay_ratio = 0.5
```

Expected：

```text
values = [0.0, 0.0, 1.0, 0.5, 0.25, 0.125]
shape = (6,)
dtype = float64
```

### 16.5 Exponential ratio zero

```text
length = 5
impulse_zero_index = 1
amplitude = -2.0
decay_ratio = 0.0
values = [0.0, -2.0, 0.0, 0.0, 0.0]
```

### 16.6 User-defined

Constructor input：

```python
values = numpy.array([0, -1, 4, 2], dtype=numpy.int16)
```

Resolved config and result：

```text
config.values = (0.0, -1.0, 4.0, 2.0)
impulse_zero_index = 2
result.values = [0.0, -1.0, 4.0, 2.0]
result dtype = float64
```

### 16.7 Sample interval metadata

```text
sample_interval input = 2
resolved sample_interval = 2.0
```

Generated values remain identical to the same source using `sample_interval = 1.0`。

---

## 17. Required Production Tests

Future implementation tests at minimum：

### 17.1 Public surface

- Exact public API and `__all__` order。
- Frozen config and result dataclasses。
- Exact config type and subclass rejection。
- Module boundary test。

### 17.2 Common validation

- Schema type／version。
- Source type type／case／whitespace／unsupported values。
- Sample interval exact Python int／float acceptance and canonicalization。
- Sample interval bool／NumPy scalar／nonfinite／zero／negative rejection。
- Normalization exact `none` only。
- Zero-index exact Python int、bool／NumPy scalar rejection、negative and out-of-range cases。
- Corrupted frozen config defensive revalidation before output allocation。

### 17.3 Relevance validation

For every source type：

- Relevant fields accepted。
- Each irrelevant field independently rejected when non-`None`。
- Multiple irrelevant fields rejected deterministically。
- Irrelevant `values` object not materialized for synthetic sources。
- User-defined irrelevant scalar fields rejected before values conversion。

### 17.4 Single-tap validation

- Default golden result。
- Hardcoded negative amplitude vector。
- Positive、negative、signed zero and zero amplitude。
- First and last valid zero index。
- Length bool／NumPy scalar／zero／negative rejection。
- Exact float64、shape、C-contiguous and finite output。

### 17.5 Exponential validation

- Hardcoded canonical vector。
- Test-side direct formula additional vector。
- Ratio `0.0` special case。
- Ratio below zero、equal one、above one、NaN、Inf rejection。
- Positive、negative and zero amplitude。
- Nonzero zero index and no synthesized precursor。
- Underflow remains finite and accepted。

### 17.6 User-defined validation

- List、tuple、ndarray and non-contiguous view acceptance。
- Bool、signed、unsigned、float16、float32、float64 input matrix → exact float64 result。
- Scalar、2D、complex、string、object、empty、NaN、Inf rejection。
- Conversion overflow to nonfinite rejection。
- Input list and ndarray mutation isolation after config construction。
- Config canonical values exact tuple of Python floats。
- First and last valid zero index。
- All-zero values accepted。

### 17.7 Output validation

- Exact ndarray type；subclass rejection through monkeypatched／internal builder seam if one exists。
- Exact shape、dtype、C-contiguity and finiteness。
- New result storage on every call。
- Two calls with same config do not share values memory。
- Result mutation does not affect config or later result。
- Exact model-level string。
- New resolved config object and config round-trip。

### 17.8 Serialization

- Canonical nine keys and exact order。
- New dictionary every call。
- New values list every call。
- Dictionary／list mutation isolation。
- Synthetic and user-defined round-trip。
- Resolved config round-trip。
- Non-mapping、missing／extra keys、wrong version type and unknown version rejection。

### 17.9 Regression

- Existing 262 tests all pass and total count increases。
- `python -c "import main"` passes。
- GUI smoke passes even though GUI is unchanged。
- GitHub Actions Windows CI passes。

Expected vectors must be hardcoded or produced by a test-side independent formula。Tests must not call production API to generate expected values。

---

## 18. Module and File Boundary

Implementation may add exactly：

```text
pcie_eq/impulse_source.py
tests/test_impulse_source.py
tests/test_impulse_source_module_boundary.py
```

Production module may depend only on：

```text
Python standard library
NumPy
```

It must not import：

```text
PyQt
PySide
pyqtgraph
main
pcie_eq.gui
pcie_eq.pipeline
pcie_eq.models
pcie_eq.channel
pcie_eq.channel_config
pcie_eq.impulse_convolution
controller modules
```

Implementation must not modify：

```text
pcie_eq/impulse_convolution.py
pcie_eq/channel.py
pcie_eq/channel_config.py
pcie_eq/models.py
pcie_eq/pipeline.py
pcie_eq/gui/**
main.py
docs/**
PCIE-TX-EQ-Simulator_Product_Roadmap.md
.github/workflows/**
```

---

## 19. Future Integration Boundary

A later contract may integrate an `ImpulseSourceResult` with convolution or ChannelConfig。That later adapter must independently define：

- Waveform sample interval metadata source。
- Exact interval compatibility comparison。
- How `impulse_zero_index` maps into `ImpulseConvolutionConfig`。
- Which convolution mode is used by ChannelConfig。
- Output length and alignment exposed to GUI／pipeline。
- Serialization nesting and schema versioning。

This V1 source contract does not authorize or assume those choices。

---

## 20. Implementation PR Contract

After this document is merged，Gemini implementation uses：

```text
Branch: feature/implement-impulse-source-core
Draft PR title: feat: add synthetic and user-defined impulse source core
```

PR body must include：

```text
Closes <implementation issue>
Related to #48
Contract: pcie_eq-impulse-source-v1 revision 1.0
Contract merge: <authoritative merge SHA>
```

It must report base／head SHA、exact changed files、source formula evidence、metadata／dtype／copy evidence、serialization、pytest count、GitHub Actions run、import result、GUI smoke and `git diff --check`。

Gemini must stop after opening Draft PR and must not mark ready、merge、close the issue or begin ChannelConfig／convolution integration。

---

## 21. Acceptance Gate

Implementation passes only when：

- Exact v1 API、source taxonomy、formulas and relevance rules are implemented。
- Sample interval、zero-index and normalization metadata are exact。
- User-defined input canonicalizes to immutable config tuple and independent float64 output。
- Empty、all-zero、dtype、copy and serialization contracts are exact。
- Existing 262 tests pass and total tests increase。
- Changed files are exactly the three allowed new files。
- GitHub Actions、import、GUI smoke and diff check pass。

---

## 22. Stop Conditions

Stop and request a docs-only correction when：

- Float64 canonicalization cannot be applied without violating an existing required behavior。
- User-defined constructor canonicalization cannot be made immutable and serializable within the file boundary。
- Sample interval metadata would require physical-unit interpretation for correctness。
- A hidden normalization or clipping path would be required。
- Existing repository imports force GUI、pipeline、ChannelConfig or convolution coupling。
- A source formula requires an unapproved external specification or physical model claim。

Production code must not change the frozen contract to work around these conditions。
