"""
Property panel for selected element.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSpinBox, QFormLayout


class PropertyPanel(QWidget):
    """Панель свойств выбранного элемента."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        lbl = QLabel("Свойства элемента")
        lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl)

        self.form = QFormLayout()

        self.spin_x = QSpinBox()
        self.spin_x.setRange(0, 1000)
        self.form.addRow("X:", self.spin_x)

        self.spin_y = QSpinBox()
        self.spin_y.setRange(0, 1000)
        self.form.addRow("Y:", self.spin_y)

        layout.addLayout(self.form)
        layout.addStretch()

    def set_element(self, element_data: dict):
        """Установка данных элемента."""
        self.spin_x.setValue(element_data.get("x", 0))
        self.spin_y.setValue(element_data.get("y", 0))
