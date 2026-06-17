"""
Drawing aggregate (EAN-13) labels in PDF.
ИСПРАВЛЕНО: единая система координат x_mm/y_mm из редактора → PDF.
ИСПРАВЛЕНО: HRI одной строкой без пробелов.
ИСПРАВЛЕНО: SSCC текст центрируется по ширине этикетки с автоуменьшением.
ИСПРАВЛЕНО: убран # перед номером агрегата, используется box_number из Excel.
"""

import os
from typing import Dict, List, Optional

from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from io import BytesIO

from .fonts import get_font_name


def _get_mm_value(
    elem: Dict, key: str, fallback_px_key: str, default_mm: float
) -> float:
    """Получить значение в мм: сначала x_mm, иначе конвертируем из пикселей."""
    if key in elem:
        return float(elem[key])
    px_val = elem.get(fallback_px_key, default_mm * 10)
    return px_val / 10.0


# === EAN-13 ПАТТЕРНЫ ===
EAN_PATTERNS = {
    "L": [
        "0001101",
        "0011001",
        "0010011",
        "0111101",
        "0100011",
        "0110001",
        "0101111",
        "0111011",
        "0110111",
        "0001011",
    ],
    "G": [
        "0100111",
        "0110011",
        "0011011",
        "0100001",
        "0011101",
        "0111001",
        "0000101",
        "0010001",
        "0001001",
        "0010111",
    ],
    "R": [
        "1110010",
        "1100110",
        "1101100",
        "1000010",
        "1011100",
        "1001110",
        "1010000",
        "1000100",
        "1001000",
        "1110100",
    ],
}

EAN_FIRST_DIGIT_PATTERNS = [
    "LLLLLL",
    "LLGLGG",
    "LLGGLG",
    "LLGGGL",
    "LGLLGG",
    "LGGLLG",
    "LGGGLL",
    "LGLGLG",
    "LGLGGL",
    "LGGLGL",
]


def _ean13_to_bars(ean_code: str) -> List[int]:
    """Преобразует EAN-13 в список модулей (1=чёрная, 0=белая)."""
    if len(ean_code) == 12:
        check = _ean13_checksum(ean_code)
        full_code = ean_code + str(check)
    else:
        full_code = ean_code[:13]
        ean_code = ean_code[:12]

    first_digit = int(full_code[0])
    left_digits = full_code[1:7]
    right_digits = full_code[7:13]
    pattern_types = EAN_FIRST_DIGIT_PATTERNS[first_digit]

    bars = []
    bars.extend([1, 0, 1])
    for i, digit in enumerate(left_digits):
        pattern = EAN_PATTERNS[pattern_types[i]][int(digit)]
        bars.extend([int(b) for b in pattern])
    bars.extend([0, 1, 0, 1, 0])
    for digit in right_digits:
        pattern = EAN_PATTERNS["R"][int(digit)]
        bars.extend([int(b) for b in pattern])
    bars.extend([1, 0, 1])
    return bars


def _ean13_checksum(ean12: str) -> int:
    """Контрольная цифра EAN-13."""
    total = 0
    for i, digit in enumerate(ean12):
        d = int(digit)
        total += d if i % 2 == 0 else d * 3
    return (10 - (total % 10)) % 10


def _draw_ean13_vector(
    c,
    x: float,
    y: float,
    w: float,
    h: float,
    ean_code: str,
    font_size: float = 9,
):
    """Рисует EAN-13 векторно: чёрные полосы + HRI одной строкой без пробелов."""
    bars = _ean13_to_bars(ean_code)
    total_modules = len(bars)
    quiet_modules = 11
    total_with_quiet = total_modules + 2 * quiet_modules
    module_width = w / total_with_quiet

    text_area_ratio = 0.22
    bar_area_ratio = 1.0 - text_area_ratio
    text_area_height = h * text_area_ratio
    bar_area_height = h * bar_area_ratio

    current_x = x + quiet_modules * module_width
    for bar in bars:
        if bar == 1:
            c.setFillColorRGB(0, 0, 0)
            c.rect(
                current_x,
                y + text_area_height,
                module_width,
                bar_area_height,
                fill=1,
                stroke=0,
            )
        current_x += module_width

    c.setFillColorRGB(0, 0, 0)
    c.setFont(get_font_name("OCRB"), font_size)

    full_code = (
        ean_code if len(ean_code) == 13 else ean_code + str(_ean13_checksum(ean_code))
    )
    hri_text = full_code
    text_width = c.stringWidth(hri_text, get_font_name("OCRB"), font_size)
    text_x = x + (w - text_width) / 2
    text_y = y + text_area_height * 0.25
    c.drawString(text_x, text_y, hri_text)


def draw_single_aggregate(
    c,
    x: float,
    y: float,
    w: float,
    h: float,
    agg_size_mm: float,
    item: Dict,
    elements: List[Dict],
    template_config: Optional[Dict] = None,
):
    """Отрисовка одного агрегата ШК (EAN-13) внутри ячейки N×N сетки."""
    sscc = item["sscc"]
    box_number = item.get("box_number", "")
    idx = item.get("index", 1)
    ean_code = _sscc_to_ean13(sscc, box_number)

    n_mm = w / mm

    number_field_height = 3 * mm
    number_field_y = y

    # === КОНТУР ЭТИКЕТКИ ===
    c.saveState()
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.setLineWidth(0.6)
    c.line(x, y, x + w, y)
    c.line(x + w, y, x + w, y + h)
    c.line(x + w, y + h, x, y + h)
    c.line(x, y + h, x, y)
    c.restoreState()

    # === EAN-13 ШТРИХКОД ===
    barcode_elem = next((e for e in elements if e.get("id") == "barcode"), None)

    if barcode_elem and barcode_elem.get("visible", True):
        bx_mm = _get_mm_value(barcode_elem, "x_mm", "x", 0)
        by_mm = _get_mm_value(barcode_elem, "y_mm", "y", 0)
        bw_mm = _get_mm_value(barcode_elem, "width_mm", "width", agg_size_mm)
        bh_mm = _get_mm_value(barcode_elem, "height_mm", "height", agg_size_mm * 0.35)
    else:
        bw_mm = min(agg_size_mm, n_mm - 2)
        bh_mm = bw_mm * 0.35
        bx_mm = (n_mm - bw_mm) / 2
        content_h_mm = n_mm - 3
        by_mm = 3 + (content_h_mm - bh_mm) / 2

    barcode_w = bw_mm * mm
    barcode_h = bh_mm * mm
    barcode_x = x + bx_mm * mm
    barcode_y = y + h - (by_mm + bh_mm) * mm

    min_barcode_y = number_field_y + number_field_height
    if barcode_y < min_barcode_y:
        barcode_y = min_barcode_y

    try:
        font_size = max(6, min(14, int(barcode_h / mm * 0.35)))
        _draw_ean13_vector(
            c,
            barcode_x,
            barcode_y,
            barcode_w,
            barcode_h,
            ean_code,
            font_size=font_size,
        )
    except Exception as e:
        import traceback

        error_msg = f"[EAN-13 ERROR] {e}\n{traceback.format_exc()}"
        print(error_msg)
        c.setFont(get_font_name("Arial"), 8)
        c.setFillColorRGB(1, 0, 0)
        c.drawCentredString(x + w / 2, y + h / 2, f"ERR #{idx}")

    # === SSCC ТЕКСТ — ЦЕНТРИРУЕМ, НЕ ВЫЛЕЗАЕМ ЗА ГРАНИЦЫ ===
    sscc_elem = next((e for e in elements if e.get("id") == "sscc_text"), None)

    sscc_font_size = 9
    if template_config and "sscc_size" in template_config:
        sscc_font_size = template_config["sscc_size"]
    sscc_font_size = max(5, min(14, sscc_font_size))

    if sscc_elem and sscc_elem.get("visible", True):
        sy_mm = _get_mm_value(sscc_elem, "y_mm", "y", n_mm * 0.85)
        pdf_y = y + h - sy_mm * mm - sscc_font_size * 0.25 * mm
    else:
        pdf_y = barcode_y - 3 * mm

    min_allowed_y = number_field_y + number_field_height
    if pdf_y < min_allowed_y:
        pdf_y = min_allowed_y

    c.setFont(get_font_name("OCRB"), sscc_font_size)
    c.setFillColorRGB(0.4, 0.4, 0.4)

    max_allowed_width = w - 2 * mm
    text_width = c.stringWidth(sscc, get_font_name("OCRB"), sscc_font_size)

    while text_width > max_allowed_width and sscc_font_size > 5:
        sscc_font_size -= 0.5
        c.setFont(get_font_name("OCRB"), sscc_font_size)
        text_width = c.stringWidth(sscc, get_font_name("OCRB"), sscc_font_size)

    text_x = x + (w - text_width) / 2
    c.drawString(text_x, pdf_y, sscc)

    # === НОМЕР АГРЕГАТА — убран # ===
    number_font_size = max(6, min(12, int(n_mm * 0.35)))
    c.setFont(get_font_name("Arial-Bold"), number_font_size)
    c.setFillColorRGB(0, 0, 0)
    if box_number:
        number_text = str(box_number)
    else:
        number_text = str(idx)

    text_width = c.stringWidth(
        number_text, get_font_name("Arial-Bold"), number_font_size
    )
    number_x = x + (w - text_width) / 2
    number_y = number_field_y + (number_field_height - number_font_size * 0.35) / 2
    c.drawString(number_x, number_y, number_text)
    c.setFillColorRGB(0, 0, 0)


def _sscc_to_ean13(sscc: str, box_number: str = "") -> str:
    """Генерация EAN-13 из номера агрегата."""
    if box_number and str(box_number).isdigit():
        return str(box_number).zfill(12)
    digits = "".join(c for c in sscc if c.isdigit())
    significant = digits.lstrip("0")
    if len(significant) >= 12:
        return significant[:12]
    return digits[-12:].zfill(12)
