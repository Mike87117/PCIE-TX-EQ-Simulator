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
# RX EQ math (NRZ only for Phase 1)
# =========================

def apply_ctle(wave, gain, alpha=0.08):
    """
    Simplified visual CTLE model.
    lowpass = simple_channel(wave)
    high_freq = wave - lowpass
    ctle = wave + gain * high_freq
    """
    if gain <= 0.0:
        return wave
    lowpass = simple_channel(wave, alpha=alpha)
    high_freq = wave - lowpass
    ctle = wave + gain * high_freq
    return ctle


def apply_dfe(ctle_wave, taps, spb, sampling_phase):
    """
    Symbol-rate Decision Feedback Equalizer.
    It uses previous slicer decisions to subtract estimated post-cursor ISI.

    Sign convention:
    corrected_sample[n] = sample[n] - tap1 * decision[n-1]
                                      - tap2 * decision[n-2]
                                      - tap3 * decision[n-3]

    Positive tap subtracts a positive post-cursor contribution when the previous decision is +1.
    Negative tap adds compensation in the opposite direction.

    This is a manual educational DFE model, not adaptive LMS and not PCIe compliance behavior.
    
    NOTE: DFE operates at symbol rate on sampling points. It does not
    generate a real analog waveform.
    """
    num_symbols = len(ctle_wave) // spb
    samples = np.zeros(num_symbols)
    for i in range(num_symbols):
        idx = i * spb + sampling_phase
        if idx < len(ctle_wave):
            samples[i] = ctle_wave[idx]
        else:
            samples[i] = ctle_wave[-1]

    decisions = np.zeros(num_symbols)
    corrected_samples = np.zeros(num_symbols)
    
    for i in range(num_symbols):
        feedback = 0.0
        for j, tap in enumerate(taps):
            prev_idx = i - 1 - j
            if prev_idx >= 0:
                feedback += tap * decisions[prev_idx]
                
        val = samples[i] - feedback
        corrected_samples[i] = val
        decisions[i] = 1.0 if val >= 0 else -1.0
        
    return samples, corrected_samples, decisions


def run_rx_pipeline(ch_wave, ctle_gain, ctle_alpha, dfe_taps, spb, sampling_phase):
    ctle_wave = apply_ctle(ch_wave, ctle_gain, alpha=ctle_alpha)
    samples, corrected_samples, decisions = apply_dfe(
        ctle_wave, dfe_taps, spb, sampling_phase
    )
    
    return {
        "ch_wave": ch_wave,
        "ctle_wave": ctle_wave,
        "dfe_input_samples": samples,
        "dfe_corrected_samples": corrected_samples,
        "dfe_decisions": decisions
    }


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

        self.tx_curve = self.wave_plot.plot(pen=pg.mkPen(width=2))
        self.ch_curve = self.wave_plot.plot(pen=pg.mkPen(width=2, style=Qt.DashLine))
        self.rx_curve = self.wave_plot.plot(pen=pg.mkPen(color='g', width=2))
        self.eye_curve = self.eye_plot.plot(pen=pg.mkPen(width=1))
        self.tx_curve.setDownsampling(auto=True)
        self.ch_curve.setDownsampling(auto=True)
        self.rx_curve.setDownsampling(auto=True)
        self.tx_curve.setClipToView(True)
        self.ch_curve.setClipToView(True)
        self.rx_curve.setClipToView(True)

        layout.addWidget(self.wave_plot, stretch=4)
        layout.addWidget(self.eye_plot, stretch=3)

        self.status_panel = QFrame()
        self.status_panel.setMinimumHeight(90)
        self.status_panel.setMaximumHeight(110)
        self.status_panel.setStyleSheet("""
            QFrame {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                background-color: #f9f9f9;
            }
        """)
        
        self.status_layout = QGridLayout(self.status_panel)
        self.status_layout.setContentsMargins(8, 4, 8, 4)
        self.status_layout.setSpacing(4)
        self.status_items = {}
        
        for r in range(2):
            for c in range(4):
                container = QWidget()
                hlay = QHBoxLayout(container)
                hlay.setContentsMargins(0, 0, 0, 0)
                hlay.setSpacing(4)
                lbl = QLabel()
                lbl.setStyleSheet("font-size: 13px; color: #555; border: none; background: transparent;")
                val = QLabel()
                val.setStyleSheet("font-size: 16px; font-weight: bold; color: #111; border: none; background: transparent;")
                hlay.addWidget(lbl)
                hlay.addWidget(val)
                hlay.addStretch()
                self.status_layout.addWidget(container, r, c)
                self.status_items[(r, c)] = (lbl, val)
                
        layout.addWidget(self.status_panel)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(210)
        scroll.setMinimumHeight(160)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)

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
        self.btn_reset_no_eq = QPushButton("Reset to TX EQ")
        self.btn_reset_no_eq.clicked.connect(self.on_reset_no_eq)
        self.btn_reset_channel = QPushButton("Reset Channel")
        self.btn_reset_channel.clicked.connect(self.on_reset_channel)
        self.btn_reset_all = QPushButton("Reset All")
        self.btn_reset_all.clicked.connect(self.on_reset_all)
        self.btn_nrz_detail = QPushButton("Detail")
        self.btn_nrz_detail.clicked.connect(self.on_toggle_nrz_detail)
        self.btn_nrz_detail.setMaximumWidth(120)
        for btn in (
            self.btn_new_wave,
            self.btn_reset_no_eq,
            self.btn_reset_channel,
            self.btn_reset_all,
            self.btn_nrz_detail,
        ):
            btn.setFixedHeight(24)
            if btn is not self.btn_nrz_detail:
                btn.setMaximumWidth(160)
            control_layout.addWidget(btn)
        bottom_layout.addLayout(control_layout)

        sliders_layout = QHBoxLayout()
        
        tx_group = QGroupBox("TX EQ / Channel")
        rx_group = QGroupBox("RX EQ")
        
        group_box_style = """
        QGroupBox {
            font-weight: bold;
            border: 1px solid #b0b0b0;
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }
        """
        tx_group.setStyleSheet(group_box_style)
        rx_group.setStyleSheet(group_box_style)
        
        tx_layout = QVBoxLayout(tx_group)
        rx_layout = QVBoxLayout(rx_group)

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

        tx_layout.addLayout(self.slider_cm1["layout"])
        tx_layout.addLayout(self.slider_cp1["layout"])
        tx_layout.addLayout(self.slider_pre["layout"])
        tx_layout.addLayout(self.slider_de["layout"])
        tx_layout.addLayout(self.slider_alpha["layout"])
        tx_layout.addStretch()

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

        # RX EQ Section
        rx_control_layout = QHBoxLayout()
        rx_view_label = QLabel("RX Eye/Wave View")
        rx_view_label.setFixedWidth(120)
        self.rx_view_combo = QComboBox()
        self.rx_view_combo.addItems(["Channel (Before RX EQ)", "CTLE", "DFE (Sample Margin)"])
        self.rx_view_combo.currentIndexChanged.connect(self.on_rx_view_change)
        rx_control_layout.addWidget(rx_view_label)
        rx_control_layout.addWidget(self.rx_view_combo)
        
        self.btn_reset_rx = QPushButton("Reset RX EQ")
        self.btn_reset_rx.setFixedHeight(24)
        self.btn_reset_rx.clicked.connect(self.on_reset_rx)
        rx_control_layout.addWidget(self.btn_reset_rx)
        rx_layout.addLayout(rx_control_layout)

        self.slider_ctle = self.make_slider("CTLE Boost", 0, 1000, int(self.ctle_boost_current * 1000))
        self.slider_dfe1 = self.make_slider("DFE Tap 1", -500, 500, int(self.dfe_tap1_current * 1000))
        self.slider_dfe2 = self.make_slider("DFE Tap 2", -500, 500, int(self.dfe_tap2_current * 1000))
        self.slider_dfe3 = self.make_slider("DFE Tap 3", -500, 500, int(self.dfe_tap3_current * 1000))
        
        self.slider_ctle["edit"].setValidator(QDoubleValidator(0.0, 1.0, 3, self))
        self.slider_dfe1["edit"].setValidator(QDoubleValidator(-0.5, 0.5, 3, self))
        self.slider_dfe2["edit"].setValidator(QDoubleValidator(-0.5, 0.5, 3, self))
        self.slider_dfe3["edit"].setValidator(QDoubleValidator(-0.5, 0.5, 3, self))
        
        rx_layout.addLayout(self.slider_ctle["layout"])
        rx_layout.addLayout(self.slider_dfe1["layout"])
        rx_layout.addLayout(self.slider_dfe2["layout"])
        rx_layout.addLayout(self.slider_dfe3["layout"])
        rx_layout.addStretch()
        
        self.slider_ctle["slider"].valueChanged.connect(self.on_rx_slider_change)
        self.slider_dfe1["slider"].valueChanged.connect(self.on_rx_slider_change)
        self.slider_dfe2["slider"].valueChanged.connect(self.on_rx_slider_change)
        self.slider_dfe3["slider"].valueChanged.connect(self.on_rx_slider_change)
        
        for s in (self.slider_ctle["slider"], self.slider_dfe1["slider"], self.slider_dfe2["slider"], self.slider_dfe3["slider"]):
            s.sliderReleased.connect(self.on_slider_released)
            
        self.slider_ctle["edit"].editingFinished.connect(lambda: self.on_rx_edit_change("ctle"))
        self.slider_dfe1["edit"].editingFinished.connect(lambda: self.on_rx_edit_change("dfe1"))
        self.slider_dfe2["edit"].editingFinished.connect(lambda: self.on_rx_edit_change("dfe2"))
        self.slider_dfe3["edit"].editingFinished.connect(lambda: self.on_rx_edit_change("dfe3"))

        sliders_layout.addWidget(tx_group)
        sliders_layout.addWidget(rx_group)
        bottom_layout.addLayout(sliders_layout)
        
        scroll.setWidget(bottom_widget)
        layout.addWidget(scroll, stretch=0)

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

        self.pam4_status_panel = QFrame()
        self.pam4_status_panel.setMinimumHeight(90)
        self.pam4_status_panel.setMaximumHeight(110)
        self.pam4_status_panel.setStyleSheet("""
            QFrame {
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                background-color: #f9f9f9;
            }
        """)
        
        self.pam4_status_layout = QGridLayout(self.pam4_status_panel)
        self.pam4_status_layout.setContentsMargins(8, 4, 8, 4)
        self.pam4_status_layout.setSpacing(4)
        self.pam4_status_items = {}
        
        for r in range(2):
            for c in range(4):
                container = QWidget()
                hlay = QHBoxLayout(container)
                hlay.setContentsMargins(0, 0, 0, 0)
                hlay.setSpacing(4)
                lbl = QLabel()
                lbl.setStyleSheet("font-size: 13px; color: #555; border: none; background: transparent;")
                val = QLabel()
                val.setStyleSheet("font-size: 16px; font-weight: bold; color: #111; border: none; background: transparent;")
                hlay.addWidget(lbl)
                hlay.addWidget(val)
                hlay.addStretch()
                self.pam4_status_layout.addWidget(container, r, c)
                self.pam4_status_items[(r, c)] = (lbl, val)
                
        layout.addWidget(self.pam4_status_panel)

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
        self.pam4_eye_mode_combo.addItem("Common t_center Eye")
        self.pam4_eye_mode_combo.currentIndexChanged.connect(self.on_pam4_eye_mode_change)
        control_layout.addWidget(eye_mode_label)
        control_layout.addWidget(self.pam4_eye_mode_combo)

        self.btn_pam4_new_wave = QPushButton("New PAM4 Wave")
        self.btn_pam4_new_wave.clicked.connect(self.on_pam4_generate_new_waveform)
        self.btn_pam4_reset_eq = QPushButton("Reset EQ")
        self.btn_pam4_reset_eq.clicked.connect(self.on_pam4_reset_eq)
        self.btn_pam4_reset_channel = QPushButton("Reset CH")
        self.btn_pam4_reset_channel.clicked.connect(self.on_pam4_reset_channel)
        self.btn_pam4_detail = QPushButton("Detail")
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
            (self.slider_pre["edit"], f"{self.pre_db_current:.2f}"),
            (self.slider_de["edit"], f"{self.de_db_current:.2f}"),
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
            for s in (
                self.slider_cm1, self.slider_cp1, self.slider_pre, 
                self.slider_de, self.slider_alpha,
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
            self.pre_db_current = 0.0
            self.de_db_current = 0.0
            self.cm1_current, self.cp1_current = db_to_taps(
                self.pre_db_current, self.de_db_current
            )
            self.current_preset = "Preset 4"
            self.control_mode = "db"
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
            "- Preshoot raises the last bit before a transition.\n"
            "- De-emphasis lowers repeated bits.\n"
            "- dB mode is for level-based visualization.\n"
            "- Tap mode is a FIR coefficient reference.\n\n"
            "Channel & RX EQ:\n"
            "- Low-pass Alpha is a simplified ISI model, not a real PCIe channel.\n"
            "- CTLE provides high-frequency boost.\n"
            "- DFE operates at symbol rate. It uses previous slicer decisions to subtract post-cursor ISI.\n"
            "- DFE sign convention: corrected[n] = sample[n] - tap * decision[n-1].\n\n"
            "Note: This is a teaching simulator, not a PCIe compliance tool."
        )
        msg.exec_()

    def get_rx_pipeline_results(self, tx_wave, ch_wave):
        # Use a fixed CTLE alpha decoupled from channel loss model
        fixed_ctle_alpha = 0.08
        return run_rx_pipeline(
            ch_wave, 
            self.ctle_boost_current, 
            fixed_ctle_alpha, 
            [self.dfe_tap1_current, self.dfe_tap2_current, self.dfe_tap3_current], 
            SPB, 
            SPB // 2
        )

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
        tx_sym = self.make_tx_symbols()
        tx_wave = np.repeat(tx_sym, SPB)
        ch_wave = simple_channel(tx_wave, alpha=self.channel_alpha_current)
        rx_results = self.get_rx_pipeline_results(tx_wave, ch_wave)
        rx_wave = self.get_target_rx_wave(rx_results)

        self.update_waveform(tx_wave, ch_wave, rx_wave if "Channel" not in self.rx_view_mode else None)
        
        if self.should_update_realtime_eye():
            self.update_eye_title()
            if "DFE" in self.rx_view_mode:
                self.update_dfe_sample_plot(rx_results, max_symbols=REALTIME_EYE_TRACES)
            else:
                self.update_eye(rx_wave, max_traces=REALTIME_EYE_TRACES)
            self.update_eye_metrics(rx_wave, rx_results, max_traces=REALTIME_EYE_TRACES)
            self.update_info()

    def redraw_all(self):
        tx_sym = self.make_tx_symbols()
        tx_wave = np.repeat(tx_sym, SPB)
        ch_wave = simple_channel(tx_wave, alpha=self.channel_alpha_current)
        rx_results = self.get_rx_pipeline_results(tx_wave, ch_wave)
        rx_wave = self.get_target_rx_wave(rx_results)

        self.update_waveform(tx_wave, ch_wave, rx_wave if "Channel" not in self.rx_view_mode else None)
        self.update_eye_title()
        if "DFE" in self.rx_view_mode:
            self.update_dfe_sample_plot(rx_results, max_symbols=MAX_EYE_TRACES)
        else:
            self.update_eye(rx_wave, max_traces=MAX_EYE_TRACES)
        self.update_eye_metrics(rx_wave, rx_results, max_traces=MAX_EYE_TRACES)
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
            "- Common t_center Eye: Centers traces based on the majority crossing phase.\n\n"
            "Note: Q10 is a special preset (Note 2).\n"
            "This is simplified visualization only. This is not a PCIe compliance calculator."
        )
        msg.exec_()

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
        self.update_pam4_eye_metrics(ch_wave)
        self.update_pam4_eye(ch_wave)
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
        invalid = {
            "valid": False,
            "upper_eye": 0.0,
            "middle_eye": 0.0,
            "lower_eye": 0.0,
            "minimum_eye": 0.0,
            "center_spread": 0.0,
            "sample_count": 0,
        }

        start = 20 * SPB
        phase = int(np.clip(phase, 0, SPB - 1))
        center_positions = np.arange(start + phase, len(wave), SPB, dtype=int)
        center_positions = center_positions[
            (center_positions >= 0) & (center_positions < len(wave))
        ]
        if center_positions.size < 20:
            return invalid

        center_samples = wave[center_positions]
        lower_band = center_samples[center_samples < -2 / 3]
        mid_low_band = center_samples[
            (center_samples >= -2 / 3) & (center_samples < 0)
        ]
        mid_high_band = center_samples[
            (center_samples >= 0) & (center_samples < 2 / 3)
        ]
        upper_band = center_samples[center_samples >= 2 / 3]

        if min(
            lower_band.size,
            mid_low_band.size,
            mid_high_band.size,
            upper_band.size,
        ) < 5:
            return invalid

        lower_eye = float(np.percentile(mid_low_band, 5) - np.percentile(lower_band, 95))
        middle_eye = float(np.percentile(mid_high_band, 5) - np.percentile(mid_low_band, 95))
        upper_eye = float(np.percentile(upper_band, 5) - np.percentile(mid_high_band, 95))
        minimum_eye = min(upper_eye, middle_eye, lower_eye)
        center_spread = float(np.max(center_samples) - np.min(center_samples))

        return {
            "valid": True,
            "upper_eye": upper_eye,
            "middle_eye": middle_eye,
            "lower_eye": lower_eye,
            "minimum_eye": minimum_eye,
            "center_spread": center_spread,
            "sample_count": int(center_samples.size),
        }

    def estimate_pam4_common_t_center_phase(self, wave):
        phase_update_margin = 0.002
        fallback = self.calc_pam4_eye_openings_at_phase(wave, SPB // 2)
        best_phase = SPB // 2
        best_openings = fallback if fallback["valid"] else {
            "valid": False,
            "upper_eye": 0.0,
            "middle_eye": 0.0,
            "lower_eye": 0.0,
            "minimum_eye": 0.0,
            "center_spread": 0.0,
            "sample_count": 0,
        }
        best_score = best_openings["minimum_eye"] if best_openings["valid"] else -np.inf

        for phase in range(SPB):
            openings = self.calc_pam4_eye_openings_at_phase(wave, phase)
            if not openings["valid"]:
                continue

            score = openings["minimum_eye"]
            if score > best_score + 1e-6:
                best_phase = phase
                best_openings = openings
                best_score = score
            elif abs(score - best_score) <= 1e-6:
                if abs(phase - (SPB // 2)) < abs(best_phase - (SPB // 2)):
                    best_phase = phase
                    best_openings = openings
                    best_score = score

        old_phase = int(np.clip(self.pam4_t_center_phase, 0, SPB - 1))
        old_openings = self.calc_pam4_eye_openings_at_phase(wave, old_phase)
        if old_openings["valid"]:
            old_score = old_openings["minimum_eye"]
            if best_score <= old_score + phase_update_margin:
                return old_phase, old_openings

        if not best_openings["valid"]:
            return SPB // 2, best_openings
        return best_phase, best_openings

    def update_pam4_eye_metrics(self, wave):
        best_phase, best_openings = self.estimate_pam4_common_t_center_phase(wave)
        self.pam4_t_center_phase = int(best_phase)
        self.pam4_t_center_score = float(best_openings["minimum_eye"])

        if not best_openings["valid"]:
            self.pam4_eye_metrics = {
                "upper_eye": 0.0,
                "middle_eye": 0.0,
                "lower_eye": 0.0,
                "minimum_eye": 0.0,
                "center_spread": 0.0,
            }
            return

        self.pam4_eye_metrics = {
            "upper_eye": best_openings["upper_eye"],
            "middle_eye": best_openings["middle_eye"],
            "lower_eye": best_openings["lower_eye"],
            "minimum_eye": best_openings["minimum_eye"],
            "center_spread": best_openings["center_spread"],
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

    def make_tx_symbols(self):
        if self.control_mode == "tap":
            tx_sym, _ = tx_fir(self.symbols, self.cm1_current, self.cp1_current)
            return tx_sym
        return tx_eq_pattern(self.symbols, self.pre_db_current, self.de_db_current)

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
        if rx_results is not None and "DFE" in self.rx_view_mode:
            # For DFE, calculate metrics based on corrected symbol-rate samples vs ground truth
            samples = rx_results["dfe_corrected_samples"]
            decisions = rx_results["dfe_decisions"]
            
            ref_len = min(len(samples), len(self.symbols))
            reference = self.symbols[:ref_len]
            samples_aligned = samples[:ref_len]
            decisions_aligned = decisions[:ref_len]
            
            warmup_symbols = 20
            if ref_len > warmup_symbols:
                reference = reference[warmup_symbols:]
                samples_aligned = samples_aligned[warmup_symbols:]
                decisions_aligned = decisions_aligned[warmup_symbols:]
            else:
                reference = np.array([])
                samples_aligned = np.array([])
                decisions_aligned = np.array([])
            
            if len(samples_aligned) > 0:
                signed_margin = samples_aligned * reference
                error_count = int(np.sum(decisions_aligned != reference))
                margin_5pct = float(np.percentile(signed_margin, 5))
                eye_height = margin_5pct * 2.0
                eye_max = float(np.max(samples_aligned))
                eye_min = float(np.min(samples_aligned))
                center_spread = float(np.max(samples_aligned) - np.min(samples_aligned))
            else:
                margin_5pct = 0.0
                eye_height = 0.0
                error_count = 0
                eye_max = 0.0
                eye_min = 0.0
                center_spread = 0.0
                
            self.eye_metrics = {
                "eye_height": eye_height,
                "margin_5pct": margin_5pct,
                "error_count": error_count,
                "eye_max": eye_max,
                "eye_min": eye_min,
                "center_spread": center_spread,
            }
            return

        seg_len = EYE_UI * SPB
        start = 20 * SPB
        trace_starts = np.arange(start, len(wave) - seg_len, SPB, dtype=int)
        if trace_starts.size == 0:
            self.eye_metrics = {
                "eye_height": 0.0,
                "margin_5pct": 0.0,
                "error_count": 0,
                "eye_max": 0.0,
                "eye_min": 0.0,
                "center_spread": 0.0,
            }
            return

        if trace_starts.size > max_traces:
            idx = np.linspace(0, trace_starts.size - 1, max_traces, dtype=int)
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
            "margin_5pct": eye_height / 2.0,
            "error_count": 0,
            "eye_max": eye_max,
            "eye_min": eye_min,
            "center_spread": center_spread,
        }

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = PCIeTxEqSimulator()
    win.show()
    sys.exit(app.exec_())
