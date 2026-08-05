# Pattern Configuration Contract

> Contract ID：`pcie_eq-pattern-config-v1`  
> 文件狀態：Frozen implementation contract after merge  
> 適用 Repository：`Mike87117/PCIE-TX-EQ-Simulator`  
> 規劃基準：`main@4a11b26176d032fcc5dbe369c41252a960f4ea7a`  
> Production baseline：`c4fd8c8191919c30d8e28383d94804fe3e68db25`／192 tests  
> Related Roadmap：Issue #48  
> Related Evidence Gate：Issue #58

---

## 1. 目的

本文件定義 GUI-independent Pattern Configuration 的第一版固定契約，讓 random、deterministic、PRBS 與 user-defined pattern 可以透過同一個 request／result boundary 產生，並保留目前已驗證的 value、shape、dtype、RNG 與 GUI compatibility。

本 Contract 是專案自有的軟體介面，不是 PCI-SIG pattern specification，也不新增任何 protocol training sequence 或 compliance pattern。

文件合併後，production code 與 tests 必須逐項符合本文件。實作者不得自行改變 taxonomy、default、dtype、RNG policy、serialization 或 validation rule；若發現衝突，必須停止並由 Planner／Reviewer另開文件變更。

---

## 2. 模型等級與宣稱界線

### 2.1 Contract layer

Pattern Configuration 本身屬於：

```text
Project-owned software contract
```

它負責描述、驗證、序列化與解析現有 pattern generator，不代表 PCIe protocol 或 compliance method。

### 2.2 Underlying pattern models

- Existing random／deterministic NRZ 與 random PAM4：以已合併 Repository 行為與 regression tests 為準。
- PRBS7／9／15／23／31：依 `docs/PRBS_CONVENTION.md`，模型等級為 **Reference-model-derived general test pattern**。
- User-defined values：只做 project-owned data validation 與 exact normalization。

### 2.3 Allowed claims

完成實作後可以宣稱：

- 提供 versioned、GUI-independent pattern request／result contract。
- 固定設定可重現 seeded random、deterministic、PRBS 與 user-defined output。
- `seed=None` 保留目前 global NumPy RNG compatibility。
- Output shape、dtype、domain 與 resolved parameters 可被程式驗證與序列化。

### 2.4 Forbidden claims

不得宣稱：

- PCIe compliance pattern。
- PCI-SIG Reference Pattern。
- PCIe training sequence／ordered set。
- PAM4 PRBSQ／QPRBS。
- Gen6 FEC pattern。
- 與指定 FPGA、transceiver、BERT 或示波器的初始 phase bit-exact。
- `seed=None` 的 request 可只靠 config 在另一個 process 重現。

---

## 3. Evidence Registry

| Evidence | Access | Contract relevance |
|---|---|---|
| `pcie_eq/patterns.py` at production merge `c4fd8c8191919c30d8e28383d94804fe3e68db25` | Repository | 現有 generator API、validation、value、shape、dtype 與 RNG 行為 |
| `tests/test_patterns.py` at production merge `c4fd8c8191919c30d8e28383d94804fe3e68db25` | Repository | seeded golden vectors、global RNG equivalence、dtype fingerprint、PRBS validation |
| `docs/PRBS_CONVENTION.md` | Repository | PRBS convention ID、polynomial、state、Golden vectors 與宣稱限制 |
| `pcie_eq/gui/window.py`、`nrz_controller.py` | Repository | NRZ global RNG initialization、Generate New Waveform call sequence與 native integer dtype |
| `pcie_eq/gui/pam4_controller.py`、`gui/random_data.py` | Repository | PAM4 random compatibility wrapper與 float64 symbol domain |
| NumPy legacy random generation documentation | Public primary documentation | `RandomState` seed範圍與 global legacy RNG 行為：https://numpy.org/doc/2.0/reference/random/legacy.html |
| NumPy 2.4 `asarray` documentation | Public primary documentation | array-like conversion、dtype與order語義：https://numpy.org/doc/2.4/reference/generated/numpy.asarray.html |

Repository regression contract 優先於外部 library 的較新建議。第一版不得將 existing `RandomState`／global RNG 行為改成 `default_rng()`。

---

## 4. Public API Proposal

後續 code implementation 新增獨立 pure module：

```text
pcie_eq/pattern_config.py
```

公開介面固定為：

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

`__all__` 順序固定為：

```python
[
    "PATTERN_CONFIG_CONTRACT_ID",
    "PatternConfig",
    "PatternResult",
    "generate_pattern",
]
```

第一版不提供 class hierarchy、plugin registry、iterator、stateful generator、continuation token 或 async API。

---

## 5. Pattern Type Taxonomy

Pattern type 是 case-sensitive exact string，不做 trim、alias、大小寫轉換或猜測。

| `pattern_type` | Modulation | Canonical domain | Existing basis |
|---|---|---|---|
| `nrz_random` | `nrz` | `bits` | `generate_random_nrz_bits` |
| `nrz_all_zeros` | `nrz` | `bits` | `generate_nrz_all_zeros` |
| `nrz_all_ones` | `nrz` | `bits` | `generate_nrz_all_ones` |
| `nrz_alternating` | `nrz` | `bits` | `generate_nrz_alternating` |
| `nrz_long_run` | `nrz` | `bits` | `generate_nrz_long_run` |
| `nrz_single_transition` | `nrz` | `bits` | `generate_nrz_single_transition` |
| `nrz_single_bit_pulse` | `nrz` | `bits` | `generate_nrz_single_bit_pulse` |
| `nrz_prbs` | `nrz` | `bits` | `generate_prbs_bits` |
| `nrz_user_bits` | `nrz` | `bits` | project-owned exact user-data validation |
| `pam4_random` | `pam4` | `symbols` | `generate_random_pam4_symbols` |
| `pam4_user_symbols` | `pam4` | `symbols` | project-owned exact user-data validation |

第一版沒有 generic `random`、generic `user_values` 或獨立 `modulation` input field。Modulation與domain由 `pattern_type` 唯一導出，避免 contradictory configurations。

---

## 6. Common Field Contract

### 6.1 `schema_version`

- Exact value：`pcie_eq-pattern-config-v1`。
- Non-string：`TypeError`。
- Unknown string：`ValueError`。
- 不做 forward-compatible fallback。

### 6.2 `pattern_type`

- 必須是 Python `str`。
- 不支援空字串或 taxonomy 以外的值。
- Non-string：`TypeError`。
- Unsupported string：`ValueError`。

### 6.3 `count`

- 必須是 Python `int`；`bool` 不接受。
- 必須 `count >= 0`。
- NRZ：bit count。
- PAM4：symbol count。
- Output shape 永遠是 `(count,)`。
- `nrz_single_bit_pulse` 額外要求 `count > 0`。
- 即使 `count == 0`，所有其他 fields仍必須完整驗證。

### 6.4 Irrelevant fields

每個 pattern type 只允許本文件 field matrix 指定的 parameters。任何不適用 field 只要不是 `None`，一律 `ValueError`。

禁止 silent ignore。這項規則確保 serialized config 中的 typo 或 stale parameter 不會被掩蓋。

---

## 7. Pattern-specific Field Matrix

符號：

- `R`：required，不能是 `None`。
- `O`：optional；`None` 會套用固定 default。
- `–`：必須是 `None`。

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

PRBS fields 包含：

```text
prbs_order: required
prbs_initial_state: optional
prbs_convention_id: optional
```

---

## 8. Defaults and Validation

### 8.1 Bit fields

`first_bit`、`initial_bit`、`baseline_bit`：

- `None` default 為 `0`。
- Explicit value 必須是 Python `int` 0 或 1。
- `bool` 不接受。
- Wrong type：`TypeError`。
- Integer outside 0／1：`ValueError`。

### 8.2 `run_length`

- Required for `nrz_long_run`。
- Python `int` only；`bool` 不接受。
- 必須 `>= 1`。
- 即使 `count == 0` 仍需提供 valid `run_length`。

### 8.3 `transition_index`

- Required for `nrz_single_transition`。
- Python `int` only；`bool` 不接受。
- 必須 `0 <= transition_index <= count`。
- `0` 代表從第一個 output bit 起已完成 transition。
- `count` 代表 output 全部維持 initial bit。

### 8.4 `pulse_index`

- Required for `nrz_single_bit_pulse`。
- Python `int` only；`bool` 不接受。
- 必須 `0 <= pulse_index < count`。
- 因此本 pattern 不允許 `count == 0`。

### 8.5 PRBS

`nrz_prbs` 必須遵守：

```text
prbs_order ∈ {7, 9, 15, 23, 31}
prbs_initial_state = None 或符合 docs/PRBS_CONVENTION.md 的 valid nonzero n-bit state
prbs_convention_id = None 或 "pcie_eq-prbs-fibonacci-lsb-v1"
```

Resolved config 必須將：

- `prbs_initial_state=None` 解析成 `(1 << prbs_order) - 1`。
- `prbs_convention_id=None` 解析成 `pcie_eq-prbs-fibonacci-lsb-v1`。

即使 `count == 0` 也必須驗證 order、state 與 convention ID。

### 8.6 User values

Public dataclass 的 `user_values` 只接受：

```text
tuple 或 None
```

Serialized dictionary 使用 JSON array；`from_dict()` 必須複製並轉成 tuple。直接傳 list／ndarray 給 dataclass 後呼叫 `generate_pattern()` 必須 `TypeError`，避免 frozen config 仍引用外部 mutable container。

通用規則：

- `len(user_values) == count`。
- 不做 truncate、pad、repeat、broadcast、rounding 或 tolerance-based correction。
- Result 必須配置新 array，不得與 input container alias。

`nrz_user_bits`：

- 每個 element 必須是 Python `int` 0／1 或 Python `bool`。
- `bool` 解析成 native integer 0／1。
- Float 0.0／1.0 不接受。
- Output dtype 為 platform native signed `int`。

`pam4_user_symbols`：

- 每個 element 必須是 Python `int` 或 `float`；`bool` 不接受。
- 必須 finite。
- 只接受與下列 canonical Python float exact-equal 的值：

```python
(-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0)
```

- 不使用 `isclose`、rounding 或 quantization。
- Output dtype exact `numpy.float64`。

CSV／measurement tolerance、symbol snapping 與 level fitting 不屬於本 Contract。

---

## 9. RNG Contract

### 9.1 Applicable patterns

只有：

```text
nrz_random
pam4_random
```

可使用 `seed`。其他 pattern 的 `seed` 必須是 `None`。

### 9.2 Seed type and range

- `None`，或
- Python `int`，且 `0 <= seed <= 2**32 - 1`。
- `bool`、NumPy integer、float、string、sequence均不接受。

本專案採用較窄、JSON-safe 的 scalar seed contract，即使 NumPy `RandomState` 也接受某些 array-like seed，第一版仍禁止這些形式。

### 9.3 `seed=None`

- 必須委派現有 generator 的 global `numpy.random` path。
- `rng_mode = "global"`。
- 不可聲稱只靠 serialized config 可重現。
- 必須維持目前 global RNG consumption order。
- `count == 0` 不消耗 RNG state。

NRZ GUI 目前在 module initialization 設定 `np.random.seed(7)`，並以 global RNG生成 initial bits；後續 Generate New Waveform 也沿用 global RNG。Pattern Config 不得改變此 baseline。

### 9.4 Explicit integer seed

- 必須委派現有 isolated `numpy.random.RandomState(seed)` path。
- `rng_mode = "seeded"`。
- 不得讀取或修改 global NumPy RNG state。
- 相同 config 必須 bit-exact repeatable。

### 9.5 Non-random patterns

- `rng_mode = "none"`。
- 不得讀取或修改任何 RNG state。

---

## 10. Output and Result Contract

### 10.1 `PatternResult.values`

- Type exact `numpy.ndarray`。
- 1D，shape exact `(count,)`。
- C-contiguous。
- 產生新 output array；user input不得被修改或共享 writable storage。

### 10.2 Dtype matrix

| Pattern group | Exact dtype contract |
|---|---|
| `nrz_random`、`nrz_all_zeros`、`nrz_all_ones`、`nrz_alternating`、`nrz_long_run`、`nrz_single_transition`、`nrz_single_bit_pulse`、`nrz_user_bits` | `numpy.dtype(int)`，即 platform native signed integer |
| `nrz_prbs` | exact `numpy.int8` |
| `pam4_random`、`pam4_user_symbols` | exact `numpy.float64` |

不得在 aggregator 中把 PRBS cast 成 native int，也不得把一般 NRZ cast 成 int8。此異質性是已驗證 compatibility contract。

### 10.3 Value matrix

- NRZ bits：只含 0／1。
- PAM4 symbols：只含 `-1.0`、`-1.0/3.0`、`1.0/3.0`、`1.0`。
- Pattern Config 不自動把 NRZ bits 轉為 `-1.0／+1.0` symbols；下游若需要，必須明確呼叫 `nrz_bits_to_symbols()`。

### 10.4 Result metadata

`PatternResult` fixed values：

- `resolved_config`：所有 applicable defaults 已填入，所有 irrelevant fields 為 `None`。
- `modulation`：`"nrz"` 或 `"pam4"`。
- `domain`：`"bits"` 或 `"symbols"`。
- `rng_mode`：`"global"`、`"seeded"` 或 `"none"`。

`PatternResult` 不保存 global RNG state、final PRBS state、hardware phase、GUI state、TXEQ、Channel 或 RXEQ config。

---

## 11. Resolution Rules

`generate_pattern()` 執行順序固定為：

1. 確認 input exact type 為 `PatternConfig`；其他 type 為 `TypeError`。
2. 驗證 schema、pattern type、count與所有 fields。
3. 拒絕 irrelevant fields。
4. 填入 applicable defaults，建立新的 `resolved_config`。
5. 依 exact pattern type 呼叫既有 pure generator，或執行 user-values copy／normalization。
6. 驗證 internal result shape、dtype與value domain；若 production helper違反 contract，拋出 `RuntimeError`，不可 silent repair。
7. 回傳 `PatternResult`。

Validation 必須發生在任何 RNG consumption 前。Invalid config 不得推進 global RNG state。

---

## 12. Serialization Contract

### 12.1 Canonical dictionary keys

`to_dict()` 必須按照下列順序建立新的 dictionary，所有 keys 必須存在，包括 value 為 `None` 的 fields：

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

`user_values`：

- tuple → 新 JSON-safe list。
- `None` → `None`。

其他值僅限 JSON scalar：string、integer、float、boolean、null。

### 12.2 `from_dict()`

- Input 必須是 `collections.abc.Mapping`；否則 `TypeError`。
- Keys 必須與 canonical key set exact match。
- Missing 或 extra key：`ValueError`，錯誤訊息需列出 keys。
- 不接受 legacy alias、camelCase、case-insensitive key或nested parameters。
- `user_values` 只接受 JSON list 或 `None`，並複製成 tuple。
- 建立 `PatternConfig` 後，完整 validation 最遲必須在 `generate_pattern()` 前執行；建議 `from_dict()` 直接執行 structural validation。

### 12.3 Round-trip

對 valid canonical config：

```python
restored = PatternConfig.from_dict(config.to_dict())
assert restored == config
```

對 resolved config也必須成立。

Dictionary與list均為新物件；修改 serialized output 不得改變原 config。

### 12.4 Version behavior

- V1 reader只接受 exact V1。
- 不自動升級 unknown version。
- 未來 migration 必須另立 Scenario／Schema Issue，不得在 V1 parser 猜測。

---

## 13. Canonical Examples

### 13.1 Seeded NRZ random

```python
PatternConfig(
    pattern_type="nrz_random",
    count=10,
    seed=42,
)
```

Expected：

```text
modulation: nrz
domain: bits
rng_mode: seeded
dtype: numpy.dtype(int)
values: [0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
```

### 13.2 Global RNG PAM4

```python
PatternConfig(
    pattern_type="pam4_random",
    count=4096,
    seed=None,
)
```

Expected：

```text
rng_mode: global
reproducible from config alone: no
dtype: numpy.float64
```

### 13.3 Long run

```python
PatternConfig(
    pattern_type="nrz_long_run",
    count=10,
    run_length=3,
    first_bit=None,
)
```

Resolved `first_bit=0`，values：

```text
[0, 0, 0, 1, 1, 1, 0, 0, 0, 1]
```

### 13.4 PRBS7

```python
PatternConfig(
    pattern_type="nrz_prbs",
    count=16,
    prbs_order=7,
)
```

Resolved：

```text
prbs_initial_state: 127
prbs_convention_id: pcie_eq-prbs-fibonacci-lsb-v1
dtype: numpy.int8
values: 1111111000000100
```

### 13.5 User PAM4 symbols

```python
PatternConfig(
    pattern_type="pam4_user_symbols",
    count=4,
    user_values=(-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0),
)
```

Output 是新的 `numpy.float64` array，與 input tuple 不共享 storage。

---

## 14. Error Contract

### 14.1 Exception type

使用：

- `TypeError`：Python type／container type不符合。
- `ValueError`：enum、range、length、value、field applicability、schema keys或version不符合。
- `RuntimeError`：validated request所呼叫的內部 generator 回傳違反 frozen output contract。

不使用 `AssertionError` 作為 public validation。

### 14.2 Error message stability

Exact full message不屬於 frozen API，但訊息必須包含：

- 失敗 field name。
- invalid value或type。
- 合法範圍／allowed values或 applicable pattern。

Tests應比對 exception type與必要 field-name substring，不應凍結完整標點。

### 14.3 No coercion

禁止：

- string轉integer。
- float count／index轉integer。
- float 0.0／1.0轉NRZ bit。
- PAM4 level tolerance snapping。
- pattern type alias。
- unknown fields忽略。
- invalid PRBS convention fallback。

---

## 15. Independent Validation Matrix

後續 code PR 至少需要以下 tests。Expected values 必須 hardcode 或來自 test-side獨立 formulation，不得使用 production function動態建立自己的 oracle。

### 15.1 Taxonomy and dispatch

- 11 種 pattern type均有一個 small-vector expected case。
- Unsupported／case mismatch／whitespace pattern type拒絕。
- modulation與domain metadata exact。

### 15.2 Random patterns

- NRZ seed 42、count 10 hardcoded vector：`[0,1,0,0,0,1,0,0,0,1]`。
- PAM4 seed 42、count 10 使用現有 hardcoded vector。
- Same seed repeatability。
- Different seed difference。
- Explicit seed不修改 global RNG state。
- `seed=None` 與 direct legacy `np.random.randint`在相同 pre-state 下 exact一致。
- Invalid config不消耗 global RNG。
- `count=0`不消耗 RNG。

### 15.3 Deterministic NRZ

沿用現有 hardcoded cases：

- all zero／one。
- alternating first bit 0／1。
- long run count 10、run 3。
- transition boundary 0／count。
- pulse boundary與 invalid zero count。

### 15.4 PRBS

- V1 all-ones frozen prefix。
- Custom initial state prefix。
- Resolved convention ID與all-ones state。
- PRBS output保持 exact int8。
- Pattern Config不得重新實作不同 recurrence；只委派 frozen PRBS core。

### 15.5 User values

- NRZ tuple 0／1與bool normalization。
- NRZ float rejection。
- PAM4 canonical four levels。
- NaN、Inf、off-level value rejection。
- Length exact match。
- Empty tuple／count zero。
- Input tuple未修改；output為新 array。
- Direct list／ndarray dataclass input拒絕。
- Serialized list由 `from_dict()`複製成 tuple。

### 15.6 Serialization

- 11 pattern types round-trip。
- Canonical keys與order。
- All keys present，包括 `None`。
- Missing／extra keys拒絕。
- Unknown version拒絕。
- Serialized dictionary／user list mutation不影響 config。
- Resolved config round-trip。

### 15.7 Output contract

- Exact ndarray、shape、dtype、C-contiguous與value set。
- General NRZ native int不被cast。
- PRBS int8不被cast。
- PAM4 float64不被cast。

### 15.8 Boundary and compatibility

- 新 module不可 import PyQt、PySide、pyqtgraph、main、GUI、pipeline或controller。
- `pcie_eq.patterns.__all__`與既有 functions不變。
- `window.py`、controllers、random wrapper與GUI call sequence不變。
- Existing 192 tests全部通過，總數增加。
- `python -c "import main"`通過。

---

## 16. Implementation Boundary

文件合併後的 code Issue 預期只允許新增／修改：

```text
pcie_eq/pattern_config.py
tests/test_pattern_config.py
tests/test_pattern_config_module_boundary.py
```

除非 Reviewer另行核准，不得修改：

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

第一個 code PR只建立 pure contract implementation，不整合 GUI或simulation pipeline。

---

## 17. Non-scope

- GUI pattern selector與parameter widgets。
- 將現有 window state改成 `PatternConfig`。
- random button行為變更。
- NRZ bit-to-symbol自動轉換。
- PAM4 bit mapping、Gray coding或precoding。
- PRBSQ／QPRBS／FEC／training sequence。
- file import、CSV tolerance、measurement level fitting。
- Channel、Cursor、Sampling、RXEQ、Scenario、Sweep與Auto EQ。
- streaming／chunk continuation與final LFSR state。

---

## 18. Stop Conditions and Change Control

實作者遇到以下任一情況必須停止，不得自行變更文件：

- 現有 generator實際行為與本文件 evidence不一致。
- 需要修改 GUI、pipeline或existing pattern function才能完成 pure contract。
- 無法保留 global RNG consumption order。
- 需要 silent cast才能統一 dtype。
- 新 pattern type缺少 authoritative definition或independent validation oracle。
- PRBS需要不同 convention、polarity或phase。
- serialized V1無法在不猜測的情況下解析。

任何 taxonomy、default、dtype、seed policy、serialization key或allowed claim修改，均需獨立 docs PR與 Reviewer Merge Gate。

---

## 19. Acceptance Gate for Future Code PR

- 完整符合 `pcie_eq-pattern-config-v1`。
- 11種 pattern type均可透過單一 pure API解析。
- 所有 defaults、irrelevant-field rejection與validation matrix通過。
- random／PRBS output與既有 core bit-exact一致。
- global RNG、dtype、shape、raw values與GUI baseline不變。
- serialization exact round-trip且unknown version拒絕。
- module boundary通過。
- Existing 192 tests全部通過，總數增加。
- GitHub Actions／`import main`／`git diff --check`通過。
- 無 GUI、pipeline、TXEQ、Channel、RXEQ、Preset或simulation math變更。
