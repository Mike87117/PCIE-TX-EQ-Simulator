# PCIE-TX-EQ-Simulator Roadmap Feasibility Audit

> Audit date: 2026-08-05  
> Repository baseline before this audit: `04f41f228b7c30fdb4a2d7f322694d8669e17626`  
> Regression baseline: 182 tests  
> Purpose: determine whether every planned phase is technically implementable, what evidence is required, and what claims are allowed.

---

## 1. Audit conclusion

The roadmap is technically achievable only if it distinguishes four different model levels:

1. **Specification-derived model** — implemented from an accessible normative specification.
2. **Reference-model-derived model** — implemented from a published reference receiver, official methodology, or validated vendor model.
3. **Teaching approximation** — demonstrates a signal-processing concept but does not represent a PCIe-compliant device.
4. **Research experiment** — exploratory work whose validity has not yet been established.

The current application already contains teaching approximations:

- `pcie_eq/channel.py` is a first-order recursive low-pass model.
- `pcie_eq/rx_eq.py` explicitly describes the CTLE and DFE as simplified educational models.
- `pcie_eq/metrics.py` contains approximate eye and margin calculations rather than compliance metrics.

Therefore, future roadmap items must not silently change from “teaching approximation” to “PCIe model.” Each implementation must declare its evidence level and claim level before code is written.

---

## 2. Evidence Gate required before every Implementation

Every new implementation Issue must include the following evidence package.

### 2.1 Required fields

- **Claim level**: specification-derived, reference-model-derived, teaching approximation, or research experiment.
- **Authoritative sources**: exact specification, official documentation, paper, or measurement dataset.
- **Access status**: public, member-only, licensed, supplied by the user, or unavailable.
- **Mathematical definition**: equations, state machine, polynomial, filter definition, or transformation rules.
- **Input/output contract**: units, sampling interval, shape, dtype, ordering, normalization, and error behavior.
- **Validation oracle**: hardcoded golden vectors, analytical result, official example, independent implementation, or measurement dataset.
- **Allowed claims**: what the GUI and reports may state.
- **Forbidden claims**: compliance, hardware accuracy, BER guarantee, or “best preset” unless separately proven.
- **Stop condition**: what happens when the required source or validation data is unavailable.

### 2.2 Minimum evidence rule

An Implementation may proceed only when at least one authoritative source and one independent validation method exist.

A production function must not be used to dynamically generate its own expected values.

If only conceptual sources are available, the feature must be labeled as a teaching approximation and validated using analytical or synthetic cases.

If neither a mathematical definition nor a validation oracle is available, the feature remains **Blocked** and must not be implemented by guessing.

---

## 3. Phase-by-phase feasibility audit

## Phase 0 — Baseline Freeze

**Decision: Completed and feasible.**

Evidence already exists in repository regression tests, GUI behavior baselines, preset-resolution golden data, and CI.

No roadmap change required.

---

## Phase 1 — Core Refactor

**Decision: Completed and feasible.**

This phase is an architecture refactor and does not depend on unavailable PCIe electrical data. Existing module-boundary tests and 182-test regression baseline provide the validation oracle.

No roadmap change required.

---

## Phase 2 — Channel Foundation

**Decision: Feasible, but each sub-step requires explicit numerical conventions.**

### PRBS Core

PRBS7, PRBS9, PRBS15, PRBS23, and PRBS31 are implementable from published polynomial definitions. AMD and Tektronix publish the same polynomial set and sequence lengths:

- PRBS7: `1 + x^6 + x^7`
- PRBS9: `1 + x^5 + x^9`
- PRBS15: `1 + x^14 + x^15`
- PRBS23: `1 + x^18 + x^23`
- PRBS31: `1 + x^28 + x^31`

However, a polynomial alone does not determine a bit-exact sequence. Implementation 23 must additionally lock:

- Fibonacci or Galois LFSR.
- left or right shift.
- MSB or LSB output.
- feedback timing.
- state bit ordering.
- inversion convention.
- first output bit.

**Decision for Implementation 23: Approved after the Issue cites its source and fixes the complete LFSR convention.**

### Channel interface and impulse convolution

Discrete convolution is a standard, directly testable operation and is supported by established numerical libraries. This work is feasible using hardcoded impulse and waveform golden cases.

The implementation must define:

- full, same, or valid convolution mode.
- sample interval compatibility.
- output length.
- time-zero and main-cursor alignment.
- normalization policy.
- truncation and padding.

### Touchstone and S-parameters

Touchstone is an official IBIS Open Forum format; Touchstone 2.1 is current. Parsing `.s2p` is feasible using the official format or a maintained library such as scikit-rf.

Converting S-parameters to an impulse response is conditional on explicit preprocessing. scikit-rf documents that accurate time-domain transformation requires uniform frequency spacing and, for low-pass transformation, frequency data beginning at 0 Hz; measured data may need interpolation and DC extrapolation.

`.s4p` mixed-mode and `SDD21` are feasible only after port ordering, reference impedance, wave definition, and differential conversion conventions are fixed and validated with known files.

### Phase 2 status

- PRBS: **Feasible now**.
- Numeric impulse and convolution: **Feasible now**.
- `.s2p`: **Feasible with documented parser and transform contracts**.
- `.s4p` / mixed-mode: **Conditional; requires validated port-order examples**.

---

## Phase 3 — NRZ Sampling & RXEQ

**Decision: Feasible as a generic teaching receiver; PCIe-accurate claims are conditional.**

Sampling phase, slicers, CTLE, FFE, DFE, and simple CDR algorithms are implementable and analytically testable. The current code already contains simplified CTLE and symbol-rate DFE building blocks.

The missing evidence is not whether these algorithms exist, but whether a selected topology and parameter set represents a specific PCIe generation. Exact receiver implementation and adaptation behavior cannot be inferred from the current GUI or from generic DSP equations.

Before Phase 3 starts, the project must choose one of two paths:

### Path A — Teaching receiver

- Use published generic DSP equations.
- Label all outputs as teaching-model results.
- Validate with synthetic channels whose expected cursor cancellation is known.
- Do not claim PCIe receiver tolerance or compliance.

### Path B — PCIe reference receiver

- Obtain the applicable PCIe Base/PHY Test specification or an official published reference-receiver methodology.
- Record the exact revision.
- Implement only the parameters and procedures supported by that source.
- Validate against official examples, reference code, or approved test vectors.

Public PCI-SIG material shows that receiver architecture changes by generation; for example, public PCIe 7.0 material describes an enhanced CTLE, 29-tap Rx FFE, and 1-tap DFE, while PCIe 6.0 used a different receiver structure. This confirms that one generic receiver cannot be silently treated as valid for every PCIe generation.

### Phase 3 status

- Generic NRZ receiver teaching model: **Feasible**.
- PCIe Gen-specific receiver model: **Conditional on specification/reference data**.
- Compliance receiver: **Out of scope without licensed specifications and independent correlation**.

---

## Phase 4 — PAM4 RXEQ

**Decision: Feasible as a generic PAM4 teaching receiver; PCIe-specific adaptation is conditional.**

IBIS-AMI officially supports PAM4/PAMn modeling, receiver thresholds, time-domain processing, and statistical optimization concepts. This provides a legitimate data basis for a generic PAM4 receiver architecture.

Feasible teaching components include:

- AGC/VGA.
- CTLE and FFE.
- common sampling phase.
- three slicer thresholds.
- symbol decisions and deterministic SER.
- simple DFE.

The following cannot be guessed:

- PCIe Gen6/7 exact receiver adaptation.
- reference receiver tap constraints.
- threshold-training procedure.
- precoding/Gray-coding interaction beyond documented rules.
- stressed-eye tolerance or compliance pass/fail.

### Phase 4 status

- Generic PAM4 receiver teaching model: **Feasible**.
- PCIe-specific PAM4 reference receiver: **Conditional on specification/reference model**.
- Compliance SER/receiver tolerance: **Not authorized from current public data alone**.

---

## Phase 5 — Signal Impairments & Statistical Metrics

**Decision: Split into a feasible deterministic part and a conditional statistical part.**

### Deterministic and seeded impairments

The following are feasible when equations and seeds are explicit:

- AWGN / vertical noise.
- sinusoidal and deterministic jitter.
- bounded random-jitter teaching model.
- frequency/phase offset.
- simplified interference/crosstalk waveform injection.
- eye-density accumulation.

These can be validated against analytical distributions and fixed-seed golden vectors.

### Eye width, bathtub, BER, and SER estimates

These are feasible only after the sampling, threshold, and decision contracts are stable.

A brute-force simulation cannot practically establish very low BER values. For example, observing roughly one error at BER `1e-12` requires on the order of `1e12` bits. Therefore the product must either:

- report only empirical error rate with sample count and confidence limits, or
- implement a documented statistical/analytical method and validate it against known synthetic cases or an independent simulator.

PCIe 6.0/7.0 public material confirms that PAM4 uses FEC and that link reliability is evaluated using first-bit error rate, FEC, CRC, and replay behavior. The current simulator does not model this complete chain, so its raw SER or BER must not be presented as PCIe link BER.

### Phase 5 status

- Deterministic/seeded impairments: **Feasible**.
- Empirical eye density and error rate: **Feasible with sample-count reporting**.
- Statistical bathtub and BER estimate: **Conditional on a documented method and validation oracle**.
- PCIe post-FEC reliability: **Blocked until FEC/link definitions and validation data are available**.

---

## Phase 6 — Reproducibility & Experiment Infrastructure

**Decision: Fully feasible and should remain a required dependency before sweeps.**

This is a software/data-contract phase. It does not require hidden PCIe electrical parameters.

Required evidence is internal and testable:

- schema examples.
- round-trip serialization tests.
- migration tests.
- deterministic run IDs and resolved configuration.
- artifact references.
- CSV/JSON/Markdown golden outputs.

Each earlier phase must already expose versionable configuration contracts, but the complete experiment infrastructure may remain here.

---

## Phase 7 — Sweep & Auto Equalization

**Decision: Computationally feasible, but conclusions are limited to the simulator objective.**

Grid search, coordinate descent, heatmaps, and parameter sweeps are normal numerical workflows. They become meaningful only after:

- deterministic Scenario/Experiment inputs exist.
- objective metrics are stable.
- invalid/unstable results are represented explicitly.
- progress and cancellation contracts exist.

The result may be called:

- highest simulated metric.
- best result inside this configured sweep.
- teaching-model comparison.

It must not be called a real-hardware optimum, PCI-SIG recommendation, or compliance result without measurement correlation.

Decision-directed adaptation is research work and must be separated from deterministic sweep delivery.

### Phase 7 status

- deterministic sweeps and heatmaps: **Feasible after Phases 5 and 6**.
- numerical optimization of simulator objective: **Feasible with limitations**.
- hardware-optimal equalization: **Not supported without measurement correlation**.
- decision-directed adaptation: **Research-only until separately validated**.

---

## Phase 8 — Measurement Integration

**Decision: Partially feasible; start with generic documented formats.**

### Generic CSV

Generic time/voltage CSV is feasible. Keysight publicly documents XY CSV files containing headers, time units, voltage units, and data points. Similar text export is available from other oscilloscopes.

The first implementation should support a project-owned canonical CSV contract and adapters for clearly documented CSV variants.

### Native vendor formats

Tektronix publishes a reference WFM format for specific instrument families, so an adapter is technically feasible for those documented versions. It must not be described as supporting every Tektronix instrument.

Keysight native formats vary by product and format version. Adapters are conditional on public documentation, SDK access, or user-provided sample files.

### Alignment and tap extraction

Waveform alignment and pulse/cursor comparison are feasible when sample rate, UI, polarity, reference pattern, and alignment objective are known.

Tap extraction is an inverse problem. It is feasible only with:

- a known transmitted pattern or step response.
- an explicit FIR/model order.
- fitting constraints.
- residual and fit-quality reporting.
- synthetic and measured validation datasets.

PCI-SIG publishes fitting-based transmitter preset measurement methodology, which can be used as a source only if the applicable document is accessible and its revision is recorded.

### Phase 8 status

- canonical CSV import: **Feasible**.
- documented vendor CSV adapters: **Feasible per documented format**.
- native binary adapters: **Conditional by instrument family and documentation**.
- measured-vs-simulated alignment: **Feasible with explicit metadata**.
- tap extraction: **Conditional on reference data and fitting methodology**.

---

## Phase 9 — Product Usability & Release

**Decision: Feasible.**

Scenario UX, reports, guides, error handling, progress/cancel behavior, and release documentation are standard software engineering work.

Release readiness still depends on model labels and limitation disclosures being complete. Packaging and antivirus behavior remain separate product decisions.

---

## Phase 10 — Advanced Research

**Decision: Do not treat this as a committed implementation phase. Convert it to a research backlog.**

The items have very different evidence and feasibility requirements:

- Retimer/multi-segment teaching model: feasible after Channel and Receiver contracts.
- package/connector/via models: conditional on S-parameters, IBIS/IBIS-ISS, or validated equivalent circuits.
- crosstalk matrix: conditional on multiport data or an explicitly synthetic model.
- Gen6 FEC and pre/post-FEC views: conditional on exact code/interleaving definitions and validation vectors.
- PCIe Gen7 profile: conditional on PCIe 7.0 specification access and reference-receiver data; PCIe 7.0 Revision 7.0 was released in June 2025, but release existence does not provide all implementation details needed by this simulator.
- Batch CLI and public Python API: feasible.
- plugin architecture: feasible but should follow API stabilization.
- hardware automation: conditional on instrument SDKs, licenses, and available hardware.

Every Advanced Research item must receive its own feasibility review before it becomes a numbered Implementation.

---

## 4. Required roadmap changes

The Product Roadmap should be updated with these governance rules:

1. Add the Evidence Gate before every Implementation.
2. Add claim-level labels: spec-derived, reference-derived, teaching approximation, research.
3. Mark Phase 3 and Phase 4 PCIe-specific behavior as conditional on specification/reference data.
4. Split Phase 5 deterministic impairments from statistical BER/bathtub authorization.
5. Restrict Phase 8 native waveform support by documented instrument family and format version.
6. Move Phase 10 from committed “Planned” work to an uncommitted Research Backlog.
7. Require a source registry and validation oracle in every Issue and PR.
8. Block implementation when data is unavailable instead of filling gaps with assumptions.

---

## 5. Immediate development decision

Implementation 23 may proceed because published PRBS polynomial definitions and independent vendor references exist.

Before coding, its Issue must be updated to include:

- selected authoritative source.
- exact polynomial table.
- complete LFSR convention.
- independent golden prefixes.
- period/recurrence validation plan.
- explicit statement that PRBS is a general test-pattern implementation and is not automatically a PCIe compliance pattern.

No Phase 3 or later PCIe-specific model is authorized until its Evidence Gate is completed.

---

## 6. Reference registry

### PCI-SIG

- PCI Express Base specification overview and approved revisions: https://pcisig.com/specification-overview/pci-express-base
- PCI Express Base Specification Revision 7.0: https://pcisig.com/PCIExpress/Spec/Base/_7.0
- PCIe 6.0 PAM4 overview: https://pcisig.com/blog/pcie%C2%AE-60-specification-webinar-qa-impact-pam4-signaling
- PCIe 6.0 supported features and FEC: https://pcisig.com/blog/pcie%C2%AE-60-specification-webinar-qa-supported-features-pcie-60-specification
- PCIe 7.0 webinar Q&A and receiver architecture discussion: https://pcisig.com/blog/pcie-70-specification-next-generation-performance-meet-needs-advanced-ai-applications-webinar
- PCI-SIG Compliance Program: https://pcisig.com/developers/compliance-program
- Fitting-based Tx Preset Measurement Methodology: https://pcisig.com/PCI%20Express/ECN/Base/Fitting-basedTxPresetMeasurementMethodologyfor8.0_16.0_and32.0GTs

### PRBS

- AMD Versal GTM Transceivers — TX Pattern Generator: https://docs.amd.com/r/en-US/am017-versal-gtm-transceivers/TX-Pattern-Generator
- Tektronix PatternPro PRBS polynomial table: https://www.tek.com/en/datasheet/ppg4001-patternpro%C2%AE-programmable-pattern-generator-datasheet
- ITU-T Recommendation O.150: https://www.itu.int/rec/T-REC-O.150

### IBIS / Touchstone / AMI

- IBIS Open Forum and current specifications: https://ibis.org/
- IBIS specification history and PAM4/PAMn support: https://ibis.org/about/
- IBIS BIRD registry: https://ibis.org/birds/
- scikit-rf Touchstone parser: https://scikit-rf.readthedocs.io/en/latest/api/io/generated/skrf.io.touchstone.Touchstone.__init__.html
- scikit-rf impulse-response transformation requirements: https://scikit-rf.readthedocs.io/en/latest/api/generated/skrf.network.Network.impulse_response.html

### Numerical processing

- SciPy convolution: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.convolve.html
- SciPy FFT convolution: https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.fftconvolve.html

### Measurement formats

- Keysight XY waveform CSV format: https://helpfiles.keysight.com/csg/d9300a/Help/Infiniium-UG/Content/Topics/Files/waveform_xy_files.htm
- Tektronix reference WFM format: https://download.tek.com/manual/001137803web_0.pdf
