"""
NRZ Preset Resolution Baseline Tests for PCIeTxEqSimulator.

Locks the NRZ Preset resolution contract for Presets 0 through 10:
1. Preset table lookup, requested dB clipping, tap calculation (cm1, cp1),
   and effective dB state resolution for every Preset (0 to 10).
2. Preshoot vs De-emphasis non-swapping contract.
3. C-1 (cm1) and C+1 (cp1) sign convention and tap constraint bounds.
4. Edge value behavior locking (specifically Preset 10 effective dB clipping).
5. Preset re-application idempotency.
6. Preset switching independence (switching from Custom or another Preset N).
7. Side-effect isolation guarantee: applying a Preset does NOT modify
   channel_alpha_current, ctle_boost_current, DFE taps (1..3), symbols, bits,
   or the NumPy global random state.
8. Proper Qt application lifecycle and window cleanup without event loop execution.

All expected values in this test module are hardcoded fixed constants.
Production functions (db_to_taps, calc_levels, apply_preset) are NOT called
during assertion evaluation to compute expected values dynamically.
"""

import sys
import pytest
import numpy as np
from PyQt5.QtWidgets import QApplication

from pcie_eq.tx_eq import PCIE_PRESET_DB_TABLE
from main import PCIeTxEqSimulator


@pytest.fixture(scope="module")
def qapp():
    """Reusable QApplication instance fixture for GUI testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


# Fixed Golden Cases for NRZ Presets 0 through 10.
# Each entry contains:
# (preset_id, tbl_pre, tbl_de, req_pre, req_de, expected_cm1, expected_cp1, eff_pre, eff_de)
NRZ_PRESET_GOLDEN_DATA = [
    (0, 0.0, -6.0, 0.0, -6.0, 0.0, -0.2494063831863639, 0.0, -6.0),
    (1, 0.0, -3.5, 0.0, -3.5, 0.0, -0.16582804121569265, 0.0, -3.5),
    (2, 0.0, -4.5, 0.0, -4.5, 0.0, -0.20216892823549477, 0.0, -4.5),
    (3, 0.0, -2.5, 0.0, -2.5, 0.0, -0.12505289533377206, 0.0, -2.5),
    (4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    (5, 1.9, 0.0, 1.9, 0.0, -0.09823693890739834, 0.0, 1.9, 0.0),
    (6, 2.5, 0.0, 2.5, 0.0, -0.12505289533377206, 0.0, 2.5, 0.0),
    (7, 3.5, -6.0, 3.5, -6.0, -0.16582804121569265, -0.2494063831863639, 3.5, -6.0),
    (8, 3.5, -3.5, 3.5, -3.5, -0.16582804121569265, -0.16582804121569265, 3.5, -3.5),
    (9, 3.5, 0.0, 3.5, 0.0, -0.16582804121569265, 0.0, 3.5, 0.0),
    (10, 0.0, -9.5, 0.0, -9.5, 0.0, -0.3, 0.0, -7.958800173440752),
]


@pytest.mark.parametrize(
    "preset_id,tbl_pre,tbl_de,req_pre,req_de,exp_cm1,exp_cp1,eff_pre,eff_de",
    NRZ_PRESET_GOLDEN_DATA,
)
def test_nrz_preset_table_resolution_golden_values(
    qapp, preset_id, tbl_pre, tbl_de, req_pre, req_de, exp_cm1, exp_cp1, eff_pre, eff_de
):
    """
    Verify Preset table entries, requested dB clipping, tap calculations,
    and effective dB states against hardcoded golden values for apply_preset(preset_id).
    """
    win = PCIeTxEqSimulator()
    try:
        # Table integrity check
        assert PCIE_PRESET_DB_TABLE[preset_id] == (tbl_pre, tbl_de)

        # Requested dB clipping check against fixed constants
        clipped_req_pre = float(np.clip(tbl_pre, 0.0, 6.0))
        clipped_req_de = float(np.clip(tbl_de, -12.0, 0.0))
        assert clipped_req_pre == req_pre
        assert clipped_req_de == req_de

        # Apply preset
        win.apply_preset(preset_id)

        # Assert resolution contract attributes against fixed golden constants
        assert win.cm1_current == pytest.approx(exp_cm1, abs=1e-12)
        assert win.cp1_current == pytest.approx(exp_cp1, abs=1e-12)
        assert win.pre_db_current == pytest.approx(eff_pre, abs=1e-12)
        assert win.de_db_current == pytest.approx(eff_de, abs=1e-12)
        assert win.current_preset == f"Preset {preset_id}"
        assert win.control_mode == "preset"
    finally:
        win.close()


@pytest.mark.parametrize(
    "preset_id,tbl_pre,tbl_de,req_pre,req_de,exp_cm1,exp_cp1,eff_pre,eff_de",
    NRZ_PRESET_GOLDEN_DATA,
)
def test_nrz_preset_gui_combo_selection_golden_values(
    qapp, preset_id, tbl_pre, tbl_de, req_pre, req_de, exp_cm1, exp_cp1, eff_pre, eff_de
):
    """
    Verify selecting Preset via preset_combo UI control triggers preset application
    and synchronizes UI controls matching fixed golden values.
    """
    win = PCIeTxEqSimulator()
    try:
        win.preset_combo.setCurrentText(f"Preset {preset_id}")

        assert win.cm1_current == pytest.approx(exp_cm1, abs=1e-12)
        assert win.cp1_current == pytest.approx(exp_cp1, abs=1e-12)
        assert win.pre_db_current == pytest.approx(eff_pre, abs=1e-12)
        assert win.de_db_current == pytest.approx(eff_de, abs=1e-12)
        assert win.current_preset == f"Preset {preset_id}"
        assert win.control_mode == "preset"

        # Check UI slider representation
        assert win.slider_cm1["slider"].value() == int(exp_cm1 * 1000)
        assert win.slider_cp1["slider"].value() == int(exp_cp1 * 1000)
    finally:
        win.close()


def test_nrz_preset_sign_convention_and_taps_constraints(qapp):
    """
    Verify that C-1 (cm1) and C+1 (cp1) maintain negative sign convention (<= 0)
    and satisfy individual tap limits (|c| <= 0.3) and total tap sum constraint (|cm1|+|cp1| <= 0.49).
    """
    win = PCIeTxEqSimulator()
    try:
        for preset_id in range(11):
            win.apply_preset(preset_id)
            cm1 = win.cm1_current
            cp1 = win.cp1_current

            # Negative sign convention check
            assert cm1 <= 0.0, f"Preset {preset_id} cm1 must be <= 0"
            assert cp1 <= 0.0, f"Preset {preset_id} cp1 must be <= 0"

            # Individual tap bound check
            assert abs(cm1) <= 0.3 + 1e-12, f"Preset {preset_id} |cm1| exceeds 0.3"
            assert abs(cp1) <= 0.3 + 1e-12, f"Preset {preset_id} |cp1| exceeds 0.3"

            # Combined tap constraint check
            assert abs(cm1) + abs(cp1) <= 0.49 + 1e-12, f"Preset {preset_id} total tap magnitude exceeds 0.49"
    finally:
        win.close()


def test_nrz_preset_preshoot_deemphasis_non_swapping(qapp):
    """
    Verify Preshoot (C-1) and De-emphasis (C+1) are not swapped across presets.
    - Preshoot-only presets (Preset 5, 6) modify cm1 and leave cp1 == 0.
    - Deemphasis-only presets (Preset 0, 1, 2, 3, 10) modify cp1 and leave cm1 == 0.
    """
    win = PCIeTxEqSimulator()
    try:
        # Preshoot-only presets
        for preset_id in (5, 6):
            win.apply_preset(preset_id)
            assert win.cm1_current < 0.0, f"Preset {preset_id} should have negative cm1 for preshoot"
            assert win.cp1_current == 0.0, f"Preset {preset_id} should have zero cp1"

        # Deemphasis-only presets
        for preset_id in (0, 1, 2, 3, 10):
            win.apply_preset(preset_id)
            assert win.cm1_current == 0.0, f"Preset {preset_id} should have zero cm1"
            assert win.cp1_current < 0.0, f"Preset {preset_id} should have negative cp1 for de-emphasis"
    finally:
        win.close()


def test_nrz_preset_boundary_effective_db_clipping_preset10(qapp):
    """
    Lock boundary case for Preset 10:
    Requested de-emphasis is -9.5 dB, but tap q is clipped to 0.3 (cp1 = -0.3).
    Effective de-emphasis is locked to exactly -7.958800173440752 dB.
    """
    win = PCIeTxEqSimulator()
    try:
        win.apply_preset(10)

        assert win.cm1_current == 0.0
        assert win.cp1_current == -0.3
        assert win.pre_db_current == 0.0
        # Effective de-emphasis is clipped due to tap constraint q <= 0.3
        assert win.de_db_current == pytest.approx(-7.958800173440752, abs=1e-12)
        assert win.de_db_current != -9.5
    finally:
        win.close()


def test_nrz_preset_reapplication_idempotency(qapp):
    """
    Verify applying the same preset twice consecutively yields identical state.
    """
    win = PCIeTxEqSimulator()
    try:
        for preset_id in range(11):
            win.apply_preset(preset_id)
            cm1_first = win.cm1_current
            cp1_first = win.cp1_current
            pre_first = win.pre_db_current
            de_first = win.de_db_current

            # Apply same preset second time
            win.apply_preset(preset_id)

            assert win.cm1_current == cm1_first
            assert win.cp1_current == cp1_first
            assert win.pre_db_current == pre_first
            assert win.de_db_current == de_first
            assert win.current_preset == f"Preset {preset_id}"
            assert win.control_mode == "preset"
    finally:
        win.close()


def test_nrz_preset_switching_state_independence(qapp):
    """
    Verify switching to a Preset from Custom mode or from a different Preset
    results in a state completely independent of prior state.
    """
    win = PCIeTxEqSimulator()
    try:
        for preset_id in range(11):
            # Mutate state to Custom mode first
            win.control_mode = "tap"
            win.current_preset = "Custom"
            win.cm1_current = -0.15
            win.cp1_current = -0.15

            # Apply target preset
            win.apply_preset(preset_id)

            exp_cm1 = NRZ_PRESET_GOLDEN_DATA[preset_id][5]
            exp_cp1 = NRZ_PRESET_GOLDEN_DATA[preset_id][6]
            eff_pre = NRZ_PRESET_GOLDEN_DATA[preset_id][7]
            eff_de = NRZ_PRESET_GOLDEN_DATA[preset_id][8]

            assert win.cm1_current == pytest.approx(exp_cm1, abs=1e-12)
            assert win.cp1_current == pytest.approx(exp_cp1, abs=1e-12)
            assert win.pre_db_current == pytest.approx(eff_pre, abs=1e-12)
            assert win.de_db_current == pytest.approx(eff_de, abs=1e-12)
            assert win.current_preset == f"Preset {preset_id}"
            assert win.control_mode == "preset"
    finally:
        win.close()


def test_nrz_preset_side_effect_isolation(qapp):
    """
    Verify that applying any Preset does NOT modify:
    - channel_alpha_current
    - ctle_boost_current
    - dfe_tap1_current, dfe_tap2_current, dfe_tap3_current
    - symbols array
    - bits array
    - NumPy global random state
    """
    win = PCIeTxEqSimulator()
    try:
        # Set custom non-default channel, RX EQ parameters
        win.channel_alpha_current = 1.234
        win.ctle_boost_current = 4.567
        win.dfe_tap1_current = 0.123
        win.dfe_tap2_current = -0.045
        win.dfe_tap3_current = 0.067

        symbols_before = np.copy(win.symbols)
        bits_before = np.copy(win.bits)
        rng_state_before = np.random.get_state()

        for preset_id in range(11):
            win.apply_preset(preset_id)

            assert win.channel_alpha_current == 1.234
            assert win.ctle_boost_current == 4.567
            assert win.dfe_tap1_current == 0.123
            assert win.dfe_tap2_current == -0.045
            assert win.dfe_tap3_current == 0.067
            assert np.array_equal(win.symbols, symbols_before)
            assert np.array_equal(win.bits, bits_before)

            rng_state_after = np.random.get_state()
            assert rng_state_before[0] == rng_state_after[0]
            assert np.array_equal(rng_state_before[1], rng_state_after[1])
            assert rng_state_before[2:] == rng_state_after[2:]
    finally:
        win.close()
