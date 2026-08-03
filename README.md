# PCIe TX/RX EQ Teaching Simulator

`PCIe TX/RX EQ Teaching Simulator` is an educational tool designed for exploring and visualizing how transmitter equalization (TX EQ), low-pass channel loss, continuous-time linear equalization (CTLE), decision feedback equalization (DFE), and PAM4 modulation change waveform shapes and eye diagram quality.

This project is for learning core concepts, not for compliance testing, preset coefficient checking, or formal PCIe specification verification.

---

## Key Features

- **PCIe Gen1~5 NRZ TX EQ**: Visualization of Preshoot, De-emphasis, Boost dB, and tap coefficients (`C-1 / C0 / C+1`) with Presets 0~10.
- **Simplified Lossy Channel**: First-order low-pass filter model for observing inter-symbol interference (ISI).
- **NRZ CTLE**: High-frequency boost visualization model for continuous-time linear equalization.
- **NRZ 3-Tap Manual DFE**: Symbol-rate decision feedback equalizer for post-cursor ISI cancellation.
- **PCIe Gen6 PAM4 TX EQ**: 4-tap FIR equalization (`C-2 / C-1 / C0 / C+1`) with Presets Q0~Q9.
- **PAM4 Raw Eye & Common `t_center` Eye**: Real-time 2 UI raw eye folding and common sampling phase alignment.
- **Eye & Margin Metrics**: Approximate visual estimations for eye height, eye width, and DFE decision margins.

---

## Quick Start

### Installation

Install runtime dependencies:

```powershell
pip install -r requirements.txt
```

Run the application:

```powershell
python main.py
```

---

## Development & Automated Tests

To install development and testing dependencies:

```powershell
pip install -r requirements-dev.txt
```

Run automated baseline test suite:

```powershell
python -m pytest
```

See [docs/BASELINE_SMOKE_TEST.md](file:///c:/Users/mikezeng/Desktop/Python/PCIE-TX-EQ-Simulator/docs/BASELINE_SMOKE_TEST.md) for the manual GUI smoke test checklist and verification results.

---

## Recommended Teaching Flow

1. **No EQ Baseline**: Observe un-equalized NRZ pulse sequence through lossy channel.
2. **De-emphasis & Preshoot**: Observe how De-emphasis lowers repeated bits and Preshoot raises pre-transition bits.
3. **CTLE High-Frequency Boost**: Apply CTLE to restore high-frequency signal energy before sampling.
4. **Manual 3-Tap DFE**: Adjust DFE taps to cancel post-cursor ISI at symbol sampling points.
5. **PAM4 Levels & Presets**: Switch to Gen6 PAM4 tab, compare Q0~Q9 4-tap FIR settings.
6. **PAM4 Eye Diagrams**: Compare Raw 2 UI eye against Common `t_center` aligned eye.

---

## Building Windows Executable

This project provides a standalone Windows build script using PyInstaller onedir mode:

```powershell
.\build_exe.bat
```

The script will automatically create a local virtual environment (`.venv-build`), install dependencies, clean old artifacts, and compile the executable using `PCIe_TX_EQ_Simulator.spec`.

Output directory:

```powershell
dist\PCIe_TX_EQ_Simulator\PCIe_TX_EQ_Simulator.exe
```

---

## Educational Scope & Limitations

- **Not a Compliance Tool**: This software does NOT perform PCI-SIG compliance certification, SigTest, or Seasim evaluation.
- **Simplified Channel**: Channel loss is modeled using a simple first-order low-pass filter, not Touchstone S-parameter matrices or empirical loss curves.
- **Teaching CTLE & DFE Models**: CTLE is a simplified high-frequency boost model, and DFE is a manual symbol-rate model (not adaptive LMS).
- **Approximate Eye Metrics**: Eye height, width, and margin values are visual estimations.
