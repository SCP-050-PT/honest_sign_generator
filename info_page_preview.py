# gui/components/info_page_preview.py
"""
Предпросмотр первой страницы PDF (EAN-13 информация).
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QFont


class InfoPagePreview(QWidget):
    """Предпросмотр первой страницы PDF (EAN-13 информация)."""

    def __init__(self):
        super().__init__()
        self.gtins_data = []
        self.current_gtin = None
        self.aggregate_size_mm = 60

    def set_data(self, gtin_data: dict):
        self.current_gtin = gtin_data
        self.update()

    def set_aggregate_size(self, size_mm: int):
        self.aggregate_size_mm = size_mm
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(255, 255, 255))

        if not self.current_gtin:
            painter.setPen(QColor(150, 150, 150))
            painter.setFont(QFont("Arial", 12))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Загрузите Excel для просмотра\nстраницы с EAN-13",
            )
            painter.end()
            return

        margin = 20
        y = margin

        painter.setPen(QColor(0, 0, 0))
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        article = self.current_gtin.get("article", "UNKNOWN")
        painter.drawText(margin, y, f"Артикул: {article}")
        y += 25

        painter.setFont(QFont("Arial", 11))
        gtin = self.current_gtin.get("gtin", "UNKNOWN")
        painter.drawText(margin, y, f"GTIN: {gtin}")
        y += 30

        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawLine(margin, y, self.width() - margin, y)
        y += 20

        painter.setPen(QColor(0, 0, 0))
        painter.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        sscc_list = self.current_gtin.get("sscc_list", [])
        painter.drawText(margin, y, f"Агрегирующие ШК (EAN-13): {len(sscc_list)} шт.")
        y += 35

        for idx, sscc_info in enumerate(sscc_list[:5]):
            sscc = sscc_info.get("sscc", "")
            count = sscc_info.get("code_count", 0)
            ean_code = sscc[-13:] if len(sscc) >= 13 else sscc.zfill(13)

            preview_scale = min(
                1.0, (self.width() - 2 * margin) / (self.aggregate_size_mm * 3)
            )
            bar_width = int(self.aggregate_size_mm * preview_scale)
            bar_height = int(20 * preview_scale)

            self._draw_ean13_stub(
                painter, margin, y, bar_width, bar_height, ean_code, idx + 1, count
            )

            y += bar_height + int(35 * preview_scale)

            if y > self.height() - 40:
                painter.setPen(QColor(150, 150, 150))
                painter.drawText(margin, y, "... и другие")
                break

        painter.end()

    def _draw_ean13_stub(
        self,
        painter: QPainter,
        x: int,
        y: int,
        w: int,
        h: int,
        ean_code: str,
        number: int,
        count: int,
    ):
        """Рисует заглушку EAN-13 штрих-кода."""
        if w <= 0 or h <= 0:
            return

        painter.setPen(QColor(0, 0, 0))
        painter.setFont(QFont("Arial", max(10, int(h * 0.4)), QFont.Weight.Bold))
        painter.drawText(x, y - 5, f"#{number}")

        ean_digits = [int(c) for c in ean_code if c.isdigit()]
        if len(ean_digits) != 13:
            ean_digits = [3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]

        module_w = max(0.5, w / 95)

        patterns = {
            0: [3, 2, 1, 1],
            1: [2, 2, 2, 1],
            2: [2, 1, 2, 2],
            3: [1, 4, 1, 1],
            4: [1, 1, 3, 2],
            5: [1, 2, 3, 1],
            6: [1, 1, 1, 4],
            7: [1, 3, 1, 2],
            8: [1, 2, 1, 3],
            9: [3, 1, 1, 2],
        }

        guard_left = [1, 0, 1]
        guard_center = [0, 1, 0, 1, 0]
        guard_right = [1, 0, 1]

        current_x = x

        for bit in guard_left:
            if bit:
                painter.fillRect(
                    int(current_x), y, max(1, int(module_w)), h, QColor(0, 0, 0)
                )
            current_x += module_w

        for digit in ean_digits[1:7]:
            pat = patterns.get(digit, [2, 2, 2, 1])
            for i, width in enumerate(pat):
                color = QColor(0, 0, 0) if i % 2 == 0 else QColor(255, 255, 255)
                painter.fillRect(
                    int(current_x), y, max(1, int(module_w * width)), h, color
                )
                current_x += module_w * width

        for bit in guard_center:
            if bit:
                painter.fillRect(
                    int(current_x), y, max(1, int(module_w)), h, QColor(0, 0, 0)
                )
            current_x += module_w

        for digit in ean_digits[7:13]:
            pat = patterns.get(digit, [2, 2, 2, 1])
            for i, width in enumerate(pat):
                color = QColor(255, 255, 255) if i % 2 == 0 else QColor(0, 0, 0)
                painter.fillRect(
                    int(current_x), y, max(1, int(module_w * width)), h, color
                )
                current_x += module_w * width

        for bit in guard_right:
            if bit:
                painter.fillRect(
                    int(current_x), y, max(1, int(module_w)), h, QColor(0, 0, 0)
                )
            current_x += module_w

        font_size = max(8, int(h * 0.35))
        painter.setFont(QFont("Arial", font_size))
        painter.setPen(QColor(0, 0, 0))

        first_digit_x = max(x + 2, 0)
        painter.drawText(first_digit_x, y + h + font_size + 2, str(ean_digits[0]))

        left_text = "".join(map(str, ean_digits[1:7]))
        left_center = x + int(w * 0.25)
        text_w = painter.fontMetrics().horizontalAdvance(left_text)
        painter.drawText(left_center - text_w // 2, y + h + font_size + 2, left_text)

        right_text = "".join(map(str, ean_digits[7:13]))
        right_center = x + int(w * 0.75)
        text_w = painter.fontMetrics().horizontalAdvance(right_text)
        painter.drawText(right_center - text_w // 2, y + h + font_size + 2, right_text)

        painter.setFont(QFont("Arial", max(7, int(h * 0.25))))
        painter.setPen(QColor(100, 100, 100))
        info_text = f"{ean_code} ({count} КИЗов)"
        painter.drawText(x, y + h + font_size * 2 + 8, info_text)
        painter.setPen(QColor(0, 0, 0))
