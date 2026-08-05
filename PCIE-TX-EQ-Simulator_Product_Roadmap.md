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
- CTLE、FFE、DFE、CDR 與 slicer 如何影響接收結果。
- PCIe Gen1～Gen5 NRZ 與 Gen6／Gen7 PAM4 的主要訊號處理差異。
- TX、Channel、RX、sampling 與 threshold 如何共同影響 Eye、Margin 與 error metrics。
- 理想模型、示波器類波形與實際量測結果為何可能不同。

本產品**不是 PCI-SIG Compliance Tool**。除非另有正式規格、Reference Model、驗證資料與相關性證據，任何結果不得宣稱等同示波器、BERT、SigTest、Seasim、PCI-SIG 認證或真實硬體最佳設定。

---

## 2. 事實來源、可行性與模型等級

### 2.1 事實來源

Roadmap 狀態以已合併至 `main` 的程式碼為準。技術功能是否可開始，則必須同時依據：

- 可取得的正式規格或官方文件。
- 公開 Reference Model／方法學／廠商技術文件。
- 可獨立重現的數學定義。
- 可用於驗證的 golden vectors、分析解、Reference implementation 或量測資料。

完整 Phase 可行性稽核與參考資料登錄於：

```text
docs/ROADMAP_FEASIBILITY_AUDIT.md
```

### 2.2 模型等級

每個 Implementation 必須標示下列其中一種等級：

1. **Specification-derived**：由可取得的正式規格直接實作。
2. **Reference-model-derived**：由官方方法學、Reference Receiver 或已驗證模型實作。
3. **Teaching approximation**：用於說明概念，不代表 PCIe-compliant receiver／channel。
4. **Research experiment**：尚未完成有效性驗證的探索工作。

GUI、報告與匯出結果必須顯示正確模型等級，不得讓 teaching approximation 看起來像規格模型。

### 2.3 狀態定義

- **Completed**：PR 已合併至 `main`，CI 與 Merge Gate 通過。
- **Active**：目前 Phase 已啟動，且存在已核准的下一個 Implementation。
- **Planned**：依賴與資料基礎已確認，但尚未開始。
- **Conditional**：演算法可行，但規格、Reference Model 或驗證資料尚未完整。
- **Blocked**：缺少必要依賴、數學定義或 validation oracle。
- **Research Backlog**：不承諾實作日期，需逐項重新做可行性審查。

Draft PR、未合併 branch、本機結果與未驗證網路資料不能當成正式產品基準。

---

## 3. Evidence Gate

每個 Implementation Issue 在交付給實作者前，必須具備：

- Claim level／模型等級。
- Authoritative sources 與精確版本。
- Source access：public、member-only、licensed、user-provided 或 unavailable。
- 完整數學定義、state machine、polynomial、filter 或轉換規則。
- input／output、單位、sample interval、shape、dtype、ordering 與 normalization contract。
- validation oracle：固定 golden vector、分析解、官方 example、獨立實作或量測資料。
- allowed claims 與 forbidden claims。
- 資料不足時的 stop condition。

啟動條件：

> 至少一個權威資料來源，加上一個獨立 validation method。

若只有概念性資料，功能只能以 Teaching approximation 實作。若數學定義或 validation oracle 不存在，功能必須保持 Blocked，不得用推測補完。

禁止：

- 使用 production function 動態產生自己的 expected values。
- 用轉型、rounding、重新計算或放寬 tolerance 掩蓋差異。
- 根據名稱猜測不同標準之間的 polynomial、receiver topology 或 compliance method 相同。

---

## 4. 目前已驗證的產品基準

### 4.1 Production code baseline

```text
latest production-code merge: c4fd8c8191919c30d8e28383d94804fe3e68db25
regression baseline: 192 tests
CI: GitHub Actions / Windows / Python 3.11
```

之後的 docs-only commits 不改變上述 production regression baseline。

### 4.2 已完成工作

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

Implementation 22／Issue #49／PR #50 已完成：

- GUI-independent `pcie_eq.patterns`。
- NRZ bits／symbols conversion。
- Seeded 與 global RNG random generation。
- All 0／All 1、Alternating、Long run、Single transition、Single-bit pulse。
- PAM4 random compatibility wrapper。
- GUI RNG、value、shape、dtype 與 raw-byte compatibility。

#### Phase 2 / Step 2.2：PRBS Core — Completed

Implementation 23／Issue #54／PR #56 已完成：

- `docs/PRBS_CONVENTION.md` 已由 PR #55 先行凍結規格。
- 新增 deterministic PRBS7／9／15／23／31 pure core。
- Convention ID：`pcie_eq-prbs-fibonacci-lsb-v1`。
- 支援 default all-ones 與 valid custom initial state。
- Exact output contract：一維 `numpy.int8`、值只含 `0 / 1`。
- 五種 order 具 hardcoded golden-prefix tests。
- PRBS7／9／15 具完整 maximal-period state traversal。
- PRBS23／31 具獨立 recurrence、custom-state、repeatability 與 prefix consistency validation。
- NumPy global RNG isolation、validation 與 module-boundary tests 通過。
- 未修改 GUI、pipeline、Preset 或 simulation math。

### 4.3 目前實際模型限制

- `pcie_eq.channel.simple_channel()` 仍是一階遞迴低通 Teaching approximation。
- 現有 CTLE 與 DFE 是簡化教學模型，不是 PCIe Gen-specific Reference Receiver。
- 現有 Eye／Margin metrics 是近似指標，不是 compliance metrics。
- 尚無 Pattern Configuration Contract、impulse convolution、Touchstone、完整 sampling／RXEQ、統計 BER 或量測相關性。

---

## 5. 整體開發順序

後續功能依資料與演算法依賴推進：

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
  → NRZ Sampling / RXEQ Teaching Model or Reference Model
  → PAM4 RXEQ Teaching Model or Reference Model
  → Deterministic Impairments
  → Statistical Metrics Validation
  → Reproducible Scenario / Experiment
  → Sweep / Auto Equalization
  → Measurement Integration
  → Product UX / Release
```

每一項新能力原則上依序完成：

```text
Evidence Gate
  → Pure Core API
  → Validation Contract
  → Unit Tests
  → Module Boundary Tests
  → Existing Behavior Compatibility
  → GUI Integration
  → Documentation / Limitations
```

---

## 6. Phase 可行性總表

| Phase | 里程碑 | 狀態 | 可行性結論 | 啟動條件 |
|---|---|---|---|---|
| Phase 0 | Baseline Freeze | Completed | 已完成 | 無 |
| Phase 1 | Core Refactor | Completed | 已完成 | Phase 0 |
| Phase 2 | Channel Foundation | Active | 可實現；部分 Touchstone mixed-mode 工作有條件 | Phase 1 + 每項 Evidence Gate |
| Phase 3 | NRZ Sampling & RXEQ | Conditional | Generic teaching receiver 可實現；PCIe Gen-specific receiver 需規格或 Reference Model | Phase 2 + Receiver Evidence Gate |
| Phase 4 | PAM4 RXEQ | Conditional | Generic PAM4 receiver 可實現；PCIe-specific adaptation 需規格或 AMI／Reference Model | Phase 2 + 共用 receiver contract |
| Phase 5 | Signal Impairments & Statistical Metrics | Conditional | seeded impairment 可實現；BER／bathtub 需統計方法與 validation oracle | Phase 3、4 的 sampling／decision 穩定 |
| Phase 6 | Reproducibility & Experiment Infrastructure | Planned | 完全可實現 | Config contracts 穩定 |
| Phase 7 | Sweep & Auto Equalization | Planned | 可最佳化 simulator objective；不能直接代表硬體最佳值 | Phase 5、6 |
| Phase 8 | Measurement Integration | Conditional | canonical CSV 可實現；native formats 與 tap fitting 視文件／資料而定 | Phase 2、5、6 + sample datasets |
| Phase 9 | Product Usability & Release | Planned | 可實現 | 核心 workflow 與模型標示穩定 |
| Research Backlog | Advanced Research | Research Backlog | 每項獨立審查，不承諾實作 | 穩定公開版本 + 個別 Evidence Gate |

---

# 7. Phase 2：Channel Foundation

## 7.1 目的

建立可替換、可驗證、可重現的 Pattern 與 Channel 基礎，使後續 ISI、cursor、sampling 與 RXEQ 不再只依賴一階 Low-pass Alpha。

## 7.2 Step 2.1：Pattern Core — Completed

Implementation 22 已完成。

## 7.3 Step 2.2：PRBS Core — Completed

Implementation 23／Issue #54／PR #56 已完成。

規格與實作依據：

- `docs/PRBS_CONVENTION.md`。
- Convention ID：`pcie_eq-prbs-fibonacci-lsb-v1`。
- PRBS7／9／15／23／31 polynomial 與 nominal period 由公開來源交叉確認。
- Fibonacci LFSR、right shift、LSB output、output-before-update 與 non-inverted polarity 已凍結。
- Default initial state 為 all ones；zero state 與超出 order 範圍的 state 會拒絕。

Validation：

- 五種 order 的 all-ones 與 custom-state hardcoded golden prefixes。
- PRBS7／9／15 full-period nonzero-state traversal。
- PRBS23／31 test-side independent recurrence 與 custom-state comparisons。
- deterministic repeatability、prefix consistency、dtype／shape／value contract。
- NumPy global RNG isolation與 module-boundary tests。

模型等級：**Reference-model-derived general test pattern**。不得稱為 PCIe compliance pattern、PCI-SIG Reference Pattern，或指定硬體 BERT 的 bit-exact phase。

PRBS Core 目前只提供 pure API；GUI selector 與 PatternConfig 尚未加入。

## 7.4 Step 2.3：Pattern Configuration Contract — Planned / Next Evidence Gate

建立 GUI-independent pattern request／configuration：

- pattern type。
- symbol count。
- random seed。
- PRBS order／initial state／convention version。
- deterministic pattern parameters。
- user-defined bits／symbols validation。

## 7.5 Step 2.4：Channel Interface / ChannelConfig

統一支援：

```text
none
legacy_lowpass
impulse_response
```

要求：

- `none` 為 identity。
- `legacy_lowpass` 保持既有 baseline。
- mode、sample interval、shape、dtype、normalization 與 errors 明確。
- core 不依賴 GUI。

## 7.6 Step 2.5：Impulse Response Convolution

必須先固定：

- `full`／`same`／`valid` policy。
- sample interval compatibility。
- output length。
- time-zero／main cursor alignment。
- normalization。
- truncation／padding。

使用分析解與固定 impulse golden cases驗證。

## 7.7 Step 2.6：Synthetic / User-defined Impulse

依序加入：

1. Synthetic impulse。
2. User-provided numeric impulse。
3. built-in teaching channels。

每個 teaching channel 必須公開公式與參數，不得假裝成真實 PCIe channel。

## 7.8 Step 2.7：Pulse / Cursor Analysis

Channel contract 與 convolution 穩定後才實作：

```text
Pre3  Pre2  Pre1  Main  Post1  Post2  Post3
```

輸出 main cursor、pre／post cursor ISI、residual ISI、sampling phase 與 stage comparison。

## 7.9 Step 2.8：Pattern / Channel GUI Integration

等 PatternConfig、ChannelConfig、convolution 與 cursor result 穩定後再加入 selector、parameters、impulse input 與 cursor overlay。

## 7.10 Step 2.9：Channel Views

顯示 frequency response、insertion loss、impulse／step／pulse response 與 time-domain waveform。GUI 只顯示 core result，不重新計算模型。

## 7.11 Step 2.10：Touchstone

- `.s2p` parser 與 single-ended teaching path可實現。
- S-parameter 轉 impulse 前必須處理 frequency spacing、DC extrapolation、windowing 與 reference impedance。
- `.s4p`／mixed-mode／`SDD21` 只有在 port ordering、wave definition 與 validated sample files 完成後才能開始。

`.s2p` 與 `.s4p` 不得塞入同一大型 PR。

## 7.12 Phase 2 Exit Gate

- Pattern 可 bit-exact 重現。
- Channel 可透過統一 interface 切換。
- `none` 與 legacy Low-pass regression 通過。
- impulse convolution 有分析解與 hardcoded golden tests。
- cursor extraction 有 synthetic golden cases。
- Pattern／Channel core 可無 PyQt 執行。
- Touchstone parser 與轉換假設有明確 errors／limitations。

---

# 8. Phase 3：NRZ Sampling & RXEQ

## 8.1 可行性界線

Generic sampling、slicer、CTLE、FFE、DFE 與 simple CDR 可以用公開 DSP 定義實作。

PCIe Gen-specific receiver 則必須取得：

- 對應 revision 的 PCIe Base／PHY Test specification，或
- 官方 Reference Receiver／方法學，或
- 可驗證的 IBIS-AMI／量測 Reference Model。

沒有上述資料時，本 Phase 只能走 Teaching Receiver 路徑。

## 8.2 Teaching Receiver 路徑

1. Sampling API、manual phase、overlay。
2. Phase sweep 與 objective contract。
3. frequency-domain CTLE teaching model。
4. manual RX FFE。
5. DFE contribution／decision history。
6. fixed／auto-center／early-late teaching CDR。
7. deterministic NRZ metrics。

Validation 使用 synthetic channel、known cursor cancellation 與 analytical cases。

## 8.3 PCIe Reference Receiver 路徑

必須另立 Evidence Gate Issue，記錄 spec revision、filter／tap constraints、adaptation rules、stressed-eye method 與 validation source。

一個通用 receiver 不得被標示為同時適用所有 PCIe generations；公開 PCI-SIG 資料已顯示不同 generation 的 Reference Receiver topology 會改變。

## 8.4 禁止宣稱

- PCIe receiver compliance。
- receiver tolerance pass／fail。
- 真實 PHY adaptation 行為。
- 未經 correlation 的 hardware margin。

---

# 9. Phase 4：PAM4 RXEQ

## 9.1 可行性界線

IBIS-AMI／PAMn 可作為 generic PAM4 receiver 的資料基礎。可實作：

- AGC／VGA。
- CTLE、FFE、simple DFE。
- common sampling phase。
- three slicer thresholds。
- symbol decisions 與 deterministic SER。

## 9.2 Conditional 工作

以下必須有 PCIe spec、Reference Receiver 或 validated AMI model：

- Gen6／Gen7 exact adaptation。
- tap constraints。
- threshold training。
- precoding／Gray coding interaction beyond documented rules。
- stressed-eye tolerance。

不得把 generic PAM4 receiver 描述為 PCIe compliance receiver。

---

# 10. Phase 5：Signal Impairments & Statistical Metrics

## 10.1 Part A：Deterministic / Seeded Impairments — Feasible

- AWGN／vertical noise。
- sinusoidal／deterministic jitter。
- bounded random-jitter teaching model。
- frequency／phase offset。
- explicitly synthetic interference／crosstalk。
- density accumulation。

每個模型必須有公式、單位、seed policy 與 distribution validation。

## 10.2 Part B：Statistical Metrics — Conditional

Eye Width、bathtub、BER／SER estimate 必須等 sampling／threshold／decision contract 穩定後開始。

產品只能：

- 報告 empirical error rate、sample count 與 confidence limits；或
- 採用有文件與獨立 validation 的 statistical／analytical method。

低 BER 不可只靠短序列 Monte Carlo 推估。Raw PAM4 SER／BER 也不得被描述為 PCIe post-FEC link reliability，因為目前尚未模擬完整 FEC、CRC 與 replay chain。

---

# 11. Phase 6：Reproducibility & Experiment Infrastructure

本 Phase 完全可實現：

- versioned Scenario schema。
- Pattern、TXEQ、Channel、RXEQ、sampling、threshold、impairment config。
- RNG policy。
- Experiment Run identity 與 resolved config。
- result／artifact references。
- batch result model。
- CSV／JSON／Markdown export core。
- schema migration policy。

Round-trip、migration 與 golden export tests 為主要 validation oracle。

---

# 12. Phase 7：Sweep & Auto Equalization

可實作：

1. Preset Resolver。
2. Sweep request／result model。
3. NRZ／PAM4 preset sweep。
4. TX／RX parameter sweep。
5. heatmap data model。
6. grid search／coordinate descent。

啟動條件：

- objective metrics 穩定。
- Scenario／Experiment 已完成。
- invalid result、progress、cancel contract 已定義。

結果只能描述為 configured sweep 內的 simulated optimum。Decision-directed adaptation 與 joint optimization 必須標示 Research experiment，不能與 deterministic sweep 混為同一交付。

---

# 13. Phase 8：Measurement Integration

## 13.1 Feasible first delivery

- project-owned canonical time／voltage CSV。
- units、sample rate、UI／baud、polarity validation。
- documented Keysight／Tektronix CSV variants。
- edge／pattern alignment。
- measured-vs-simulated waveform／cursor comparison。

## 13.2 Conditional adapters

Native vendor formats只支援有公開格式文件、SDK 或 user-provided sample files 的指定 instrument family／version。

例如 Tektronix 公開 WFM 格式只代表文件列出的 instrument families，不代表所有 Tektronix oscilloscopes。

## 13.3 Tap extraction

必須具備 known pattern／step response、明確 FIR order、constraints、residual、fit quality 與 validation datasets。沒有 reference waveform 或 fitting methodology 時保持 Blocked。

---

# 14. Phase 9：Product Usability & Release

- Scenario New／Save／Load UX。
- A／B comparison。
- reports、guides、limitations、validation cases。
- Basic／Advanced mode。
- 統一 errors、progress／cancel UX。
- Release Notes 與 glossary。

Release Gate 必須確認每個 output 顯示正確模型等級與限制。

Packaging、EXE、Installer 與防毒誤判仍需另立產品決策。

---

# 15. Research Backlog

下列項目不再列為承諾中的 Planned Phase；每項需獨立 feasibility review：

- Retimer／multi-segment channel。
- package、connector、via model。
- crosstalk matrix。
- Gen6 FEC／pre-FEC／post-FEC view。
- RLM／SNDR approximation。
- advanced CDR。
- PCIe Gen7 profile。
- Batch CLI／public API。
- plugin architecture。
- hardware measurement automation。

其中 CLI／API 可實現；FEC、Gen7、hardware automation 等則取決於規格、Reference Model、SDK、license、hardware 與 validation data。

---

## 16. 所有 PR 的 Merge Gate

每個 PR 必須提供：

- Related Roadmap Issue。
- Evidence Gate summary 與模型等級。
- Authoritative source／version／access status。
- Scope／non-scope／allowed claims／forbidden claims。
- mathematical／data contract。
- validation oracle 與 independent expected values。
- unit tests、module-boundary tests、regression count。
- GitHub Actions run 與 `python -c "import main"`。
- GUI startup／interaction evidence（涉及 GUI 時）。
- `git diff --check`。
- value／shape／dtype／ordering／raw-byte compatibility。
- RNG state／seed／consumption order。
- public import surface 與 call sequence。
- known limitations。

任何資料不足、Reference Model 缺失或 validation 無法獨立成立的功能，不得通過 Merge Gate。

---

## 17. 立即下一步

### Implementation 24：Define Pattern Configuration Contract

下一項工作是由 Planner／Reviewer先完成 Pattern Configuration 的 Evidence Gate 與文件，不直接交付 code implementation。

資料基礎：

- 已合併的 `pcie_eq.patterns` public API。
- 已合併的 `docs/PRBS_CONVENTION.md`。
- 既有 NRZ／PAM4 random、deterministic pattern 與 dtype compatibility tests。
- Pattern Configuration 是本產品內部 software contract，不以名稱猜測 PCIe compliance pattern。

開始 code 前必須先凍結：

- pattern type taxonomy 與 versioning。
- bit／symbol domain、modulation 與 count semantics。
- random seed、PRBS order／state／convention ID。
- deterministic pattern parameters。
- user-defined bit／symbol validation。
- resolved request／result shape、dtype、ordering 與 error contract。
- round-trip、validation matrix 與 independent expected cases。
- allowed／forbidden claims 與 GUI／Channel non-scope。

文件由 Planner／Reviewer建立並先合併；Gemini 只在文件凍結後負責 pure code 與 tests。

完成 Pattern Configuration 後，再依序進入 Channel Interface、Impulse Convolution、Synthetic／User Impulse 與 Cursor Analysis。每一步仍須個別通過 Evidence Gate。