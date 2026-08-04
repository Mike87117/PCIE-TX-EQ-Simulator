"""
Main Window Layout Composition Module for PCIe TX/RX EQ Simulator.

Provides helper function to construct the top-level main window widget structure,
tab widgets, and layout.
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from pcie_eq.gui.nrz_tab import build_nrz_tab

__all__ = ["build_main_window_ui"]


def build_main_window_ui(window):
    """Build and compose top-level main window layout and tabs."""
    root = QWidget()
    root_layout = QVBoxLayout(root)
    window.tabs = QTabWidget()
    window.nrz_tab = QWidget()
    window.pam4_tab = QWidget()
    window.tabs.addTab(window.nrz_tab, "PCIe Gen1~5 NRZ TX EQ")
    window.tabs.addTab(window.pam4_tab, "PCIe Gen6 PAM4 TX EQ")
    root_layout.addWidget(window.tabs)

    build_nrz_tab(window)
    window.init_pam4_tab()
    window.setCentralWidget(root)
