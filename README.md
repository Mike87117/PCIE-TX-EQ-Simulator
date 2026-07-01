# PCIe TX EQ Simulator

PCIe TX EQ Simulator is a teaching and visualization tool for exploring how transmitter equalization affects waveform shape, simplified channel response, and eye diagram behavior.

This project is intended for learning concepts and visual intuition. It is not a PCIe compliance tool, preset coefficient checker, or formal PCIe specification calculator.

## Main Views

* PCIe Gen1~5 NRZ TX EQ / RX EQ visualization
* PCIe Gen6 PAM4 TX EQ visualization

## Features

### Gen1~5 NRZ

* Measurement-like Va / Vb / Vc level model
* Direct C-1 and C+1 control
* Derived Preshoot / De-emphasis display
* Approximate Preset 0~10 selection for teaching visualization
* Simplified low-pass channel model
* Simplified CTLE and DFE visualization
* Waveform and eye diagram display

### Gen6 PAM4

* Simplified PAM4 4-level waveform visualization
* C-2 / C-1 / C0 / C+1 tap display
* Approximate Q0~Q9 preset selection for visualization
* Upper / Middle / Lower eye opening display
* Raw Eye and Common t_center Eye views

## Requirements

* Python 3.10 or newer is recommended
* numpy
* PyQt5
* pyqtgraph

Install dependencies with:

```powershell
pip install -r requirements.txt
```

If `requirements.txt` is not used, install manually:

```powershell
pip install numpy pyqt5 pyqtgraph
```

## Run from Source

```powershell
python main.py
```

## Recommended Teaching Flow

1. Start with the Gen1~5 NRZ tab.
2. Select Preset 4 or reset to the TX EQ baseline.
3. Adjust C-1 and observe how Preshoot changes.
4. Adjust C+1 and observe how De-emphasis changes.
5. Adjust Low-pass Alpha to increase or reduce the simplified channel loss.
6. Try CTLE and DFE to observe simplified RX equalization behavior.
7. Switch to the Gen6 PAM4 tab.
8. Try Q0 first, then Q2 / Q4 / Q6 / Q9 to compare simplified PAM4 TX EQ behavior.
9. Compare waveform shape and eye diagram changes.

## Gen1~5 NRZ Model Notes

The Gen1~5 NRZ tab uses a measurement-like Va / Vb / Vc level model.

* Va: first bit after transition
* Vb: repeated / de-emphasized level
* Vc: last bit before transition / preshoot level

User controls:

* C-1
* C+1
* Low-pass Alpha

Derived display values:

* Preshoot dB
* De-emphasis dB
* C0
* Eye metrics

In this simulator:

* C-1 controls Preshoot and raises Vc relative to Vb.
* C+1 controls De-emphasis and lowers Vb relative to Va.
* Preshoot dB and De-emphasis dB are derived measurement values, not direct UI controls.
* Preset values are approximate visualization settings.
* `tx_fir()` is kept as an ideal FIR reference function, but it is not the default NRZ waveform display model.

This design is intended to match the visual intuition of oscilloscope-style TX EQ behavior more closely than a purely idealized coefficient-only FIR display.

## Gen6 PAM4 Model Notes

The Gen6 PAM4 tab visualizes simplified PAM4 TX EQ concepts:

* PAM4 uses four normalized levels.
* PAM4 has Upper, Middle, and Lower eye openings.
* The tab uses a simplified 4-tap TX FIR visualization model.
* The displayed taps are C-2 / C-1 / C0 / C+1.
* C0 is calculated automatically from C-2, C-1, and C+1.
* The Q0~Q9 selector is for visualization.
* Raw Eye uses fixed 2 UI slicing.
* Common t_center Eye estimates one shared PAM4 sampling phase.
* Common t_center Eye scans one UI of sampling phase.
* Common t_center Eye selects one shared t_center phase that maximizes the minimum Upper / Middle / Lower eye opening.
* The common t_center is shared by Upper, Middle, and Lower eyes.
* The simulator does not independently align the three PAM4 eyes.
* The simulator does not perform per-trace x_shift or per-eye shifting.
* It does not model full oscilloscope CDR, SER contour, TDECQ, or compliance-grade measurement.

The Gen6 PAM4 control path is separate from the Gen1~5 NRZ control path.

## Channel and RX EQ Notes

Low-pass Alpha is a simplified ISI demonstration. It is not a real PCIe channel model.

The RX EQ section is also simplified:

* CTLE provides a visual high-frequency boost effect.
* DFE operates at symbol-rate sampling points.
* DFE is intended for teaching the concept of post-cursor ISI cancellation.
* The DFE model is not an adaptive LMS model and is not a compliance-grade RX model.

## Build Windows EXE

For PyQt5 applications, the packaged EXE or distribution folder can be large because Python runtime, Qt DLLs, numpy, and pyqtgraph dependencies are included.

A clean virtual environment is recommended before packaging.

### Create a clean virtual environment

```powershell
py -3.11 -m venv build_env
build_env\Scripts\activate
python -m pip install --upgrade pip
pip install numpy pyqt5 pyqtgraph pyinstaller
```

### Recommended onedir build

Use `onedir` first because it is usually more stable and easier to debug than `onefile`.

```powershell
pyinstaller --clean --noconfirm --windowed --onedir `
  --name PCIe_TX_EQ_Simulator `
  --exclude-module matplotlib `
  --exclude-module pandas `
  --exclude-module scipy `
  --exclude-module sklearn `
  --exclude-module IPython `
  --exclude-module notebook `
  --exclude-module tkinter `
  main.py
```

The output will be created under:

```text
dist\PCIe_TX_EQ_Simulator\
```

Run:

```powershell
dist\PCIe_TX_EQ_Simulator\PCIe_TX_EQ_Simulator.exe
```

### Optional onefile build

Use `onefile` only after the `onedir` build works correctly.

```powershell
pyinstaller --clean --noconfirm --windowed --onefile `
  --name PCIe_TX_EQ_Simulator `
  --exclude-module matplotlib `
  --exclude-module pandas `
  --exclude-module scipy `
  --exclude-module sklearn `
  --exclude-module IPython `
  --exclude-module notebook `
  --exclude-module tkinter `
  main.py
```

Onefile builds may still be large and may start more slowly because the application is extracted before running.

## EXE Build Checklist

After packaging, check the following:

* Gen1~5 NRZ tab opens normally.
* Gen6 PAM4 tab opens normally.
* Presets can be selected.
* C-1 and C+1 sliders update the waveform and derived Pre/De values.
* Low-pass Alpha updates the simplified channel response.
* CTLE and DFE controls update the RX view.
* Waveform and eye diagram update correctly.
* Detail button opens correctly.
* No black console window appears when using `--windowed`.

## Limitations

* This is not a PCIe compliance tool.
* Preset values are approximate and for visualization only.
* Eye metrics are approximate visualization values.
* The channel model is simplified.
* The CTLE and DFE models are simplified teaching models.
* Gen6 PAM4 eye visualization is simplified and does not model full oscilloscope alignment or compliance-grade measurement.
* Raw Eye uses fixed 2 UI slicing, while Common t_center Eye uses a shared common t_center phase.
* Density eye mode is not implemented.

## Recommended Use

Use this simulator to build intuition about TX EQ concepts, waveform shape, simplified ISI impact, and eye diagram behavior before moving to formal PCIe specifications or compliance tools.
