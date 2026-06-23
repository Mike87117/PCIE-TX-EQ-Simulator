import sys
import numpy as np
from contextlib import contextmanager
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QSlider, QLineEdit, QPushButton, QComboBox,
    QPlainTextEdit, QTabWidget
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
PAM4_SYMBOL_COUNT = 512
# Density eye rendering is not implemented; line eye rendering is always used.

# Approx preset values for simulation only (not PCIe compliance table).
PCIE_PRESET_DB_TABLE = {
    0: (0.0, -6.0),
    1: (0.0, -3.5),
    2: (0.0, -4.5),
    3: (0.0, -2.5),
    4: (0.0, 0.0),
    5: (1.9, 0.0),
    6: (2.5, 0.0),
    7: (3.5, -6.0),
    8: (3.5, -3.5),
    9: (3.5, 0.0),
    10: (0.0, -9.5),
}

PCIE_GEN6_PRESET_TAP_TABLE = {
    "Q0": (0.000, 0.000, 0.000),
    "Q1": (0.000, -0.083, 0.000),
    "Q2": (0.000, -0.167, 0.000),
    "Q3": (0.000, 0.000, -0.083),
    "Q4": (0.000, 0.000, -0.167),
    "Q5": (0.042, -0.208, 0.000),
    "Q6": (0.042, -0.125, -0.125),
    "Q7": (0.083, -0.208, 0.000),
    "Q8": (0.083, -0.250, 0.000),
    "Q9": (0.083, -0.250, -0.042),
}

np.random.seed(7)
bits = np.random.randint(0, 2, BIT_COUNT)
symbols = 2 * bits - 1

# =========================
# PCIe TX EQ math
# =========================

def calc_levels(cm1, cp1):
    c0 = 1 - abs(cm1) - abs(cp1)
    va = abs(cm1 * 1 + c0 * 1 + cp1 * -1)
    vb = abs(cm1 * 1 + c0 * 1 + cp1 * 1)
    vc = abs(cm1 * 1 + c0 * -1 + cp1 * -1)
    de_db = 20 * np.log10(vb / va) if va > 0 and vb > 0 else -99
    pre_db = 20 * np.log10(vc / vb) if vb > 0 and vc > 0 else 99
    return c0, va, vb, vc, pre_db, de_db


def db_to_taps(pre_db, de_db):
    eps = 1e-6

    # Pure preshoot: only C-1 active, C+1 ~ 0
    if abs(de_db) < eps and abs(pre_db) >= eps:
        r_pre = 10 ** (pre_db / 20)
        cm1 = (r_pre - 1) / (r_pre + 1)
        cp1 = 0.0
        cm1 = float(np.clip(cm1, 0.0, 0.45))
        return cm1, cp1

    # Pure de-emphasis: only C+1 active, C-1 ~ 0
    if abs(pre_db) < eps and abs(de_db) >= eps:
        r_de = 10 ** (de_db / 20)
        cp1_mag = (1 - r_de) / (1 + r_de)
        cm1 = 0.0
        cp1 = -float(np.clip(cp1_mag, 0.0, 0.45))
        return cm1, cp1

    # Mixed mode
    r_de = 10 ** (de_db / 20)
    r_pre = 10 ** (pre_db / 20)
    denom = (1 - r_de) + r_pre * r_de
    va = 1 / denom
    p = (1 - va) / 2
    q = va * (1 - r_de) / 2
    p = np.clip(p, 0, 0.45)
    q = np.clip(q, 0, 0.45)
    if p + q >= 0.49:
        scale = 0.49 / (p + q)
        p *= scale
        q *= scale
    cm1 = float(p)
    cp1 = -float(q)

    # Keep |C-1|+|C0|+|C+1| normalized and robust numerically.
    c0 = 1 - abs(cm1) - abs(cp1)
    norm = abs(cm1) + abs(c0) + abs(cp1)
    if norm > eps:
        cm1 /= norm
        cp1 /= norm

    return cm1, cp1


def tx_fir(symbols_in, cm1, cp1):
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


def pam4_symbols_from_random(count):
    levels = np.array([-3.0, -1.0, 1.0, 3.0], dtype=float) / 3.0
    return levels[np.random.randint(0, 4, count)]


def constrain_gen6_taps(cm2, cm1, cp1):
    cm2 = float(np.clip(abs(cm2), 0.0, 0.25))
    cm1 = float(np.clip(-abs(cm1), -0.30, 0.0))
    cp1 = float(np.clip(-abs(cp1), -0.25, 0.0))
    tap_sum = abs(cm2) + abs(cm1) + abs(cp1)
    if tap_sum >= 0.95:
        scale = 0.95 / tap_sum
        cm2 *= scale
        cm1 *= scale
        cp1 *= scale
    return cm2, cm1, cp1


def calc_gen6_levels(cm2, cm1, cp1):
    cm2, cm1, cp1 = constrain_gen6_taps(cm2, cm1, cp1)
    c0 = 1.0 - abs(cm2) - abs(cm1) - abs(cp1)
    va = abs(cm2 + cm1 + c0 - cp1)
    vb = abs(cm2 + cm1 + c0 + cp1)
    vc1 = abs(cm2 - cm1 + c0 + cp1)
    vc2 = abs(-cm2 + cm1 + c0 + cp1)
    vd = abs(cm2 - cm1 + c0 - cp1)
    de_db = 20 * np.log10(vb / va) if va > 0 and vb > 0 else -99
    pre1_db = 20 * np.log10(vc1 / vb) if vb > 0 and vc1 > 0 else -99
    pre2_db = 20 * np.log10(vc2 / vb) if vb > 0 and vc2 > 0 else -99
    boost_db = 20 * np.log10(vd / vb) if vb > 0 and vd > 0 else -99
    return c0, va, vb, vc1, vc2, vd, pre1_db, pre2_db, de_db, boost_db


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


def gen6_pam4_fir(symbols_in, cm2, cm1, cp1):
    cm2, cm1, cp1 = constrain_gen6_taps(cm2, cm1, cp1)
    c0 = 1.0 - abs(cm2) - abs(cm1) - abs(cp1)
    padded = np.pad(symbols_in, (2, 1), mode="edge")
    y = []
    for i in range(2, len(padded) - 1):
        prev2_sym = padded[i - 2]
        prev_sym = padded[i - 1]
        now_sym = padded[i]
        next_sym = padded[i + 1]
        out = (
            cm2 * prev2_sym +
            cm1 * prev_sym +
            c0 * now_sym +
            cp1 * next_sym
        )
        y.append(out)
    return np.array(y), c0


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
        self.nrz_show_detail = False

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

        self.gen6_preset_current = "Q0"
        self.pam4_cm2_current = 0.0
        self.pam4_cm1_current = 0.0
        self.pam4_cp1_current = 0.0
        self.pam4_alpha_current = 0.08
        self.pam4_show_detail = False
        self.pam4_eye_mode = "raw"
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
        self.info_text.setMinimumHeight(120)
        self.info_text.setMaximumHeight(150)
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
        self.btn_reset_no_eq = QPushButton("Reset to No EQ")
        self.btn_reset_no_eq.clicked.connect(self.on_reset_no_eq)
        self.btn_reset_channel = QPushButton("Reset Channel")
        self.btn_reset_channel.clicked.connect(self.on_reset_channel)
        self.btn_reset_all = QPushButton("Reset EQ + Channel")
        self.btn_reset_all.clicked.connect(self.on_reset_all)
        self.btn_nrz_detail = QPushButton("Show Detail")
        self.btn_nrz_detail.clicked.connect(self.on_toggle_nrz_detail)
        for btn in (
            self.btn_new_wave,
            self.btn_reset_eq,
            self.btn_reset_no_eq,
            self.btn_reset_channel,
            self.btn_reset_all,
            self.btn_nrz_detail,
        ):
            btn.setFixedHeight(24)
            control_layout.addWidget(btn)
        layout.addLayout(control_layout)

        self.slider_cm1 = self.make_slider(
            "C-1", 0, 300, int(self.cm1_current * 1000)
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

        self.slider_cm1["edit"].setValidator(QDoubleValidator(0.0, 0.3, 4, self))
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

        self.init_pam4_tab()
        self.setCentralWidget(root)

    def init_pam4_tab(self):
        layout = QVBoxLayout(self.pam4_tab)

        self.pam4_wave_plot = pg.PlotWidget(title="PCIe Gen6 PAM4 TX EQ Waveform")
        self.pam4_wave_plot.setLabel("bottom", "Symbol / UI")
        self.pam4_wave_plot.setLabel("left", "Normalized Level")
        self.pam4_wave_plot.showGrid(x=True, y=True)

        self.pam4_eye_plot = pg.PlotWidget(title="PAM4 Eye Diagram after Simplified Channel")
        self.pam4_eye_plot.setLabel("bottom", "UI")
        self.pam4_eye_plot.setLabel("left", "Normalized Level")
        self.pam4_eye_plot.showGrid(x=True, y=True)

        self.pam4_tx_curve = self.pam4_wave_plot.plot(pen=pg.mkPen(width=2))
        self.pam4_ch_curve = self.pam4_wave_plot.plot(pen=pg.mkPen(width=2, style=Qt.DashLine))
        self.pam4_eye_curve = self.pam4_eye_plot.plot(pen=pg.mkPen(width=1))
        self.pam4_tx_curve.setDownsampling(auto=True)
        self.pam4_ch_curve.setDownsampling(auto=True)
        self.pam4_tx_curve.setClipToView(True)
        self.pam4_ch_curve.setClipToView(True)

        layout.addWidget(self.pam4_wave_plot, stretch=4)
        layout.addWidget(self.pam4_eye_plot, stretch=3)

        self.pam4_info_text = QPlainTextEdit()
        self.pam4_info_text.setReadOnly(True)
        self.pam4_info_text.setMinimumHeight(140)
        self.pam4_info_text.setMaximumHeight(170)
        self.pam4_info_text.setStyleSheet("font-size: 17px;")
        layout.addWidget(self.pam4_info_text)

        control_layout = QHBoxLayout()
        preset_label = QLabel("Gen6 Preset")
        preset_label.setFixedWidth(120)
        self.gen6_preset_combo = QComboBox()
        self.gen6_preset_combo.addItem("Custom")
        for q in range(11):
            label = f"Q{q}"
            if q == 10:
                label = "Q10 (special / Note 2)"
            self.gen6_preset_combo.addItem(label)
        self.gen6_preset_combo.currentIndexChanged.connect(self.on_gen6_preset_change)
        control_layout.addWidget(preset_label)
        control_layout.addWidget(self.gen6_preset_combo)

        eye_mode_label = QLabel("PAM4 Eye Mode")
        eye_mode_label.setFixedWidth(120)
        self.pam4_eye_mode_combo = QComboBox()
        self.pam4_eye_mode_combo.addItem("Raw Eye")
        self.pam4_eye_mode_combo.addItem("Centered Eye")
        self.pam4_eye_mode_combo.currentIndexChanged.connect(self.on_pam4_eye_mode_change)
        control_layout.addWidget(eye_mode_label)
        control_layout.addWidget(self.pam4_eye_mode_combo)

        self.btn_pam4_new_wave = QPushButton("Generate New PAM4 Waveform")
        self.btn_pam4_new_wave.clicked.connect(self.on_pam4_generate_new_waveform)
        self.btn_pam4_reset_eq = QPushButton("Reset PAM4 EQ")
        self.btn_pam4_reset_eq.clicked.connect(self.on_pam4_reset_eq)
        self.btn_pam4_reset_channel = QPushButton("Reset PAM4 Channel")
        self.btn_pam4_reset_channel.clicked.connect(self.on_pam4_reset_channel)
        self.btn_pam4_detail = QPushButton("Show Detail")
        self.btn_pam4_detail.clicked.connect(self.on_toggle_pam4_detail)
        for btn in (
            self.btn_pam4_new_wave,
            self.btn_pam4_reset_eq,
            self.btn_pam4_reset_channel,
            self.btn_pam4_detail,
        ):
            btn.setFixedHeight(24)
            control_layout.addWidget(btn)
        layout.addLayout(control_layout)

        self.pam4_slider_cm2 = self.make_slider(
            "C-2", 0, 250, int(self.pam4_cm2_current * 1000)
        )
        self.pam4_slider_cm1 = self.make_slider(
            "C-1", -300, 0, int(self.pam4_cm1_current * 1000)
        )
        self.pam4_slider_cp1 = self.make_slider(
            "C+1", -250, 0, int(self.pam4_cp1_current * 1000)
        )
        self.pam4_slider_alpha = self.make_slider(
            "PAM4 Low-pass Alpha", 1, 300, int(self.pam4_alpha_current * 1000)
        )

        self.pam4_slider_cm2["edit"].setValidator(QDoubleValidator(0.0, 0.25, 4, self))
        self.pam4_slider_cm1["edit"].setValidator(QDoubleValidator(-0.30, 0.0, 4, self))
        self.pam4_slider_cp1["edit"].setValidator(QDoubleValidator(-0.25, 0.0, 4, self))
        self.pam4_slider_alpha["edit"].setValidator(QDoubleValidator(0.001, 0.3, 3, self))

        layout.addLayout(self.pam4_slider_cm2["layout"])
        layout.addLayout(self.pam4_slider_cm1["layout"])
        layout.addLayout(self.pam4_slider_cp1["layout"])
        layout.addLayout(self.pam4_slider_alpha["layout"])

        self.pam4_slider_cm2["slider"].valueChanged.connect(self.on_pam4_slider_change)
        self.pam4_slider_cm1["slider"].valueChanged.connect(self.on_pam4_slider_change)
        self.pam4_slider_cp1["slider"].valueChanged.connect(self.on_pam4_slider_change)
        self.pam4_slider_alpha["slider"].valueChanged.connect(self.on_pam4_slider_change)

        self.pam4_slider_cm2["edit"].editingFinished.connect(lambda: self.on_pam4_edit_change("cm2"))
        self.pam4_slider_cm1["edit"].editingFinished.connect(lambda: self.on_pam4_edit_change("cm1"))
        self.pam4_slider_cp1["edit"].editingFinished.connect(lambda: self.on_pam4_edit_change("cp1"))
        self.pam4_slider_alpha["edit"].editingFinished.connect(lambda: self.on_pam4_edit_change("alpha"))

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
        cm1 = float(np.clip(abs(cm1), 0.0, 0.3))
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
                self.update_nrz_realtime()
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

    def on_toggle_nrz_detail(self):
        self.nrz_show_detail = not self.nrz_show_detail
        self.btn_nrz_detail.setText("Hide Detail" if self.nrz_show_detail else "Show Detail")
        self.update_info()

    def update_waveform_only(self):
        tx_sym = self.make_tx_symbols()
        tx_wave = np.repeat(tx_sym, SPB)
        ch_wave = simple_channel(tx_wave, alpha=self.channel_alpha_current)

        self.update_waveform(tx_wave, ch_wave)

    def update_nrz_realtime(self):
        tx_sym = self.make_tx_symbols()
        tx_wave = np.repeat(tx_sym, SPB)
        ch_wave = simple_channel(tx_wave, alpha=self.channel_alpha_current)

        self.update_waveform(tx_wave, ch_wave)
        self.update_eye(ch_wave)
        self.update_eye_metrics(ch_wave)
        self.update_info()

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
            if target == "Q10":
                target = "Q10 (special / Note 2)"
            idx = self.gen6_preset_combo.findText(target)
            if idx >= 0:
                self.gen6_preset_combo.setCurrentIndex(idx)
        finally:
            self.gen6_preset_combo.blockSignals(False)

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

        if preset_name.startswith("Q10"):
            self.gen6_preset_current = "Q10"
            self.pam4_cm2_current = 0.0
            self.pam4_cm1_current = 0.0
            self.pam4_cp1_current = 0.0
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
        mode_text = self.pam4_eye_mode_combo.currentText()
        self.pam4_eye_mode = "centered" if mode_text == "Centered Eye" else "raw"
        self.pam4_redraw_all()

    def on_toggle_pam4_detail(self):
        self.pam4_show_detail = not self.pam4_show_detail
        self.btn_pam4_detail.setText("Hide Detail" if self.pam4_show_detail else "Show Detail")
        self.update_pam4_info()

    def pam4_full_refresh(self):
        with self.ui_sync() as active:
            if not active:
                return
            self.pam4_sync_ui_from_state(update_edits=True)
            self.pam4_redraw_all()

    def pam4_make_tx_symbols(self):
        tx_sym, _ = gen6_pam4_fir(
            self.pam4_symbols,
            self.pam4_cm2_current,
            self.pam4_cm1_current,
            self.pam4_cp1_current,
        )
        return tx_sym

    def pam4_redraw_all(self):
        tx_sym = self.pam4_make_tx_symbols()
        tx_wave = np.repeat(tx_sym, SPB)
        ch_wave = simple_channel(tx_wave, alpha=self.pam4_alpha_current)

        self.update_pam4_waveform(tx_wave, ch_wave)
        self.update_pam4_eye(ch_wave)
        self.update_pam4_eye_metrics(ch_wave)
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
        x_all = np.empty(sampled_starts.size * (seg_len + 1), dtype=float)
        y_all = np.empty(sampled_starts.size * (seg_len + 1), dtype=float)
        search_start = int(0.35 * SPB)
        search_end = min(int(1.65 * SPB), seg_len - 1)
        for idx, s in enumerate(sampled_starts):
            base = idx * (seg_len + 1)
            segment = wave[s:s + seg_len]
            x_shift = 0.0
            if search_end > search_start:
                diff = np.abs(np.diff(segment))
                search_diff = diff[search_start:search_end]
                if search_diff.size > 0 and np.max(search_diff) > 1e-6:
                    peak_idx = int(np.argmax(search_diff) + search_start)
                    transition_x = peak_idx / SPB
                    if 0.0 <= transition_x <= EYE_UI:
                        x_shift = float(np.clip(1.0 - transition_x, -0.35, 0.35))
            x_all[base:base + seg_len] = x + x_shift
            y_all[base:base + seg_len] = segment
            x_all[base + seg_len] = np.nan
            y_all[base + seg_len] = np.nan

        self.pam4_eye_curve.setData(x_all, y_all)
        self.pam4_eye_plot.setXRange(0, EYE_UI, padding=0)
        self.pam4_eye_plot.setYRange(-1.4, 1.4)

    def update_pam4_eye_metrics(self, wave):
        seg_len = EYE_UI * SPB
        start = 20 * SPB
        trace_starts = np.arange(start, len(wave) - seg_len, SPB, dtype=int)
        if trace_starts.size == 0:
            self.pam4_eye_metrics = {
                "upper_eye": 0.0,
                "middle_eye": 0.0,
                "lower_eye": 0.0,
                "minimum_eye": 0.0,
                "center_spread": 0.0,
            }
            return

        if trace_starts.size > MAX_EYE_TRACES:
            idx = np.linspace(0, trace_starts.size - 1, MAX_EYE_TRACES, dtype=int)
            sampled_starts = trace_starts[idx]
        else:
            sampled_starts = trace_starts

        segs = np.array([wave[s:s + seg_len] for s in sampled_starts], dtype=float)
        center_idx = seg_len // 2
        center_samples = segs[:, center_idx]
        center_spread = float(np.max(center_samples) - np.min(center_samples))

        lower_band = center_samples[center_samples < -2 / 3]
        mid_low_band = center_samples[
            (center_samples >= -2 / 3) & (center_samples < 0)
        ]
        mid_high_band = center_samples[
            (center_samples >= 0) & (center_samples < 2 / 3)
        ]
        upper_band = center_samples[center_samples >= 2 / 3]

        def eye_gap(left, right):
            if left.size == 0 or right.size == 0:
                return 0.0
            return float(np.percentile(right, 5) - np.percentile(left, 95))

        lower_eye = eye_gap(lower_band, mid_low_band)
        middle_eye = eye_gap(mid_low_band, mid_high_band)
        upper_eye = eye_gap(mid_high_band, upper_band)
        positive_openings = [
            value for value in (upper_eye, middle_eye, lower_eye) if value > 0
        ]
        minimum_eye = min(positive_openings) if positive_openings else 0.0

        self.pam4_eye_metrics = {
            "upper_eye": upper_eye,
            "middle_eye": middle_eye,
            "lower_eye": lower_eye,
            "minimum_eye": minimum_eye,
            "center_spread": center_spread,
        }

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
        eye_mode_text = "Centered Eye" if self.pam4_eye_mode == "centered" else "Raw Eye"
        q10_note = ""
        if self.gen6_preset_current == "Q10":
            q10_note = (
                " Q10 is a special preset / Note 2 and is not explicitly modeled. "
                "Coefficients are reset to Q0 for visualization safety."
            )
        if self.pam4_show_detail:
            text = (
                "Teaching Focus: PAM4 uses four levels and three eyes; this tab uses a simplified 4-tap FIR concept. "
                "C0 is automatically calculated from C-2 / C-1 / C+1.\n\n"
                f"Preset / Tap: Gen6 Preset = {self.gen6_preset_current}    "
                f"C-2 = {self.pam4_cm2_current:.4f}    "
                f"C-1 = {self.pam4_cm1_current:.4f}    "
                f"C0 = {c0:.4f}    "
                f"C+1 = {self.pam4_cp1_current:.4f}    "
                f"TapSum = {tap_sum:.4f}\n\n"
                f"Level / Ratio: Va = {va:.4f}    "
                f"Vb = {vb:.4f}    "
                f"Vc1 = {vc1:.4f}    "
                f"Vc2 = {vc2:.4f}    "
                f"Vd = {vd:.4f}\n"
                f"Va/Vd = {va_ratio:.3f}    "
                f"Vb/Vd = {vb_ratio:.3f}    "
                f"Vc1/Vd = {vc1_ratio:.3f}    "
                f"Vc2/Vd = {vc2_ratio:.3f}\n\n"
                f"dB Metrics: De-emphasis = {de_db:.2f} dB    "
                f"Preshoot 1 = {pre1_db:.2f} dB    "
                f"Preshoot 2 = {pre2_db:.2f} dB    "
                f"Boost = {boost_db:.2f} dB    "
                f"Low-pass Alpha = {self.pam4_alpha_current:.3f}    "
                f"Eye Mode = {eye_mode_text}\n\n"
                f"Eye Metrics: Upper Eye Opening = {self.pam4_eye_metrics['upper_eye']:.4f}    "
                f"Middle Eye Opening = {self.pam4_eye_metrics['middle_eye']:.4f}    "
                f"Lower Eye Opening = {self.pam4_eye_metrics['lower_eye']:.4f}    "
                f"Minimum Eye Opening = {self.pam4_eye_metrics['minimum_eye']:.4f}    "
                f"Center UI Spread = {self.pam4_eye_metrics['center_spread']:.4f}\n\n"
                f"Note: simplified visualization only. "
                f"This is not a PCIe compliance calculator. "
                f"Centered Eye horizontally shifts each eye trace so detected transition centers align near x = 1 UI. "
                f"The PAM4 levels and three eyes remain unchanged.{q10_note}"
            )
        else:
            text = (
                "Teaching Focus: PAM4 has 4 levels and 3 eyes; this tab uses simplified 4-tap FIR.\n"
                f"Preset = {self.gen6_preset_current}    Low-pass Alpha = {self.pam4_alpha_current:.3f}    "
                f"Eye Mode = {eye_mode_text}\n"
                f"C-2 = {self.pam4_cm2_current:.4f}    C-1 = {self.pam4_cm1_current:.4f}    "
                f"C0 = {c0:.4f}    C+1 = {self.pam4_cp1_current:.4f}\n"
                f"De-emphasis = {de_db:.2f} dB    Preshoot 1 = {pre1_db:.2f} dB    "
                f"Preshoot 2 = {pre2_db:.2f} dB    Boost = {boost_db:.2f} dB\n"
                f"Upper Eye = {self.pam4_eye_metrics['upper_eye']:.4f}    "
                f"Middle Eye = {self.pam4_eye_metrics['middle_eye']:.4f}    "
                f"Lower Eye = {self.pam4_eye_metrics['lower_eye']:.4f}    "
                f"Minimum Eye = {self.pam4_eye_metrics['minimum_eye']:.4f}"
            )
        self.pam4_info_text.setPlainText(text)

    def make_tx_symbols(self):
        if self.control_mode == "tap":
            tx_sym, _ = tx_fir(self.symbols, self.cm1_current, self.cp1_current)
            return tx_sym
        return tx_eq_pattern(self.symbols, self.pre_db_current, self.de_db_current)

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
        # Density eye is not implemented; always render the line eye diagram.
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
        Density eye rendering is not implemented.

        This method is intentionally not reachable from the UI so the simulator
        does not suggest that density eye mode is available.
        """
        raise NotImplementedError("Density eye rendering is not implemented.")

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
        c0, va, vb, vc, _, _ = calc_levels(self.cm1_current, self.cp1_current)
        tap_sum = abs(self.cm1_current) + abs(c0) + abs(self.cp1_current)

        if self.nrz_show_detail:
            text = (
                "Teaching Focus: Preshoot raises the last bit before a transition. "
                "De-emphasis lowers repeated bits. "
                "dB mode is for level-based visualization. "
                "Tap mode is a FIR coefficient reference.\n\n"
                f"EQ State: Preset = {self.current_preset}    "
                f"Control Mode = {self.control_mode}    "
                f"Preshoot = {self.pre_db_current:.2f} dB    "
                f"De-emphasis = {self.de_db_current:.2f} dB    "
                f"Low-pass Alpha = {self.channel_alpha_current:.3f} (smaller = more ISI)\n\n"
                f"Tap / Level Reference: C-1 = {self.cm1_current:.4f}    "
                f"C0 = {c0:.4f}    "
                f"C+1 = {self.cp1_current:.4f}    "
                f"Va = {va:.4f}    "
                f"Vb = {vb:.4f}    "
                f"Vc = {vc:.4f}    "
                f"TapSum = {tap_sum:.4f}\n\n"
                f"Eye Metrics: Eye Height = {self.eye_metrics['eye_height']:.4f}    "
                f"Eye Max = {self.eye_metrics['eye_max']:.4f}    "
                f"Eye Min = {self.eye_metrics['eye_min']:.4f}    "
                f"Center UI Spread = {self.eye_metrics['center_spread']:.4f}\n\n"
                f"Note: This is a teaching simulator, not a PCIe compliance tool. "
                f"Preset values are approximate and for visualization only. "
                f"Low-pass Alpha is a simplified ISI model, not a real PCIe channel model."
            )
        else:
            text = (
                "Teaching Focus: Preshoot raises the bit before transition; De-emphasis lowers repeated bits.\n"
                f"Preset = {self.current_preset}    Mode = {self.control_mode}    "
                f"Low-pass Alpha = {self.channel_alpha_current:.3f}\n"
                f"Preshoot = {self.pre_db_current:.2f} dB    De-emphasis = {self.de_db_current:.2f} dB    "
                f"C-1 = {self.cm1_current:.4f}    C0 = {c0:.4f}    C+1 = {self.cp1_current:.4f}\n"
                f"Va = {va:.4f}    Vb = {vb:.4f}    Vc = {vc:.4f}\n"
                f"Eye Height = {self.eye_metrics['eye_height']:.4f}    "
                f"Center UI Spread = {self.eye_metrics['center_spread']:.4f}    "
                f"Teaching visualization only, not PCIe compliance."
            )

        self.info_text.setPlainText(text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = PCIeTxEqSimulator()
    win.show()
    sys.exit(app.exec_())
