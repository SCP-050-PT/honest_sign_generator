"""
Drawing KIZ (Data Matrix) labels in PDF.
ИСПРАВЛЕНО: DM максимально крупный, текстовые элементы прижаты к низу.
Шрифт текстовых элементов: 5-16pt.
"""

from typing import Dict, List, Optional
from io import BytesIO

from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from .fonts import get_font_name


def _get_mm_value(
    elem: Dict, key: str, fallback_px_key: str, default_mm: float
) -> float:
    if key in elem:
        return float(elem[key])
    px_val = elem.get(fallback_px_key, default_mm * 10)
    return px_val / 10.0


def draw_single_kiz(
    c,
    x: float,
    y: float,
    w: float,
    h: float,
    dm_size_mm: float,
    bottom_field_mm: float,
    code_info: Dict,
    elements: List[Dict],
    template_config: Optional[Dict] = None,
):
    """Отрисовка одного КИЗ. DM максимально крупный, текст прижат к низу."""
    n_mm = w / mm

    # === КОНТУР ЭТИКЕТКИ ===
    c.saveState()
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.setLineWidth(0.2)
    c.line(x, y, x + w, y)
    c.line(x + w, y, x + w, y + h)
    c.line(x + w, y + h, x, y + h)
    c.line(x, y + h, x, y)
    c.restoreState()

    # === ПОЛЕ НОМЕРА (внизу, минимальная высота) ===
    number_field_height = 1.5 * mm  # УМЕНЬШИЛИ с 2.5 до 1.5
    number_field_y = y

    # === DATA MATRIX — МАКСИМАЛЬНО КРУПНЫЙ ===
    margin = 0.2  
    dm_w_mm = dm_size_mm
    dm_h_mm = dm_size_mm

    dm_x_mm = (n_mm - dm_w_mm) / 2
    dm_y_mm = margin

    dm_w = dm_w_mm * mm
    dm_h = dm_h_mm * mm
    dm_x = x + dm_x_mm * mm
    dm_y_pdf = y + h - (dm_y_mm + dm_h_mm) * mm
    dm_bottom_pdf = dm_y_pdf

    # УБРАНА ПРОВЕРКА УМЕНЬШЕНИЯ DM — используем размер из UI

    # PDF: инверсия Y
    dm_y_pdf = y + h - (dm_y_mm + dm_h_mm) * mm

    # Нижняя граница DM
    dm_bottom_pdf = dm_y_pdf

    # Проверка: DM не залезает на номер?
    min_dm_bottom = number_field_y + number_field_height + 0.5 * mm
    if dm_bottom_pdf < min_dm_bottom:
        # Уменьшаем DM до доступного пространства
        available_h_mm = n_mm - number_field_height / mm - 0.5 - margin
        dm_w_mm = available_h_mm
        dm_h_mm = available_h_mm
        dm_w = dm_w_mm * mm
        dm_h = dm_h_mm * mm
        dm_y_pdf = min_dm_bottom
        dm_bottom_pdf = dm_y_pdf

    # Рисуем DM
    try:
        from ..data_matrix import DataMatrixGenerator

        quiet_zone = template_config.get("quiet_zone_mm", 0) if template_config else 0
        dm_gen = DataMatrixGenerator(quiet_zone_mm=quiet_zone)
        code = code_info.get("code", "") or code_info.get("kiz", "") or ""
        dm_buffer = dm_gen.generate(code, target_size_mm=dm_w_mm)
        dm_image = ImageReader(BytesIO(dm_buffer))
        c.drawImage(dm_image, dm_x, dm_y_pdf, width=dm_w, height=dm_h)
    except Exception as e:
        print(f"[DM ERROR] {e}")

    # === НИЖНЕЕ ПОЛЕ (номер КИЗа) ===
    bottom_type = (
        template_config.get("bottom_field_type", "index")
        if template_config
        else "index"
    )

    text = ""
    font_size = 8

    if bottom_type == "gtin":
        text = code_info.get("gtin", "")
        font_size = template_config.get("gtin_size", 8) if template_config else 8
    elif bottom_type == "article":
        text = code_info.get("article", "")
        font_size = template_config.get("article_size", 8) if template_config else 8
    elif bottom_type == "kiz_number":
        text = code_info.get("kiz_number", "")
        if not text:
            text = str(code_info.get("global_index", 1))
        font_size = template_config.get("index_size", 8) if template_config else 8
    elif bottom_type == "index":
        kiz_number = code_info.get("kiz_number", "")
        if kiz_number:
            text = str(kiz_number)
        else:
            text = str(code_info.get("global_index", 1))
        font_size = template_config.get("index_size", 8) if template_config else 8

    if text:
        font_size = max(5, min(16, font_size))
        c.setFont(get_font_name("Arial-Bold"), font_size)
        c.setFillColorRGB(0, 0, 0)
        text_width = c.stringWidth(text, get_font_name("Arial-Bold"), font_size)
        number_x = x + (w - text_width) / 2
        number_y = y + 1.5 * mm
        c.drawString(number_x, number_y, text)

    # === ТЕКСТОВЫЕ ЭЛЕМЕНТЫ — ПРИЖАТЫ К НИЗУ, ПОД DM ===
    # Собираем все видимые текстовые элементы
    text_elements_data = []
    for elem_id, text_key in [
        ("gtin", "gtin"),
        ("article", "article"),
        ("name", "name"),
    ]:
        elem = next((e for e in elements if e.get("id") == elem_id), None)
        if elem and elem.get("visible", True):
            text_val = code_info.get(text_key, "")
            if text_val:
                text_elements_data.append((elem_id, text_val, elem))

    # Если есть текстовые элементы — считаем доступную высоту
    if text_elements_data:
        # Доступная высота для текста: от нижнего края DM до верхнего края поля номера
        available_text_height = dm_bottom_pdf - (
            number_field_y + number_field_height + 0.5 * mm
        )
        available_text_height_mm = available_text_height / mm

        # Количество строк текста
        num_lines = len(text_elements_data)

        # Высота на одну строку (минимум 5pt + отступ)
        line_height = (
            available_text_height / num_lines
            if num_lines > 0
            else available_text_height
        )

        # Рисуем текстовые элементы снизу вверх (прижаты к низу)
        current_y = number_field_y + number_field_height + 0.5 * mm

        for i, (elem_id, text_val, elem) in enumerate(reversed(text_elements_data)):
            # Размер шрифта: мин 5pt, макс 16pt, авто-подгон под высоту строки
            font_size = max(5, min(16, int(line_height / mm * 0.6)))

            ex_mm = _get_mm_value(elem, "x_mm", "x", 2)

            c.setFont(get_font_name("Arial"), font_size)
            c.setFillColorRGB(0.3, 0.3, 0.3)

            text_width = c.stringWidth(text_val, get_font_name("Arial"), font_size)
            max_allowed_width = w - 4 * mm

            # Уменьшаем шрифт если текст не влезает
            if text_width > max_allowed_width:
                while text_width > max_allowed_width and font_size > 5:
                    font_size -= 0.5
                    c.setFont(get_font_name("Arial"), font_size)
                    text_width = c.stringWidth(
                        text_val, get_font_name("Arial"), font_size
                    )

            # Центрируем по горизонтали или позиция из редактора
            if ex_mm <= 2:  # если позиция по умолчанию — центрируем
                text_x = x + (w - text_width) / 2
            else:
                text_x = x + ex_mm * mm

            # Y позиция: прижаты к низу, каждая следующая строка выше
            text_y = current_y + i * line_height + font_size * 0.3 * mm

            # Не выше нижнего края DM
            if text_y + font_size * mm > dm_bottom_pdf - 0.2 * mm:
                text_y = dm_bottom_pdf - 0.2 * mm - font_size * mm

            c.drawString(text_x, text_y, text_val)

    c.setFillColorRGB(0, 0, 0)


def draw_single_kiz_dm_only(
    c,
    x: float,
    y: float,
    w: float,
    h: float,
    dm_size_mm: float,
    quiet_zone_mm: float,
    code_info: Dict,
):
    """Отрисовка КИЗ: только DM+QZ на всю этикетку."""
    n_mm = w / mm

    print(f"[DM_ONLY] label={n_mm}mm, dm_size={dm_size_mm}mm, qz={quiet_zone_mm}mm")

    try:
        from ..data_matrix import DataMatrixGenerator

        dm_gen = DataMatrixGenerator(quiet_zone_mm=quiet_zone_mm)
        code = code_info.get("code", "") or code_info.get("kiz", "") or ""

        dm_buffer = dm_gen.generate(code, target_size_mm=dm_size_mm)
        dm_image = ImageReader(BytesIO(dm_buffer))

        c.drawImage(
            dm_image,
            x,
            y,
            width=w,
            height=h,
            preserveAspectRatio=False,
        )

        print(
            f"[DM_ONLY] drawn at ({x/mm:.1f}, {y/mm:.1f}), size=({w/mm:.1f}x{h/mm:.1f})"
        )

    except Exception as e:
        print(f"[DM ERROR] {e}")
        import traceback

        traceback.print_exc()
