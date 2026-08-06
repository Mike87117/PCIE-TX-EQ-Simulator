# Impulse Response Convolution Contract

> Contract ID：`pcie_eq-impulse-convolution-v1`  
> Contract revision：`1.0`  
> 文件狀態：Proposed implementation contract；合併後 Frozen  
> 適用 Repository：`Mike87117/PCIE-TX-EQ-Simulator`  
> Production baseline：`bd1765d1658806229233ed7cd01b50180bed1fd3`／247 tests  
> Related Roadmap：Issue #48  
> Tracking Issue：Issue #78

---

## 1. 目的與界線

本文件定義 GUI-independent discrete impulse convolution v1，使兩個一維實數離散序列可透過單一、可序列化、可驗證的 request／result boundary執行線性卷積。

本Contract是專案自有數值primitive，不是PCI-SIG channel specification、Reference Channel、S-parameter model、insertion-loss model或實際線材／PCB correlation model。

文件合併後，production implementation只能依本文件修改pure code與tests。若NumPy behavior、existing repository boundary或測試evidence與本文件衝突，必須停止並由Planner／Reviewer另開docs-only PR；不得自行修改mode、alignment、dtype、normalization、serialization或claims。

### 1.1 模型等級

```text
discrete linear convolution / project-owned numerical primitive
```

### 1.2 Allowed claims

- Deterministic discrete linear convolution primitive。
- Explicit `full`、wave-aligned `same`與full-overlap `valid` semantics。
- Explicit impulse lag-zero index與output start index。
- Exact dtype、shape、empty、copy與serialization contract。

### 1.3 Forbidden claims

- PCIe-compliant channel或PCI-SIG Reference Channel。
- Physical insertion loss、frequency response、trace length、connector／via loss或S-parameter behavior。
- Physical seconds、UI、Hz、baud或distance interpretation。
- Continuous-time convolution、automatic resampling或correlation result。
- Impulse response本身已經validated、normalized或代表真實硬體。

---

## 2. Evidence Registry

| Evidence | Access | Contract relevance |
|---|---|---|
| [NumPy 2.4 `numpy.convolve`](https://numpy.org/doc/2.4/reference/generated/numpy.convolve.html) | Public primary | Discrete linear convolution definition and full output length |
| [NumPy 2.4 `numpy.result_type`](https://numpy.org/doc/2.4/reference/generated/numpy.result_type.html) | Public primary | Common dtype promotion rule |
| `docs/CHANNEL_CONFIGURATION_CONTRACT.md` | Repository | Sample-index-domain boundary and no-physical-claim policy |
| `docs/TECHNICAL_AUDIT_2026-08-06.md` | Repository | Step 2.5 entry requirements and baseline migration rules |
| `pcie_eq/channel_config.py` | Repository | Existing GUI-independent request/result pattern and strict validation style |

NumPy documents `full`、`same`與`valid`, but this project only delegates `mode="full"`. Project `same` and `valid` are explicit slices of the full result so alignment remains tied to the waveform index and `impulse_zero_index`.

### 2.1 Independent validation strategy

- Test-side direct summation implementation for full convolution。
- Hardcoded full／same／valid vectors with a non-centered zero index。
- Delta impulse identity and alignment cases。
- Dtype、empty、ownership、serialization and helper-failure tests。
- Monkeypatch verification that production calls NumPy with exact `mode="full"` only。

---

## 3. Frozen Scope

V1 supports exactly:

```text
full
same
valid
```

V1 excludes:

```text
FFT convolution
streaming or stateful convolution
sample-rate conversion
interpolation
normalization
Touchstone
ChannelConfig impulse_response mode
GUI or pipeline integration
cursor extraction
frequency response
```

V1 does not modify `pcie_eq.channel_config`, `pcie_eq.channel`, models, pipeline or GUI.

---

## 4. Frozen Public API

Production implementation adds:

```text
pcie_eq/impulse_convolution.py
```

```python
IMPULSE_CONVOLUTION_CONTRACT_ID = "pcie_eq-impulse-convolution-v1"

@dataclass(frozen=True)
class ImpulseConvolutionConfig:
    mode: str = "full"
    impulse_zero_index: int = 0
    schema_version: str = IMPULSE_CONVOLUTION_CONTRACT_ID

    def __post_init__(self) -> None: ...
    def to_dict(self) -> dict[str, object]: ...

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ImpulseConvolutionConfig": ...

@dataclass(frozen=True)
class ImpulseConvolutionResult:
    values: numpy.ndarray
    resolved_config: ImpulseConvolutionConfig
    output_start_index: int
    model_level: str


def convolve_impulse(
    wave,
    impulse,
    config: ImpulseConvolutionConfig,
) -> ImpulseConvolutionResult: ...
```

Exact `__all__` order：

```python
[
    "IMPULSE_CONVOLUTION_CONTRACT_ID",
    "ImpulseConvolutionConfig",
    "ImpulseConvolutionResult",
    "convolve_impulse",
]
```

`ImpulseConvolutionConfig.__post_init__()` validates all configuration fields possible without array lengths. `convolve_impulse()` defensively revalidates the original config before converting either input and completes the impulse-length-dependent zero-index check after impulse validation.

V1 provides no subclass hierarchy、plugin registry、async API or hidden defaults beyond the dataclass defaults shown above。

---

## 5. Configuration Fields

### 5.1 `schema_version`

- Exact Python `str` only。
- Exact value：`pcie_eq-impulse-convolution-v1`。
- Non-string：`TypeError`。
- Unknown string：`ValueError`。
- No fallback or migration guessing。

### 5.2 `mode`

- Exact Python `str` only。
- Case-sensitive exact strings：`full`、`same`、`valid`。
- Unsupported、empty、case mismatch or whitespace variant：`ValueError`。
- No trim、case conversion or alias。

### 5.3 `impulse_zero_index`

- Exact Python `int` only。
- `bool` and NumPy integer scalars：`TypeError`。
- Constructor requires `>= 0`; negative：`ValueError`。
- `convolve_impulse()` requires `< len(impulse)` after impulse validation; otherwise `ValueError`。
- It identifies the impulse tap representing lag 0。
- The implementation must not infer it fromargmax、first nonzero、center index or any heuristic。

---

## 6. Input Contract

`convolve_impulse(wave, impulse, config)` accepts two 1D real numeric array-like inputs。

### 6.1 Accepted input

For both wave and impulse：

- Python list／tuple。
- 1D NumPy ndarray。
- Boolean、signed integer、unsigned integer and floating dtype。
- Non-contiguous 1D ndarray views。

Wave may be empty。Impulse must contain at least one element。All-zero impulse is valid。

### 6.2 Rejection

For either input：

- Scalar or `ndim != 1`：`ValueError`。
- Complex、string、object or other non-real-numeric dtype：`TypeError`。
- Any NaN／Inf element：`ValueError`。

Additional impulse rule：

- Empty impulse：`ValueError`。

### 6.3 Ownership

- Caller wave and impulse are never modified。
- Returned values never share memory with caller ndarray inputs。
- Returned values are never the same object as either caller input。
- Output is a new C-contiguous ndarray。

---

## 7. Fixed Validation and Dispatch Order

`convolve_impulse()` uses this order：

1. Require exact config type：`type(config) is ImpulseConvolutionConfig`; subclass or other type → `TypeError`。
2. Defensively revalidate original schema、mode and zero-index type／nonnegative value。
3. Materialize and validate wave。
4. Materialize and validate impulse。
5. Reject empty impulse and validate `impulse_zero_index < len(impulse)`。
6. Resolve exact output dtype。
7. Build a new resolved config。
8. If wave is empty, return the frozen empty result without calling NumPy convolution。
9. Convert working arrays to the resolved dtype。
10. Call the production helper with exact `numpy.convolve(wave_work, impulse_work, mode="full")`。
11. Validate raw full helper output。
12. Apply exact project slicing for the requested mode。
13. Validate final output and return result。

Config validation must occur before either input conversion so a corrupted frozen config is rejected deterministically。

Wave validation precedes impulse validation; when both inputs are invalid, the wave error is raised first。

---

## 8. Sample Interval and Units

V1 is sample-index domain：

- Wave and impulse must already use the same implicit sample grid。
- One index step represents one common discrete sample step。
- No sample-interval field is added in V1。
- No resampling、interpolation or tolerance comparison occurs。
- No multiplication by `Δt` occurs；this API implements discrete-time convolution, not continuous-time numerical integration。
- Future Scenario／measurement adapters carrying physical sample metadata must validate compatibility before calling this core。

No result from this API alone may be interpreted in seconds、UI、Hz or physical distance。

---

## 9. Dtype Contract

After successful input validation：

```python
promoted = numpy.result_type(wave_array.dtype, impulse_array.dtype)
expected_dtype = (
    promoted
    if promoted.kind == "f"
    else numpy.dtype(numpy.float64)
)
```

Rules：

- Both working arrays are explicitly converted to `expected_dtype` before convolution。
- Boolean／integer-only combinations promote to exact `numpy.float64`。
- Floating combinations follow NumPy result-type promotion。
- Examples：
  - float16 + float16 → float16。
  - float32 + float32 → float32。
  - float32 + float64 → float64。
  - float32 + int16 → NumPy result type, expected float32 under the pinned CI behavior。
  - int16 + uint8 → float64。
  - bool + bool → float64。
- Empty wave follows the same dtype resolution using the non-empty impulse dtype。
- Complex inputs are rejected before dtype resolution。
- No post-convolution cast is permitted to hide helper mismatch。

---

## 10. Mathematical and Alignment Contract

Let：

```text
N = len(wave)
M = len(impulse)
z = impulse_zero_index
```

The full convolution is：

```text
y[j] = Σ wave[k] × impulse[j-k]
```

Production must call only：

```python
numpy.convolve(wave_work, impulse_work, mode="full")
```

It must not call NumPy `mode="same"` or `mode="valid"`。

### 10.1 `full`

For non-empty wave：

```text
output length = N + M - 1
values = full_result
output_start_index = -z
```

`output_start_index` is the coordinate, in waveform sample-index units, represented by `values[0]`。

### 10.2 `same`

For non-empty wave：

```text
output length = N
values = full_result[z : z + N]
output_start_index = 0
```

The returned values correspond exactly to waveform coordinates `0 ... N-1`。

This semantics intentionally differs from NumPy `mode="same"` when impulse is longer than wave or when the requested zero index is not NumPy's centered crop。

### 10.3 `valid`

For non-empty wave：

- Require `N >= M`; otherwise `ValueError`。

```text
output length = N - M + 1
values = full_result[M - 1 : N]
output_start_index = M - 1 - z
```

Only positions where the entire impulse support lies within the waveform support are retained。

This semantics intentionally does not swap operands when impulse is longer than wave。

### 10.4 Empty wave

After validating a non-empty impulse and valid zero index, all modes return：

```text
values shape = (0,)
values dtype = resolved expected dtype
output_start_index = 0
model_level = discrete_linear_convolution
```

The implementation must not call NumPy convolution for an empty wave。

---

## 11. Normalization, Padding and Truncation

- No peak、sum、energy or area normalization。
- No implicit sample-interval scaling。
- No trimming of leading or trailing impulse zeros。
- No impulse padding or repetition。
- `full` endpoint behavior is the standard zero extension implied by discrete full convolution。
- `same` and `valid` use only the exact slices specified in Section 10。
- All-zero impulse returns exact zeros in the resolved dtype。

---

## 12. Helper and Output Validation

### 12.1 Raw full helper output

For non-empty wave, helper output must be：

- Exact `numpy.ndarray`; ndarray subclass is invalid。
- 1D。
- Shape exact `(N + M - 1,)`。
- Dtype exact `expected_dtype`。
- C-contiguous。
- Finite。
- Not the same object as either working input。
- Not sharing memory with caller wave or impulse ndarrays。

Any violation raises `RuntimeError`。No silent cast、copy、reshape or repair is allowed。

### 12.2 Final output

Final values must be：

- Exact `numpy.ndarray`。
- 1D with the exact mode-specific length。
- Dtype exact `expected_dtype`。
- C-contiguous。
- Finite。
- New independent storage，不與wave、impulse或raw helper output共享可寫memory。

For `same` and `valid`, producing a new C-contiguous copy of the exact specified slice is part of the mode definition, not a helper-repair path。

### 12.3 Result metadata

```text
resolved_config: new valid exact ImpulseConvolutionConfig
output_start_index: exact Python int
model_level: "discrete_linear_convolution"
```

`ImpulseConvolutionResult` is frozen but does not make the ndarray contents immutable；caller mutation of result values must not affect either input。

---

## 13. Serialization

Canonical dictionary exact keys and order：

```text
schema_version
mode
impulse_zero_index
```

### 13.1 `to_dict()`

- Returns a new dictionary on every call。
- Uses only JSON-safe string／integer scalars。
- Contains exactly the three canonical keys in the specified order。

### 13.2 `from_dict()`

- Input must be `collections.abc.Mapping`; otherwise `TypeError`。
- Key set must exactly match the canonical set。
- Missing／extra keys：`ValueError` and message lists the affected keys。
- Wrong schema type：`TypeError`。
- Unknown schema string：`ValueError`。
- Semantic validation occurs through the constructor。
- No aliases、camelCase、nested parameters or migration guessing。

### 13.3 Round-trip

Input and resolved configs must satisfy：

```python
restored = ImpulseConvolutionConfig.from_dict(config.to_dict())
assert restored == config
```

---

## 14. Canonical Golden Cases

Use：

```python
wave = numpy.array([1.0, 2.0, 3.0, 4.0], dtype=numpy.float64)
impulse = numpy.array([0.5, 1.0, 0.25], dtype=numpy.float64)
z = 1
```

### 14.1 Full

```text
values = [0.5, 2.0, 3.75, 5.5, 4.75, 1.0]
dtype = float64
shape = (6,)
output_start_index = -1
```

### 14.2 Same

```text
values = [2.0, 3.75, 5.5, 4.75]
dtype = float64
shape = (4,)
output_start_index = 0
```

### 14.3 Valid

```text
values = [3.75, 5.5]
dtype = float64
shape = (2,)
output_start_index = 1
```

### 14.4 Delta alignment

```python
impulse = numpy.array([0.0, 1.0, 0.0])
config = ImpulseConvolutionConfig(mode="same", impulse_zero_index=1)
```

Expected values equal wave exactly and `output_start_index == 0`。

### 14.5 Integer promotion

```python
wave = numpy.array([1, 2, 3], dtype=numpy.int16)
impulse = numpy.array([1, 1], dtype=numpy.int8)
```

Expected full values：`[1.0, 3.0, 5.0, 3.0]` with exact `numpy.float64` dtype。

---

## 15. Required Production Tests

Future implementation tests at minimum：

### 15.1 Public surface

- Exact public API and `__all__` order。
- Frozen config and result dataclasses。
- Exact config type and subclass rejection。
- Module boundary test。

### 15.2 Configuration and order

- Schema type／version。
- Mode type／case／whitespace／unsupported values。
- Zero-index exact Python int、bool／NumPy scalar rejection、negative and out-of-range cases。
- Corrupted frozen config defensive revalidation。
- Config validation before wave and impulse conversion。
- Wave conversion before impulse conversion。

### 15.3 Input validation

- List／tuple／ndarray。
- Scalar、2D、complex、string、object rejection for each input。
- NaN／Inf rejection for each input。
- Empty impulse rejection。
- Empty wave acceptance for all modes。
- Non-contiguous input views。
- Input immutability and output non-aliasing。

### 15.4 Mathematical validation

- Hardcoded full／same／valid golden vectors。
- Independent test-side direct summation for additional vectors。
- Non-centered zero-index cases。
- Delta alignment。
- `valid` when `N < M` rejection。
- Single-tap impulse。
- All-zero impulse。
- Exact output start indices。

### 15.5 Dtype validation

- bool、signed、unsigned、float16、float32、float64 combinations。
- Empty wave dtype matrix。
- Exact NumPy result-type-based expectations。
- Integer-only promotion to float64。

### 15.6 Helper failure validation

Monkeypatch helper to return：

- Non-ndarray。
- ndarray subclass。
- Wrong shape。
- Wrong dtype。
- Non-C-contiguous output。
- Caller wave object／alias。
- Caller impulse object／alias。
- Non-finite output。

Each must raise `RuntimeError` without repair。

Verify helper is called exactly with `mode="full"` and is not called for empty wave。

### 15.7 Serialization

- Canonical keys and order。
- New dictionary each call and mutation isolation。
- Input／resolved round-trip。
- Non-mapping、missing／extra keys、wrong version type and unknown version rejection。

### 15.8 Regression

- Existing 247 tests all pass and total count increases。
- `python -c "import main"` passes。
- GUI smoke passes even though GUI is unchanged。
- GitHub Actions Windows CI passes。

---

## 16. Module Boundary and File Boundary

Implementation may add exactly：

```text
pcie_eq/impulse_convolution.py
tests/test_impulse_convolution.py
tests/test_impulse_convolution_module_boundary.py
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
controller modules
```

Implementation must not modify：

```text
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

## 17. Implementation PR Contract

After this document is merged, Gemini implementation uses：

```text
Branch: feature/implement-impulse-response-convolution
Draft PR title: feat: add impulse response convolution core
```

PR body must include：

```text
Closes <implementation issue>
Related to #48
Contract: pcie_eq-impulse-convolution-v1 revision 1.0
Contract merge: <authoritative merge SHA>
```

It must report base/head SHA、exact changed files、pytest count、GitHub Actions run、import result、GUI smoke and `git diff --check`。

Gemini must stop after opening the Draft PR and must not mark ready、merge、close the issue or begin ChannelConfig integration。

---

## 18. Acceptance Gate

The implementation passes only when：

- Exact v1 API、validation、mode and serialization contracts are implemented。
- Full／same／valid values and output coordinates match hardcoded and independent golden cases。
- Dtype、empty、copy and helper-failure contracts are exact。
- NumPy helper is used only in full mode。
- Existing 247 tests pass and total tests increase。
- Changed files are exactly the three allowed new files。
- GitHub Actions、import、GUI smoke and diff check pass。

---

## 19. Stop Conditions

Stop and request a docs-only correction when：

- NumPy 2.4 result dtype differs from the frozen matrix。
- Exact aligned same／valid slices conflict with a required existing behavior。
- A silent cast、reshape or helper repair would be needed。
- Existing repository imports force GUI、pipeline or ChannelConfig coupling。
- Physical sample-interval metadata becomes necessary for correctness rather than future integration。

Production code must not change the frozen contract to work around these conditions。
