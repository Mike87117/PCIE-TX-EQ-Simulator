"""
Window State Initializer Module for PCIe TX/RX EQ Simulator.

Provides helper function to initialize NRZ and PAM4 state attributes on PCIeTxEqSimulator instance.
"""

from PyQt5.QtCore import QElapsedTimer
from pcie_eq.tx_eq import db_to_taps
from pcie_eq.gui.constants import SPB, PAM4_SYMBOL_COUNT
from pcie_eq.gui.random_data import pam4_symbols_from_random

__all__ = ["initialize_window_state"]


def initialize_window_state(window, initial_bits, initial_symbols):
    """Initialize initial NRZ and PAM4 state attributes on window instance."""
    window.syncing_ui = False
    window.control_mode = "db"
    window.current_preset = "Custom"
    window.channel_alpha_current = 0.08

    window.pre_db_current = 1.5
    window.de_db_current = -3.5
    window.cm1_current, window.cp1_current = db_to_taps(
        pre_db=window.pre_db_current,
        de_db=window.de_db_current
    )
    window.rx_view_mode = "Channel (Before RX EQ)"
    window.ctle_boost_current = 0.0
    window.dfe_tap1_current = 0.0
    window.dfe_tap2_current = 0.0
    window.dfe_tap3_current = 0.0
    window.eye_metrics = {
        "eye_height": 0.0,
        "eye_max": 0.0,
        "eye_min": 0.0,
        "center_spread": 0.0,
    }
    window.bits = initial_bits.copy()
    window.symbols = initial_symbols.copy()

    window.realtime_eye_timer = QElapsedTimer()
    window.realtime_eye_timer.start()

    window.gen6_preset_current = "Q0"
    window.pam4_cm2_current = 0.0
    window.pam4_cm1_current = 0.0
    window.pam4_cp1_current = 0.0
    window.pam4_alpha_current = 0.08
    window.pam4_eye_mode = "raw"
    window.pam4_t_center_phase = SPB // 2
    window.pam4_t_center_score = 0.0
    window.pam4_symbols = pam4_symbols_from_random(PAM4_SYMBOL_COUNT)
    window.pam4_eye_metrics = {
        "upper_eye": 0.0,
        "middle_eye": 0.0,
        "lower_eye": 0.0,
        "minimum_eye": 0.0,
        "center_spread": 0.0,
    }
