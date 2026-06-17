"""
File management utilities.
"""

import shutil
from pathlib import Path
from datetime import datetime


class FileManager:
    """Управление файлами проекта."""

    def __init__(self, uploads_dir: Path, output_dir: Path):
        self.uploads_dir = uploads_dir
        self.output_dir = output_dir

        # Создание директорий
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_upload(self, source_path: Path, original_name: str) -> Path:
        """Сохранение загруженного файла."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{timestamp}_{original_name}"
        dest_path = self.uploads_dir / safe_name

        shutil.copy2(source_path, dest_path)
        return dest_path

    def get_output_path(self, prefix: str = "labels", ext: str = "pdf") -> Path:
        """Генерация пути для выходного файла."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.{ext}"
        return self.output_dir / filename

    def cleanup_old_files(self, max_age_days: int = 7):
        """Очистка старых файлов."""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=max_age_days)

        for directory in [self.uploads_dir, self.output_dir]:
            for file_path in directory.iterdir():
                if file_path.is_file():
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff:
                        file_path.unlink()
