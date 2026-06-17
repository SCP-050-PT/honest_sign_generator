"""
Drag-and-drop canvas for template editing.
N×N этикетка, блокировка DM+QZ для текстовых элементов.
Поле номера — отдельная визуализация (синяя линия), НЕ красная зона.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPaintEvent,
)

from typing import List, Optional, Tuple


class DraggableElement:
    """Элемент на холсте."""

    def __init__(
        self,
        element_id: str,
        x: int,
        y: int,
        width: int,
        height: int,
        label: str,
        element_type: str = "text",
        draggable: bool = True,
    ):
        self.id = element_id
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.label = label
        self.type = element_type
        self.draggable = draggable
        self.selected = False
        self.visible = True

    def contains(self, point: QPoint) -> bool:
        return QRect(self.x, self.y, self.width, self.height).contains(point)

    def move(self, dx: int, dy: int):
        self.x += dx
        self.y += dy

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "label": self.label,
            "type": self.type,
            "visible": self.visible,
        }


class DragDropCanvas(QWidget):
    """Холст предпросмотра этикетки с Data Matrix."""

    element_moved = pyqtSignal()
    element_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        self.setStyleSheet("background-color: #f0f0f0;")

        self.label_size = (30, 30)
        self.base_px_per_mm = 10
        self.scale = 1.0

        self.quiet_zone_mm = 2.0
        self.bottom_field_mm = 0
        self.dm_size_mm = 12.0
        self.label_padding_mm = 1.0

        self.show_gtin = False
        self.show_article = False
        self.show_index = True
        self.gtin_size = 8
        self.article_size = 8

        self.config = {}
        self.code_info = None

        self.elements: List[DraggableElement] = []
        self._init_elements()

        self.dragging = False
        self.drag_element: Optional[DraggableElement] = None
        self.last_pos: Optional[QPoint] = None

        self.setMouseTracking(True)

    def _init_elements(self):
        """Инициализация элементов. Только DM (текстовые убраны)."""
        self.elements.clear()

        n = self.label_size[0]
        total_px = n * self.base_px_per_mm
        padding_px = int(self.label_padding_mm * self.base_px_per_mm)
        number_field_px = self._get_number_field_height_px()

        dm_px = int(self.dm_size_mm * self.base_px_per_mm)
        dm_px = max(50, min(dm_px, total_px - 2 * padding_px - 20))

        available_w = total_px - 2 * padding_px
        available_h = total_px - 2 * padding_px - number_field_px

        dm_x = padding_px + (available_w - dm_px) // 2
        dm_y = padding_px + (available_h - dm_px) // 2

        self.elements.append(
            DraggableElement(
                "barcode", dm_x, dm_y, dm_px, dm_px, "Data Matrix", "barcode", draggable=False
            )
        )

    def _get_total_px(self) -> int:
        return int(self.label_size[0] * self.base_px_per_mm * self.scale)

    def _get_offset(self) -> Tuple[int, int]:
        total_px = self._get_total_px()
        offset_x = (self.width() - total_px) // 2
        offset_y = (self.height() - total_px) // 2
        return offset_x, offset_y

    def _get_number_field_height_px(self) -> int:
        """Минимальная высота поля номера = высота шрифта + 2px отступ."""
        font_size = max(6, min(10, int(self.label_size[0] * 0.3)))
        return int((font_size + 2) * self.scale)

    def set_label_size(self, size_mm: Tuple[int, int]):
        old_visibility = {e.id: e.visible for e in self.elements}
        old_positions = {e.id: (e.x, e.y) for e in self.elements}
        self.label_size = size_mm
        n = size_mm[0]

        total_px = n * self.base_px_per_mm
        padding = int(self.label_padding_mm * self.base_px_per_mm)
        number_field_px = self._get_number_field_height_px()

        dm_px = int(self.dm_size_mm * self.base_px_per_mm)
        dm_px = max(50, min(dm_px, total_px - 2 * padding - 20))

        dm_x = (total_px - dm_px) // 2
        dm_y = (
            padding
            + number_field_px
            + (total_px - padding - number_field_px - dm_px) // 2
        )

        scale_factor = total_px / 300.0

        positions = {
            "barcode": (dm_x, dm_y, dm_px, dm_px),
            "article": (
                padding + 4,
                padding + 4,
                max(50, int(70 * scale_factor)),
                max(12, int(16 * scale_factor)),
            ),
            "gtin": (
                padding + 4,
                total_px
                - padding
                - number_field_px
                - max(10, int(14 * scale_factor))
                - 4,
                max(40, int(60 * scale_factor)),
                max(10, int(14 * scale_factor)),
            ),
        }

        for elem in self.elements:
            if elem.id in positions:
                x, y, w, h = positions[elem.id]
                elem.x = x
                elem.y = y
                elem.width = w
                elem.height = h
            elif elem.id in old_positions and elem.draggable:
                old_x, old_y = old_positions[elem.id]
                elem.x = int(old_x * scale_factor)
                elem.y = int(old_y * scale_factor)

        for elem in self.elements:
            if elem.id in old_visibility:
                elem.visible = old_visibility[elem.id]

        self.update()

    def set_dm_config(
        self,
        quiet_zone_mm: float = 2.0,
        bottom_field_mm: float = 0.0,
        dm_size_mm: float = 12.0,
        bottom_field_type: str = "index",
        gtin_size: int = 8,
        article_size: int = 8,
        index_size: int = 8,
        label_padding_mm: float = 1.0,
    ):
        self.quiet_zone_mm = quiet_zone_mm
        self.bottom_field_mm = 0
        self.dm_size_mm = dm_size_mm
        self.bottom_field_type = bottom_field_type
        self.label_padding_mm = label_padding_mm
        self.gtin_size = gtin_size
        self.article_size = article_size
        self.index_size = index_size

        self.set_label_size(self.label_size)

    def update_config(self, config: dict):
        self.config = config
        self.code_info = config.get("code_info")
        self.bottom_field_type = config.get("bottom_field_type", "index")
        self.gtin_size = config.get("gtin_size", 8)
        self.article_size = config.get("article_size", 8)
        self.index_size = config.get("index_size", 8)
        self.update()

    def get_elements(self) -> List[dict]:
        """Возвращает элементы с координатами в мм (x_mm, y_mm от верха этикетки)."""
        result = []
        for elem in self.elements:
            if not elem.visible:
                continue
            d = elem.to_dict()
            # Добавляем мм-координаты (y_mm от верха этикетки вниз)
            d["x_mm"] = elem.x / self.base_px_per_mm
            d["y_mm"] = elem.y / self.base_px_per_mm
            d["width_mm"] = elem.width / self.base_px_per_mm
            d["height_mm"] = elem.height / self.base_px_per_mm
            result.append(d)
        return result

    def set_elements(self, elements_data: List[dict]):
        """Восстановить элементы из сохранённого шаблона."""
        # Очищаем текущие элементы (кроме barcode)
        self.elements = [e for e in self.elements if e.id == "barcode"]
        
        for data in elements_data:
            elem_id = data.get("id", "")
            if elem_id == "barcode":
                # Обновляем позицию barcode
                for elem in self.elements:
                    if elem.id == "barcode":
                        elem.x = int(data.get("x", elem.x))
                        elem.y = int(data.get("y", elem.y))
                        elem.width = int(data.get("width", elem.width))
                        elem.height = int(data.get("height", elem.height))
                        elem.visible = data.get("visible", True)
                continue
                
            # Создаём новый элемент
            new_elem = DraggableElement(
                element_id=elem_id,
                x=int(data.get("x", 0)),
                y=int(data.get("y", 0)),
                width=int(data.get("width", 50)),
                height=int(data.get("height", 12)),
                label=data.get("label", elem_id),
                element_type=data.get("type", "text"),
                draggable=data.get("draggable", True),
            )
            new_elem.visible = data.get("visible", True)
            self.elements.append(new_elem)
        
        self.update()
    # === ВАЛИДАЦИЯ ===

    def _get_label_rect(self) -> QRect:
        total_px = self._get_total_px()
        offset_x, offset_y = self._get_offset()
        padding_px = int(self.label_padding_mm * self.base_px_per_mm)
        number_field_px = self._get_number_field_height_px()

        return QRect(
            offset_x + padding_px,
            offset_y + padding_px,
            total_px - 2 * padding_px,
            total_px - 2 * padding_px - number_field_px,
        )

    def _get_number_field_rect(self) -> QRect:
        total_px = self._get_total_px()
        offset_x, offset_y = self._get_offset()
        padding_px = int(self.label_padding_mm * self.base_px_per_mm)
        number_field_px = self._get_number_field_height_px()

        return QRect(
            offset_x + padding_px,
            offset_y + total_px - padding_px - number_field_px,
            total_px - 2 * padding_px,
            number_field_px,
        )

    def _get_dm_rect(self) -> QRect:
        offset_x, offset_y = self._get_offset()

        for elem in self.elements:
            if elem.id == "barcode":
                elem_x = offset_x + elem.x
                elem_y = offset_y + elem.y
                elem_w = elem.width
                elem_h = elem.height

                qz_px = int(self.quiet_zone_mm * self.base_px_per_mm)
                return QRect(
                    elem_x - qz_px,
                    elem_y - qz_px,
                    elem_w + 2 * qz_px,
                    elem_h + 2 * qz_px,
                )

        return QRect()

    def _get_forbidden_zone(self) -> QRect:
        """Только DM+QZ — красная зона. Поле номера — отдельно."""
        return self._get_dm_rect()

    def _clamp_position(
        self, elem: DraggableElement, new_x: int, new_y: int
    ) -> Tuple[int, int]:
        total_px = self._get_total_px()
        padding_px = int(self.label_padding_mm * self.base_px_per_mm)
        number_field_px = self._get_number_field_height_px()

        min_x = padding_px
        max_x = total_px - padding_px - elem.width
        min_y = padding_px
        max_y = total_px - padding_px - number_field_px - elem.height

        clamped_x = max(min_x, min(new_x, max_x))
        clamped_y = max(min_y, min(new_y, max_y))

        return clamped_x, clamped_y

    def _check_bounds(self, elem: DraggableElement, new_x: int, new_y: int) -> bool:
        clamped_x, clamped_y = self._clamp_position(elem, new_x, new_y)
        return (new_x == clamped_x) and (new_y == clamped_y)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor(240, 240, 240))

        total_px = self._get_total_px()
        offset_x, offset_y = self._get_offset()
        padding_px = int(self.label_padding_mm * self.base_px_per_mm)
        number_field_px = self._get_number_field_height_px()

        white_x = offset_x + padding_px
        white_y = offset_y + padding_px
        white_w = total_px - 2 * padding_px
        white_h = total_px - 2 * padding_px - number_field_px

        painter.fillRect(white_x, white_y, white_w, white_h, QColor(255, 255, 255))

        # Рамка этикетки
        pen = QPen(QColor(255, 0, 0), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(offset_x, offset_y, total_px, total_px)

        # Запретная зона DM+QZ — ТОЛЬКО ОНА КРАСНАЯ
        forbidden = self._get_forbidden_zone()
        if forbidden.isValid():
            painter.fillRect(forbidden, QColor(255, 0, 0, 30))
            pen_forbidden = QPen(QColor(220, 50, 50), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen_forbidden)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(forbidden)

            # === НИЖНЕЕ ПОЛЕ DM ===
        number_field_rect = self._get_number_field_rect()
        if number_field_rect.isValid():
            code_info = self.code_info or {}

            # Определяем что рисовать
            bottom_type = getattr(self, "bottom_field_type", "index")

            if bottom_type == "gtin":
                text = code_info.get("gtin", "")
                font_size = getattr(self, "gtin_size", 8)
            elif bottom_type == "article":
                text = code_info.get("article", "")
                font_size = self.config.get("article_size", 8)
            elif bottom_type == "index":
                text = f"#{code_info.get('global_index', 1)}"
                font_size = self.config.get("index_size", 8)
            else:  # none
                text = ""
                font_size = 8

            if text:
                font_size = max(5, min(16, font_size))
                painter.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
                painter.setPen(QColor(0, 0, 0))
                fm = painter.fontMetrics()
                text_w = fm.horizontalAdvance(text)
                text_x = (
                    number_field_rect.x() + (number_field_rect.width() - text_w) // 2
                )
                text_y = (
                    number_field_rect.y()
                    + (number_field_rect.height() + font_size) // 2
                )
                painter.drawText(text_x, text_y, text)

        # Отрисовка элементов — ТОЛЬКО DM
        for elem in self.elements:
            if not elem.visible:
                continue

            elem_x = offset_x + elem.x
            elem_y = offset_y + elem.y

            if elem.selected:
                painter.fillRect(
                    elem_x - 2,
                    elem_y - 2,
                    elem.width + 4,
                    elem.height + 4,
                    QColor(100, 150, 255, 100),
                )

            if elem.type == "barcode":
                self._draw_dm_with_qz(painter, elem_x, elem_y, elem.width, elem.height)

        painter.end()

    def _draw_dm_with_qz(self, painter: QPainter, x: int, y: int, w: int, h: int):
        qz_px = int(self.quiet_zone_mm * self.base_px_per_mm)

        qz_rect = QRect(x - qz_px, y - qz_px, w + 2 * qz_px, h + 2 * qz_px)
        pen_qz = QPen(QColor(220, 50, 50), 2, Qt.PenStyle.SolidLine)
        painter.setPen(pen_qz)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(qz_rect)

        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.setPen(QColor(220, 50, 50))
        painter.drawText(x - qz_px + 3, y - qz_px - 4, "QZ")

        painter.fillRect(x, y, w, h, QColor(0, 0, 0))

        import random

        random.seed(42)

        cell_size = max(3, w // 14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255))

        max_row = (h // cell_size) * cell_size
        max_col = (w // cell_size) * cell_size

        for row in range(0, max_row, cell_size):
            for col in range(0, max_col, cell_size):
                is_finder = (
                    (row < cell_size * 2 and col < cell_size * 2)
                    or (row < cell_size * 2 and col >= max_col - cell_size * 2)
                    or (row >= max_row - cell_size * 2 and col < cell_size * 2)
                )

                if is_finder:
                    continue
                elif random.random() > 0.55:
                    draw_w = min(cell_size - 2, w - col - 1)
                    draw_h = min(cell_size - 2, h - row - 1)
                    if draw_w > 0 and draw_h > 0:
                        painter.drawRect(x + col + 1, y + row + 1, draw_w, draw_h)

    def _get_element_at_pos(self, pos: QPoint) -> Optional[DraggableElement]:
        offset_x, offset_y = self._get_offset()

        for elem in reversed(self.elements):
            if not elem.visible:
                continue

            elem_x = offset_x + elem.x
            elem_y = offset_y + elem.y
            elem_w = elem.width
            elem_h = elem.height

            if QRect(elem_x, elem_y, elem_w, elem_h).contains(pos):
                return elem
        return None

    def _check_collision_with_forbidden(
        self, elem: DraggableElement, new_x: int, new_y: int
    ) -> bool:
        forbidden = self._get_forbidden_zone()
        offset_x, offset_y = self._get_offset()

        elem_rect = QRect(
            offset_x + new_x,
            offset_y + new_y,
            elem.width,
            elem.height,
        )

        return forbidden.intersects(elem_rect)

    def mousePressEvent(self, event: QMouseEvent):
        elem = self._get_element_at_pos(event.pos())

        if elem and elem.draggable:
            for e in self.elements:
                e.selected = False
            elem.selected = True
            self.drag_element = elem
            self.dragging = True
            self.last_pos = event.pos()
            self.element_selected.emit(elem.id)
        else:
            for e in self.elements:
                e.selected = False
            if elem and elem.id == "barcode":
                elem.selected = True

        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.dragging or not self.drag_element or not self.last_pos:
            return

        if not self.drag_element.draggable:
            return

        pos = event.pos()
        dx = pos.x() - self.last_pos.x()
        dy = pos.y() - self.last_pos.y()

        new_x = self.drag_element.x + dx
        new_y = self.drag_element.y + dy

        # Блокировка: нельзя заходить в DM+QZ
        if self._check_collision_with_forbidden(self.drag_element, new_x, new_y):
            return

        # Блокировка: нельзя выходить за границы (включая поле номера)
        if not self._check_bounds(self.drag_element, new_x, new_y):
            clamped_x, clamped_y = self._clamp_position(self.drag_element, new_x, new_y)
            self.drag_element.x = clamped_x
            self.drag_element.y = clamped_y
            self.last_pos = pos
            self.update()
            return

        self.drag_element.move(dx, dy)
        self.last_pos = pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.dragging:
            self.dragging = False
            self.drag_element = None
            self.last_pos = None
            self.element_moved.emit()
