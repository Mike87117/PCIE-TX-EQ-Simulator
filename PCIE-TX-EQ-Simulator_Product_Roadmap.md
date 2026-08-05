# PCIE-TX-EQ-Simulator Product Roadmap

> 文件用途：作為產品、開發、測試與 Merge Gate 的共同開發藍圖。  
> 文件狀態：Active Roadmap  
> 最後核對日期：2026-08-05  
> 適用 Repository：`Mike87117/PCIE-TX-EQ-Simulator`

---

## 1. 產品定位

PCIE-TX-EQ-Simulator 的定位是：

> **用於學習、視覺化與比較 PCIe TX Equalization、Channel Effect 與 RX Equalization 行為的教學型模擬工具。**

產品應協助使用者理解：

- TX FIR tap、Preshoot、De-emphasis 與波形之間的關係。
- Channel loss、ISI、reflection、noise 與 jitter 對訊號品質的影響。
- CTLE、FFE、DFE、CDR 與 slicer 如何改善接收品質。
- PCIe Gen1～Gen5 NRZ 與 Gen6 PAM4 equalization 的差異。
- TX、Channel、RX、sampling 與 threshold 如何共同影響 Eye、Margin 與 error metrics。
- 理想模型、示波器類波形與實際量測結果為何可能不同。

本產品**不是 PCI-SIG Compliance Tool**，不得宣稱模擬結果等同正式示波器、BERT、SigTest、Seasim 或 PCI-SIG 認證結果。

---

## 2. 事實來源與狀態規則

Roadmap 內容必須以已合併至 `main` 的程式碼為準。

狀態定義：

- **Completed**：PR 已合併至 `main`，CI 與 Merge Gate 通過。
- **In Review**：已有 PR，但尚未合併。
- **Planned**：只有 Roadmap 或 Issue，尚未開始實作。
- **Blocked**：依賴尚未完成，或 Merge Gate 發現阻擋問題。

下列事件發生後必須同步本文件：

- Phase 或 Implementation 完成。
- Roadmap 順序或依賴關係改變。
- 新增或取消主要產品能力。
- 實際架構與文件描述產生明顯落差。
- Regression baseline、CI policy 或 Merge Gate 發生重大改變。

Draft PR、未合併 branch 與本機結果只能列為進行中證據，不能當成正式產品基準。

---

## 3. 目前已驗證的產品基準

### 3.1 `main` 基準

截至 2026-08-05：

```text
main commit: 3812ef850523d4dabbcf33ad1e056bc140c2b45f
regression baseline: 182 tests
CI: GitHub Actions / Windows / Python 3.11
```

### 3.2 已完成工作

#### Phase 0：Baseline Freeze — Completed

- NRZ／PAM4 baseline tests。
- TX EQ、Channel、RX EQ、Metrics 與 GUI interaction regression tests。
- Preset、Reset、random sequence、plotting contract 與重要數值行為鎖定。
- NRZ Preset 0～10 resolution contract 鎖定。

#### Phase 1：Core Refactor — Completed

- `main.py` 已縮減為 launcher 與相容匯出層。
- TX EQ、Channel、RX EQ、Metrics、Models 與 Pipeline 已拆分。
- `run_simulation(config)` 統一 pipeline 已建立。
- NRZ／PAM4 controller、tab builder、Window state、layout 與 helpers 已模組化。
- 核心模組具備 module-boundary tests。
- GitHub Actions regression CI 已建立。

#### Phase 2 / Step 2.1：Pattern Core — Completed

Implementation 22 已透過 Issue #49 與 PR #50 完成：

- 新增 GUI-independent `pcie_eq.patterns`。
- NRZ bits／symbols conversion。
- Seeded 與 global RNG random generation。
- All 0／All 1、Alternating、Long run、Single transition、Single-bit pulse。
- `pam4_symbols_from_random()` 保持相容 wrapper。
- GUI module-level random sequence 與 Generate New Waveform 保持既有 RNG、value、shape 與 dtype contract。
- Raw-byte fingerprint、global RNG consumption 與 module-boundary tests 已鎖定。

### 3.3 目前進行中

- Roadmap Issue：#48 `Phase 2: Channel Foundation`。
- 下一個 Implementation：**Implementation 23 — Add deterministic PRBS generator core**。
- Implementation 23 尚未建立 PR，狀態為 **Planned**。

### 3.4 目前實際架構

```text
PCIE-TX-EQ-Simulator/
├─ main.py
├─ PCIE-TX-EQ-Simulator_Product_Roadmap.md
├─ pcie_eq/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ tx_eq.py
│  ├─ channel.py
│  ├─ rx_eq.py
│  ├─ metrics.py
│  ├─ pipeline.py
│  ├─ patterns.py
│  └─ gui/
│     ├─ window.py
│     ├─ window_state.py
│     ├─ window_layout.py
│     ├─ window_helpers.py
│     ├─ nrz_controller.py
│     ├─ pam4_controller.py
│     ├─ nrz_tab.py
│     ├─ pam4_tab.py
│     └─ random_data.py
├─ tests/
├─ requirements.txt
└─ requirements-dev.txt
```

### 3.5 目前已有能力

- PCIe Gen1～Gen5 NRZ TX EQ 視覺化。
- NRZ Preset 0～10。
- Preshoot、De-emphasis 與 `C-1 / C0 / C+1` 顯示。
- 簡化的一階 Low-pass Channel。
- NRZ 簡化 CTLE 與 3-tap 手動 DFE。
- Channel、CTLE 與 DFE Sample Margin 檢視。
- PCIe Gen6 PAM4 4-tap TX FIR 與 Q0～Q9。
- PAM4 Raw Eye 與 Common `t_center` Eye。
- NRZ／PAM4 波形與近似 Eye metrics。
- GUI-independent simulation pipeline。
- GUI-independent deterministic／random Pattern Core。
- Windows GitHub Actions regression gate。

### 3.6 目前主要限制

- 尚無 PRBS7／9／15／23／31。
- 尚無 Pattern configuration contract 與 user-defined sequence validation。
- Channel 仍只有一階 Low-pass Alpha，尚未形成可替換的 Channel interface。
- 尚無 impulse response convolution、synthetic channel 或 Touchstone import。
- NRZ sampling phase 仍缺少完整 API、phase sweep 與 CDR。
- CTLE 與 DFE 仍是簡化教學模型。
- PAM4 尚未加入完整 RXEQ、threshold optimization 與 decision chain。
- 尚無 noise、jitter、crosstalk 與統計型 impairment model。
- 尚無可信的 Density Eye、Eye Width、Bathtub、BER／SER estimate。
- 尚無 versioned scenario schema、experiment run、batch result 與完整 export contract。
- 尚無 Auto EQ、heatmap、joint optimization 或 measurement import。

---

## 4. 開發先後順序原則

### 4.1 依賴優先

後續功能必須依資料與演算法依賴順序實作，不以 UI 顯示順序決定開發順序。

```text
Pattern Core
  → PRBS Core
  → Pattern Configuration Contract
  → Channel Interface / ChannelConfig
  → Impulse Response Convolution
  → Synthetic / User-defined Impulse
  → Pulse / Cursor Analysis
  → Pattern / Channel GUI Integration
  → Channel Views
  → Touchstone
  → NRZ Sampling / RXEQ
  → PAM4 RXEQ
  → Signal Impairments / Statistical Metrics
  → Reproducible Scenario / Experiment
  → Sweep / Auto Equalization
  → Measurement Integration
  → Product UX / Release
```

### 4.2 Core 先於 GUI

每一項新能力原則上依序完成：

```text
Pure Core API
  → Validation Contract
  → Unit Tests
  → Module Boundary Tests
  → Existing Behavior Compatibility
  → GUI Integration
  → Documentation
```

不得先在 controller 中堆疊功能，再回頭尋找 core boundary。

### 4.3 Channel 先於 Cursor

Single-bit pulse 只是分析輸入。要得到有意義的 pre／main／post cursor，必須先有明確的 Channel representation、sampling interval 與 convolution contract。

### 4.4 Metrics 先穩定，再做最佳化

Auto EQ 需要穩定、可比較、可重現的 objective。Preset Resolver、Preset Sweep 與 Auto EQ 不屬於 Phase 2 的立即工作。

### 4.5 Scenario／Experiment 先於批次與最佳化

Sweep、Auto EQ 與 measurement comparison 必須保存 Pattern、seed、TXEQ、Channel、RXEQ、sampling、threshold、objective 與 result metadata。

### 4.6 相容性優先於表面相同

回歸驗證需要視契約同時鎖定：

- value、shape、dtype、array ordering。
- raw-byte fingerprint。
- RNG state／consumption order。
- import surface 與 call sequence。
- GUI state 與 interaction behavior。

禁止以轉型、rounding 或重新計算掩蓋 baseline 差異。

---

## 5. 整體 Roadmap

| Phase | 里程碑 | 狀態 | 啟動依賴 | 主要成果 |
|---|---|---|---|---|
| Phase 0 | Baseline Freeze | Completed | 無 | regression vectors、GUI baseline、behavior freeze |
| Phase 1 | Core Refactor | Completed | Phase 0 | core modules、pipeline、GUI split、CI |
| Phase 2 | Channel Foundation | Active | Phase 1 | pattern、channel interface、impulse、cursor、channel views |
| Phase 3 | NRZ Sampling & RXEQ | Planned | Phase 2 | sampling、phase sweep、CTLE、FFE、DFE、teaching CDR |
| Phase 4 | PAM4 RXEQ | Planned | Phase 2；共用 Phase 3 架構 | AGC、CTLE、FFE、DFE、3 thresholds、decision chain |
| Phase 5 | Signal Impairments & Statistical Metrics | Planned | Phase 3、4 基礎穩定 | noise、jitter、density eye、eye width、bathtub、BER／SER estimate |
| Phase 6 | Reproducibility & Experiment Infrastructure | Planned | Config contracts 穩定 | versioned scenario、experiment run、batch result、export core |
| Phase 7 | Sweep & Auto Equalization | Planned | Phase 5、6 | preset／tap sweep、heatmap、optimization、history |
| Phase 8 | Measurement Integration | Planned | Phase 2、5、6 | waveform import、alignment、comparison、tap extraction |
| Phase 9 | Product Usability & Release | Planned | 核心工作流程穩定 | scenario UX、reports、guides、error UX、release discipline |
| Phase 10 | Advanced Research | Planned | 至少一個穩定公開版本 | retimer、FEC、Gen7、plugin、automation |

---

# 6. Phase 2：Channel Foundation

## 6.1 目的

建立可替換、可驗證、可重現的 Pattern 與 Channel 基礎，讓後續 ISI、cursor、sampling 與 RXEQ 不再只依賴單一 Low-pass Alpha。

## 6.2 依賴順序

### Step 2.1：Pattern Core — Completed

Implementation 22 / Issue #49 / PR #50 已完成並合併。

### Step 2.2：PRBS Core — Planned / Next

下一個 Implementation 應加入：

- PRBS7。
- PRBS9。
- PRBS15。
- PRBS23。
- PRBS31。
- polynomial、initial state、shift direction、output bit 與 feedback convention 文件化。
- hardcoded golden prefixes。
- PRBS7／9 完整 period tests。
- PRBS15 的完整 period 或等價 recurrence validation。
- PRBS23／31 的 golden prefix、recurrence 與 state-transition tests。
- zero state、unsupported order、invalid count／state validation。
- 不讀取或修改 NumPy global RNG。

不得在此步驟加入 GUI selector、PatternConfig、Channel、Cursor、Scenario 或 Auto EQ。

### Step 2.3：Pattern Configuration Contract

建立 GUI-independent pattern request／configuration contract，至少描述：

- pattern type。
- symbol count。
- random seed。
- PRBS order／initial state。
- deterministic pattern parameters。
- user-defined bits／symbols 與 validation。

此步驟不處理完整 Scenario save/load UI。

### Step 2.4：Channel Interface 與 ChannelConfig

建立統一 Channel contract：

```text
none
legacy_lowpass
impulse_response
```

要求：

- `none` 為 TX waveform identity。
- `legacy_lowpass` 保持目前 baseline。
- core 不依賴 GUI。
- 所有 mode 有明確 input／output shape、dtype 與 validation。

### Step 2.5：Impulse Response Convolution

建立：

- impulse validation 與 normalization policy。
- convolution length／alignment contract。
- time-zero／main cursor reference。
- truncation／padding policy。
- invalid data error model。

先完成 pure-core tests，再接入 pipeline。

### Step 2.6：Synthetic 與 User-defined Impulse

依序加入：

1. Synthetic impulse response。
2. User-provided numeric impulse response。
3. 可重現 built-in teaching channels。

此步驟不處理 Touchstone parser。

### Step 2.7：Pulse／Cursor Analysis

Channel contract 與 convolution 穩定後，才建立：

```text
Pre3  Pre2  Pre1  Main  Post1  Post2  Post3
```

提供 main cursor、pre／post cursor ISI、residual ISI、sampling phase 與 TX／Channel／CTLE stage comparison。

### Step 2.8：Pattern／Channel GUI Integration

等 PatternConfig、ChannelConfig、convolution 與 cursor result 穩定後，再一次整合：

- Pattern selector 與 parameters。
- Channel mode selector。
- Impulse input。
- Cursor table／overlay。

### Step 2.9：Channel Views

依 core result 顯示：

- frequency response。
- insertion loss。
- impulse／step／pulse response。
- time-domain waveform。

GUI 不得重新計算模型。

### Step 2.10：Touchstone

依序實作：

1. `.s2p` single-ended teaching path。
2. frequency unit、port、reference impedance 與 interpolation contract。
3. `.s4p`／mixed-mode／`SDD21` 評估。

`.s2p` 與 differential `.s4p` 不得塞入同一個大型 PR。

## 6.3 Phase 2 Exit Gate

- Pattern 可由固定設定 bit-exact 重現。
- Channel 可透過統一介面切換。
- `none` 與 legacy Low-pass regression 通過。
- impulse convolution 有 hardcoded golden tests。
- pulse response 可正確標示 main、pre、post cursor。
- Pattern／Channel core 可在無 PyQt 環境執行。
- GUI 不直接實作 pattern 或 channel 數學。
- Touchstone 錯誤輸入具備清楚且可測試的錯誤。
- 所有 PR 通過 GitHub Actions 與 Merge Gate。

## 6.4 Phase 2 非範圍

- CDR 與完整 NRZ／PAM4 RXEQ redesign。
- Noise／jitter statistical model。
- Density Eye／Bathtub／BER。
- Preset Sweep／Auto EQ／ranking。
- Measurement waveform import。
- Packaging、EXE、Installer。

---

# 7. Phase 3：NRZ Sampling & RXEQ

開發順序：

1. Sampling API、manual phase 與 sampling overlay。
2. Phase sweep 與 objective contract。
3. CTLE frequency-domain parameter model與 legacy compatibility。
4. RX FFE manual mode。
5. DFE tap expansion、contribution 與 decision history。
6. Teaching CDR：fixed、auto center、early／late、tracking。
7. NRZ deterministic metrics consolidation。

Eye Width、Bathtub 與 BER 不得在 sampling contract 穩定前提前實作。

---

# 8. Phase 4：PAM4 RXEQ

開發順序：

1. PAM4 pattern／coding contract。
2. AGC／VGA。
3. PAM4 CTLE。
4. RX FFE。
5. common sampling／CDR phase。
6. three slicer thresholds。
7. PAM4 DFE。
8. threshold optimization。
9. deterministic SER／decision metrics。

NRZ／PAM4 可共用資料流與 result architecture，但不得強迫共用不合理的 decision algorithm。

---

# 9. Phase 5：Signal Impairments & Statistical Metrics

開發順序：

1. AWGN／vertical noise。
2. deterministic jitter。
3. random jitter teaching model。
4. frequency／phase offset。
5. simplified crosstalk／interference。
6. density accumulation contract。
7. Eye Width。
8. horizontal／vertical bathtub。
9. BER／SER estimate 與信賴限制說明。

不得將有限樣本 estimate 描述為 compliance BER。

---

# 10. Phase 6：Reproducibility & Experiment Infrastructure

必須建立：

- versioned Scenario schema。
- Pattern、TXEQ、Channel、RXEQ、sampling、threshold、impairment 設定。
- random seed 與 RNG policy。
- Experiment Run identity 與 resolved configuration。
- result／artifact references。
- batch result model。
- CSV／JSON／Markdown export core。
- schema migration policy。

完整 GUI New／Save／Load 可延後，但 core schema 必須先於 Auto EQ。

---

# 11. Phase 7：Sweep & Auto Equalization

開發順序：

1. GUI-independent Preset Resolver。
2. Sweep request／result model。
3. NRZ TX Preset sweep。
4. PAM4 Q Preset sweep。
5. TX tap sweep。
6. sampling／CTLE／FFE／DFE／threshold sweep。
7. heatmap data model與 GUI。
8. grid search／coordinate descent。
9. decision-directed adaptation research。
10. joint TX／RX optimization。

結果只能描述為 configured sweep 內的 simulated comparison，不得宣稱真實硬體最佳 preset 或 PCI-SIG 結論。

---

# 12. Phase 8：Measurement Integration

依序加入：

1. Generic waveform CSV。
2. time／voltage／unit validation。
3. sampling rate／UI／baud contract。
4. edge alignment。
5. Tektronix／Keysight adapters。
6. measured-vs-simulated comparison。
7. pulse／cursor comparison。
8. tap extraction 與 fit quality reporting。

Parser、alignment 與 analysis 必須能獨立測試，不得直接耦合 GUI。

---

# 13. Phase 9：Product Usability & Release

- Scenario New／Save／Save As／Load UX。
- A／B comparison。
- 未儲存變更提示。
- CSV／JSON／Markdown reports。
- User Guide、Architecture Guide、Model Limitations、Validation Cases。
- Release Notes、Glossary、Basic／Advanced mode。
- 統一錯誤訊息與大型工作 progress／cancel UX。

Packaging、EXE、Installer 與防毒誤判需另立產品決策，不自動納入本 Phase。

---

# 14. Phase 10：Advanced Research

候選功能：

- Retimer／multi-segment channel。
- package、connector、via model。
- crosstalk matrix。
- Gen6 FEC teaching model。
- pre-FEC／post-FEC error view。
- RLM／SNDR approximation。
- advanced CDR、PCIe Gen7 profile。
- Batch CLI、public Python API、plugin architecture。
- hardware measurement automation interface。

---

## 15. 所有 PR 的 Merge Gate

每個 PR 必須提供：

- Related Roadmap Issue。
- Scope／non-scope。
- unit tests 與 module-boundary tests。
- regression count 與 GitHub Actions run。
- `python -c "import main"`。
- 涉及 GUI 時的 startup／interaction smoke evidence。
- `git diff --check`。
- value／shape／dtype／raw-byte compatibility 說明。
- RNG state／seed／consumption order 說明。
- public import surface 說明。
- 模擬數學與 GUI 行為是否改變。
- known limitations。

禁止：

- 以轉型、rounding 或重新計算掩蓋 baseline 差異。
- 為了讓測試通過而弱化 expected values、tolerance 或 assertions。
- 在同一 PR 混入不相干重構、UI redesign 或 packaging。
- 未經明確規劃提前實作後續 Phase。

---

## 16. 立即下一步

### Implementation 23：Add deterministic PRBS generator core

下一個工作只包含 GUI-independent PRBS7／9／15／23／31、明確 LFSR convention、hardcoded golden vectors、period／recurrence／validation tests 與 module-boundary tests。

建議公開 API：

```python
generate_prbs_bits(
    order: int,
    count: int,
    initial_state: int | None = None,
) -> numpy.ndarray
```

第一版必須固定：

- supported orders：7、9、15、23、31。
- default initial state：all ones。
- zero state：拒絕。
- output：一維整數 `0 / 1` array。
- `count=0`：空整數 array。
- NumPy global RNG：完全不讀取、不修改。
- polynomial、shift direction、output bit、feedback timing 與 state bit ordering 全部文件化。

不得在 Implementation 23 同時加入：

- Pattern selector GUI。
- PatternConfig／user-defined sequence。
- Channel model／ChannelConfig。
- Cursor analysis。
- Scenario storage。
- Preset Sweep／Auto EQ。

Implementation 23 完成後，依序進入 Pattern Configuration Contract、Channel Interface、Impulse Convolution、Synthetic／User Impulse 與 Cursor Analysis。
