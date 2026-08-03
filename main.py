"""
Main entry point for PCIe TX/RX EQ Simulator application.

Provides thin main() application launcher and backward compatibility re-exports.
"""

import sys
from PyQt5.QtWidgets import QApplication

from pcie_eq.gui.window import (
    PCIeTxEqSimulator,
    SPB,
    BIT_COUNT,
    PAM4_SYMBOL_COUNT,
)
from pcie_eq.tx_eq import (
    PCIE_PRESET_DB_TABLE,
    PCIE_GEN6_PRESET_TAP_TABLE,
    taps_to_db,
    calc_levels,
    db_to_taps,
    tx_fir,
    tx_eq_levels,
    constrain_gen6_taps,
    calc_gen6_levels,
    gen6_pam4_fir,
)
from pcie_eq.channel import simple_channel
from pcie_eq.rx_eq import (
    apply_ctle,
    apply_dfe,
    run_rx_pipeline,
)
from pcie_eq.metrics import (
    calc_pam4_eye_openings_at_phase,
    estimate_pam4_common_t_center_phase,
    calculate_pam4_eye_metrics,
    calculate_eye_metrics,
)
from pcie_eq.models import NrzSimulationConfig, Pam4SimulationConfig
from pcie_eq.pipeline import run_simulation

__all__ = [
    "PCIeTxEqSimulator",
    "SPB",
    "BIT_COUNT",
    "PAM4_SYMBOL_COUNT",
    "main",
]


def main():
    app = QApplication(sys.argv)
    win = PCIeTxEqSimulator()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
