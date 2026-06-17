"""
Бизнес-логика редактора шаблона: валидации, конфигурация, режимы.
Убран серийный номер.
ИСПРАВЛЕНО: print_mode берётся напрямую из right_panel.print_mode_data.
ДОБАВЛЕНО: split_threshold в get_template_config().
"""


class TemplateState:
    """Состояние и бизнес-логика редактора шаблона."""

    def __init__(self, editor):
        self.editor = editor
        self.sscc_data = {}
        self.selected_code_idx = 0
        self.current_mode = "15x15"
        self.print_mode = "fill"
        self.label_size = (30, 30)  # ДЕФОЛТ 30×30

    def _calc_max_per_page(self) -> int:
        """Расчёт максимального количества этикеток на лист."""
        panel = self.editor.right_panel
        n = panel.label_size_mm
        pw = panel.paper_width_mm
        ph = panel.paper_height_mm

        # === АВТО-ОТСТУПЫ: минимум 2мм или 5% от меньшей стороны ===
        auto_margin = max(2, min(n * 0.1, 10))

        available_w = max(1, pw - 2 * auto_margin)
        available_h = max(1, ph - 2 * auto_margin)

        cols = max(1, int(available_w / n))
        rows = max(1, int(available_h / n))
        return cols * rows

    def update_label_size_text(self):
        panel = self.editor.right_panel
        n = panel.label_size_mm
        # ИСПРАВЛЕНО: берём print_mode из панели
        current_print_mode = panel.print_mode_data
        mode_str = "сетка" if current_print_mode == "fill" else "один на лист"
        self.editor.lbl_size.setText(f"Размер этикетки: {n}×{n} мм ({mode_str})")

    # === Aggregate ===

    def on_aggregate_size_changed(self):
        size = self.editor.right_panel.aggregate_size
        self.editor.info_page.set_aggregate_size(size)
        self.editor.template_changed.emit()

    # === DM Settings ===

    def on_dm_settings_changed(self):
        """Обработка изменений настроек Data Matrix."""
        if self.current_mode != "15x15":
            return

        panel = self.editor.right_panel
        quiet_mm = panel.quiet_zone
        bottom_mm = panel.bottom_field

        self.editor.canvas.set_dm_config(
            quiet_zone_mm=quiet_mm,
            bottom_field_mm=bottom_mm,
            show_gtin=panel.show_gtin,
            show_article=panel.show_article,
            gtin_size=panel.gtin_size,
            article_size=panel.article_size,
        )

        self.validate_limit()

    # === Print mode ===

    def on_print_mode_changed(self, index):
        panel = self.editor.right_panel
        self.print_mode = panel.print_mode_data
        self.update_max_count_label()
        self.update_label_size_text()
        self.validate_limit()

    def update_max_count_label(self):
        panel = self.editor.right_panel
        max_count = self._calc_max_per_page()
        # ИСПРАВЛЕНО: берём print_mode из панели
        current_print_mode = panel.print_mode_data

        if self.current_mode == "15x15":
            if current_print_mode == "fill":
                panel.set_max_count_text(f"Макс. на лист: {max_count} шт.")
                panel.set_limit_maximum(1000)
                panel.set_limit_enabled(True)
            else:
                panel.set_max_count_text("Макс. на лист: 1 шт.")
                panel.set_limit_value(1)
                panel.set_limit_enabled(False)
        else:
            panel.set_max_count_text("Макс. на лист: 1 шт.")
            panel.set_print_mode_index(1)
            panel.set_print_mode_enabled(False)
            panel.set_limit_value(1)
            panel.set_limit_enabled(False)

    # === Validation ===

    def validate_limit(self):
        if not self.sscc_data:
            return

        total_codes = sum(len(data["codes"]) for data in self.sscc_data.values())
        panel = self.editor.right_panel
        requested = panel.limit
        # ИСПРАВЛЕНО: берём print_mode из панели
        current_print_mode = panel.print_mode_data

        if self.current_mode == "15x15" and current_print_mode == "fill":
            codes_per_page = self._calc_max_per_page()

            if requested > codes_per_page:
                panel.set_validation_text(
                    f"⚠️ Установлено максимум: {codes_per_page}",
                    "color: #FF9800; font-size: 10px;",
                )
                panel.set_limit_value(codes_per_page)
            elif requested > total_codes:
                panel.set_validation_text(
                    f"ℹ️ В файле только {total_codes} КИЗов",
                    "color: #2196F3; font-size: 10px;",
                )
            else:
                pages_needed = (requested + codes_per_page - 1) // codes_per_page
                panel.set_validation_text(
                    f"✓ {pages_needed} стр. ({codes_per_page} на лист)",
                    "color: #4CAF50; font-size: 10px;",
                )

    # === Mode ===

    def set_mode(self, mode: str):
        self.current_mode = mode
        panel = self.editor.right_panel

        if mode == "15x15":
            self.label_size = (panel.label_size_mm, panel.label_size_mm)
            self.editor.page_tabs.setTabText(1, "🏷️ Страница 2: Этикетки")
            panel.set_print_mode_enabled(True)
            panel.set_print_mode_index(0)
            panel.set_limit_enabled(True)
        else:
            self.label_size = (30, 30)
            self.editor.page_tabs.setTabText(1, "🏷️ Страница 2: Этикетки")
            panel.set_print_mode_index(1)
            panel.set_print_mode_enabled(False)
            panel.set_limit_value(1)
            panel.set_limit_enabled(False)

        self.update_label_size_text()
        self.update_max_count_label()
        self.editor.canvas.set_label_size(self.label_size)
        self.editor.aggregate_editor.set_label_size(self.label_size)
        self.editor._update_preview()

    # === Data ===

    def set_sscc_data(self, data: dict):
        self.sscc_data = data
        self.update_info_page()
        self.update_preview()
        self.validate_limit()

    def update_info_page(self):
        """Обновление страницы EAN-13 (инфо)."""
        if not self.sscc_data:
            self.editor.info_page.set_data(None)
            return

        gtin_groups = {}
        seen_sscc = set()

        for sscc, data in self.sscc_data.items():
            gtin = data.get("gtin", "UNKNOWN")
            article = data.get("article", "UNKNOWN")

            if gtin not in gtin_groups:
                gtin_groups[gtin] = {
                    "gtin": gtin,
                    "article": article,
                    "sscc_list": [],
                }

            if sscc not in seen_sscc:
                seen_sscc.add(sscc)
                gtin_groups[gtin]["sscc_list"].append(
                    {"sscc": sscc, "code_count": len(data["codes"])}
                )

        first_gtin = list(gtin_groups.values())[0] if gtin_groups else None
        self.editor.info_page.set_data(first_gtin)

    def select_gtin(self, gtin_text: str):
        """Выбор GTIN — обновляем EAN-13 страницу."""
        gtin_groups = {}
        seen_sscc = set()

        for sscc, data in self.sscc_data.items():
            gtin = data.get("gtin", "UNKNOWN")
            article = data.get("article", "UNKNOWN")

            if gtin not in gtin_groups:
                gtin_groups[gtin] = {
                    "gtin": gtin,
                    "article": article,
                    "sscc_list": [],
                }

            if sscc not in seen_sscc:
                seen_sscc.add(sscc)
                gtin_groups[gtin]["sscc_list"].append(
                    {"sscc": sscc, "code_count": len(data["codes"])}
                )

        gtin_data = gtin_groups.get(gtin_text)
        if not gtin_data:
            for group in gtin_groups.values():
                if group.get("article") == gtin_text:
                    gtin_data = group
                    break

        if gtin_data:
            self.editor.info_page.set_data(gtin_data)

    # === Preview ===

    def update_preview(self):
        """Обновление предпросмотра этикетки с реальными данными из Excel."""
        first_data = None
        first_code = None
        for data in self.sscc_data.values():
            if data["codes"]:
                first_data = data
                first_code = data["codes"][0]
                break

        if not first_code:
            return

        if self.sscc_data:
            idx = 1
            for sscc, data in self.sscc_data.items():
                for code in data["codes"]:
                    code["global_index"] = idx
                    idx += 1

        panel = self.editor.right_panel

        code_info = dict(first_code)
        if first_data:
            code_info["article"] = first_data.get("article", "UNKNOWN")
            code_info["gtin"] = first_data.get("gtin", "UNKNOWN")

        config = {
            "bottom_field_type": panel.bottom_field_type,
            "code_info": code_info,
            "label_size": self.label_size,
            "gtin_size": panel.gtin_size,
            "article_size": panel.article_size,
            "index_size": panel.index_size,
            "quiet_zone_mm": panel.quiet_zone,
            "bottom_field_mm": panel.bottom_field,
        }
        self.editor.canvas.update_config(config)

    # === Config ===

    def get_template_config(self) -> dict:
        panel = self.editor.right_panel
        n = panel.label_size_mm

        # === АВТО-ОТСТУПЫ ===
        auto_margin = max(2, min(n * 0.1, 10))

        # === ЗАЗОР МЕЖДУ ЭТИКЕТКАМИ (мм) ===
        gap_mm = getattr(panel, "gap_mm", 2)

        # === РАСЧЁТ СЕТКИ С УЧЁТОМ ЗАЗОРОВ ===
        available_w = max(1, panel.paper_width_mm - 2 * auto_margin)
        available_h = max(1, panel.paper_height_mm - 2 * auto_margin)

        if gap_mm > 0:
            cols = max(1, int((available_w + gap_mm) / (n + gap_mm)))
            rows = max(1, int((available_h + gap_mm) / (n + gap_mm)))
        else:
            cols = max(1, int(available_w / n))
            rows = max(1, int(available_h / n))

        # ИСПРАВЛЕНО: берём print_mode НАПРЯМУЮ из панели!
        current_print_mode = panel.print_mode_data

        # === ДОБАВЛЕНО: split_threshold из main_window ===
        # Берём из main_window, если доступен
        split_threshold = 0
        main_window = self.editor.window()
        if hasattr(main_window, "spin_split_threshold"):
            split_threshold = main_window.spin_split_threshold.value()

        return {
            "elements": self.editor.canvas.get_elements(),
            "aggregate_elements": self.editor.aggregate_editor.get_elements(),
            "sscc_size": panel.sscc_size,
            "label_size": (panel.dm_label_size_mm, panel.dm_label_size_mm),
            "label_size_mm": panel.dm_label_size_mm,
            "aggregate_label_size_mm": panel.agg_label_size_mm,
            "page_limit": panel.limit,
            "print_mode": current_print_mode,
            "aggregate_size_mm": panel.aggregate_size,
            "dm_size_mm": panel.dm_size,
            "quiet_zone_mm": panel.quiet_zone,
            "bottom_field_mm": panel.bottom_field,
            "gtin_size": panel.gtin_size,
            "article_size": panel.article_size,
            "page_width_mm": panel.paper_width_mm,
            "page_height_mm": panel.paper_height_mm,
            "margins_mm": auto_margin,
            "gap_mm": gap_mm,
            "cols_per_page": 1 if current_print_mode == "single" else cols,
            "rows_per_page": 1 if current_print_mode == "single" else rows,
            "single_mode_type": getattr(panel, "single_mode_type", "with_elements"),
            "bottom_field_type": panel.bottom_field_type,
            "index_size": panel.index_size,
            # === ДОБАВЛЕНО ===
            "split_threshold": split_threshold,
        }
