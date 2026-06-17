"""
Template editor with three-page PDF preview.
ИСПРАВЛЕНО: добавлен вызов _update_pdf_info() при смене настроек.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QScrollArea,
)
from PyQt6.QtCore import pyqtSignal, Qt
from .components.drag_drop_canvas import DragDropCanvas
from .components.info_page_preview import InfoPagePreview
from .components.dynamic_right_panel import DynamicRightPanel
from .components.template_state import TemplateState
from .components.aggregate_editor import AggregateEditor


class TemplateEditor(QWidget):
    """Виджет редактора шаблона с предпросмотром трёх страниц PDF."""

    template_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.state = TemplateState(self)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # === ЛЕВАЯ ЧАСТЬ ===
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        lbl_title = QLabel("Редактор шаблона")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        left_layout.addWidget(lbl_title)

        # Табы страниц PDF
        self.page_tabs = QTabWidget()
        self.page_tabs.setDocumentMode(True)
        self.page_tabs.currentChanged.connect(self._on_page_changed)

        # Страница 1: EAN-13 (инфо)
        self.info_page = InfoPagePreview()
        self.page_tabs.addTab(self.info_page, "📄 Страница 1: EAN-13 (инфо)")

        # Страница 2: Data Matrix
        labels_container = QWidget()
        labels_layout = QVBoxLayout(labels_container)
        labels_layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = DragDropCanvas()
        labels_layout.addWidget(self.canvas, stretch=1)

        self.lbl_size = QLabel("Размер этикетки: 30×30 мм")
        self.lbl_size.setStyleSheet("color: #666;")
        labels_layout.addWidget(self.lbl_size)

        self.page_tabs.addTab(labels_container, "🏷️ Страница 2: Data Matrix")

        # Страница 3: Агрегат ШК
        self.aggregate_editor = AggregateEditor()
        self.page_tabs.addTab(self.aggregate_editor, "📦 Страница 3: Агрегат")

        self.page_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #ccc; }
            QTabBar::tab {
                padding: 8px 20px;
                font-size: 11px;
                background: #f5f5f5;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #4CAF50;
                color: white;
                font-weight: bold;
            }
        """)

        left_layout.addWidget(self.page_tabs, stretch=1)

        main_layout.addWidget(left_container, stretch=1)

        # === ПРАВАЯ ПАНЕЛЬ (динамическая) ===
        self.right_panel = DynamicRightPanel(self)
        self.right_panel.settings_changed.connect(self._on_settings_changed)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.right_panel)
        scroll.setFixedWidth(350)
        scroll.setMinimumHeight(400)

        main_layout.addWidget(scroll)

    def _on_page_changed(self, index: int):
        """При смене вкладки меняем видимые настройки."""
        if hasattr(self, "right_panel") and self.right_panel:
            self.right_panel.set_page(index)
            self._on_settings_changed()

    def _on_settings_changed(self):
        """Любая настройка изменена — обновляем редакторы."""
        panel = self.right_panel
        dm_n = panel.dm_label_size_mm      # <-- DM размер
        agg_n = panel.agg_label_size_mm    # <-- Агрегат размер

        # === ОБНОВЛЯЕМ print_mode В STATE ===
        self.state.print_mode = panel.print_mode_data

        # === РАЗМЕР ЭТИКЕТКИ — РАЗДЕЛЬНЫЙ ===
        self.canvas.set_label_size((dm_n, dm_n))
        self.aggregate_editor.set_label_size((agg_n, agg_n))

        # DM-настройки
        self.canvas.set_dm_config(
            quiet_zone_mm=panel.quiet_zone,
            bottom_field_mm=panel.bottom_field,
            dm_size_mm=panel.dm_size,
            bottom_field_type=panel.bottom_field_type,
            gtin_size=panel.gtin_size,
            article_size=panel.article_size,
            index_size=panel.index_size,
        )

        # Агрегат ШК
        self.aggregate_editor.set_config(
            barcode_size_mm=panel.aggregate_size,
            hri_size=panel.hri_size,
            box_number_size=panel.box_number_size,
            sscc_size=panel.sscc_size,
        )

        # Info page
        self.info_page.set_aggregate_size(panel.aggregate_size)

        self.state.update_label_size_text()
        self.state.validate_limit()

        # ИСПРАВЛЕНО: обновляем инфо о PDF в main_window
        parent = self.parent()
        while parent:
            if hasattr(parent, "_update_pdf_info"):
                parent._update_pdf_info()
                break
            parent = parent.parent()

    # === Прокси-методы ===

    def set_mode(self, mode: str):
        self.state.set_mode(mode)

    def set_sscc_data(self, data: dict):
        self.state.set_sscc_data(data)
        self.aggregate_editor.set_sscc_data(data)

    def select_gtin(self, gtin_text: str):
        self.state.select_gtin(gtin_text)

    def show_ean13_page(self):
        self.page_tabs.setCurrentIndex(0)

    def show_labels_page(self):
        self.page_tabs.setCurrentIndex(1)

    def show_aggregate_page(self):
        self.page_tabs.setCurrentIndex(2)

    def get_template_config(self) -> dict:
        return self.state.get_template_config()

    def _on_dm_settings_changed(self):
        """Обратная совместимость."""
        self._on_settings_changed()

    def _update_preview(self):
        """Обратная совместимость."""
        self.state.update_preview()
