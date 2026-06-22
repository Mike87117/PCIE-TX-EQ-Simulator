import sys
import numpy as np
from contextlib import contextmanager
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QSlider, QLineEdit, QPushButton, QComboBox,
    QPlainTextEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator
import pyqtgraph as pg

# =========================
# Basic parameters
# =========================

BIT_COUNT = 512
SPB = 32
PLOT_BITS = 64
EYE_UI = 2
MAX_EYE_TRACES = 200
EYE_RENDER_MODE = "line"  # "line" | "density" (reserved)

# Approx preset values for visualization only. This is not a PCIe compliance
# table and the channel model below is intentionally simplified.
PCIE_PRESET_DB_TABLE = {
    0: (0.0, -6.0),
    1: (0.0, -3.5),
    2: (0.0, -4.4),
    3: (0.0, -2.5),
    4: (0.0, 0.0),
    5: (1.9, 0.0),
    6: (2.5, 0.0),
    7: (3.5, -6.0),
    8: (3.5, -3.5),
    9: (3.5, 0.0),
    10: (0.0, -9.5),
}

PRESET_TAP_TABLE = {
    0: (0.000, -0.250),
    1: (0.000, -0.167),
    2: (0.000, -0.200),
    3: (0.000, -0.125),
    4: (0.000, 0.000),
    5: (-0.100, 0.000),
    6: (-0.125, 0.000),
    7: (-0.100, -0.200),
    8: (-0.125, -0.125),
    9: (-0.166, 0.000),
}

np.random.seed(7)
bits = np.random.randint(0, 2, BIT_COUNT)
symbols = 2 * bits - 1

# =========================
# PCIe TX EQ math
# =========================

def calc_levels(cm1, cp1):
    cm1 = min(float(cm1), 0.0)
    cp1 = min(float(cp1), 0.0)
    c0 = 1 - abs(cm1) - abs(cp1)
    # Va: first UI after transition, Vb: repeated/de-emphasis level,
    # Vc: UI before transition/preshoot level.
    va = abs(cm1 * 1 + c0 * 1 + cp1 * -1)
    vb = abs(cm1 * 1 + c0 * 1 + cp1 * 1)
    vc = abs(cm1 * -1 + c0 * 1 + cp1 * 1)
    de_db = 20 * np.log10(vb / va) if va > 0 and vb > 0 else -99
    pre_db = 20 * np.log10(vc / vb) if vb > 0 and vc > 0 else 99
    return c0, va, vb, vc, pre_db, de_db


def db_to_taps(pre_db, de_db):
    eps = 1e-6
    pre_db = max(float(pre_db), 0.0)
    de_db = min(float(de_db), 0.0)

    r_pre = 10 ** (pre_db / 20)
    r_de = 10 ** (de_db / 20)
    va = 1.0 / (1.0 + r_de * (r_pre - 1.0))
    vc = r_pre * r_de * va

    cm1_mag = max(0.0, (1.0 - va) / 2.0)
    cp1_mag = max(0.0, (1.0 - vc) / 2.0)
    if cm1_mag + cp1_mag >= 0.49:
        scale = 0.49 / (cm1_mag + cp1_mag + eps)
        cm1_mag *= scale
        cp1_mag *= scale

    cm1 = -float(np.clip(cm1_mag, 0.0, 0.45))
    cp1 = -float(np.clip(cp1_mag, 0.0, 0.45))
    return cm1, cp1


def tx_fir(symbols_in, cm1, cp1):
    cm1 = min(float(cm1), 0.0)
    cp1 = min(float(cp1), 0.0)
    c0 = 1 - abs(cm1) - abs(cp1)
    padded = np.pad(symbols_in, (1, 1), mode="edge")
    y = []
    for i in range(1, len(padded) - 1):
        prev_bit = padded[i - 1]
        now_bit = padded[i]
        next_bit = padded[i + 1]
        out = (
            cm1 * next_bit +
            c0 * now_bit +
            cp1 * prev_bit
        )
        y.append(out)
    return np.array(y), c0


def simple_channel(wave, alpha=0.08):
    out = np.zeros_like(wave)
    out[0] = wave[0]
    for i in range(1, len(wave)):
        out[i] = out[i - 1] + alpha * (wave[i] - out[i - 1])
    return out


def tx_eq_pattern(symbols_in, preshoot_db, deemph_db):
    """
    Legacy/reference dB amplitude pattern helper.

    The simulator's main TX output path no longer uses this function; both dB
    mode and tap mode are converted to canonical FIR taps and rendered through
    tx_fir().
    """
    va = 1.0
    vb = 10 ** (deemph_db / 20)
    vc = vb * 10 ** (preshoot_db / 20)

    y = np.zeros_like(symbols_in, dtype=float)

    for i in range(len(symbols_in)):
        prev_bit = symbols_in[i - 1] if i > 0 else symbols_in[i]
        now_bit = symbols_in[i]
        next_bit = symbols_in[i + 1] if i < len(symbols_in) - 1 else symbols_in[i]

        is_before_transition = now_bit != next_bit
        is_repeated = now_bit == prev_bit

        if is_before_transition and is_repeated:
            amp = vc
        elif is_repeated:
            amp = vb
        else:
            amp = va

        y[i] = now_bit * amp

    return y


# =========================
# Main GUI
# =========================

class PCIeTxEqSimulator(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PCIe TX EQ Simulator - PyQtGraph")
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
        self.eye_metrics = {
            "eye_height": 0.0,
            "eye_max": 0.0,
            "eye_min": 0.0,
            "center_spread": 0.0,
        }
        self.bits = bits.copy()
        self.symbols = symbols.copy()

        self.init_ui()
        self.full_refresh()

    def init_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)

        pg.setConfigOptions(antialias=False)

        self.wave_plot = pg.PlotWidget(title="PCIe TX EQ Waveform")
        self.wave_plot.setLabel("bottom", "Bit / UI")
        self.wave_plot.setLabel("left", "Voltage")
        self.wave_plot.showGrid(x=True, y=True)

        self.eye_plot = pg.PlotWidget(title="Eye Diagram after Channel")
        self.eye_plot.setLabel("bottom", "UI")
        self.eye_plot.setLabel("left", "Voltage")
        self.eye_plot.showGrid(x=True, y=True)

        self.tx_curve = self.wave_plot.plot(pen=pg.mkPen(width=2))
        self.ch_curve = self.wave_plot.plot(pen=pg.mkPen(width=2, style=Qt.DashLine))
        self.eye_curve = self.eye_plot.plot(pen=pg.mkPen(width=1))
        self.eye_img = pg.ImageItem()
        self.eye_img.hide()
        self.eye_plot.addItem(self.eye_img)
        self.tx_curve.setDownsampling(auto=True)
        self.ch_curve.setDownsampling(auto=True)
        self.tx_curve.setClipToView(True)
        self.ch_curve.setClipToView(True)

        layout.addWidget(self.wave_plot, stretch=4)
        layout.addWidget(self.eye_plot, stretch=3)

        self.info_text = QPlainTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMinimumHeight(90)
        self.info_text.setMaximumHeight(120)
        self.info_text.setStyleSheet("font-size: 17px;")
        layout.addWidget(self.info_text)

        control_layout = QHBoxLayout()
        preset_label = QLabel("PCIe Preset")
        preset_label.setFixedWidth(120)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Custom")
        for p in range(11):
            self.preset_combo.addItem(f"Preset {p}")
        self.preset_combo.currentIndexChanged.connect(self.on_preset_change)
        control_layout.addWidget(preset_label)
        control_layout.addWidget(self.preset_combo)

        self.btn_new_wave = QPushButton("Generate New Waveform")
        self.btn_new_wave.clicked.connect(self.on_generate_new_waveform)
        self.btn_reset_eq = QPushButton("Reset EQ")
        self.btn_reset_eq.clicked.connect(self.on_reset_eq)
        self.btn_reset_channel = QPushButton("Reset Channel")
        self.btn_reset_channel.clicked.connect(self.on_reset_channel)
        self.btn_reset_all = QPushButton("Reset EQ + Channel")
        self.btn_reset_all.clicked.connect(self.on_reset_all)
        for btn in (
            self.btn_new_wave,
            self.btn_reset_eq,
            self.btn_reset_channel,
            self.btn_reset_all,
        ):
            btn.setFixedHeight(24)
            control_layout.addWidget(btn)
        layout.addLayout(control_layout)

        self.slider_cm1 = self.make_slider(
            "C-1", -300, 0, int(self.cm1_current * 1000)
        )
        self.slider_cp1 = self.make_slider(
            "C+1", -300, 0, int(self.cp1_current * 1000)
        )

        self.slider_pre = self.make_slider(
            "Preshoot dB", 0, 600, int(self.pre_db_current * 100)
        )

        self.slider_de = self.make_slider(
            "De-emphasis dB", -1200, 0, int(self.de_db_current * 100)
        )
        self.slider_alpha = self.make_slider(
            "Low-pass Alpha", 1, 300, int(self.channel_alpha_current * 1000)
        )

        self.slider_cm1["edit"].setValidator(QDoubleValidator(-0.3, 0.0, 4, self))
        self.slider_cp1["edit"].setValidator(QDoubleValidator(-0.3, 0.0, 4, self))
        self.slider_pre["edit"].setValidator(QDoubleValidator(0.0, 6.0, 2, self))
        self.slider_de["edit"].setValidator(QDoubleValidator(-12.0, 0.0, 2, self))

        layout.addLayout(self.slider_cm1["layout"])
        layout.addLayout(self.slider_cp1["layout"])
        layout.addLayout(self.slider_pre["layout"])
        layout.addLayout(self.slider_de["layout"])
        layout.addLayout(self.slider_alpha["layout"])

        self.slider_cm1["slider"].valueChanged.connect(self.on_tap_slider_change)
        self.slider_cp1["slider"].valueChanged.connect(self.on_tap_slider_change)

        self.slider_pre["slider"].valueChanged.connect(self.on_db_slider_change)
        self.slider_de["slider"].valueChanged.connect(self.on_db_slider_change)
        self.slider_alpha["slider"].valueChanged.connect(self.on_alpha_slider_change)

        for s in (
            self.slider_cm1["slider"],
            self.slider_cp1["slider"],
            self.slider_pre["slider"],
            self.slider_de["slider"],
            self.slider_alpha["slider"],
        ):
            s.sliderReleased.connect(self.on_slider_released)

        self.slider_cm1["edit"].editingFinished.connect(lambda: self.on_edit_change("cm1"))
        self.slider_cp1["edit"].editingFinished.connect(lambda: self.on_edit_change("cp1"))
        self.slider_pre["edit"].editingFinished.connect(lambda: self.on_edit_change("pre"))
        self.slider_de["edit"].editingFinished.connect(lambda: self.on_edit_change("de"))
        self.slider_alpha["edit"].editingFinished.connect(lambda: self.on_edit_change("alpha"))

        self.setCentralWidget(root)

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
        self.set_slider_value_silent(self.slider_pre["slider"], int(self.pre_db_current * 100))
        self.set_slider_value_silent(self.slider_de["slider"], int(self.de_db_current * 100))
        self.set_slider_value_silent(self.slider_alpha["slider"], int(self.channel_alpha_current * 1000))
        self.set_preset_combo_silent(self.current_preset)

        if not update_edits:
            return

        edit_rows = [
            (self.slider_cm1["edit"], f"{self.cm1_current:.4f}"),
            (self.slider_cp1["edit"], f"{self.cp1_current:.4f}"),
            (self.slider_pre["edit"], f"{self.pre_db_current:.2f}"),
            (self.slider_de["edit"], f"{self.de_db_current:.2f}"),
            (self.slider_alpha["edit"], f"{self.channel_alpha_current:.3f}"),
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
        if preset_id in PRESET_TAP_TABLE:
            cm1, cp1 = PRESET_TAP_TABLE[preset_id]
            self.cm1_current, self.cp1_current = self.enforce_tap_constraint(cm1, cp1)
            _, _, _, _, pre_db, de_db = calc_levels(self.cm1_current, self.cp1_current)
            self.pre_db_current = float(np.clip(pre_db, 0.0, 6.0))
            self.de_db_current = float(np.clip(de_db, -12.0, 0.0))
        else:
            # P10 is kept as approximate dB handling until its special preset
            # behavior is modeled explicitly.
            pre_db, de_db = PCIE_PRESET_DB_TABLE[preset_id]
            self.pre_db_current = float(np.clip(pre_db, 0.0, 6.0))
            self.de_db_current = float(np.clip(de_db, -12.0, 0.0))
            self.cm1_current, self.cp1_current = db_to_taps(
                self.pre_db_current, self.de_db_current
            )
        self.control_mode = "db"
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
                elif target == "pre":
                    self.control_mode = "db"
                    self.set_custom_preset()
                    pre_db = abs(float(self.slider_pre["edit"].text()))
                    self.pre_db_current = float(np.clip(pre_db, 0.0, 6.0))
                    self.cm1_current, self.cp1_current = db_to_taps(
                        self.pre_db_current, self.de_db_current
                    )
                elif target == "de":
                    self.control_mode = "db"
                    self.set_custom_preset()
                    de_db = -abs(float(self.slider_de["edit"].text()))
                    self.de_db_current = float(np.clip(de_db, -12.0, 0.0))
                    self.cm1_current, self.cp1_current = db_to_taps(
                        self.pre_db_current, self.de_db_current
                    )
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
                self.update_waveform_only()
            else:
                self.redraw_all()

    def on_db_slider_change(self):
        if self.syncing_ui:
            return

        with self.ui_sync() as active:
            if not active:
                return
            self.control_mode = "db"
            self.set_custom_preset()
            self.pre_db_current = self.slider_pre["slider"].value() / 100
            self.de_db_current = self.slider_de["slider"].value() / 100
            self.cm1_current, self.cp1_current = db_to_taps(
                self.pre_db_current, self.de_db_current
            )
            self.sync_ui_from_state(update_edits=True)
            if self.is_any_slider_down():
                self.update_waveform_only()
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
                self.update_waveform_only()
            else:
                self.redraw_all()

    def is_any_slider_down(self):
        return any(
            s["slider"].isSliderDown()
            for s in (self.slider_cm1, self.slider_cp1, self.slider_pre, self.slider_de, self.slider_alpha)
        )

    def on_slider_released(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
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

    def on_reset_eq(self):
        if self.syncing_ui:
            return
        with self.ui_sync() as active:
            if not active:
                return
            self.pre_db_current = 1.5
            self.de_db_current = -3.5
            self.cm1_current, self.cp1_current = db_to_taps(
                self.pre_db_current, self.de_db_current
            )
            self.current_preset = "Custom"
            self.control_mode = "db"
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
            self.pre_db_current = 1.5
            self.de_db_current = -3.5
            self.cm1_current, self.cp1_current = db_to_taps(
                self.pre_db_current, self.de_db_current
            )
            self.current_preset = "Custom"
            self.control_mode = "db"
            self.channel_alpha_current = 0.08
            self.sync_ui_from_state(update_edits=True)
            self.redraw_all()

    def update_waveform_only(self):
        tx_sym = self.make_tx_symbols()
        tx_wave = np.repeat(tx_sym, SPB)
        ch_wave = simple_channel(tx_wave, alpha=self.channel_alpha_current)

        self.update_waveform(tx_wave, ch_wave)

    def redraw_all(self):
        tx_sym = self.make_tx_symbols()
        tx_wave = np.repeat(tx_sym, SPB)
        ch_wave = simple_channel(tx_wave, alpha=self.channel_alpha_current)

        self.update_waveform(tx_wave, ch_wave)
        self.update_eye(ch_wave)
        self.update_eye_metrics(ch_wave)
        self.update_info()

    def full_refresh(self):
        with self.ui_sync() as active:
            if not active:
                return
            self.sync_ui_from_state(update_edits=True)
            self.redraw_all()

    def make_tx_symbols(self):
        tx_sym, _ = tx_fir(self.symbols, self.cm1_current, self.cp1_current)
        return tx_sym

    def update_waveform(self, tx_wave, ch_wave):
        length = PLOT_BITS * SPB
        t = np.arange(length) / SPB

        self.tx_curve.setData(t, tx_wave[:length])
        self.ch_curve.setData(t, ch_wave[:length])

        self.wave_plot.setXRange(0, PLOT_BITS)
        ymax = max(
            1.3,
            float(np.max(np.abs(tx_wave[:length]))),
            float(np.max(np.abs(ch_wave[:length]))),
        )
        ymax *= 1.1
        self.wave_plot.setYRange(-ymax, ymax)

    def update_eye(self, wave):
        if EYE_RENDER_MODE == "density":
            self.update_eye_density(wave)
            return
        self.update_eye_line(wave)

    def update_eye_line(self, wave):
        self.eye_img.hide()
        self.eye_curve.show()

        seg_len = EYE_UI * SPB
        start = 20 * SPB
        trace_starts = np.arange(start, len(wave) - seg_len, SPB, dtype=int)
        if trace_starts.size == 0:
            self.eye_curve.setData([], [])
            self.eye_plot.setXRange(0, EYE_UI)
            self.eye_plot.setYRange(-1.3, 1.3)
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

        self.eye_curve.setData(x_all, y_all)

        self.eye_plot.setXRange(0, EYE_UI)
        ymax = max(1.3, float(np.max(np.abs(wave))))
        ymax *= 1.1
        self.eye_plot.setYRange(-ymax, ymax)

    def update_eye_density(self, wave):
        """
        Reserved hook for future density-eye rendering.
        Planned path:
        1) build (x, y) cloud from eye segments
        2) np.histogram2d(...)
        3) self.eye_img.setImage(...)
        """
        self.eye_curve.hide()
        self.eye_img.show()
        self.eye_img.setImage(np.zeros((2, 2), dtype=float))
        self.eye_plot.setXRange(0, EYE_UI)
        self.eye_plot.setYRange(-1.3, 1.3)

    def update_eye_metrics(self, wave):
        seg_len = EYE_UI * SPB
        start = 20 * SPB
        trace_starts = np.arange(start, len(wave) - seg_len, SPB, dtype=int)
        if trace_starts.size == 0:
            self.eye_metrics = {
                "eye_height": 0.0,
                "eye_max": 0.0,
                "eye_min": 0.0,
                "center_spread": 0.0,
            }
            return

        if trace_starts.size > MAX_EYE_TRACES:
            idx = np.linspace(0, trace_starts.size - 1, MAX_EYE_TRACES, dtype=int)
            sampled_starts = trace_starts[idx]
        else:
            sampled_starts = trace_starts

        segs = np.array([wave[s:s + seg_len] for s in sampled_starts], dtype=float)
        eye_max = float(np.max(segs))
        eye_min = float(np.min(segs))
        eye_height = eye_max - eye_min

        center_idx = seg_len // 2
        center_samples = segs[:, center_idx]
        center_spread = float(np.max(center_samples) - np.min(center_samples))
        upper = center_samples[center_samples >= 0]
        lower = center_samples[center_samples < 0]
        if upper.size > 0 and lower.size > 0:
            eye_height = float(np.percentile(upper, 5) - np.percentile(lower, 95))
        else:
            eye_height = 0.0

        self.eye_metrics = {
            "eye_height": eye_height,
            "eye_max": eye_max,
            "eye_min": eye_min,
            "center_spread": center_spread,
        }

    def update_info(self):
        c0, va, vb, vc, pre_db, de_db = calc_levels(self.cm1_current, self.cp1_current)

        text = (
            f"C-1 = {self.cm1_current:.4f}    "
            f"C0 = {c0:.4f}    "
            f"C+1 = {self.cp1_current:.4f}    "
            f"|C-1| + |C0| + |C+1| = "
            f"{abs(self.cm1_current) + abs(c0) + abs(self.cp1_current):.4f}\n"
            f"Va = {va:.4f}    "
            f"Vb = {vb:.4f}    "
            f"Vc = {vc:.4f}    "
            f"De-emphasis = {de_db:.2f} dB    "
            f"Preshoot = {pre_db:.2f} dB    "
            f"Control Mode = {self.control_mode}    "
            f"Preset = {self.current_preset}    "
            f"Low-pass Alpha = {self.channel_alpha_current:.3f} (smaller = more ISI)\n"
            f"Preset values are approximate and for visualization only. "
            f"This is not a PCIe compliance tool. "
            f"Low-pass Alpha is a simplified ISI model, not a real PCIe channel model.\n"
            f"Approx Eye Height = {self.eye_metrics['eye_height']:.4f}    "
            f"Eye Max = {self.eye_metrics['eye_max']:.4f}    "
            f"Eye Min = {self.eye_metrics['eye_min']:.4f}    "
            f"Center UI spread = {self.eye_metrics['center_spread']:.4f}"
        )

        self.info_text.setPlainText(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = PCIeTxEqSimulator()
    win.show()
    sys.exit(app.exec_())
