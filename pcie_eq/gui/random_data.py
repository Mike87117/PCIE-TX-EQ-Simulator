"""
Random Symbol Generator Module for PCIe TX/RX EQ Simulator.

Provides helpers for generating random symbol sequences for PAM4 simulation.
"""

import numpy as np

__all__ = ["pam4_symbols_from_random"]


def pam4_symbols_from_random(count):
    levels = np.array([-3.0, -1.0, 1.0, 3.0], dtype=float) / 3.0
    return levels[np.random.randint(0, 4, count)]
