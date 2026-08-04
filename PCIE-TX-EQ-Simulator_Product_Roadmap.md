# PCIE-TX-EQ-Simulator Product Roadmap

> 文件用途：作為產品、開發、測試與 Merge Gate 的共同開發藍圖。  
> 文件狀態：Active Roadmap  
> 最後核對日期：2026-08-04  
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
- 理想數學模型、示波器類波形與實際量測結果為何可能不同。

本產品**不是 PCI-SIG Compliance Tool**，不得宣稱模擬結果等同正式示波器、BERT、SigTest、Seasim 或 PCI-SIG 認證結果。

---

## 2. Roadmap 的事實來源與更新規則

Roadmap 內容必須以已合併至 `main` 的程式碼為準。

狀態定義：

- **Completed**：PR 已合併至 `main`，CI 與 Merge Gate 通過。
- **In Review**：已有 PR，但尚未合併，不得列為完成。
- **Planned**：只有規劃或 Issue，尚未開始實作。
- **Blocked**：依賴尚未完成，或 Merge Gate 發現阻擋問題。

每次完成下列事件時，應同步更新本文件：

- Phase 完成。
- Roadmap 順序或依賴關係改變。
- 新增或取消主要產品能力。
- 實際架構與文件描述產生明顯落差。
- Regression baseline、CI policy 或 Merge Gate 發生重大改變。

Draft PR、未合併 branch 與本機結果只能列為進行中證據，不能當成正式產品基準。

---

## 3. 目前已驗證的產品基準

### 3.1 `main` 基準

截至 2026-08-04，本文件更新 branch 建立時的正式基準為：

```text
main commit: ef5ebda83fecd0fcd830555ab76cb07945788076
regression baseline: 167 tests
CI: GitHub Actions / windows-latest / Python 3.11
```

### 3.2 已完成工作

#### Phase 0：Baseline Freeze — Completed

已完成：

- NRZ／PAM4 baseline tests。
- TX EQ、Channel、RX EQ、Metrics 與 GUI interaction regression tests。
- Preset、Reset、random sequence、plotting contract 與重要數值行為鎖定。
- NRZ Preset 0～10 resolution contract 鎖定。

#### Phase 1：Core Refactor — Completed

已完成：

- `main.py` 已縮減為 launcher 與相容匯出層。
- TX EQ、Channel、RX EQ、Metrics、Models 與 Pipeline 已拆分。
- `run_simulation(config)` 統一 pipeline 已建立。
- NRZ／PAM4 controller、tab builder、Window state、layout 與 helpers 已模組化。
- 核心模組具備 module-boundary tests。
- GitHub Actions regression CI 已建立。

### 3.3 目前進行中

- Roadmap Issue：#48 `Phase 2: Channel Foundation`。
- Implementation Issue：#49 `Add GUI-independent pattern generator core`。
- Draft PR：#50。
- PR #50 在合併前仍屬 **In Review**；只有通過 dtype、RNG、fingerprint 與 GUI compatibility Merge Gate 後才能列為 Completed。

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

`pcie_eq.patterns` 只有在 PR #50 通過並合併後，才正式成為上述架構的一部分。

### 3.5 目前已有能力

- PCIe Gen1～Gen5 NRZ TX EQ 視覺化。
- NRZ Preset 0～10。
- Preshoot、De-emphasis 與 `C-1 / C0 / C+1` 顯示。
- 簡化的一階 Low-pass Channel。
- NRZ 簡化 CTLE。
- NRZ 3-tap 手動 DFE。
- Channel、CTLE 與 DFE Sample Margin 檢視。
- PCIe Gen6 PAM4 4-tap TX FIR。
- PAM4 Q0～Q9。
- PAM4 Raw Eye 與 Common `t_center` Eye。
- NRZ／PAM4 波形與近似 Eye metrics。
- PyQt5 GUI 與 PyQtGraph 即時顯示。
- GUI-independent simulation pipeline。
- Windows GitHub Actions regression gate。

### 3.6 目前主要限制

- Channel 仍只有一階 Low-pass Alpha，尚未形成可替換的 Channel interface。
- 尚無 impulse response convolution、synthetic channel 或 Touchstone import。
- Pattern 尚未具有完整的 PRBS、user-defined sequence 與 versioned configuration contract。
- NRZ sampling phase 仍缺少完整可調 API、phase sweep 與 CDR。
- CTLE 與 DFE 仍是簡化教學模型。
- PAM4 尚未加入完整 RXEQ、threshold optimization 與 decision chain。
- 尚無 noise、jitter、crosstalk 與統計型 impairment model。
- 尚無可信的 Density Eye、Eye Width、Bathtub、BER／SER estimate。
- 尚無 versioned scenario schema、experiment run、batch result 與完整 export contract。
- 尚無 Auto EQ、heatmap 或 joint optimization。
- 尚無示波器 waveform import 與 measured-vs-simulated workflow。

---

## 4. 開發先後順序原則

### 4.1 依賴優先

後續功能必須依照資料與演算法依賴順序實作，不以 UI 顯示順序決定開發順序。

正確主幹為：

```text
Pattern Core
  → Pattern Configuration
  → Channel Interface
  → Impulse Convolution
  → Pulse / Cursor Analysis
  → Channel Views / Touchstone
  → Sampling / RXEQ
  → Signal Impairments
  → Statistical Metrics
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

### 4.3 Channel 先於 Cursor 分析

Single-bit pulse pattern 只是分析輸入。要得到有意義的 pre／main／post cursor，必須先有明確的 Channel representation、sampling interval 與 convolution contract。

因此原 Roadmap 中「Pulse／Cursor Analysis 早於 Channel Model」的順序已修正。

### 4.4 Metrics 先穩定，再做最佳化

Auto EQ 需要穩定且可重現的 objective。不得在 Eye Width、sampling phase、threshold、noise／jitter 與結果格式仍不穩定時提前建立「最佳 preset」或「最佳設定」功能。

Preset Resolver 與 Preset Sweep 因此歸入 Auto Equalization 前置工作，不屬於目前 Phase 2 的立即工作。

### 4.5 最小可重現資料契約先於批次工作

Sweep、Auto EQ 與 Measurement comparison 必須能保存：

- Pattern 與 seed。
- TX EQ。
- Channel。
- RX EQ。
- Sampling／threshold。
- Metric objective。
- Result metadata。

因此完整 Auto EQ 前必須先建立最小 versioned Scenario／Experiment contract。

### 4.6 相容性優先於表面相同

回歸驗證不得只比較經過轉型或正規化後的結果。需要視契約同時鎖定：

- value。
- shape。
- dtype。
- array ordering。
- RNG state consumption。
- import surface。
- call sequence。
- GUI state。

---

## 5. 修訂後的整體 Roadmap

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

本次修訂將原本過早的 Auto Equalization 往後移，並將「可重現 Scenario／Experiment」從單純 UX 功能提升為 Auto EQ 的正式前置依賴。

---

# 6. Phase 2：Channel Foundation

## 6.1 目的

建立真正可替換、可驗證、可重現的 Pattern 與 Channel 基礎，讓後續 ISI、cursor、sampling 與 RXEQ 不再只依賴單一 Low-pass Alpha。

## 6.2 依賴順序

### Step 2.1：Pattern Core

#### Implementation 22 — In Review

建立：

- NRZ bits／symbols conversion。
- Seeded 與 global RNG random generation。
- All 0／All 1。
- Alternating。
- Long run。
- Single transition。
- Single-bit pulse。

Merge Gate 必須鎖定：

- legacy global RNG consumption order。
- initial NRZ／PAM4 sequence。
- value、shape 與 dtype。
- raw-byte fingerprint。
- GUI Generate New Waveform 行為。

### Step 2.2：PRBS Core

完成 Pattern Core 後，再加入：

- PRBS7。
- PRBS9。
- PRBS15。
- PRBS23。
- PRBS31。
- polynomial、seed、initial state 與 output convention 文件化。
- hardcoded golden vectors 與 period／prefix tests。

不得先加入 GUI selector。

### Step 2.3：Pattern Configuration Contract

建立 GUI-independent 的 pattern request／configuration contract，至少描述：

- pattern type。
- symbol count。
- seed。
- PRBS order／initial state。
- deterministic pattern parameters。
- user-defined bits／symbols。

同時加入 user-defined sequence validation，但不在此步驟處理完整 Scenario save/load UI。

### Step 2.4：Channel Interface 與 Config

先建立統一 Channel contract，再加入更多 Channel model：

```text
none
legacy_lowpass
impulse_response
```

要求：

- `none` 必須是 TX waveform identity。
- `legacy_lowpass` 必須保持目前 baseline。
- core 不依賴 GUI。
- 所有 mode 有明確 input／output shape、dtype 與 validation。

### Step 2.5：Impulse Response Convolution

建立：

- impulse validation。
- normalization policy。
- convolution length／alignment contract。
- time-zero／main cursor reference。
- truncation／padding policy。
- invalid data error model。

先完成單元測試，再接入 pipeline。

### Step 2.6：Synthetic 與 User-defined Impulse Response

依序加入：

1. Synthetic impulse response。
2. User-provided numeric impulse response。
3. 可重現的 built-in teaching channels。

此時仍不處理 Touchstone parser。

### Step 2.7：Pulse／Cursor Analysis

Channel contract 穩定後，才建立：

```text
Pre3  Pre2  Pre1  Main  Post1  Post2  Post3
```

提供：

- main cursor amplitude。
- pre-cursor ISI。
- post-cursor ISI。
- residual ISI。
- cursor sampling phase。
- TX、Channel、CTLE 後的 cursor comparison contract。

Cursor extraction 必須有 synthetic golden impulse cases，不能只依靠視覺判斷。

### Step 2.8：Pattern／Channel GUI Integration

等 PatternConfig、ChannelConfig、convolution 與 cursor result 穩定後，再一次整合：

- Pattern selector。
- Pattern parameters。
- Channel mode selector。
- Impulse input。
- Cursor table／overlay。

避免在 core contract 尚未穩定時反覆重新設計 GUI。

### Step 2.9：Channel Views

依既有 core result 顯示：

- frequency response。
- insertion loss。
- impulse response。
- step response。
- pulse response。
- time-domain waveform。

所有 plot 必須使用 result data，不在 GUI 內重新計算模型。

### Step 2.10：Touchstone

依序實作：

1. `.s2p` single-ended teaching path。
2. 明確的 frequency unit、port、reference impedance 與 interpolation contract。
3. `.s4p`／mixed-mode／`SDD21` 評估。

Differential `.s4p` 不得與第一版 `.s2p` 同一個大型 PR 一次完成。

## 6.3 Phase 2 Exit Gate

Phase 2 完成必須同時符合：

- Pattern 可以由固定設定 bit-exact 重現。
- Channel 可透過統一介面切換。
- `none` 與 legacy Low-pass regression 通過。
- impulse convolution 有 hardcoded golden tests。
- pulse response 能正確標示 main、pre、post cursor。
- Pattern／Channel core 可在無 PyQt 環境執行。
- GUI 不直接實作 pattern 或 channel 數學。
- Touchstone 錯誤輸入有清楚且可測試的錯誤。
- 所有 PR 通過 GitHub Actions 與 Merge Gate。

## 6.4 Phase 2 非範圍

- CDR。
- 完整 NRZ／PAM4 RXEQ redesign。
- Noise／jitter statistical model。
- Density Eye／Bathtub／BER。
- Preset Sweep／Auto EQ／ranking。
- Measurement waveform import。
- Packaging、EXE、Installer。

---

# 7. Phase 3：NRZ Sampling & RXEQ

## 7.1 開發順序

1. Sampling API、manual phase 與 sampling overlay。
2. Phase sweep 與 objective contract。
3. CTLE frequency-domain parameter model與 legacy compatibility。
4. RX FFE manual mode。
5. DFE tap expansion、contribution 與 decision history。
6. Teaching CDR：fixed、auto center、early／late、tracking。
7. NRZ deterministic metrics consolidation。

Eye Width、Bathtub 與 BER 不在 sampling 尚未穩定時提前實作。

## 7.2 Exit Gate

- 使用者可以比較 Channel、CTLE、FFE、DFE 各階段。
- sampling phase 改變會同步更新 waveform、decision 與 metrics。
- phase sweep 有 deterministic regression cases。
- DFE taps 對 post-cursor 的影響可由 cursor result 驗證。
- CDR 清楚標示為 teaching model。

---

# 8. Phase 4：PAM4 RXEQ

## 8.1 開發順序

1. PAM4 pattern／coding contract。
2. AGC／VGA。
3. PAM4 CTLE。
4. RX FFE。
5. common sampling／CDR phase。
6. three slicer thresholds。
7. PAM4 DFE。
8. threshold optimization。
9. deterministic SER／decision metrics。

PAM4 可以共用 Phase 3 的資料流、sampling 與 result architecture，但不得強迫共用不合理的 NRZ decision algorithm。

## 8.2 Exit Gate

- TX、Channel、RX、decision views 分離。
- 三個 thresholds 可手動與自動調整。
- Upper／Middle／Lower eye 使用共同 phase。
- reference symbol 輔助模式必須明確標示，不得偽裝為正式 receiver decision。
- 固定 seed 的 SER regression 通過。

---

# 9. Phase 5：Signal Impairments & Statistical Metrics

## 9.1 目的

在 sampling、decision 與 RXEQ chain 穩定後，再建立具有統計意義的訊號劣化與 metrics。

## 9.2 開發順序

1. AWGN／vertical noise。
2. deterministic jitter。
3. random jitter teaching model。
4. frequency／phase offset。
5. simplified crosstalk／interference。
6. density accumulation contract。
7. Eye Width。
8. horizontal／vertical bathtub。
9. BER／SER estimate 與信賴限制說明。

## 9.3 原則

- noise 與 jitter 必須具備固定 seed。
- error estimate 必須記錄 sample count 與限制。
- 不得將有限樣本 estimate 描述為 compliance BER。
- metrics 必須清楚區分 deterministic、measured 與 estimated。

---

# 10. Phase 6：Reproducibility & Experiment Infrastructure

## 10.1 必須建立

- versioned Scenario schema。
- Pattern、TXEQ、Channel、RXEQ、sampling、threshold、impairment 設定。
- random seed 與 RNG policy。
- Experiment Run identity。
- resolved configuration。
- result／artifact references。
- batch result model。
- CSV／JSON／Markdown export core。
- schema migration policy。

## 10.2 啟動理由

Auto EQ 與 measurement comparison 都會產生大量可比較結果。若沒有 versioned input 與 result metadata，無法重現或判斷比較是否有效。

完整 GUI 的 New／Save／Load 可在 Phase 9 完成，但 core schema 必須在 Auto EQ 前完成。

---

# 11. Phase 7：Sweep & Auto Equalization

## 11.1 開發順序

1. GUI-independent Preset Resolver。
2. Sweep request／result model。
3. NRZ TX Preset sweep。
4. PAM4 Q Preset sweep。
5. TX tap sweep。
6. sampling／CTLE／FFE／DFE／threshold sweep。
7. heatmap data model與 GUI。
8. grid search。
9. coordinate descent。
10. decision-directed adaptation research。
11. joint TX／RX optimization。

## 11.2 啟動條件

- objective metrics 已穩定。
- Scenario／Experiment schema 已完成。
- sweep 可在 GUI 外執行。
- 相同設定與 seed 得到相同結果。
- 長時間工作具備 progress／cancel contract。

## 11.3 用語限制

在模型仍為教學／近似模型時，結果只能描述為：

- highest simulated metric。
- best result within this configured sweep。
- teaching-model comparison。

不得直接描述為真實硬體最佳 preset、PCI-SIG 建議或 compliance 結論。

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
8. tap extraction。
9. fit residual、fit quality 與 limitation reporting。

Measurement import 不得直接耦合 GUI；parser、alignment 與 analysis 必須可以獨立測試。

---

# 13. Phase 9：Product Usability & Release

完成：

- Scenario New／Save／Save As／Load UX。
- A／B comparison。
- 未儲存變更提示。
- CSV／JSON／Markdown reports。
- User Guide。
- Developer／Architecture Guide。
- Model Limitations。
- Validation Cases。
- Release Notes。
- Glossary。
- Basic／Advanced mode。
- 統一錯誤訊息與輸入提示。
- 大型工作 progress／cancel UX。

Packaging、EXE、Installer 與防毒誤判仍需另立產品決策，不自動納入本 Phase。

---

# 14. Phase 10：Advanced Research

候選功能：

- Retimer／multi-segment channel。
- package、connector、via model。
- crosstalk matrix。
- Gen6 FEC teaching model。
- pre-FEC／post-FEC error view。
- RLM／SNDR approximation。
- advanced CDR。
- PCIe Gen7 profile。
- Batch CLI。
- public Python API stabilization。
- plugin architecture。
- hardware measurement automation interface。

啟動條件：

- Core architecture 穩定。
- NRZ 與 PAM4 RXEQ 完成。
- Scenario format 穩定。
- 統計 metrics 有明確限制與 regression。
- Auto EQ 可重現。
- 至少有一個穩定公開版本。

---

## 15. 所有 PR 的 Merge Gate

每個 PR 必須提供：

- Related Roadmap Issue。
- Scope／non-scope。
- unit tests。
- module-boundary tests。
- regression count。
- GitHub Actions run。
- `python -c "import main"`。
- 涉及 GUI 時的 startup／interaction smoke evidence。
- `git diff --check`。
- value／shape／dtype compatibility 說明。
- RNG state／seed compatibility 說明。
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

### 目前 Merge Gate

PR #50 必須先修正並重新驗證 GUI `symbols` dtype contract；在問題解決前，不得合併，也不得將 Implementation 22 標示為 Completed。

### PR #50 通過後

下一個 Implementation 應為：

```text
Implementation 23: Add deterministic PRBS generator core
```

工作只包含 GUI-independent PRBS7／9／15／23／31、明確 polynomial／seed convention、hardcoded golden vectors 與 boundary tests。

不得在 Implementation 23 同時加入：

- Pattern selector GUI。
- Channel model。
- Cursor analysis。
- Scenario storage。
- Auto EQ。

完成 PRBS core 後，再建立 Pattern Configuration Contract，之後才進入 Channel interface 與 impulse convolution。
