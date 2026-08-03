"""
PAM4 Tab UI Builder for PCIe TX/RX EQ Simulator.

Constructs the PAM4 Gen6 tab layout, plots, status panel, controls, sliders,
validators, and connects UI signals to handlers on owner.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QLineEdit, QPushButton,
    QComboBox, QGroupBox, QGridLayout, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator
import pyqtgraph as pg

__all__ = ["build_pam4_tab"]


def build_pam4_tab(owner):
    """
    Builds the PAM4 Gen6 Tab UI layout and widgets on owner.pam4_tab.
    Attaches all PAM4 plots, curves, status items, controls, and sliders to owner.
    """
    layout = QVBoxLayout(owner.pam4_tab)

    owner.pam4_wave_plot = pg.PlotWidget(title="PCIe Gen6 PAM4 TX EQ Waveform")
    owner.pam4_wave_plot.setLabel("bottom", "Symbol / UI")
    owner.pam4_wave_plot.setLabel("left", "Normalized Level")
    owner.pam4_wave_plot.showGrid(x=True, y=True)

    owner.pam4_eye_plot = pg.PlotWidget(title="PAM4 Eye Diagram after Simplified Channel")
    owner.pam4_eye_plot.setLabel("bottom", "UI")
    owner.pam4_eye_plot.setLabel("left", "Normalized Level")
    owner.pam4_eye_plot.showGrid(x=True, y=True)

    owner.pam4_tx_curve = owner.pam4_wave_plot.plot(pen=pg.mkPen(width=2))
    owner.pam4_ch_curve = owner.pam4_wave_plot.plot(pen=pg.mkPen(width=2, style=Qt.DashLine))
    owner.pam4_eye_curve = owner.pam4_eye_plot.plot(pen=pg.mkPen(width=1))
    owner.pam4_tx_curve.setDownsampling(auto=True)
    owner.pam4_ch_curve.setDownsampling(auto=True)
    owner.pam4_tx_curve.setClipToView(True)
    owner.pam4_ch_curve.setClipToView(True)

    layout.addWidget(owner.pam4_wave_plot, stretch=4)
    layout.addWidget(owner.pam4_eye_plot, stretch=3)

    # Status Panel
    owner.pam4_status_panel = QFrame()
    owner.pam4_status_panel.setMinimumHeight(90)
    owner.pam4_status_panel.setMaximumHeight(110)
    owner.pam4_status_panel.setStyleSheet("""
        QFrame {
            border: 1px solid #c0c0c0;
            border-radius: 4px;
            background-color: #f9f9f9;
        }
    """)

    owner.pam4_status_layout = QGridLayout(owner.pam4_status_panel)
    owner.pam4_status_layout.setContentsMargins(8, 4, 8, 4)
    owner.pam4_status_layout.setSpacing(4)
    owner.pam4_status_items = {}

    for r in range(2):
        for c in range(4):
            container = QWidget()
            hlay = QHBoxLayout(container)
            hlay.setContentsMargins(0, 0, 0, 0)
            hlay.setSpacing(4)
            lbl = QLabel()
            lbl.setStyleSheet("font-size: 13px; color: #555; border: none; background: transparent;")
            val = QLabel()
            val.setStyleSheet("font-size: 16px; font-weight: bold; color: #111; border: none; background: transparent;")
            hlay.addWidget(lbl)
            hlay.addWidget(val)
            hlay.addStretch()
            owner.pam4_status_layout.addWidget(container, r, c)
            owner.pam4_status_items[(r, c)] = (lbl, val)

    layout.addWidget(owner.pam4_status_panel)

    # Control Layout
    control_layout = QHBoxLayout()
    preset_label = QLabel("Gen6 Preset")
    preset_label.setFixedWidth(120)
    owner.gen6_preset_combo = QComboBox()
    owner.gen6_preset_combo.addItem("Custom")
    for q in range(10):
        owner.gen6_preset_combo.addItem(f"Q{q}")
    owner.gen6_preset_combo.currentIndexChanged.connect(owner.on_gen6_preset_change)
    control_layout.addWidget(preset_label)
    control_layout.addWidget(owner.gen6_preset_combo)

    eye_mode_label = QLabel("PAM4 Eye Mode")
    eye_mode_label.setFixedWidth(120)
    owner.pam4_eye_mode_combo = QComboBox()
    owner.pam4_eye_mode_combo.addItem("Raw Eye")
    owner.pam4_eye_mode_combo.addItem("Common t_center Eye")
    owner.pam4_eye_mode_combo.currentIndexChanged.connect(owner.on_pam4_eye_mode_change)
    control_layout.addWidget(eye_mode_label)
    control_layout.addWidget(owner.pam4_eye_mode_combo)

    owner.btn_pam4_new_wave = QPushButton("New PAM4 Wave")
    owner.btn_pam4_new_wave.clicked.connect(owner.on_pam4_generate_new_waveform)
    owner.btn_pam4_reset_eq = QPushButton("Reset EQ")
    owner.btn_pam4_reset_eq.clicked.connect(owner.on_pam4_reset_eq)
    owner.btn_pam4_reset_channel = QPushButton("Reset CH")
    owner.btn_pam4_reset_channel.clicked.connect(owner.on_pam4_reset_channel)
    owner.btn_pam4_detail = QPushButton("Detail")
    owner.btn_pam4_detail.clicked.connect(owner.on_toggle_pam4_detail)
    for btn in (
        owner.btn_pam4_new_wave,
        owner.btn_pam4_reset_eq,
        owner.btn_pam4_reset_channel,
        owner.btn_pam4_detail,
    ):
        btn.setFixedHeight(24)
        control_layout.addWidget(btn)
    layout.addLayout(control_layout)

    # Sliders & Validators
    owner.pam4_slider_cm2 = owner.make_slider(
        "C-2", 0, 250, int(owner.pam4_cm2_current * 1000)
    )
    owner.pam4_slider_cm1 = owner.make_slider(
        "C-1", -300, 0, int(owner.pam4_cm1_current * 1000)
    )
    owner.pam4_slider_cp1 = owner.make_slider(
        "C+1", -250, 0, int(owner.pam4_cp1_current * 1000)
    )
    owner.pam4_slider_alpha = owner.make_slider(
        "PAM4 Low-pass Alpha", 1, 300, int(owner.pam4_alpha_current * 1000)
    )

    owner.pam4_slider_cm2["edit"].setValidator(QDoubleValidator(0.0, 0.25, 4, owner))
    owner.pam4_slider_cm1["edit"].setValidator(QDoubleValidator(-0.30, 0.0, 4, owner))
    owner.pam4_slider_cp1["edit"].setValidator(QDoubleValidator(-0.25, 0.0, 4, owner))
    owner.pam4_slider_alpha["edit"].setValidator(QDoubleValidator(0.001, 0.3, 3, owner))

    layout.addLayout(owner.pam4_slider_cm2["layout"])
    layout.addLayout(owner.pam4_slider_cm1["layout"])
    layout.addLayout(owner.pam4_slider_cp1["layout"])
    layout.addLayout(owner.pam4_slider_alpha["layout"])

    owner.pam4_slider_cm2["slider"].valueChanged.connect(owner.on_pam4_slider_change)
    owner.pam4_slider_cm1["slider"].valueChanged.connect(owner.on_pam4_slider_change)
    owner.pam4_slider_cp1["slider"].valueChanged.connect(owner.on_pam4_slider_change)
    owner.pam4_slider_alpha["slider"].valueChanged.connect(owner.on_pam4_slider_change)

    owner.pam4_slider_cm2["edit"].editingFinished.connect(lambda: owner.on_pam4_edit_change("cm2"))
    owner.pam4_slider_cm1["edit"].editingFinished.connect(lambda: owner.on_pam4_edit_change("cm1"))
    owner.pam4_slider_cp1["edit"].editingFinished.connect(lambda: owner.on_pam4_edit_change("cp1"))
    owner.pam4_slider_alpha["edit"].editingFinished.connect(lambda: owner.on_pam4_edit_change("alpha"))
