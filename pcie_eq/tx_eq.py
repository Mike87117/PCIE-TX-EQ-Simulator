"""
Transmitter Equalization (TX EQ) Core Module.

Provides NRZ and PAM4 TX FIR equalization, Preset tables,
dB <-> tap conversions, tap constraints, and level calculations.
"""

import numpy as np

__all__ = [
    "PCIE_PRESET_DB_TABLE",
    "PCIE_GEN6_PRESET_TAP_TABLE",
    "taps_to_db",
    "calc_levels",
    "db_to_taps",
    "tx_fir",
    "tx_eq_levels",
    "constrain_gen6_taps",
    "calc_gen6_levels",
    "gen6_pam4_fir",
]

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

# =========================
# PCIe TX EQ math
# =========================


def taps_to_db(cm1, cp1):
    p = abs(cm1)
    q = abs(cp1)

    # C-1 controls preshoot.
    # Larger p means higher Vc/Vb.
    r_pre = 1.0 / max(1.0 - 2.0 * p, 1e-6)

    # C+1 controls de-emphasis.
    # Larger q means lower Vb/Va.
    r_de = max(1.0 - 2.0 * q, 1e-6)

    pre_db = 20 * np.log10(r_pre)
    de_db = 20 * np.log10(r_de)

    return pre_db, de_db


def calc_levels(cm1, cp1):
    c0 = 1 - abs(cm1) - abs(cp1)

    pre_db, de_db = taps_to_db(cm1, cp1)

    va = 1.0
    vb = 10 ** (de_db / 20)
    vc = vb * 10 ** (pre_db / 20)

    return c0, va, vb, vc, pre_db, de_db


def db_to_taps(pre_db, de_db):
    pre_db = float(np.clip(pre_db, 0.0, 6.0))
    de_db = float(np.clip(de_db, -12.0, 0.0))

    r_pre = 10 ** (pre_db / 20)
    r_de = 10 ** (de_db / 20)

    # inverse of:
    # r_pre = 1 / (1 - 2p)
    # r_de = 1 - 2q
    p = (1.0 - 1.0 / r_pre) / 2.0
    q = (1.0 - r_de) / 2.0

    p = float(np.clip(p, 0.0, 0.3))
    q = float(np.clip(q, 0.0, 0.3))

    return -p, -q


def tx_fir(symbols_in, cm1, cp1, normalize_mode="none"):
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
    y = np.array(y)

    if normalize_mode == "steady":
        steady_level = abs(cm1 + c0 + cp1)
        if steady_level > 1e-9:
            y = y / steady_level
    elif normalize_mode == "peak":
        peak = float(np.max(np.abs(y)))
        if peak > 1e-9:
            y = y / peak

    return y, c0


def tx_eq_levels(symbols_in, preshoot_db, deemph_db):
    va = 1.0
    vb = 10 ** (deemph_db / 20)
    vc = vb * 10 ** (preshoot_db / 20)

    y = np.zeros_like(symbols_in, dtype=float)

    for i in range(len(symbols_in)):
        prev_bit = symbols_in[i - 1] if i > 0 else symbols_in[i]
        now_bit = symbols_in[i]
        next_bit = symbols_in[i + 1] if i < len(symbols_in) - 1 else symbols_in[i]

        is_first_after_transition = now_bit != prev_bit
        is_last_before_transition = now_bit != next_bit
        is_repeated = now_bit == prev_bit

        if is_last_before_transition and is_repeated:
            amp = vc
        elif is_repeated:
            amp = vb
        else:
            amp = va

        y[i] = now_bit * amp

    return y


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


def gen6_pam4_fir(symbols_in, cm2, cm1, cp1):
    cm2, cm1, cp1 = constrain_gen6_taps(cm2, cm1, cp1)
    c0 = 1.0 - abs(cm2) - abs(cm1) - abs(cp1)
    # Simulator convention:
    # C-2 / C-1 are precursor taps.
    # C+1 is the post-cursor tap.
    # This matches the NRZ tx_fir() convention used in this project.
    padded = np.pad(symbols_in, (1, 2), mode="edge")
    y = []
    for i in range(1, len(padded) - 2):
        prev_sym = padded[i - 1]
        now_sym = padded[i]
        next_sym = padded[i + 1]
        next2_sym = padded[i + 2]
        out = (
            cm2 * next2_sym +
            cm1 * next_sym +
            c0 * now_sym +
            cp1 * prev_sym
        )
        y.append(out)
    return np.array(y), c0
