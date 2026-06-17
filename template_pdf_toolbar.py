"""
Toolbar для редактора шаблона PDF с zoom controls.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QSlider
from PyQt6.QtCore import Qt, pyqtSignal


class TemplatePdfToolbar(QWidget):
    """Toolbar с контролами zoom для редактора шаблона."""

    zoom_in = pyqtSignal()
    zoom_out = pyqtSignal()
    zoom_reset = pyqtSignal()
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False  # Флаг блокировки рекурсии
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 5, 10, 5)

        # Zoom out
        self.btn_zoom_out = QPushButton("🔍−")
        self.btn_zoom_out.setFixedSize(32, 28)
        self.btn_zoom_out.setToolTip("Уменьшить")
        self.btn_zoom_out.clicked.connect(self.zoom_out.emit)
        layout.addWidget(self.btn_zoom_out)

        # Zoom slider
        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(10, 500)
        self.slider_zoom.setValue(100)
        self.slider_zoom.setFixedWidth(120)
        self.slider_zoom.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider_zoom)

        # Zoom in
        self.btn_zoom_in = QPushButton("🔍+")
        self.btn_zoom_in.setFixedSize(32, 28)
        self.btn_zoom_in.setToolTip("Увеличить")
        self.btn_zoom_in.clicked.connect(self.zoom_in.emit)
        layout.addWidget(self.btn_zoom_in)

        # Zoom label
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(50)
        self.lbl_zoom.setStyleSheet("font-size: 11px; color: #666;")
        layout.addWidget(self.lbl_zoom)

        # Reset
        self.btn_reset = QPushButton("↺")
        self.btn_reset.setFixedSize(32, 28)
        self.btn_reset.setToolTip("Сбросить масштаб")
        self.btn_reset.clicked.connect(self.zoom_reset.emit)
        layout.addWidget(self.btn_reset)

        layout.addStretch()

        # Подсказка
        self.lbl_hint = QLabel(
            "🖱️ Колёсико = zoom  |  Пробел + drag = перемещение  |  Drag элемент = перемещение"
        )
        self.lbl_hint.setStyleSheet("font-size: 10px; color: #888;")
        layout.addWidget(self.lbl_hint)

    def _on_slider_changed(self, value: int):
        if self._updating:
            return
        zoom = value / 100.0
        self.lbl_zoom.setText(f"{value}%")
        self.zoom_changed.emit(zoom)

    def set_zoom(self, zoom: float):
        """Установить значение zoom извне (без эмиссии сигнала)."""
        self._updating = True
        try:
            value = int(zoom * 100)
            value = max(10, min(500, value))
            self.slider_zoom.setValue(value)
            self.lbl_zoom.setText(f"{value}%")
        finally:
            self._updating = False
