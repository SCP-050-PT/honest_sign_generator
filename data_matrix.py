"""
Data Matrix barcode generation — ZXing.Net с правильным FNC1.
ИСПРАВЛЕНО: обрезка встроенного quiet zone ZXing, только программный QZ.
"""

import io
import sys
import threading
from pathlib import Path
from PIL import Image

# === НАСТРОЙКА ZXING.NET ===
_dll_loaded = False
_dll_lock = threading.Lock()


def _ensure_zxing():
    """Ленивая загрузка ZXing.Net DLL."""
    global _dll_loaded
    if _dll_loaded:
        return

    with _dll_lock:
        if _dll_loaded:
            return

        # Ищем DLL в нескольких местах
        possible_paths = [
            Path(__file__).parent.parent / "zxing",  # рядом с проектом
            (
                Path(sys._MEIPASS) / "zxing" if getattr(sys, "frozen", False) else None
            ),  # PyInstaller
            Path.cwd() / "zxing",  # текущая папка
        ]

        for dll_path in possible_paths:
            if dll_path and dll_path.exists():
                if str(dll_path) not in sys.path:
                    sys.path.append(str(dll_path))
                break

        import clr

        clr.AddReference("zxing")
        _dll_loaded = True


# Импортируем после загрузки DLL
_ensure_zxing()

from ZXing import BarcodeWriter, BarcodeFormat
from System.Drawing.Imaging import ImageFormat
from System.IO import MemoryStream


class DataMatrixGenerator:
    """Генератор GS1 Data Matrix через ZXing.Net с FNC1."""

    def __init__(self, quiet_zone_mm: int = 2):
        self.quiet_zone_mm = quiet_zone_mm

        # === ОПТИМИЗАЦИЯ: разогретый BarcodeWriter ===
        self._writer = BarcodeWriter()
        self._writer.Format = BarcodeFormat.DATA_MATRIX

        # === ОПТИМИЗАЦИЯ: кеш DM-изображений ===
        self._cache = {}
        self._cache_lock = threading.Lock()
        self._cache_max_size = 10000  # лимит кеша

    def _prepare_gs1_data(self, raw_data: str) -> str:
        """
        Подготовить GS1-данные для ZXing.Net.
        - Заменяем Excel-экранированный GS (_x001D_) на реальный \x1d
        - Добавляем FNC1 (\x1d) в начало если отсутствует
        """
        # Очищаем от старых спецсимволов и Excel-экранирования
        clean = (
            raw_data.replace("_x001D_", "\x1d")
            .replace("_x001d_", "\x1d")
            .replace("\xf1", "")
            .replace("\xe8", "")
            .replace("\xe6", "")
        )

        # Добавляем FNC1 в начало если нет
        if not clean.startswith("\x1d"):
            clean = "\x1d" + clean

        return clean

    def _get_cache_key(
        self, data: str, target_size_mm: float, dpi: int, exact_size: bool
    ) -> tuple:
        """Ключ для кеша."""
        return (data, target_size_mm, dpi, exact_size, self.quiet_zone_mm)

    def _crop_zxing_margin(self, img: Image.Image) -> Image.Image:
        """
        Обрезать встроенный quiet zone от ZXing.Net.
        Используем getbbox() для поиска границ чёрных пикселей DM.
        """
        # Конвертируем в grayscale для точного определения границ
        gray = img.convert("L")
        # getbbox() находит bounding box не-чёрных пикселей
        # Но DM на белом фоне — белые пиксели = 255, чёрные = 0
        # Инвертируем: чёрные модули DM станут "не-чёрными" для getbbox
        from PIL import ImageOps

        inverted = ImageOps.invert(gray)
        bbox = inverted.getbbox()

        if bbox:
            # Добавляем 1px padding чтобы не обрезать крайние модули
            left, upper, right, lower = bbox
            # Убедимся, что не выходим за границы
            left = max(0, left - 1)
            upper = max(0, upper - 1)
            right = min(img.width, right + 1)
            lower = min(img.height, lower + 1)
            return img.crop((left, upper, right, lower))

        return img

    def generate(
        self,
        data: str,
        target_size_mm: float = 12,
        dpi: int = 300,
        exact_size: bool = False,
    ) -> bytes:
        """
        Генерация GS1 Data Matrix с FNC1 через ZXing.Net.
        С кешированием для повторяющихся кодов.
        ИСПРАВЛЕНО: обрезка встроенного margin ZXing, только программный QZ.
        """
        # === ПРОВЕРКА КЕША ===
        cache_key = self._get_cache_key(data, target_size_mm, dpi, exact_size)

        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            gs1_data = self._prepare_gs1_data(data)

            # Генерация через ZXing.Net (разогретый writer)
            bitmap = self._writer.Write(gs1_data)

            # Конвертация в PNG
            stream = MemoryStream()
            bitmap.Save(stream, ImageFormat.Png)
            stream.Position = 0
            png_bytes = bytes(stream.ToArray())

            # === ОБРЕЗКА ВСТРОЕННОГО MARGIN ZXING ===
            img = Image.open(io.BytesIO(png_bytes))
            img = self._crop_zxing_margin(img)
            # Теперь img — чистый DM без встроенного quiet zone

            # Масштабируем до целевого размера
            dm_only_mm = max(5, target_size_mm)
            target_px = int(dm_only_mm * dpi / 25.4)
            target_px = max(50, target_px)

            scale = target_px / max(img.width, img.height)
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.Resampling.NEAREST)

            # Добавляем ТОЛЬКО программный Quiet Zone
            if not exact_size and self.quiet_zone_mm > 0:
                quiet_zone_px = int(self.quiet_zone_mm * dpi / 25.4)
                if quiet_zone_px > 0:
                    new_size = (
                        img.width + 2 * quiet_zone_px,
                        img.height + 2 * quiet_zone_px,
                    )
                    padded = Image.new("RGB", new_size, "white")
                    padded.paste(img, (quiet_zone_px, quiet_zone_px))
                    img = padded

            # Сохраняем в PNG
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", dpi=(dpi, dpi))
            result = buffer.getvalue()

            # === СОХРАНЕНИЕ В КЕШ ===
            with self._cache_lock:
                if len(self._cache) < self._cache_max_size:
                    self._cache[cache_key] = result
            return result

        except Exception as e:
            print(f"[DM ERROR] {e}")
            import traceback

            traceback.print_exc()
            return self._generate_placeholder(target_size_mm, dpi)

    def _generate_placeholder(self, target_size_mm: float, dpi: int) -> bytes:
        """Заглушка при ошибке."""
        from PIL import ImageDraw, ImageFont

        size_px = int(target_size_mm * dpi / 25.4)
        size_px = max(50, size_px)

        image = Image.new("RGB", (size_px, size_px), "#ffcccc")
        draw = ImageDraw.Draw(image)
        draw.line([(5, 5), (size_px - 5, size_px - 5)], fill="red", width=2)
        draw.line([(5, size_px - 5), (size_px - 5, 5)], fill="red", width=2)

        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
        draw.text((5, size_px // 2), "ERR", fill="red", font=font)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    def validate_code(self, code: str) -> bool:
        """Валидация кода."""
        if not code or len(code) < 8:
            return False
        return all(32 <= ord(c) <= 126 for c in code)
