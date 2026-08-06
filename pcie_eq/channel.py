"""
Simplified channel core model.
"""

import numpy as np

__all__ = ["simple_channel"]


def simple_channel(wave, alpha=0.08):
    """
    First-order recursive low-pass teaching model.

    out[0] = wave[0]
    out[i] = out[i-1] + alpha * (wave[i] - out[i-1])

    The recurrence is always evaluated in floating point. Non-floating input
    is promoted to float64 so that integer input cannot truncate the
    per-sample increment to zero. Floating input keeps its own dtype.

    Empty input returns an empty array rather than raising.
    """
    wave = np.asarray(wave)
    if not np.issubdtype(wave.dtype, np.floating):
        wave = wave.astype(np.float64)

    out = np.zeros_like(wave)
    if wave.size == 0:
        return out

    out[0] = wave[0]
    for i in range(1, len(wave)):
        out[i] = out[i - 1] + alpha * (wave[i] - out[i - 1])
    return out
