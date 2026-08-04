"""
Shared Window UI Helpers Mixin for PCIe TX/RX EQ Simulator.

Provides common UI widget creation and silent synchronization helper methods.
"""

from contextlib import contextmanager
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QSlider, QLineEdit
from PyQt5.QtCore import Qt

__all__ = ["WindowUiHelpersMixin"]


class WindowUiHelpersMixin:
    """
    Mixin providing common UI widget creation, layout construction, and
    signal-silent control synchronization helper methods for PCIeTxEqSimulator.
    """

    def make_slider(self, name, minimum, maximum, value):
        layout = QHBoxLayout()

        name_label = QLabel(name)
        name_label.setFixedWidth(120)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)
        slider.setValue(value)

        value_edit = QLineEdit()
        value_edit.setFixedWidth(80)
        value_edit.setAlignment(Qt.AlignRight)

        layout.addWidget(name_label)
        layout.addWidget(slider)
        layout.addWidget(value_edit)

        return {
            "layout": layout,
            "slider": slider,
            "edit": value_edit
        }

    @contextmanager
    def ui_sync(self):
        if self.syncing_ui:
            yield False
            return
        self.syncing_ui = True
        try:
            yield True
        finally:
            self.syncing_ui = False

    def set_slider_value_silent(self, slider, value):
        slider.blockSignals(True)
        try:
            slider.setValue(value)
        finally:
            slider.blockSignals(False)

    def set_edit_text_silent(self, edit, text):
        edit.blockSignals(True)
        try:
            edit.setText(text)
        finally:
            edit.blockSignals(False)
