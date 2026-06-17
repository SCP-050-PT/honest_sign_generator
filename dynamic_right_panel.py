"""
Динамическая правая панель настроек.
ИСПРАВЛЕНО: размеры этикеток разделены — DM на стр.2, Агрегат на стр.3.
ИСПРАВЛЕНО: Quiet Zone min=0, подписи шрифтов с tooltips.
ДОБАВЛЕНО: динамический расчёт макс. размера DM с учётом текста.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QStackedWidget,
    QButtonGroup,
    QRadioButton,
)
from PyQt6.QtCore import pyqtSignal


class DynamicRightPanel(QWidget):
    """Динамическая панель настроек."""

    settings_changed = pyqtSignal()

    def __init__(self, parent_editor):
        super().__init__()
        self.editor = parent_editor
        self.setMinimumWidth(330)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 12, 10, 12)

        # === ОБЩИЕ НАСТРОЙКИ (видны всегда) ===
        self.common_group = QGroupBox("Общие настройки")
        common_layout = QVBoxLayout(self.common_group)
        common_layout.setSpacing(8)

        # === РАЗМЕР БУМАГИ ===
        paper_layout = QVBoxLayout()
        paper_label = QLabel("Размер бумаги (мм)")
        paper_layout.addWidget(paper_label)

        paper_inputs = QHBoxLayout()
        self.spin_paper_w = QSpinBox()
        self.spin_paper_w.setRange(50, 500)
        self.spin_paper_w.setValue(210)
        self.spin_paper_w.setSuffix(" мм")
        self.spin_paper_w.valueChanged.connect(self._emit_settings_changed)
        paper_inputs.addWidget(QLabel("Ш:"))
        paper_inputs.addWidget(self.spin_paper_w)

        self.spin_paper_h = QSpinBox()
        self.spin_paper_h.setRange(50, 500)
        self.spin_paper_h.setValue(297)
        self.spin_paper_h.setSuffix(" мм")
        self.spin_paper_h.valueChanged.connect(self._emit_settings_changed)
        paper_inputs.addWidget(QLabel("В:"))
        paper_inputs.addWidget(self.spin_paper_h)

        paper_layout.addLayout(paper_inputs)

        self.lbl_paper_info = QLabel("210×297 мм (A4)")
        self.lbl_paper_info.setStyleSheet("color: #666; font-size: 10px;")
        paper_layout.addWidget(self.lbl_paper_info)
        common_layout.addLayout(paper_layout)

        # === АВТО-ОТСТУПЫ ===
        self.lbl_auto_margin = QLabel("Отступы: авто (2–10 мм)")
        self.lbl_auto_margin.setStyleSheet("color: #2196F3; font-size: 10px;")
        self.lbl_auto_margin.setToolTip(
            "Отступы рассчитываются автоматически в зависимости от размера этикетки"
        )
        common_layout.addWidget(self.lbl_auto_margin)

        # Режим печати
        mode_layout = QVBoxLayout()
        mode_label = QLabel("Режим печати")
        mode_layout.addWidget(mode_label)

        self.cmb_print_mode = QComboBox()
        self.cmb_print_mode.addItem("🖨️ Заполнение листа (сетка)", "fill")
        self.cmb_print_mode.addItem("📄 Один код на лист", "single")
        self.cmb_print_mode.currentIndexChanged.connect(self._emit_settings_changed)
        mode_layout.addWidget(self.cmb_print_mode)

        common_layout.addLayout(mode_layout)

        self.cmb_single_mode = QComboBox()
        self.cmb_single_mode.addItem("📄 С элементами", "with_elements")
        self.cmb_single_mode.addItem("🔲 Только DM+QZ", "dm_only")
        self.cmb_single_mode.currentIndexChanged.connect(self._emit_settings_changed)
        mode_layout.addWidget(self.cmb_single_mode)

        # Количество на лист
        limit_layout = QVBoxLayout()
        limit_label = QLabel("Количество на лист")
        limit_layout.addWidget(limit_label)

        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(1, 1000)
        self.spin_limit.setValue(42)
        self.spin_limit.setSuffix(" шт.")
        self.spin_limit.valueChanged.connect(self._emit_settings_changed)
        limit_layout.addWidget(self.spin_limit)

        self.lbl_validation = QLabel("")
        self.lbl_validation.setWordWrap(True)
        self.lbl_validation.setStyleSheet("font-size: 10px;")
        limit_layout.addWidget(self.lbl_validation)
        common_layout.addLayout(limit_layout)

        layout.addWidget(self.common_group)

        # === СТЕК НАСТРОЕК ===
        self.stack = QStackedWidget()

        # Страница 0: Пустая
        self.page_empty = QWidget()
        self.stack.addWidget(self.page_empty)

        # Страница 1: Настройки Data Matrix
        self.page_dm = self._create_dm_page()
        self.stack.addWidget(self.page_dm)

        # Страница 2: Настройки Агрегата
        self.page_aggregate = self._create_aggregate_page()
        self.stack.addWidget(self.page_aggregate)

        # Скрываем все страницы кроме первой
        self.page_dm.setVisible(False)
        self.page_aggregate.setVisible(False)

        layout.addWidget(self.stack, stretch=1)


    def _create_dm_page(self) -> QWidget:
        """Создание страницы настроек Data Matrix."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        dm_group = QGroupBox("Настройка Data Matrix")
        dm_layout = QVBoxLayout(dm_group)
        dm_layout.setSpacing(8)

        # === РАЗМЕР ЭТИКЕТКИ DM ===
        label_size_layout = QVBoxLayout()
        label_size_label = QLabel("Размер этикетки DM:")
        label_size_layout.addWidget(label_size_label)

        self.spin_dm_label_size = QSpinBox()
        self.spin_dm_label_size.setRange(10, 100)
        self.spin_dm_label_size.setValue(30)
        self.spin_dm_label_size.setSuffix(" мм")
        self.spin_dm_label_size.valueChanged.connect(self._on_dm_label_size_changed)
        label_size_layout.addWidget(self.spin_dm_label_size)

        self.lbl_dm_label_info = QLabel("30×30 мм | На лист A4: ~42 шт.")
        self.lbl_dm_label_info.setStyleSheet("color: #666; font-size: 10px;")
        label_size_layout.addWidget(self.lbl_dm_label_info)
        dm_layout.addLayout(label_size_layout)

        # === РАЗМЕР DM + МАКС ===
        dm_size_layout = QHBoxLayout()
        dm_size_layout.addWidget(QLabel("Размер DM:"))

        self.spin_dm_size = QSpinBox()
        self.spin_dm_size.setRange(5, 99)
        self.spin_dm_size.setValue(16)
        self.spin_dm_size.setSuffix(" мм")
        self.spin_dm_size.valueChanged.connect(self._on_dm_size_changed)
        dm_size_layout.addWidget(self.spin_dm_size)

        # === ДОБАВЛЕНО: label макс. DM ===
        self.lbl_dm_max = QLabel("Макс: --")
        self.lbl_dm_max.setStyleSheet("color: #FF9800; font-size: 10px;")
        dm_size_layout.addWidget(self.lbl_dm_max)

        dm_layout.addLayout(dm_size_layout)

        # Quiet Zone
        qz_layout = QHBoxLayout()
        qz_label = QLabel("Quiet Zone:")
        qz_label.setToolTip(
            "Тихая зона (отступ) вокруг Data Matrix.\n"
            "0 = без отступа, код занимает всю этикетку.\n"
            "Рекомендуется 2 мм для корректного сканирования."
        )
        qz_layout.addWidget(qz_label)
        self.spin_quiet_zone = QSpinBox()
        self.spin_quiet_zone.setRange(0, 5)
        self.spin_quiet_zone.setValue(2)
        self.spin_quiet_zone.setSuffix(" мм")
        self.spin_quiet_zone.setToolTip(
            "0 = без Quiet Zone\n"
            "2 = стандартный отступ (рекомендуется)\n"
            "5 = максимальный отступ"
        )
        self.spin_quiet_zone.valueChanged.connect(self._emit_settings_changed)
        qz_layout.addWidget(self.spin_quiet_zone)
        dm_layout.addLayout(qz_layout)

        # === НИЖНЕЕ ПОЛЕ DM — радио-кнопки ===
        bottom_group = QGroupBox("Нижнее поле DM")
        bottom_layout = QVBoxLayout(bottom_group)
        bottom_layout.setSpacing(6)

        self.bottom_field_group = QButtonGroup(self)

        self.radio_none = QRadioButton("Ничего")
        self.radio_gtin = QRadioButton("GTIN")
        self.radio_index = QRadioButton("№пп")
        self.radio_article = QRadioButton("Артикул")

        self.bottom_field_group.addButton(self.radio_none, 0)
        self.bottom_field_group.addButton(self.radio_gtin, 1)
        self.bottom_field_group.addButton(self.radio_index, 2)
        self.bottom_field_group.addButton(self.radio_article, 3)

        self.radio_index.setChecked(True)

        self.bottom_field_group.idClicked.connect(self._emit_settings_changed)

        bottom_layout.addWidget(self.radio_none)
        bottom_layout.addWidget(self.radio_gtin)
        bottom_layout.addWidget(self.radio_index)
        bottom_layout.addWidget(self.radio_article)

        sizes_hint = QLabel("пт = размер шрифта текста под Data Matrix")
        sizes_hint.setStyleSheet("color: #888; font-size: 9px; padding-bottom: 4px;")
        bottom_layout.addWidget(sizes_hint)

        sizes_layout = QHBoxLayout()

        # GTIN размер
        gtin_size_layout = QVBoxLayout()
        gtin_lbl = QLabel("GTIN:")
        gtin_lbl.setToolTip("Размер шрифта для текста GTIN под кодом")
        gtin_size_layout.addWidget(gtin_lbl)
        self.spin_gtin_size = QSpinBox()
        self.spin_gtin_size.setRange(5, 16)
        self.spin_gtin_size.setValue(8)
        self.spin_gtin_size.setSuffix(" пт")
        self.spin_gtin_size.setToolTip("Размер шрифта GTIN (5–16 пт)")
        self.spin_gtin_size.valueChanged.connect(self._emit_settings_changed)
        gtin_size_layout.addWidget(self.spin_gtin_size)
        sizes_layout.addLayout(gtin_size_layout)

        # №пп размер
        index_size_layout = QVBoxLayout()
        idx_lbl = QLabel("№пп:")
        idx_lbl.setToolTip("Размер шрифта для номера по порядку")
        index_size_layout.addWidget(idx_lbl)
        self.spin_index_size = QSpinBox()
        self.spin_index_size.setRange(5, 16)
        self.spin_index_size.setValue(5)  # ИЗМЕНЕНО: дефолт 5пт для макс. DM
        self.spin_index_size.setSuffix(" пт")
        self.spin_index_size.setToolTip("Размер шрифта номера (5–16 пт)")
        self.spin_index_size.valueChanged.connect(self._emit_settings_changed)
        index_size_layout.addWidget(self.spin_index_size)
        sizes_layout.addLayout(index_size_layout)

        # Артикул размер
        article_size_layout = QVBoxLayout()
        art_lbl = QLabel("Артикул:")
        art_lbl.setToolTip("Размер шрифта для текста артикула")
        article_size_layout.addWidget(art_lbl)
        self.spin_article_size = QSpinBox()
        self.spin_article_size.setRange(5, 16)
        self.spin_article_size.setValue(8)
        self.spin_article_size.setSuffix(" пт")
        self.spin_article_size.setToolTip("Размер шрифта артикула (5–16 пт)")
        self.spin_article_size.valueChanged.connect(self._emit_settings_changed)
        article_size_layout.addWidget(self.spin_article_size)
        sizes_layout.addLayout(article_size_layout)

        bottom_layout.addLayout(sizes_layout)
        dm_layout.addWidget(bottom_group)

        layout.addWidget(dm_group)
        return page

    def _create_aggregate_page(self) -> QWidget:
        """Создание страницы настроек Агрегата."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        agg_group = QGroupBox("Настройка агрегирующего ШК")
        agg_layout = QVBoxLayout(agg_group)
        agg_layout.setSpacing(8)

        agg_label_layout = QVBoxLayout()
        agg_label_label = QLabel("Размер этикетки агрегата:")
        agg_label_layout.addWidget(agg_label_label)

        self.spin_agg_label_size = QSpinBox()
        self.spin_agg_label_size.setRange(10, 100)
        self.spin_agg_label_size.setValue(30)
        self.spin_agg_label_size.setSuffix(" мм")
        self.spin_agg_label_size.valueChanged.connect(self._on_agg_label_size_changed)
        agg_label_layout.addWidget(self.spin_agg_label_size)

        self.lbl_agg_label_info = QLabel("30×30 мм")
        self.lbl_agg_label_info.setStyleSheet("color: #666; font-size: 10px;")
        agg_label_layout.addWidget(self.lbl_agg_label_info)
        agg_layout.addLayout(agg_label_layout)

        agg_size_layout = QHBoxLayout()
        agg_size_layout.addWidget(QLabel("Размер ШК:"))
        self.spin_agg_size = QSpinBox()
        self.spin_agg_size.setRange(20, 98)
        self.spin_agg_size.setValue(60)
        self.spin_agg_size.setSuffix(" мм")
        self.spin_agg_size.valueChanged.connect(self._on_agg_size_changed)
        agg_size_layout.addWidget(self.spin_agg_size)
        agg_layout.addLayout(agg_size_layout)

        sscc_layout = QHBoxLayout()
        sscc_layout.addWidget(QLabel("SSCC:"))
        self.spin_sscc_size = QSpinBox()
        self.spin_sscc_size.setRange(6, 16)
        self.spin_sscc_size.setValue(9)
        self.spin_sscc_size.setSuffix(" пт")
        self.spin_sscc_size.setToolTip("Размер шрифта текста SSCC")
        self.spin_sscc_size.valueChanged.connect(self._emit_settings_changed)
        sscc_layout.addWidget(self.spin_sscc_size)
        agg_layout.addLayout(sscc_layout)

        layout.addWidget(agg_group)
        return page

    # === ДОБАВЛЕНО: динамический расчёт макс. DM ===
    def _calc_dm_max(self) -> float:
        """Рассчитать максимальный размер DM с учётом текста."""
        label_size = self.spin_dm_label_size.value()
        margin = 0.2
        gap = 0.2

        # Высота поля номера (№пп) — если не "Ничего"
        bottom_type = self.bottom_field_type
        if bottom_type == "none":
            number_height = 0
        else:
            number_height = max(self.spin_index_size.value() * 0.3, 1.0)

        # GTIN и Артикул рисуются в оставшемся пространстве под DM
        # Не уменьшаем DM ради них — они сожмутся сами
        text_height = 0

        # DM = этикетка - отступы - номер - зазор
        dm_max = label_size - margin * 2 - number_height - text_height - gap

        return max(5, min(dm_max, label_size - 0.5))

    def _update_dm_max(self):
        """Обновить label макс. DM и ограничить spin."""
        dm_max = self._calc_dm_max()

        self.lbl_dm_max.setText(f"Макс: {dm_max:.1f} мм")

        # Ограничиваем spin_dm_size
        current_max = self.spin_dm_size.maximum()
        if current_max != int(dm_max):
            self.spin_dm_size.setMaximum(int(dm_max))

        # Если текущее значение больше максимума — уменьшаем
        current = self.spin_dm_size.value()
        if current > dm_max:
            self.spin_dm_size.setValue(int(dm_max))

        return dm_max

    def _on_dm_label_size_changed(self):
        self._update_dm_max()  # ДОБАВЛЕНО
        self._update_dm_label_info()
        self._emit_settings_changed()

    def _on_dm_size_changed(self):
        self._emit_settings_changed()

    def _on_agg_label_size_changed(self):
        n = self.spin_agg_label_size.value()
        self.spin_agg_size.setMaximum(max(20, n - 2))
        if self.spin_agg_size.value() > n - 2:
            self.spin_agg_size.setValue(n - 2)
        self._update_agg_label_info()
        self._emit_settings_changed()

    def _on_agg_size_changed(self):
        n = self.spin_agg_label_size.value()
        if self.spin_agg_size.value() > n - 2:
            self.spin_agg_size.setValue(n - 2)
        self._emit_settings_changed()

    def _update_dm_label_info(self):
        n = self.spin_dm_label_size.value()
        pw = self.spin_paper_w.value()
        ph = self.spin_paper_h.value()

        auto_margin = max(2, min(n * 0.1, 10))
        available_w = pw - 2 * auto_margin
        available_h = ph - 2 * auto_margin

        cols = max(1, int(available_w / n))
        rows = max(1, int(available_h / n))
        max_count = cols * rows

        self.lbl_dm_label_info.setText(f"{n}×{n} мм | На лист: ~{max_count} шт.")
        self.lbl_auto_margin.setText(f"Отступы: авто ({auto_margin:.1f} мм)")

    def _update_agg_label_info(self):
        n = self.spin_agg_label_size.value()
        self.lbl_agg_label_info.setText(f"{n}×{n} мм")

    def _emit_settings_changed(self):
        w = self.spin_paper_w.value()
        h = self.spin_paper_h.value()
        if w == 210 and h == 297:
            self.lbl_paper_info.setText("210×297 мм (A4)")
        elif w == 148 and h == 210:
            self.lbl_paper_info.setText("148×210 мм (A5)")
        elif w == 105 and h == 148:
            self.lbl_paper_info.setText("105×148 мм (A6)")
        else:
            self.lbl_paper_info.setText(f"{w}×{h} мм (кастом)")

        self._update_dm_label_info()
        self._update_dm_max()  # ДОБАВЛЕНО
        self.settings_changed.emit()

    def set_page(self, page_index: int):
        """Переключить видимую страницу настроек."""
        self.stack.setCurrentIndex(page_index)
        # Явно управляем видимостью каждой страницы
        for i in range(self.stack.count()):
            self.stack.widget(i).setVisible(i == page_index)

    # --- Геттеры ---

    @property
    def dm_label_size_mm(self):
        return self.spin_dm_label_size.value()

    @property
    def agg_label_size_mm(self):
        return self.spin_agg_label_size.value()

    @property
    def label_size_mm(self):
        return self.dm_label_size_mm

    @property
    def margins_mm(self):
        n = self.dm_label_size_mm
        return max(2, min(n * 0.1, 10))

    @property
    def limit(self):
        return self.spin_limit.value()

    @property
    def print_mode_data(self):
        return self.cmb_print_mode.currentData()

    @property
    def print_mode_index(self):
        return self.cmb_print_mode.currentIndex()

    @property
    def single_mode_type(self):
        return self.cmb_single_mode.currentData()

    @property
    def paper_width_mm(self):
        return self.spin_paper_w.value()

    @property
    def paper_height_mm(self):
        return self.spin_paper_h.value()

    @property
    def dm_size(self):
        return self.spin_dm_size.value()

    @property
    def quiet_zone(self):
        return self.spin_quiet_zone.value()

    @property
    def bottom_field(self):
        return 3

    @property
    def gtin_size(self):
        return self.spin_gtin_size.value()

    @property
    def article_size(self):
        return self.spin_article_size.value()

    @property
    def bottom_field_type(self) -> str:
        btn_id = self.bottom_field_group.checkedId()
        mapping = {0: "none", 1: "gtin", 2: "index", 3: "article"}
        return mapping.get(btn_id, "index")

    @property
    def index_size(self) -> int:
        return self.spin_index_size.value()

    @property
    def aggregate_size(self):
        return self.spin_agg_size.value()

    @property
    def hri_size(self):
        return 10

    @property
    def box_number_size(self):
        return 14

    @property
    def sscc_size(self):
        return self.spin_sscc_size.value()

    @property
    def show_hri(self):
        return True

    @property
    def show_box_number(self):
        return True

    @property
    def show_sscc(self):
        return True

    @property
    def show_serial_agg(self):
        return False

    @property
    def serial_agg_size(self):
        return 10

    # --- Сеттеры ---

    def set_print_mode_index(self, index: int):
        self.cmb_print_mode.setCurrentIndex(index)

    def set_print_mode_enabled(self, enabled: bool):
        self.cmb_print_mode.setEnabled(enabled)

    def set_limit_value(self, value: int):
        self.spin_limit.setValue(value)

    def set_limit_enabled(self, enabled: bool):
        self.spin_limit.setEnabled(enabled)

    def set_limit_maximum(self, maximum: int):
        self.spin_limit.setMaximum(maximum)

    def set_max_count_text(self, text: str):
        pass

    def set_validation_text(self, text: str, style: str = ""):
        self.lbl_validation.setText(text)
        if style:
            self.lbl_validation.setStyleSheet(style)

    def set_show_gtin(self, checked: bool):
        pass

    def set_show_serial(self, checked: bool):
        pass
