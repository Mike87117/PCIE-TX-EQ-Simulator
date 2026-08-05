# Pattern Configuration Contract

> Contract ID：`pcie_eq-pattern-config-v1`  
> 文件狀態：Frozen implementation contract after merge  
> 適用 Repository：`Mike87117/PCIE-TX-EQ-Simulator`  
> 規劃基準：`main@4a11b26176d032fcc5dbe369c41252a960f4ea7a`  
> Production baseline：`c4fd8c8191919c30d8e28383d94804fe3e68db25`／192 tests  
> Related Roadmap：Issue #48  
> Related Evidence Gate：Issue #58

---

## 1. 目的與界線

本文件定義 GUI-independent Pattern Configuration v1，使現有 random、deterministic、PRBS 與 user-defined pattern 可透過單一 request／result boundary 產生，同時保存既有 value、shape、dtype、RNG 與 GUI compatibility。

本 Contract 是專案自有軟體規格，不是 PCI-SIG pattern specification，也不新增 protocol training sequence、compliance pattern、PRBSQ／QPRBS 或 FEC pattern。

文件合併後，Gemini 只能依本文件實作 pure code 與 tests。若 code、tests 或現有 generator 與本文件衝突，必須停止並由 Planner／Reviewer另開 docs PR；不得自行修改 taxonomy、default、dtype、RNG、serialization 或 validation rule。

### 模型等級

- Contract layer：**Project-owned software contract**。
- Existing NRZ／PAM4 random 與 deterministic patterns：Repository regression-derived。
- PRBS7／9／15／23／31：依 `docs/PRBS_CONVENTION.md`，屬 **Reference-model-derived general test pattern**。
- User-defined values：project-owned exact data validation。

### Allowed claims

- Versioned、GUI-independent pattern request／result contract。
- Seeded random、deterministic、PRBS 與 user-defined output可依固定 config 重現。
- `seed=None` 保留 legacy global NumPy RNG compatibility。
- Output domain、shape、dtype與resolved parameters可驗證與序列化。

### Forbidden claims

- PCIe compliance／PCI-SIG Reference Pattern。
- PCIe training sequence／ordered set。
- PAM4 PRBSQ／QPRBS或Gen6 FEC pattern。
- 與指定 FPGA、transceiver、BERT或示波器初始 phase bit-exact。
- `seed=None` 可只靠 config 在另一個 process 重現。

---

## 2. Evidence Registry

| Evidence | Access | Contract relevance |
|---|---|---|
| `pcie_eq/patterns.py` at `c4fd8c8191919c30d8e28383d94804fe3e68db25` | Repository | 現有 generator API、validation、value、shape、dtype與RNG行為 |
| `tests/test_patterns.py` at `c4fd8c8191919c30d8e28383d94804fe3e68db25` | Repository | seeded golden vectors、global RNG equivalence、dtype fingerprint與PRBS validation |
| `docs/PRBS_CONVENTION.md` | Repository | PRBS convention、state、Golden vectors與宣稱限制 |
| `pcie_eq/gui/window.py`、`nrz_controller.py` | Repository | NRZ global RNG initialization、Generate New Waveform call sequence與native integer dtype |
| `pcie_eq/gui/pam4_controller.py`、`gui/random_data.py` | Repository | PAM4 random compatibility wrapper與float64 symbol domain |
| NumPy legacy random documentation | Public primary | `RandomState` scalar seed range與global legacy RNG：https://numpy.org/doc/2.0/reference/random/legacy.html |
| NumPy 2.4 `asarray` documentation | Public primary | array conversion、dtype與order：https://numpy.org/doc/2.4/reference/generated/numpy.asarray.html |

Repository regression contract 優先。V1 不得將 existing `RandomState`／global RNG改成 `default_rng()`。

---

## 3. Frozen Public API

後續 code implementation 新增：

```text
pcie_eq/pattern_config.py
```

公開介面：

```python
PATTERN_CONFIG_CONTRACT_ID = "pcie_eq-pattern-config-v1"

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

    def __post_init__(self) -> None: ...
    def to_dict(self) -> dict[str, object]: ...

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "PatternConfig": ...

@dataclass(frozen=True)
class PatternResult:
    values: numpy.ndarray
    resolved_config: PatternConfig
    modulation: str
    domain: str
    rng_mode: str

def generate_pattern(config: PatternConfig) -> PatternResult: ...
```

`__all__` exact order：

```python
[
    "PATTERN_CONFIG_CONTRACT_ID",
    "PatternConfig",
    "PatternResult",
    "generate_pattern",
]
```

`PatternConfig.__post_init__()` 必須完成全部 input validation，包括 irrelevant-field rejection；因此正常 public API 不得產生無效 `PatternConfig`。`generate_pattern()` 仍須在任何 RNG 操作前做防禦性驗證。

V1 不提供 subclass hierarchy、plugin registry、iterator、stateful generator、continuation token或async API。

---

## 4. Pattern Taxonomy

`pattern_type` 是 case-sensitive exact string，不做 trim、alias、大小寫轉換或猜測。

| Pattern type | Modulation | Canonical domain | Existing basis |
|---|---|---|---|
| `nrz_random` | `nrz` | `bits` | `generate_random_nrz_bits` |
| `nrz_all_zeros` | `nrz` | `bits` | `generate_nrz_all_zeros` |
| `nrz_all_ones` | `nrz` | `bits` | `generate_nrz_all_ones` |
| `nrz_alternating` | `nrz` | `bits` | `generate_nrz_alternating` |
| `nrz_long_run` | `nrz` | `bits` | `generate_nrz_long_run` |
| `nrz_single_transition` | `nrz` | `bits` | `generate_nrz_single_transition` |
| `nrz_single_bit_pulse` | `nrz` | `bits` | `generate_nrz_single_bit_pulse` |
| `nrz_prbs` | `nrz` | `bits` | `generate_prbs_bits` |
| `nrz_user_bits` | `nrz` | `bits` | project-owned validation |
| `pam4_random` | `pam4` | `symbols` | `generate_random_pam4_symbols` |
| `pam4_user_symbols` | `pam4` | `symbols` | project-owned validation |

V1 不提供獨立 `modulation`／`domain` input field。兩者由 `pattern_type` 唯一導出，避免 contradictory config。

---

## 5. Common Fields

### `schema_version`

- Exact `pcie_eq-pattern-config-v1`。
- Non-string：`TypeError`。
- Unknown string：`ValueError`。
- 不做 fallback或migration猜測。

### `pattern_type`

- Python `str` only。
- Non-string：`TypeError`。
- Unsupported／empty／case mismatch／whitespace variant：`ValueError`。

### `count`

- Python `int` only；`bool` 不接受。
- `count >= 0`。
- NRZ表示bit count；PAM4表示symbol count。
- Output shape exact `(count,)`。
- `nrz_single_bit_pulse`要求 `count > 0`。
- `count == 0` 仍須驗證所有其他fields。

### Irrelevant fields

每個 pattern type只允許下表指定parameters。不適用field只要不是 `None`，一律 `ValueError`；禁止silent ignore。

---

## 6. Field Applicability Matrix

- `R`：required。
- `O`：optional；`None`套用固定default。
- `–`：必須為 `None`。

| Pattern | seed | first_bit | run_length | transition_index | initial_bit | pulse_index | baseline_bit | PRBS fields | user_values |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `nrz_random` | O | – | – | – | – | – | – | – | – |
| `nrz_all_zeros` | – | – | – | – | – | – | – | – | – |
| `nrz_all_ones` | – | – | – | – | – | – | – | – | – |
| `nrz_alternating` | – | O | – | – | – | – | – | – | – |
| `nrz_long_run` | – | O | R | – | – | – | – | – | – |
| `nrz_single_transition` | – | – | – | R | O | – | – | – | – |
| `nrz_single_bit_pulse` | – | – | – | – | – | R | O | – | – |
| `nrz_prbs` | – | – | – | – | – | – | – | R／O | – |
| `nrz_user_bits` | – | – | – | – | – | – | – | – | R |
| `pam4_random` | O | – | – | – | – | – | – | – | – |
| `pam4_user_symbols` | – | – | – | – | – | – | – | – | R |

PRBS fields：

```text
prbs_order: required
prbs_initial_state: optional
prbs_convention_id: optional
```

---

## 7. Pattern-specific Validation

### Bit defaults

`first_bit`、`initial_bit`、`baseline_bit`：

- `None` resolves to `0`。
- Explicit value必須是Python `int` 0／1；`bool` 不接受。
- Wrong type：`TypeError`；out of range：`ValueError`。

### `run_length`

- `nrz_long_run` required。
- Python `int` only；`bool` 不接受。
- `run_length >= 1`，即使 `count == 0` 仍需valid。

### `transition_index`

- `nrz_single_transition` required。
- Python `int` only；`bool` 不接受。
- `0 <= transition_index <= count`。
- `0`：第一個output起已transition；`count`：全部維持initial bit。

### `pulse_index`

- `nrz_single_bit_pulse` required。
- Python `int` only；`bool` 不接受。
- `0 <= pulse_index < count`。

### PRBS

```text
prbs_order ∈ {7, 9, 15, 23, 31}
prbs_initial_state = None 或 valid nonzero n-bit state
prbs_convention_id = None 或 "pcie_eq-prbs-fibonacci-lsb-v1"
```

Resolved defaults：

```text
prbs_initial_state = (1 << prbs_order) - 1
prbs_convention_id = pcie_eq-prbs-fibonacci-lsb-v1
```

`count == 0` 仍驗證order、state與convention。

### User values container

Public dataclass只接受：

```text
user_values: tuple 或 None
```

直接傳list／ndarray：`TypeError`。Serialized JSON array由 `from_dict()`複製並轉tuple。這避免frozen config引用外部mutable container。

通用規則：

- `len(user_values) == count`。
- 不truncate、pad、repeat、broadcast、round或tolerance-correct。
- Result必須建立新array，不修改input或共享writable storage。

`nrz_user_bits`：

- Element只接受Python `int` 0／1或Python `bool`。
- Bool resolves to native integer 0／1。
- Float 0.0／1.0不接受。
- Output dtype `numpy.dtype(int)`。

`pam4_user_symbols`：

- Element只接受Python `int`／`float`；`bool`不接受。
- 必須finite。
- 必須與下列canonical Python float exact-equal：

```python
(-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0)
```

- 不使用 `isclose`、rounding或quantization。
- Output dtype exact `numpy.float64`。

CSV tolerance、measurement snapping與level fitting不屬於本Contract。

---

## 8. RNG Contract

只有 `nrz_random`、`pam4_random` 可使用 `seed`；其他pattern的 `seed` 必須為 `None`。

### Seed type and range

- `None`，或Python `int`，`0 <= seed <= 2**32 - 1`。
- `bool`、NumPy integer、float、string與sequence不接受。
- V1刻意使用JSON-safe scalar seed，不開放NumPy array-like seed。

### `seed=None`

- 委派現有global `numpy.random` path。
- `rng_mode = "global"`。
- 保留global RNG consumption order。
- `count == 0`不消耗RNG。
- 不得宣稱config-alone reproducibility。

NRZ GUI目前於module initialization呼叫 `np.random.seed(7)`，以global RNG建立initial bits；Generate New Waveform也沿用global RNG。Pattern Config不得改變此baseline。

### Explicit seed

- 委派現有 `numpy.random.RandomState(seed)` path。
- `rng_mode = "seeded"`。
- 不讀取或修改global NumPy RNG state。
- 相同config bit-exact repeatable。

### Non-random patterns

- `rng_mode = "none"`。
- 不讀取或修改RNG state。

所有validation必須發生於RNG consumption之前。Constructor或`generate_pattern()`失敗不得推進global RNG。

---

## 9. Output and Result Contract

### `PatternResult.values`

- Exact `numpy.ndarray`。
- 1D、shape `(count,)`、C-contiguous。
- User-defined output為新array，不與input共享writable storage。

### Dtype matrix

| Pattern group | Exact dtype |
|---|---|
| General NRZ random／deterministic、`nrz_user_bits` | `numpy.dtype(int)`，platform native signed integer |
| `nrz_prbs` | `numpy.int8` |
| PAM4 random／user symbols | `numpy.float64` |

不得為了統一外觀silent cast：PRBS不可cast成native int，一般NRZ不可cast成int8。

### Value domain

- NRZ：0／1 bits。
- PAM4：`-1.0`、`-1.0/3.0`、`1.0/3.0`、`1.0`。
- Contract不自動把NRZ bits轉成`-1.0／+1.0` symbols；下游須明確呼叫 `nrz_bits_to_symbols()`。

### Metadata

`PatternResult`：

- `resolved_config`：applicable defaults已填入；irrelevant fields皆 `None`。
- `modulation`：`"nrz"`／`"pam4"`。
- `domain`：`"bits"`／`"symbols"`。
- `rng_mode`：`"global"`／`"seeded"`／`"none"`。

Result不保存global RNG state、final PRBS state、hardware phase、GUI state、TXEQ、Channel或RXEQ config。

---

## 10. Resolution Order

`generate_pattern()`固定流程：

1. Input exact type必須是 `PatternConfig`，否則 `TypeError`。
2. 防禦性重驗schema、pattern type、count、applicable與irrelevant fields。
3. 填入defaults並建立新的 `resolved_config`。
4. 依exact pattern type委派現有pure generator，或copy／normalize user values。
5. 驗證internal result shape、dtype與value domain。
6. Helper若違反frozen output contract，拋出 `RuntimeError`；不可silent repair。
7. 回傳 `PatternResult`。

V1 aggregator不得重新實作PRBS recurrence或random algorithm。

---

## 11. Serialization Contract

### Canonical keys

`to_dict()`建立新dictionary，key order與key set exact如下；所有keys均存在，包括value為`None`者：

```text
schema_version
pattern_type
count
seed
first_bit
run_length
transition_index
initial_bit
pulse_index
baseline_bit
prbs_order
prbs_initial_state
prbs_convention_id
user_values
```

- Tuple `user_values` → 新JSON-safe list。
- `None` → `None`。
- 其他value僅使用JSON scalar。

### `from_dict()`

- Input必須是 `collections.abc.Mapping`，否則 `TypeError`。
- Key set必須exact match；missing／extra key為 `ValueError`，訊息列出keys。
- 不接受alias、camelCase、case-insensitive key或nested parameters。
- `user_values`只接受JSON list／`None`，並copy成tuple。
- 透過 `PatternConfig` constructor完成全部semantic validation；不得回傳無效config。

### Round-trip

```python
restored = PatternConfig.from_dict(config.to_dict())
assert restored == config
```

Input config與resolved config均須成立。Dictionary與list為新物件；修改serialized output不得改變原config。

V1 reader只接受exact V1；future migration另立Issue，不自行猜測。

---

## 12. Canonical Cases

### Seeded NRZ random

```python
PatternConfig(pattern_type="nrz_random", count=10, seed=42)
```

```text
modulation: nrz
domain: bits
rng_mode: seeded
dtype: numpy.dtype(int)
values: [0,1,0,0,0,1,0,0,0,1]
```

### Long run

```python
PatternConfig(
    pattern_type="nrz_long_run",
    count=10,
    run_length=3,
)
```

Resolved `first_bit=0`：

```text
[0,0,0,1,1,1,0,0,0,1]
```

### PRBS7

```python
PatternConfig(pattern_type="nrz_prbs", count=16, prbs_order=7)
```

```text
resolved state: 127
convention: pcie_eq-prbs-fibonacci-lsb-v1
dtype: numpy.int8
values: 1111111000000100
```

### User PAM4

```python
PatternConfig(
    pattern_type="pam4_user_symbols",
    count=4,
    user_values=(-1.0, -1.0/3.0, 1.0/3.0, 1.0),
)
```

Output為新 `numpy.float64` array。

---

## 13. Error Contract

- `TypeError`：Python type／container type錯誤。
- `ValueError`：enum、range、length、value、field applicability、schema key或version錯誤。
- `RuntimeError`：validated request呼叫的internal generator違反frozen output contract。
- Public validation不使用 `AssertionError`。

Exact完整錯誤文字不凍結，但訊息必須包含field name、invalid value／type與合法範圍或allowed values。Tests只比對exception type與必要field substring。

禁止coercion：

- string→integer。
- float count／index→integer。
- float 0.0／1.0→NRZ bit。
- PAM4 tolerance snapping。
- pattern alias。
- unknown field忽略。
- invalid PRBS convention fallback。

---

## 14. Independent Validation Matrix

Expected values必須hardcode或由test-side獨立formulation取得；不得呼叫production function建立自己的oracle。

### Taxonomy／dispatch

- 11種pattern type各一個small-vector case。
- Unsupported／case mismatch／whitespace拒絕。
- Modulation、domain與rng_mode exact。
- Constructor立即拒絕invalid／irrelevant fields。

### Random

- NRZ seed 42／count 10 hardcoded vector。
- PAM4 seed 42／count 10沿用現有hardcoded vector。
- Same seed repeatability與different seed difference。
- Explicit seed不修改global RNG。
- `seed=None`與direct legacy `np.random.randint`在相同pre-state下exact一致。
- Invalid config與count zero不消耗global RNG。

### Deterministic NRZ

- All zero／one。
- Alternating first bit 0／1。
- Long run count 10／run 3。
- Transition boundary 0／count。
- Pulse boundary與zero-count rejection。

### PRBS

- V1 all-ones frozen prefix與custom-state prefix。
- Resolved convention與all-ones state。
- Exact int8。
- 只委派frozen PRBS core，不重寫recurrence。

### User values

- NRZ int／bool normalization；float rejection。
- PAM4 canonical levels；NaN、Inf與off-level rejection。
- Exact length、empty tuple／count zero。
- Input未修改；output為新array。
- Direct list／ndarray constructor input拒絕。
- Serialized list由`from_dict()`copy成tuple。

### Serialization

- 11 pattern types與resolved config round-trip。
- Canonical keys／order與all-keys-present。
- Missing／extra keys與unknown version拒絕。
- Mutating serialized dictionary／list不影響config。

### Output／compatibility

- Exact ndarray、shape、dtype、C-contiguous與value set。
- General NRZ native int、PRBS int8、PAM4 float64均不被cast。
- New module無PyQt、PySide、pyqtgraph、main、GUI、pipeline或controller import。
- `pcie_eq.patterns` public API不變。
- Window、controllers、random wrapper與GUI call sequence不變。
- Existing 192 tests全部通過，總數增加。
- `python -c "import main"`通過。

---

## 15. Implementation Boundary

後續 code Issue預期只允許：

```text
pcie_eq/pattern_config.py
tests/test_pattern_config.py
tests/test_pattern_config_module_boundary.py
```

未經Reviewer核准不得修改：

```text
pcie_eq/patterns.py
pcie_eq/models.py
pcie_eq/pipeline.py
pcie_eq/gui/**
main.py
docs/PATTERN_CONFIGURATION_CONTRACT.md
docs/PRBS_CONVENTION.md
PCIE-TX-EQ-Simulator_Product_Roadmap.md
```

第一個code PR只建立pure contract implementation，不整合GUI或simulation pipeline。

---

## 16. Non-scope

- GUI pattern selector／parameter widgets與window state migration。
- Random button behavior變更。
- NRZ bit-to-symbol自動轉換。
- PAM4 bit mapping、Gray coding或precoding。
- PRBSQ／QPRBS／FEC／training sequence。
- File import、CSV tolerance、measurement fitting。
- Channel、Cursor、Sampling、RXEQ、Scenario、Sweep與Auto EQ。
- Streaming／chunk continuation與final LFSR state。

---

## 17. Stop Conditions／Change Control

實作者遇到以下情況必須停止：

- Existing generator行為與本文件evidence不一致。
- 需要修改GUI、pipeline或existing pattern function才能完成pure contract。
- 無法保留global RNG consumption order。
- 需要silent cast才能統一dtype。
- 新pattern缺少authoritative definition或independent oracle。
- PRBS需要不同convention、polarity或phase。
- Serialized V1無法在不猜測下解析。

Taxonomy、default、dtype、seed policy、serialization key或allowed claim的任何修改，均需獨立docs PR與Merge Gate。

---

## 18. Acceptance Gate for Future Code PR

- 完整符合 `pcie_eq-pattern-config-v1`。
- 11種pattern可透過單一pure API解析。
- Constructor validation、defaults、irrelevant-field rejection與validation matrix通過。
- Random／PRBS output與既有core bit-exact一致。
- Global RNG、dtype、shape、raw values與GUI baseline不變。
- Serialization exact round-trip且unknown version拒絕。
- Module boundary通過。
- Existing 192 tests全部通過，總數增加。
- GitHub Actions、`import main`與`git diff --check`通過。
- 無GUI、pipeline、TXEQ、Channel、RXEQ、Preset或simulation math變更。
