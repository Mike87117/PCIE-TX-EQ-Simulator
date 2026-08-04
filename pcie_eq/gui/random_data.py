"""
Random Symbol Generator Module for PCIe TX/RX EQ Simulator.

Provides helpers for generating random symbol sequences for PAM4 simulation.
"""

from pcie_eq.patterns import generate_random_pam4_symbols

__all__ = ["pam4_symbols_from_random"]


def pam4_symbols_from_random(count):
    """Compatibility wrapper delegating to pattern generator core."""
    return generate_random_pam4_symbols(count, seed=None)
