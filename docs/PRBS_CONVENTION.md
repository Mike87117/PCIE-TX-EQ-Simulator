# PRBS Convention

> 文件狀態：Frozen implementation contract  
> Convention ID：`pcie_eq-prbs-fibonacci-lsb-v1`  
> 適用範圍：Implementation 23／Issue #54  
> 最後核對日期：2026-08-05

---

## 1. 文件目的

本文件固定 `PCIE-TX-EQ-Simulator` deterministic PRBS generator 的數學定義、state representation、輸出順序、validation contract 與 golden vectors。

PRBS polynomial 本身不足以唯一決定 bit sequence。不同設備或軟體可能採用不同的：

- Fibonacci／Galois topology。
- shift direction。
- MSB／LSB output。
- feedback timing。
- initial-state bit ordering。
- output inversion。
- first-bit phase。

因此本專案不以「PRBS7」等名稱推測完整序列，而是另外固定具版本的 project convention。

---

## 2. 模型等級與宣稱範圍

模型等級：

```text
Reference-model-derived general test pattern
```

Polynomial 與 nominal period 由公開官方／廠商文件交叉確認；輸出 phase、state ordering 與 polarity 則由本文件定義。

### 2.1 允許宣稱

- 支援 PRBS7／9／15／23／31 的標準 polynomial。
- 使用已文件化的 `pcie_eq-prbs-fibonacci-lsb-v1` convention。
- 對固定 order、count 與 initial state 可 bit-exact 重現。
- PRBS7／9／15 可透過完整 period tests 驗證 maximal-period behavior。

### 2.2 禁止宣稱

- PCIe compliance pattern generator。
- PCI-SIG Reference Pattern。
- 與指定 AMD／Intel／Tektronix／BERT 裝置的初始 phase bit-exact。
- PCIe Gen6 PAM4 PRBSQ／QPRBS。
- PCIe FEC、CRC、replay 或 compliance result。

---

## 3. 權威資料來源

### 3.1 AMD Versal GTY／GTYP Transceivers Architecture Manual

```text
Document ID: AM002
Revision: 1.3 English
Release date: 2023-10-26
Access: Public
URL: https://docs.amd.com/r/en-US/am002-versal-gty-transceivers/TX-Pattern-Generator
```

用途：確認 PRBS7／9／15／23／31 polynomial 與 `2^n - 1` nominal sequence length。

### 3.2 AMD Versal GTM Transceivers Architecture Manual

```text
Document ID: AM017
Revision: 1.1 English
Release date: 2024-09-05
Access: Public
URL: https://docs.amd.com/r/en-US/am017-versal-gtm-transceivers/TX-Pattern-Generator
```

用途：交叉確認 polynomial，並確認不同設備可能具有不同 inversion convention。

### 3.3 Tektronix PPG4001 PatternPro Datasheet

```text
Access: Public
URL: https://www.tek.com/en/datasheet/ppg4001-patternpro%C2%AE-programmable-pattern-generator-datasheet
```

用途：獨立交叉確認五種 polynomial。

### 3.4 ITU-T Recommendation O.150

```text
Recommendation: O.150 (05/96)
Status: In force
Access: Freely available
URL: https://www.itu.int/rec/T-REC-O.150/en
```

用途：pseudo-random digital test pattern 的標準化背景與測試用途。

### 3.5 Intel 50G Interlaken IP User Guide

```text
Document ID: 683217
Date: 2022-10-31
Access: Public
URL: https://www.intel.com/content/www/us/en/docs/programmable/683217/22-1/prbs-generation-and-validation.html
```

用途：再次交叉確認 PRBS7／9／15／23／31 polynomial。

---

## 4. Polynomial 與 nominal period

| Order | Polynomial | `k` | Nominal period |
|---:|---|---:|---:|
| 7 | `x^7 + x^6 + 1` | 6 | `2^7 - 1 = 127` |
| 9 | `x^9 + x^5 + 1` | 5 | `2^9 - 1 = 511` |
| 15 | `x^15 + x^14 + 1` | 14 | `2^15 - 1 = 32767` |
| 23 | `x^23 + x^18 + 1` | 18 | `2^23 - 1 = 8388607` |
| 31 | `x^31 + x^28 + 1` | 28 | `2^31 - 1 = 2147483647` |

這張表只決定 characteristic polynomial 與 nominal period，不決定 first output bit 或 sequence phase。

---

## 5. Project convention v1

Convention ID：

```text
pcie_eq-prbs-fibonacci-lsb-v1
```

對 polynomial：

```text
x^n + x^k + 1
```

固定以下規則。

### 5.1 LFSR topology

- 使用 `n`-bit Fibonacci LFSR。
- State 使用 Python non-negative integer 表示。
- State bit `0` 是 LSB。
- State bit `n - 1` 是 MSB。

### 5.2 Output timing

每個 iteration 先輸出、再更新：

```text
output_bit = state_bit[0]
```

第一個輸出 bit 直接來自 initial state，不先 advance。

### 5.3 Feedback

```text
feedback = state_bit[0] XOR state_bit[n-k]
```

等價 Python expression：

```python
feedback = (state & 1) ^ ((state >> (n - k)) & 1)
```

### 5.4 State update

使用 right shift，feedback 放入 MSB：

```python
state = (state >> 1) | (feedback << (n - 1))
```

### 5.5 Initial state

- Default initial state：all ones。
- Default value：`(1 << n) - 1`。
- Valid range：`1 .. (1 << n) - 1`。
- State `0` 必須拒絕，避免 all-zero lock-up。
- Custom state 按照相同 LSB／MSB ordering 解讀。

### 5.6 Polarity

- 所有 order 採 non-inverted output。
- 不進行 XOR 1 或其他 output inversion。
- 未來若需要其他 polarity／phase，不得靜默修改 v1；必須建立新的 convention ID。

### 5.7 RNG

PRBS generator 是 deterministic state machine：

- 不讀取 NumPy global RNG。
- 不修改 NumPy global RNG。
- 不接受 random seed 參數。

---

## 6. Public API contract

```python
generate_prbs_bits(
    order: int,
    count: int,
    initial_state: int | None = None,
) -> numpy.ndarray
```

### 6.1 Output

- Type：`numpy.ndarray`。
- Shape：`(count,)`。
- Exact dtype：`numpy.int8`。
- Values：只允許 `0` 與 `1`。
- `count=0`：回傳 `np.array([], dtype=np.int8)`。
- 相同輸入必須 bit-exact 重現。

選擇 signed `int8` 是為了固定跨平台 dtype，並避免未來進行 `2 * bits - 1` 時出現 unsigned underflow。

### 6.2 `order` validation

- `bool`：`TypeError`。
- 非 integer：`TypeError`。
- 不在 `{7, 9, 15, 23, 31}`：`ValueError`。

### 6.3 `count` validation

沿用 `pcie_eq.patterns._validate_count()`：

- `bool`：`TypeError`。
- 非 integer：`TypeError`。
- negative：`ValueError`。
- zero：有效。

### 6.4 `initial_state` validation

- `None`：使用 all-ones state。
- `bool`：`TypeError`。
- 非 integer：`TypeError`。
- `0`：`ValueError`。
- negative：`ValueError`。
- 大於 `(1 << order) - 1`：`ValueError`。

即使 `count=0`，仍必須先驗證 `order` 與 `initial_state`。

---

## 7. Frozen golden vectors

Golden vectors 在 planning 階段使用兩個獨立 reference formulations 交叉比對：

1. Integer-state recurrence。
2. Explicit bit-array recurrence，其中 `bits[0]` 明確代表 LSB。

Production tests 必須直接寫入下列 frozen values，不得在測試執行期間呼叫 production function 或共用 production helper 產生 expected output。

### 7.1 All-ones initial state，前 64 bits

```text
PRBS7
1111111000000100000110000101000111100100010110011101010011111010

PRBS9
1111111110000011110111110001011100110010000010010100111011010001

PRBS15
1111111111111110000000000000010000000000000110000000000001010000

PRBS23
1111111111111111111111100000000000000000011111000000000000011111

PRBS31
1111111111111111111111111111111000000000000000000000000000011100
```

### 7.2 `initial_state=1`，前 32 bits

```text
PRBS7
10000001000001100001010001111001

PRBS9
10000000010000100011000010011100

PRBS15
10000000000000010000000000000110

PRBS23
10000000000000000000000100000000

PRBS31
10000000000000000000000000000001
```

---

## 8. Validation strategy

### 8.1 Golden-prefix validation

五種 order 都必須驗證：

- all-ones 64-bit prefix。
- `initial_state=1` 32-bit prefix。
- exact `np.int8` dtype。
- one-dimensional shape。
- values only `0 / 1`。

### 8.2 Full-period validation

完整測試：

```text
PRBS7  : 127 states
PRBS9  : 511 states
PRBS15 : 32767 states
```

每個完整 period test 必須證明：

- period 後回到相同 initial state／phase。
- period 內沒有提前重複 state。
- 不出現 all-zero state。
- 覆蓋所有 `2^n - 1` nonzero states。

Period test 可以在 test code 中使用獨立、明確的 state transition helper；不得呼叫 production private helper 當作 validation oracle。

### 8.3 PRBS23／PRBS31 validation

不得執行完整 period 測試，避免 CI 產生不合理時間與記憶體成本。

改用：

- frozen golden prefixes。
- custom-state transitions。
- independent recurrence spot checks。
- 長度切片一致性：同 seed 的 `generate(count=a+b)` 前綴必須等於 `generate(count=a)`。
- deterministic repeatability。

注意：目前 API 不回傳 final state，因此不得以第二次 function call 假裝 sequence continuation。

### 8.4 RNG isolation

呼叫前後比較完整 NumPy global RNG state，必須完全相同。

---

## 9. Implementation boundaries

Gemini 的 code PR 只允許修改：

```text
pcie_eq/patterns.py
tests/test_patterns.py
tests/test_patterns_module_boundary.py
```

本文件由 Planner／Reviewer 維護，Gemini 不得在 Implementation 23 code PR 中修改：

```text
docs/PRBS_CONVENTION.md
PCIE-TX-EQ-Simulator_Product_Roadmap.md
docs/ROADMAP_FEASIBILITY_AUDIT.md
```

除非 Reviewer 先更新文件並明確修改 Issue contract，production code 與 tests 必須以本文件為準。

不得修改：

- GUI files。
- `pipeline.py`／`models.py`。
- TXEQ／Channel／RXEQ／Metrics。
- Preset／random sequence／fingerprints。

---

## 10. Change-control policy

下列任何一項變更都視為 breaking contract：

- polynomial。
- Fibonacci／Galois topology。
- shift direction。
- output bit position。
- feedback tap interpretation。
- update-before-output／output-before-update。
- initial-state ordering。
- output inversion。
- exact dtype。
- frozen golden vectors。

若需要變更：

1. 先建立新的 Evidence Gate Issue。
2. 由 Planner／Reviewer 更新本文件或建立新 convention 文件。
3. 使用新的 convention ID。
4. 不得靜默改寫 `pcie_eq-prbs-fibonacci-lsb-v1`。
