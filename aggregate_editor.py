"""
Редактор шаблона агрегирующего ШК (EAN-13).
Поле номера — минимальная высота, без рамки.
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
    """Элемент на холсте агрегата."""

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
            "x_mm": self.x / 10.0,
            "y_mm": self.y / 10.0,
            "width": self.width,
            "height": self.height,
            "width_mm": self.width / 10.0,
            "height_mm": self.height / 10.0,
            "label": self.label,
            "type": self.type,
            "visible": self.visible,
        }


class AggregateEditor(QWidget):
    """Редактор шаблона агрегирующего ШК с drag-drop и валидацией границ N×N."""

    element_moved = pyqtSignal()
    element_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 400)
        self.setStyleSheet("background-color: #f0f0f0;")
        self.setMouseTracking(True)

        self.label_size = (30, 30)
        self.base_px_per_mm = 10
        self.scale = 1.0
        self.label_padding_mm = 1.0

        self.barcode_size_mm = 60
        self.sscc_size = 9

        self.sscc_data = {}
        self.current_sscc = None

        self.elements: List[DraggableElement] = []
        self._init_elements()

        self.dragging = False
        self.drag_element: Optional[DraggableElement] = None
        self.last_pos: Optional[QPoint] = None

    def _get_number_field_height_px(self) -> int:
        """Минимальная высота поля номера = высота шрифта + 2px отступ."""
        font_size = max(6, min(10, int(self.label_size[0] * 0.3)))
        return int((font_size + 2) * self.scale)

    def _init_elements(self):
        """Инициализация. УБРАН: box_number."""
        self.elements.clear()
        n = self.label_size[0]
        n_px = n * self.base_px_per_mm
        number_field_px = self._get_number_field_height_px()

        # Размер ШК без ограничения (валидация сделает это позже)
        barcode_w_mm = self.barcode_size_mm
        barcode_h_mm = max(8, barcode_w_mm * 0.35)

        barcode_w = int(barcode_w_mm * self.base_px_per_mm)
        barcode_h = int(barcode_h_mm * self.base_px_per_mm)

        # ЦЕНТРИРОВАНИЕ ШК по X и Y
        barcode_x = (n_px - barcode_w) // 2
        available_h = (
            n_px
            - number_field_px
            - 2 * int(self.label_padding_mm * self.base_px_per_mm)
        )
        barcode_y = (
            int(self.label_padding_mm * self.base_px_per_mm)
            + (available_h - barcode_h) // 2
        )

        self.elements.append(
            DraggableElement(
                "barcode",
                barcode_x,
                barcode_y,
                barcode_w,
                barcode_h,
                "EAN-13",
                "barcode",
                draggable=False,
            )
        )

        # SSCC — сверху ШК, центрирован по X
        sscc_text = "0123124126040900000000001"
        sscc_font = QFont("OCRB", int(self.sscc_size * 0.8))
        fm_sscc = QFontMetrics(sscc_font)
        max_sscc_w = n_px - 20
        sscc_text_w = min(fm_sscc.horizontalAdvance(sscc_text), max_sscc_w - 8)
        sscc_w = max(60, sscc_text_w + 8)
        sscc_h = 14
        sscc_x = (n_px - sscc_w) // 2
        sscc_y = max(5, barcode_y - sscc_h - 5)

        self.elements.append(
            DraggableElement(
                "sscc_text",
                sscc_x,
                sscc_y,
                sscc_w,
                sscc_h,
                sscc_text,
                "text",
                draggable=True,
            )
        )

    def set_label_size(self, size_mm: Tuple[int, int]):
        old_visibility = {e.id: e.visible for e in self.elements}
        old_positions = {e.id: (e.x, e.y, e.width, e.height) for e in self.elements}
        old_label_size = self.label_size[0]
        self.label_size = size_mm
        n = size_mm[0]

        self._init_elements()

        for elem in self.elements:
            if elem.id in old_visibility:
                elem.visible = old_visibility[elem.id]

        scale_factor = n / old_label_size if old_label_size > 0 else 1.0
        n_px = n * self.base_px_per_mm
        number_field_px = self._get_number_field_height_px()
        for elem in self.elements:
            if elem.id in old_positions and elem.draggable:
                old_x, old_y, old_w, old_h = old_positions[elem.id]
                elem.x = int(old_x * scale_factor)
                elem.y = int(old_y * scale_factor)
                elem.width = int(old_w * scale_factor)
                elem.height = int(old_h * scale_factor)
                elem.x = max(5, min(elem.x, n_px - elem.width - 5))
                elem.y = max(5, min(elem.y, n_px - number_field_px - elem.height - 5))

        self._update_element_labels()
        self.update()

    def set_sscc_data(self, sscc_data: dict):
        self.sscc_data = sscc_data
        self._update_element_labels()
        self.update()

    def _update_element_labels(self):
        if not self.sscc_data:
            return

        first_sscc = list(self.sscc_data.keys())[0]
        data = self.sscc_data[first_sscc]
        self.current_sscc = first_sscc

        sscc = data.get("sscc", "0123124126040900000000001")

        for elem in self.elements:
            if elem.id == "sscc_text":
                elem.label = sscc

    def set_config(
        self,
        barcode_size_mm: int = 60,
        show_hri: bool = True,
        show_box_number: bool = True,
        show_sscc: bool = True,
        hri_size: int = 10,
        box_number_size: int = 14,
        sscc_size: int = 9,
    ):
        self.barcode_size_mm = barcode_size_mm
        self.sscc_size = sscc_size

        n = self.label_size[0]
        n_px = n * self.base_px_per_mm
        number_field_px = self._get_number_field_height_px()

        # Обновляем barcode
        barcode_w_mm = min(self.barcode_size_mm, n - 2)
        barcode_h_mm = max(8, barcode_w_mm * 0.35)
        barcode_w = int(barcode_w_mm * self.base_px_per_mm)
        barcode_h = int(barcode_h_mm * self.base_px_per_mm)
        barcode_x = (n_px - barcode_w) // 2
        available_h = (
            n_px
            - number_field_px
            - 2 * int(self.label_padding_mm * self.base_px_per_mm)
        )
        barcode_y = (
            int(self.label_padding_mm * self.base_px_per_mm)
            + (available_h - barcode_h) // 2
        )

        for elem in self.elements:
            if elem.id == "barcode":
                elem.x = barcode_x
                elem.y = barcode_y
                elem.width = barcode_w
                elem.height = barcode_h
            elif elem.id == "sscc_text":
                # Пересчитываем позицию SSCC относительно нового barcode
                sscc_text = elem.label
                sscc_font = QFont("OCRB", int(self.sscc_size * 0.8))
                fm_sscc = QFontMetrics(sscc_font)
                max_sscc_w = n_px - 20
                sscc_text_w = min(fm_sscc.horizontalAdvance(sscc_text), max_sscc_w - 8)
                sscc_w = max(60, sscc_text_w + 8)
                sscc_h = 14
                sscc_x = (n_px - sscc_w) // 2
                sscc_y = max(5, barcode_y - sscc_h - 5)
                elem.x = sscc_x
                elem.y = sscc_y
                elem.width = sscc_w
                elem.height = sscc_h

        self._update_element_labels()
        self.update()

    def get_elements(self) -> List[dict]:
        return [elem.to_dict() for elem in self.elements if elem.visible]

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
        
        self._update_element_labels()
        self.update()
    
    def _get_label_rect(self) -> QRect:
        base_label_w = self.label_size[0] * self.base_px_per_mm
        base_label_h = self.label_size[1] * self.base_px_per_mm
        label_w_px = int(base_label_w * self.scale)
        label_h_px = int(base_label_h * self.scale)
        offset_x = (self.width() - label_w_px) // 2
        offset_y = (self.height() - label_h_px) // 2

        padding_px = int(self.label_padding_mm * self.base_px_per_mm * self.scale)
        number_field_px = self._get_number_field_height_px()
        return QRect(
            offset_x + padding_px,
            offset_y + padding_px,
            label_w_px - 2 * padding_px,
            label_h_px - 2 * padding_px - number_field_px,
        )

    def _get_number_field_rect(self) -> QRect:
        base_label_w = self.label_size[0] * self.base_px_per_mm
        base_label_h = self.label_size[1] * self.base_px_per_mm
        label_w_px = int(base_label_w * self.scale)
        label_h_px = int(base_label_h * self.scale)
        offset_x = (self.width() - label_w_px) // 2
        offset_y = (self.height() - label_h_px) // 2

        padding_px = int(self.label_padding_mm * self.base_px_per_mm * self.scale)
        number_field_px = self._get_number_field_height_px()
        return QRect(
            offset_x + padding_px,
            offset_y + label_h_px - padding_px - number_field_px,
            label_w_px - 2 * padding_px,
            number_field_px,
        )

    def _get_barcode_rect(self) -> QRect:
        base_label_w = self.label_size[0] * self.base_px_per_mm
        base_label_h = self.label_size[1] * self.base_px_per_mm
        label_w_px = int(base_label_w * self.scale)
        label_h_px = int(base_label_h * self.scale)
        offset_x = (self.width() - label_w_px) // 2
        offset_y = (self.height() - label_h_px) // 2

        for elem in self.elements:
            if elem.id == "barcode":
                elem_x = offset_x + int(elem.x * self.scale)
                elem_y = offset_y + int(elem.y * self.scale)
                elem_w = int(elem.width * self.scale)
                elem_h = int(elem.height * self.scale)
                return QRect(elem_x, elem_y, elem_w, elem_h)

        return QRect()

    def _get_forbidden_zone(self) -> QRect:
        """Только штрихкод — красная зона. Поле номера — отдельно."""
        return self._get_barcode_rect()

    def _clamp_position(
        self, elem: DraggableElement, new_x: int, new_y: int
    ) -> Tuple[int, int]:
        label_rect = self._get_label_rect()

        base_label_w = self.label_size[0] * self.base_px_per_mm
        base_label_h = self.label_size[1] * self.base_px_per_mm
        label_w_px = int(base_label_w * self.scale)
        label_h_px = int(base_label_h * self.scale)
        offset_x = (self.width() - label_w_px) // 2
        offset_y = (self.height() - label_h_px) // 2

        min_x = int((label_rect.x() - offset_x) / self.scale)
        max_x = int((label_rect.right() - offset_x) / self.scale) - elem.width
        min_y = int((label_rect.y() - offset_y) / self.scale)
        max_y = int((label_rect.bottom() - offset_y) / self.scale) - elem.height

        clamped_x = max(min_x, min(new_x, max_x))
        clamped_y = max(min_y, min(new_y, max_y))

        return clamped_x, clamped_y

    def _check_bounds(self, elem: DraggableElement, new_x: int, new_y: int) -> bool:
        clamped_x, clamped_y = self._clamp_position(elem, new_x, new_y)
        return (new_x == clamped_x) and (new_y == clamped_y)

    def _check_collision_with_forbidden(
        self, elem: DraggableElement, new_x: int, new_y: int
    ) -> bool:
        forbidden = self._get_forbidden_zone()

        base_label_w = self.label_size[0] * self.base_px_per_mm
        base_label_h = self.label_size[1] * self.base_px_per_mm
        label_w_px = int(base_label_w * self.scale)
        label_h_px = int(base_label_h * self.scale)
        offset_x = (self.width() - label_w_px) // 2
        offset_y = (self.height() - label_h_px) // 2

        elem_rect = QRect(
            offset_x + int(new_x * self.scale),
            offset_y + int(new_y * self.scale),
            int(elem.width * self.scale),
            int(elem.height * self.scale),
        )

        return forbidden.intersects(elem_rect)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor(240, 240, 240))

        base_label_w = self.label_size[0] * self.base_px_per_mm
        base_label_h = self.label_size[1] * self.base_px_per_mm
        label_w_px = int(base_label_w * self.scale)
        label_h_px = int(base_label_h * self.scale)

        offset_x = (self.width() - label_w_px) // 2
        offset_y = (self.height() - label_h_px) // 2

        padding_px = int(self.label_padding_mm * self.base_px_per_mm * self.scale)
        number_field_px = self._get_number_field_height_px()
        white_x = offset_x + padding_px
        white_y = offset_y + padding_px
        white_w = label_w_px - 2 * padding_px
        white_h = label_h_px - 2 * padding_px - number_field_px

        painter.fillRect(white_x, white_y, white_w, white_h, QColor(255, 255, 255))

        # Рамка этикетки
        pen = QPen(QColor(255, 0, 0), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(offset_x, offset_y, label_w_px, label_h_px)

        # Запретная зона штрихкода — ТОЛЬКО ОНА КРАСНАЯ
        forbidden = self._get_forbidden_zone()
        if forbidden.isValid():
            painter.fillRect(forbidden, QColor(255, 0, 0, 30))
            pen_forbidden = QPen(QColor(220, 50, 50), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen_forbidden)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(forbidden)

        # === ПОЛЕ НОМЕРА — минимальная высота, без рамки ===
        number_field_rect = self._get_number_field_rect()
        if number_field_rect.isValid():
            # Только номер агрегата, без рамки и подписи
            box_number = "1"
            if self.sscc_data:
                first_sscc = list(self.sscc_data.keys())[0]
                box_number = self.sscc_data[first_sscc].get("box_number", "1") or "1"
            number_text = f"#{box_number}"
            number_font_size = max(6, min(10, int(self.label_size[0] * 0.3)))
            painter.setFont(QFont("Arial", number_font_size, QFont.Weight.Bold))
            painter.setPen(QColor(0, 0, 0))
            fm_number = painter.fontMetrics()
            num_w = fm_number.horizontalAdvance(number_text)
            num_x = number_field_rect.x() + (number_field_rect.width() - num_w) // 2
            num_y = (
                number_field_rect.y()
                + (number_field_rect.height() + number_font_size) // 2
            )
            painter.drawText(num_x, num_y, number_text)

        # Отрисовка элементов
        for elem in self.elements:
            if not elem.visible:
                continue

            elem_x = offset_x + int(elem.x * self.scale)
            elem_y = offset_y + int(elem.y * self.scale)
            elem_w = int(elem.width * self.scale)
            elem_h = int(elem.height * self.scale)

            if elem.selected:
                painter.fillRect(
                    elem_x - 2,
                    elem_y - 2,
                    elem_w + 4,
                    elem_h + 4,
                    QColor(100, 150, 255, 100),
                )
                painter.setPen(QPen(QColor(100, 150, 255), 2, Qt.PenStyle.SolidLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(elem_x - 2, elem_y - 2, elem_w + 4, elem_h + 4)

            if elem.type == "barcode":
                self._draw_barcode(painter, elem_x, elem_y, elem_w, elem_h)
            else:
                if elem.id == "sscc_text":
                    base_font = self.sscc_size
                else:
                    base_font = 10

                font_size = max(8, int(base_font * self.scale * 0.9))
                font = QFont("Arial", font_size)
                if elem.id == "sscc_text":
                    font = QFont("OCRB", font_size)
                painter.setFont(font)

                fm = painter.fontMetrics()
                text_rect = fm.boundingRect(elem.label)
                text_width = text_rect.width()
                text_height = fm.height()
                padding_x = 4
                padding_y = 2

                draw_w = min(text_width + padding_x * 2, white_w - (elem_x - white_x))
                draw_h = min(text_height + padding_y * 2, white_h - (elem_y - white_y))
                draw_w = max(elem_w, draw_w)
                draw_h = max(elem_h, draw_h)
                draw_w = min(draw_w, white_w - (elem_x - white_x))
                draw_h = min(draw_h, white_h - (elem_y - white_y))

                text_x = elem_x + (draw_w - text_width) // 2
                text_y = elem_y + (draw_h - text_height) // 2 + text_height - 2

                painter.setPen(QPen(QColor(180, 180, 180), 1, Qt.PenStyle.DotLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(elem_x, elem_y, draw_w, draw_h)

                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(text_x, text_y, elem.label)

        painter.end()

    def _draw_barcode(self, painter: QPainter, x: int, y: int, w: int, h: int):
        """Рисует EAN-13, растянутый на всю ширину w и высоту h."""
        painter.setPen(Qt.PenStyle.NoPen)

        if w < 20 or h < 5:
            painter.fillRect(x, y, w, h, QColor(0, 0, 0))
            return

        # EAN-13: 95 модулей шириной, растягиваем на w
        module_w = w / 95.0

        # Упрощённая структура EAN-13
        patterns = []
        # Старт: 101
        patterns.extend([1, 0, 1])
        # Левая половина: 6 цифр × 7 модулей (паттерны A)
        for _ in range(6):
            patterns.extend([1, 0, 1, 0, 1, 0, 1])
        # Разделитель: 01010
        patterns.extend([0, 1, 0, 1, 0])
        # Правая половина: 6 цифр × 7 модулей (паттерны C)
        for _ in range(6):
            patterns.extend([0, 1, 0, 1, 0, 1, 0])
        # Стоп: 101
        patterns.extend([1, 0, 1])

        x_pos = x
        for bit in patterns:
            if bit:
                draw_w = max(1, round(module_w))
                if x_pos + draw_w <= x + w:
                    painter.setBrush(QColor(0, 0, 0))
                    painter.drawRect(int(x_pos), y, draw_w, h)
            x_pos += module_w

    def _get_element_at_pos(self, pos: QPoint) -> Optional[DraggableElement]:
        base_label_w = self.label_size[0] * self.base_px_per_mm
        base_label_h = self.label_size[1] * self.base_px_per_mm
        label_w_px = int(base_label_w * self.scale)
        label_h_px = int(base_label_h * self.scale)
        offset_x = (self.width() - label_w_px) // 2
        offset_y = (self.height() - label_h_px) // 2

        for elem in reversed(self.elements):
            if not elem.visible:
                continue

            elem_x = offset_x + int(elem.x * self.scale)
            elem_y = offset_y + int(elem.y * self.scale)
            elem_w = int(elem.width * self.scale)
            elem_h = int(elem.height * self.scale)

            if QRect(elem_x, elem_y, elem_w, elem_h).contains(pos):
                return elem
        return None

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
        dx = int((pos.x() - self.last_pos.x()) / self.scale)
        dy = int((pos.y() - self.last_pos.y()) / self.scale)

        new_x = self.drag_element.x + dx
        new_y = self.drag_element.y + dy

        # Блокировка: нельзя заходить в область штрихкода
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
