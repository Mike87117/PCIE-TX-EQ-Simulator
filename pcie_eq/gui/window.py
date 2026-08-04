"""
PCIe TX/RX EQ Teaching Simulator GUI Window Module.

Contains PCIeTxEqSimulator main window class and associated GUI constants/helpers.
Source authority: main.py @ commit bb6f9d956f5d61201b8a134b1016437a6de5156e
"""

import sys
import numpy as np
from contextlib import contextmanager
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QSlider, QLineEdit, QPushButton, QComboBox,
    QPlainTextEdit, QTabWidget, QScrollArea, QSizePolicy, QGroupBox, QGridLayout,
    QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, QElapsedTimer
from PyQt5.QtGui import QDoubleValidator
import pyqtgraph as pg

from pcie_eq.tx_eq import (
    PCIE_PRESET_DB_TABLE,
    PCIE_GEN6_PRESET_TAP_TABLE,
    taps_to_db,
    calc_levels,
    db_to_taps,
    tx_fir,
    tx_eq_levels,
    constrain_gen6_taps,
    calc_gen6_levels,
    gen6_pam4_fir,
)
from pcie_eq.channel import simple_channel
from pcie_eq.rx_eq import (
    apply_ctle,
    apply_dfe,
    run_rx_pipeline,
)
from pcie_eq.metrics import (
    calc_pam4_eye_openings_at_phase,
    estimate_pam4_common_t_center_phase,
    calculate_pam4_eye_metrics,
    calculate_eye_metrics,
)
from pcie_eq.models import NrzSimulationConfig, Pam4SimulationConfig
from pcie_eq.pipeline import run_simulation
from pcie_eq.gui.constants import (
    BIT_COUNT,
    SPB,
    PLOT_BITS,
    EYE_UI,
    MAX_EYE_TRACES,
    REALTIME_EYE_TRACES,
    REALTIME_EYE_INTERVAL_MS,
    PAM4_SYMBOL_COUNT,
)
from pcie_eq.gui.nrz_tab import build_nrz_tab
from pcie_eq.gui.pam4_tab import build_pam4_tab
from pcie_eq.gui.nrz_controller import NrzControllerMixin

__all__ = [
    "BIT_COUNT",
    "SPB",
    "PLOT_BITS",
    "EYE_UI",
    "MAX_EYE_TRACES",
    "REALTIME_EYE_TRACES",
    "REALTIME_EYE_INTERVAL_MS",
    "PAM4_SYMBOL_COUNT",
    "pam4_symbols_from_random",
    "validate_gen6_presets",
    "PCIeTxEqSimulator",
]

# Density eye rendering is not implemented; line eye rendering is always used.

np.random.seed(7)
bits = np.random.randint(0, 2, BIT_COUNT)
symbols = 2 * bits - 1

# =========================
# PCIe TX EQ & Channel math
# =========================


def pam4_symbols_from_random(count):
    levels = np.array([-3.0, -1.0, 1.0, 3.0], dtype=float) / 3.0
    return levels[np.random.randint(0, 4, count)]


def validate_gen6_presets():
    """Developer debug helper for manually inspecting Gen6 visualization presets."""
    header = (
        "Preset  C-2     C-1      C0      C+1      Va      Vb      "
        "Vc1     Vc2     Vd      Va/Vd   Vb/Vd   Vc1/Vd  Vc2/Vd  "
        "Pre1    Pre2    De      Boost   TapSum"
    )
    print(header)
    print("-" * len(header))
    for preset_name in sorted(
        PCIE_GEN6_PRESET_TAP_TABLE,
        key=lambda name: int(name[1:]),
    ):
        cm2, cm1, cp1 = PCIE_GEN6_PRESET_TAP_TABLE[preset_name]
        (
            c0,
            va,
            vb,
            vc1,
            vc2,
            vd,
            pre1_db,
            pre2_db,
            de_db,
            boost_db,
        ) = calc_gen6_levels(cm2, cm1, cp1)
        tap_sum = abs(cm2) + abs(cm1) + abs(c0) + abs(cp1)
        if vd > 0:
            va_ratio = f"{va / vd:7.3f}"
            vb_ratio = f"{vb / vd:7.3f}"
            vc1_ratio = f"{vc1 / vd:7.3f}"
            vc2_ratio = f"{vc2 / vd:7.3f}"
        else:
            va_ratio = vb_ratio = vc1_ratio = vc2_ratio = "    N/A"
        print(
            f"{preset_name:<6} "
            f"{cm2:6.3f} {cm1:7.3f} {c0:7.3f} {cp1:7.3f} "
            f"{va:7.3f} {vb:7.3f} {vc1:7.3f} {vc2:7.3f} {vd:7.3f} "
            f"{va_ratio} {vb_ratio} {vc1_ratio} {vc2_ratio} "
            f"{pre1_db:7.2f} {pre2_db:7.2f} {de_db:7.2f} {boost_db:7.2f} "
            f"{tap_sum:7.3f}"
        )






# =========================
# Main GUI
# =========================

class PCIeTxEqSimulator(NrzControllerMixin, QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PCIe TX/RX EQ Teaching Simulator")
        self.resize(1200, 850)

        self.syncing_ui = False
        self.control_mode = "db"
        self.current_preset = "Custom"
        self.channel_alpha_current = 0.08

        self.pre_db_current = 1.5
        self.de_db_current = -3.5
        self.cm1_current, self.cp1_current = db_to_taps(
            pre_db=self.pre_db_current,
            de_db=self.de_db_current
        )
        self.rx_view_mode = "Channel (Before RX EQ)"
        self.ctle_boost_current = 0.0
        self.dfe_tap1_current = 0.0
        self.dfe_tap2_current = 0.0
        self.dfe_tap3_current = 0.0
        self.eye_metrics = {
            "eye_height": 0.0,
            "eye_max": 0.0,
            "eye_min": 0.0,
            "center_spread": 0.0,
        }
        self.bits = bits.copy()
        self.symbols = symbols.copy()

        self.realtime_eye_timer = QElapsedTimer()
        self.realtime_eye_timer.start()

        self.gen6_preset_current = "Q0"
        self.pam4_cm2_current = 0.0
        self.pam4_cm1_current = 0.0
        self.pam4_cp1_current = 0.0
        self.pam4_alpha_current = 0.08
        self.pam4_eye_mode = "raw"
        self.pam4_t_center_phase = SPB // 2
        self.pam4_t_center_score = 0.0
        self.pam4_symbols = pam4_symbols_from_random(PAM4_SYMBOL_COUNT)
        self.pam4_eye_metrics = {
            "upper_eye": 0.0,
            "middle_eye": 0.0,
            "lower_eye": 0.0,
            "minimum_eye": 0.0,
            "center_spread": 0.0,
        }

        self.init_ui()
        self.full_refresh()
        self.pam4_full_refresh()

    def init_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        self.tabs = QTabWidget()
        self.nrz_tab = QWidget()
        self.pam4_tab = QWidget()
        self.tabs.addTab(self.nrz_tab, "PCIe Gen1~5 NRZ TX EQ")
        self.tabs.addTab(self.pam4_tab, "PCIe Gen6 PAM4 TX EQ")
        root_layout.addWidget(self.tabs)

        build_nrz_tab(self)
        self.init_pam4_tab()
        self.setCentralWidget(root)

    def init_pam4_tab(self):
        build_pam4_tab(self)

    def make_slider(self, name, minimum, maximum, value):
        layout = QHBoxLayout()

        name_label = QLabel(name)
        name_label.setFixedWidth(120)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)
        slider.setValue(value)

        value_edit = QLineEdit()
        value_edit.setFixedWidth(80)
        value_edit.setAlignment(Qt.AlignRight)

        layout.addWidget(name_label)
        layout.addWidget(slider)
        layout.addWidget(value_edit)

        return {
            "layout": layout,
            "slider": slider,
            "edit": value_edit
        }

    @contextmanager
    def ui_sync(self):
        if self.syncing_ui:
            yield False
            return
        self.syncing_ui = True
        try:
            yield True
        finally:
            self.syncing_ui = False

    def set_slider_value_silent(self, slider, value):
        slider.blockSignals(True)
        try:
            slider.setValue(value)
        finally:
            slider.blockSignals(False)

    def set_edit_text_silent(self, edit, text):
        edit.blockSignals(True)
        try:
            edit.setText(text)
        finally:
            edit.blockSignals(False)

    def pam4_sync_ui_from_state(self, update_edits=True):
        self.set_slider_value_silent(
            self.pam4_slider_cm2["slider"], int(self.pam4_cm2_current * 1000)
        )
        self.set_slider_value_silent(
            self.pam4_slider_cm1["slider"], int(self.pam4_cm1_current * 1000)
        )
        self.set_slider_value_silent(
            self.pam4_slider_cp1["slider"], int(self.pam4_cp1_current * 1000)
        )
        self.set_slider_value_silent(
            self.pam4_slider_alpha["slider"], int(self.pam4_alpha_current * 1000)
        )
        self.gen6_preset_combo.blockSignals(True)
        try:
            target = self.gen6_preset_current
            idx = self.gen6_preset_combo.findText(target)
            if idx >= 0:
                self.gen6_preset_combo.setCurrentIndex(idx)
        finally:
            self.gen6_preset_combo.blockSignals(False)
        self.pam4_eye_mode_combo.blockSignals(True)
        try:
            target_mode = "Common t_center Eye" if self.pam4_eye_mode == "centered" else "Raw Eye"
            idx = self.pam4_eye_mode_combo.findText(target_mode)
            if idx >= 0:
                self.pam4_eye_mode_combo.setCurrentIndex(idx)
        finally:
            self.pam4_eye_mode_combo.blockSignals(False)

        if not update_edits:
            return

        edit_rows = [
            (self.pam4_slider_cm2["edit"], f"{self.pam4_cm2_current:.4f}"),
            (self.pam4_slider_cm1["edit"], f"{self.pam4_cm1_current:.4f}"),
            (self.pam4_slider_cp1["edit"], f"{self.pam4_cp1_current:.4f}"),
            (self.pam4_slider_alpha["edit"], f"{self.pam4_alpha_current:.3f}"),
        ]
        for edit, text in edit_rows:
            if not edit.hasFocus():
                self.set_edit_text_silent(edit, text)

    def apply_gen6_preset(self, preset_name):
        if preset_name == "Custom":
            self.gen6_preset_current = "Custom"
            return

        if preset_name in PCIE_GEN6_PRESET_TAP_TABLE:
            self.pam4_cm2_current, self.pam4_cm1_current, self.pam4_cp1_current = (
                PCIE_GEN6_PRESET_TAP_TABLE[preset_name]
            )
            self.gen6_preset_current = preset_name

    def on_gen6_preset_change(self, _index):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.apply_gen6_preset(self.gen6_preset_combo.currentText())
            self.pam4_sync_ui_from_state(update_edits=True)
            self.pam4_redraw_all()

    def set_gen6_custom_preset(self):
        self.gen6_preset_current = "Custom"

    def on_pam4_slider_change(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.set_gen6_custom_preset()
            cm2 = self.pam4_slider_cm2["slider"].value() / 1000
            cm1 = self.pam4_slider_cm1["slider"].value() / 1000
            cp1 = self.pam4_slider_cp1["slider"].value() / 1000
            self.pam4_cm2_current, self.pam4_cm1_current, self.pam4_cp1_current = (
                constrain_gen6_taps(cm2, cm1, cp1)
            )
            self.pam4_alpha_current = self.pam4_slider_alpha["slider"].value() / 1000
            self.pam4_sync_ui_from_state(update_edits=True)
            self.pam4_redraw_all()

    def on_pam4_edit_change(self, target):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            try:
                if target == "cm2":
                    self.set_gen6_custom_preset()
                    value = float(self.pam4_slider_cm2["edit"].text())
                    self.pam4_cm2_current, self.pam4_cm1_current, self.pam4_cp1_current = (
                        constrain_gen6_taps(value, self.pam4_cm1_current, self.pam4_cp1_current)
                    )
                elif target == "cm1":
                    self.set_gen6_custom_preset()
                    value = float(self.pam4_slider_cm1["edit"].text())
                    self.pam4_cm2_current, self.pam4_cm1_current, self.pam4_cp1_current = (
                        constrain_gen6_taps(self.pam4_cm2_current, value, self.pam4_cp1_current)
                    )
                elif target == "cp1":
                    self.set_gen6_custom_preset()
                    value = float(self.pam4_slider_cp1["edit"].text())
                    self.pam4_cm2_current, self.pam4_cm1_current, self.pam4_cp1_current = (
                        constrain_gen6_taps(self.pam4_cm2_current, self.pam4_cm1_current, value)
                    )
                elif target == "alpha":
                    value = float(self.pam4_slider_alpha["edit"].text())
                    self.pam4_alpha_current = float(np.clip(value, 0.001, 0.3))
            except ValueError:
                self.pam4_sync_ui_from_state(update_edits=True)
                return
            self.pam4_sync_ui_from_state(update_edits=True)
            self.pam4_redraw_all()

    def on_pam4_generate_new_waveform(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.pam4_symbols = pam4_symbols_from_random(PAM4_SYMBOL_COUNT)
            self.pam4_redraw_all()

    def on_pam4_reset_eq(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.gen6_preset_current = "Q0"
            self.pam4_cm2_current = 0.0
            self.pam4_cm1_current = 0.0
            self.pam4_cp1_current = 0.0
            self.pam4_sync_ui_from_state(update_edits=True)
            self.pam4_redraw_all()

    def on_pam4_reset_channel(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.pam4_alpha_current = 0.08
            self.pam4_sync_ui_from_state(update_edits=True)
            self.pam4_redraw_all()

    def on_pam4_eye_mode_change(self, _index):
        if self.syncing_ui:
            return
        self.pam4_eye_mode = (
            "centered" if self.pam4_eye_mode_combo.currentText() == "Common t_center Eye" else "raw"
        )
        self.pam4_redraw_all()

    def on_toggle_pam4_detail(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("PAM4 TX EQ Details")
        msg.setIcon(QMessageBox.Information)
        msg.setText("PAM4 Teaching Simulator Detailed Information")
        msg.setInformativeText(
            "Teaching Focus:\n"
            "- PAM4 uses four levels and three eyes.\n"
            "- This tab uses a simplified 4-tap FIR concept.\n"
            "- C0 is calculated from C-2 / C-1 / C+1.\n"
            "- Levels: Va, Vb, Vc1, Vc2, Vd.\n"
            "- Ratios: Va/Vd, Vb/Vd, Vc1/Vd, Vc2/Vd.\n"
            "- Metrics: De-emphasis, Preshoot 1, Preshoot 2, Boost.\n\n"
            "Eye Modes:\n"
            "- Raw Eye: Superimposes traces directly.\n"
            "- Common t_center Eye: Estimates one shared sampling phase that maximizes the minimum upper/middle/lower eye opening, then slices the 2 UI eye around that shared t_center. It does not independently align each PAM4 eye.\n\n"
            "This is simplified visualization only. This is not a PCIe compliance calculator."
        )
        msg.exec_()

    def pam4_full_refresh(self):
        with self.ui_sync() as active:
            if not active:
                return
            self.pam4_sync_ui_from_state(update_edits=True)
            self.pam4_redraw_all()

    def pam4_redraw_all(self):
        config = Pam4SimulationConfig(
            symbols=self.pam4_symbols,
            spb=SPB,
            cm2=self.pam4_cm2_current,
            cm1=self.pam4_cm1_current,
            cp1=self.pam4_cp1_current,
            channel_alpha=self.pam4_alpha_current,
            old_phase=self.pam4_t_center_phase,
            eye_ui=EYE_UI,
        )
        res = run_simulation(config)
        self.pam4_t_center_phase = res.t_center_phase
        self.pam4_t_center_score = res.t_center_score
        self.pam4_eye_metrics = res.pam4_eye_metrics

        self.update_pam4_waveform(res.tx_wave, res.ch_wave)
        self.update_pam4_eye(res.ch_wave)
        self.update_pam4_info()

    def update_pam4_waveform(self, tx_wave, ch_wave):
        length = PLOT_BITS * SPB
        t = np.arange(length) / SPB

        self.pam4_tx_curve.setData(t, tx_wave[:length])
        self.pam4_ch_curve.setData(t, ch_wave[:length])
        self.pam4_wave_plot.setXRange(0, PLOT_BITS)
        self.pam4_wave_plot.setYRange(-1.4, 1.4)

    def update_pam4_eye(self, wave):
        if self.pam4_eye_mode == "centered":
            self.update_pam4_eye_centered(wave)
        else:
            self.update_pam4_eye_raw(wave)

    def update_pam4_eye_raw(self, wave):
        seg_len = EYE_UI * SPB
        start = 20 * SPB
        trace_starts = np.arange(start, len(wave) - seg_len, SPB, dtype=int)
        if trace_starts.size == 0:
            self.pam4_eye_curve.setData([], [])
            self.pam4_eye_plot.setXRange(0, EYE_UI, padding=0)
            self.pam4_eye_plot.setYRange(-1.4, 1.4)
            return

        if trace_starts.size > MAX_EYE_TRACES:
            idx = np.linspace(0, trace_starts.size - 1, MAX_EYE_TRACES, dtype=int)
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

        self.pam4_eye_curve.setData(x_all, y_all)
        self.pam4_eye_plot.setXRange(0, EYE_UI, padding=0)
        self.pam4_eye_plot.setYRange(-1.4, 1.4)

    def update_pam4_eye_centered(self, wave):
        seg_len = EYE_UI * SPB
        half_seg = seg_len // 2
        start = 20 * SPB
        phase = int(np.clip(self.pam4_t_center_phase, 0, SPB - 1))

        center_positions = np.arange(start + phase, len(wave), SPB, dtype=int)
        trace_starts = center_positions - half_seg
        trace_starts = trace_starts[
            (trace_starts >= 0) & (trace_starts + seg_len <= len(wave))
        ]
        if trace_starts.size == 0:
            self.pam4_eye_curve.setData([], [])
            self.pam4_eye_plot.setXRange(0, EYE_UI, padding=0)
            self.pam4_eye_plot.setYRange(-1.4, 1.4)
            return

        if trace_starts.size > MAX_EYE_TRACES:
            idx = np.linspace(0, trace_starts.size - 1, MAX_EYE_TRACES, dtype=int)
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

        self.pam4_eye_curve.setData(x_all, y_all)
        self.pam4_eye_plot.setXRange(0, EYE_UI, padding=0)
        self.pam4_eye_plot.setYRange(-1.4, 1.4)

    def calc_pam4_eye_openings_at_phase(self, wave, phase):
        return calc_pam4_eye_openings_at_phase(wave, self.pam4_symbols, phase, spb=SPB)

    def estimate_pam4_common_t_center_phase(self, wave):
        return estimate_pam4_common_t_center_phase(
            wave, self.pam4_symbols, old_phase=self.pam4_t_center_phase, spb=SPB
        )

    def update_pam4_eye_metrics(self, wave):
        best_phase, best_score, metrics = calculate_pam4_eye_metrics(
            wave, self.pam4_symbols, old_phase=self.pam4_t_center_phase, spb=SPB
        )
        self.pam4_t_center_phase = int(best_phase)
        self.pam4_t_center_score = float(best_score)
        self.pam4_eye_metrics = metrics

    def update_pam4_info(self):
        (
            c0,
            va,
            vb,
            vc1,
            vc2,
            vd,
            pre1_db,
            pre2_db,
            de_db,
            boost_db,
        ) = calc_gen6_levels(
            self.pam4_cm2_current,
            self.pam4_cm1_current,
            self.pam4_cp1_current,
        )
        tap_sum = (
            abs(self.pam4_cm2_current)
            + abs(self.pam4_cm1_current)
            + abs(c0)
            + abs(self.pam4_cp1_current)
        )
        if vd > 0:
            va_ratio = va / vd
            vb_ratio = vb / vd
            vc1_ratio = vc1 / vd
            vc2_ratio = vc2 / vd
        else:
            va_ratio = vb_ratio = vc1_ratio = vc2_ratio = 0.0
        t_center_ui = self.pam4_t_center_phase / SPB
        eye_mode_text = "Common t_center Eye" if self.pam4_eye_mode == "centered" else "Raw Eye"
        if self.pam4_eye_mode == "centered":
            eye_mode_note = (
                "Common t_center Eye estimates one shared PAM4 sampling phase that maximizes the minimum Upper/Middle/Lower eye opening, "
                "then slices the 2 UI eye around that shared t_center. It does not independently align the three PAM4 eyes, "
                "and it does not perform per-trace x_shift or per-eye shifting."
            )
        else:
            eye_mode_note = (
                "Raw Eye uses fixed 2 UI slicing without common t_center re-centering."
            )
        eye_mode_text = "Raw" if self.pam4_eye_mode == "raw" else "Center"

        def set_item(r, c, label_text, value_text):
            lbl, val = self.pam4_status_items[(r, c)]
            if label_text:
                lbl.setText(label_text)
                lbl.show()
                val.setText(value_text)
                val.show()
            else:
                lbl.hide()
                val.hide()

        set_item(0, 0, "Preset:", self.gen6_preset_current)
        set_item(0, 1, "Eye:", eye_mode_text)
        set_item(0, 2, "Alpha:", f"{self.pam4_alpha_current:.3f}")
        set_item(0, 3, "tC:", f"{t_center_ui:.3f} UI")
        
        set_item(1, 0, "Taps:", f"{self.pam4_cm2_current:.3f} / {self.pam4_cm1_current:.3f} / {c0:.3f} / {self.pam4_cp1_current:.3f}")
        set_item(1, 1, "U/M/L:", f"{self.pam4_eye_metrics['upper_eye']:.3f} / {self.pam4_eye_metrics['middle_eye']:.3f} / {self.pam4_eye_metrics['lower_eye']:.3f}")
        set_item(1, 2, "Min Eye:", f"{self.pam4_eye_metrics['minimum_eye']:.4f}")
        set_item(1, 3, "Spread:", f"{self.pam4_eye_metrics['center_spread']:.4f}")
