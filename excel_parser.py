"""
Парсер Excel файлов с кодами Честного Знака.
Поддерживает кастомный маппинг колонок.
ИСПРАВЛЕНО: декодирование _x001D_ → реальный символ GS (ASCII 29) для Data Matrix.
ИСПРАВЛЕНО: kiz_number теперь сохраняется как строка (не int), чтобы сохранить ведущие нули.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable

import pandas as pd


class ExcelParser:
    """Парсер Excel файлов с кодами Честного Знака."""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.df = None
        self._mapping: Optional[Dict[str, str]] = None

    def set_mapping(self, mapping: Dict[str, str]):
        """Установка маппинга колонок (из ExcelMappingDialog)."""
        self._mapping = mapping

    def _decode_gs1_code(self, raw_code: str) -> str:
        """Декодирует escape-последовательности Excel в реальные GS1 символы."""
        if not raw_code:
            return raw_code

        decoded = raw_code.replace("_x001D_", "\x1d")
        decoded = decoded.replace("_x001E_", "\x1e")
        decoded = decoded.replace("_x0004_", "\x04")

        return decoded

    def preview_headers(self, rows: int = 3) -> Dict:
        """Быстрое чтение заголовков и первых N строк для превью."""
        try:
            df = pd.read_excel(
                self.file_path,
                header=0,
                nrows=rows + 1,
                engine="openpyxl",
            )
        except Exception:
            df = pd.read_excel(
                self.file_path,
                header=None,
                nrows=rows,
                engine="openpyxl",
            )
            df.columns = [f"Колонка {i+1}" for i in range(len(df.columns))]

        headers = list(df.columns.astype(str))

        rows_data = []
        for _, row in df.head(rows).iterrows():
            rows_data.append([str(v) if pd.notna(v) else "" for v in row])

        return {
            "headers": headers,
            "rows": rows_data,
        }

    def parse(
        self,
        mapping: Optional[Dict[str, str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Dict]:
        """Парсинг Excel файла с группировкой по SSCC."""
        if mapping:
            return self._parse_with_mapping(mapping, progress_callback)
        else:
            return self._parse_legacy(progress_callback)

    def _parse_with_mapping(
        self,
        mapping: Dict[str, str],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Dict]:

        """Парсинг с кастомным маппингом колонок."""
        try:
            self.df = pd.read_excel(self.file_path, header=0, engine="openpyxl")
        except Exception as e:
            raise ValueError(f"Не удалось открыть файл: {e}")
        print(f"[DEBUG HEADERS] {list(self.df.columns)}")
        total_rows = len(self.df)

        active_mapping = {
            k: v for k, v in mapping.items() if v is not None and v != "None"
        }
        missing = []
        for field, col_name in active_mapping.items():
            if col_name not in self.df.columns:
                missing.append(f"{FIELD_LABELS.get(field, field)} → '{col_name}'")

        if missing:
            raise ValueError(
                f"В файле не найдены указанные колонки:\n" + "\n".join(missing)
            )

        result = {}

        for idx, row in self.df.iterrows():
            if progress_callback and idx % 100 == 0:
                try:
                    progress_callback(min(idx, total_rows), total_rows)
                except InterruptedError:
                    raise InterruptedError("Операция отменена пользователем")

            article_val = row.get(active_mapping.get("article"))
            gtin_val = row.get(active_mapping.get("gtin"))
            box_number_val = (
                row.get(active_mapping.get("box_number"))
                if "box_number" in active_mapping
                else None
            )
            sscc_val = row.get(active_mapping.get("sscc"))
            kiz_number_val = (
                row.get(active_mapping.get("kiz_number"))
                if "kiz_number" in active_mapping
                else None
            )
            kiz_val = row.get(active_mapping.get("kiz"))


            if pd.isna(sscc_val) or pd.isna(kiz_val):
                continue

            sscc = str(sscc_val).strip()
            kiz_raw = str(kiz_val).strip()
            kiz = self._decode_gs1_code(kiz_raw)

            if pd.notna(article_val):
                article = str(article_val).strip()
            else:
                article = ""

            if pd.notna(gtin_val):
                gtin = str(gtin_val).strip()
            else:
                gtin = ""

            box_number = ""
            if box_number_val is not None and pd.notna(box_number_val):
                box_number = str(box_number_val).strip()

            # === ИСПРАВЛЕНИЕ: kiz_number как строка, сохраняем ведущие нули ===
            kiz_number = ""
            if kiz_number_val is not None and pd.notna(kiz_number_val):
                kiz_number = str(kiz_number_val).strip()

            if not gtin:
                gtin = "UNKNOWN"

            if not article:
                article = gtin

            if not sscc or not kiz:
                continue

            if sscc not in result:
                result[sscc] = {
                    "sscc": sscc,
                    "article": article,
                    "gtin": gtin,
                    "box_number": box_number,
                    "codes": [],
                }

            code_data = {
                "kiz": kiz,
                "index": len(result[sscc]["codes"]) + 1,
            }

            if kiz_number:
                code_data["kiz_number"] = kiz_number

            result[sscc]["codes"].append(code_data)

        # === ДОБАВЛЯЕМ ГЛОБАЛЬНЫЙ ИНДЕКС ===
        global_idx = 1
        for sscc in result:
            for code in result[sscc]["codes"]:
                code["global_index"] = global_idx
                global_idx += 1

        if progress_callback:
            progress_callback(total_rows, total_rows)

        if not result:
            raise ValueError(
                "Не найдены данные. Проверьте выбор колонок и содержимое файла."
            )

        return result

    def _parse_legacy(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Dict]:
        """Старый формат парсинга (без заголовков, фиксированные колонки)."""
        try:
            self.df = pd.read_excel(self.file_path, header=None)
        except Exception as e:
            raise ValueError(f"Не удалось открыть файл: {e}")

        if len(self.df.columns) < 3:
            raise ValueError(
                f"Файл должен содержать минимум 3 колонки "
                f"(A=SSCC, B=КИЗ, C=GTIN+название). Найдено: {len(self.df.columns)}"
            )

        total_rows = len(self.df)
        result = {}

        for idx, row in self.df.iterrows():
            if progress_callback and idx % 100 == 0:
                progress_callback(min(idx, total_rows), total_rows)

            sscc_val = row[0]
            kiz_val = row[1]
            gtin_name_val = row[2]

            if pd.isna(sscc_val) or pd.isna(kiz_val):
                continue

            sscc = str(sscc_val).strip()
            kiz_raw = str(kiz_val).strip()
            kiz = self._decode_gs1_code(kiz_raw)

            gtin_name = str(gtin_name_val).strip() if pd.notna(gtin_name_val) else ""

            gtin, name = self._parse_gtin_name(gtin_name)

            if not sscc or not kiz:
                continue

            if sscc not in result:
                result[sscc] = {
                    "sscc": sscc,
                    "article": name if name else gtin,
                    "gtin": gtin if gtin else "UNKNOWN",
                    "box_number": "",
                    "codes": [],
                }

            result[sscc]["codes"].append(
                {
                    "kiz": kiz,
                    "index": len(result[sscc]["codes"]) + 1,
                }
            )

        # === ДОБАВЛЯЕМ ГЛОБАЛЬНЫЙ ИНДЕКС ===
        global_idx = 1
        for sscc in result:
            for code in result[sscc]["codes"]:
                code["global_index"] = global_idx
                global_idx += 1

        if progress_callback:
            progress_callback(total_rows, total_rows)

        if not result:
            raise ValueError(
                "Не найдены данные. Проверьте формат файла: A=SSCC, B=КИЗ, C=GTIN+название"
            )

        return result

    def _parse_gtin_name(self, gtin_name: str) -> Tuple[str, str]:
        """Извлечение GTIN и названия из строки."""
        if not gtin_name:
            return "", "Неизвестный товар"

        match = re.search(r"\b(\d{8}|\d{12}|\d{13}|\d{14})\b", gtin_name)

        if match:
            gtin = match.group(1)
            name_start = match.end()
            name = gtin_name[name_start:].strip()
            name = re.sub(r"^[\s\-–—_]+", "", name)
            return gtin, name if name else f"Товар {gtin}"

        return "", gtin_name


# Константы для ошибок маппинга
FIELD_LABELS = {
    "article": "Артикул",
    "gtin": "GTIN",
    "box_number": "Номер агрегата",
    "sscc": "Агрегат (SSCC)",
    "kiz_number": "номер киза",
    "kiz": "Код маркировки (КИЗ)",
}
