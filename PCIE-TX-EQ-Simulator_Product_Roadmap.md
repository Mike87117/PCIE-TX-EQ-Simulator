# PCIE-TX-EQ-Simulator 後續產品開發計畫

> 文件用途：作為 PCIE-TX-EQ-Simulator 的共同開發藍圖，讓產品、開發、測試與使用者對產品定位、優先順序、交付標準與版本範圍有一致認知。  
> 文件狀態：規劃基準版  
> 適用專案：`Mike87117/PCIE-TX-EQ-Simulator`

---

## 1. 產品定位

PCIE-TX-EQ-Simulator 的定位是：

> **用於學習、視覺化與比較 PCIe TX Equalization、Channel Effect 與 RX Equalization 行為的教學型模擬工具。**

產品應協助使用者理解：

- TX FIR tap、Preshoot、De-emphasis 與實際波形之間的關係。
- Channel loss、ISI、reflection、noise 與 jitter 對訊號品質的影響。
- CTLE、FFE、DFE、CDR 與 slicer 如何改善接收品質。
- PCIe Gen1～Gen5 NRZ 與 Gen6 PAM4 的 equalization 差異。
- TX、Channel 與 RX 設定如何共同影響 Eye、Margin、BER 與最佳取樣點。
- 理想數學模型、示波器類波形與實際量測結果為何可能不同。

本產品**不是 PCI-SIG Compliance Tool**，不得宣稱模擬結果等同正式示波器、BERT、SigTest、Seasim 或 PCI-SIG 認證結果。

---

## 2. 目前產品基準

目前已具備的主要能力：

- PCIe Gen1～Gen5 NRZ TX EQ 視覺化。
- Preset 0～10。
- Preshoot、De-emphasis 與 `C-1 / C0 / C+1` 顯示。
- 簡化的 Low-pass Channel。
- NRZ CTLE。
- NRZ 3-tap 手動 DFE。
- Channel、CTLE 與 DFE Sample Margin 檢視。
- PCIe Gen6 PAM4 4-tap TX FIR。
- PAM4 Q0～Q9。
- PAM4 Raw Eye 與 Common `t_center` Eye。
- NRZ／PAM4 波形與近似 Eye metrics。
- PyQt5 GUI 與 PyQtGraph 即時顯示。
- Windows PyInstaller onedir 發布流程。

目前主要限制：

- 大部分程式集中在單一 `main.py`。
- GUI、模擬邏輯、資料狀態與 metrics 高度耦合。
- Channel 僅為一階 Low-pass 模型。
- CTLE 與 DFE 仍是簡化教學模型。
- NRZ sampling phase 固定，沒有完整 CDR。
- PAM4 尚未加入 RXEQ。
- 沒有 Touchstone、impulse response、noise、jitter 與 crosstalk。
- 沒有 Density Eye、Eye Width、Bathtub 與可靠的 BER／SER 評估。
- README 與實際功能存在落差。
- 缺少完整自動測試、場景回歸測試與版本化設定格式。

---

## 3. 產品目標

### 3.1 第一階段目標

建立一個可維護、可測試、可持續擴充的模擬核心，使 GUI 不再直接承擔所有運算。

### 3.2 中期目標

完成可信的：

```text
Pattern
  → TX EQ
  → Channel
  → RX CTLE / FFE / DFE
  → CDR / Slicer
  → Eye / Margin / BER Metrics
```

### 3.3 長期目標

讓使用者可以：

- 匯入實際 Channel 或示波器資料。
- 比較不同 TX Preset、RX setting 與 Channel。
- 自動搜尋較佳 Equalization 設定。
- 觀察 PCIe Link Equalization 的概念流程。
- 儲存、重現與匯出完整分析場景。

---

## 4. 非產品目標

下列項目不列入近期產品承諾：

- 正式 PCI-SIG Compliance Pass／Fail。
- 完整 LTSSM 模擬器。
- 晶體管級 SerDes analog simulation。
- 替代正式示波器、BERT 或 Channel Compliance Software。
- 宣稱模擬 preset、BER、SNDR、TDECQ 或 receiver tolerance 結果具有認證效力。
- 在基礎架構尚未穩定前直接擴充 PCIe Gen7 全功能。

---

## 5. 開發原則

1. **先重整，再擴充。**  
   新功能不得繼續大量堆疊在 `main.py`。

2. **運算核心不得依賴 GUI。**  
   模擬函式不得直接讀寫 PyQt widget。

3. **每一階段都必須可執行。**  
   不採用長期無法執行的全面重寫。

4. **先建立 baseline，再移動程式。**  
   重整前後相同輸入應得到相同輸出。

5. **教學模型與近似模型必須明確標示。**  
   不得將簡化結果包裝為正式規範結果。

6. **每個新模型都要有可視化與數值驗證。**

7. **NRZ 與 PAM4 共用架構，但不強迫共用不合理的演算法。**

8. **所有場景必須可重現。**  
   Pattern、random seed、EQ 設定與 Channel 設定都要能保存。

---

## 6. 整體 Roadmap

| 階段 | 里程碑 | 主要成果 | 優先級 |
|---|---|---|---|
| Phase 0 | Baseline Freeze | 鎖定現有行為、測試向量與版本基準 | P0 |
| Phase 1 | Core Refactor | 模擬核心與 GUI 分離、建立 pipeline | P0 |
| Phase 2 | Channel Foundation | Pulse、Cursor、Impulse、Touchstone 基礎 | P0 |
| Phase 3 | NRZ RXEQ | Sampling、CDR、CTLE、DFE、NRZ metrics | P0 |
| Phase 4 | PAM4 RXEQ | AGC、CTLE、FFE、DFE、3 thresholds、SER | P0 |
| Phase 5 | Auto Equalization | Sweep、Auto adaptation、最佳化與 heatmap | P1 |
| Phase 6 | Measurement Integration | 示波器 CSV、量測比較、tap extraction | P1 |
| Phase 7 | Productization | 場景管理、匯出、文件、安裝與正式發布 | P1 |
| Phase 8 | Advanced Research | FEC、Retimer、Gen7、進階 compliance-like 模型 | P2 |

> 工期應依投入人力重新估算。若以一名主開發者為基準，建議每個 Phase 再拆成數個可獨立驗收的 Sprint，不直接承諾固定完成日期。

---

# 7. 各階段詳細計畫

## Phase 0：Baseline Freeze

### 目的

在重整前建立可比較的產品基準，避免架構調整後無法判斷功能是否被破壞。

### 工作項目

- 建立目前穩定版本 tag。
- 固定 NRZ 與 PAM4 random seed。
- 建立標準測試 pattern。
- 保存標準場景設定。
- 記錄目前各場景的 waveform、tap、Eye metrics 與 status values。
- 建立 Smoke Test Checklist。
- 更新 README，先正確反映目前已有的 RXEQ 功能。
- 記錄已知限制與已知問題。

### 必須建立的 Baseline Cases

- NRZ No EQ。
- NRZ Preshoot only。
- NRZ De-emphasis only。
- NRZ Preshoot + De-emphasis。
- NRZ Channel only。
- NRZ CTLE。
- NRZ CTLE + DFE。
- PAM4 Q0。
- PAM4 Q6。
- PAM4 Raw Eye。
- PAM4 Common `t_center` Eye。

### 驗收條件

- 所有基準場景都能由固定設定重現。
- 重啟程式後能得到相同 pattern 與相同數值結果。
- README 不再將目前產品描述為只有 TXEQ。
- 建立第一批 regression data。

---

## Phase 1：Core Refactor

### 目的

將模擬核心、狀態、metrics 與 GUI 分離，建立後續功能的共同基礎。

### 建議目錄

```text
PCIE-TX-EQ-Simulator/
├─ main.py
├─ pcie_eq/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ profiles.py
│  ├─ patterns.py
│  ├─ tx_eq.py
│  ├─ channel.py
│  ├─ rx_eq.py
│  ├─ metrics.py
│  └─ pipeline.py
├─ ui/
│  ├─ main_window.py
│  ├─ nrz_tab.py
│  ├─ pam4_tab.py
│  └─ widgets.py
└─ tests/
   ├─ test_tx_eq.py
   ├─ test_channel.py
   ├─ test_rx_eq.py
   ├─ test_metrics.py
   └─ test_pipeline.py
```

### 工作項目

#### 1. 建立資料模型

至少包含：

- `SimulationConfig`
- `TxEqConfig`
- `ChannelConfig`
- `RxEqConfig`
- `ClockConfig`
- `PatternConfig`
- `SimulationResult`
- `EyeMetrics`
- `Pam4Metrics`

#### 2. 抽離 TX EQ

移出：

- Preset tables。
- dB／tap conversion。
- NRZ level model。
- NRZ FIR。
- PAM4 FIR。
- Tap constraint。

#### 3. 抽離 Channel

移出：

- Low-pass model。
- Channel configuration。
- Waveform convolution interface。

#### 4. 抽離 RX EQ

移出：

- CTLE。
- DFE。
- Sampling。
- Slicer。
- RX pipeline。

#### 5. 抽離 Metrics

移出：

- NRZ Eye metrics。
- DFE sample margin。
- PAM4 eye openings。
- Error count。

#### 6. 建立統一 Pipeline

```python
result = run_simulation(config)
```

GUI 僅負責：

```text
讀取控制項
  → 建立 SimulationConfig
  → 執行 run_simulation()
  → 顯示 SimulationResult
```

#### 7. 拆分 GUI

- Main Window。
- NRZ Tab。
- PAM4 Tab。
- 共用 Slider／Numeric Input component。
- Plot rendering helper。

### 驗收條件

- `pcie_eq` 模組可以在沒有 PyQt 的情況下執行測試。
- GUI 不直接呼叫底層運算細節。
- Baseline Cases 的結果在允許誤差內保持一致。
- Reset、Preset、Slider、Text input 與切換分頁行為不退化。
- 所有核心模組具備單元測試。
- `main.py` 僅保留程式入口或極少量組裝程式碼。

### 此階段禁止事項

- 不同時大幅修改 UI。
- 不在重整過程順便更改所有數學模型。
- 不新增 Touchstone、CDR、Auto EQ 等大型功能。
- 不進行整套重寫。

---

## Phase 2：Channel Foundation

### 目的

讓使用者能觀察真正與 Channel 相關的 ISI，而不只是一個 Low-pass Alpha。

### 工作項目

#### 1. Pattern Generator

新增：

- All 0／All 1。
- `1010`。
- Long run。
- Single transition。
- Single-bit pulse。
- PRBS7／9／15／23／31。
- User-defined sequence。
- 固定 random seed。

#### 2. Pulse／Cursor Analysis

顯示：

```text
Pre3  Pre2  Pre1  Main  Post1  Post2  Post3
```

提供：

- Main cursor amplitude。
- Pre-cursor ISI。
- Post-cursor ISI。
- Residual ISI。
- 最佳 sampling point。
- TX、Channel、CTLE 後的 cursor 比較。

#### 3. Channel Model 分級

- Simplified Low-pass。
- Synthetic impulse response。
- User-defined impulse response。
- Touchstone `.s2p`。
- Differential `.s4p`／`SDD21`，視函式庫與資料格式支援情況逐步加入。

#### 4. Channel Views

- Frequency response。
- Insertion loss。
- Impulse response。
- Step response。
- Pulse response。
- Time-domain waveform。

### 驗收條件

- Channel 可以透過統一介面切換。
- 匯入相同 Channel 時結果可重現。
- Pulse response 可正確標示 main、pre 與 post cursor。
- No Channel 模式不改變原始 TX waveform。
- Impulse response convolution 有單元測試。
- 不合法 Touchstone 或 impulse data 有清楚錯誤訊息。

---

## Phase 3：NRZ RXEQ

### 目的

完成可理解、可比較、可自動調整的 NRZ receiver chain。

### 工作項目

#### 1. Sampling Phase

- 手動 phase slider。
- Phase sweep。
- 最佳 Eye Height phase。
- 最佳 Margin phase。
- Sampling point overlay。

#### 2. CDR

第一版採教學模型：

- Fixed phase。
- Auto center。
- Early／Late detector。
- Phase tracking。
- Frequency offset。
- Lock／unlock indication。

後續再評估：

- Loop bandwidth。
- Jitter tracking。
- Clock phase trajectory。

#### 3. CTLE

加入：

- DC gain。
- Peaking dB。
- Zero frequency。
- Pole frequency。
- Frequency response plot。
- Noise amplification 顯示。

#### 4. RX FFE

新增：

- Pre-cursor taps。
- Main tap。
- Post-cursor taps。
- Tap normalization。
- Manual mode。

#### 5. DFE

新增：

- 可調 tap 數量。
- 1～5 taps 初始版本。
- Tap contribution 顯示。
- Error propagation 顯示。
- Decision history。
- Manual／Auto mode。

#### 6. NRZ Metrics

- Eye Height。
- Eye Width。
- Sampling Margin。
- Decision histogram。
- Error count。
- BER estimate。
- Horizontal／Vertical bathtub 初版。
- Density Eye。

### 驗收條件

- 使用者可以比較 Channel、CTLE、FFE、DFE 各階段的結果。
- Sampling phase 改變會同步更新 Eye 與 Metrics。
- Auto center 能找到合理取樣位置。
- DFE taps 對 post-cursor ISI 的影響可由 pulse response 驗證。
- CTLE 過度增益時能觀察到 noise amplification。
- 所有 metrics 都清楚標示為模擬或估計值。

---

## Phase 4：PAM4 RXEQ

### 目的

使 Gen6 分頁從 PAM4 TX EQ Viewer 升級為完整 PAM4 TX／Channel／RX 教學流程。

### 工作項目

#### 1. PAM4 Pattern 與 Coding

- PAM4 symbol generator。
- Gray coding。
- Precoding on／off。
- User-defined PAM4 symbols。

#### 2. PAM4 RX Front End

- AGC／VGA。
- PAM4 CTLE。
- RX FFE。
- Common CDR phase。
- 三個 slicer thresholds。

#### 3. PAM4 DFE

- 多 tap DFE。
- 各 level decision。
- Error propagation。
- Burst error observation。

#### 4. Threshold Optimization

- Manual thresholds。
- Auto thresholds。
- Level mean。
- Level sigma。
- Level mismatch。

#### 5. PAM4 Metrics

- Upper／Middle／Lower Eye Height。
- Upper／Middle／Lower Eye Width。
- Minimum Eye。
- Eye skew。
- Symbol Error Rate。
- Bit Error Rate。
- Error burst length。
- Level histogram。

### 驗收條件

- PAM4 RXEQ 有獨立的 TX、Channel、RX 與 decision views。
- 三個 thresholds 可手動與自動調整。
- Upper／Middle／Lower 三個 eye 使用共同 CDR phase。
- Auto threshold 不得以已知 transmitted symbol 作為正式 decision shortcut；若教學模式使用 reference data，必須明確標示。
- SER 與 BER 計算具有固定 seed 的回歸測試。

---

## Phase 5：Auto Equalization

### 目的

讓使用者從手動觀察升級到系統化比較與最佳化。

### 工作項目

#### 1. Sweep Engine

- TX Preset sweep。
- TX tap sweep。
- CTLE sweep。
- FFE sweep。
- DFE sweep。
- Sampling phase sweep。
- PAM4 threshold sweep。

#### 2. Heatmap

支援：

- TX Preset × CTLE。
- TX Preset × DFE。
- CTLE × Sampling phase。
- Channel loss × Preset。
- PAM4 Threshold × CTLE。

顏色指標可選：

- Eye Height。
- Eye Width。
- Margin。
- BER／SER。
- Minimum PAM4 Eye。

#### 3. Auto Adaptation

依序實作：

1. Grid search。
2. Coordinate descent。
3. Sign-sign LMS 或簡化 decision-directed adaptation。
4. Joint TX／RX optimization。

#### 4. Equalization History

顯示：

- Iteration。
- Current taps。
- Metric。
- Best setting。
- Convergence。
- Lock／fail reason。

#### 5. Link Equalization Visualizer

概念性顯示：

```text
Local RX evaluates signal
  → requests Link Partner TX preset/coefficient
  → Link Partner updates TX
  → Local RX re-evaluates
```

### 驗收條件

- Sweep 可以在 GUI 外獨立執行。
- Auto EQ 的結果可以保存與重現。
- 使用者可選擇最佳化目標。
- 最佳化過程不阻塞 GUI；需有取消功能。
- 同一場景與同一 random seed 得到一致結果。
- Link Equalization 畫面不得宣稱完整模擬 LTSSM。

---

## Phase 6：Measurement Integration

### 目的

建立模擬與實際量測資料之間的橋梁。

### 工作項目

#### 1. Waveform Import

- Generic CSV。
- Time／Voltage 欄位選擇。
- Tektronix CSV。
- Keysight CSV。
- Differential waveform。
- UI／Baud rate 設定。
- Edge alignment。

#### 2. Measured vs Simulated

比較：

- Ideal FIR。
- Scope-like waveform。
- Imported waveform。
- Pulse response。
- Cursor。
- Eye。
- Level。
- Estimated taps。

#### 3. Tap Extraction

第一版：

- Step／pulse response fitting。
- Estimate `C-1 / C0 / C+1`。
- Residual error。
- Fit quality。
- Manual fit range。

#### 4. Export

- Waveform CSV。
- Metrics CSV。
- Eye PNG。
- Pulse／cursor CSV。
- Scenario JSON。
- Analysis summary Markdown。

### 驗收條件

- 匯入錯誤資料時不造成程式崩潰。
- 單位、sampling rate 與 UI 定義清楚。
- 模擬與量測 alignment 可手動修正。
- Tap extraction 顯示 fit residual 與限制。
- 所有量測推估結果標示為 estimated。

---

## Phase 7：Productization

### 目的

讓產品具備穩定發布、文件、場景管理與日常使用能力。

### 工作項目

#### 1. Scenario Management

- New／Save／Save As／Load。
- JSON schema version。
- Recent files。
- Unsaved changes warning。
- Default profiles。
- A／B comparison。

#### 2. Generation Profiles

建立：

- Gen1。
- Gen2。
- Gen3。
- Gen4。
- Gen5。
- Gen6。
- Custom。

每個 Profile 管理：

- Data rate。
- Modulation。
- Samples per UI。
- TX tap count。
- Preset table。
- Pattern defaults。
- Channel defaults。
- RX architecture。
- Metric defaults。

#### 3. 文件

- README。
- User Guide。
- Architecture Guide。
- Model Limitations。
- Developer Guide。
- Validation Cases。
- Release Notes。
- Glossary。

#### 4. Windows 發布

- Clean virtual environment。
- PyInstaller onedir。
- 啟動時間檢查。
- Windows Defender 誤判風險檢查。
- 版本資訊。
- Icon。
- Portable package。
- Installer 是否導入另案評估。

#### 5. UI／UX

- 清楚區分 TX、Channel、RX、Metrics。
- Basic／Advanced 模式。
- Tooltips。
- Reset scope 清楚化。
- 設定變更提示。
- 長任務 progress 與 cancel。
- Error dialog 統一格式。

### 驗收條件

- 新使用者可只靠 User Guide 完成基本情境。
- 所有場景可儲存、載入與跨版本 migration。
- Windows release package 可在乾淨環境執行。
- README、版本號與實際功能一致。
- 至少完成一次完整 release candidate 測試。

---

## Phase 8：Advanced Research

### 候選功能

- Retimer／Multi-segment Channel。
- Package、connector 與 via model。
- Crosstalk matrix。
- Gen6 FEC teaching model。
- Pre-FEC／Post-FEC error view。
- RLM／SNDR approximation。
- More advanced CDR。
- PCIe Gen7 profile。
- Batch CLI。
- Python API。
- Plugin architecture。
- Hardware measurement automation interface。

### 啟動條件

此階段只有在以下條件完成後才開始：

- Core architecture 穩定。
- NRZ RXEQ 完成。
- PAM4 RXEQ 完成。
- Scenario format 穩定。
- 自動測試覆蓋核心模型。
- 至少有一個穩定公開版本。

---

# 8. 建議版本策略

| 建議版本 | 主要範圍 |
|---|---|
| `0.x-refactor` | Baseline、模組化、測試與 pipeline |
| `0.x-channel` | Pattern、Pulse、Cursor、Impulse、Touchstone |
| `0.x-nrz-rxeq` | CDR、CTLE、FFE、DFE、NRZ metrics |
| `0.x-pam4-rxeq` | PAM4 RXEQ、threshold、SER／BER |
| `0.x-auto-eq` | Sweep、Heatmap、Auto adaptation |
| `0.x-measurement` | CSV import、comparison、tap extraction |
| `1.0` | 穩定教學版、文件完整、場景可重現 |

版本號可依目前專案實際版本調整，但每個版本只應承擔一個主要產品主題。

---

# 9. 開發工作流程

## 9.1 Issue 分類

建議使用以下 labels：

- `type:feature`
- `type:refactor`
- `type:bug`
- `type:test`
- `type:docs`
- `type:research`
- `area:tx`
- `area:channel`
- `area:rx`
- `area:metrics`
- `area:pam4`
- `area:ui`
- `area:release`
- `priority:P0`
- `priority:P1`
- `priority:P2`
- `status:blocked`
- `status:needs-validation`

## 9.2 每個 Feature Issue 必須包含

- 背景。
- 使用者問題。
- 產品目標。
- 範圍。
- 非範圍。
- UI 行為。
- 模型定義。
- 輸入／輸出。
- 驗收條件。
- 測試案例。
- 文件需求。
- 已知限制。
- 相依 Issue。

## 9.3 Branch 建議

```text
refactor/<topic>
feature/<topic>
fix/<topic>
docs/<topic>
test/<topic>
```

## 9.4 Pull Request 必須包含

- 變更摘要。
- 為何需要。
- 影響模組。
- Before／After。
- 測試證據。
- Baseline 比較。
- UI screenshot 或 waveform 比較。
- 已知限制。
- 後續工作。

---

# 10. Definition of Done

一個功能只有在以下條件全部完成後才算 Done：

- 功能符合 Issue 驗收條件。
- 核心運算不直接依賴 GUI。
- 已加入單元測試。
- 已加入至少一個 regression case。
- Invalid input 有錯誤處理。
- 不會破壞既有 baseline。
- UI 有清楚標籤與 tooltip。
- README 或 User Guide 已更新。
- 教學模型與近似限制已標示。
- PR 已完成 review。
- Windows build smoke test 通過。
- Release notes 已記錄使用者可見變更。

---

# 11. 測試策略

## 11.1 Unit Tests

- Tap conversion。
- TX FIR。
- PAM4 FIR。
- Channel convolution。
- CTLE response。
- FFE。
- DFE sign convention。
- Slicer。
- Sampling phase。
- Eye metrics。
- BER／SER。
- Scenario serialization。

## 11.2 Golden Vector Tests

對固定輸入保存預期輸出：

- TX symbols。
- Waveform。
- Cursor。
- Sample values。
- Decisions。
- Metrics。

## 11.3 Property Tests

例如：

- No EQ 時 main tap 不應被改變。
- Identity Channel 應保持 waveform。
- DFE tap 為零時不應改變 sample。
- PAM4 threshold 必須保持順序。
- 相同 seed 必須產生相同結果。

## 11.4 GUI Smoke Tests

- 啟動。
- 切換 tab。
- Preset。
- Slider。
- Text input。
- Reset。
- Load／Save。
- Long-running sweep cancel。
- Invalid file import。

## 11.5 Performance Tests

- GUI redraw latency。
- Eye trace rendering。
- Density Eye。
- Large pattern。
- Touchstone convolution。
- Preset sweep。
- Memory usage。
- Windows executable startup。

---

# 12. 主要風險與對策

| 風險 | 影響 | 對策 |
|---|---|---|
| 重整時改變原本結果 | 高 | 先建立 baseline 與 golden vectors |
| 模型越做越像 compliance，但不夠準確 | 高 | 清楚標示 educational approximation |
| GUI 與模型再次耦合 | 高 | 所有新功能必須先有非 GUI API |
| Auto EQ 過度補償 | 高 | 加入 noise、tap limits 與多目標 metrics |
| PAM4 複雜度快速增加 | 高 | 先完成 common CDR 與 threshold，再加入 adaptive DFE |
| Touchstone 匯入格式不一致 | 中 | 限定支援格式並提供 validation |
| 即時繪圖變慢 | 中 | 分離計算頻率與繪圖頻率、使用背景工作與取消 |
| 版本場景不相容 | 中 | JSON schema version 與 migration |
| README 落後於實作 | 中 | 文件列入 Definition of Done |
| Windows 防毒誤判 | 中 | 維持 onedir、乾淨環境建置與 release checksum |

---

# 13. 優先級總表

## P0：必須先完成

- Baseline Freeze。
- Core Refactor。
- 統一 Simulation Pipeline。
- 單元測試與 Regression Tests。
- Pattern Generator。
- Pulse／Cursor Analysis。
- Channel Engine。
- Sampling Phase。
- CDR 基礎。
- NRZ CTLE／FFE／DFE 完整化。
- PAM4 RXEQ。
- 正確的 Eye／Margin／BER／SER metrics。

## P1：完成核心產品後加入

- Density Eye。
- Bathtub。
- Sweep。
- Heatmap。
- Auto Equalization。
- Link Equalization Visualizer。
- 示波器 CSV 匯入。
- Measured vs Simulated。
- Tap extraction。
- Scenario Save／Load。
- 匯出與報告。
- 完整 User Guide。

## P2：延後研究

- FEC。
- Retimer。
- SNDR／RLM approximation。
- Gen7。
- 完整 compliance-like reference receiver。
- Hardware automation。
- Plugin system。

---

# 14. 下一步執行清單

建議立即建立以下工作：

1. 建立 `Roadmap` 與 `Architecture Refactor` milestone。
2. 建立目前穩定版 tag。
3. 建立 10 組 Baseline Cases。
4. 更新 README，使 TXEQ／RXEQ 現況一致。
5. 建立 `models.py`。
6. 抽離 `tx_eq.py`。
7. 抽離 `channel.py`。
8. 抽離 `rx_eq.py`。
9. 抽離 `metrics.py`。
10. 建立 `pipeline.py`。
11. 為每個模組建立單元測試。
12. 完成 baseline regression。
13. 再開始 Pulse／Cursor Analysis。

---

# 15. 產品決策摘要

PCIE-TX-EQ-Simulator 後續開發的核心策略是：

> **先讓架構可維護，再讓模型更完整；先讓結果可重現，再增加自動化；先完成 Gen1～Gen6 教學流程，再考慮 Gen7 與 compliance-like 功能。**

第一個正式開發主題不是新增更多滑桿，而是：

> **Baseline Freeze + Core Refactor + Simulation Pipeline**

此階段完成後，Channel、CDR、PAM4 RXEQ、自動 Equalization 與量測資料整合才有穩定的開發基礎。
