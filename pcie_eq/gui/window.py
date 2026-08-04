"""
PCIe TX/RX EQ Teaching Simulator GUI Window Module.

Contains PCIeTxEqSimulator main window class and associated GUI constants/helpers.
Source authority: main.py @ commit bb6f9d956f5d61201b8a134b1016437a6de5156e
"""

import sys
import numpy as np
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
    taps_to_db,
    calc_levels,
    db_to_taps,
    tx_fir,
    tx_eq_levels,
    constrain_gen6_taps,
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
from pcie_eq.gui.pam4_controller import Pam4ControllerMixin
from pcie_eq.gui.window_helpers import WindowUiHelpersMixin
from pcie_eq.gui.random_data import pam4_symbols_from_random
from pcie_eq.gui.preset_debug import validate_gen6_presets

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
# Main GUI
# =========================

class PCIeTxEqSimulator(
    NrzControllerMixin,
    Pam4ControllerMixin,
    WindowUiHelpersMixin,
    QMainWindow,
):
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
