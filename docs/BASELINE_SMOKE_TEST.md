# Baseline GUI Smoke Test Checklist

This document tracks the baseline GUI smoke test results for `PCIE-TX-EQ-Simulator` prior to any code refactoring.

## Environment Summary

- **OS**: Windows (x64)
- **Python Version**: Python 3.12.10
- **PyQt5 Version**: 5.15.11
- **PyQtGraph Version**: 0.14.0

---

## Smoke Test Items

| # | Feature / Test Step | Expected Result | Status | Notes / Reason |
|---|----------------------|-----------------|--------|----------------|
| 1 | `python main.py` launch | GUI window launches without crash or error | Passed | Verified program startup |
| 2 | NRZ tab display | PCIe Gen1~5 NRZ tab renders controls and plots | Passed | Controls & PyQtGraph display correctly |
| 3 | PAM4 tab display | PCIe Gen6 PAM4 tab renders controls and plots | Passed | Controls & PyQtGraph display correctly |
| 4 | P0~P10 switching | Selecting P0~P10 updates sliders and waveform | Passed | Verified preset selection updates UI |
| 5 | Q0~Q9 switching | Selecting Q0~Q9 updates PAM4 taps and plots | Passed | Verified Q0~Q9 tap loading |
| 6 | Slider & line edit sync | Moving slider updates QLineEdit and vice versa | Passed | Bidirectional sync operational |
| 7 | Generate New Waveform | Regenerates bit/symbol pattern and updates plots | Passed | Triggers new random sequence |
| 8 | Reset TX EQ | Resets TX EQ controls to No EQ baseline | Passed | Resets taps and dB controls |
| 9 | Reset Channel | Resets Low-pass Alpha to default (0.08) | Passed | Resets channel parameter |
| 10 | Reset RX EQ | Resets CTLE gain and DFE taps to 0 | Passed | Resets RX parameters |
| 11 | Reset All | Resets all parameters to initial state | Passed | Resets TX, Channel, RX, PAM4 |
| 12 | Channel view | Displays lossy channel waveform | Passed | Waveform updates with alpha |
| 13 | CTLE view | Displays CTLE equalized waveform | Passed | Waveform updates with boost gain |
| 14 | DFE Sample Margin view | Displays DFE decision margin and metrics | Passed | Margin plot and stats display correctly |
| 15 | PAM4 Raw Eye | Displays 2 UI folded PAM4 raw eye diagram | Passed | Raw eye traces update in real time |
| 16 | PAM4 Common `t_center` Eye | Displays aligned PAM4 eye diagram around t_center | Passed | Re-sliced eye traces render correctly |
| 17 | Detail dialog | Clicking Detail opens numerical details window | Passed | Opens detail dialog without errors |

---

## Known Baseline Limitations

1. `main.py` monolithic structure: all GUI components, simulation logic, and plotting are tightly coupled in a single file.
2. CTLE & DFE models are educational approximations (symbol-rate DFE, single-stage simplified CTLE), not adaptive LMS or compliance models.
3. Channel is a first-order IIR low-pass filter, not a Touchstone / S-parameter model.
4. `simple_channel` does not validate empty array or illegal alpha parameters (raises `IndexError` on empty array).
5. NRZ sampling phase is fixed without a clock data recovery (CDR) loop.
