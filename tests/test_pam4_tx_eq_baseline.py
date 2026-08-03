"""
PAM4 TX Equalization Baseline Tests for PCIE-TX-EQ-Simulator.

Locks in existing pre-refactor behavior of:
- PCIE_GEN6_PRESET_TAP_TABLE
- constrain_gen6_taps()
- calc_gen6_levels()
- gen6_pam4_fir()
"""

import pytest
import numpy as np
from pcie_eq.tx_eq import (
    PCIE_GEN6_PRESET_TAP_TABLE,
    constrain_gen6_taps,
    calc_gen6_levels,
    gen6_pam4_fir,
)


def test_pam4_preset_table_integrity():
    """
    Verify Q0~Q9 preset table completeness and exact baseline values.
    """
    expected_presets = {
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

    assert len(PCIE_GEN6_PRESET_TAP_TABLE) == 10

    for q_name, expected_taps in expected_presets.items():
        assert q_name in PCIE_GEN6_PRESET_TAP_TABLE
        actual_taps = PCIE_GEN6_PRESET_TAP_TABLE[q_name]
        np.testing.assert_allclose(actual_taps, expected_taps, rtol=1e-6, atol=1e-6)


def test_pam4_fir_q0_identity():
    """
    Verify preset Q0 (0, 0, 0) acts as identity transform with c0 = 1.0.
    Verifies output length equals input length and input array is unmodified.
    """
    pam4_symbols = np.array(
        [-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0, 1.0, 1.0 / 3.0, -1.0 / 3.0, -1.0],
        dtype=float,
    )
    pam4_symbols_copy = pam4_symbols.copy()

    cm2, cm1, cp1 = PCIE_GEN6_PRESET_TAP_TABLE["Q0"]
    y, c0 = gen6_pam4_fir(pam4_symbols, cm2, cm1, cp1)

    assert c0 == 1.0
    assert len(y) == len(pam4_symbols)
    np.testing.assert_array_equal(pam4_symbols, pam4_symbols_copy)
    np.testing.assert_allclose(y, pam4_symbols, rtol=1e-7, atol=1e-7)


def test_pam4_fir_indexing_and_q6_golden():
    """
    Verify gen6_pam4_fir indexing (C-2, C-1, C0, C+1) and golden output for Q6.

    Q6 taps: cm2 = 0.042, cm1 = -0.125, cp1 = -0.125
    c0 = 1.0 - abs(cm2) - abs(cm1) - abs(cp1) = 0.708

    Formula per symbol i (with pad(1, 2, mode='edge')):
    y[i] = cm2 * next2_sym + cm1 * next_sym + c0 * now_sym + cp1 * prev_sym

    Input pam4_symbols: [-1.0, -1/3, 1/3, 1.0, 1.0, 1/3, -1/3, -1.0]
    Padded input (edge mode): [-1.0, -1.0, -1/3, 1/3, 1.0, 1.0, 1/3, -1/3, -1.0, -1.0, -1.0]
    """
    pam4_symbols = np.array(
        [-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0, 1.0, 1.0 / 3.0, -1.0 / 3.0, -1.0],
        dtype=float,
    )
    pam4_symbols_copy = pam4_symbols.copy()

    cm2, cm1, cp1 = PCIE_GEN6_PRESET_TAP_TABLE["Q6"]
    y, c0 = gen6_pam4_fir(pam4_symbols, cm2, cm1, cp1)

    assert c0 == pytest.approx(0.708, abs=1e-6)
    assert len(y) == len(pam4_symbols)
    np.testing.assert_array_equal(pam4_symbols, pam4_symbols_copy)

    # Hand-calculated golden vector for Q6:
    # padded = [-1.0, -1.0, -1/3, 1/3, 1.0, 1.0, 1/3, -1/3, -1.0, -1.0, -1.0]
    # i=0 (now=-1.0, prev=-1.0, next=-1/3, next2=1/3):
    #   y[0] = 0.042*(1/3) + (-0.125)*(-1/3) + 0.708*(-1.0) + (-0.125)*(-1.0)
    #        = 0.014 + 0.0416666667 - 0.708 + 0.125 = -0.5273333333
    # i=1 (now=-1/3, prev=-1.0, next=1/3, next2=1.0):
    #   y[1] = 0.042*(1.0) + (-0.125)*(1/3) + 0.708*(-1/3) + (-0.125)*(-1.0)
    #        = 0.042 - 0.0416666667 - 0.236 + 0.125 = -0.1106666667
    expected_y = np.array([
        0.042*(1/3) + (-0.125)*(-1/3) + 0.708*(-1.0) + (-0.125)*(-1.0),
        0.042*(1.0) + (-0.125)*(1/3)  + 0.708*(-1/3) + (-0.125)*(-1.0),
        0.042*(1.0) + (-0.125)*(1.0)  + 0.708*(1/3)  + (-0.125)*(-1/3),
        0.042*(1/3) + (-0.125)*(1.0)  + 0.708*(1.0)  + (-0.125)*(1/3),
        0.042*(-1/3)+ (-0.125)*(1/3)  + 0.708*(1.0)  + (-0.125)*(1.0),
        0.042*(-1.0)+ (-0.125)*(-1/3) + 0.708*(1/3)  + (-0.125)*(1.0),
        0.042*(-1.0)+ (-0.125)*(-1.0) + 0.708*(-1/3) + (-0.125)*(1/3),
        0.042*(-1.0)+ (-0.125)*(-1.0) + 0.708*(-1.0) + (-0.125)*(-1/3),
    ], dtype=float)

    np.testing.assert_allclose(y, expected_y, rtol=1e-6, atol=1e-6)


def test_constrain_gen6_taps():
    """
    Verify tap clipping and scaling limits in constrain_gen6_taps.
    - cm2 clipped to [0.0, 0.25]
    - cm1 clipped to [-0.30, 0.0]
    - cp1 clipped to [-0.25, 0.0]
    - if tap_sum >= 0.95, scale down so sum equals 0.95
    """
    # 1. Normal values within range
    cm2, cm1, cp1 = constrain_gen6_taps(0.042, -0.125, -0.125)
    assert (cm2, cm1, cp1) == pytest.approx((0.042, -0.125, -0.125), abs=1e-6)

    # 2. Out of bounds clipping
    cm2, cm1, cp1 = constrain_gen6_taps(0.50, -0.50, -0.50)
    # clipped to (0.25, -0.30, -0.25), sum = 0.80 < 0.95, no scaling
    assert (cm2, cm1, cp1) == pytest.approx((0.25, -0.30, -0.25), abs=1e-6)


def test_calc_gen6_levels_golden():
    """
    Verify calc_gen6_levels results for preset Q0 and Q1.

    Q0: cm2=0, cm1=0, cp1=0 -> c0=1.0, va=1.0, vb=1.0, vc1=1.0, vc2=1.0, vd=1.0
        pre1_db = 0, pre2_db = 0, de_db = 0, boost_db = 0
    Q1: cm2=0, cm1=-0.083, cp1=0 -> c0=0.917
        va = |0 - 0.083 + 0.917 - 0| = 0.834
        vb = |0 - 0.083 + 0.917 + 0| = 0.834
        vc1 = |0 - (-0.083) + 0.917 + 0| = 1.000
        vc2 = |-0 + (-0.083) + 0.917 + 0| = 0.834
        vd = |0 - (-0.083) + 0.917 - 0| = 1.000
    """
    # Q0
    c0, va, vb, vc1, vc2, vd, pre1_db, pre2_db, de_db, boost_db = calc_gen6_levels(0.0, 0.0, 0.0)
    assert c0 == pytest.approx(1.0, abs=1e-6)
    assert (va, vb, vc1, vc2, vd) == pytest.approx((1.0, 1.0, 1.0, 1.0, 1.0), abs=1e-6)
    assert (pre1_db, pre2_db, de_db, boost_db) == pytest.approx((0.0, 0.0, 0.0, 0.0), abs=1e-6)

    # Q1
    cm2, cm1, cp1 = PCIE_GEN6_PRESET_TAP_TABLE["Q1"]
    c0, va, vb, vc1, vc2, vd, pre1_db, pre2_db, de_db, boost_db = calc_gen6_levels(cm2, cm1, cp1)

    assert c0 == pytest.approx(0.917, abs=1e-6)
    assert va == pytest.approx(0.834, abs=1e-6)
    assert vb == pytest.approx(0.834, abs=1e-6)
    assert vc1 == pytest.approx(1.000, abs=1e-6)
    assert vc2 == pytest.approx(0.834, abs=1e-6)
    assert vd == pytest.approx(1.000, abs=1e-6)
    assert pre1_db == pytest.approx(20 * np.log10(1.000 / 0.834), abs=1e-4)
    assert de_db == pytest.approx(0.0, abs=1e-6)
