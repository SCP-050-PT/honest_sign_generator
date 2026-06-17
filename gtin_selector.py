"""
GTIN selector component.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QLabel, QListWidget


class GtinSelector(QWidget):
    """Виджет выбора GTIN."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("GTIN:"))

        self.combo = QComboBox()
        layout.addWidget(self.combo)

        layout.addWidget(QLabel("Коды:"))
        self.list_codes = QListWidget()
        layout.addWidget(self.list_codes)

    def set_gtin_list(self, gtin_list: list):
        """Установка списка GTIN."""
        self.combo.clear()
        self.combo.addItems(gtin_list)

    def set_codes(self, codes: list):
        """Установка кодов для выбранного GTIN."""
        self.list_codes.clear()
        self.list_codes.addItems(codes[:100])  # Лимит отображения
        if len(codes) > 100:
            self.list_codes.addItem(f"... и ещё {len(codes) - 100} кодов")

    def current_gtin(self) -> str:
        """Получение текущего GTIN."""
        return self.combo.currentText()
