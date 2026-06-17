"""
About dialog.
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt


class AboutDialog(QDialog):
    """Диалог 'О программе'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout(self)

        title = QLabel("Генератор Data Matrix")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version = QLabel("Версия 1.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        desc = QLabel(
            "Генератор этикеток Честный ЗНАК\n\n"
            "Возможности:\n"
            "• Загрузка кодов из Excel\n"
            "• Генерация Data Matrix\n"
            "• Настраиваемые шаблоны этикеток\n"
            "• Размеры 15×15 мм и 30×30 мм\n"
            "• Quiet Zone 2 мм\n"
            "• Агрегирующий штрихкод"
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        btn = QPushButton("Закрыть")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
