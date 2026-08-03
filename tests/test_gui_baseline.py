"""
GUI Interaction Baseline Tests for PCIeTxEqSimulator.

Locks in existing GUI behaviors:
1. Initial NRZ / PAM4 states and main control defaults.
2. NRZ Preset P0-P10 selection, Custom mode, and Channel/CTLE/DFE view mode switching.
3. NRZ Reset actions (Reset to TX EQ, Reset Channel, Reset RX EQ, Reset All).
4. PAM4 Q0-Q9 preset selection, Custom mode, and Reset actions (Reset EQ, Reset CH).
5. PAM4 Raw Eye vs Common t_center Eye mode switching.
6. NRZ & PAM4 Generate New Waveform functionality.
7. Exception-free full refreshes across all GUI interactions.
"""

import sys
import pytest
import numpy as np
from PyQt5.QtWidgets import QApplication
import main
from main import PCIeTxEqSimulator, SPB


@pytest.fixture(scope="module")
def qapp():
    """Reusable QApplication instance fixture for GUI testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_gui_initial_state(qapp):
    """Verify initial NRZ and PAM4 control values, presets, and view modes."""
    win = PCIeTxEqSimulator()
    assert win is not None

    # NRZ Initial Controls
    assert win.current_preset == "Custom"
    assert win.control_mode == "db"
    assert win.pre_db_current == 1.5
    assert win.de_db_current == -3.5
    assert win.channel_alpha_current == 0.08
    assert win.ctle_boost_current == 0.0
    assert win.dfe_tap1_current == 0.0
    assert win.dfe_tap2_current == 0.0
    assert win.dfe_tap3_current == 0.0
    assert win.rx_view_mode == "Channel (Before RX EQ)"

    # PAM4 Initial Controls
    assert win.gen6_preset_current == "Q0"
    assert win.pam4_cm2_current == 0.0
    assert win.pam4_cm1_current == 0.0
    assert win.pam4_cp1_current == 0.0
    assert win.pam4_alpha_current == 0.08
    assert win.pam4_eye_mode == "raw"
    assert 0 <= win.pam4_t_center_phase < SPB


def test_nrz_presets_and_custom_and_views(qapp):
    """Verify NRZ Preset selection (P0-P10), Custom preset, and RX View modes."""
    win = PCIeTxEqSimulator()

    # Test Presets P0 to P10
    for p in range(11):
        preset_name = f"Preset {p}"
        win.preset_combo.setCurrentText(preset_name)
        assert win.current_preset == preset_name
        assert win.control_mode == "preset"
        win.full_refresh()

    # Test Custom Preset selection
    win.preset_combo.setCurrentText("Custom")
    assert win.current_preset == "Custom"
    win.full_refresh()

    # Test RX View Mode switching
    view_modes = [
        "Channel (Before RX EQ)",
        "CTLE",
        "DFE (Sample Margin)",
    ]
    for mode in view_modes:
        win.rx_view_combo.setCurrentText(mode)
        assert win.rx_view_mode == mode
        win.full_refresh()


def test_nrz_reset_actions(qapp):
    """Verify NRZ Reset buttons (Reset TX EQ, Reset Channel, Reset RX EQ, Reset All)."""
    win = PCIeTxEqSimulator()

    # 1. Reset to TX EQ
    win.preset_combo.setCurrentText("Preset 0")
    win.on_reset_no_eq()
    assert win.pre_db_current == 0.0
    assert win.de_db_current == 0.0
    assert win.current_preset == "Preset 4"

    # 2. Reset Channel
    win.slider_alpha["slider"].setValue(150)
    win.on_alpha_slider_change()
    assert win.channel_alpha_current == pytest.approx(0.150)
    win.on_reset_channel()
    assert win.channel_alpha_current == 0.08

    # 3. Reset RX EQ
    win.slider_ctle["slider"].setValue(300)
    win.on_rx_slider_change()
    assert win.ctle_boost_current == pytest.approx(0.300)
    win.on_reset_rx()
    assert win.ctle_boost_current == 0.0
    assert win.dfe_tap1_current == 0.0
    assert win.dfe_tap2_current == 0.0
    assert win.dfe_tap3_current == 0.0

    # 4. Reset All
    win.preset_combo.setCurrentText("Preset 1")
    win.slider_alpha["slider"].setValue(200)
    win.on_alpha_slider_change()
    win.slider_ctle["slider"].setValue(400)
    win.on_rx_slider_change()
    win.rx_view_combo.setCurrentText("CTLE")
    win.on_reset_all()

    assert win.pre_db_current == 0.0
    assert win.de_db_current == 0.0
    assert win.current_preset == "Preset 4"
    assert win.channel_alpha_current == 0.08
    assert win.ctle_boost_current == 0.0
    assert win.rx_view_mode == "Channel (Before RX EQ)"


def test_pam4_presets_and_resets(qapp):
    """Verify PAM4 Q0-Q9 Preset selection, Custom preset, and PAM4 Reset buttons."""
    win = PCIeTxEqSimulator()

    # Test PAM4 Presets Q0 to Q9
    for q in range(10):
        preset_name = f"Q{q}"
        win.gen6_preset_combo.setCurrentText(preset_name)
        assert win.gen6_preset_current == preset_name
        win.pam4_full_refresh()

    # Test PAM4 Custom Preset selection
    win.gen6_preset_combo.setCurrentText("Custom")
    assert win.gen6_preset_current == "Custom"
    win.pam4_full_refresh()

    # Test Reset EQ
    win.gen6_preset_combo.setCurrentText("Q5")
    win.on_pam4_reset_eq()
    assert win.gen6_preset_current == "Q0"
    assert win.pam4_cm2_current == 0.0
    assert win.pam4_cm1_current == 0.0
    assert win.pam4_cp1_current == 0.0

    # Test Reset CH
    win.pam4_slider_alpha["slider"].setValue(180)
    win.on_pam4_slider_change()
    assert win.pam4_alpha_current == pytest.approx(0.180)
    win.on_pam4_reset_channel()
    assert win.pam4_alpha_current == 0.08


def test_pam4_eye_mode_toggle(qapp):
    """Verify PAM4 Raw Eye vs Common t_center Eye mode switching."""
    win = PCIeTxEqSimulator()

    win.pam4_eye_mode_combo.setCurrentText("Raw Eye")
    assert win.pam4_eye_mode == "raw"
    win.pam4_full_refresh()

    win.pam4_eye_mode_combo.setCurrentText("Common t_center Eye")
    assert win.pam4_eye_mode == "centered"
    win.pam4_full_refresh()


def test_generate_new_waveforms(qapp):
    """Verify NRZ and PAM4 Generate New Waveform actions."""
    win = PCIeTxEqSimulator()

    old_nrz_symbols = win.symbols.copy()
    win.on_generate_new_waveform()
    assert len(win.symbols) == len(old_nrz_symbols)
    assert not np.array_equal(win.symbols, old_nrz_symbols)

    old_pam4_symbols = win.pam4_symbols.copy()
    win.on_pam4_generate_new_waveform()
    assert len(win.pam4_symbols) == len(old_pam4_symbols)
    assert not np.array_equal(win.pam4_symbols, old_pam4_symbols)

    win.full_refresh()
    win.pam4_full_refresh()


def test_full_refreshes_after_interactions_no_exceptions(qapp):
    """Verify that full_refresh() and pam4_full_refresh() execute without exceptions under combined interactions."""
    win = PCIeTxEqSimulator()

    # Step 1: Change NRZ parameters & refresh
    win.preset_combo.setCurrentText("Preset 3")
    win.rx_view_combo.setCurrentText("DFE (Sample Margin)")
    win.full_refresh()

    # Step 2: Change PAM4 parameters & refresh
    win.gen6_preset_combo.setCurrentText("Q4")
    win.pam4_eye_mode_combo.setCurrentText("Common t_center Eye")
    win.pam4_full_refresh()

    # Step 3: Trigger Resets & refresh
    win.on_reset_all()
    win.on_pam4_reset_eq()
    win.full_refresh()
    win.pam4_full_refresh()
