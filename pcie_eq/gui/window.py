"""
PCIe TX/RX EQ Teaching Simulator GUI Window Module.

Contains PCIeTxEqSimulator main window class and associated GUI constants/helpers.
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

# =========================
# Basic parameters
# =========================

BIT_COUNT = 512
SPB = 32
PLOT_BITS = 64
EYE_UI = 2
MAX_EYE_TRACES = 200
REALTIME_EYE_TRACES = 60
REALTIME_EYE_INTERVAL_MS = 50
PAM4_SYMBOL_COUNT = 512
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

class PCIeTxEqSimulator(QMainWindow):
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

        layout = QVBoxLayout(self.nrz_tab)

        pg.setConfigOptions(antialias=False)

        self.wave_plot = pg.PlotWidget(title="PCIe TX EQ Waveform")
        self.wave_plot.setLabel("bottom", "Bit / UI")
        self.wave_plot.setLabel("left", "Voltage")
        self.wave_plot.showGrid(x=True, y=True)
        
        self.wave_plot.hideButtons()

        self.eye_plot = pg.PlotWidget(title="Eye Diagram after Channel")
        self.eye_plot.setLabel("bottom", "UI")
        self.eye_plot.setLabel("left", "Voltage")
        self.eye_plot.showGrid(x=True, y=True)
        
        self.eye_plot.hideButtons()

        layout.addWidget(self.wave_plot, stretch=2)
        layout.addWidget(self.eye_plot, stretch=3)

        controls_panel = self.create_nrz_controls_panel()
        layout.addWidget(controls_panel)

        self.setCentralWidget(root)

        self.init_pam4_tab()

    def init_pam4_tab(self):
        layout = QVBoxLayout(self.pam4_tab)

        self.pam4_wave_plot = pg.PlotWidget(title="PCIe Gen6 PAM4 TX Waveform")
        self.pam4_wave_plot.setLabel("bottom", "Symbol / UI")
        self.pam4_wave_plot.setLabel("left", "Voltage")
        self.pam4_wave_plot.showGrid(x=True, y=True)
        self.pam4_wave_plot.hideButtons()

        self.pam4_eye_plot = pg.PlotWidget(title="PAM4 Eye Diagram after Channel")
        self.pam4_eye_plot.setLabel("bottom", "UI")
        self.pam4_eye_plot.setLabel("left", "Voltage")
        self.pam4_eye_plot.showGrid(x=True, y=True)
        self.pam4_eye_plot.hideButtons()

        layout.addWidget(self.pam4_wave_plot, stretch=2)
        layout.addWidget(self.pam4_eye_plot, stretch=3)

        controls_panel = self.create_pam4_controls_panel()
        layout.addWidget(controls_panel)

        self.pam4_tx_curve = self.pam4_wave_plot.plot(pen=pg.mkPen("#4DF0FF", width=2), name="TX FIR")
        self.pam4_ch_curve = self.pam4_wave_plot.plot(pen=pg.mkPen("#FF8A00", width=2), name="Channel")
        self.pam4_eye_curves = []

    def create_nrz_controls_panel(self):
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(4)

        control_group = QGroupBox("Equalization Controls")
        control_layout = QHBoxLayout(control_group)
        control_layout.setContentsMargins(8, 4, 8, 4)
        control_layout.setSpacing(8)

        preset_label = QLabel("PCIe Preset")
        preset_label.setFixedWidth(120)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Custom")
        for p in range(11):
            self.preset_combo.addItem(f"Preset {p}")
        self.preset_combo.currentIndexChanged.connect(self.on_preset_change)
        control_layout.addWidget(preset_label)
        control_layout.addWidget(self.preset_combo)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        control_layout.addWidget(sep1)

        self.btn_reset_no_eq = QPushButton("Reset to TX EQ")
        self.btn_reset_no_eq.clicked.connect(self.on_reset_no_eq)
        self.btn_reset_channel = QPushButton("Reset Channel")
        self.btn_reset_channel.clicked.connect(self.on_reset_channel)
        self.btn_reset_all = QPushButton("Reset All")
        self.btn_reset_all.clicked.connect(self.on_reset_all)

        for btn in (
            self.btn_reset_no_eq,
            self.btn_reset_channel,
            self.btn_reset_all,
        ):
            btn.setFixedHeight(24)
            control_layout.addWidget(btn)

        self.btn_toggle_detail = QPushButton("Teaching Details")
        self.btn_toggle_detail.setFixedHeight(24)
        self.btn_toggle_detail.clicked.connect(self.on_toggle_nrz_detail)
        control_layout.addWidget(self.btn_toggle_detail)

        self.btn_gen_wave = QPushButton("Generate New Waveform")
        self.btn_gen_wave.setFixedHeight(24)
        self.btn_gen_wave.clicked.connect(self.on_generate_new_waveform)
        control_layout.addWidget(self.btn_gen_wave)

        panel_layout.addWidget(control_group)

        sliders_group = QGroupBox("TX Equalization & Channel Sliders")
        sliders_layout = QHBoxLayout(sliders_group)
        sliders_layout.setContentsMargins(8, 4, 8, 4)
        sliders_layout.setSpacing(12)

        self.slider_cm1 = self.create_slider_control(
            "C-1 (Pre):", -0.300, 0.000, 0.001, self.on_tap_slider_change, lambda: self.on_edit_change("cm1")
        )
        self.slider_cp1 = self.create_slider_control(
            "C+1 (Post):", -0.300, 0.000, 0.001, self.on_tap_slider_change, lambda: self.on_edit_change("cp1")
        )
        self.slider_alpha = self.create_slider_control(
            "Channel Alpha:", 0.001, 0.300, 0.001, self.on_alpha_slider_change, lambda: self.on_edit_change("alpha")
        )

        sliders_layout.addWidget(self.slider_cm1["widget"])
        sliders_layout.addWidget(self.slider_cp1["widget"])
        sliders_layout.addWidget(self.slider_alpha["widget"])

        panel_layout.addWidget(sliders_group)

        rx_group = QGroupBox("RX Equalization Controls (CTLE & DFE)")
        rx_layout = QHBoxLayout(rx_group)
        rx_layout.setContentsMargins(8, 4, 8, 4)
        rx_layout.setSpacing(12)

        rx_control_panel = QWidget()
        rx_control_layout = QVBoxLayout(rx_control_panel)
        rx_control_layout.setContentsMargins(0, 0, 0, 0)

        rx_view_label = QLabel("Eye View Mode:")
        self.rx_view_combo = QComboBox()
        self.rx_view_combo.addItems(["Channel (Before RX EQ)", "CTLE", "DFE (Sample Margin)"])
        self.rx_view_combo.currentIndexChanged.connect(self.on_rx_view_change)

        rx_control_layout.addWidget(rx_view_label)
        rx_control_layout.addWidget(self.rx_view_combo)

        self.btn_reset_rx = QPushButton("Reset RX EQ")
        self.btn_reset_rx.setFixedHeight(24)
        self.btn_reset_rx.clicked.connect(self.on_reset_rx)
        rx_control_layout.addWidget(self.btn_reset_rx)

        rx_layout.addWidget(rx_control_panel, stretch=1)

        self.slider_ctle = self.create_slider_control(
            "CTLE Boost:", 0.000, 1.000, 0.010, self.on_rx_slider_change, lambda: self.on_rx_edit_change("ctle")
        )
        self.slider_dfe1 = self.create_slider_control(
            "DFE Tap 1:", -0.500, 0.500, 0.005, self.on_rx_slider_change, lambda: self.on_rx_edit_change("dfe1")
        )
        self.slider_dfe2 = self.create_slider_control(
            "DFE Tap 2:", -0.500, 0.500, 0.005, self.on_rx_slider_change, lambda: self.on_rx_edit_change("dfe2")
        )
        self.slider_dfe3 = self.create_slider_control(
            "DFE Tap 3:", -0.500, 0.500, 0.005, self.on_rx_slider_change, lambda: self.on_rx_edit_change("dfe3")
        )

        rx_layout.addWidget(self.slider_ctle["widget"], stretch=1)
        rx_layout.addWidget(self.slider_dfe1["widget"], stretch=1)
        rx_layout.addWidget(self.slider_dfe2["widget"], stretch=1)
        rx_layout.addWidget(self.slider_dfe3["widget"], stretch=1)

        panel_layout.addWidget(rx_group)

        info_panel = self.create_info_panel()
        panel_layout.addWidget(info_panel)

        self.tx_curve = self.wave_plot.plot(pen=pg.mkPen("#4DF0FF", width=2), name="TX FIR")
        self.ch_curve = self.wave_plot.plot(pen=pg.mkPen("#FF8A00", width=2), name="Channel")
        self.rx_curve = self.wave_plot.plot(pen=pg.mkPen("#7C4DFF", width=2), name="RX EQ Target")
        self.eye_curves = []

        return panel

    def create_pam4_controls_panel(self):
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(4)

        control_group = QGroupBox("Gen6 Preset & Controls")
        control_layout = QHBoxLayout(control_group)
        control_layout.setContentsMargins(8, 4, 8, 4)
        control_layout.setSpacing(8)

        preset_label = QLabel("Gen6 Preset")
        preset_label.setFixedWidth(120)
        self.gen6_preset_combo = QComboBox()
        self.gen6_preset_combo.addItem("Custom")
        for q in range(10):
            self.gen6_preset_combo.addItem(f"Q{q}")
        self.gen6_preset_combo.currentIndexChanged.connect(self.on_gen6_preset_change)
        control_layout.addWidget(preset_label)
        control_layout.addWidget(self.gen6_preset_combo)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        control_layout.addWidget(sep1)

        self.btn_pam4_reset_eq = QPushButton("Reset EQ")
        self.btn_pam4_reset_eq.clicked.connect(self.on_pam4_reset_eq)
        self.btn_pam4_reset_channel = QPushButton("Reset CH")
        self.btn_pam4_reset_channel.clicked.connect(self.on_pam4_reset_channel)

        for btn in (
            self.btn_pam4_reset_eq,
            self.btn_pam4_reset_channel,
        ):
            btn.setFixedHeight(24)
            control_layout.addWidget(btn)

        self.pam4_eye_mode_combo = QComboBox()
        self.pam4_eye_mode_combo.addItems(["Raw Eye", "Common t_center Eye"])
        self.pam4_eye_mode_combo.currentIndexChanged.connect(self.on_pam4_eye_mode_change)
        control_layout.addWidget(self.pam4_eye_mode_combo)

        self.btn_toggle_pam4_detail = QPushButton("Teaching Details")
        self.btn_toggle_pam4_detail.setFixedHeight(24)
        self.btn_toggle_pam4_detail.clicked.connect(self.on_toggle_pam4_detail)
        control_layout.addWidget(self.btn_toggle_pam4_detail)

        self.btn_pam4_gen_wave = QPushButton("Generate New Waveform")
        self.btn_pam4_gen_wave.setFixedHeight(24)
        self.btn_pam4_gen_wave.clicked.connect(self.on_pam4_generate_new_waveform)
        control_layout.addWidget(self.btn_pam4_gen_wave)

        panel_layout.addWidget(control_group)

        sliders_group = QGroupBox("4-Tap FIR & Channel Sliders")
        sliders_layout = QHBoxLayout(sliders_group)
        sliders_layout.setContentsMargins(8, 4, 8, 4)
        sliders_layout.setSpacing(12)

        self.pam4_slider_cm2 = self.create_slider_control(
            "C-2 (Pre2):", 0.000, 0.100, 0.001, self.on_pam4_slider_change, lambda: self.on_pam4_edit_change("cm2")
        )
        self.pam4_slider_cm1 = self.create_slider_control(
            "C-1 (Pre1):", -0.300, 0.000, 0.001, self.on_pam4_slider_change, lambda: self.on_pam4_edit_change("cm1")
        )
        self.pam4_slider_cp1 = self.create_slider_control(
            "C+1 (Post1):", -0.300, 0.000, 0.001, self.on_pam4_slider_change, lambda: self.on_pam4_edit_change("cp1")
        )
        self.pam4_slider_alpha = self.create_slider_control(
            "Channel Alpha:", 0.001, 0.300, 0.001, self.on_pam4_slider_change, lambda: self.on_pam4_edit_change("alpha")
        )

        sliders_layout.addWidget(self.pam4_slider_cm2["widget"])
        sliders_layout.addWidget(self.pam4_slider_cm1["widget"])
        sliders_layout.addWidget(self.pam4_slider_cp1["widget"])
        sliders_layout.addWidget(self.pam4_slider_alpha["widget"])

        panel_layout.addWidget(sliders_group)

        info_panel = self.create_pam4_info_panel()
        panel_layout.addWidget(info_panel)

        return panel

    def create_slider_control(self, label_text, min_val, max_val, step, slider_cb, edit_cb):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel(label_text)
        lbl.setFixedWidth(90)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(int(min_val * 1000))
        slider.setMaximum(int(max_val * 1000))
        slider.setSingleStep(int(step * 1000))
        slider.setValue(0)
        slider.valueChanged.connect(slider_cb)
        slider.sliderReleased.connect(self.on_slider_released)

        edit = QLineEdit()
        edit.setFixedWidth(60)
        validator = QDoubleValidator(min_val, max_val, 3)
        validator.setNotation(QDoubleValidator.StandardNotation)
        edit.setValidator(validator)
        edit.editingFinished.connect(edit_cb)

        layout.addWidget(lbl)
        layout.addWidget(slider)
        layout.addWidget(edit)

        return {
            "widget": container,
            "label": lbl,
            "slider": slider,
            "edit": edit,
            "min": min_val,
            "max": max_val,
        }

    def create_info_panel(self):
        panel = QGroupBox("Status & Metrics")
        grid = QGridLayout(panel)
        grid.setContentsMargins(8, 4, 8, 4)
        grid.setSpacing(6)

        self.status_items = {}
        for r in range(2):
            for c in range(4):
                lbl = QLabel()
                val = QLabel()
                lbl.setStyleSheet("font-weight: bold;")
                val.setStyleSheet("color: #00E676;")
                grid.addWidget(lbl, r, c * 2)
                grid.addWidget(val, r, c * 2 + 1)
                self.status_items[(r, c)] = (lbl, val)

        return panel

    def create_pam4_info_panel(self):
        panel = QGroupBox("PAM4 Status & Metrics")
        grid = QGridLayout(panel)
        grid.setContentsMargins(8, 4, 8, 4)
        grid.setSpacing(6)

        self.pam4_status_items = {}
        for r in range(2):
            for c in range(4):
                lbl = QLabel()
                val = QLabel()
                lbl.setStyleSheet("font-weight: bold;")
                val.setStyleSheet("color: #00E676;")
                grid.addWidget(lbl, r, c * 2)
                grid.addWidget(val, r, c * 2 + 1)
                self.pam4_status_items[(r, c)] = (lbl, val)

        return panel

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

    def set_slider_silent(self, control, value):
        val = int(value * 1000)
        control["slider"].blockSignals(True)
        control["slider"].setValue(val)
        control["slider"].blockSignals(False)

    def set_edit_text_silent(self, edit, text):
        edit.blockSignals(True)
        edit.setText(text)
        edit.blockSignals(False)

    def set_preset_combo_silent(self, text):
        self.preset_combo.blockSignals(True)
        idx = self.preset_combo.findText(text)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        self.preset_combo.blockSignals(False)

    def set_rx_view_combo_silent(self, text):
        self.rx_view_combo.blockSignals(True)
        idx = self.rx_view_combo.findText(text)
        if idx >= 0:
            self.rx_view_combo.setCurrentIndex(idx)
        self.rx_view_combo.blockSignals(False)

    def sync_ui_from_state(self, update_edits=True):
        c0, _, _, _, pre_db, de_db = calc_levels(self.cm1_current, self.cp1_current)
        self.set_slider_silent(self.slider_cm1, self.cm1_current)
        self.set_slider_silent(self.slider_cp1, self.cp1_current)
        self.set_slider_silent(self.slider_alpha, self.channel_alpha_current)

        self.set_slider_silent(self.slider_ctle, self.ctle_boost_current)
        self.set_slider_silent(self.slider_dfe1, self.dfe_tap1_current)
        self.set_slider_silent(self.slider_dfe2, self.dfe_tap2_current)
        self.set_slider_silent(self.slider_dfe3, self.dfe_tap3_current)
        self.set_rx_view_combo_silent(self.rx_view_mode)

        self.set_preset_combo_silent(self.current_preset)

        if update_edits:
            for s, v in (
                (self.slider_cm1, f"{self.cm1_current:.3f}"),
                (self.slider_cp1, f"{self.cp1_current:.3f}"),
                (self.slider_alpha, f"{self.channel_alpha_current:.3f}"),
                (self.slider_ctle, f"{self.ctle_boost_current:.3f}"),
                (self.slider_dfe1, f"{self.dfe_tap1_current:.3f}"),
                (self.slider_dfe2, f"{self.dfe_tap2_current:.3f}"),
                (self.slider_dfe3, f"{self.dfe_tap3_current:.3f}"),
            ):
                self.set_edit_text_silent(s["edit"], v)

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
            self.bits = np.random.randint(0, 2, BIT_COUNT)
            self.symbols = 2 * self.bits - 1
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

    def should_update_realtime_eye(self):
        return self.realtime_eye_timer.elapsed() >= REALTIME_EYE_INTERVAL_MS

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

    def update_dfe_sample_plot(self, rx_results, max_symbols=MAX_EYE_TRACES):
        corrected = rx_results["dfe_corrected_samples"]
        decisions = rx_results["dfe_decisions"]

        N = min(len(corrected), max_symbols + 20)
        corrected_sub = corrected[20:N]
        decisions_sub = decisions[20:N]

        for curve in self.eye_curves:
            self.eye_plot.removeItem(curve)
        self.eye_curves.clear()

        if len(corrected_sub) == 0:
            return

        x_zeros = np.zeros(len(corrected_sub))
        x_ones = np.ones(len(corrected_sub))

        mask_zeros = (decisions_sub == -1)
        mask_ones = (decisions_sub == 1)

        y_zeros = corrected_sub[mask_zeros]
        y_ones = corrected_sub[mask_ones]

        x_z = x_zeros[mask_zeros]
        x_o = x_ones[mask_ones]

        scatter_z = pg.ScatterPlotItem(x=x_z, y=y_zeros, size=5, pen=None, brush=pg.mkBrush("#FF5252"))
        scatter_o = pg.ScatterPlotItem(x=x_o, y=y_ones, size=5, pen=None, brush=pg.mkBrush("#69F0AE"))

        line_z = pg.PlotCurveItem(x=[0, 0], y=[-1.5, 1.5], pen=pg.mkPen("#757575", style=Qt.DashLine))
        line_o = pg.PlotCurveItem(x=[1, 1], y=[-1.5, 1.5], pen=pg.mkPen("#757575", style=Qt.DashLine))

        line_thresh = pg.PlotCurveItem(x=[-0.5, 1.5], y=[0, 0], pen=pg.mkPen("#FFD54F", width=2))

        for item in (scatter_z, scatter_o, line_z, line_o, line_thresh):
            self.eye_plot.addItem(item)
            self.eye_curves.append(item)

        self.eye_plot.setXRange(-0.5, 1.5)
        self.eye_plot.setYRange(-1.5, 1.5)

    @staticmethod
    def calc_pam4_eye_openings_at_phase(wave, pam4_symbols, phase, spb=32):
        return calc_pam4_eye_openings_at_phase(wave, pam4_symbols, phase, spb=spb)

    @staticmethod
    def estimate_pam4_common_t_center_phase(wave, pam4_symbols, old_phase=16, spb=32):
        return estimate_pam4_common_t_center_phase(wave, pam4_symbols, old_phase=old_phase, spb=spb)

    def update_pam4_eye_metrics(self, wave):
        self.pam4_t_center_phase, self.pam4_t_center_score, self.pam4_eye_metrics = (
            calculate_pam4_eye_metrics(
                wave,
                self.pam4_symbols,
                old_phase=self.pam4_t_center_phase,
                spb=SPB,
            )
        )

    def full_refresh(self):
        self.sync_ui_from_state(update_edits=True)
        self.redraw_all()

    def pam4_full_refresh(self):
        self.pam4_sync_ui_from_state(update_edits=True)
        self.pam4_redraw_all()

    def update_pam4_preset_combo_silent(self, text):
        self.gen6_preset_combo.blockSignals(True)
        idx = self.gen6_preset_combo.findText(text)
        if idx >= 0:
            self.gen6_preset_combo.setCurrentIndex(idx)
        self.gen6_preset_combo.blockSignals(False)

    def update_gen6_preset_combo_silent(self, text):
        self.gen6_preset_combo.blockSignals(True)
        idx = self.gen6_preset_combo.findText(text)
        if idx >= 0:
            self.gen6_preset_combo.setCurrentIndex(idx)
        self.gen6_preset_combo.blockSignals(False)

    def pam4_sync_ui_from_state(self, update_edits=True):
        c0, va, vb, vc1, vc2, vd, pre1_db, pre2_db, de_db, boost_db = calc_gen6_levels(
            self.pam4_cm2_current,
            self.pam4_cm1_current,
            self.pam4_cp1_current,
        )

        self.set_slider_silent(self.pam4_slider_cm2, self.pam4_cm2_current)
        self.set_slider_silent(self.pam4_slider_cm1, self.pam4_cm1_current)
        self.set_slider_silent(self.pam4_slider_cp1, self.pam4_cp1_current)
        self.set_slider_silent(self.pam4_slider_alpha, self.pam4_alpha_current)

        self.update_gen6_preset_combo_silent(self.gen6_preset_current)

        if update_edits:
            for s, v in (
                (self.pam4_slider_cm2, f"{self.pam4_cm2_current:.3f}"),
                (self.pam4_slider_cm1, f"{self.pam4_cm1_current:.3f}"),
                (self.pam4_slider_cp1, f"{self.pam4_cp1_current:.3f}"),
                (self.pam4_slider_alpha, f"{self.pam4_alpha_current:.3f}"),
            ):
                self.set_edit_text_silent(s["edit"], v)

    def apply_gen6_preset(self, preset_name):
        if preset_name not in PCIE_GEN6_PRESET_TAP_TABLE:
            self.gen6_preset_current = "Custom"
            return
        cm2, cm1, cp1 = PCIE_GEN6_PRESET_TAP_TABLE[preset_name]
        self.pam4_cm2_current, self.pam4_cm1_current, self.pam4_cp1_current = (
            constrain_gen6_taps(cm2, cm1, cp1)
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
        msg.setWindowTitle("PAM4 Gen6 TX EQ Details")
        msg.setIcon(QMessageBox.Information)
        msg.setText("PCIe Gen6 PAM4 4-Tap FIR Specification & Model")
        msg.setInformativeText(
            "Specification Rules:\n"
            "- Taps: C-2, C-1, C0, C+1.\n"
            "- Constraints: C-2 >= 0, C-1 <= 0, C+1 <= 0, |C-2| + |C-1| + |C0| + |C+1| = 1.\n"
            "- Levels: Va (11-10), Vb (11-11), Vc1 (01-11), Vc2 (00-11), Vd (00-11).\n"
            "- Ratios: Pre1=Vc1/Vd, Pre2=Vc2/Vd, De=Vb/Vd, Boost=Va/Vd.\n"
            "- Presets: Q0 to Q9 map to standardized tap combinations.\n\n"
            "Visualization Model:\n"
            "- Ideal step transition model is used for intuitive teaching visualization.\n"
            "- Eye diagram displays PAM4 3-eye structure after simplified channel loss.\n"
            "- Common t_center Eye mode aligns all 3 eye centers at a shared sampling phase."
        )
        msg.exec_()

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
        ymax = max(1.2, float(np.max(np.abs(tx_wave[:length]))) * 1.1)
        self.pam4_wave_plot.setYRange(-ymax, ymax)

    def update_pam4_eye(self, ch_wave):
        for item in self.pam4_eye_curves:
            self.pam4_eye_plot.removeItem(item)
        self.pam4_eye_curves.clear()

        spb = SPB
        trace_len = EYE_UI * spb
        n_traces = min(MAX_EYE_TRACES, (len(ch_wave) - trace_len) // spb)

        if n_traces <= 0:
            return

        if self.pam4_eye_mode == "centered":
            phase_offset = (self.pam4_t_center_phase - (spb // 2)) % spb
        else:
            phase_offset = 0

        t = np.arange(trace_len) / spb

        for i in range(n_traces):
            start_idx = i * spb + phase_offset
            segment = ch_wave[start_idx : start_idx + trace_len]
            if len(segment) < trace_len:
                continue

            curve = pg.PlotCurveItem(
                t, segment, pen=pg.mkPen(color=(0, 229, 255, 60), width=1)
            )
            self.pam4_eye_plot.addItem(curve)
            self.pam4_eye_curves.append(curve)

        if self.pam4_eye_mode == "centered":
            center_x = 0.5
            center_line = pg.PlotCurveItem(
                x=[center_x, center_x],
                y=[-1.5, 1.5],
                pen=pg.mkPen("#FFD54F", width=1.5, style=Qt.DashLine),
            )
            self.pam4_eye_plot.addItem(center_line)
            self.pam4_eye_curves.append(center_line)
            self.pam4_eye_plot.setTitle(
                f"PAM4 Common t_center Eye (Phase {self.pam4_t_center_phase}/{spb}, Score={self.pam4_t_center_score:.3f})"
            )
        else:
            self.pam4_eye_plot.setTitle("PAM4 Raw Eye Diagram after Channel")

        self.pam4_eye_plot.setXRange(0, EYE_UI)
        ymax = max(1.2, float(np.max(np.abs(ch_wave))) * 1.1)
        self.pam4_eye_plot.setYRange(-ymax, ymax)

    def update_pam4_info(self):
        c0, _, _, _, _, _, _, _, _, _ = calc_gen6_levels(
            self.pam4_cm2_current,
            self.pam4_cm1_current,
            self.pam4_cp1_current,
        )

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
        set_item(0, 1, "Mode:", "4-Tap FIR")
        set_item(0, 2, "Phase/Score:", f"{self.pam4_t_center_phase} / {self.pam4_t_center_score:.3f}")
        set_item(0, 3, "CH:", f"{self.pam4_alpha_current:.3f}")

        set_item(1, 0, "Taps:", f"{self.pam4_cm2_current:.3f} / {self.pam4_cm1_current:.3f} / {c0:.3f} / {self.pam4_cp1_current:.3f}")
        set_item(1, 1, "U/M/L:", f"{self.pam4_eye_metrics['upper_eye']:.3f} / {self.pam4_eye_metrics['middle_eye']:.3f} / {self.pam4_eye_metrics['lower_eye']:.3f}")
        set_item(1, 2, "Min Eye:", f"{self.pam4_eye_metrics['minimum_eye']:.4f}")
        set_item(1, 3, "Spread:", f"{self.pam4_eye_metrics['center_spread']:.4f}")

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
        ymax = max(1.2, float(np.max(np.abs(tx_wave[:length]))) * 1.1)
        self.wave_plot.setYRange(-ymax, ymax)

    def update_eye(self, wave, max_traces=MAX_EYE_TRACES):
        spb = SPB
        trace_len = EYE_UI * spb
        n_traces = min(max_traces, (len(wave) - trace_len) // spb)

        for curve in self.eye_curves:
            self.eye_plot.removeItem(curve)
        self.eye_curves.clear()

        if n_traces <= 0:
            return

        t = np.arange(trace_len) / spb

        for i in range(n_traces):
            start_idx = i * spb
            segment = wave[start_idx : start_idx + trace_len]
            if len(segment) < trace_len:
                continue

            curve = pg.PlotCurveItem(
                t, segment, pen=pg.mkPen(color=(0, 229, 255, 60), width=1)
            )
            self.eye_plot.addItem(curve)
            self.eye_curves.append(curve)

        self.eye_plot.setXRange(0, EYE_UI)
        ymax = max(1.2, float(np.max(np.abs(wave))) * 1.1)
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
