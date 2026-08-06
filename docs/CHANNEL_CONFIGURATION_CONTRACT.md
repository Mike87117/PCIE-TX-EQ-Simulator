# Channel Configuration Contract

> Contract ID：`pcie_eq-channel-config-v1`  
> Contract revision：`1.0`  
> 文件狀態：Proposed implementation contract；合併後 Frozen  
> 適用 Repository：`Mike87117/PCIE-TX-EQ-Simulator`  
> Production baseline：`0c09531869ca7dd2201566a04db67b1a45d20236`／233 tests  
> Related Roadmap：Issue #48  
> Tracking Issue：Issue #73

---

## 1. 目的與界線

本文件定義 GUI-independent Channel Configuration v1，使現有 identity path 與 `simple_channel()` first-order low-pass teaching model 可透過單一、可序列化且可驗證的 request／result boundary 執行。

本 Contract 是專案自有軟體規格，不是 PCI-SIG channel specification、Reference Channel、S-parameter model、insertion-loss model 或實際線材／PCB correlation model。

文件合併後，production implementation 只能依本文件修改 pure code 與 tests。若 code、tests 或現有 `simple_channel()` 與本文件衝突，必須停止並由 Planner／Reviewer另開 docs-only PR；不得自行修改 mode taxonomy、defaults、dtype、copy policy、serialization、validation 或 claims。

### 1.1 模型等級

| Mode | Model level |
|---|---|
| `none` | Identity／project-owned software behavior |
| `legacy_lowpass` | Teaching approximation |

### 1.2 Allowed claims

- Versioned、GUI-independent channel request／result contract。
- `none` mode提供不alias caller input的identity copy。
- `legacy_lowpass`保存既有first-order recursive low-pass teaching behavior。
- Output shape、dtype、empty behavior、copy policy與resolved parameters可驗證並序列化。

### 1.3 Forbidden claims

- PCIe-compliant channel、PCI-SIG Reference Channel或compliance result。
- Physical insertion loss、frequency response、trace length、connector loss或S-parameter behavior。
- `alpha`與dB、GHz、UI、seconds、distance或實體材料的直接對應。
- 尚未實作的impulse-response convolution、Touchstone或mixed-mode能力。
- `none` mode可以共享caller writable storage。

---

## 2. Evidence Registry

| Evidence | Access | Contract relevance |
|---|---|---|
| `pcie_eq/channel.py` at production merge `0c09531869ca7dd2201566a04db67b1a45d20236` | Repository | Existing `simple_channel()` recurrence、input conversion、dtype、empty與copy behavior |
| `tests/test_channel_baseline.py` | Repository | Hardcoded recurrence、edge alpha、dtype matrix、empty、validation、immutability與non-aliasing oracle |
| `pcie_eq/models.py` | Repository | Current `channel_alpha` compatibility surface |
| `pcie_eq/pipeline.py` | Repository | Current direct `simple_channel()` call sequence；future integration evidence only |
| `docs/TECHNICAL_AUDIT_2026-08-06.md` | Repository | Identity alias risk、ChannelConfig entry gate、sample interval與convolution separation |

Repository regression contract優先。V1不修改 `simple_channel()`，也不整合pipeline或GUI。

### 2.1 Independent validation strategy

- `none`：hardcoded identity values、exact dtype、shape、C-contiguity與non-aliasing。
- `legacy_lowpass`：test-side independent recurrence與既有hardcoded golden cases。
- Existing `simple_channel()` direct tests作為compatibility oracle；不得呼叫future aggregator產生自己的expected values。
- Helper contract failure以monkeypatch錯誤type／shape／dtype／contiguity／alias／domain output驗證 `RuntimeError`。

---

## 3. Frozen Scope

Channel Configuration v1只支援：

```text
none
legacy_lowpass
```

`impulse_response`不在V1。

加入impulse response前，必須先另行凍結：

- convolution mode與output length。
- input／impulse sample interval compatibility。
- time-zero與main-cursor alignment。
- normalization。
- truncation／padding。
- empty與all-zero impulse behavior。

完成上述Step 2.5 contract後，才能透過明示revision或新schema加入 `impulse_response`。V1禁止建立無法執行的placeholder mode。

---

## 4. Frozen Public API

後續production implementation新增：

```text
pcie_eq/channel_config.py
```

公開介面：

```python
CHANNEL_CONFIG_CONTRACT_ID = "pcie_eq-channel-config-v1"

@dataclass(frozen=True)
class ChannelConfig:
    mode: str
    schema_version: str = CHANNEL_CONFIG_CONTRACT_ID
    alpha: int | float | None = None

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

`__all__` exact order：

```python
[
    "CHANNEL_CONFIG_CONTRACT_ID",
    "ChannelConfig",
    "ChannelResult",
    "apply_channel",
]
```

`ChannelConfig.__post_init__()`必須完成全部input validation，包括irrelevant-field rejection；正常public API不得建立無效config。`apply_channel()`仍須在wave conversion、default resolution與delegate前防禦性重驗原始config。

V1不提供subclass hierarchy、plugin registry、stateful channel、continuation state、frequency response、async API或pipeline integration。

---

## 5. Configuration Fields

### 5.1 `schema_version`

- Exact `pcie_eq-channel-config-v1`。
- Exact Python `str` only。
- Non-string：`TypeError`。
- Unknown string：`ValueError`。
- 不做fallback或migration猜測。

### 5.2 `mode`

- Exact Python `str` only。
- Case-sensitive exact string。
- 只接受 `none`、`legacy_lowpass`。
- Unsupported／empty／case mismatch／whitespace variant：`ValueError`。
- 不trim、不轉大小寫、不接受alias。

### 5.3 `alpha`

| Mode | Applicability | Input contract | Resolved value |
|---|---|---|---|
| `none` | Irrelevant | 必須為`None` | `None` |
| `legacy_lowpass` | Optional | `None`或exact Python `int`／`float` | Python `float` |

規則：

- `none`的`alpha`只要不是`None`，一律`ValueError`；禁止silent ignore。
- `legacy_lowpass`的`None` resolves to `0.08`。
- Explicit value只接受exact Python `int`／`float`。
- `bool`、NumPy scalar、string、sequence與其他type：`TypeError`。
- 必須finite；NaN／Inf：`ValueError`。
- 不限制到`[0, 1]`。
- Negative、zero與greater-than-one保留既有teaching behavior。
- Resolved config中的explicit或default alpha一律為Python `float`。

---

## 6. Wave Input Contract

`apply_channel(wave, config)`接受1D real numeric array-like。

### 6.1 Accepted input

- Python list／tuple。
- 1D NumPy ndarray。
- Boolean、signed integer、unsigned integer與floating dtype。
- Empty input。

### 6.2 Rejection

- Scalar或`ndim != 1`：`ValueError`。
- Complex、string、object與其他non-real-numeric dtype：`TypeError`。
- 任一wave element為NaN／Inf：`ValueError`。

### 6.3 Ownership and layout

- 不修改caller input。
- Output一律為新的1D ndarray。
- Output不得與caller ndarray共享memory。
- Output必須C-contiguous。
- Output shape exact `(len(materialized_input),)`。
- Empty output shape exact `(0,)`。

---

## 7. Resolution and Dispatch Order

`apply_channel()`固定流程：

1. Input exact type必須是`ChannelConfig`；subclass或其他object為`TypeError`。
2. 防禦性重驗原始config的schema、mode、alpha與irrelevant fields。
3. 使用`numpy.asarray()` materialize wave並驗證dimension、dtype與finite values。
4. 填入defaults並建立新的`resolved_config`。
5. 依exact mode執行identity copy或委派existing `simple_channel()`。
6. 驗證helper／mode output的type、shape、dtype、C-contiguity、non-aliasing與finite values。
7. Helper若違反frozen output contract，拋`RuntimeError`；不可silent repair、copy或cast。
8. 回傳`ChannelResult`。

Config validation必須發生在wave conversion與helper call之前，讓遭`object.__setattr__()`破壞的frozen config能穩定被拒絕。

---

## 8. Mode Contract

### 8.1 `none`

- Exact identity values與ordering。
- 建立獨立C-contiguous copy。
- Output dtype exact等於`numpy.asarray(wave).dtype`。
- 不做promotion、normalization、rounding或quantization。
- Python sequence先依`numpy.asarray()`取得platform dtype，再建立獨立copy。
- Empty input遵守相同dtype規則。
- `resolved_config.alpha is None`。
- `model_level = "identity"`。

### 8.2 `legacy_lowpass`

必須委派：

```python
pcie_eq.channel.simple_channel(wave, alpha=resolved_alpha)
```

不得重新實作recurrence：

```text
out[0] = wave[0]
out[i] = out[i-1] + alpha * (wave[i] - out[i-1])
```

Compatibility contract：

- Existing non-empty floating-input values、shape、dtype與ordering保持。
- Floating input保存原floating dtype。
- Integer／unsigned／boolean input提升為exact `numpy.float64`。
- Empty input使用相同dtype matrix：
  - empty floating input保留dtype。
  - empty integer／unsigned／bool input為`numpy.float64`。
  - empty Python list／tuple materialize後為platform integer，再由helper提升為`numpy.float64`。
- Output不得alias caller input。
- `resolved_config.alpha`為Python `float`。
- `model_level = "teaching_approximation"`。

Aggregator不得修改 `pcie_eq.channel.simple_channel()` public API、`__all__`或direct behavior。

---

## 9. Sample Interval, Units, and Normalization

V1是**sample-index domain**。

- 不宣稱seconds、UI、Hz或任何physical time unit。
- 不新增未使用的`sample_interval`field。
- `alpha`是per-sample dimensionless teaching coefficient。
- `none`與`legacy_lowpass`沒有normalization setting。
- Step 2.5 impulse-response contract必須另行定義sample interval、time-zero、alignment與normalization；不得從V1猜測。

---

## 10. Output Validation

### 10.1 Common

Output必須：

- exact `numpy.ndarray`。
- `ndim == 1`。
- shape exact與input長度相同。
- C-contiguous。
- 不與caller ndarray alias。
- 所有values finite。

違反時拋`RuntimeError`。

### 10.2 Dtype matrix

| Mode / input | Exact output dtype |
|---|---|
| `none` | `numpy.asarray(wave).dtype` |
| `legacy_lowpass`, floating input | input floating dtype |
| `legacy_lowpass`, integer／unsigned／bool input | `numpy.float64` |

Aggregator不得為了統一外觀而cast。

---

## 11. Serialization

Canonical dictionary exact 3 keys，全部存在且順序固定：

```text
schema_version
mode
alpha
```

### 11.1 `to_dict()`

- 回傳新的dictionary。
- 只使用JSON-safe scalar或`None`。
- Input與resolved config均可序列化。

### 11.2 `from_dict()`

- Input必須是`collections.abc.Mapping`，否則`TypeError`。
- Key set必須exact match。
- Missing／extra key：`ValueError`，訊息列出keys。
- 不接受alias、camelCase、case-insensitive key或nested parameters。
- 透過`ChannelConfig` constructor完成全部semantic validation。
- 不做schema migration猜測。

### 11.3 Round-trip

```python
restored = ChannelConfig.from_dict(config.to_dict())
assert restored == config
```

Input config與resolved config均須成立。Dictionary必須是新物件。

---

## 12. Golden Cases

### 12.1 `none`

```python
wave = numpy.array([0, 1, -1, 2], dtype=numpy.int16)
```

Expected：

```text
values: [0, 1, -1, 2]
dtype: numpy.int16
shape: (4,)
model_level: identity
output does not alias input
```

### 12.2 `legacy_lowpass`, default alpha

```python
wave = numpy.array([0.0, 1.0, 1.0, 0.0], dtype=numpy.float64)
alpha = 0.08
```

Independent recurrence expected：

```text
[0.0, 0.08, 0.1536, 0.141312]
dtype: numpy.float64
```

### 12.3 `legacy_lowpass`, alpha 0.5

```python
wave = numpy.array([0, 1, 1, 0], dtype=numpy.int64)
```

Expected：

```text
[0.0, 0.5, 0.75, 0.375]
dtype: numpy.float64
```

### 12.4 Empty

```text
none(empty float32)             -> empty float32
none(empty int32)               -> empty int32
legacy_lowpass(empty float32)   -> empty float32
legacy_lowpass(empty int32)     -> empty float64
```

---

## 13. Required Production Tests

後續implementation至少涵蓋：

### 13.1 Public surface

- Exact public API與`__all__` order。
- Frozen dataclasses。
- Exact config type與subclass rejection。
- Module boundary。

### 13.2 Constructor validation

- Schema type／version。
- Mode type／case／whitespace／unsupported values。
- Alpha applicability、exact Python scalar type、finite validation與default resolution。
- Corrupted frozen config defensive revalidation。

### 13.3 Wave validation

- List／tuple／ndarray。
- Scalar、2D、complex、string、object rejection。
- NaN／Inf rejection。
- Input immutability。

### 13.4 `none`

- Boolean、integer、unsigned、float16、float32、float64與empty dtype matrix。
- Identity values、ordering、shape、C-contiguity與non-aliasing。
- Non-contiguous input view產生獨立C-contiguous output。

### 13.5 `legacy_lowpass`

- Default alpha與explicit alpha hardcoded golden cases。
- Existing floating numerical baseline preservation。
- Integer／unsigned／bool promotion至float64。
- Empty dtype matrix。
- Negative、zero與greater-than-one alpha cases。
- Direct `simple_channel()` equivalence。

### 13.6 Helper contract failures

Monkeypatch imported helper reference，驗證bad：

- return type。
- shape／ndim。
- dtype。
- contiguity。
- alias。
- non-finite values。

全部須拋`RuntimeError`，不得silent repair。

### 13.7 Serialization

- Exact canonical keys／order。
- Input與resolved config round-trip。
- Missing／extra／unknown version rejection。
- Dictionary copy isolation。

### 13.8 Regression

- Existing 233 tests全部通過且總數增加。
- `python -c "import main"`通過。
- GUI smoke通過。
- `git diff --check` clean。

---

## 14. Module Boundary

`pcie_eq/channel_config.py`不得import：

```text
PyQt
PySide
pyqtgraph
main
pcie_eq.gui
pcie_eq.pipeline
pcie_eq.models
controller modules
```

允許依賴：

```text
Python standard library
NumPy
pcie_eq.channel.simple_channel
```

不得修改 `pcie_eq.channel` public API或export order。

---

## 15. Future Production PR Boundary

後續Gemini implementation只允許新增：

```text
pcie_eq/channel_config.py
tests/test_channel_config.py
tests/test_channel_config_module_boundary.py
```

不得修改：

```text
pcie_eq/channel.py
pcie_eq/models.py
pcie_eq/pipeline.py
pcie_eq/gui/**
main.py
docs/**
PCIE-TX-EQ-Simulator_Product_Roadmap.md
.github/workflows/**
```

也不得加入impulse convolution、sampling、cursor、GUI integration、Scenario、RXEQ或metrics變更。

Branch：

```text
feature/implement-channel-configuration-core
```

Draft PR title：

```text
feat: add channel configuration core
```

PR body必須包含：

```text
Closes <future implementation issue>
Related to #48
Contract: pcie_eq-channel-config-v1 revision 1.0
```

完成Draft PR後停止，不得mark ready、merge或開始下一項工作。

---

## 16. Stop Conditions

遇到任一情況立即停止並回報：

- Existing `simple_channel()`與本contract無法同時符合。
- 必須修改`simple_channel()`才能通過aggregator tests。
- `none`無法在不alias input的情況保存exact dtype／values。
- Existing tests對alpha、dtype、empty或copy policy提供矛盾evidence。
- 實作者需要加入`impulse_response`、pipeline或GUI才能完成V1。

不得以cast、silent copy repair、放寬tolerance、修改existing golden或擴大file scope掩蓋衝突。
