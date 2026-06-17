"""
Main PDF generator class.
ИСПРАВЛЕНО: single режим без PyMuPDF — прямой canvas с setPageSize().
ИСПРАВЛЕНО: разбивка PDF настраивается через template_config (split_threshold).
           0 = без разбивки (один файл).
ИСПРАВЛЕНО: global_kiz_index и global_box_index теперь сквозные через ВСЕ GTIN.
ИСПРАВЛЕНО: max_dm_size — вычитание вместо умножения для with_elements.
"""

import warnings
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Callable
from io import BytesIO

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

from ..data_matrix import DataMatrixGenerator
from config import DEFAULT_LABEL_CONFIG, DEFAULT_PDF_CONFIG, OUTPUT_DIR

from .fonts import get_font_name
from .grid import get_page_size, get_margins, calc_grid
from .validation import validate_elements_for_label, validate_aggregate_elements
from .draw_aggregate import draw_single_aggregate
from .draw_kiz import draw_single_kiz, draw_single_kiz_dm_only

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


class PDFGenerator:
    """Генератор PDF с этикетками."""

    DPI = 300

    def __init__(
        self, mode="15x15", print_mode="fill", label_config=None, pdf_config=None
    ):
        self.mode = mode
        self.print_mode = print_mode
        self.label_config = label_config or DEFAULT_LABEL_CONFIG
        self.pdf_config = pdf_config or DEFAULT_PDF_CONFIG
        quiet_zone = getattr(self.label_config, "quiet_zone_mm", 2)
        self.dm_generator = DataMatrixGenerator(quiet_zone_mm=quiet_zone)

    def _split_sequence_by_boxes(
        self, sequence: List[Dict], max_kiz: int
    ) -> List[List[Dict]]:
        """Разбивает sequence на чанки по коробам, макс max_kiz КИЗов.
        Короб не разрывается — весь короб (агрегат + все его КИЗы) идёт в один файл."""
        chunks = []
        current_chunk = []
        current_kiz_count = 0

        i = 0
        while i < len(sequence):
            item = sequence[i]

            if item["type"] == "aggregate":
                box_kiz_count = 0
                j = i + 1
                while j < len(sequence) and sequence[j]["type"] == "kiz":
                    box_kiz_count += 1
                    j += 1

                if (
                    current_kiz_count + box_kiz_count > max_kiz
                    and current_kiz_count > 0
                ):
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_kiz_count = 0

                current_chunk.append(item)
                for k in range(i + 1, j):
                    current_chunk.append(sequence[k])
                current_kiz_count += box_kiz_count
                i = j
            else:
                if current_kiz_count + 1 > max_kiz and current_kiz_count > 0:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_kiz_count = 0
                current_chunk.append(item)
                current_kiz_count += 1
                i += 1

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def generate_by_gtin(
        self,
        sscc_groups: Dict[str, Dict],
        template_config: Optional[Dict] = None,
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Path]:
        """Генерация PDF по артикулам/GTIN с разбивкой на части."""
        if output_dir is None:
            output_dir = OUTPUT_DIR

        output_dir.mkdir(parents=True, exist_ok=True)

        gtin_groups = {}
        for sscc, data in sscc_groups.items():
            gtin = data.get("gtin") or "UNKNOWN"
            article = data.get("article") or gtin

            if gtin not in gtin_groups:
                gtin_groups[gtin] = {
                    "gtin": gtin,
                    "article": article,
                    "sscc_list": [],
                    "codes": [],
                }

            box_number = data.get("box_number") or str(
                len(gtin_groups[gtin]["sscc_list"]) + 1
            )

            if sscc not in [s["sscc"] for s in gtin_groups[gtin]["sscc_list"]]:
                gtin_groups[gtin]["sscc_list"].append(
                    {
                        "sscc": sscc,
                        "code_count": len(data["codes"]),
                        "box_number": box_number,
                    }
                )

            for code_info in data["codes"]:
                code_with_ref = {
                    **code_info,
                    "parent_sscc": sscc,
                    "gtin": gtin,
                    "article": article,
                }
                gtin_groups[gtin]["codes"].append(code_with_ref)

        total_kiz = sum(len(data["codes"]) for data in gtin_groups.values())
        processed_kiz = 0

        generated_files = []
        total_gtin = len(gtin_groups)

        # === ИСПРАВЛЕНИЕ: сквозные индексы через ВСЕ GTIN ===
        global_kiz_index = 1
        global_box_index = 1

        for idx, (gtin, data) in enumerate(gtin_groups.items(), 1):
            if progress_callback:
                try:
                    progress_callback(
                        processed_kiz,
                        total_kiz,
                        f"Генерация PDF {idx}/{total_gtin}: GTIN {gtin} ({len(data['codes'])} КИЗов)",
                    )
                except InterruptedError:
                    return generated_files

            safe_gtin = "".join(c for c in gtin if c.isalnum()) or "UNKNOWN"
            safe_article = (
                "".join(c for c in data["article"] if c.isalnum()) or "UNKNOWN"
            )
            base_output_path = (
                output_dir
                / f"ART_{safe_article}_{safe_gtin}_{self.mode}_{self.print_mode}"
            )

            # === ИСПРАВЛЕНИЕ: передаём сквозные индексы в _generate_gtin_pdf_split ===
            paths, global_kiz_index, global_box_index = self._generate_gtin_pdf_split(
                data,
                template_config,
                base_output_path,
                progress_callback,
                processed_kiz,
                total_kiz,
                global_kiz_index,
                global_box_index,
            )
            generated_files.extend(paths)

            processed_kiz += len(data["codes"])

        if progress_callback:
            try:
                progress_callback(total_kiz, total_kiz, "Генерация завершена!")
            except InterruptedError:
                pass

        return generated_files

    def _generate_gtin_pdf_split(
        self,
        gtin_data: Dict,
        template_config: Optional[Dict],
        base_output_path: Path,
        progress_callback: Optional[Callable] = None,
        processed_kiz: int = 0,
        total_kiz: int = 0,
        global_kiz_index: int = 1,
        global_box_index: int = 1,
    ):
        """Генерация PDF для одного артикула/GTIN с разбивкой на части.
        Возвращает: (paths, new_global_kiz_index, new_global_box_index)
        """
        gtin = gtin_data["gtin"]
        article = gtin_data.get("article", "UNKNOWN")
        sscc_list = gtin_data["sscc_list"]
        codes = gtin_data["codes"]

        with_aggregates = (
            template_config.get("with_aggregates", True) if template_config else True
        )

        dm_n = template_config.get("label_size_mm", 15) if template_config else 15
        agg_n = (
            template_config.get("aggregate_label_size_mm", dm_n)
            if template_config
            else dm_n
        )
        gap_mm = template_config.get("gap_mm", 2) if template_config else 2

        single_mode_type = (
            template_config.get("single_mode_type", "with_elements")
            if template_config
            else "with_elements"
        )

        print_mode = (
            template_config.get("print_mode", self.print_mode)
            if template_config
            else self.print_mode
        )

        if print_mode == "single":
            cols_per_page = 1
            rows_per_page = 1
        else:
            page_w = (
                template_config.get("page_width_mm", 210) if template_config else 210
            )
            page_h = (
                template_config.get("page_height_mm", 297) if template_config else 297
            )
            margins = get_margins(template_config)
            cols_per_page, rows_per_page, _ = calc_grid(
                page_w, page_h, dm_n, margins, gap_mm
            )

        max_per_page = cols_per_page * rows_per_page

        quiet_zone_mm = (
            template_config.get("quiet_zone_mm", 2) if template_config else 2
        )
        self.dm_generator.quiet_zone_mm = quiet_zone_mm

        bottom_field = (
            template_config.get("bottom_field_mm", 1) if template_config else 1
        )

        dm_size = (
            template_config.get("dm_size_mm", dm_n - 1) if template_config else dm_n - 1
        )
        dm_size = max(dm_size, 1)

        # === ДОБАВЛЕНО: динамический расчёт макс. DM ===
        from .validation import calc_max_dm_size
        
        dm_max = calc_max_dm_size(
            dm_n,
            template_config.get("bottom_field_type", "index") if template_config else "index",
            template_config.get("index_size", 8) if template_config else 8,
            template_config.get("gtin_size", 8) if template_config else 8,
            template_config.get("article_size", 8) if template_config else 8,
            quiet_zone_mm,
        )
        
        if dm_size > dm_max:
            print(f"[WARNING] DM {dm_size}мм уменьшен до {dm_max}мм (не хватает места для текста)")
            dm_size = dm_max

        agg_size = (
            template_config.get("aggregate_size_mm", agg_n - 3)
            if template_config
            else agg_n - 3
        )

        elements = template_config.get("elements", []) if template_config else []
        aggregate_elements = (
            template_config.get("aggregate_elements", []) if template_config else []
        )

        elements = validate_elements_for_label(
            elements, dm_n, dm_size, quiet_zone_mm, bottom_field, single_mode_type
        )
        aggregate_elements = validate_aggregate_elements(
            aggregate_elements, agg_n, agg_size
        )

        # Формируем последовательность этикеток
        sequence = []
        if with_aggregates:
            for idx, sscc_info in enumerate(sscc_list, start=1):
                sequence.append(
                    {
                        "type": "aggregate",
                        "sscc": sscc_info["sscc"],
                        "box_number": sscc_info.get("box_number", str(idx)),
                        "article": article,
                        "gtin": gtin,
                        "index": idx,
                    }
                )
                parent_sscc = sscc_info["sscc"]
                sscc_codes = [c for c in codes if c.get("parent_sscc") == parent_sscc]
                for code_info in sscc_codes:
                    sequence.append(
                        {
                            "type": "kiz",
                            "data": code_info,
                            "article": article,
                            "gtin": gtin,
                        }
                    )
        else:
            for code_info in codes:
                sequence.append(
                    {
                        "type": "kiz",
                        "data": code_info,
                        "article": article,
                        "gtin": gtin,
                    }
                )

        # === Разбивка ===
        split_threshold = (
            template_config.get("split_threshold", 0) if template_config else 0
        )

        if split_threshold == 0:
            chunks = [sequence]
        else:
            chunks = self._split_sequence_by_boxes(sequence, split_threshold)

        generated_files = []
        current_processed = processed_kiz

        for chunk_idx, chunk in enumerate(chunks):
            chunk_kiz_count = sum(1 for item in chunk if item["type"] == "kiz")

            if len(chunks) == 1:
                output_path = Path(f"{base_output_path}.pdf")
            else:
                output_path = Path(f"{base_output_path}_part{chunk_idx+1}.pdf")

            if output_path.exists() and len(chunks) > 1:
                output_path = Path(
                    f"{base_output_path}_part{chunk_idx+1}_{chunk_kiz_count}шт.pdf"
                )

            # Обновляем сквозные индексы в chunk
            chunk_with_indices = []
            for item in chunk:
                new_item = dict(item)
                if new_item["type"] == "aggregate":
                    new_item["index"] = global_box_index
                    global_box_index += 1
                else:
                    new_item["data"] = dict(new_item["data"])
                    new_item["data"]["global_index"] = global_kiz_index
                    global_kiz_index += 1
                chunk_with_indices.append(new_item)

            # Генерируем PDF для этого чанка
            if print_mode == "single" and dm_n != agg_n:
                path = self._generate_single_pdf_direct(
                    chunk_with_indices,
                    output_path,
                    dm_n,
                    agg_n,
                    dm_size,
                    agg_size,
                    bottom_field,
                    elements,
                    aggregate_elements,
                    template_config,
                    progress_callback,
                    current_processed,
                    total_kiz,
                )
            else:
                path = self._generate_fill_pdf(
                    chunk_with_indices,
                    output_path,
                    dm_n,
                    dm_size,
                    agg_size,
                    bottom_field,
                    elements,
                    aggregate_elements,
                    template_config,
                    cols_per_page,
                    rows_per_page,
                    max_per_page,
                    gap_mm,
                    progress_callback,
                    current_processed,
                    total_kiz,
                    agg_n,
                )

            generated_files.append(path)
            current_processed += chunk_kiz_count

        return generated_files, global_kiz_index, global_box_index

    def _generate_single_pdf_direct(
        self,
        sequence: List[Dict],
        output_path: Path,
        dm_n: float,
        agg_n: float,
        dm_size: float,
        agg_size: float,
        bottom_field: float,
        elements: List[Dict],
        aggregate_elements: List[Dict],
        template_config: Optional[Dict],
        progress_callback: Optional[Callable],
        processed_kiz: int,
        total_kiz: int,
    ) -> Path:
        """Генерация single режима БЕЗ PyMuPDF — прямой canvas с setPageSize()."""
        c = canvas.Canvas(str(output_path))
        kiz_counter = 0

        single_mode_type = (
            template_config.get("single_mode_type", "with_elements")
            if template_config
            else "with_elements"
        )

        quiet_zone_mm = (
            template_config.get("quiet_zone_mm", 2) if template_config else 2
        )

        for idx, item in enumerate(sequence):
            if item["type"] == "aggregate":
                c.setPageSize((agg_n * mm, agg_n * mm))
                draw_single_aggregate(
                    c,
                    0,
                    0,
                    agg_n * mm,
                    agg_n * mm,
                    agg_size,
                    item,
                    aggregate_elements,
                    template_config,
                )
            else:
                c.setPageSize((dm_n * mm, dm_n * mm))
                if single_mode_type == "dm_only":
                    draw_single_kiz_dm_only(
                        c,
                        0,
                        0,
                        dm_n * mm,
                        dm_n * mm,
                        dm_size,
                        quiet_zone_mm,
                        item["data"],
                    )
                else:
                    print(f"[GEN_CALL] dm_size={dm_size}, dm_n={dm_n}")
                    print(f"[GEN_CALL] single_mode_type={single_mode_type}")
                    print(f"[GEN_CALL] elements count={len(elements)}")
                    draw_single_kiz(
                        c,
                        0,
                        0,
                        dm_n * mm,
                        dm_n * mm,
                        dm_size,
                        bottom_field,
                        item["data"],
                        elements,
                        template_config,
                    )
                kiz_counter += 1

            c.showPage()

            if progress_callback and item["type"] == "kiz":
                current_kiz = processed_kiz + kiz_counter
                try:
                    progress_callback(
                        current_kiz,
                        total_kiz,
                        f"Обработано КИЗов: {current_kiz:,} / {total_kiz:,}",
                    )
                except InterruptedError:
                    c.save()
                    return output_path

        c.save()
        return output_path

    def _generate_fill_pdf(
        self,
        sequence: List[Dict],
        output_path: Path,
        dm_n: float,
        dm_size: float,
        agg_size: float,
        bottom_field: float,
        elements: List[Dict],
        aggregate_elements: List[Dict],
        template_config: Optional[Dict],
        cols: int,
        rows: int,
        max_per_page: int,
        gap_mm: float,
        progress_callback: Optional[Callable],
        processed_kiz: int,
        total_kiz: int,
        agg_n: float,
    ) -> Path:
        """Генерация fill режима (сетка на странице)."""
        page_size = get_page_size(
            template_config,
            cols=cols,
            rows=rows,
            gap_mm=gap_mm,
        )

        c = canvas.Canvas(str(output_path), pagesize=page_size)

        self._draw_sequence(
            c,
            sequence,
            dm_n,
            dm_size,
            agg_size,
            bottom_field,
            elements,
            aggregate_elements,
            template_config,
            cols,
            rows,
            max_per_page,
            gap_mm,
            progress_callback,
            processed_kiz,
            total_kiz,
            agg_n,
        )

        c.save()
        return output_path

    def _draw_sequence(
        self,
        c,
        sequence: List[Dict],
        label_size_mm: float,
        dm_size_mm: float,
        agg_size_mm: float,
        bottom_field_mm: float,
        elements: List[Dict],
        aggregate_elements: List[Dict],
        template_config: Optional[Dict] = None,
        cols: int = 1,
        rows: int = 1,
        max_per_page: int = 1,
        gap_mm: float = 0,
        progress_callback: Optional[Callable] = None,
        processed_kiz: int = 0,
        total_kiz: int = 0,
        agg_label_size_mm: float = None,
    ):
        """Отрисовка последовательности этикеток."""
        from reportlab.lib.units import mm

        page_w, page_h = c._pagesize
        label_w = label_size_mm * mm
        label_h = label_size_mm * mm
        gap = gap_mm * mm

        margins_mm = 0
        margin = 0 * mm

        available_w = page_w
        available_h = page_h

        total_grid_w = cols * label_w + max(0, cols - 1) * gap
        total_grid_h = rows * label_h + max(0, rows - 1) * gap
        offset_x = 0
        offset_y = 0

        kiz_counter = 0
        is_single_mode = cols == 1 and rows == 1

        single_mode_type = (
            template_config.get("single_mode_type", "with_elements")
            if template_config
            else "with_elements"
        )

        for idx, item in enumerate(sequence):
            if is_single_mode:
                if idx > 0:
                    c.showPage()

                if item["type"] == "aggregate":
                    elem_w = (agg_label_size_mm or label_size_mm) * mm
                    elem_h = (agg_label_size_mm or label_size_mm) * mm
                else:
                    elem_w = label_size_mm * mm
                    elem_h = label_size_mm * mm

                x = (page_w - elem_w) / 2
                y = (page_h - elem_h) / 2
                w = elem_w
                h = elem_h

            else:
                if idx > 0 and idx % max_per_page == 0:
                    c.showPage()

                idx_in_page = idx % max_per_page
                col = idx_in_page % cols
                row = idx_in_page // cols
                x = offset_x + col * (label_w + gap)
                y = page_h - offset_y - (row + 1) * label_h - row * gap
                w = label_w
                h = label_h

            if item["type"] == "aggregate":
                draw_single_aggregate(
                    c,
                    x,
                    y,
                    w,
                    h,
                    agg_size_mm,
                    item,
                    aggregate_elements,
                    template_config,
                )
            else:
                if is_single_mode and single_mode_type == "dm_only":
                    quiet_zone_mm = (
                        template_config.get("quiet_zone_mm", 2)
                        if template_config
                        else 2
                    )
                    draw_single_kiz_dm_only(
                        c,
                        x,
                        y,
                        w,
                        h,
                        dm_size_mm,
                        quiet_zone_mm,
                        item["data"],
                    )
                else:
                    draw_single_kiz(
                        c,
                        x,
                        y,
                        w,
                        h,
                        dm_size_mm,
                        bottom_field_mm,
                        item["data"],
                        elements,
                        template_config,
                    )
                kiz_counter += 1

            if progress_callback and item["type"] == "kiz":
                current_kiz = processed_kiz + kiz_counter
                try:
                    progress_callback(
                        current_kiz,
                        total_kiz,
                        f"Обработано КИЗов: {current_kiz:,} / {total_kiz:,}",
                    )
                except InterruptedError:
                    return

    def generate_all(
        self,
        sscc_groups: Dict[str, Dict],
        template_config: Optional[Dict] = None,
        output_dir: Optional[Path] = None,
    ) -> List[Path]:
        """Обратная совместимость."""
        return self.generate_by_gtin(sscc_groups, template_config, output_dir)
