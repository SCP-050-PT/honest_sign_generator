"""
Генерация PDF с наложением Data Matrix на готовый PDF-шаблон.
PyMuPDF (fitz) открывает шаблон, накладывает DM и текст, сохраняет.
"""

import fitz
from pathlib import Path
from typing import List, Dict, Optional, Callable
from io import BytesIO

from ..data_matrix import DataMatrixGenerator
from .fonts import get_font_name


class TemplateOverlayGenerator:
    """Генератор PDF с наложением DM на шаблон."""

    DPI = 300

    def __init__(self, template_path: Path, quiet_zone_mm: int = 2):
        self.template_path = template_path
        self.dm_generator = DataMatrixGenerator(quiet_zone_mm=quiet_zone_mm)

    def generate(
        self,
        codes: List[Dict],
        config: Dict,
        output_path: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Path:
        """
        Генерация PDF: шаблон + DM + текст для каждого КИЗа.

        Args:
            codes: Список словарей с данными КИЗов
            config: Конфигурация из TemplatePdfState.get_config()
            output_path: Путь для сохранения
            progress_callback: Колбэк прогресса (current, total, message)

        Returns:
            Путь к сохранённому файлу
        """
        template_doc = fitz.open(str(self.template_path))
        template_page = template_doc[0]

        output_doc = fitz.open()

        total = len(codes)

        for i, code_info in enumerate(codes):
            # Прогресс
            if progress_callback:
                try:
                    progress_callback(
                        i + 1, total, f"Обработано КИЗов: {i + 1:,} / {total:,}"
                    )
                except InterruptedError:
                    template_doc.close()
                    output_doc.close()
                    return output_path

            # Создаём новую страницу из шаблона
            new_page = output_doc.new_page(
                width=template_page.rect.width, height=template_page.rect.height
            )

            # Копируем содержимое шаблона
            new_page.show_pdf_page(new_page.rect, template_doc, 0)

            # Накладываем DM
            self._overlay_dm(new_page, code_info, config)

            # Накладываем текст
            self._overlay_text(new_page, code_info, config)

        output_doc.save(str(output_path))
        output_doc.close()
        template_doc.close()

        return output_path

    def _overlay_dm(self, page: fitz.Page, code_info: Dict, config: Dict):
        """Наложить Data Matrix на страницу."""
        dm_config = config.get("dm_element", {})

        x_mm = dm_config.get("x_mm", 10)
        y_mm = dm_config.get("y_mm", 10)
        size_mm = dm_config.get("size_mm", 16)
        quiet_zone_mm = dm_config.get("quiet_zone_mm", 2)

        # Конвертируем мм → pt (1 pt = 1/72 inch, 1 mm = 2.83465 pt)
        PT_PER_MM = 2.83465

        x_pt = x_mm * PT_PER_MM
        y_pt = y_mm * PT_PER_MM
        w_pt = size_mm * PT_PER_MM
        h_pt = size_mm * PT_PER_MM

        # Генерируем DM
        code = code_info.get("code", "") or code_info.get("kiz", "") or ""

        try:
            dm_bytes = self.dm_generator.generate(
                code,
                target_size_mm=size_mm,
                dpi=self.DPI,
                exact_size=True,  # Точный размер без дополнительного QZ
            )

            # Вставляем изображение
            rect = fitz.Rect(x_pt, y_pt, x_pt + w_pt, y_pt + h_pt)
            page.insert_image(rect, stream=dm_bytes)

        except Exception as e:
            print(f"[OVERLAY DM ERROR] {e}")

    def _overlay_text(self, page: fitz.Page, code_info: Dict, config: Dict):
        """Наложить текст на страницу."""
        text_config = config.get("text_element")
        if not text_config:
            return

        text_type = text_config.get("text_type", "index")
        if text_type == "none":
            return

        # Получаем текст
        text = self._get_text(code_info, text_type)
        if not text:
            return

        x_mm = text_config.get("x_mm", 10)
        y_mm = text_config.get("y_mm", 30)
        font_size = text_config.get("font_size", 8)

        PT_PER_MM = 2.83465

        x_pt = x_mm * PT_PER_MM
        y_pt = y_mm * PT_PER_MM

        # PyMuPDF: y=0 сверху, текст рисуется с базовой линии
        # Смещаем вниз на высоту шрифта
        font_size_pt = font_size * 0.35 * PT_PER_MM  # Приблизительно pt

        # Вставляем текст
        text_rect = fitz.Rect(
            x_pt, y_pt - font_size_pt, x_pt + 100 * PT_PER_MM, y_pt + 5 * PT_PER_MM
        )

        page.insert_text(
            (x_pt, y_pt),
            text,
            fontsize=font_size_pt,
            color=(0, 0, 0),
        )

    def _get_text(self, code_info: Dict, text_type: str) -> str:
        """Получить текст в зависимости от типа."""
        if text_type == "gtin":
            return code_info.get("gtin", "")
        elif text_type == "article":
            return code_info.get("article", "")
        elif text_type == "index":
            kiz_number = code_info.get("kiz_number", "")
            if kiz_number:
                return str(kiz_number)
            return str(code_info.get("global_index", ""))
        return ""

    def generate_split(
        self,
        codes: List[Dict],
        config: Dict,
        output_dir: Path,
        base_name: str,
        split_threshold: int = 0,
        progress_callback: Optional[Callable] = None,
    ) -> List[Path]:
        """
        Генерация с разбивкой по лимиту страниц.

        Args:
            codes: Список КИЗов
            config: Конфигурация
            output_dir: Папка для сохранения
            base_name: Базовое имя файла (без расширения)
            split_threshold: Лимит страниц на файл (0 = без разбивки)
            progress_callback: Колбэк прогресса

        Returns:
            Список путей к созданным файлам
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        if split_threshold == 0 or len(codes) <= split_threshold:
            # Один файл
            output_path = output_dir / f"{base_name}.pdf"
            self.generate(codes, config, output_path, progress_callback)
            return [output_path]

        # Разбивка на части
        chunks = []
        for i in range(0, len(codes), split_threshold):
            chunks.append(codes[i : i + split_threshold])

        generated_files = []
        total_codes = len(codes)
        processed = 0

        for chunk_idx, chunk in enumerate(chunks):
            start_num = chunk_idx * split_threshold + 1
            end_num = min((chunk_idx + 1) * split_threshold, total_codes)

            output_path = output_dir / f"{base_name}_{start_num:03d}-{end_num:03d}.pdf"

            def chunk_progress(current, total, msg):
                if progress_callback:
                    global_current = processed + current
                    progress_callback(global_current, total_codes, msg)

            self.generate(chunk, config, output_path, chunk_progress)
            generated_files.append(output_path)
            processed += len(chunk)

        return generated_files
