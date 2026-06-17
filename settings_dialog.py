"""
Settings dialog for label configuration.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QPushButton,
    QFormLayout,
    QGroupBox,
    QDialogButtonBox,
)


class SettingsDialog(QDialog):
    """Диалог настроек размеров и параметров."""

    def __init__(self, parent=None, current_settings: dict = None):
        super().__init__(parent)
        self.setWindowTitle("Настройки этикетки")
        self.setMinimumWidth(300)

        self.settings = current_settings or {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Группа размеров
        size_group = QGroupBox("Размер этикетки")
        size_layout = QFormLayout(size_group)

        self.cmb_size = QComboBox()
        self.cmb_size.addItems(["15×15 мм", "30×30 мм"])
        current_size = self.settings.get("label_size", (30, 30))
        self.cmb_size.setCurrentIndex(0 if current_size[0] == 15 else 1)
        size_layout.addRow("Стандартный размер:", self.cmb_size)

        # Пользовательский размер
        self.spin_width = QSpinBox()
        self.spin_width.setRange(10, 100)
        self.spin_width.setValue(current_size[0])
        self.spin_width.setSuffix(" мм")
        size_layout.addRow("Ширина:", self.spin_width)

        self.spin_height = QSpinBox()
        self.spin_height.setRange(10, 100)
        self.spin_height.setValue(current_size[1])
        self.spin_height.setSuffix(" мм")
        size_layout.addRow("Высота:", self.spin_height)

        layout.addWidget(size_group)

        # Quiet Zone
        quiet_group = QGroupBox("Quiet Zone (граница)")
        quiet_layout = QFormLayout(quiet_group)

        self.spin_quiet = QSpinBox()
        self.spin_quiet.setRange(1, 10)
        self.spin_quiet.setValue(self.settings.get("quiet_zone", 2))
        self.spin_quiet.setSuffix(" мм")
        quiet_layout.addRow("Отступ:", self.spin_quiet)

        layout.addWidget(quiet_group)

        # DPI для печати
        dpi_group = QGroupBox("Качество печати")
        dpi_layout = QFormLayout(dpi_group)

        self.spin_dpi = QSpinBox()
        self.spin_dpi.setRange(150, 600)
        self.spin_dpi.setSingleStep(50)
        self.spin_dpi.setValue(self.settings.get("dpi", 300))
        self.spin_dpi.setSuffix(" DPI")
        dpi_layout.addRow("Разрешение:", self.spin_dpi)

        layout.addWidget(dpi_group)

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Связь размеров
        self.cmb_size.currentTextChanged.connect(self._on_preset_changed)

    def _on_preset_changed(self, text: str):
        """Изменение пресета размера."""
        if "15×15" in text:
            self.spin_width.setValue(15)
            self.spin_height.setValue(15)
        else:
            self.spin_width.setValue(30)
            self.spin_height.setValue(30)

    def get_settings(self) -> dict:
        """Получение настроек."""
        return {
            "label_size": (self.spin_width.value(), self.spin_height.value()),
            "quiet_zone": self.spin_quiet.value(),
            "dpi": self.spin_dpi.value(),
        }
