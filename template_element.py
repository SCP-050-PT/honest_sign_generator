"""
Модель элемента на PDF-шаблоне.
"""

from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class TemplateElement:
    """Элемент на PDF-шаблоне (DM или текст)."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = "dm"  # "dm" | "text"

    # Позиция в мм от левого верхнего угла шаблона
    x_mm: float = 10.0
    y_mm: float = 10.0

    # Для DM:
    size_mm: float = 16.0  # Размер DM (ширина = высота)
    quiet_zone_mm: float = 2.0

    # Для текста:
    text_type: str = "index"  # "none" | "gtin" | "index" | "article"
    font_size: int = 8
    text: str = ""  # Для превью (заполняется динамически)

    def __post_init__(self):
        if self.type not in ("dm", "text"):
            raise ValueError(f"Unknown element type: {self.type}")
