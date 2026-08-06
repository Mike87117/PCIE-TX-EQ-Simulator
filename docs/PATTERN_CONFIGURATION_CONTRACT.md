# Pattern Configuration Contract

> Contract ID：`pcie_eq-pattern-config-v1`  
> Contract revision：`1.1`（schema ID 不變；尚無 production implementation）  
> 文件狀態：Frozen implementation contract after merge  
> 適用 Repository：`Mike87117/PCIE-TX-EQ-Simulator`  
> Production baseline：`c4fd8c8191919c30d8e28383d94804fe3e68db25`／192 tests  
> Related Roadmap：Issue #48  
> Original Evidence Gate：Issue #58  
> Dtype Contract Erratum：Issue #64

---

## 1. 目的與界線

本文件定義 GUI-independent Pattern Configuration v1，使現有 random、deterministic、PRBS 與 user-defined pattern 可透過單一 request／result boundary 產生，同時保存已驗證的 value、shape、dtype、RNG 與 GUI compatibility。

本 Contract 是專案自有軟體規格，不是 PCI-SIG pattern specification，也不新增 protocol training sequence、compliance pattern、PRBSQ／QPRBS 或 FEC pattern。

文件合併後，Gemini 只能依本文件實作 pure code 與 tests。若 code、tests 或現有 generator 與本文件衝突，必須停止並由 Planner／Reviewer另開 docs PR；不得自行修改 taxonomy、defaults、dtype、RNG、serialization、validation 或 claims。

### 1.1 模型等級

- Contract layer：**Project-owned software contract**。
- Existing NRZ／PAM4 random 與 deterministic patterns：Repository regression-derived。
- PRBS7／9／15／23／31：依 `docs/PRBS_CONVENTION.md`，屬 **Reference-model-derived general test pattern**。
- User-defined values：project-owned exact data validation。

### 1.2 Allowed claims

- Versioned、GUI-independent pattern request／result contract。
- Seeded random、deterministic、PRBS 與 user-defined output 可依固定 config 重現。
- `seed=None` 保留 legacy global NumPy RNG compatibility。
- Output domain、shape、dtype 與 resolved parameters 可驗證與序列化。

### 1.3 Forbidden claims

- PCIe compliance／PCI-SIG Reference Pattern。
- PCIe training sequence／ordered set。
- PAM4 PRBSQ／QPRBS 或 Gen6 FEC pattern。
- 與指定 FPGA、transceiver、BERT 或示波器初始 phase bit-exact。
- `seed=None` 可只靠 config 在另一個 process 重現。
- 所有 NRZ pattern 具有相同 integer width。

---

## 2. Evidence Registry

| Evidence | Access | Contract relevance |
|---|---|---|
| `pcie_eq/patterns.py` at production merge `c4fd8c8191919c30d8e28383d94804fe3e68db25` | Repository | Existing generator API、empty／non-empty branches、validation、value、shape、dtype 與 RNG |
| `tests/test_patterns.py` at production merge `c4fd8c8191919c30d8e28383d94804fe3e68db25` | Repository | Seeded golden vectors、global RNG equivalence、Windows／non-Windows dtype fingerprints、PRBS validation |
| `docs/PRBS_CONVENTION.md` | Repository | PRBS convention、state、Golden vectors 與宣稱限制 |
| `pcie_eq/gui/window.py`、`nrz_controller.py` | Repository | NRZ global RNG initialization、Generate New Waveform call sequence 與 raw-byte compatibility |
| `pcie_eq/gui/pam4_controller.py`、`gui/random_data.py` | Repository | PAM4 random compatibility wrapper 與 float64 symbol domain |
| NumPy legacy random documentation | Public primary | `RandomState` scalar seed range 與 global legacy RNG |
| NumPy `numpy.random.randint` documentation | Public primary | Default dtype 是 C long；Windows 為 32-bit，其他 64-bit 平台通常為 64-bit；`dtype=int` 與多數 NumPy function 的 default integer 不同 |
| NumPy `asarray` documentation | Public primary | Array conversion、dtype 與 order semantics |

Repository regression contract 優先。V1 不得將 existing `RandomState`／global RNG 改成 `default_rng()`。

### 2.1 Dtype erratum rationale

Existing `generate_random_nrz_bits()`：

```python
if count == 0:
    return np.array([], dtype=int)
if seed is None:
    return np.random.randint(0, 2, count)
rng = np.random.RandomState(seed)
return rng.randint(0, 2, count)
```

因此 dtype 取決於 branch：

- Empty branch：`numpy.dtype(int)`，即 NumPy platform integer／`intp`。
- Non-empty branch：legacy `randint` default C-long，表示為 `numpy.dtype("l")`。
- 在 64-bit Windows，`numpy.dtype("l")` 通常是 `int32`，而 `numpy.dtype(int)` 是 `int64`。

這是既有 compatibility behavior，不是理想化統一設計。V1 aggregator 必須保存此差異，不得 cast 掩蓋。

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

`PatternConfig.__post_init__()` 必須完成全部 input validation，包括 irrelevant-field rejection；正常 public API 不得建立無效 `PatternConfig`。`generate_pattern()` 仍須在任何 RNG 操作前做防禦性重驗。

V1 不提供 subclass hierarchy、plugin registry、iterator、stateful generator、continuation token 或 async API。

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

### 5.1 `schema_version`

- Exact `pcie_eq-pattern-config-v1`。
- Non-string：`TypeError`。
- Unknown string：`ValueError`。
- 不做 fallback 或 migration 猜測。

### 5.2 `pattern_type`

- Python `str` only。
- Non-string：`TypeError`。
- Unsupported／empty／case mismatch／whitespace variant：`ValueError`。

### 5.3 `count`

- Python `int` only；`bool` 不接受。
- `count >= 0`。
- NRZ 表示 bit count；PAM4 表示 symbol count。
- Output shape exact `(count,)`。
- `nrz_single_bit_pulse` 要求 `count > 0`。
- `count == 0` 仍須驗證所有其他 fields。

### 5.4 Irrelevant fields

每個 pattern type 只允許 field matrix 指定 parameters。不適用 field 只要不是 `None`，一律 `ValueError`；禁止 silent ignore。

---

## 6. Field Applicability Matrix

- `R`：required。
- `O`：optional；`None` 套用固定 default。
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

### 7.1 Bit defaults

`first_bit`、`initial_bit`、`baseline_bit`：

- `None` resolves to `0`。
- Explicit value 必須是 Python `int` 0／1；`bool` 不接受。
- Wrong type：`TypeError`；out of range：`ValueError`。

### 7.2 `run_length`

- `nrz_long_run` required。
- Python `int` only；`bool` 不接受。
- `run_length >= 1`，即使 `count == 0` 仍需 valid。

### 7.3 `transition_index`

- `nrz_single_transition` required。
- Python `int` only；`bool` 不接受。
- `0 <= transition_index <= count`。
- `0`：第一個 output 起已 transition；`count`：全部維持 initial bit。

### 7.4 `pulse_index`

- `nrz_single_bit_pulse` required。
- Python `int` only；`bool` 不接受。
- `0 <= pulse_index < count`。

### 7.5 PRBS

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

`count == 0` 仍驗證 order、state 與 convention。

### 7.6 User values container

Public dataclass 只接受：

```text
user_values: tuple 或 None
```

直接傳 list／ndarray：`TypeError`。Serialized JSON array 由 `from_dict()` 複製並轉 tuple，避免 frozen config 引用外部 mutable container。

通用規則：

- `len(user_values) == count`。
- 不 truncate、pad、repeat、broadcast、round 或 tolerance-correct。
- Result 必須建立新 array，不修改 input 或共享 writable storage。

`nrz_user_bits`：

- Element 只接受 Python `int` 0／1 或 Python `bool`。
- Bool resolves to integer 0／1。
- Float 0.0／1.0 不接受。
- Output dtype exact `numpy.dtype(int)`。

`pam4_user_symbols`：

- Element 只接受 Python `int`／`float`；`bool` 不接受。
- 必須 finite。
- 必須與下列 canonical Python float exact-equal：

```python
(-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0)
```

- 不使用 `isclose`、rounding 或 quantization。
- Output dtype exact `numpy.float64`。

CSV tolerance、measurement snapping 與 level fitting 不屬於本 Contract。

---

## 8. RNG Contract

只有 `nrz_random`、`pam4_random` 可使用 `seed`；其他 pattern 的 `seed` 必須為 `None`。

### 8.1 Seed type and range

- `None`，或 Python `int`，`0 <= seed <= 2**32 - 1`。
- `bool`、NumPy integer、float、string 與 sequence 不接受。
- V1 刻意使用 JSON-safe scalar seed，不開放 NumPy array-like seed。

### 8.2 `seed=None`

- 委派現有 global `numpy.random` path。
- `rng_mode = "global"`。
- 保留 global RNG consumption order。
- `count == 0` 不消耗 RNG state。
- 不得宣稱 config-alone reproducibility。

NRZ GUI 目前於 module initialization 呼叫 `np.random.seed(7)`，以 global RNG 建立 initial bits；Generate New Waveform 也沿用 global RNG。Pattern Config 不得改變此 baseline。

### 8.3 Explicit seed

- 委派現有 `numpy.random.RandomState(seed)` path。
- `rng_mode = "seeded"`。
- 不讀取或修改 global NumPy RNG state。
- 相同 config bit-exact repeatable。

### 8.4 Non-random patterns

- `rng_mode = "none"`。
- 不讀取或修改 RNG state。

所有 validation 必須發生於 RNG consumption 前。Constructor 或 `generate_pattern()` 失敗不得推進 global RNG。

---

## 9. Output and Result Contract

### 9.1 `PatternResult.values`

- Exact `numpy.ndarray`。
- 1D、shape `(count,)`、C-contiguous。
- User-defined output 為新 array，不與 input 共享 writable storage。

### 9.2 Exact dtype matrix

| Pattern group | Exact dtype contract |
|---|---|
| `nrz_random`, `count > 0` | `numpy.dtype("l")`，legacy C-long dtype；Windows通常為 `int32`，其他 64-bit 平台通常為 `int64` |
| `nrz_random`, `count == 0` | `numpy.dtype(int)`，保存 existing empty-array branch |
| `nrz_all_zeros`、`nrz_all_ones`、`nrz_alternating`、`nrz_long_run`、`nrz_single_transition`、`nrz_single_bit_pulse`、`nrz_user_bits` | `numpy.dtype(int)` |
| `nrz_prbs` | exact `numpy.int8` |
| `pam4_random`、`pam4_user_symbols` | exact `numpy.float64` |

規則：

- Aggregator 必須直接保存 existing generator output dtype，不得 cast。
- `numpy.dtype("l")` 與 `numpy.dtype(int)` 不得視為同義詞。
- `nrz_random` empty／non-empty dtype 差異屬 legacy compatibility contract。
- 不得為了統一外觀把 random NRZ cast 成 `dtype=int`、把 deterministic NRZ cast 成 C long，或把 PRBS cast 成一般 integer。
- 未來若要統一 dtype，必須另立 explicit baseline-change Issue／PR，更新 GUI raw-byte fingerprints、cross-platform contract 與必要的 schema/version policy。

### 9.3 Value domain

- NRZ：只含 0／1 bits。
- PAM4：只含 `-1.0`、`-1.0/3.0`、`1.0/3.0`、`1.0`。
- Contract 不自動把 NRZ bits 轉成 `-1.0／+1.0` symbols；下游若需要，須明確呼叫 `nrz_bits_to_symbols()`。

### 9.4 Metadata

`PatternResult`：

- `resolved_config`：applicable defaults 已填入；irrelevant fields 皆 `None`。
- `modulation`：`"nrz"`／`"pam4"`。
- `domain`：`"bits"`／`"symbols"`。
- `rng_mode`：`"global"`／`"seeded"`／`"none"`。

Result 不保存 global RNG state、final PRBS state、hardware phase、GUI state、TXEQ、Channel 或 RXEQ config。

---

## 10. Resolution Order

`generate_pattern()` 固定流程：

1. Input exact type 必須是 `PatternConfig`，否則 `TypeError`。
2. 防禦性重驗 schema、pattern type、count、applicable 與 irrelevant fields。
3. 填入 defaults 並建立新的 `resolved_config`。
4. 依 exact pattern type 委派現有 pure generator，或 copy／normalize user values。
5. 依 §9.2 的 pattern-specific／count-specific matrix 驗證 result shape、dtype 與 value domain。
6. Helper 若違反 frozen output contract，拋出 `RuntimeError`；不可 silent repair 或 cast。
7. 回傳 `PatternResult`。

V1 aggregator 不得重新實作 PRBS recurrence、random algorithm 或 existing deterministic generator。

---

## 11. Serialization Contract

### 11.1 Canonical keys

`to_dict()` 建立新 dictionary，key order 與 key set exact 如下；所有 keys 均存在，包括 value 為 `None` 者：

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

- Tuple `user_values` → 新 JSON-safe list。
- `None` → `None`。
- 其他 value 僅使用 JSON scalar。

### 11.2 `from_dict()`

- Input 必須是 `collections.abc.Mapping`，否則 `TypeError`。
- Key set 必須 exact match；missing／extra key 為 `ValueError`，訊息列出 keys。
- 不接受 alias、camelCase、case-insensitive key 或 nested parameters。
- `user_values` 只接受 JSON list／`None`，並 copy 成 tuple。
- 透過 `PatternConfig` constructor 完成全部 semantic validation；不得回傳無效 config。

### 11.3 Round-trip

```python
restored = PatternConfig.from_dict(config.to_dict())
assert restored == config
```

Input config 與 resolved config 均須成立。Dictionary 與 list 為新物件；修改 serialized output 不得改變原 config。

V1 reader 只接受 exact V1；future migration 另立 Issue，不自行猜測。

---

## 12. Canonical Cases

### 12.1 Seeded NRZ random — non-empty

```python
PatternConfig(pattern_type="nrz_random", count=10, seed=42)
```

```text
modulation: nrz
domain: bits
rng_mode: seeded
dtype: numpy.dtype("l")
values: [0,1,0,0,0,1,0,0,0,1]
```

在 current 64-bit Windows CI，expected dtype 是 `numpy.int32`；在多數 64-bit non-Windows，expected dtype 是 `numpy.int64`。Cross-platform assertion 必須使用 `numpy.dtype("l")`。

### 12.2 NRZ random — empty

```python
PatternConfig(pattern_type="nrz_random", count=0, seed=42)
```

```text
rng_mode: seeded
dtype: numpy.dtype(int)
shape: (0,)
RNG consumption: none
```

Empty output 不可改成 C-long dtype，因 existing helper 明確建立 `np.array([], dtype=int)`。

### 12.3 Long run

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
dtype: numpy.dtype(int)
```

### 12.4 PRBS7

```python
PatternConfig(pattern_type="nrz_prbs", count=16, prbs_order=7)
```

```text
resolved state: 127
convention: pcie_eq-prbs-fibonacci-lsb-v1
dtype: numpy.int8
values: 1111111000000100
```

### 12.5 User PAM4

```python
PatternConfig(
    pattern_type="pam4_user_symbols",
    count=4,
    user_values=(-1.0, -1.0/3.0, 1.0/3.0, 1.0),
)
```

Output 為新 `numpy.float64` array。

---

## 13. Error Contract

- `TypeError`：Python type／container type 錯誤。
- `ValueError`：enum、range、length、value、field applicability、schema key 或 version 錯誤。
- `RuntimeError`：validated request 呼叫的 internal generator 違反 frozen output contract。
- Public validation 不使用 `AssertionError`。

Exact 完整錯誤文字不凍結，但訊息必須包含 field name、invalid value／type 與合法範圍或 allowed values。Tests 只比對 exception type 與必要 field substring。

禁止 coercion：

- string → integer。
- float count／index → integer。
- float 0.0／1.0 → NRZ bit。
- PAM4 tolerance snapping。
- pattern alias。
- unknown field ignore。
- invalid PRBS convention fallback。
- dtype normalization cast。

---

## 14. Independent Validation Matrix

Expected values 必須 hardcode 或由 test-side independent formulation 取得；不得呼叫 production aggregator 建立自己的 oracle。

### 14.1 Taxonomy／dispatch

- 11 種 pattern type 各一個 small-vector case。
- Unsupported／case mismatch／whitespace 拒絕。
- Modulation、domain 與 rng_mode exact。
- Constructor 立即拒絕 invalid／irrelevant fields。

### 14.2 Random

- NRZ seed 42／count 10 hardcoded vector。
- Non-empty NRZ random dtype exact `np.dtype("l")`，global 與 seeded path 均驗證。
- Empty NRZ random dtype exact `np.dtype(int)`，global 與 seeded path 均驗證。
- 在 current 64-bit Windows CI，額外 assert non-empty `np.int32`、empty `np.int64`；此 platform-specific test 必須用 platform guard。
- PAM4 seed 42／count 10 沿用現有 hardcoded vector。
- Same seed repeatability 與 different seed difference。
- Explicit seed 不修改 global RNG。
- `seed=None` 與 direct legacy `np.random.randint` 在相同 pre-state 下 exact 一致。
- Invalid config 與 count zero 不消耗 global RNG。

### 14.3 Deterministic NRZ

- All zero／one。
- Alternating first bit 0／1。
- Long run count 10／run 3。
- Transition boundary 0／count。
- Pulse boundary 與 zero-count rejection。
- 所有 deterministic NRZ dtype exact `np.dtype(int)`。

### 14.4 PRBS

- V1 all-ones frozen prefix 與 custom-state prefix。
- Resolved convention 與 all-ones state。
- Exact `np.int8`。
- 只委派 frozen PRBS core，不重寫 recurrence。

### 14.5 User values

- NRZ int／bool normalization；float rejection。
- `nrz_user_bits` dtype exact `np.dtype(int)`。
- PAM4 canonical levels；NaN、Inf 與 off-level rejection。
- Exact length、empty tuple／count zero。
- Input 未修改；output 為新 array。
- Direct list／ndarray constructor input 拒絕。
- Serialized list 由 `from_dict()` copy 成 tuple。

### 14.6 Serialization

- 11 pattern types 與 resolved config round-trip。
- Canonical keys／order 與 all-keys-present。
- Missing／extra keys 與 unknown version 拒絕。
- Mutating serialized dictionary／list 不影響 config。

### 14.7 Output／compatibility

- Exact ndarray、shape、C-contiguous 與 value set。
- Dtype assertion 依 §9.2 exact matrix，不使用「所有 NRZ 都是 `np.dtype(int)`」的簡化規則。
- Existing helper output 不得被 cast。
- New module 無 PyQt、PySide、pyqtgraph、main、GUI、pipeline 或 controller import。
- `pcie_eq.patterns` public API 不變。
- Window、controllers、random wrapper 與 GUI call sequence 不變。
- Existing 192 tests 全部通過，總數增加。
- `python -c "import main"` 通過。

---

## 15. Implementation Boundary

後續 code Issue 預期只允許：

```text
pcie_eq/pattern_config.py
tests/test_pattern_config.py
tests/test_pattern_config_module_boundary.py
```

未經 Reviewer 核准不得修改：

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

第一個 code PR 只建立 pure contract implementation，不整合 GUI 或 simulation pipeline。

---

## 16. Non-scope

- 統一 legacy random NRZ dtype。
- GUI pattern selector／parameter widgets 與 window state migration。
- Random button behavior 變更。
- NRZ bit-to-symbol 自動轉換。
- PAM4 bit mapping、Gray coding 或 precoding。
- PRBSQ／QPRBS／FEC／training sequence。
- File import、CSV tolerance、measurement fitting。
- Channel、Cursor、Sampling、RXEQ、Scenario、Sweep 與 Auto EQ。
- Streaming／chunk continuation 與 final LFSR state。

---

## 17. Stop Conditions／Change Control

實作者遇到以下情況必須停止：

- Existing generator 行為與本文件 evidence 不一致。
- 需要修改 GUI、pipeline 或 existing pattern function 才能完成 pure contract。
- 無法保留 global RNG consumption order。
- 需要 cast 才能符合或統一 dtype。
- 新 pattern 缺少 authoritative definition 或 independent oracle。
- PRBS 需要不同 convention、polarity 或 phase。
- Serialized V1 無法在不猜測下解析。

Taxonomy、default、dtype、seed policy、serialization key 或 allowed claim 的任何修改，均需獨立 docs PR 與 Merge Gate。

---

## 18. Acceptance Gate for Future Code PR

- 完整符合 `pcie_eq-pattern-config-v1` revision 1.1。
- 11 種 pattern 可透過單一 pure API 解析。
- Constructor validation、defaults、irrelevant-field rejection 與 validation matrix 通過。
- Random／PRBS output 與既有 core bit-exact一致。
- `nrz_random` empty／non-empty dtype 依 §9.2 保存，不做 cast。
- Global RNG、shape、raw values 與 GUI baseline 不變。
- Serialization exact round-trip 且 unknown version 拒絕。
- Module boundary 通過。
- Existing 192 tests 全部通過，總數增加。
- GitHub Actions、`import main` 與 `git diff --check` 通過。
- 無 GUI、pipeline、TXEQ、Channel、RXEQ、Preset 或 simulation math 變更。
