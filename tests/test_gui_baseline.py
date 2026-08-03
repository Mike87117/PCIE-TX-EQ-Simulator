"""
GUI Interaction Baseline Tests for PCIeTxEqSimulator.

Locks in existing GUI behaviors:
1. Presence of tabs and core NRZ/PAM4 controls.
2. Initial NRZ / PAM4 states and main control defaults.
3. NRZ & PAM4 representative preset parameter value locking.
4. Channel/CTLE/DFE view mode switching, title updates, and metrics correspondence.
5. NRZ Reset actions (Reset to TX EQ, Reset Channel, Reset RX EQ, Reset All).
6. PAM4 Q0-Q9 preset selection, Custom mode, and Reset actions (Reset EQ, Reset CH).
7. PAM4 Raw Eye vs Common t_center Eye mode switching.
8. NRZ & PAM4 Generate New Waveform array shapes and valid symbol level sets.
9. Exception-free full refreshes across all GUI interactions and window cleanup.
"""

import sys
import pytest
import numpy as np
from PyQt5.QtWidgets import QApplication
import main
from main import PCIeTxEqSimulator, SPB, BIT_COUNT, PAM4_SYMBOL_COUNT


@pytest.fixture(scope="module")
def qapp():
    """Reusable QApplication instance fixture for GUI testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_gui_tabs_and_controls_presence(qapp):
    """Verify presence of main tab widget, tab titles, and core NRZ/PAM4 control widgets."""
    win = PCIeTxEqSimulator()
    try:
        assert hasattr(win, "tabs")
        assert win.tabs.count() == 2
        assert win.tabs.tabText(0) == "PCIe Gen1~5 NRZ TX EQ"
        assert win.tabs.tabText(1) == "PCIe Gen6 PAM4 TX EQ"

        # Check NRZ controls
        assert hasattr(win, "preset_combo")
        assert hasattr(win, "slider_cm1")
        assert hasattr(win, "slider_cp1")
        assert hasattr(win, "slider_alpha")
        assert hasattr(win, "slider_ctle")
        assert hasattr(win, "slider_dfe1")
        assert hasattr(win, "slider_dfe2")
        assert hasattr(win, "slider_dfe3")
        assert hasattr(win, "rx_view_combo")
        assert hasattr(win, "btn_reset_no_eq")
        assert hasattr(win, "btn_reset_channel")
        assert hasattr(win, "btn_reset_rx")
        assert hasattr(win, "btn_reset_all")

        # Check PAM4 controls
        assert hasattr(win, "gen6_preset_combo")
        assert hasattr(win, "pam4_slider_cm2")
        assert hasattr(win, "pam4_slider_cm1")
        assert hasattr(win, "pam4_slider_cp1")
        assert hasattr(win, "pam4_slider_alpha")
        assert hasattr(win, "pam4_eye_mode_combo")
        assert hasattr(win, "btn_pam4_reset_eq")
        assert hasattr(win, "btn_pam4_reset_channel")
    finally:
        win.close()


def test_gui_initial_state(qapp):
    """Verify initial NRZ and PAM4 control values, presets, and view modes."""
    win = PCIeTxEqSimulator()
    try:
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
    finally:
        win.close()


def test_nrz_representative_preset_values(qapp):
    """Verify representative NRZ presets set expected dB values."""
    win = PCIeTxEqSimulator()
    try:
        # Preset 0: (0.0 dB, -6.0 dB)
        win.preset_combo.setCurrentText("Preset 0")
        assert win.current_preset == "Preset 0"
        assert win.pre_db_current == pytest.approx(0.0)
        assert win.de_db_current == pytest.approx(-6.0)

        # Preset 1: (0.0 dB, -3.5 dB)
        win.preset_combo.setCurrentText("Preset 1")
        assert win.current_preset == "Preset 1"
        assert win.pre_db_current == pytest.approx(0.0)
        assert win.de_db_current == pytest.approx(-3.5)

        # Preset 4: (0.0 dB, 0.0 dB)
        win.preset_combo.setCurrentText("Preset 4")
        assert win.current_preset == "Preset 4"
        assert win.pre_db_current == pytest.approx(0.0)
        assert win.de_db_current == pytest.approx(0.0)

        # Preset 5: (1.9 dB, 0.0 dB)
        win.preset_combo.setCurrentText("Preset 5")
        assert win.current_preset == "Preset 5"
        assert win.pre_db_current == pytest.approx(1.9)
        assert win.de_db_current == pytest.approx(0.0)

        # Preset 7: (3.5 dB, -6.0 dB)
        win.preset_combo.setCurrentText("Preset 7")
        assert win.current_preset == "Preset 7"
        assert win.pre_db_current == pytest.approx(3.5)
        assert win.de_db_current == pytest.approx(-6.0)
    finally:
        win.close()


def test_pam4_representative_preset_values(qapp):
    """Verify representative PAM4 Gen6 presets set expected tap values."""
    win = PCIeTxEqSimulator()
    try:
        # Q0: C-2=0.0, C-1=0.0, C+1=0.0
        win.gen6_preset_combo.setCurrentText("Q0")
        assert win.gen6_preset_current == "Q0"
        assert win.pam4_cm2_current == pytest.approx(0.0)
        assert win.pam4_cm1_current == pytest.approx(0.0)
        assert win.pam4_cp1_current == pytest.approx(0.0)

        # Q1: C-2=0.0, C-1=-0.083, C+1=0.0
        win.gen6_preset_combo.setCurrentText("Q1")
        assert win.gen6_preset_current == "Q1"
        assert win.pam4_cm2_current == pytest.approx(0.0)
        assert win.pam4_cm1_current == pytest.approx(-0.083)
        assert win.pam4_cp1_current == pytest.approx(0.0)

        # Q5: C-2=0.042, C-1=-0.208, C+1=0.0
        win.gen6_preset_combo.setCurrentText("Q5")
        assert win.gen6_preset_current == "Q5"
        assert win.pam4_cm2_current == pytest.approx(0.042)
        assert win.pam4_cm1_current == pytest.approx(-0.208)
        assert win.pam4_cp1_current == pytest.approx(0.0)
    finally:
        win.close()


def test_rx_view_mode_switching_and_title_and_metrics(qapp):
    """Verify RX View mode switching updates eye plot title and corresponding metrics dictionary."""
    win = PCIeTxEqSimulator()
    try:
        # 1. Channel View Mode
        win.rx_view_combo.setCurrentText("Channel (Before RX EQ)")
        win.full_refresh()
        assert win.rx_view_mode == "Channel (Before RX EQ)"
        assert win.eye_plot.plotItem.titleLabel.text == "Eye Diagram after Channel"
        assert "eye_height" in win.eye_metrics
        assert "margin_5pct" in win.eye_metrics

        # 2. CTLE View Mode
        win.rx_view_combo.setCurrentText("CTLE")
        win.full_refresh()
        assert win.rx_view_mode == "CTLE"
        assert win.eye_plot.plotItem.titleLabel.text == "Eye Diagram after CTLE"
        assert "eye_height" in win.eye_metrics

        # 3. DFE View Mode
        win.rx_view_combo.setCurrentText("DFE (Sample Margin)")
        win.full_refresh()
        assert win.rx_view_mode == "DFE (Sample Margin)"
        assert win.eye_plot.plotItem.titleLabel.text == "DFE Corrected Sample Margin"
        assert "error_count" in win.eye_metrics
        assert "margin_5pct" in win.eye_metrics
    finally:
        win.close()


def test_nrz_reset_actions(qapp):
    """Verify NRZ Reset buttons (Reset TX EQ, Reset Channel, Reset RX EQ, Reset All)."""
    win = PCIeTxEqSimulator()
    try:
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
    finally:
        win.close()


def test_pam4_presets_and_resets(qapp):
    """Verify PAM4 Q0-Q9 Preset selection, Custom preset, and PAM4 Reset buttons."""
    win = PCIeTxEqSimulator()
    try:
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
    finally:
        win.close()


def test_pam4_eye_mode_toggle(qapp):
    """Verify PAM4 Raw Eye vs Common t_center Eye mode switching."""
    win = PCIeTxEqSimulator()
    try:
        win.pam4_eye_mode_combo.setCurrentText("Raw Eye")
        assert win.pam4_eye_mode == "raw"
        win.pam4_full_refresh()

        win.pam4_eye_mode_combo.setCurrentText("Common t_center Eye")
        assert win.pam4_eye_mode == "centered"
        win.pam4_full_refresh()
    finally:
        win.close()


def test_generate_new_waveforms_array_shapes_and_symbol_levels(qapp):
    """Verify NRZ and PAM4 Generate New Waveform array shapes and valid symbol level sets."""
    win = PCIeTxEqSimulator()
    try:
        # NRZ Waveform Generation
        old_nrz_symbols = win.symbols.copy()
        win.on_generate_new_waveform()

        assert win.symbols.shape == (BIT_COUNT,)
        assert not np.array_equal(win.symbols, old_nrz_symbols)
        # NRZ valid levels must be {-1.0, 1.0}
        nrz_unique = set(np.unique(win.symbols))
        assert nrz_unique.issubset({-1.0, 1.0})

        # PAM4 Waveform Generation
        old_pam4_symbols = win.pam4_symbols.copy()
        win.on_pam4_generate_new_waveform()

        assert win.pam4_symbols.shape == (PAM4_SYMBOL_COUNT,)
        assert not np.array_equal(win.pam4_symbols, old_pam4_symbols)
        # PAM4 valid levels must be {-1.0, -1/3, 1/3, 1.0}
        pam4_unique = np.unique(win.pam4_symbols)
        allowed_levels = [-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0]
        for val in pam4_unique:
            assert any(np.isclose(val, level) for level in allowed_levels), f"Invalid PAM4 level: {val}"

        win.full_refresh()
        win.pam4_full_refresh()
    finally:
        win.close()


def test_full_refreshes_after_interactions_no_exceptions(qapp):
    """Verify that full_refresh() and pam4_full_refresh() execute without exceptions under combined interactions."""
    win = PCIeTxEqSimulator()
    try:
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
    finally:
        win.close()
