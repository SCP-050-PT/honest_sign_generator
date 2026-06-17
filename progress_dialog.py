"""
Модальное окно прогресса с отменой.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QProgressBar,
    QLabel,
    QPushButton,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal


class ProgressDialog(QDialog):
    """Модальное окно прогресса с кнопкой Отмена."""

    cancelled = pyqtSignal()

    def __init__(self, title="Выполнение...", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(450)
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        self._cancelled = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Заголовок операции
        self.lbl_operation = QLabel("Инициализация...")
        self.lbl_operation.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(self.lbl_operation)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                text-align: center;
                height: 24px;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background-color: #9C27B0;
                border-radius: 3px;
            }
        """
        )
        layout.addWidget(self.progress_bar)

        # Детали (обработано/всего, скорость, ETA)
        self.lbl_details = QLabel("—")
        self.lbl_details.setStyleSheet("color: #666; font-size: 11px;")
        self.lbl_details.setWordWrap(True)
        layout.addWidget(self.lbl_details)

        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #ddd;")
        layout.addWidget(line)

        # Кнопка Отмена
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("❌ Отмена")
        self.btn_cancel.setFixedHeight(32)
        self.btn_cancel.setFixedWidth(120)
        self.btn_cancel.setStyleSheet(
            """
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d32f2f; }
            QPushButton:disabled { background-color: #ccc; color: #888; }
        """
        )
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def _on_cancel(self):
        self._cancelled = True
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("Отмена...")
        self.lbl_operation.setText("Отмена операции...")
        self.cancelled.emit()

    def is_cancelled(self) -> bool:
        return self._cancelled

    def set_operation(self, text: str):
        self.lbl_operation.setText(text)

    def set_progress(self, current: int, total: int):
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(min(percent, 100))
            self.progress_bar.setFormat(f"%p%  ({current:,} / {total:,})")
        else:
            self.progress_bar.setMaximum(0)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Обработано: %v")

    def set_details(self, text: str):
        formatted_text = text.replace("\n", "<br>")
        self.lbl_details.setText(formatted_text)

    def set_finished(self, success: bool = True):
        self.btn_cancel.setEnabled(False)
        if success:
            self.btn_cancel.setText("✓ Готово")
            self.btn_cancel.setStyleSheet(
                """
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: bold;
                }
            """
            )
        else:
            self.btn_cancel.setText("✗ Ошибка")
            self.btn_cancel.setStyleSheet(
                """
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: bold;
                }
            """
            )
