"""
Simplified channel core model.
"""

import numpy as np

__all__ = ["simple_channel"]


def simple_channel(wave, alpha=0.08):
    out = np.zeros_like(wave)
    out[0] = wave[0]
    for i in range(1, len(wave)):
        out[i] = out[i - 1] + alpha * (wave[i] - out[i - 1])
    return out
