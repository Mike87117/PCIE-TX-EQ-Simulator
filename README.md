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

The Gen6 PAM4 control path is separate from the Gen1~5 NRZ control path.

## Channel

Low-pass Alpha is a simplified ISI demonstration. It is not a real PCIe channel model.

## Limitations

- This is not a PCIe compliance tool.
- Preset values are approximate and for visualization only.
- Eye metrics are approximate visualization values.
- The channel model is simplified.
- Density eye mode is not implemented.
