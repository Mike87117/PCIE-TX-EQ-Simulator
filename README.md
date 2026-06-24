# PCIe TX EQ Simulator

PCIe TX EQ teaching / visualization simulator for exploring how transmitter equalization changes waveform and eye diagram shape.

This project is for learning concepts, not for compliance testing, preset coefficient checking, or formal PCIe specification calculation.

## Views

- PCIe Gen1~5 NRZ TX EQ
- PCIe Gen6 PAM4 TX EQ

## Run

```powershell
python PCIETXEQ5.py
```

## How to Use

1. Start with the Gen1~5 NRZ tab.
2. Click Reset to No EQ to observe the baseline waveform.
3. Adjust Preshoot and De-emphasis to see how the waveform and eye diagram change.
4. Switch to the Gen6 PAM4 tab.
5. Try Q0 first, then Q2 / Q4 / Q6 / Q9 to compare different 4-tap FIR effects.
6. Observe the PAM4 waveform and Upper / Middle / Lower eye openings.
7. Adjust Low-pass Alpha to see the simplified ISI impact.

## Recommended Teaching Flow

1. No EQ baseline
2. De-emphasis only
3. Preshoot only
4. Mixed Preshoot + De-emphasis
5. PAM4 level introduction
6. Gen6 4-tap FIR comparison
7. Eye diagram comparison

## Requirements

- numpy
- PyQt5
- pyqtgraph

Install dependencies with:

```powershell
pip install -r requirements.txt
```

## Build Windows EXE

This project uses PyInstaller onedir mode for the Windows executable.
Onedir is usually a better fit for PyQt GUI apps than onefile because it starts faster, is easier to inspect, and avoids onefile self-extraction overhead.

For the smallest practical build, use a clean virtual environment so PyInstaller does not discover unrelated packages from a larger Python environment.

```powershell
python -m venv .venv
.venv\Scripts\activate
build_exe.bat
```

The build script will:

1. Upgrade pip.
2. Install runtime dependencies from `requirements.txt`.
3. Install PyInstaller as a build dependency.
4. Remove old `build` / `dist` folders.
5. Run `python -m PyInstaller PCIETXEQ5.spec`.

Build output:

```powershell
dist\PCIe_TX_EQ_Simulator\PCIe_TX_EQ_Simulator.exe
```

Run the EXE and check:

- Gen1~5 NRZ tab displays normally.
- Gen6 PAM4 tab displays normally.
- Presets can be selected.
- Sliders update waveform and eye diagram.
- No black console window appears.

Onefile builds are not used here because they may be larger and can start more slowly for PyQt applications.

## Gen1~5 NRZ Teaching Notes

The Gen1~5 tab visualizes classic NRZ TX EQ concepts:

- Preshoot raises the last bit before a transition.
- De-emphasis lowers repeated bits after a transition.
- dB mode uses a level-based visualization model.
- Tap mode uses an FIR coefficient reference model.
- Presets 0~10 are approximate visualization settings.

dB mode and tap mode are intentionally separate views. They are useful for comparing concepts, but they are not guaranteed to produce identical waveforms.

## Gen6 PAM4 Teaching Notes

The Gen6 tab visualizes simplified PAM4 TX EQ concepts:

- PAM4 uses four normalized levels.
- PAM4 has Upper, Middle, and Lower eye openings.
- The tab uses a simplified 4-tap TX FIR visualization model.
- The displayed taps are C-2 / C-1 / C0 / C+1.
- C0 is calculated automatically from C-2, C-1, and C+1.
- The Q0~Q10 selector is for visualization.
- Q10 is special / Note 2 and is not explicitly modeled; selecting Q10 resets coefficients to Q0 for visualization safety.
- Raw Eye shows fixed 2 UI slicing.
- Raw Eye is useful for observing raw eye folding.
- Common t_center Eye estimates one shared PAM4 sampling phase.
- Common t_center Eye scans one UI of sampling phase.
- Common t_center Eye selects one shared t_center phase that maximizes the minimum Upper / Middle / Lower eye opening.
- Common t_center Eye re-slices the 2 UI eye around that shared t_center.
- The common t_center is shared by Upper, Middle, and Lower eyes.
- The simulator does not independently align the three PAM4 eyes.
- The simulator does not perform per-trace x_shift or per-eye shifting.
- It does not model full oscilloscope CDR, SER contour, TDECQ, or compliance-grade measurement.
- The goal is a simplified visual approximation, not a formal measurement.
- Upper / Middle / Lower eye metrics are approximate visualization values.

The Gen6 PAM4 control path is separate from the Gen1~5 NRZ control path.

## Channel

Low-pass Alpha is a simplified ISI demonstration. It is not a real PCIe channel model.

## Limitations

- This is not a PCIe compliance tool.
- Preset values are approximate and for visualization only.
- Eye metrics are approximate visualization values.
- Raw Eye uses fixed 2 UI slicing, while Common t_center Eye uses a shared common t_center phase.
- PAM4 eye visualization here is simplified and does not model full oscilloscope alignment or compliance-grade measurement.
- The channel model is simplified.
- Density eye mode is not implemented.
