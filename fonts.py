"""
Font registration for PDF generation.
ИСПРАВЛЕНО: поддержка PyInstaller (sys._MEIPASS).
"""

import sys
import os
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def _get_base_path() -> Path:
    """Получить базовый путь (учитывает PyInstaller)."""
    if getattr(sys, "frozen", False):
        # PyInstaller создаёт временную папку _MEIPASS
        return Path(sys._MEIPASS)
    else:
        # Обычный запуск — путь к папке core/pdf/
        return Path(__file__).parent.parent.parent


def _get_fonts_dir() -> Path:
    """Получить путь к папке fonts."""
    return _get_base_path() / "fonts"


def register_fonts():
    """Регистрация всех шрифтов из папки fonts/."""
    fonts_dir = _get_fonts_dir()

    if not fonts_dir.exists():
        print(f"[FONTS WARNING] Fonts dir not found: {fonts_dir}")
        return

    font_mappings = {
        "Arial": "arial.ttf",
        "Arial-Bold": "arialbd.ttf",
        "Arial-Italic": "ariali.ttf",
        "Arial-BoldItalic": "arialbi.ttf",
        "OCRB": "ocrb.ttf",
    }

    for font_name, filename in font_mappings.items():
        font_path = fonts_dir / filename
        if font_path.exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                print(f"[FONTS] Registered: {font_name} -> {font_path}")
            except Exception as e:
                print(f"[FONTS ERROR] Failed to register {font_name}: {e}")
        else:
            print(f"[FONTS WARNING] Font file not found: {font_path}")


def get_font_name(name: str) -> str:
    """Получить зарегистрированное имя шрифта."""
    # Проверяем, зарегистрирован ли шрифт
    registered = pdfmetrics.getRegisteredFontNames()
    if name in registered:
        return name

    # Fallback на стандартные шрифты ReportLab
    fallback_map = {
        "Arial": "Helvetica",
        "Arial-Bold": "Helvetica-Bold",
        "Arial-Italic": "Helvetica-Oblique",
        "Arial-BoldItalic": "Helvetica-BoldOblique",
        "OCRB": "Courier",
    }

    fallback = fallback_map.get(name, "Helvetica")
    print(f"[FONTS FALLBACK] {name} -> {fallback}")
    return fallback


# Авторегистрация при импорте
register_fonts()
