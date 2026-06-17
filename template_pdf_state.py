"""
Состояние редактора шаблона PDF.
"""

from typing import List, Optional, Dict
from pathlib import Path
from .template_element import TemplateElement


class TemplatePdfState:
    """Состояние редактора шаблона PDF."""

    def __init__(self):
        self.template_path: Optional[Path] = None
        self.template_pixmap_path: Optional[Path] = None
        self.page_width_mm: float = 210.0
        self.page_height_mm: float = 297.0

        # Элементы на шаблоне
        self.elements: List[TemplateElement] = []

        # DM-элемент (всегда один)
        self.dm_element: Optional[TemplateElement] = None

        # Текстовый элемент (нижнее поле DM)
        self.text_element: Optional[TemplateElement] = None

        # Настройки DM
        self.dm_size_mm: float = 16.0
        self.quiet_zone_mm: float = 2.0
        self.bottom_field_type: str = "index"  # "none" | "gtin" | "index" | "article"
        self.gtin_size: int = 8
        self.article_size: int = 8
        self.index_size: int = 5

        # Zoom
        self.zoom: float = 1.0
        self.min_zoom: float = 0.1
        self.max_zoom: float = 5.0

        # Pan offset
        self.pan_x: float = 0.0
        self.pan_y: float = 0.0

        # Drag state
        self.dragged_element_id: Optional[str] = None
        self.drag_start_x: float = 0.0
        self.drag_start_y: float = 0.0
        self.drag_element_start_x: float = 0.0
        self.drag_element_start_y: float = 0.0

        # Pan state
        self.is_panning: bool = False
        self.pan_start_x: float = 0.0
        self.pan_start_y: float = 0.0
        self.pan_start_offset_x: float = 0.0
        self.pan_start_offset_y: float = 0.0

        # Кэш DM pixmap
        self.dm_pixmap_cache: Optional[object] = None  # QPixmap
        self.cached_dm_size: float = 0.0
        self.cached_qz: float = 0.0

    def set_template(self, path: Path, width_mm: float, height_mm: float):
        """Установить шаблон PDF."""
        self.template_path = path
        self.page_width_mm = width_mm
        self.page_height_mm = height_mm

        # Создаём DM-элемент по центру
        self.dm_element = TemplateElement(
            type="dm",
            x_mm=width_mm / 2 - self.dm_size_mm / 2,
            y_mm=height_mm / 2 - self.dm_size_mm / 2,
            size_mm=self.dm_size_mm,
            quiet_zone_mm=self.quiet_zone_mm,
        )

        # Создаём текстовый элемент под DM
        self._update_text_element()

        self.elements = [self.dm_element]
        if self.text_element and self.bottom_field_type != "none":
            self.elements.append(self.text_element)

    def _update_text_element(self):
        """Обновить текстовый элемент в зависимости от настроек."""
        if self.bottom_field_type == "none" or not self.dm_element:
            self.text_element = None
            return

        # Позиция под DM
        text_y = self.dm_element.y_mm + self.dm_element.size_mm + 2.0

        font_size = self.index_size
        if self.bottom_field_type == "gtin":
            font_size = self.gtin_size
        elif self.bottom_field_type == "article":
            font_size = self.article_size

        self.text_element = TemplateElement(
            type="text",
            x_mm=self.dm_element.x_mm,  # ← По умолчанию под DM
            y_mm=text_y,
            text_type=self.bottom_field_type,
            font_size=font_size,
            text=self._get_preview_text(self.bottom_field_type),
        )

    def _get_preview_text(self, text_type: str) -> str:
        texts = {
            "gtin": "4600365422259",
            "article": "FT62007",
            "index": "#1",
            "none": "",
        }
        return texts.get(text_type, "")
    
    def update_dm_settings(
        self,
        size_mm: float,
        quiet_zone_mm: float,
        bottom_field_type: str,
        gtin_size: int,
        article_size: int,
        index_size: int,
    ):
        """Обновить настройки DM."""
        self.dm_size_mm = size_mm
        self.quiet_zone_mm = quiet_zone_mm
        self.bottom_field_type = bottom_field_type
        self.gtin_size = gtin_size
        self.article_size = article_size
        self.index_size = index_size

        if self.dm_element:
            self.dm_element.size_mm = size_mm
            self.dm_element.quiet_zone_mm = quiet_zone_mm

        self._update_text_element()
        self._rebuild_elements()

    def _rebuild_elements(self):
        """Перестроить список элементов."""
        self.elements = []
        if self.dm_element:
            self.elements.append(self.dm_element)
        if self.text_element and self.bottom_field_type != "none":
            self.elements.append(self.text_element)

    def get_element_at(self, x_mm: float, y_mm: float) -> Optional[TemplateElement]:
        """Найти элемент по координатам (мм)."""
        # Проверяем в обратном порядке (сверху вниз)
        for elem in reversed(self.elements):
            if self._hit_test(elem, x_mm, y_mm):
                return elem
        return None

    def _hit_test(self, elem: TemplateElement, x_mm: float, y_mm: float) -> bool:
        if elem.type == "dm":
            size = elem.size_mm + 2 * elem.quiet_zone_mm
            return (elem.x_mm <= x_mm <= elem.x_mm + size and
                    elem.y_mm <= y_mm <= elem.y_mm + size)
        else:  # text
            # Конвертируем pt → mm (1 pt ≈ 0.3528 mm)
            font_size_mm = elem.font_size * 0.3528
            # Ширина символа ≈ 0.6 * font_size_mm
            text_width_mm = len(elem.text) * font_size_mm * 0.6 if elem.text else 15
            text_height_mm = font_size_mm * 1.2
            
            # Текст рисуется с базовой линии в y, текст ВЫШЕ y
            padding_mm = 3  # 3 мм отступ
            return (elem.x_mm - padding_mm <= x_mm <= elem.x_mm + text_width_mm + padding_mm and
                    elem.y_mm - text_height_mm - padding_mm <= y_mm <= elem.y_mm + padding_mm)

    def move_element(self, element_id: str, dx_mm: float, dy_mm: float):
        """Переместить элемент."""
        for elem in self.elements:
            if elem.id == element_id:
                elem.x_mm += dx_mm
                elem.y_mm += dy_mm

                # Ограничиваем границами шаблона
                elem.x_mm = max(0, min(elem.x_mm, self.page_width_mm))
                elem.y_mm = max(0, min(elem.y_mm, self.page_height_mm))
                break

    def get_config(self) -> dict:
        """Получить конфигурацию для генерации."""
        return {
            "template_path": str(self.template_path) if self.template_path else None,
            "page_width_mm": self.page_width_mm,
            "page_height_mm": self.page_height_mm,
            "dm_element": {
                "x_mm": self.dm_element.x_mm if self.dm_element else 0,
                "y_mm": self.dm_element.y_mm if self.dm_element else 0,
                "size_mm": self.dm_size_mm,
                "quiet_zone_mm": self.quiet_zone_mm,
            },
            "text_element": (
                {
                    "x_mm": self.text_element.x_mm if self.text_element else 0,
                    "y_mm": self.text_element.y_mm if self.text_element else 0,
                    "text_type": self.bottom_field_type,
                    "font_size": (
                        self.text_element.font_size if self.text_element else 8
                    ),
                }
                if self.text_element and self.bottom_field_type != "none"
                else None
            ),
            "dm_size_mm": self.dm_size_mm,
            "quiet_zone_mm": self.quiet_zone_mm,
            "bottom_field_type": self.bottom_field_type,
            "gtin_size": self.gtin_size,
            "article_size": self.article_size,
            "index_size": self.index_size,
        }
