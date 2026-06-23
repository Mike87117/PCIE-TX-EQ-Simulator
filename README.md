# PCIe TX EQ Simulator

PCIe TX EQ Preshoot / De-emphasis visualization tool for exploring how TX EQ settings affect waveform and eye diagram shape.

This tool is intended for learning and visualization. It is not a PCIe compliance tool.

## Views

- PCIe Gen1~5 NRZ TX EQ: NRZ Preshoot / De-emphasis visualization, preserving the original dB and tap mode behavior.
- PCIe Gen6 PAM4 TX EQ: simplified 4-tap PAM4 TX FIR waveform and eye visualization with an independent PAM4 control path.

## Run

```powershell
python PCIETXEQ5.py
```

## Gen6 Preset Validation

```powershell
python PCIETXEQ5.py --validate-gen6
```

This command prints the Q0~Q9 Gen6 preset validation table and does not launch the GUI.

The table shows:

- C-2 / C-1 / C0 / C+1
- Va/Vd, Vb/Vd, Vc1/Vd, Vc2/Vd
- Preshoot 1, Preshoot 2, De-emphasis, Boost

Q10 is special / Note 2 and is not explicitly modeled. Selecting Q10 in the GUI resets coefficients to Q0 for visualization safety.

## Requirements

- numpy
- PyQt5
- pyqtgraph

Install dependencies with:

```powershell
pip install -r requirements.txt
```

## Gen1~5 NRZ Model Notes

- dB mode uses a level-based visualization model.
- Tap mode uses an FIR coefficient reference model.
- dB mode and tap mode are not guaranteed to produce identical output because they are used for different reference views.
- The C-1 / C0 / C+1 values shown in dB mode are synchronized reference values, not a replacement for the dB visualization model.

## Gen6 PAM4 Model Notes

- The Gen6 PAM4 tab uses a simplified 4-tap TX FIR visualization model.
- The displayed coefficients are C-2 / C-1 / C0 / C+1.
- C0 is calculated automatically from the other taps.
- The Gen6 preset selector includes Q0 through Q10.
- The Gen6 tab includes Q0~Q9 coefficient presets.
- Q10 is special / Note 2 and is not explicitly modeled.
- Selecting Q10 resets coefficients to Q0 for visualization safety.
- The Gen6 info panel shows Va/Vd, Vb/Vd, Vc1/Vd, and Vc2/Vd for comparison with preset ratio tables.
- `python PCIETXEQ5.py --validate-gen6` can be used to print a preset validation table without launching the GUI.
- PAM4 eye openings are approximate visualization values only.
- The Gen6 PAM4 tab is intentionally separate from the NRZ TX EQ control flow.

## Presets

Preset values are approximate and for visualization only. This simulator is not a PCIe compliance preset coefficient calculator.

## Channel

Low-pass Alpha is a simplified ISI model. It is not a real PCIe channel model.

## Limitations

- This tool is not a PCIe compliance tool.
- Eye height is approximate visualization only.
- Density eye mode is not implemented.
