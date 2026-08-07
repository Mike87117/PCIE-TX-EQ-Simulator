# Impulse Channel Integration Contract

> Contract ID：`pcie_eq-impulse-channel-integration-v1`  
> Contract revision：`1.0`  
> 文件狀態：Proposed implementation contract；合併後 Frozen  
> 適用 Repository：`Mike87117/PCIE-TX-EQ-Simulator`  
> Production baseline：`0600ebc0c22d851cf84a032aef05e0d9df71c9e5`／283 tests  
> Related Roadmap：Issue #48  
> Tracking Issue：Issue #86

---

## 1. 目的與邊界

本文件定義 GUI-independent Impulse Channel Integration v1，使已凍結的：

```text
pcie_eq.channel_config
pcie_eq.impulse_source
pcie_eq.impulse_convolution
```

可以透過單一 deterministic sample-index-domain channel boundary 串接，而不重新實作任何 impulse generation 或 convolution 數學。

本 Contract 是 project-owned software integration contract，不是 PCI-SIG channel specification、PCI-SIG Reference Channel、S-parameter model、insertion-loss model、physical cable／PCB／connector model 或 measurement-correlation contract。

本文件只凍結 pure-core integration semantics。V1 不修改 `pcie_eq.pipeline`、simulation models、GUI 或 receiver sampling semantics。

文件合併後，production implementation只能依本文件修改明示允許的 pure code 與 tests。若 existing frozen contracts、NumPy behavior 或 repository boundary無法同時滿足本文件，必須停止並由 Planner／Reviewer另開 docs-only correction；不得自行修改 schema、mode、sample interval、alignment、dtype、serialization、child ownership 或 claims。

### 1.1 模型等級

```text
project-owned discrete impulse channel / deterministic teaching primitive
```

### 1.2 Allowed claims

- Versioned GUI-independent impulse channel request／result boundary。
- Deterministic source → convolution → channel composition。
- Explicit lag-zero ownership與wave-aligned same-length output。
- Exact dtype、shape、empty、copy、serialization與failure behavior。
- `none`與`legacy_lowpass` existing numerical behavior preserved。

### 1.3 Forbidden claims

- PCIe-compliant channel或PCI-SIG Reference Channel。
- Physical insertion loss、return loss、frequency response、trace length、connector／via loss。
- S-parameter、Touchstone或mixed-mode behavior。
- Sample interval必然代表seconds、UI、Hz、baud或distance。
- Automatic resampling、interpolation或continuous-time convolution。
- User-defined impulse已經physical-valid、passive、causal、normalized或measurement-correlated。
- Issue #68 sampling phase／cursor phase已經由本contract解決。

---

## 2. Evidence Registry

| Evidence | Access | Contract relevance |
|---|---|---|
| `docs/CHANNEL_CONFIGURATION_CONTRACT.md` | Repository | Existing `ChannelConfig` v1、same-length channel result boundary、explicit requirement that impulse mode use a new revision/schema after convolution semantics are frozen |
| `pcie_eq/channel_config.py` | Repository | Current exact API、validation order、wave materialization、dtype/copy checks、`none` and `legacy_lowpass` behavior |
| `tests/test_channel_config.py` | Repository | Existing v1 regression oracle and helper-failure style |
| `docs/IMPULSE_RESPONSE_CONVOLUTION_CONTRACT.md` | Repository | Project `same` semantics, lag-zero alignment, dtype, empty and ownership contract |
| `pcie_eq/impulse_convolution.py` | Repository | Existing production convolution API and child result contract |
| `docs/IMPULSE_SOURCE_CONTRACT.md` | Repository | Source taxonomy、sample metadata、lag-zero ownership、normalization、serialization and copy semantics |
| `pcie_eq/impulse_source.py` | Repository | Existing production source API and exact float64 output |
| `pcie_eq/pipeline.py` | Repository | Future integration evidence only; current pipeline still calls `simple_channel()` directly |
| Issue #68 | Repository | Sampling/cursor phase remains a separate design gate and is not solved here |

### 2.1 Independent validation strategy

- Hardcoded delta-impulse identity through the complete source → convolution → channel path。
- Hardcoded exponential-postcursor convolution vector。
- User-defined non-centered lag-zero case。
- All-zero and empty-wave cases。
- V1 / V2 schema round-trip and defensive-copy checks。
- Child result monkeypatch failures independent from child production computation。
- Existing `none` / `legacy_lowpass` tests remain regression oracle and must not be regenerated through the new impulse path。

---

## 3. Frozen Scope

This integration contract adds exactly one new channel mode：

```text
impulse_response
```

It composes only the already-frozen APIs：

```text
ImpulseSourceConfig
build_impulse()
ImpulseConvolutionConfig
convolve_impulse()
ChannelConfig
apply_channel()
ChannelResult
```

V1 excludes：

```text
pipeline integration
SimulationConfig / models migration
GUI controls or editors
full / valid channel output modes
sampling phase / cursor phase
resampling / interpolation
sample-interval tolerance matching
physical time units
normalization other than source contract none
Touchstone / S-parameters
frequency-domain synthesis
FFT
measurement import
cursor extraction
frequency response
PCIe compliance / Reference Channel claims
```

---

## 4. Channel Schema Versioning

Existing schema：

```text
pcie_eq-channel-config-v1
```

remains a valid explicit legacy schema for：

```text
none
legacy_lowpass
```

This integration introduces：

```text
pcie_eq-channel-config-v2
```

V2 supports exactly：

```text
none
legacy_lowpass
impulse_response
```

No mode aliases、case folding、whitespace trimming or schema guessing are allowed。

### 4.1 Public constants

Future implementation changes the channel schema constants to：

```python
CHANNEL_CONFIG_CONTRACT_ID = "pcie_eq-channel-config-v2"
LEGACY_CHANNEL_CONFIG_CONTRACT_ID = "pcie_eq-channel-config-v1"
```

`CHANNEL_CONFIG_CONTRACT_ID` is the default/current schema ID after V2 implementation。

### 4.2 Backward compatibility policy

- Explicit v1 dictionaries remain accepted and exact-round-trippable。
- V1 remains limited to `none` / `legacy_lowpass`。
- `impulse_response` with v1 schema is `ValueError`。
- V1 and V2 are selected only by exact `schema_version` string。
- No heuristic migration occurs。
- `from_dict()` may parse both exact schemas according to the key rules in Section 13。

Changing the default constructor schema from v1 to v2 is an explicit schema migration, but it must not change `none` / `legacy_lowpass` numerical behavior、dtype、shape、copy or model-level semantics。

---

## 5. Frozen Channel Public API

Existing public type names remain：

```python
@dataclass(frozen=True)
class ChannelConfig:
    mode: str
    schema_version: str = CHANNEL_CONFIG_CONTRACT_ID
    alpha: int | float | None = None
    impulse_source: ImpulseSourceConfig | None = None

    def __post_init__(self) -> None: ...
    def to_dict(self) -> dict[str, object]: ...

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ChannelConfig": ...


@dataclass(frozen=True)
class ChannelResult:
    values: numpy.ndarray
    resolved_config: ChannelConfig
    model_level: str


def apply_channel(wave, config: ChannelConfig) -> ChannelResult: ...
```

No parallel `apply_impulse_channel()` public API is added。

Exact `__all__` order becomes：

```python
[
    "CHANNEL_CONFIG_CONTRACT_ID",
    "LEGACY_CHANNEL_CONFIG_CONTRACT_ID",
    "ChannelConfig",
    "ChannelResult",
    "apply_channel",
]
```

No subclass hierarchy、registry、plugin framework、stateful channel or async API is introduced。

---

## 6. Field Relevance Matrix

### 6.1 V1 `none`

```text
schema_version = pcie_eq-channel-config-v1
mode = none
alpha = None
impulse_source = None
```

`impulse_source` is a runtime field introduced by the current class definition but is not serialized in v1 and must be `None`。

### 6.2 V1 `legacy_lowpass`

```text
schema_version = pcie_eq-channel-config-v1
mode = legacy_lowpass
alpha = None or valid legacy alpha
impulse_source = None
```

### 6.3 V2 `none`

```text
schema_version = pcie_eq-channel-config-v2
mode = none
alpha = None
impulse_source = None
```

### 6.4 V2 `legacy_lowpass`

```text
schema_version = pcie_eq-channel-config-v2
mode = legacy_lowpass
alpha = None or valid legacy alpha
impulse_source = None
```

### 6.5 V2 `impulse_response`

```text
schema_version = pcie_eq-channel-config-v2
mode = impulse_response
alpha = None
impulse_source = exact ImpulseSourceConfig
```

Any irrelevant non-`None` field is rejected with `ValueError` before unrelated data is materialized or delegated。

---

## 7. Child Config Ownership

`ChannelConfig` owns exactly one nested canonical `ImpulseSourceConfig` for `impulse_response`。

The following source fields must not be duplicated as parallel ChannelConfig fields：

```text
source_type
sample_interval
impulse_zero_index
normalization
length
amplitude
decay_ratio
values
```

The authoritative lag-zero metadata is exactly：

```text
ChannelConfig.impulse_source.impulse_zero_index
```

No ChannelConfig-level `impulse_zero_index` is added。

### 7.1 ImpulseConvolutionConfig ownership

`ImpulseConvolutionConfig` is not serialized or stored in ChannelConfig。

It is a derived execution config created inside `apply_channel()` after source resolution：

```python
ImpulseConvolutionConfig(
    mode="same",
    impulse_zero_index=source_result.resolved_config.impulse_zero_index,
)
```

No caller-selectable convolution mode is exposed through ChannelConfig V2。

---

## 8. Nested ImpulseSourceConfig Validation

For `impulse_response`：

- `type(config.impulse_source) is ImpulseSourceConfig` is required。
- Subclass → `TypeError`。
- Other object → `TypeError`。
- The nested frozen config must be defensively reconstructed/revalidated before wave materialization。
- Corruption through `object.__setattr__()` must be detected before `build_impulse()` and before wave materialization where the invalidity is knowable from config alone。
- The nested config remains governed by `pcie_eq-impulse-source-v1` revision 1.0；integration must not relax or reinterpret source validation。

For `none` / `legacy_lowpass`，a non-`None` `impulse_source` is rejected as irrelevant without calling source conversion/build logic。

---

## 9. Sample Interval Compatibility

Existing `apply_channel(wave, config)` receives only a raw 1D waveform array-like and carries no independent waveform sample-interval metadata。

Impulse Channel Integration v1 therefore defines one waveform array index as one normalized discrete sample step and accepts exactly：

```text
ImpulseSourceConfig.sample_interval == 1.0
```

The source constructor already canonicalizes this field to exact Python `float`。

### 9.1 Comparison rule

Use exact equality：

```python
resolved_sample_interval == 1.0
```

No absolute／relative tolerance is defined。

### 9.2 Failure

Any other valid positive source interval, such as：

```text
0.5
2.0
1.0000001
```

is rejected with `ValueError` before wave materialization and before source/convolution execution。

### 9.3 Forbidden behavior

V1 must not：

```text
ignore the mismatch
resample
interpolate
scale amplitudes by Δt
interpret the value as seconds / UI / Hz / baud / distance
infer waveform sample interval from spb or other external config
```

A future Scenario／measurement contract may add explicit waveform sample metadata and a new integration revision。

---

## 10. Fixed Convolution and Alignment Semantics

For `impulse_response` channel mode, convolution mode is fixed to project `same`。

Let：

```text
N = len(wave)
M = len(impulse)
z = impulse_source.impulse_zero_index
```

The child convolution contract computes full convolution and returns：

```text
values = full[z : z + N]
output length = N
output_start_index = 0
```

Consequences：

- Channel output remains wave-coordinate aligned。
- Channel output length always equals input waveform length。
- A delta impulse located at `z` is an exact identity in values for `same` mode。
- ChannelResult does not add `output_start_index` because the integration requires child result `output_start_index == 0`。
- `full` and `valid` remain accessible only through the low-level convolution core。

No leading/trailing impulse zeros are trimmed。No padding beyond the existing full-convolution zero extension is added。

---

## 11. Wave Input Contract

The common wave input contract from Channel Configuration remains unchanged：

Accepted：

```text
Python list / tuple
1D NumPy ndarray
bool
signed integer
unsigned integer
floating dtype
empty input
non-contiguous 1D ndarray views
```

Rejected：

```text
scalar or ndim != 1 -> ValueError
complex / string / object / non-real numeric dtype -> TypeError
NaN / Inf -> ValueError
```

Caller input is never modified。

Config and integration metadata validation precede wave materialization where specified in Section 14。

---

## 12. Output Contract

### 12.1 `none` / `legacy_lowpass`

Existing v1 numerical and output contracts remain unchanged under both v1 and v2 schema：

- `none` preserves materialized input dtype and returns independent identity copy。
- `legacy_lowpass` preserves existing floating dtype and promotes integer／unsigned／bool to exact float64。
- Existing empty behavior remains unchanged。
- Existing model levels remain：

```text
none -> identity
legacy_lowpass -> teaching_approximation
```

### 12.2 `impulse_response`

Because every `ImpulseSourceResult.values` is exact float64, child convolution dtype resolution yields exact：

```python
numpy.float64
```

for every accepted wave dtype。

Final values must be：

```text
exact numpy.ndarray, no subclass
1D
shape == (len(wave),)
exact numpy.float64
C-contiguous
finite
new independent storage
not caller wave object
not sharing memory with caller wave ndarray
```

Empty wave returns：

```text
shape = (0,)
dtype = float64
```

All-zero impulse is valid and returns exact same-length zeros。

### 12.3 Result metadata

For `impulse_response`：

```text
model_level = "project_owned_discrete_impulse_channel"
resolved_config = new exact valid ChannelConfig
```

The nested `resolved_config.impulse_source` must be a new exact valid `ImpulseSourceConfig` corresponding to the source result's resolved config and must not be the original caller nested config object。

---

## 13. Serialization Contract

Serialization is schema-specific。

### 13.1 V1 canonical dictionary

Exact keys and order：

```text
schema_version
mode
alpha
```

No `impulse_source` key exists in serialized v1 data。

### 13.2 V2 canonical dictionary

Exact keys and order：

```text
schema_version
mode
alpha
impulse_source
```

For V2：

```text
none -> impulse_source = None
legacy_lowpass -> impulse_source = None
impulse_response -> impulse_source = fresh ImpulseSourceConfig.to_dict() dictionary
```

### 13.3 `to_dict()`

- Returns a new top-level dictionary each call。
- V2 nested source dictionary must be newly allocated each call。
- Nested `values` list from user-defined source must also be newly allocated according to the source contract。
- Returned data must be JSON-safe。

### 13.4 `from_dict()`

- Input must be `collections.abc.Mapping`; otherwise `TypeError`。
- `schema_version` key must exist before schema-specific parsing can proceed; missing schema is `ValueError`。
- `schema_version` must be exact Python `str`; otherwise `TypeError`。
- Exact recognized schemas only：v1 / v2。
- Unknown schema string → `ValueError`。
- After exact schema selection, key set must exactly match that schema's canonical key set。
- Missing / extra keys → `ValueError` listing affected keys。
- V1 must not accept an `impulse_source` extra key。
- V2 `impulse_source` mapping is reconstructed through `ImpulseSourceConfig.from_dict()`。
- V2 non-mapping/non-None nested source representation is rejected according to mode and nested type rules。
- No alias、camelCase、case-insensitive key or migration guessing。

### 13.5 Round-trip

All valid configs satisfy：

```python
restored = ChannelConfig.from_dict(config.to_dict())
assert restored == config
```

and preserve the original explicit schema version。

Resolved configs satisfy the same rule。

---

## 14. Fixed Validation and Dispatch Order

`apply_channel(wave, config)` uses this conceptual order：

1. Require exact `ChannelConfig` type；subclass/other → `TypeError`。
2. Validate exact schema version and mode compatibility。
3. Validate `alpha` / `impulse_source` relevance before touching irrelevant nested data。
4. For impulse mode, require exact `ImpulseSourceConfig` and defensively reconstruct/revalidate nested source config。
5. Validate integration sample interval exact `1.0`。
6. Materialize and validate wave using the existing Channel wave contract。
7. For `none` / `legacy_lowpass`, follow existing dispatch unchanged。
8. For `impulse_response`, call `build_impulse()` exactly once using the defensively resolved source config。
9. Validate the exact child `ImpulseSourceResult` boundary required by Section 15。
10. Derive a new exact `ImpulseConvolutionConfig(mode="same", impulse_zero_index=source_result.resolved_config.impulse_zero_index)`。
11. Call `convolve_impulse()` exactly once with wave, source values and derived convolution config。
12. Validate the exact child `ImpulseConvolutionResult` boundary required by Section 15。
13. Build a new resolved `ChannelConfig` with a new nested resolved source config。
14. Validate final common ChannelResult values and return frozen result。

Config errors that can be determined before wave conversion must occur before wave conversion。

No fallback from `impulse_response` to `legacy_lowpass` or `none` is allowed。

---

## 15. Child Boundary Validation

Although `build_impulse()` and `convolve_impulse()` validate their own contracts, the channel adapter must also treat their return objects as delegated child boundaries and fail closed when monkeypatched or otherwise violated。

### 15.1 Impulse source child result

Required：

```text
type(result) is ImpulseSourceResult
type(result.resolved_config) is ImpulseSourceConfig
result.model_level == "project_owned_discrete_impulse_source"
type(result.values) is numpy.ndarray
result.values exact float64 / 1D / expected source length / C-contiguous / finite
result.values does not alias caller-owned nested source input storage where applicable
resolved_config.sample_interval == 1.0
```

The adapter must not repair bad child results。

### 15.2 Convolution child result

Required：

```text
type(result) is ImpulseConvolutionResult
type(result.resolved_config) is ImpulseConvolutionConfig
result.resolved_config.mode == "same"
result.resolved_config.impulse_zero_index == source_result.resolved_config.impulse_zero_index
result.output_start_index == 0
result.model_level == "discrete_linear_convolution"
type(result.values) is numpy.ndarray
result.values exact float64 / 1D / shape (len(wave),) / C-contiguous / finite
result.values does not alias caller wave or source values
```

Any child boundary violation raises `RuntimeError`。No silent copy、cast、reshape、metadata correction or recomputation is allowed。

Creating the new final resolved ChannelConfig is normal adapter behavior, not a repair path。

---

## 16. Error Taxonomy

### `TypeError`

Examples：

```text
non-exact ChannelConfig passed to apply_channel
ChannelConfig subclass
non-string schema/mode
invalid alpha type
impulse_source wrong type/subclass
wave non-real-numeric dtype
serialization input not Mapping
nested serialization wrong structural type
```

### `ValueError`

Examples：

```text
unknown schema
unsupported mode
impulse_response under v1
irrelevant alpha / impulse_source
invalid nested source semantics
sample_interval != 1.0
wave scalar / 2D / NaN / Inf
missing / extra serialization keys
```

Nested source constructor errors retain the source contract's own exact TypeError / ValueError taxonomy。

### `RuntimeError`

Reserved for delegated child/result or final internal output contract violations that should have been impossible under valid production helpers。

No error is silently downgraded into another channel mode。

---

## 17. Canonical Golden Cases

### 17.1 Delta identity

```python
wave = numpy.array([1.0, 2.0, -1.0, 0.5], dtype=numpy.float64)
source = ImpulseSourceConfig(
    source_type="single_tap",
    sample_interval=1.0,
    impulse_zero_index=1,
    normalization="none",
    length=3,
    amplitude=1.0,
    decay_ratio=None,
    values=None,
)
```

Generated impulse：

```text
[0.0, 1.0, 0.0]
```

Expected channel result：

```text
[1.0, 2.0, -1.0, 0.5]
dtype = float64
shape = (4,)
model_level = project_owned_discrete_impulse_channel
```

### 17.2 Exponential postcursor

```python
wave = numpy.array([1.0, 0.0, 0.0, 0.0], dtype=numpy.float64)
source = ImpulseSourceConfig(
    source_type="exponential_postcursor",
    sample_interval=1.0,
    impulse_zero_index=0,
    normalization="none",
    length=3,
    amplitude=1.0,
    decay_ratio=0.5,
    values=None,
)
```

Generated impulse：

```text
[1.0, 0.5, 0.25]
```

Expected channel result：

```text
[1.0, 0.5, 0.25, 0.0]
dtype = float64
```

### 17.3 Non-centered user-defined zero index

```text
wave = [1.0, 2.0, 3.0]
impulse values = [0.25, 1.0, 0.5]
impulse_zero_index = 1
```

Expected values are independently derived from full convolution followed by exact project slice `full[1:4]`。Tests must hardcode or independently compute the vector; they must not call production channel APIs to generate expected values。

### 17.4 All-zero impulse

Any legal all-zero source returns same-length exact zero float64 output without normalization or main-cursor insertion。

### 17.5 Empty wave

Any legal impulse source with `sample_interval == 1.0` plus an accepted empty wave returns：

```text
shape = (0,)
dtype = float64
model_level = project_owned_discrete_impulse_channel
```

---

## 18. Required Future Implementation Tests

The production implementation PR must at minimum cover：

### 18.1 Public surface and schema

- Exact `__all__` order。
- New current and legacy schema constants。
- Frozen dataclasses。
- Exact ChannelConfig type / subclass rejection。
- V1 explicit mode support unchanged。
- V2 exact mode taxonomy。
- `impulse_response` rejected under v1。

### 18.2 Relevance and nested config

- Full alpha / impulse_source relevance matrix for every schema/mode。
- Irrelevant nested object rejected without materialization/build。
- Exact `ImpulseSourceConfig` type and subclass rejection。
- Corrupted nested source config defensive revalidation before wave materialization。

### 18.3 Sample interval

- `1` source constructor canonicalizes to `1.0` and is accepted。
- Exact `1.0` accepted。
- Multiple positive non-1.0 values rejected。
- Rejection occurs before wave materialization using an explosive wave test object。
- No tolerance or resampling path。

### 18.4 Integration golden cases

- Delta identity。
- Exponential postcursor hardcoded vector。
- User-defined non-centered zero-index vector。
- Negative source amplitude where legal。
- All-zero source。
- Empty wave。
- Integer / uint / bool / float16 / float32 / float64 wave matrix all yield exact float64 impulse-channel output。
- Non-contiguous wave input。

### 18.5 Ownership / output

- Same-length output for all impulse cases。
- Exact ndarray / float64 / C-contiguous / finite。
- Caller wave non-aliasing and immutability。
- New result values each call。
- New resolved ChannelConfig each call。
- New nested resolved ImpulseSourceConfig each call。
- Result mutation does not affect caller config, caller wave or later calls。

### 18.6 Delegation

- `build_impulse()` called exactly once。
- `convolve_impulse()` called exactly once for non-empty and empty wave according to child contract path。
- Derived convolution config exact type, `mode="same"`, source zero-index copied exactly。
- No direct call to `numpy.convolve()` from `channel_config.py`。
- No duplicate impulse formula in `channel_config.py`。

### 18.7 Child failure matrix

Monkeypatch source/convolution delegation to return：

```text
wrong result type
result subclass
wrong resolved config type
wrong model_level
wrong dtype
wrong shape
non-C-contiguous values
non-finite values
caller alias/shared memory
wrong convolution mode metadata
wrong convolution zero index
nonzero output_start_index
```

All must raise `RuntimeError` without repair。

### 18.8 Serialization

- V1 exact 3-key order and round-trip。
- V2 exact 4-key order and round-trip。
- V1 extra `impulse_source` rejection。
- V2 missing / extra keys rejection。
- Nested source serialized through exact source schema。
- New top-level dict / nested dict / values list allocation each call。
- Caller nested dict/list mutation after `from_dict()` does not affect config。
- Input and resolved v1/v2 round-trip。

### 18.9 Regression / module boundary

- Existing 283 tests all pass and total count increases。
- `none` / `legacy_lowpass` existing golden values and dtype matrix unchanged。
- `python -c "import main"` passes。
- GUI smoke passes even though GUI behavior is not changed。
- Module boundary enforces allowed dependencies in Section 19。

---

## 19. Future Implementation File and Module Boundary

After this contract is merged, the separate implementation issue may modify only：

```text
pcie_eq/channel_config.py
tests/test_channel_config.py
tests/test_channel_config_module_boundary.py
tests/test_impulse_channel_integration.py
```

No other file is authorized unless a new docs-only correction explicitly changes the boundary before implementation starts。

`pcie_eq.channel_config` may import：

```text
Python standard library
NumPy
pcie_eq.channel
pcie_eq.impulse_source
pcie_eq.impulse_convolution
```

It must not import：

```text
pcie_eq.pipeline
pcie_eq.models
pcie_eq.gui.*
main
controllers
PyQt
PySide
pyqtgraph
SciPy
```

The implementation must not modify：

```text
pcie_eq/impulse_source.py
pcie_eq/impulse_convolution.py
pcie_eq/channel.py
pcie_eq/pipeline.py
pcie_eq/models.py
GUI
workflow
Roadmap
docs during implementation
```

---

## 20. Issue #68 Relationship

Issue #68 remains an open blocker for Cursor Analysis and later receiver sampling semantics。

This contract solves only：

```text
wave sample-index coordinates
impulse lag-zero coordinates
same-mode integer sample alignment
```

It does not define：

```text
symbol-relative sampling phase
fractional UI phase
DFE decision phase
eye metric center phase
cursor extraction phase
group-delay compensation
phase sweep objective or tie-break
```

Therefore Issue #68 is not a blocker for this integer sample-index-domain channel adapter, but remains a blocker for Step 2.7 Cursor Analysis and Phase 3 sampling changes。

---

## 21. Stop Conditions

Stop implementation and return to a docs-only correction if any of the following are discovered：

- Existing frozen source/convolution behavior cannot satisfy the adapter without changing child contracts。
- V1 `none` / `legacy_lowpass` numerical or dtype behavior would need to change。
- Explicit v1 serialization cannot be preserved while supporting v2 as specified。
- The adapter would need resampling, interpolation, physical time units or Issue #68 sampling decisions。
- Child output ownership cannot be validated without silently repairing child results。
- Required implementation exceeds the exact file boundary in Section 19 for architectural reasons not already frozen here。

Do not broaden scope inside the implementation PR。

---

## 22. Docs PR Contract

This contract PR may add exactly：

```text
docs/IMPULSE_CHANNEL_INTEGRATION_CONTRACT.md
```

It must not modify production code、tests、Roadmap、workflow、GUI or existing contracts。

Branch：

```text
docs/impulse-channel-integration-contract
```

Draft PR title：

```text
docs: define impulse channel integration contract
```

PR body must include：

```text
Closes #86
Related to #48
Contract: pcie_eq-impulse-channel-integration-v1 revision 1.0
Production baseline: 0600ebc0c22d851cf84a032aef05e0d9df71c9e5 / 283 tests
```

Merge Gate must confirm：

```text
base SHA / head SHA
main drift
exact changed files = one contract file
contract consistency with ChannelConfig v1
contract consistency with Impulse Source v1
contract consistency with Impulse Convolution v1
v1/v2 serialization compatibility
same-mode alignment
sample interval policy
Issue #68 separation
no production/test changes
CI / import main if workflow runs
review threads
```

After contract merge, create a separate Implementation 29B issue。Do not begin 29B before this contract is frozen。
