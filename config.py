"""
Configuration for Honest Sign Generator.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import Tuple


@dataclass
class LabelConfig:
    """Конфигурация этикетки."""

    width_mm: int = 30
    height_mm: int = 30
    quiet_zone_mm: int = 2  # Настраиваемый Quiet Zone (дефолт 2мм)
    dpi: int = 300

    @property
    def width_px(self) -> int:
        """Ширина в пикселях."""
        return int(self.width_mm * self.dpi / 25.4)

    @property
    def height_px(self) -> int:
        """Высота в пикселях."""
        return int(self.height_mm * self.dpi / 25.4)

    @property
    def quiet_zone_px(self) -> int:
        """Quiet Zone в пикселях."""
        return int(self.quiet_zone_mm * self.dpi / 25.4)


@dataclass
class PDFConfig:
    """Конфигурация PDF."""

    page_limit_per_gtin: int = 100
    include_aggregating_code: bool = True
    aggregating_code_page: int = 0  # Первая страница


# Пути
BASE_DIR = Path(__file__).parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

# Создание директорий
UPLOADS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Дефолтные конфиги
DEFAULT_LABEL_CONFIG = LabelConfig()
DEFAULT_PDF_CONFIG = PDFConfig()

# Размеры этикеток
LABEL_SIZES = {
    "15x15": (15, 15),
    "30x30": (30, 30),
}
