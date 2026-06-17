"""
Element validation for PDF labels.
Координаты из редактора (пиксели, base_px_per_mm=10) → миллиметры.
БЕЗ инверсии Y — инверсия делается только в draw_*.py при отрисовке в PDF.
ДОБАВЛЕНО: calc_max_dm_size — динамический расчёт макс. размера DM.
"""

from typing import Dict, List, Tuple


def calc_max_dm_size(
    label_size_mm: float,
    bottom_field_type: str,
    index_size_pt: int,
    gtin_size_pt: int,
    article_size_pt: int,
    quiet_zone_mm: float = 0,
) -> float:
    """Рассчитать максимальный размер DM с учётом текста."""
    margin = 0.2
    gap = 0.2

    # Высота поля номера (№пп)
    if bottom_field_type == "none":
        number_height = 0
    else:
        number_height = max(index_size_pt * 0.3, 1.0)

    # GTIN и Артикул рисуются в остатке — не уменьшаем DM
    text_height = 0

    # DM = этикетка - отступы - номер - зазор - quiet_zone*2
    dm_max = (
        label_size_mm
        - margin * 2
        - number_height
        - text_height
        - gap
        - quiet_zone_mm * 2
    )

    return max(5, min(dm_max, label_size_mm - 0.5))


def validate_elements_for_label(
    elements: List[Dict],
    label_size_mm: float,
    dm_size_mm: float,
    quiet_zone_mm: float,
    bottom_field_mm: float,
    single_mode_type: str = "with_elements",
) -> List[Dict]:
    """Валидация позиций DM-элементов: конвертируем px → мм."""
    validated = []

    # === ВАЛИДАЦИЯ DM+QZ ===
    dm_total = dm_size_mm + 2 * quiet_zone_mm

    if dm_total > label_size_mm:
        # Урезаем DM, чтобы DM+QZ = этикетка
        new_dm_size = label_size_mm - 2 * quiet_zone_mm
        new_dm_size = max(5, new_dm_size)  # минимум 5мм
        print(
            f"[WARNING] DM+QZ={dm_total:.1f}мм > этикетка={label_size_mm}мм. "
            f"DM уменьшен: {dm_size_mm}мм → {new_dm_size}мм"
        )
        dm_size_mm = new_dm_size

    dm_rect_base = _calc_dm_rect_base(
        label_size_mm, dm_size_mm, quiet_zone_mm, bottom_field_mm, single_mode_type
    )
    print(f"[DM VALIDATION] label_size={label_size_mm}, dm_rect={dm_rect_base}")

    editor_px_per_mm = 10.0

    for elem in elements:
        elem_id = elem.get("id", "")
        x = elem.get("x", 0)
        y = elem.get("y", 0)
        w = elem.get("width", 20)
        h = elem.get("height", 10)

        # Конвертируем пиксели редактора в мм (БЕЗ инверсии Y!)
        x_mm = x / editor_px_per_mm
        y_mm = y / editor_px_per_mm
        w_mm = w / editor_px_per_mm
        h_mm = h / editor_px_per_mm

        print(
            f"[DM ELEM {elem_id}] raw: x={x}, y={y}, w={w}, h={h} | mm: x_mm={x_mm:.1f}, y_mm={y_mm:.1f}, w_mm={w_mm:.1f}, h_mm={h_mm:.1f}"
        )

        # Ограничиваем границами этикетки
        x_mm = max(0.5, min(x_mm, label_size_mm - w_mm - 0.5))
        y_mm = max(0.5, min(y_mm, label_size_mm - h_mm - 0.5))

        # Проверяем пересечение с DM+QZ (только для текстовых)
        if elem_id != "barcode":
            elem_rect_mm = (x_mm, y_mm, w_mm, h_mm)
            if _rects_intersect_mm(elem_rect_mm, dm_rect_base):
                print(f"[DM ELEM {elem_id}] INTERSECTS DM! Moving outside...")
                x_mm, y_mm = _move_outside_dm(
                    x_mm, y_mm, w_mm, h_mm, dm_rect_base, label_size_mm
                )
                print(
                    f"[DM ELEM {elem_id}] AFTER MOVE: x_mm={x_mm:.1f}, y_mm={y_mm:.1f}"
                )

        elem_copy = dict(elem)
        elem_copy["x_mm"] = x_mm
        elem_copy["y_mm"] = y_mm
        elem_copy["width_mm"] = w_mm
        elem_copy["height_mm"] = h_mm
        validated.append(elem_copy)
        print(f"[DM ELEM {elem_id}] FINAL: x_mm={x_mm:.1f}, y_mm={y_mm:.1f}")

    return validated


def validate_aggregate_elements(
    elements: List[Dict],
    label_size_mm: float,
    barcode_size_mm: float,
) -> List[Dict]:
    """Валидация позиций элементов агрегата."""
    validated = []

    max_barcode_size = label_size_mm - 2
    actual_barcode_size = min(barcode_size_mm, max_barcode_size)

    if actual_barcode_size < barcode_size_mm:
        print(
            f"[AGG WARNING] Размер ШК {barcode_size_mm}мм ограничен до {actual_barcode_size}мм (этикетка {label_size_mm}мм)"
        )

    barcode_w_mm = actual_barcode_size
    barcode_h_mm = max(8, barcode_w_mm * 0.35)
    barcode_x = (label_size_mm - barcode_w_mm) / 2
    barcode_y = (label_size_mm - barcode_h_mm) / 2 - 3
    barcode_rect = (barcode_x, barcode_y, barcode_w_mm, barcode_h_mm)

    print(
        f"[AGG VALIDATION] label_size={label_size_mm}, barcode_size={actual_barcode_size}, barcode_rect={barcode_rect}"
    )

    editor_px_per_mm = 10.0

    for elem in elements:
        elem_id = elem.get("id", "")
        x = elem.get("x", 0)
        y = elem.get("y", 0)
        w = elem.get("width", 20)
        h = elem.get("height", 10)

        x_mm = x / editor_px_per_mm
        y_mm = y / editor_px_per_mm
        w_mm = w / editor_px_per_mm
        h_mm = h / editor_px_per_mm

        if elem_id == "barcode":
            w_mm = barcode_w_mm
            h_mm = barcode_h_mm
            x_mm = (label_size_mm - w_mm) / 2
            y_mm = (label_size_mm - 3 - h_mm) / 2

        print(
            f"[AGG ELEM {elem_id}] mm: x_mm={x_mm:.1f}, y_mm={y_mm:.1f}, w_mm={w_mm:.1f}, h_mm={h_mm:.1f}"
        )

        x_mm = max(0.5, min(x_mm, label_size_mm - w_mm - 0.5))
        y_mm = max(0.5, min(y_mm, label_size_mm - h_mm - 0.5))

        if elem_id != "barcode":
            elem_rect_mm = (x_mm, y_mm, w_mm, h_mm)
            if _rects_intersect_mm(elem_rect_mm, barcode_rect):
                print(f"[AGG ELEM {elem_id}] INTERSECTS BARCODE! Moving outside...")
                x_mm, y_mm = _move_outside_barcode(
                    x_mm, y_mm, w_mm, h_mm, barcode_rect, label_size_mm
                )

        elem_copy = dict(elem)
        elem_copy["x_mm"] = x_mm
        elem_copy["y_mm"] = y_mm
        elem_copy["width_mm"] = w_mm
        elem_copy["height_mm"] = h_mm
        validated.append(elem_copy)

    return validated


def _calc_dm_rect_base(
    label_size_mm: float,
    dm_size_mm: float,
    quiet_zone_mm: float,
    bottom_field_mm: float,
    single_mode_type: str = "with_elements",
) -> Tuple[float, float, float, float]:
    """Расчёт прямоугольника DM+QZ в мм (y от верха этикетки вниз)."""
    dm_total = dm_size_mm + 2 * quiet_zone_mm

    if single_mode_type == "dm_only":
        dm_actual = min(dm_total, label_size_mm)
        dm_x = (label_size_mm - dm_actual) / 2
        dm_y = (label_size_mm - dm_actual) / 2
        return (dm_x, dm_y, dm_actual, dm_actual)

    # DM прижат к верху, максимальный размер
    margin = 0.2
    dm_actual = min(dm_total, label_size_mm - margin * 2)
    dm_x = (label_size_mm - dm_actual) / 2
    dm_y = margin

    return (dm_x, dm_y, dm_actual, dm_actual)


def _rects_intersect_mm(
    rect1: Tuple[float, float, float, float],
    rect2: Tuple[float, float, float, float],
) -> bool:
    """Проверка пересечения прямоугольников (x, y, w, h). y от верха вниз."""
    x1, y1, w1, h1 = rect1
    x2, y2, w2, h2 = rect2
    return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)


def _move_outside_dm(
    x: float,
    y: float,
    w: float,
    h: float,
    dm_rect: Tuple[float, float, float, float],
    label_size_mm: float,
) -> Tuple[float, float]:
    """Сдвинуть элемент за пределы DM+QZ. Приоритет: ВНИЗ."""
    dm_x, dm_y, dm_w, dm_h = dm_rect

    candidates = []

    # ПРИОРИТЕТ: под DM
    if dm_y + dm_h + h <= label_size_mm - 0.5:
        candidates.append((x, dm_y + dm_h + 0.5))

    if dm_y - h >= 0.5:
        candidates.append((x, dm_y - h - 0.5))
    if dm_x - w >= 0.5:
        candidates.append((dm_x - w - 0.5, y))
    if dm_x + dm_w + w <= label_size_mm - 0.5:
        candidates.append((dm_x + dm_w + 0.5, y))

    if candidates:
        return min(candidates, key=lambda pos: (pos[0] - x) ** 2 + (pos[1] - y) ** 2)

    return (0.5, 0.5)


def _move_outside_barcode(
    x: float,
    y: float,
    w: float,
    h: float,
    barcode_rect: Tuple[float, float, float, float],
    label_size_mm: float,
) -> Tuple[float, float]:
    """Сдвинуть элемент за пределы штрихкода. y от верха вниз."""
    bx, by, bw, bh = barcode_rect

    candidates = []

    if by - h >= 0.5:
        candidates.append((x, by - h - 0.5))
    if by + bh + h <= label_size_mm - 0.5:
        candidates.append((x, by + bh + 0.5))
    if bx - w >= 0.5:
        candidates.append((bx - w - 0.5, y))
    if bx + bw + w <= label_size_mm - 0.5:
        candidates.append((bx + bw + 0.5, y))

    if candidates:
        return min(candidates, key=lambda pos: (pos[0] - x) ** 2 + (pos[1] - y) ** 2)

    return (0.5, 0.5)
