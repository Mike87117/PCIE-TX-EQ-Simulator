"""
NRZ TX Equalization Baseline Tests for PCIE-TX-EQ-Simulator.

Locks in existing pre-refactor behavior of:
- taps_to_db()
- db_to_taps()
- calc_levels()
- tx_eq_levels()
- tx_fir()
"""

import pytest
import numpy as np
from pcie_eq.tx_eq import (
    taps_to_db,
    db_to_taps,
    calc_levels,
    tx_eq_levels,
    tx_fir,
)


def test_nrz_taps_to_db_and_db_to_taps_roundtrip():
    """
    Verify dB -> taps -> dB conversion consistency and tap sign conventions.
    """
    target_pre_db = 3.5
    target_de_db = -6.0

    cm1, cp1 = db_to_taps(target_pre_db, target_de_db)

    # Tap sign convention: precursor and postcursor taps in db_to_taps are negative
    assert cm1 <= 0.0
    assert cp1 <= 0.0

    # Mathematical conversion verification:
    # r_pre = 10^(pre_db/20), p = (1 - 1/r_pre)/2, cm1 = -p
    # r_de = 10^(de_db/20), q = (1 - r_de)/2, cp1 = -q
    r_pre_expected = 10 ** (3.5 / 20.0)
    r_de_expected = 10 ** (-6.0 / 20.0)
    p_expected = (1.0 - 1.0 / r_pre_expected) / 2.0
    q_expected = (1.0 - r_de_expected) / 2.0

    np.testing.assert_allclose(cm1, -p_expected, rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(cp1, -q_expected, rtol=1e-6, atol=1e-6)

    # Convert back from taps to dB
    pre_db_recalc, de_db_recalc = taps_to_db(cm1, cp1)

    np.testing.assert_allclose(pre_db_recalc, target_pre_db, rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(de_db_recalc, target_de_db, rtol=1e-5, atol=1e-5)


def test_nrz_calc_levels_golden():
    """
    Verify calc_levels() output for known tap values.
    cm1 = -0.05, cp1 = -0.15
    c0 = 1 - |cm1| - |cp1| = 0.80
    va = 1.0
    de_db = 20 * log10(1 - 2*0.15) = 20 * log10(0.70) = -3.098039...
    vb = 10^(de_db/20) = 0.70
    pre_db = 20 * log10(1 / (1 - 2*0.05)) = 20 * log10(1 / 0.90) = 0.915150...
    vc = vb * 10^(pre_db/20) = 0.70 * (1 / 0.90) = 0.7777777...
    """
    cm1 = -0.05
    cp1 = -0.15

    c0, va, vb, vc, pre_db, de_db = calc_levels(cm1, cp1)

    assert c0 == pytest.approx(0.80, abs=1e-6)
    assert va == pytest.approx(1.0, abs=1e-6)
    assert vb == pytest.approx(0.70, abs=1e-6)
    assert vc == pytest.approx(0.70 / 0.90, abs=1e-6)
    assert de_db == pytest.approx(20 * np.log10(0.70), abs=1e-5)
    assert pre_db == pytest.approx(20 * np.log10(1 / 0.90), abs=1e-5)


def test_nrz_tx_fir_no_eq_identity():
    """
    Verify tx_fir with zero pre/post cursor taps behaves as identity (c0 = 1.0).
    Also verify input array is not modified in place and output length matches input.
    """
    symbols = np.array([-1.0, -1.0, 1.0, 1.0, -1.0, 1.0, -1.0, -1.0], dtype=float)
    symbols_copy = symbols.copy()

    y, c0 = tx_fir(symbols, cm1=0.0, cp1=0.0, normalize_mode="none")

    assert c0 == 1.0
    assert len(y) == len(symbols)
    np.testing.assert_array_equal(symbols, symbols_copy)
    np.testing.assert_allclose(y, symbols, rtol=1e-7, atol=1e-7)


def test_nrz_tx_fir_indexing_and_tap_sign():
    """
    Verify C-1 (pre-cursor, next_bit) and C+1 (post-cursor, prev_bit) indexing
    and contributions are distinct and not swapped.
    
    Formula: y[i] = cm1 * next_bit + c0 * now_bit + cp1 * prev_bit
    With symbols = [-1, -1, 1, 1], edge padding gives [-1, -1, -1, 1, 1, 1]:
      i=0 (sym=0): now=-1, prev=-1, next=-1 -> y[0] = cm1*(-1) + c0*(-1) + cp1*(-1)
      i=1 (sym=1): now=-1, prev=-1, next=+1 -> y[1] = cm1*(+1) + c0*(-1) + cp1*(-1)
      i=2 (sym=2): now=+1, prev=-1, next=+1 -> y[2] = cm1*(+1) + c0*(+1) + cp1*(-1)
      i=3 (sym=3): now=+1, prev=+1, next=+1 -> y[3] = cm1*(+1) + c0*(+1) + cp1*(+1)
    """
    symbols = np.array([-1.0, -1.0, 1.0, 1.0], dtype=float)
    cm1 = -0.10
    cp1 = -0.20
    c0_expected = 1.0 - abs(cm1) - abs(cp1)  # 0.70

    y, c0 = tx_fir(symbols, cm1=cm1, cp1=cp1, normalize_mode="none")

    assert c0 == pytest.approx(c0_expected, abs=1e-6)

    y_expected = np.array([
        -0.10 * (-1.0) + 0.70 * (-1.0) + (-0.20) * (-1.0),  # 0.10 - 0.70 + 0.20 = -0.40
        -0.10 * (1.0)  + 0.70 * (-1.0) + (-0.20) * (-1.0),  # -0.10 - 0.70 + 0.20 = -0.60
        -0.10 * (1.0)  + 0.70 * (1.0)  + (-0.20) * (-1.0),  # -0.10 + 0.70 + 0.20 = 0.80
        -0.10 * (1.0)  + 0.70 * (1.0)  + (-0.20) * (1.0),   # -0.10 + 0.70 - 0.20 = 0.40
    ], dtype=float)

    np.testing.assert_allclose(y, y_expected, rtol=1e-6, atol=1e-6)


# Preshoot and deemphasis levels used across parametrized level pattern tests
PRESHOOT_DB_TEST = 2.5
DEEMPH_DB_TEST = -3.5
VA_TEST = 1.0
VB_TEST = 10 ** (DEEMPH_DB_TEST / 20.0)
VC_TEST = VB_TEST * (10 ** (PRESHOOT_DB_TEST / 20.0))


@pytest.mark.parametrize(
    ("pattern_name", "symbols", "expected_levels"),
    [
        (
            "0000",
            np.array([-1.0, -1.0, -1.0, -1.0]),
            np.array([-VB_TEST, -VB_TEST, -VB_TEST, -VB_TEST]),
        ),
        (
            "0001",
            np.array([-1.0, -1.0, -1.0, 1.0]),
            np.array([-VB_TEST, -VB_TEST, -VC_TEST, VA_TEST]),
        ),
        (
            "0011",
            np.array([-1.0, -1.0, 1.0, 1.0]),
            np.array([-VB_TEST, -VC_TEST, VA_TEST, VB_TEST]),
        ),
        (
            "0111",
            np.array([-1.0, 1.0, 1.0, 1.0]),
            np.array([-VC_TEST, VA_TEST, VB_TEST, VB_TEST]),
        ),
        (
            "1010",
            np.array([1.0, -1.0, 1.0, -1.0]),
            np.array([VC_TEST, -VA_TEST, VA_TEST, -VA_TEST]),
        ),
        (
            "1110",
            np.array([1.0, 1.0, 1.0, -1.0]),
            np.array([VB_TEST, VB_TEST, VC_TEST, -VA_TEST]),
        ),
        (
            "1000",
            np.array([1.0, -1.0, -1.0, -1.0]),
            np.array([VC_TEST, -VA_TEST, -VB_TEST, -VB_TEST]),
        ),
    ],
)
def test_nrz_tx_eq_level_pattern_vectors(pattern_name, symbols, expected_levels):
    """
    Verify tx_eq_levels with explicit expected output vectors for all 7 required patterns:
    0000, 0001, 0011, 0111, 1010, 1110, 1000.

    Verifies:
    1. No EQ identity behavior when preshoot=0, deemph=0.
    2. Exact level assignment (Va, Vb, Vc) for every symbol position.
    3. Preshoot and De-emphasis are not swapped.
    4. Output length equals input length.
    5. Input array is not modified in place.
    """
    symbols_copy = symbols.copy()

    # 1. No EQ verification (preshoot=0, deemph=0) -> output equals input symbols
    y_no_eq = tx_eq_levels(symbols, preshoot_db=0.0, deemph_db=0.0)
    assert len(y_no_eq) == len(symbols)
    np.testing.assert_array_equal(symbols, symbols_copy)
    np.testing.assert_allclose(y_no_eq, symbols, rtol=1e-7, atol=1e-7)

    # 2. EQ active verification with explicit expected vector
    y_eq = tx_eq_levels(symbols, preshoot_db=PRESHOOT_DB_TEST, deemph_db=DEEMPH_DB_TEST)
    assert len(y_eq) == len(symbols)
    np.testing.assert_array_equal(symbols, symbols_copy)
    np.testing.assert_allclose(y_eq, expected_levels, rtol=1e-6, atol=1e-6)


def test_nrz_tx_fir_empty_input():
    """
    Verify tx_fir returns an empty float array for empty input instead of raising.

    np.pad(mode="edge") cannot extend an empty axis, so this previously raised
    ValueError. c0 is still derived from the taps and returned unchanged.
    """
    y, c0 = tx_fir(np.array([], dtype=float), cm1=-0.1, cp1=-0.2)

    assert isinstance(y, np.ndarray)
    assert y.shape == (0,)
    assert y.dtype == np.float64
    assert c0 == pytest.approx(1 - 0.1 - 0.2, abs=1e-12)


def test_nrz_tx_eq_levels_empty_input():
    """Verify tx_eq_levels already tolerates empty input and returns an empty float array."""
    y = tx_eq_levels(np.array([], dtype=float), preshoot_db=1.5, deemph_db=-3.5)

    assert isinstance(y, np.ndarray)
    assert y.shape == (0,)
    assert y.dtype == np.float64
