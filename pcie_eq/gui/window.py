"""
PCIe TX/RX EQ Teaching Simulator GUI Window Module.

Contains PCIeTxEqSimulator main window class and associated GUI constants/helpers.
Source authority: main.py @ commit bb6f9d956f5d61201b8a134b1016437a6de5156e
"""

import numpy as np
from PyQt5.QtWidgets import QMainWindow

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
from pcie_eq.gui.pam4_tab import build_pam4_tab
from pcie_eq.gui.nrz_controller import NrzControllerMixin
from pcie_eq.gui.pam4_controller import Pam4ControllerMixin
from pcie_eq.gui.window_helpers import WindowUiHelpersMixin
from pcie_eq.gui.random_data import pam4_symbols_from_random
from pcie_eq.gui.preset_debug import validate_gen6_presets
from pcie_eq.gui.window_state import initialize_window_state
from pcie_eq.gui.window_layout import build_main_window_ui

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

        initialize_window_state(self, bits, symbols)

        self.init_ui()
        self.full_refresh()
        self.pam4_full_refresh()

    def init_ui(self):
        build_main_window_ui(self)

    def init_pam4_tab(self):
        build_pam4_tab(self)
