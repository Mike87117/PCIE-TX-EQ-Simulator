"""
NRZ Tab UI Builder for PCIe TX/RX EQ Simulator.

Constructs the NRZ tab layout, plots, status panel, controls, sliders,
and connects UI signals to handlers on owner.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QLineEdit, QPushButton,
    QComboBox, QScrollArea, QSizePolicy, QGroupBox, QGridLayout, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator
import pyqtgraph as pg

__all__ = ["build_nrz_tab"]


def build_nrz_tab(owner):
    """
    Builds the NRZ Tab UI layout and widgets on owner.nrz_tab.
    Attaches all NRZ plots, curves, status items, controls, and sliders to owner.
    """
    layout = QVBoxLayout(owner.nrz_tab)

    pg.setConfigOptions(antialias=False)

    owner.wave_plot = pg.PlotWidget(title="PCIe TX EQ Waveform")
    owner.wave_plot.setLabel("bottom", "Bit / UI")
    owner.wave_plot.setLabel("left", "Voltage")
    owner.wave_plot.showGrid(x=True, y=True)
    owner.wave_plot.hideButtons()

    owner.eye_plot = pg.PlotWidget(title="Eye Diagram after Channel")
    owner.eye_plot.setLabel("bottom", "UI")
    owner.eye_plot.setLabel("left", "Voltage")
    owner.eye_plot.showGrid(x=True, y=True)
    owner.eye_plot.hideButtons()

    owner.tx_curve = owner.wave_plot.plot(pen=pg.mkPen(width=2))
    owner.ch_curve = owner.wave_plot.plot(pen=pg.mkPen(width=2, style=Qt.DashLine))
    owner.rx_curve = owner.wave_plot.plot(pen=pg.mkPen(color='g', width=2))
    owner.eye_curve = owner.eye_plot.plot(pen=pg.mkPen(width=1))

    owner.tx_curve.setDownsampling(auto=True)
    owner.ch_curve.setDownsampling(auto=True)
    owner.rx_curve.setDownsampling(auto=True)
    owner.tx_curve.setClipToView(True)
    owner.ch_curve.setClipToView(True)
    owner.rx_curve.setClipToView(True)

    layout.addWidget(owner.wave_plot, stretch=4)
    layout.addWidget(owner.eye_plot, stretch=3)

    # Status Panel
    owner.status_panel = QFrame()
    owner.status_panel.setMinimumHeight(90)
    owner.status_panel.setMaximumHeight(110)
    owner.status_panel.setStyleSheet("""
        QFrame {
            border: 1px solid #c0c0c0;
            border-radius: 4px;
            background-color: #f9f9f9;
        }
    """)

    owner.status_layout = QGridLayout(owner.status_panel)
    owner.status_layout.setContentsMargins(8, 4, 8, 4)
    owner.status_layout.setSpacing(4)
    owner.status_items = {}

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
            owner.status_layout.addWidget(container, r, c)
            owner.status_items[(r, c)] = (lbl, val)

    layout.addWidget(owner.status_panel)

    # Scrollable Controls Area
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setMaximumHeight(210)
    scroll.setMinimumHeight(160)
    scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

    bottom_widget = QWidget()
    bottom_layout = QVBoxLayout(bottom_widget)

    control_layout = QHBoxLayout()
    preset_label = QLabel("PCIe Preset")
    preset_label.setFixedWidth(120)
    owner.preset_combo = QComboBox()
    owner.preset_combo.addItem("Custom")
    for p in range(11):
        owner.preset_combo.addItem(f"Preset {p}")
    owner.preset_combo.currentIndexChanged.connect(owner.on_preset_change)
    control_layout.addWidget(preset_label)
    control_layout.addWidget(owner.preset_combo)

    owner.btn_new_wave = QPushButton("Generate New Waveform")
    owner.btn_new_wave.clicked.connect(owner.on_generate_new_waveform)
    owner.btn_reset_no_eq = QPushButton("Reset to TX EQ")
    owner.btn_reset_no_eq.clicked.connect(owner.on_reset_no_eq)
    owner.btn_reset_channel = QPushButton("Reset Channel")
    owner.btn_reset_channel.clicked.connect(owner.on_reset_channel)
    owner.btn_reset_all = QPushButton("Reset All")
    owner.btn_reset_all.clicked.connect(owner.on_reset_all)
    owner.btn_nrz_detail = QPushButton("Detail")
    owner.btn_nrz_detail.clicked.connect(owner.on_toggle_nrz_detail)
    owner.btn_nrz_detail.setMaximumWidth(120)

    for btn in (
        owner.btn_new_wave,
        owner.btn_reset_no_eq,
        owner.btn_reset_channel,
        owner.btn_reset_all,
        owner.btn_nrz_detail,
    ):
        btn.setFixedHeight(24)
        if btn is not owner.btn_nrz_detail:
            btn.setMaximumWidth(160)
        control_layout.addWidget(btn)
    bottom_layout.addLayout(control_layout)

    # Sliders Layout
    sliders_layout = QHBoxLayout()

    tx_group = QGroupBox("TX EQ / Channel")
    rx_group = QGroupBox("RX EQ")

    group_box_style = """
    QGroupBox {
        font-weight: bold;
        border: 1px solid #b0b0b0;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }
    """
    tx_group.setStyleSheet(group_box_style)
    rx_group.setStyleSheet(group_box_style)

    tx_layout = QVBoxLayout(tx_group)
    rx_layout = QVBoxLayout(rx_group)

    owner.slider_cm1 = owner.make_slider(
        "C-1", -300, 0, int(owner.cm1_current * 1000)
    )
    owner.slider_cp1 = owner.make_slider(
        "C+1", -300, 0, int(owner.cp1_current * 1000)
    )
    owner.slider_alpha = owner.make_slider(
        "Low-pass Alpha", 1, 300, int(owner.channel_alpha_current * 1000)
    )

    owner.slider_cm1["edit"].setValidator(QDoubleValidator(-0.3, 0.0, 4, owner))
    owner.slider_cp1["edit"].setValidator(QDoubleValidator(-0.3, 0.0, 4, owner))
    owner.slider_alpha["edit"].setValidator(QDoubleValidator(0.001, 0.3, 3, owner))

    tx_layout.addLayout(owner.slider_cm1["layout"])
    tx_layout.addLayout(owner.slider_cp1["layout"])
    tx_layout.addLayout(owner.slider_alpha["layout"])
    tx_layout.addStretch()

    owner.slider_cm1["slider"].valueChanged.connect(owner.on_tap_slider_change)
    owner.slider_cp1["slider"].valueChanged.connect(owner.on_tap_slider_change)
    owner.slider_alpha["slider"].valueChanged.connect(owner.on_alpha_slider_change)

    for s in (
        owner.slider_cm1["slider"],
        owner.slider_cp1["slider"],
        owner.slider_alpha["slider"],
    ):
        s.sliderReleased.connect(owner.on_slider_released)

    owner.slider_cm1["edit"].editingFinished.connect(lambda: owner.on_edit_change("cm1"))
    owner.slider_cp1["edit"].editingFinished.connect(lambda: owner.on_edit_change("cp1"))
    owner.slider_alpha["edit"].editingFinished.connect(lambda: owner.on_edit_change("alpha"))

    # RX EQ Section
    rx_control_layout = QHBoxLayout()
    rx_view_label = QLabel("RX Eye/Wave View")
    rx_view_label.setFixedWidth(120)
    owner.rx_view_combo = QComboBox()
    owner.rx_view_combo.addItems(["Channel (Before RX EQ)", "CTLE", "DFE (Sample Margin)"])
    owner.rx_view_combo.currentIndexChanged.connect(owner.on_rx_view_change)
    rx_control_layout.addWidget(rx_view_label)
    rx_control_layout.addWidget(owner.rx_view_combo)

    owner.btn_reset_rx = QPushButton("Reset RX EQ")
    owner.btn_reset_rx.setFixedHeight(24)
    owner.btn_reset_rx.clicked.connect(owner.on_reset_rx)
    rx_control_layout.addWidget(owner.btn_reset_rx)
    rx_layout.addLayout(rx_control_layout)

    owner.slider_ctle = owner.make_slider("CTLE Boost", 0, 1000, int(owner.ctle_boost_current * 1000))
    owner.slider_dfe1 = owner.make_slider("DFE Tap 1", -500, 500, int(owner.dfe_tap1_current * 1000))
    owner.slider_dfe2 = owner.make_slider("DFE Tap 2", -500, 500, int(owner.dfe_tap2_current * 1000))
    owner.slider_dfe3 = owner.make_slider("DFE Tap 3", -500, 500, int(owner.dfe_tap3_current * 1000))

    owner.slider_ctle["edit"].setValidator(QDoubleValidator(0.0, 1.0, 3, owner))
    owner.slider_dfe1["edit"].setValidator(QDoubleValidator(-0.5, 0.5, 3, owner))
    owner.slider_dfe2["edit"].setValidator(QDoubleValidator(-0.5, 0.5, 3, owner))
    owner.slider_dfe3["edit"].setValidator(QDoubleValidator(-0.5, 0.5, 3, owner))

    rx_layout.addLayout(owner.slider_ctle["layout"])
    rx_layout.addLayout(owner.slider_dfe1["layout"])
    rx_layout.addLayout(owner.slider_dfe2["layout"])
    rx_layout.addLayout(owner.slider_dfe3["layout"])
    rx_layout.addStretch()

    owner.slider_ctle["slider"].valueChanged.connect(owner.on_rx_slider_change)
    owner.slider_dfe1["slider"].valueChanged.connect(owner.on_rx_slider_change)
    owner.slider_dfe2["slider"].valueChanged.connect(owner.on_rx_slider_change)
    owner.slider_dfe3["slider"].valueChanged.connect(owner.on_rx_slider_change)

    for s in (owner.slider_ctle["slider"], owner.slider_dfe1["slider"], owner.slider_dfe2["slider"], owner.slider_dfe3["slider"]):
        s.sliderReleased.connect(owner.on_slider_released)

    owner.slider_ctle["edit"].editingFinished.connect(lambda: owner.on_rx_edit_change("ctle"))
    owner.slider_dfe1["edit"].editingFinished.connect(lambda: owner.on_rx_edit_change("dfe1"))
    owner.slider_dfe2["edit"].editingFinished.connect(lambda: owner.on_rx_edit_change("dfe2"))
    owner.slider_dfe3["edit"].editingFinished.connect(lambda: owner.on_rx_edit_change("dfe3"))

    sliders_layout.addWidget(tx_group)
    sliders_layout.addWidget(rx_group)
    bottom_layout.addLayout(sliders_layout)

    scroll.setWidget(bottom_widget)
    layout.addWidget(scroll, stretch=0)
