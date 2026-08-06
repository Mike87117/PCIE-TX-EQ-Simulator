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
    arr = np.asarray(wave)
    if arr.ndim != 1:
        raise ValueError(f"wave must be a 1D array, got shape {arr.shape}")
    if arr.dtype.kind not in {"b", "i", "u", "f"}:
        raise TypeError(f"wave must have real numeric dtype, got dtype {arr.dtype}")

    if arr.dtype.kind != "f":
        work = arr.astype(np.float64)
    else:
        work = arr

    out = np.empty(len(work), dtype=work.dtype)
    if work.size == 0:
        return out

    out[0] = work[0]
    for i in range(1, len(work)):
        out[i] = out[i - 1] + alpha * (work[i] - out[i - 1])
    return out
