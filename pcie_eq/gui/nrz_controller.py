"""
NRZ Controller Mixin for PCIe TX/RX EQ Simulator.

Contains NRZ-specific UI synchronization, handlers, simulation orchestration,
plotting, and status rendering methods.
"""

import numpy as np
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt
import pyqtgraph as pg

from pcie_eq.tx_eq import (
    PCIE_PRESET_DB_TABLE,
    db_to_taps,
    calc_levels,
)
from pcie_eq.metrics import calculate_eye_metrics
from pcie_eq.models import NrzSimulationConfig
from pcie_eq.pipeline import run_simulation
from pcie_eq.patterns import generate_random_nrz_bits, nrz_bits_to_symbols
from pcie_eq.gui.constants import (
    BIT_COUNT,
    SPB,
    PLOT_BITS,
    EYE_UI,
    MAX_EYE_TRACES,
    REALTIME_EYE_TRACES,
    REALTIME_EYE_INTERVAL_MS,
)

__all__ = ["NrzControllerMixin"]


class NrzControllerMixin:
    """
    Mixin providing NRZ tab UI synchronization, handlers, simulation pipeline
    orchestration, plotting, and info panel rendering for PCIeTxEqSimulator.
    """

    def set_preset_combo_silent(self, text):
        self.preset_combo.blockSignals(True)
        try:
            idx = self.preset_combo.findText(text)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
        finally:
            self.preset_combo.blockSignals(False)

    def sync_ui_from_state(self, update_edits=True):
        self.set_slider_value_silent(self.slider_cm1["slider"], int(self.cm1_current * 1000))
        self.set_slider_value_silent(self.slider_cp1["slider"], int(self.cp1_current * 1000))
        self.set_slider_value_silent(self.slider_alpha["slider"], int(self.channel_alpha_current * 1000))
        self.set_preset_combo_silent(self.current_preset)

        # RX UI Sync
        self.set_slider_value_silent(self.slider_ctle["slider"], int(self.ctle_boost_current * 1000))
        self.set_slider_value_silent(self.slider_dfe1["slider"], int(self.dfe_tap1_current * 1000))
        self.set_slider_value_silent(self.slider_dfe2["slider"], int(self.dfe_tap2_current * 1000))
        self.set_slider_value_silent(self.slider_dfe3["slider"], int(self.dfe_tap3_current * 1000))
        self.rx_view_combo.blockSignals(True)
        idx = self.rx_view_combo.findText(self.rx_view_mode)
        if idx >= 0:
            self.rx_view_combo.setCurrentIndex(idx)
        self.rx_view_combo.blockSignals(False)

        if not update_edits:
            return

        edit_rows = [
            (self.slider_cm1["edit"], f"{self.cm1_current:.4f}"),
            (self.slider_cp1["edit"], f"{self.cp1_current:.4f}"),
            (self.slider_alpha["edit"], f"{self.channel_alpha_current:.3f}"),
            (self.slider_ctle["edit"], f"{self.ctle_boost_current:.3f}"),
            (self.slider_dfe1["edit"], f"{self.dfe_tap1_current:.3f}"),
            (self.slider_dfe2["edit"], f"{self.dfe_tap2_current:.3f}"),
            (self.slider_dfe3["edit"], f"{self.dfe_tap3_current:.3f}"),
        ]
        for edit, text in edit_rows:
            if not edit.hasFocus():
                self.set_edit_text_silent(edit, text)

    def enforce_tap_constraint(self, cm1, cp1):
        cm1 = float(np.clip(-abs(cm1), -0.3, 0.0))
        cp1 = float(np.clip(-abs(cp1), -0.3, 0.0))
        if abs(cm1) + abs(cp1) >= 0.49:
            scale = 0.49 / (abs(cm1) + abs(cp1))
            cm1 *= scale
            cp1 *= scale
        return cm1, cp1

    def set_custom_preset(self):
        self.current_preset = "Custom"

    def apply_preset(self, preset_id):
        pre_db, de_db = PCIE_PRESET_DB_TABLE[preset_id]

        requested_pre_db = float(np.clip(pre_db, 0.0, 6.0))
        requested_de_db = float(np.clip(de_db, -12.0, 0.0))

        self.cm1_current, self.cp1_current = db_to_taps(
            requested_pre_db,
            requested_de_db
        )

        _, _, _, _, actual_pre_db, actual_de_db = calc_levels(
            self.cm1_current,
            self.cp1_current
        )

        self.pre_db_current = float(np.clip(actual_pre_db, 0.0, 6.0))
        self.de_db_current = float(np.clip(actual_de_db, -12.0, 0.0))

        self.control_mode = "preset"
        self.current_preset = f"Preset {preset_id}"

    def on_preset_change(self, _index):
        if self.syncing_ui:
            return

        text = self.preset_combo.currentText()
        with self.ui_sync() as active:
            if not active:
                return
            if text == "Custom":
                self.current_preset = "Custom"
                self.sync_ui_from_state(update_edits=True)
                self.redraw_all()
                return
            if text.startswith("Preset "):
                preset_id = int(text.split()[-1])
                self.apply_preset(preset_id)
                self.sync_ui_from_state(update_edits=True)
                self.redraw_all()

    def on_edit_change(self, target):
        if self.syncing_ui:
            return

        with self.ui_sync() as active:
            if not active:
                return
            try:
                if target == "cm1":
                    self.control_mode = "tap"
                    self.set_custom_preset()
                    cm1 = float(self.slider_cm1["edit"].text())
                    self.cm1_current, self.cp1_current = self.enforce_tap_constraint(
                        cm1, self.cp1_current
                    )
                    _, _, _, _, pre_db, de_db = calc_levels(self.cm1_current, self.cp1_current)
                    self.pre_db_current = float(np.clip(pre_db, 0.0, 6.0))
                    self.de_db_current = float(np.clip(de_db, -12.0, 0.0))
                elif target == "cp1":
                    self.control_mode = "tap"
                    self.set_custom_preset()
                    cp1 = float(self.slider_cp1["edit"].text())
                    self.cm1_current, self.cp1_current = self.enforce_tap_constraint(
                        self.cm1_current, cp1
                    )
                    _, _, _, _, pre_db, de_db = calc_levels(self.cm1_current, self.cp1_current)
                    self.pre_db_current = float(np.clip(pre_db, 0.0, 6.0))
                    self.de_db_current = float(np.clip(de_db, -12.0, 0.0))
                elif target == "alpha":
                    alpha = float(self.slider_alpha["edit"].text())
                    self.channel_alpha_current = float(np.clip(alpha, 0.001, 0.3))
            except ValueError:
                self.sync_ui_from_state(update_edits=True)
                return

            self.sync_ui_from_state(update_edits=True)
            self.redraw_all()

    def on_tap_slider_change(self):
        if self.syncing_ui:
            return

        with self.ui_sync() as active:
            if not active:
                return
            self.control_mode = "tap"
            self.set_custom_preset()
            cm1 = self.slider_cm1["slider"].value() / 1000
            cp1 = self.slider_cp1["slider"].value() / 1000
            self.cm1_current, self.cp1_current = self.enforce_tap_constraint(cm1, cp1)
            _, _, _, _, pre_db, de_db = calc_levels(self.cm1_current, self.cp1_current)
            self.pre_db_current = float(np.clip(pre_db, 0.0, 6.0))
            self.de_db_current = float(np.clip(de_db, -12.0, 0.0))
            self.sync_ui_from_state(update_edits=True)
            if self.is_any_slider_down():
                self.update_nrz_realtime()
            else:
                self.redraw_all()

    def on_alpha_slider_change(self):
        if self.syncing_ui:
            return

        with self.ui_sync() as active:
            if not active:
                return
            self.channel_alpha_current = self.slider_alpha["slider"].value() / 1000
            self.sync_ui_from_state(update_edits=True)
            if self.is_any_slider_down():
                self.update_nrz_realtime()
            else:
                self.redraw_all()

    def is_any_slider_down(self):
        return any(
            s["slider"].isSliderDown()
            for s in (
                self.slider_cm1, self.slider_cp1, self.slider_alpha,
                self.slider_ctle, self.slider_dfe1, self.slider_dfe2, self.slider_dfe3
            )
        )

    def on_slider_released(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.sync_ui_from_state(update_edits=True)
            self.redraw_all()

    def on_rx_slider_change(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.ctle_boost_current = self.slider_ctle["slider"].value() / 1000
            self.dfe_tap1_current = self.slider_dfe1["slider"].value() / 1000
            self.dfe_tap2_current = self.slider_dfe2["slider"].value() / 1000
            self.dfe_tap3_current = self.slider_dfe3["slider"].value() / 1000
            self.sync_ui_from_state(update_edits=True)
            if self.is_any_slider_down():
                self.update_nrz_realtime()
            else:
                self.redraw_all()

    def on_rx_edit_change(self, target):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            try:
                if target == "ctle":
                    val = float(self.slider_ctle["edit"].text())
                    self.ctle_boost_current = float(np.clip(val, 0.0, 1.0))
                elif target == "dfe1":
                    val = float(self.slider_dfe1["edit"].text())
                    self.dfe_tap1_current = float(np.clip(val, -0.5, 0.5))
                elif target == "dfe2":
                    val = float(self.slider_dfe2["edit"].text())
                    self.dfe_tap2_current = float(np.clip(val, -0.5, 0.5))
                elif target == "dfe3":
                    val = float(self.slider_dfe3["edit"].text())
                    self.dfe_tap3_current = float(np.clip(val, -0.5, 0.5))
            except ValueError:
                self.sync_ui_from_state(update_edits=True)
                return
            self.sync_ui_from_state(update_edits=True)
            self.redraw_all()

    def on_rx_view_change(self):
        if self.syncing_ui:
            return
        self.rx_view_mode = self.rx_view_combo.currentText()
        self.redraw_all()

    def on_reset_rx(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.ctle_boost_current = 0.0
            self.dfe_tap1_current = 0.0
            self.dfe_tap2_current = 0.0
            self.dfe_tap3_current = 0.0
            self.sync_ui_from_state(update_edits=True)
            self.redraw_all()

    def on_generate_new_waveform(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.bits = generate_random_nrz_bits(BIT_COUNT)
            self.symbols = nrz_bits_to_symbols(self.bits)
            self.redraw_all()

    def on_reset_no_eq(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.pre_db_current = 0.0
            self.de_db_current = 0.0
            self.cm1_current, self.cp1_current = db_to_taps(
                self.pre_db_current, self.de_db_current
            )
            self.current_preset = "Preset 4"
            self.control_mode = "preset"
            self.sync_ui_from_state(update_edits=True)
            self.redraw_all()

    def on_reset_channel(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.channel_alpha_current = 0.08
            self.sync_ui_from_state(update_edits=True)
            self.redraw_all()

    def on_reset_all(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.pre_db_current = 0.0
            self.de_db_current = 0.0
            self.cm1_current, self.cp1_current = db_to_taps(
                self.pre_db_current, self.de_db_current
            )
            self.current_preset = "Preset 4"
            self.control_mode = "preset"
            self.channel_alpha_current = 0.08

            # Reset RX EQ too
            self.ctle_boost_current = 0.0
            self.dfe_tap1_current = 0.0
            self.dfe_tap2_current = 0.0
            self.dfe_tap3_current = 0.0
            self.rx_view_mode = "Channel (Before RX EQ)"

            self.sync_ui_from_state(update_edits=True)
            self.redraw_all()

    def on_toggle_nrz_detail(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("NRZ TX/RX EQ Details")
        msg.setIcon(QMessageBox.Information)
        msg.setText("Teaching Simulator Detailed Information")
        msg.setInformativeText(
            "Teaching Focus:\n"
            "- NRZ waveform uses a measurement-like Va/Vb/Vc level model.\n"
            "- User directly controls C-1 and C+1.\n"
            "- C-1 controls Preshoot and raises Vc relative to Vb.\n"
            "- C+1 controls De-emphasis and lowers Vb relative to Va.\n"
            "- Preshoot dB and De-emphasis dB are displayed as derived measurement values, not direct UI controls.\n"
            "- Va is the first bit after transition.\n"
            "- Vb is the repeated / de-emphasized level.\n"
            "- Vc is the last bit before transition / preshoot level.\n"
            "- tx_fir() is kept only as an ideal FIR reference, not as the default NRZ waveform display.\n"
            "- This is a teaching simulator, not a PCIe compliance calculator.\n\n"
            "Channel & RX EQ:\n"
            "- Low-pass Alpha is a simplified ISI model, not a real PCIe channel.\n"
            "- CTLE provides high-frequency boost.\n"
            "- DFE operates at symbol rate. It uses previous slicer decisions to subtract post-cursor ISI.\n"
            "- DFE sign convention: corrected[n] = sample[n] - tap * decision[n-1].\n\n"
            "Note:\n"
            "- This is a teaching simulator, not a PCIe compliance tool."
        )
        msg.exec_()

    def get_target_rx_wave(self, rx_results):
        if "CTLE" in self.rx_view_mode:
            return rx_results["ctle_wave"]
        elif "DFE" in self.rx_view_mode:
            return rx_results["ctle_wave"]
        else:
            return rx_results["ch_wave"]

    def update_eye_title(self):
        if "CTLE" in self.rx_view_mode:
            self.eye_plot.setTitle("Eye Diagram after CTLE")
        elif "DFE" in self.rx_view_mode:
            self.eye_plot.setTitle("DFE Corrected Sample Margin")
        else:
            self.eye_plot.setTitle("Eye Diagram after Channel")

    def should_update_realtime_eye(self):
        if self.realtime_eye_timer.hasExpired(REALTIME_EYE_INTERVAL_MS):
            self.realtime_eye_timer.restart()
            return True
        return False

    def update_nrz_realtime(self):
        config = NrzSimulationConfig(
            symbols=self.symbols,
            spb=SPB,
            pre_db=self.pre_db_current,
            de_db=self.de_db_current,
            channel_alpha=self.channel_alpha_current,
            ctle_gain=self.ctle_boost_current,
            ctle_alpha=0.08,
            dfe_taps=[self.dfe_tap1_current, self.dfe_tap2_current, self.dfe_tap3_current],
            sampling_phase=SPB // 2,
            max_traces=REALTIME_EYE_TRACES,
            eye_ui=EYE_UI,
        )
        res = run_simulation(config)
        rx_results = {
            "ctle_wave": res.ctle_wave,
            "dfe_input_samples": res.dfe_input_samples,
            "dfe_corrected_samples": res.dfe_corrected_samples,
            "dfe_decisions": res.dfe_decisions,
        }
        rx_wave = res.ctle_wave if ("CTLE" in self.rx_view_mode or "DFE" in self.rx_view_mode) else res.ch_wave

        self.update_waveform(res.tx_wave, res.ch_wave, rx_wave if "Channel" not in self.rx_view_mode else None)

        if self.should_update_realtime_eye():
            self.update_eye_title()
            if "DFE" in self.rx_view_mode:
                self.update_dfe_sample_plot(rx_results, max_symbols=REALTIME_EYE_TRACES)
                self.eye_metrics = res.dfe_eye_metrics
            elif "CTLE" in self.rx_view_mode:
                self.update_eye(rx_wave, max_traces=REALTIME_EYE_TRACES)
                self.eye_metrics = res.ctle_eye_metrics
            else:
                self.update_eye(rx_wave, max_traces=REALTIME_EYE_TRACES)
                self.eye_metrics = res.channel_eye_metrics
            self.update_info()

    def redraw_all(self):
        config = NrzSimulationConfig(
            symbols=self.symbols,
            spb=SPB,
            pre_db=self.pre_db_current,
            de_db=self.de_db_current,
            channel_alpha=self.channel_alpha_current,
            ctle_gain=self.ctle_boost_current,
            ctle_alpha=0.08,
            dfe_taps=[self.dfe_tap1_current, self.dfe_tap2_current, self.dfe_tap3_current],
            sampling_phase=SPB // 2,
            max_traces=MAX_EYE_TRACES,
            eye_ui=EYE_UI,
        )
        res = run_simulation(config)
        rx_results = {
            "ctle_wave": res.ctle_wave,
            "dfe_input_samples": res.dfe_input_samples,
            "dfe_corrected_samples": res.dfe_corrected_samples,
            "dfe_decisions": res.dfe_decisions,
        }
        rx_wave = res.ctle_wave if ("CTLE" in self.rx_view_mode or "DFE" in self.rx_view_mode) else res.ch_wave

        self.update_waveform(res.tx_wave, res.ch_wave, rx_wave if "Channel" not in self.rx_view_mode else None)
        self.update_eye_title()
        if "DFE" in self.rx_view_mode:
            self.update_dfe_sample_plot(rx_results, max_symbols=MAX_EYE_TRACES)
            self.eye_metrics = res.dfe_eye_metrics
        elif "CTLE" in self.rx_view_mode:
            self.update_eye(rx_wave, max_traces=MAX_EYE_TRACES)
            self.eye_metrics = res.ctle_eye_metrics
        else:
            self.update_eye(rx_wave, max_traces=MAX_EYE_TRACES)
            self.eye_metrics = res.channel_eye_metrics
        self.update_info()

    def full_refresh(self):
        with self.ui_sync() as active:
            if not active:
                return
            self.sync_ui_from_state(update_edits=True)
            self.redraw_all()

    def update_waveform(self, tx_wave, ch_wave, rx_wave=None):
        length = PLOT_BITS * SPB
        t = np.arange(length) / SPB

        self.tx_curve.setData(t, tx_wave[:length])
        self.ch_curve.setData(t, ch_wave[:length])

        if rx_wave is not None:
            self.rx_curve.setData(t, rx_wave[:length])
        else:
            self.rx_curve.setData([], [])

        self.wave_plot.setXRange(0, PLOT_BITS)
        ymax = max(
            1.3,
            float(np.max(np.abs(tx_wave[:length]))),
            float(np.max(np.abs(ch_wave[:length]))),
        )
        if rx_wave is not None:
            ymax = max(ymax, float(np.max(np.abs(rx_wave[:length]))))

        ymax *= 1.1
        self.wave_plot.setYRange(-ymax, ymax)

    def update_eye(self, wave, max_traces=MAX_EYE_TRACES):
        # Density eye is not implemented; always render the line eye diagram.
        self.update_eye_line(wave, max_traces)

    def update_eye_line(self, wave, max_traces=MAX_EYE_TRACES):
        self.eye_curve.show()
        self.eye_plot.setLabel("bottom", "UI")
        self.eye_plot.setLabel("left", "Voltage")
        if hasattr(self, 'eye_zero_line'):
            self.eye_zero_line.hide()
        self.eye_curve.setPen(pg.mkPen((50, 150, 255, 100)))
        self.eye_curve.setSymbol(None)

        seg_len = EYE_UI * SPB
        start = 20 * SPB
        trace_starts = np.arange(start, len(wave) - seg_len, SPB, dtype=int)
        if trace_starts.size == 0:
            self.eye_curve.setData([], [])
            self.eye_plot.setXRange(0, EYE_UI)
            self.eye_plot.setYRange(-1.3, 1.3)
            return

        if trace_starts.size > max_traces:
            idx = np.linspace(0, trace_starts.size - 1, max_traces, dtype=int)
            sampled_starts = trace_starts[idx]
        else:
            sampled_starts = trace_starts

        x = np.arange(seg_len, dtype=float) / SPB
        x_block = np.concatenate([x, [np.nan]])
        x_all = np.tile(x_block, sampled_starts.size)

        y_all = np.empty(sampled_starts.size * (seg_len + 1), dtype=float)
        for idx, s in enumerate(sampled_starts):
            base = idx * (seg_len + 1)
            y_all[base:base + seg_len] = wave[s:s + seg_len]
            y_all[base + seg_len] = np.nan

        self.eye_curve.setData(x_all, y_all)

        self.eye_plot.setXRange(0, EYE_UI)
        ymax = max(1.3, float(np.max(np.abs(wave))))
        ymax *= 1.1
        self.eye_plot.setYRange(-ymax, ymax)

    def update_dfe_sample_plot(self, rx_results, max_symbols=200):
        self.eye_curve.show()
        self.eye_plot.setLabel("bottom", "Symbol Index")
        self.eye_plot.setLabel("left", "Corrected Sample Value")

        if not hasattr(self, 'eye_zero_line'):
            self.eye_zero_line = pg.InfiniteLine(angle=0, pen=pg.mkPen('y', style=Qt.DashLine))
            self.eye_plot.addItem(self.eye_zero_line)
        self.eye_zero_line.show()

        samples = rx_results["dfe_corrected_samples"]
        if len(samples) == 0:
            self.eye_curve.setData([], [])
            return

        start_idx = 20
        if start_idx < len(samples):
            samples = samples[start_idx:]
        else:
            start_idx = 0

        if len(samples) > max_symbols:
            idx = np.linspace(0, len(samples) - 1, max_symbols, dtype=int)
            samples = samples[idx]
            x_vals = idx + start_idx
        else:
            x_vals = np.arange(len(samples)) + start_idx

        self.eye_curve.setPen(None)
        self.eye_curve.setSymbol('o')
        self.eye_curve.setSymbolSize(6)
        self.eye_curve.setSymbolBrush(pg.mkBrush(100, 200, 255, 200))
        self.eye_curve.setData(x_vals, samples)

        self.eye_plot.setXRange(max(0, x_vals[0] - 5), x_vals[-1] + 5)
        ymax = max(1.3, float(np.max(np.abs(samples)))) * 1.1
        self.eye_plot.setYRange(-ymax, ymax)

    def update_eye_metrics(self, wave, rx_results=None, max_traces=MAX_EYE_TRACES):
        is_dfe = rx_results is not None and "DFE" in self.rx_view_mode
        self.eye_metrics = calculate_eye_metrics(
            wave,
            rx_results=rx_results,
            is_dfe=is_dfe,
            reference_symbols=self.symbols,
            max_traces=max_traces,
            eye_ui=EYE_UI,
            spb=SPB,
        )

    def update_info(self):
        c0, _, _, _, _, _ = calc_levels(self.cm1_current, self.cp1_current)

        def set_item(r, c, label_text, value_text):
            lbl, val = self.status_items[(r, c)]
            if label_text:
                lbl.setText(label_text)
                lbl.show()
                val.setText(value_text)
                val.show()
            else:
                lbl.hide()
                val.hide()

        set_item(0, 0, "Preset:", self.current_preset)
        set_item(0, 1, "Mode:", self.control_mode)

        if "DFE" in self.rx_view_mode:
            set_item(0, 2, "RX:", "DFE Margin")
            set_item(0, 3, "CTLE:", f"{self.ctle_boost_current:.3f}")

            set_item(1, 0, "DFE:", f"{self.dfe_tap1_current:.3f} / {self.dfe_tap2_current:.3f} / {self.dfe_tap3_current:.3f}")
            set_item(1, 1, "Margin:", f"{self.eye_metrics.get('margin_5pct', 0.0):.4f}")
            set_item(1, 2, "Errors:", str(self.eye_metrics.get('error_count', 0)))
            set_item(1, 3, "Spread:", f"{self.eye_metrics.get('center_spread', 0.0):.4f}")
        else:
            set_item(0, 2, "Pre/De:", f"{self.pre_db_current:.2f} / {self.de_db_current:.2f} dB")
            set_item(0, 3, "CH:", f"{self.channel_alpha_current:.3f}")

            set_item(1, 0, "C-1:", f"{self.cm1_current:.4f}")
            set_item(1, 1, "C0:", f"{c0:.4f}")
            set_item(1, 2, "C+1:", f"{self.cp1_current:.4f}")
            set_item(1, 3, "Eye:", f"{self.eye_metrics.get('eye_height', 0.0):.4f} / {self.eye_metrics.get('center_spread', 0.0):.4f}")
