"""
Менеджер шаблонов: сохранение/загрузка настроек в JSON.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from config import BASE_DIR


class TemplateManager:
    """Управление шаблонами настроек."""

    TEMPLATES_DIR = BASE_DIR / "templates"

    def __init__(self):
        self.TEMPLATES_DIR.mkdir(exist_ok=True)

    def _sanitize_name(self, name: str) -> str:
        """Очистка имени файла от недопустимых символов."""
        invalid = '\/:*?"<>|'
        for ch in invalid:
            name = name.replace(ch, "_")
        return name.strip()

    def save_template(self, name: str, config: Dict) -> Path:
        """Сохранить шаблон в JSON."""
        safe_name = self._sanitize_name(name)
        if not safe_name:
            safe_name = "template"

        file_path = self.TEMPLATES_DIR / f"template_{safe_name}.json"

        # Добавляем метаданные
        data = {
            "name": name,
            "config": config,
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return file_path

    def load_template(self, name: str) -> Optional[Dict]:
        """Загрузить шаблон по имени."""
        safe_name = self._sanitize_name(name)
        file_path = self.TEMPLATES_DIR / f"template_{safe_name}.json"

        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("config", {})

    def load_template_by_path(self, file_path: Path) -> Optional[Dict]:
        """Загрузить шаблон по пути."""
        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("config", {})

    def list_templates(self) -> List[str]:
        """Список сохранённых шаблонов."""
        templates = []
        for f in sorted(self.TEMPLATES_DIR.glob("template_*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                templates.append(data.get("name", f.stem.replace("template_", "")))
            except:
                templates.append(f.stem.replace("template_", ""))
        return templates

    def get_template_path(self, name: str) -> Path:
        """Путь к файлу шаблона."""
        safe_name = self._sanitize_name(name)
        return self.TEMPLATES_DIR / f"template_{safe_name}.json"

    def delete_template(self, name: str) -> bool:
        """Удалить шаблон."""
        file_path = self.get_template_path(name)
        if file_path.exists():
            file_path.unlink()
            return True
        return False
