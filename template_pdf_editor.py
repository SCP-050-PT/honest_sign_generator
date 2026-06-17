"""
Редактор шаблона PDF с drag-drop DM и текстовых элементов.
Поддержка zoom (колёсико) и pan (пробел + движение / СКМ).
"""

import sys
from pathlib import Path

# Добавляем корень проекта в путь
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPixmap, QPen, QColor, QFont, QCursor, QFontMetrics

import fitz
from typing import Optional

from models.template_element import TemplateElement
from models.template_pdf_state import TemplatePdfState
from core.data_matrix import DataMatrixGenerator


class TemplatePdfEditor(QWidget):
    """Виджет редактора шаблона PDF."""

    element_moved = pyqtSignal(str, float, float)  # id, x_mm, y_mm
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = TemplatePdfState()
        self.dm_generator = DataMatrixGenerator(quiet_zone_mm=2)

        self.template_pixmap: Optional[QPixmap] = None
        self.px_per_mm: float = 10.0
        self.dm_pixmap: Optional[QPixmap] = None
        self.dm_pixmap_size_mm: float = 0.0

        self._default_cursor = QCursor(Qt.CursorShape.ArrowCursor)
        self._hand_cursor = QCursor(Qt.CursorShape.OpenHandCursor)
        self._closed_hand_cursor = QCursor(Qt.CursorShape.ClosedHandCursor)

        self._space_pressed = False
        self._middle_mouse_pressed = False

        self.setMouseTracking(True)
        self.setMinimumSize(400, 300)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_template(self, pdf_path: Path):
        """Загрузить PDF-шаблон."""
        doc = fitz.open(str(pdf_path))
        page = doc[0]

        rect = page.rect
        width_mm = rect.width * 0.3528
        height_mm = rect.height * 0.3528

        mat = fitz.Matrix(150 / 72, 150 / 72)
        pix = page.get_pixmap(matrix=mat)

        img_data = pix.tobytes("png")
        self.template_pixmap = QPixmap()
        self.template_pixmap.loadFromData(img_data)

        self.px_per_mm = self.template_pixmap.width() / width_mm

        doc.close()

        self.state.set_template(pdf_path, width_mm, height_mm)
        self._generate_dm_pixmap()

        self.state.zoom = 1.0
        self.state.pan_x = 0.0
        self.state.pan_y = 0.0

        self.update()

    def _generate_dm_pixmap(self):
        """Сгенерировать DM pixmap для отрисовки."""
        if not self.state.dm_element:
            return

        size_mm = self.state.dm_size_mm
        qz_mm = self.state.quiet_zone_mm

        if (
            self.dm_pixmap
            and self.dm_pixmap_size_mm == size_mm
            and self.state.cached_qz == qz_mm
        ):
            return

        test_code = "010460036542225921ABCDEF1234567890"
        try:
            dm_bytes = self.dm_generator.generate(
                test_code, target_size_mm=size_mm, dpi=150
            )

            self.dm_pixmap = QPixmap()
            self.dm_pixmap.loadFromData(dm_bytes)
            self.dm_pixmap_size_mm = size_mm
            self.state.cached_dm_size = size_mm
            self.state.cached_qz = qz_mm

        except Exception as e:
            print(f"[DM PREVIEW ERROR] {e}")
            self.dm_pixmap = None

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
        self.state.update_dm_settings(
            size_mm,
            quiet_zone_mm,
            bottom_field_type,
            gtin_size,
            article_size,
            index_size,
        )
        self._generate_dm_pixmap()
        self.update()

    def _mm_to_px(self, mm: float) -> float:
        return mm * self.px_per_mm * self.state.zoom

    def _px_to_mm(self, px: float) -> float:
        return px / (self.px_per_mm * self.state.zoom)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        painter.fillRect(self.rect(), QColor("#f0f0f0"))

        if not self.template_pixmap:
            painter.setPen(QColor("#999"))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Загрузите PDF-шаблон"
            )
            return

        template_w_px = self._mm_to_px(self.state.page_width_mm)
        template_h_px = self._mm_to_px(self.state.page_height_mm)

        offset_x = (self.width() - template_w_px) / 2 + self.state.pan_x
        offset_y = (self.height() - template_h_px) / 2 + self.state.pan_y

        scaled_pixmap = self.template_pixmap.scaled(
            int(template_w_px),
            int(template_h_px),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(int(offset_x), int(offset_y), scaled_pixmap)

        for elem in self.state.elements:
            self._draw_element(painter, elem, offset_x, offset_y)

    def _draw_element(
        self, painter: QPainter, elem: TemplateElement, offset_x: float, offset_y: float
    ):
        if elem.type == "dm":
            self._draw_dm(painter, elem, offset_x, offset_y)
        else:
            self._draw_text(painter, elem, offset_x, offset_y)

    def _draw_dm(
        self, painter: QPainter, elem: TemplateElement, offset_x: float, offset_y: float
    ):
        if elem.quiet_zone_mm > 0:
            qz_px = self._mm_to_px(elem.quiet_zone_mm)
            total_size_px = self._mm_to_px(elem.size_mm + 2 * elem.quiet_zone_mm)

            x = offset_x + self._mm_to_px(elem.x_mm) - qz_px
            y = offset_y + self._mm_to_px(elem.y_mm) - qz_px

            pen = QPen(QColor("#FF6B6B"))
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(int(x), int(y), int(total_size_px), int(total_size_px))

        dm_size_px = self._mm_to_px(elem.size_mm)
        x = offset_x + self._mm_to_px(elem.x_mm)
        y = offset_y + self._mm_to_px(elem.y_mm)

        if self.dm_pixmap:
            scaled_dm = self.dm_pixmap.scaled(
                int(dm_size_px),
                int(dm_size_px),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            painter.drawPixmap(int(x), int(y), scaled_dm)
        else:
            painter.fillRect(
                int(x), int(y), int(dm_size_px), int(dm_size_px), QColor("#333")
            )

        if self.state.dragged_element_id == elem.id:
            pen = QPen(QColor("#2196F3"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(int(x), int(y), int(dm_size_px), int(dm_size_px))

    def _draw_text(
        self, painter: QPainter, elem: TemplateElement, offset_x: float, offset_y: float
    ):
        x = offset_x + self._mm_to_px(elem.x_mm)
        y = offset_y + self._mm_to_px(elem.y_mm)

        font_px = max(8, int(self._mm_to_px(elem.font_size * 0.35)))
        font = QFont("Arial", font_px)
        painter.setFont(font)

        display_text = elem.text or self._get_display_text(elem.text_type)

        metrics = QFontMetrics(font)
        text_w = metrics.horizontalAdvance(display_text)
        text_h = metrics.height()

        painter.fillRect(
            int(x - 2),
            int(y - text_h + 2),
            text_w + 4,
            text_h,
            QColor(255, 255, 255, 200),
        )

        painter.setPen(QColor("#333"))
        painter.drawText(int(x), int(y), display_text)

        if self.state.dragged_element_id == elem.id:
            pen = QPen(QColor("#2196F3"))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(int(x - 2), int(y - text_h + 2), text_w + 4, text_h)

    def _get_display_text(self, text_type: str) -> str:
        texts = {
            "gtin": "4600365422259",
            "article": "FT62007",
            "index": "#1",
            "none": "",
        }
        return texts.get(text_type, "")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x_mm, y_mm = self._screen_to_mm(event.pos())
            elem = self.state.get_element_at(x_mm, y_mm)

            if elem and not self._space_pressed:
                self.state.dragged_element_id = elem.id
                self.state.drag_start_x = event.pos().x()
                self.state.drag_start_y = event.pos().y()
                self.state.drag_element_start_x = elem.x_mm
                self.state.drag_element_start_y = elem.y_mm
                self.setCursor(self._closed_hand_cursor)
            else:
                self.state.is_panning = True
                self.state.pan_start_x = event.pos().x()
                self.state.pan_start_y = event.pos().y()
                self.state.pan_start_offset_x = self.state.pan_x
                self.state.pan_start_offset_y = self.state.pan_y
                self.setCursor(self._closed_hand_cursor)

        elif event.button() == Qt.MouseButton.MiddleButton:
            self._middle_mouse_pressed = True
            self.state.is_panning = True
            self.state.pan_start_x = event.pos().x()
            self.state.pan_start_y = event.pos().y()
            self.state.pan_start_offset_x = self.state.pan_x
            self.state.pan_start_offset_y = self.state.pan_y
            self.setCursor(self._closed_hand_cursor)

        self.update()

    def mouseMoveEvent(self, event):
        if self.state.dragged_element_id and not self._space_pressed:
            dx_px = event.pos().x() - self.state.drag_start_x
            dy_px = event.pos().y() - self.state.drag_start_y

            dx_mm = self._px_to_mm(dx_px)
            dy_mm = self._px_to_mm(dy_px)

            for elem in self.state.elements:
                if elem.id == self.state.dragged_element_id:
                    elem.x_mm = self.state.drag_element_start_x + dx_mm
                    elem.y_mm = self.state.drag_element_start_y + dy_mm

                    elem.x_mm = max(0, min(elem.x_mm, self.state.page_width_mm))
                    elem.y_mm = max(0, min(elem.y_mm, self.state.page_height_mm))
                    break

            self.element_moved.emit(
                self.state.dragged_element_id,
                self.state.elements[0].x_mm if self.state.elements else 0,
                self.state.elements[0].y_mm if self.state.elements else 0,
            )
            self.update()

        elif self.state.is_panning:
            dx = event.pos().x() - self.state.pan_start_x
            dy = event.pos().y() - self.state.pan_start_y

            self.state.pan_x = self.state.pan_start_offset_x + dx
            self.state.pan_y = self.state.pan_start_offset_y + dy
            self.update()

        else:
            x_mm, y_mm = self._screen_to_mm(event.pos())
            elem = self.state.get_element_at(x_mm, y_mm)

            if elem and not self._space_pressed:
                self.setCursor(self._closed_hand_cursor)
            elif self._space_pressed:
                self.setCursor(self._hand_cursor)
            else:
                self.setCursor(self._default_cursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.state.dragged_element_id = None
            if not self._middle_mouse_pressed:
                self.state.is_panning = False

            if self._space_pressed:
                self.setCursor(self._hand_cursor)
            else:
                self.setCursor(self._default_cursor)

        elif event.button() == Qt.MouseButton.MiddleButton:
            self._middle_mouse_pressed = False
            self.state.is_panning = False
            if not self._space_pressed:
                self.setCursor(self._default_cursor)

        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        zoom_factor = 1.1 if delta > 0 else 0.9

        new_zoom = self.state.zoom * zoom_factor
        new_zoom = max(self.state.min_zoom, min(self.state.max_zoom, new_zoom))

        if new_zoom != self.state.zoom:
            self.state.zoom = new_zoom
            self.zoom_changed.emit(new_zoom)
            self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self._space_pressed = True
            if not self.state.dragged_element_id:
                self.setCursor(self._hand_cursor)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self._space_pressed = False
            if not self.state.dragged_element_id and not self.state.is_panning:
                self.setCursor(self._default_cursor)

    def _screen_to_mm(self, pos) -> tuple:
        template_w_px = self._mm_to_px(self.state.page_width_mm)
        template_h_px = self._mm_to_px(self.state.page_height_mm)

        offset_x = (self.width() - template_w_px) / 2 + self.state.pan_x
        offset_y = (self.height() - template_h_px) / 2 + self.state.pan_y

        x_mm = self._px_to_mm(pos.x() - offset_x)
        y_mm = self._px_to_mm(pos.y() - offset_y)

        return x_mm, y_mm

    def get_config(self) -> dict:
        return self.state.get_config()
