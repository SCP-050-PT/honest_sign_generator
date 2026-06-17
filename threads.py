"""
Потоки для длительных операций с сигналами прогресса.
ИСПРАВЛЕНО: убран cancel_event, генерация последовательная.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.excel_parser import ExcelParser
from core.pdf import PDFGenerator


class ExcelLoadThread(QThread):
    """Поток загрузки Excel с прогрессом и поддержкой маппинга."""

    progress = pyqtSignal(int, int)
    details = pyqtSignal(str)
    preview_ready = pyqtSignal(dict)
    mapping_needed = pyqtSignal()
    finished_ok = pyqtSignal(dict, str)
    error = pyqtSignal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        self._cancelled = False
        self._mapping: Optional[Dict[str, str]] = None
        self._wait_for_mapping = True

    def cancel(self):
        self._cancelled = True

    def set_mapping(self, mapping: Dict[str, str]):
        self._mapping = mapping
        self._wait_for_mapping = False

    def run(self):
        try:
            parser = ExcelParser(self.file_path)

            self.details.emit("Анализ структуры файла...")
            preview = parser.preview_headers(rows=3)
            self.preview_ready.emit(preview)
            self.mapping_needed.emit()

            wait_count = 0
            while self._wait_for_mapping and not self._cancelled:
                time.sleep(0.1)
                wait_count += 1
                if wait_count > 600:
                    self.error.emit("Таймаут ожидания выбора колонок")
                    return

            if self._cancelled:
                self.error.emit("Операция отменена пользователем")
                return

            if not self._mapping:
                self.error.emit("Не выбран маппинг колонок")
                return

            self.details.emit("Чтение данных с выбранными колонками...")

            import pandas as pd

            df = pd.read_excel(self.file_path, header=0, engine="openpyxl")
            total_rows = len(df)
            self.progress.emit(0, total_rows)

            def parse_progress(current, total):
                self.progress.emit(current, total)
                self.details.emit(f"Обработано строк: {current:,} / {total:,}")

            result = parser.parse(
                mapping=self._mapping, progress_callback=parse_progress
            )
            self.progress.emit(total_rows, total_rows)
            self.finished_ok.emit(result, Path(self.file_path).name)

        except Exception as e:
            self.error.emit(str(e))


class PDFGenerationThread(QThread):
    """
    Поток генерации PDF — последовательная обработка.
    """

    progress = pyqtSignal(int, int)
    details = pyqtSignal(str)
    finished_ok = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(
        self,
        sscc_data: Dict,
        template_config: dict,
        output_dir: Path,
        mode: str,
        print_mode: str = "fill",
    ):
        super().__init__()
        self.sscc_data = sscc_data
        self.template_config = template_config
        self.output_dir = output_dir
        self.mode = mode
        self.print_mode = print_mode
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            start_time = time.time()

            total_kiz = sum(len(data["codes"]) for data in self.sscc_data.values())
            total_sscc = len(self.sscc_data)

            self.details.emit(f"SSCC: {total_sscc}  |  КИЗов: {total_kiz:,}")

            generator = PDFGenerator(mode=self.mode, print_mode=self.print_mode)

            def progress_callback(current, total, message):
                """Обновляет прогресс."""
                if self._cancelled:
                    raise InterruptedError("Операция отменена")
                self.progress.emit(current, total)
                self.details.emit(message)

            # Запускаем генерацию — без cancel_event
            generated_files = generator.generate_by_gtin(
                self.sscc_data,
                template_config=self.template_config,
                output_dir=self.output_dir,
                progress_callback=progress_callback,
            )

            if self._cancelled:
                self.error.emit("Операция отменена пользователем")
                return

            if not generated_files:
                self.error.emit("Не сгенерировано ни одного файла")
                return

            elapsed = time.time() - start_time
            self.details.emit(f"Готово! Время: {elapsed:.1f} сек")

            self.progress.emit(total_kiz, total_kiz)
            self.finished_ok.emit([str(p) for p in generated_files])

        except InterruptedError:
            self.error.emit("Операция отменена пользователем")
        except Exception as e:
            self.error.emit(str(e))
