"""
Диалог маппинга колонок Excel — пользователь выбирает,
какая колонка соответствует GTIN, КИЗу, SSCC и т.д.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QCheckBox,
    QMessageBox,
    QHeaderView,
)
from PyQt6.QtCore import Qt, pyqtSignal


# Ключевые слова для авто-определения колонок
KEYWORDS = {
    "article": [
        "артикул",
        "арт.",
        "article",
        "код товара",
        "product code",
        "артикул товара",
    ],
    "gtin": [
        "гтин",
        "gtin",
        "gs1",
        "gsin",
        "ean",
        "код gtin",
    ],
    "box_number": [
        "номер агрегата",
        "номер короба",
        "box number",
        "номер упаковки",
        "порядковый номер агрегата",
    ],
    "sscc": [
        "агрегат",
        "sscc",
        "короб",
        "box",
        "aggregat",
        "упаковка",
        "паллета",
        "контейнер",
    ],
    "kiz_number": [
        "номер киза",
        "порядковый номер киза",
        "kiz number",
        "номер маркировки",
        "sequence number",
    ],
    "kiz": [
        "киз",
        "код маркировки",
        "honest sign",
        "честный знак",
        "mark code",
        "dm",
        "data matrix",
        "маркировка",
        "код чз",
    ],
}

# Читаемые названия для UI
FIELD_LABELS = {
    "article": "📝 Артикул",
    "gtin": "📊 GTIN",
    "box_number": "📦 Номер агрегата",
    "sscc": "📋 Агрегат (SSCC)",
    "kiz_number": "🔢 Номер киза",
    "kiz": "🏷️ Код маркировки (КИЗ)",
}

# Обязательные поля
REQUIRED_FIELDS = ["article", "gtin", "sscc", "kiz"]


class ExcelMappingDialog(QDialog):
    """Диалог выбора соответствия колонок Excel полям данных."""

    # Сигнал: выбран маппинг, можно парсить
    mapping_confirmed = pyqtSignal(dict)

    def __init__(
        self,
        headers: List[str],
        preview_rows: List[List[str]],
        file_path: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("📁 Кастомный импорт Excel")
        self.setMinimumSize(700, 500)
        self.headers = headers
        self.preview_rows = preview_rows
        self.file_path = Path(file_path)
        self.presets_dir = Path(__file__).parent.parent.parent / "presets"
        self.presets_dir.mkdir(exist_ok=True)

        self._mapping: Dict[str, Optional[str]] = {
            "article": None,
            "gtin": None,
            "box_number": None,
            "sscc": None,
            "kiz_number": None,
            "kiz": None,
        }

        self._combos: Dict[str, QComboBox] = {}
        self._setup_ui()
        self._auto_detect_mapping()
        self._load_preset()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Заголовок
        lbl_title = QLabel(f"Файл: <b>{self.file_path.name}</b>")
        lbl_title.setStyleSheet("font-size: 13px;")
        layout.addWidget(lbl_title)

        # === ПРЕДПРОСМОТР ДАННЫХ ===
        preview_group = QGroupBox("Предпросмотр данных (первые строки)")
        preview_layout = QVBoxLayout(preview_group)

        self.table_preview = QTableWidget()
        self.table_preview.setColumnCount(len(self.headers))
        self.table_preview.setHorizontalHeaderLabels(self.headers)
        self.table_preview.setRowCount(len(self.preview_rows))

        for row_idx, row_data in enumerate(self.preview_rows):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value)[:50])  # Обрезаем длинные строки
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table_preview.setItem(row_idx, col_idx, item)

        self.table_preview.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table_preview.setMaximumHeight(150)
        self.table_preview.setStyleSheet(
            """
            QTableWidget {
                border: 1px solid #ddd;
                font-size: 11px;
            }
            QHeaderView::section {
                background: #4CAF50;
                color: white;
                padding: 5px;
                font-weight: bold;
            }
        """
        )

        preview_layout.addWidget(self.table_preview)
        layout.addWidget(preview_group)

        # === НАЗНАЧЕНИЕ КОЛОНОК ===
        mapping_group = QGroupBox("Назначение колонок")
        mapping_layout = QVBoxLayout(mapping_group)
        mapping_layout.setSpacing(10)

        # Для каждого поля — выпадающий список
        fields_layout = QHBoxLayout()
        fields_layout.setSpacing(15)

        for field_key, field_label in FIELD_LABELS.items():
            field_box = QVBoxLayout()

            lbl = QLabel(field_label)
            lbl.setStyleSheet(
                "font-size: 11px; font-weight: bold;"
                if field_key in REQUIRED_FIELDS
                else "font-size: 11px;"
            )
            field_box.addWidget(lbl)

            combo = QComboBox()
            combo.setMinimumWidth(180)
            combo.addItem("— Не выбрано —", None)

            for header in self.headers:
                combo.addItem(header, header)

            combo.currentIndexChanged.connect(
                lambda idx, key=field_key: self._on_mapping_changed(key)
            )

            # Помечаем обязательные
            if field_key in REQUIRED_FIELDS:
                lbl.setText(lbl.text() + " *")

            field_box.addWidget(combo)
            self._combos[field_key] = combo
            fields_layout.addLayout(field_box)

        mapping_layout.addLayout(fields_layout)

        # Чекбокс запомнить
        self.chk_remember = QCheckBox("Запомнить выбор для файлов с такими заголовками")
        self.chk_remember.setChecked(True)
        mapping_layout.addWidget(self.chk_remember)

        layout.addWidget(mapping_group)

        # === КНОПКИ ===
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setFixedWidth(120)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_load = QPushButton("✓ Загрузить")
        self.btn_load.setFixedWidth(120)
        self.btn_load.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #ccc; }
        """
        )
        self.btn_load.clicked.connect(self._on_confirm)

        buttons_layout.addWidget(self.btn_cancel)
        buttons_layout.addWidget(self.btn_load)

        layout.addLayout(buttons_layout)

        # Статус валидации
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 11px;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

    def _auto_detect_mapping(self):
        """Авто-определение колонок по ключевым словам."""
        for field_key, keywords in KEYWORDS.items():
            best_match = None
            best_score = 0

            for header in self.headers:
                header_lower = header.lower().strip()
                score = 0

                for keyword in keywords:
                    if keyword in header_lower:
                        # Точное совпадение важнее частичного
                        if header_lower == keyword:
                            score = 100
                        elif header_lower.startswith(keyword):
                            score = max(score, 50)
                        else:
                            score = max(score, 20)

                if score > best_score:
                    best_score = score
                    best_match = header

            if best_match and best_score >= 20:
                combo = self._combos[field_key]
                idx = combo.findData(best_match)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                    self._mapping[field_key] = best_match

        self._validate_mapping()

    def _on_mapping_changed(self, field_key: str):
        """Обработка изменения выбора в комбо."""
        combo = self._combos[field_key]
        data = combo.currentData()
        self._mapping[field_key] = data
        self._validate_mapping()

    def _validate_mapping(self) -> bool:
        """Проверка, что все обязательные поля выбраны."""
        missing = []
        for field in REQUIRED_FIELDS:
            if not self._mapping.get(field):
                missing.append(
                    FIELD_LABELS[field]
                    .replace("📝 ", "")
                    .replace("📊 ", "")
                    .replace("📦 ", "")
                    .replace("📋 ", "")
                    .replace("🔢 ", "")
                    .replace("🏷️ ", "")
                )

        if missing:
            self.lbl_status.setText(
                f"⚠️ Выберите обязательные поля: {', '.join(missing)}"
            )
            self.lbl_status.setStyleSheet("color: #f44336; font-size: 11px;")
            self.btn_load.setEnabled(False)
            return False

        # Проверка уникальности (одна колонка не может быть назначена дважды)
        used = {}
        duplicates = []
        for field, col in self._mapping.items():
            if col and col in used:
                duplicates.append(f"{FIELD_LABELS[field]} ↔ {FIELD_LABELS[used[col]]}")
            elif col:
                used[col] = field

        if duplicates:
            self.lbl_status.setText(f"⚠️ Колонки дублируются: {'; '.join(duplicates)}")
            self.lbl_status.setStyleSheet("color: #f44336; font-size: 11px;")
            self.btn_load.setEnabled(False)
            return False

        self.lbl_status.setText("✓ Все поля назначены корректно")
        self.lbl_status.setStyleSheet("color: #4CAF50; font-size: 11px;")
        self.btn_load.setEnabled(True)
        return True

    def _get_preset_path(self) -> Path:
        """Путь к файлу пресета на основе хеша заголовков."""
        import hashlib

        headers_str = "|".join(sorted(self.headers))
        hash_val = hashlib.md5(headers_str.encode()).hexdigest()[:12]
        return self.presets_dir / f"mapping_{hash_val}.json"

    def _load_preset(self):
        """Загрузка сохранённого маппинга."""
        preset_path = self._get_preset_path()
        if not preset_path.exists():
            return

        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                preset = json.load(f)

            for field_key, col_name in preset.items():
                if col_name in self.headers and field_key in self._combos:
                    combo = self._combos[field_key]
                    idx = combo.findData(col_name)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                        self._mapping[field_key] = col_name

            self._validate_mapping()

        except Exception:
            pass  # Игнорируем битые пресеты

    def _save_preset(self):
        """Сохранение маппинга в файл."""
        if not self.chk_remember.isChecked():
            return

        preset_path = self._get_preset_path()
        try:
            with open(preset_path, "w", encoding="utf-8") as f:
                json.dump(self._mapping, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _on_confirm(self):
        """Подтверждение выбора."""
        if not self._validate_mapping():
            return

        self._save_preset()
        self.mapping_confirmed.emit(self._mapping)
        self.accept()

    def get_mapping(self) -> Dict[str, Optional[str]]:
        """Получение итогового маппинга."""
        return self._mapping.copy()

    def get_required_mapping(self) -> Dict[str, str]:
        """Получение только обязательных полей (без None)."""
        return {k: v for k, v in self._mapping.items() if v is not None}
