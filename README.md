# PCIe TX EQ Simulator

PCIe TX EQ Preshoot / De-emphasis visualization tool for exploring how TX EQ settings affect waveform and eye diagram shape.

This tool is intended for learning and visualization. It is not a PCIe compliance tool.

## Run

```powershell
python PCIETXEQ5.py
```

## Requirements

- numpy
- PyQt5
- pyqtgraph

Install dependencies with:

```powershell
pip install -r requirements.txt
```

## Model Notes

- dB mode uses a level-based visualization model.
- Tap mode uses an FIR coefficient reference model.
- dB mode and tap mode are not guaranteed to produce identical output because they are used for different reference views.
- The C-1 / C0 / C+1 values shown in dB mode are synchronized reference values, not a replacement for the dB visualization model.

## Presets

Preset values are approximate and for visualization only. This simulator is not a PCIe compliance preset coefficient calculator.

## Channel

Low-pass Alpha is a simplified ISI model. It is not a real PCIe channel model.

## Limitations

- This tool is not a PCIe compliance tool.
- Eye height is approximate visualization only.
- Density eye mode is not implemented.
