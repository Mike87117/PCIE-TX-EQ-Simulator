"""Eye diagram metrics core module."""

import numpy as np

from pcie_eq.sampling import select_phase_centered_trace_starts, NRZ_WARMUP_SYMBOLS

__all__ = [
    "calc_pam4_eye_openings_at_phase",
    "estimate_pam4_common_t_center_phase",
    "calculate_pam4_eye_metrics",
    "calculate_dfe_eye_metrics",
    "calculate_nrz_eye_metrics",
    "calculate_eye_metrics",
]


def calc_pam4_eye_openings_at_phase(wave, pam4_symbols, phase, spb=32):
    invalid = {
        "valid": False,
        "upper_eye": 0.0,
        "middle_eye": 0.0,
        "lower_eye": 0.0,
        "minimum_eye": 0.0,
        "center_spread": 0.0,
        "sample_count": 0,
    }

    start = 20 * spb
    phase = int(np.clip(phase, 0, spb - 1))
    center_positions = np.arange(start + phase, len(wave), spb, dtype=int)
    center_positions = center_positions[
        (center_positions >= 0) & (center_positions < len(wave))
    ]
    if center_positions.size < 20:
        return invalid

    center_samples = wave[center_positions]
    symbol_indices = center_positions // spb
    valid_mask = symbol_indices < len(pam4_symbols)
    if np.count_nonzero(valid_mask) < 20:
        return invalid

    center_positions = center_positions[valid_mask]
    symbol_indices = symbol_indices[valid_mask]
    center_samples = wave[center_positions]
    ref_symbols = pam4_symbols[symbol_indices]

    lower_band = center_samples[np.isclose(ref_symbols, -1.0)]
    mid_low_band = center_samples[np.isclose(ref_symbols, -1.0 / 3.0)]
    mid_high_band = center_samples[np.isclose(ref_symbols, 1.0 / 3.0)]
    upper_band = center_samples[np.isclose(ref_symbols, 1.0)]

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


def estimate_pam4_common_t_center_phase(wave, pam4_symbols, old_phase=16, spb=32):
    phase_update_margin = 0.002
    fallback = calc_pam4_eye_openings_at_phase(wave, pam4_symbols, spb // 2, spb=spb)
    best_phase = spb // 2
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

    for phase in range(spb):
        openings = calc_pam4_eye_openings_at_phase(wave, pam4_symbols, phase, spb=spb)
        if not openings["valid"]:
            continue

        score = openings["minimum_eye"]
        if score > best_score + 1e-6:
            best_phase = phase
            best_openings = openings
            best_score = score
        elif abs(score - best_score) <= 1e-6:
            if abs(phase - (spb // 2)) < abs(best_phase - (spb // 2)):
                best_phase = phase
                best_openings = openings
                best_score = score

    old_phase = int(np.clip(old_phase, 0, spb - 1))
    old_openings = calc_pam4_eye_openings_at_phase(wave, pam4_symbols, old_phase, spb=spb)
    if old_openings["valid"]:
        old_score = old_openings["minimum_eye"]
        if best_score <= old_score + phase_update_margin:
            return old_phase, old_openings

    if not best_openings["valid"]:
        return spb // 2, best_openings
    return best_phase, best_openings


def calculate_pam4_eye_metrics(wave, pam4_symbols, old_phase=16, spb=32):
    best_phase, best_openings = estimate_pam4_common_t_center_phase(
        wave, pam4_symbols, old_phase=old_phase, spb=spb
    )
    if not best_openings["valid"]:
        metrics = {
            "upper_eye": 0.0,
            "middle_eye": 0.0,
            "lower_eye": 0.0,
            "minimum_eye": 0.0,
            "center_spread": 0.0,
        }
    else:
        metrics = {
            "upper_eye": best_openings["upper_eye"],
            "middle_eye": best_openings["middle_eye"],
            "lower_eye": best_openings["lower_eye"],
            "minimum_eye": best_openings["minimum_eye"],
            "center_spread": best_openings["center_spread"],
        }
    return best_phase, float(best_openings["minimum_eye"]), metrics


def calculate_dfe_eye_metrics(samples, decisions, reference, warmup_symbols=20):
    ref_len = min(len(samples), len(reference))
    ref_aligned = reference[:ref_len]
    samples_aligned = samples[:ref_len]
    decisions_aligned = decisions[:ref_len]

    if ref_len > warmup_symbols:
        ref_aligned = ref_aligned[warmup_symbols:]
        samples_aligned = samples_aligned[warmup_symbols:]
        decisions_aligned = decisions_aligned[warmup_symbols:]
    else:
        ref_aligned = np.array([])
        samples_aligned = np.array([])
        decisions_aligned = np.array([])

    if len(samples_aligned) > 0:
        signed_margin = samples_aligned * ref_aligned
        error_count = int(np.sum(decisions_aligned != ref_aligned))
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

    return {
        "eye_height": eye_height,
        "margin_5pct": margin_5pct,
        "error_count": error_count,
        "eye_max": eye_max,
        "eye_min": eye_min,
        "center_spread": center_spread,
    }


def calculate_nrz_eye_metrics(wave, eye_ui=2, spb=32, max_traces=200, sampling_phase=None):
    if type(eye_ui) is not int:
        raise TypeError(f"eye_ui must be exact int, got {type(eye_ui).__name__}")
    if eye_ui != 2:
        raise ValueError(f"eye_ui must be 2 under contract v1, got {eye_ui}")

    sampled_starts = select_phase_centered_trace_starts(
        len(wave), spb, sampling_phase, max_traces, warmup_symbols=NRZ_WARMUP_SYMBOLS
    )
    if sampled_starts.size == 0:
        return {
            "eye_height": 0.0,
            "margin_5pct": 0.0,
            "error_count": 0,
            "eye_max": 0.0,
            "eye_min": 0.0,
            "center_spread": 0.0,
        }

    seg_len = 2 * spb
    segs = np.array([wave[s:s + seg_len] for s in sampled_starts], dtype=float)
    eye_max = float(np.max(segs))
    eye_min = float(np.min(segs))

    center_samples = segs[:, spb]
    center_spread = float(np.max(center_samples) - np.min(center_samples))
    upper = center_samples[center_samples >= 0]
    lower = center_samples[center_samples < 0]
    if upper.size > 0 and lower.size > 0:
        eye_height = float(np.percentile(upper, 5) - np.percentile(lower, 95))
    else:
        eye_height = 0.0

    return {
        "eye_height": eye_height,
        "margin_5pct": eye_height / 2.0,
        "error_count": 0,
        "eye_max": eye_max,
        "eye_min": eye_min,
        "center_spread": center_spread,
    }


def calculate_eye_metrics(wave, rx_results=None, is_dfe=False, reference_symbols=None, max_traces=200, eye_ui=2, spb=32, sampling_phase=None):
    if is_dfe and rx_results is not None:
        samples = rx_results.get("dfe_corrected_samples", np.array([]))
        decisions = rx_results.get("dfe_decisions", np.array([]))
        reference = reference_symbols if reference_symbols is not None else np.array([])
        return calculate_dfe_eye_metrics(samples, decisions, reference)
    return calculate_nrz_eye_metrics(wave, eye_ui=eye_ui, spb=spb, max_traces=max_traces, sampling_phase=sampling_phase)
