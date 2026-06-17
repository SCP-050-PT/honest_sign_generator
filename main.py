"""
Main entry point for Honest Sign Generator.
"""

import sys
from pathlib import Path

# Добавляем корень в path для импортов
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from gui.main_window import MainWindow


def main():
    """Запуск приложения."""
    # Включаем поддержку высокого DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Honest Sign Generator")
    app.setApplicationVersion("1.0")

    # Шрифт по умолчанию
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Стили
    app.setStyle("Fusion")

    # Создание и показ главного окна
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
