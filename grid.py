"""
Page size and grid calculations for PDF layout.
ИСПРАВЛЕНО: страница в режиме fill = точный размер сетки, без лишних полей.
"""

from typing import Dict, Optional, Tuple

from reportlab.lib.units import mm


def get_page_size(
    template_config: Optional[Dict] = None,
    cols: int = 1,
    rows: int = 1,
    gap_mm: float = 0,
) -> tuple:
    """
    Получить размер страницы.
    - single (cols=1, rows=1): страница = N×N (поштучно)
    - fill (cols>1 или rows>1): страница = точный размер сетки этикеток, без полей
    """
    n = template_config.get("label_size_mm", 15) if template_config else 15

    if cols == 1 and rows == 1:
        return (n * mm, n * mm)
    else:
        # Точный размер = сетка этикеток + зазоры между ними, без margins
        page_w = cols * n + max(0, cols - 1) * gap_mm
        page_h = rows * n + max(0, rows - 1) * gap_mm
        return (page_w * mm, page_h * mm)


def get_margins(template_config: Optional[Dict] = None) -> float:
    """Получить отступы из конфига. В режиме fill margins = 0."""
    # Возвращаем 0, т.к. страница уже точного размера сетки
    return 0


def calc_grid(
    page_w_mm: float,
    page_h_mm: float,
    n_mm: float,
    margins_mm: float,
    gap_mm: float = 0,
) -> Tuple[int, int, int]:
    """
    Расчёт сетки. ВСЕ параметры в мм.
    Возвращает cols, rows, max_per_page.
    """
    # margins_mm игнорируем — страница уже точного размера
    if gap_mm > 0:
        cols = max(1, int((page_w_mm + gap_mm) / (n_mm + gap_mm)))
        rows = max(1, int((page_h_mm + gap_mm) / (n_mm + gap_mm)))
    else:
        cols = max(1, int(page_w_mm / n_mm))
        rows = max(1, int(page_h_mm / n_mm))

    max_per_page = cols * rows
    return cols, rows, max_per_page
