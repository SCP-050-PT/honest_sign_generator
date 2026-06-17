"""
Main application window for Honest Sign Generator (GTIN version).
ДОБАВЛЕНО: режим "Шаблон PDF" с меню Режим.
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QMenuBar,
    QMenu,
    QSplitter,
    QFrame,
    QListWidget,
    QGroupBox,
    QTabWidget,
    QDialog,
    QCheckBox,
    QLineEdit,
    QSpinBox,
    QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.excel_parser import ExcelParser
from core.pdf import PDFGenerator
from core.pdf.template_overlay import TemplateOverlayGenerator
from core.file_manager import FileManager
from config import UPLOADS_DIR, OUTPUT_DIR
from core.template_manager import TemplateManager
from .template_editor import TemplateEditor
from .components.template_pdf_editor import TemplatePdfEditor
from .components.template_pdf_toolbar import TemplatePdfToolbar
from .components.template_pdf_settings_panel import TemplatePdfSettingsPanel
from .dialogs.about_dialog import AboutDialog
from .dialogs.progress_dialog import ProgressDialog
from .threads import ExcelLoadThread, PDFGenerationThread


class MainWindow(QMainWindow):
    """Главное окно приложения."""

    # Режимы работы
    MODE_STANDARD = "standard"
    MODE_TEMPLATE = "template"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Генератор Data Matrix — Честный ЗНАК")
        self.setMinimumSize(1400, 900)

        self.current_file = None
        self.sscc_data = {}
        self.file_manager = FileManager(UPLOADS_DIR, OUTPUT_DIR)
        self.output_dir = OUTPUT_DIR
        self.template_manager = TemplateManager()

        # Текущий режим
        self.current_mode = self.MODE_STANDARD

        # Путь к PDF-шаблону (для режима шаблона)
        self.template_pdf_path: Path = None

        self._excel_thread = None
        self._pdf_thread = None
        self._progress_dialog = None

        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # === СТЕК РЕДАКТОРОВ ===
        self.editor_stack = QStackedWidget()

        # Стандартный редактор
        self.template_editor = TemplateEditor()
        self.editor_stack.addWidget(self.template_editor)

        # Редактор шаблона PDF
        self.template_pdf_editor = TemplatePdfEditor()
        self.template_pdf_editor.element_moved.connect(self._on_template_element_moved)
        self.template_pdf_editor.zoom_changed.connect(self._on_template_zoom_changed)
        self.editor_stack.addWidget(self.template_pdf_editor)

        # Toolbar для редактора шаблона
        self.template_pdf_toolbar = TemplatePdfToolbar()
        self.template_pdf_toolbar.zoom_in.connect(self._on_zoom_in)
        self.template_pdf_toolbar.zoom_out.connect(self._on_zoom_out)
        self.template_pdf_toolbar.zoom_reset.connect(self._on_zoom_reset)
        self.template_pdf_toolbar.zoom_changed.connect(self._on_zoom_slider_changed)
        self.template_pdf_toolbar.setVisible(False)

        # Панель настроек DM для режима шаблона
        self.template_pdf_settings = TemplatePdfSettingsPanel()
        self.template_pdf_settings.setVisible(False)
        self.template_pdf_settings.settings_changed.connect(
            self._on_template_pdf_settings_changed
        )

        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Центральная область: toolbar + editor + settings
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(self.template_pdf_toolbar)
        center_layout.addWidget(self.editor_stack)
        center_layout.addWidget(self.template_pdf_settings)  # ← СНИЗУ

        splitter.addWidget(center_container)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1000])
        main_layout.addWidget(splitter, stretch=1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к работе. Загрузите Excel")

        self._setup_menu()

        # Устанавливаем стандартный режим
        self.set_mode(self.MODE_STANDARD)

        # Подключаем изменения настроек DM для синхронизации
        self.template_editor.right_panel.settings_changed.connect(
            self._on_right_panel_settings_changed
        )

    def _create_left_panel(self) -> QFrame:
        panel = QFrame()
        panel.setFrameStyle(QFrame.Shape.StyledPanel)
        panel.setFixedWidth(320)

        layout = QVBoxLayout(panel)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        # === ЗАГРУЗКА PDF-ШАБЛОНА (только для режима шаблона) ===
        self.btn_load_template_pdf = QPushButton("📄 Загрузить PDF-шаблон")
        self.btn_load_template_pdf.setFixedHeight(36)
        self.btn_load_template_pdf.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        self.btn_load_template_pdf.clicked.connect(self._load_template_pdf)
        self.btn_load_template_pdf.setVisible(False)
        layout.addWidget(self.btn_load_template_pdf)

        # === ЗАГРУЗКА EXCEL ===
        self.btn_load = QPushButton("📁 Загрузить Excel")
        self.btn_load.setFixedHeight(36)
        self.btn_load.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.btn_load.clicked.connect(self._load_excel)
        layout.addWidget(self.btn_load)

        self.lbl_filename = QLabel("Файл не выбран")
        self.lbl_filename.setStyleSheet(
            "color: #666; font-size: 11px; padding-left: 5px;"
        )
        self.lbl_filename.setWordWrap(True)
        layout.addWidget(self.lbl_filename)

        # === ГЕНЕРАЦИЯ PDF ===
        self.btn_generate = QPushButton("📄 Сгенерировать PDF")
        self.btn_generate.setFixedHeight(36)
        self.btn_generate.setEnabled(False)
        self.btn_generate.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #ccc; color: #888; }
        """)
        self.btn_generate.clicked.connect(self._generate_pdf)
        layout.addWidget(self.btn_generate)

        # === ГАЛКА "Генерировать с агрегатами" ===
        self.chk_with_aggregates = QCheckBox("📦 Генерировать с агрегатами")
        self.chk_with_aggregates.setChecked(True)
        self.chk_with_aggregates.setStyleSheet(
            "font-size: 11px; padding-left: 5px; color: #333;"
        )
        layout.addWidget(self.chk_with_aggregates)

        # === РАЗБИВКА PDF ===
        split_group = QGroupBox("Разбивка PDF")
        split_group.setStyleSheet("""
            QGroupBox {
                font-size: 10px;
                font-weight: bold;
                color: #555;
                border: 1px solid #ccc;
                border-radius: 4px;
                margin-top: 6px;
                padding-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)
        split_layout = QVBoxLayout(split_group)
        split_layout.setSpacing(4)
        split_layout.setContentsMargins(8, 4, 8, 8)

        split_hbox = QHBoxLayout()
        split_hbox.setSpacing(6)

        self.spin_split_threshold = QSpinBox()
        self.spin_split_threshold.setRange(0, 50000)
        self.spin_split_threshold.setValue(0)
        self.spin_split_threshold.setSingleStep(1000)
        self.spin_split_threshold.setSpecialValueText("Без разбивки")
        self.spin_split_threshold.setStyleSheet("""
            QSpinBox {
                font-size: 10px;
                padding: 2px 4px;
                min-width: 80px;
            }
        """)
        self.spin_split_threshold.setToolTip(
            "0 = один PDF-файл"
            "3000 = разбивка по 3000 КИЗов на файл"
        )

        split_hbox.addWidget(QLabel("По:"))
        split_hbox.addWidget(self.spin_split_threshold)
        split_hbox.addWidget(QLabel("КИЗов"))
        split_hbox.addStretch()

        split_layout.addLayout(split_hbox)

        self.lbl_split_info = QLabel("0 = без разбивки (один файл)")
        self.lbl_split_info.setStyleSheet("color: #888; font-size: 9px;")
        self.lbl_split_info.setWordWrap(True)
        split_layout.addWidget(self.lbl_split_info)

        self.spin_split_threshold.valueChanged.connect(self._on_split_threshold_changed)

        layout.addWidget(split_group)

        self.lbl_pdf_info = QLabel("—")
        self.lbl_pdf_info.setStyleSheet(
            "color: #666; font-size: 11px; padding-left: 5px;"
        )
        self.lbl_pdf_info.setWordWrap(True)
        layout.addWidget(self.lbl_pdf_info)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #ddd;")
        layout.addWidget(line)

        # === ВКЛАДКИ: Артикулы / SSCC / КИЗы ===
        self.tabs_nav = QTabWidget()
        self.tabs_nav.setDocumentMode(True)

        self.tab_gtin = QListWidget()
        self.tab_gtin.itemClicked.connect(self._on_gtin_selected)
        self.tabs_nav.addTab(self.tab_gtin, "📦 Артикулы (GTIN)")

        self.tab_sscc = QListWidget()
        self.tab_sscc.itemClicked.connect(self._on_sscc_selected)
        self.tabs_nav.addTab(self.tab_sscc, "📋 SSCC (короба)")

        self.tab_codes = QListWidget()
        self.tab_codes.itemClicked.connect(self._on_code_selected)
        self.tabs_nav.addTab(self.tab_codes, "🏷️ КИЗы")

        self.tabs_nav.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #ccc; }
            QTabBar::tab {
                padding: 6px 10px;
                font-size: 10px;
                background: #f0f0f0;
            }
            QTabBar::tab:selected {
                background: #2196F3;
                color: white;
                font-weight: bold;
            }
        """)

        layout.addWidget(self.tabs_nav)

        # === СВОДКА ===
        self.lbl_summary = QLabel("—")
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setStyleSheet("color: #333; font-size: 11px;")
        layout.addWidget(self.lbl_summary)

        layout.addStretch()
        return panel

    def _setup_menu(self):
        menubar = self.menuBar()

        # === ФАЙЛ ===
        file_menu = menubar.addMenu("Файл")

        open_action = QAction("Открыть Excel...", self)
        open_action.triggered.connect(self._load_excel)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # === ПАРАМЕТРЫ ===
        params_menu = menubar.addMenu("Параметры")

        output_dir_action = QAction("Место сохранения PDF...", self)
        output_dir_action.triggered.connect(self._select_output_dir)
        params_menu.addAction(output_dir_action)
        params_menu.addSeparator()

        save_template_action = QAction("💾 Сохранить шаблон...", self)
        save_template_action.triggered.connect(self._save_template)
        params_menu.addAction(save_template_action)

        load_template_action = QAction("📂 Загрузить шаблон...", self)
        load_template_action.triggered.connect(self._load_template)
        params_menu.addAction(load_template_action)

        # === РЕЖИМ ===
        self.mode_menu = menubar.addMenu("Режим")

        self.mode_action_group = QActionGroup(self)
        self.mode_action_group.setExclusive(True)

        self.action_standard = QAction("📝 Стандартный", self)
        self.action_standard.setCheckable(True)
        self.action_standard.setChecked(True)
        self.action_standard.triggered.connect(lambda: self.set_mode(self.MODE_STANDARD))
        self.mode_action_group.addAction(self.action_standard)
        self.mode_menu.addAction(self.action_standard)

        self.mode_menu.addSeparator()

        self.action_template = QAction("📄 Шаблон PDF", self)
        self.action_template.setCheckable(True)
        self.action_template.triggered.connect(lambda: self.set_mode(self.MODE_TEMPLATE))
        self.mode_action_group.addAction(self.action_template)
        self.mode_menu.addAction(self.action_template)

        # === СПРАВКА ===
        help_menu = menubar.addMenu("Справка")

        about_action = QAction("О программе", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def set_mode(self, mode: str):
        """Переключить режим работы."""
        self.current_mode = mode
        is_template = (mode == self.MODE_TEMPLATE)

        # Обновляем меню
        self.action_standard.setChecked(not is_template)
        self.action_template.setChecked(is_template)

        # Переключаем редактор
        if is_template:
            self.editor_stack.setCurrentIndex(1)
            self.template_pdf_toolbar.setVisible(True)
            self.template_pdf_settings.setVisible(True)
            self.setWindowTitle("Генератор Data Matrix — Честный ЗНАК [Шаблон PDF]")
        else:
            self.editor_stack.setCurrentIndex(0)
            self.template_pdf_toolbar.setVisible(False)
            self.template_pdf_settings.setVisible(False)
            self.setWindowTitle("Генератор Data Matrix — Честный ЗНАК")

        # Левая панель
        self.btn_load_template_pdf.setVisible(is_template)
        self.chk_with_aggregates.setVisible(not is_template)

        # Кнопка генерации
        if is_template:
            self.btn_generate.setText("🖨️ Наложить DM на шаблон")
        else:
            self.btn_generate.setText("📄 Сгенерировать PDF")

        # Правая панель — настройки
        if hasattr(self, 'template_editor') and self.template_editor.right_panel:
            panel = self.template_editor.right_panel

            # В режиме шаблона скрываем общие настройки и агрегат
            if is_template:
                panel.common_group.setVisible(False)
                panel.page_aggregate.setVisible(False)
                # Оставляем только настройки DM
                panel.set_page(1)  # Страница DM
            else:
                panel.common_group.setVisible(True)
                panel.page_aggregate.setVisible(True)
                panel.set_page(0)

        # Если переключаемся в режим шаблона и шаблон уже загружен — синхронизируем
        if is_template and self.template_pdf_path:
            self._sync_dm_settings_to_template_editor()

        self._update_pdf_info()
        self.status_bar.showMessage(
            f"Режим: {'Шаблон PDF' if is_template else 'Стандартный'}"
        )

    def _on_right_panel_settings_changed(self):
        """Обработчик изменения настроек в правой панели."""
        # Если в режиме шаблона — синхронизируем настройки DM
        if self.current_mode == self.MODE_TEMPLATE and self.template_pdf_path:
            self._sync_dm_settings_to_template_editor()

        # Обновляем инфо о PDF
        self._update_pdf_info()

    def _load_template_pdf(self):
        """Загрузить PDF-шаблон."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите PDF-шаблон",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        if not file_path:
            return

        try:
            self.template_pdf_path = Path(file_path)
            self.template_pdf_editor.set_template(self.template_pdf_path)

            # Синхронизируем настройки DM из правой панели
            self._sync_dm_settings_to_template_editor()

            self.status_bar.showMessage(f"Шаблон загружен: {self.template_pdf_path.name}")
            self._update_pdf_info()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить PDF-шаблон:{e}")

    def _sync_dm_settings_to_template_editor(self):
        """Синхронизировать настройки DM из правой панели в редактор шаблона."""
        panel = self.template_editor.right_panel
        self.template_pdf_editor.update_dm_settings(
            size_mm=panel.dm_size,
            quiet_zone_mm=panel.quiet_zone,
            bottom_field_type=panel.bottom_field_type,
            gtin_size=panel.gtin_size,
            article_size=panel.article_size,
            index_size=panel.index_size,
        )

    def _on_template_pdf_settings_changed(self):
        """Изменены настройки DM в режиме шаблона."""
        panel = self.template_pdf_settings
        self.template_pdf_editor.update_dm_settings(
            size_mm=panel.dm_size,
            quiet_zone_mm=panel.quiet_zone,
            bottom_field_type=panel.bottom_field_type,
            gtin_size=panel.gtin_size,
            article_size=panel.article_size,
            index_size=panel.index_size,
        )
        
    def _on_template_element_moved(self, element_id: str, x_mm: float, y_mm: float):
        """Обработчик перемещения элемента в редакторе шаблона."""
        self.status_bar.showMessage(f"DM позиция: X={x_mm:.1f}мм, Y={y_mm:.1f}мм")

    def _on_template_zoom_changed(self, zoom: float):
        """Обработчик изменения zoom колёсиком."""
        self.template_pdf_toolbar.set_zoom(zoom)

    def _on_zoom_in(self):
        self.template_pdf_editor.state.zoom = min(
            self.template_pdf_editor.state.max_zoom,
            self.template_pdf_editor.state.zoom * 1.2
        )
        self.template_pdf_editor.update()
        self.template_pdf_toolbar.set_zoom(self.template_pdf_editor.state.zoom)

    def _on_zoom_out(self):
        self.template_pdf_editor.state.zoom = max(
            self.template_pdf_editor.state.min_zoom,
            self.template_pdf_editor.state.zoom / 1.2
        )
        self.template_pdf_editor.update()
        self.template_pdf_toolbar.set_zoom(self.template_pdf_editor.state.zoom)

    def _on_zoom_reset(self):
        self.template_pdf_editor.state.zoom = 1.0
        self.template_pdf_editor.state.pan_x = 0.0
        self.template_pdf_editor.state.pan_y = 0.0
        self.template_pdf_editor.update()
        self.template_pdf_toolbar.set_zoom(1.0)

    def _on_zoom_slider_changed(self, zoom: float):
        self.template_pdf_editor.state.zoom = zoom
        self.template_pdf_editor.update()

    def _on_split_threshold_changed(self, value: int):
        if value == 0:
            self.lbl_split_info.setText("0 = без разбивки (один файл)")
            self.lbl_split_info.setStyleSheet("color: #888; font-size: 9px;")
        else:
            self.lbl_split_info.setText(f"Разбивка по {value} КИЗов на файл")
            self.lbl_split_info.setStyleSheet("color: #2196F3; font-size: 9px;")
        self._update_pdf_info()

    def _on_gtin_selected(self, item):
        gtin_text = item.text().split("")[0]
        self.template_editor.select_gtin(gtin_text)
        self.template_editor.show_ean13_page()

    def _on_sscc_selected(self, item):
        sscc_text = item.text().split("")[0]
        self.template_editor.show_ean13_page()

    def _on_code_selected(self, item):
        self.template_editor.show_labels_page()

    def _select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "Выберите папку для сохранения PDF", str(self.output_dir)
        )
        if dir_path:
            self.output_dir = Path(dir_path)
            self.status_bar.showMessage(f"Папка сохранения: {self.output_dir}")

    def _load_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите Excel файл", "", "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if not file_path:
            return

        self.btn_load.setEnabled(False)
        self.btn_generate.setEnabled(False)

        self._excel_thread = ExcelLoadThread(file_path)
        self._excel_thread.preview_ready.connect(self._on_preview_ready)
        self._excel_thread.mapping_needed.connect(self._on_mapping_needed)
        self._excel_thread.finished_ok.connect(self._on_excel_finished)
        self._excel_thread.error.connect(self._on_excel_error)

        self._excel_thread.start()

    def _on_preview_ready(self, preview: dict):
        from .dialogs.excel_mapping_dialog import ExcelMappingDialog

        self._mapping_dialog = ExcelMappingDialog(
            headers=preview["headers"],
            preview_rows=preview["rows"],
            file_path=self._excel_thread.file_path,
            parent=self,
        )
        self._mapping_dialog.mapping_confirmed.connect(self._on_mapping_confirmed)

        if self._mapping_dialog.exec() != QDialog.DialogCode.Accepted:
            self._excel_thread.cancel()
            self.btn_load.setEnabled(True)
            return

    def _on_mapping_needed(self):
        """Обработчик запроса на маппинг колонок (заглушка для совместимости)."""
        pass

    def _on_mapping_confirmed(self, mapping: dict):
        active_mapping = {
            k: v for k, v in mapping.items() if v is not None and v != "None"
        }

        self._excel_thread.set_mapping(active_mapping)

        self._progress_dialog = ProgressDialog("Загрузка Excel...", parent=self)
        self._progress_dialog.set_operation("Чтение данных...")
        self._progress_dialog.set_progress(0, 100)
        self._progress_dialog.set_details("Инициализация...")

        self._excel_thread.progress.connect(self._on_excel_progress)
        self._excel_thread.details.connect(self._progress_dialog.set_details)

        self._progress_dialog.cancelled.connect(self._excel_thread.cancel)
        self._progress_dialog.show()

    def _on_excel_progress(self, current: int, total: int):
        if self._progress_dialog:
            self._progress_dialog.set_progress(current, total)

    def _on_excel_finished(self, sscc_data: dict, filename: str):
        self.sscc_data = sscc_data
        self.current_file = filename
        self.lbl_filename.setText(filename)

        self._update_tabs()
        self.template_editor.set_sscc_data(self.sscc_data)
        self.btn_generate.setEnabled(True)
        self._update_pdf_info()

        total_kiz = sum(len(d["codes"]) for d in sscc_data.values())
        gtin_count = len(self._get_gtin_groups())

        if self._progress_dialog:
            self._progress_dialog.set_progress(100, 100)
            self._progress_dialog.set_finished(True)
            self._progress_dialog.set_operation("✓ Загрузка завершена!")
            self._progress_dialog.set_details(
                f"Загружено: {gtin_count} артикулов, {total_kiz} КИЗов"
            )

        self.status_bar.showMessage(
            f"Загружено: {gtin_count} артикулов, {total_kiz} КИЗов"
        )

        self.btn_load.setEnabled(True)

        if self._progress_dialog:
            QTimer.singleShot(1500, self._close_progress_dialog)

    def _on_excel_error(self, error_msg: str):
        self.btn_load.setEnabled(True)
        self.btn_generate.setEnabled(False)

        self._close_progress_dialog()

        clean_msg = error_msg.replace("", "<br>")
        QMessageBox.critical(
            self, "Ошибка", f"Не удалось загрузить файл:<br>{clean_msg}"
        )
        self.status_bar.showMessage("Ошибка загрузки")

    def _get_gtin_groups(self) -> dict:
        gtin_groups = {}
        for data in self.sscc_data.values():
            article = data.get("article", "UNKNOWN")
            gtin = data.get("gtin", "UNKNOWN")
            if gtin not in gtin_groups:
                gtin_groups[gtin] = {"article": article, "count": 0}
            gtin_groups[gtin]["count"] += len(data["codes"])
        return gtin_groups

    def _update_tabs(self):
        self.tab_gtin.clear()
        gtin_groups = self._get_gtin_groups()

        total_codes = 0
        for gtin, info in sorted(gtin_groups.items()):
            total_codes += info["count"]
            article = info["article"]
            display_article = article[:25] + "..." if len(article) > 28 else article
            self.tab_gtin.addItem(f"{article}{display_article} ({info['count']} шт.)")

        self.tab_sscc.clear()
        for sscc, data in sorted(self.sscc_data.items()):
            count = len(data["codes"])
            article = data.get("article", "UNKNOWN")
            self.tab_sscc.addItem(f"{sscc}Арт: {article} ({count} КИЗов)")

        self.tab_codes.clear()
        for sscc, data in list(self.sscc_data.items())[:5]:
            article = data.get("article", "UNKNOWN")
            for i, code in enumerate(data["codes"][:10]):
                kiz = code.get("kiz", "")[:20]
                kiz_num = code.get("kiz_number", str(i + 1))
                self.tab_codes.addItem(f"#{kiz_num} {article}...{kiz}...")

        self.lbl_summary.setText(
            f"<b>Артикулов (GTIN):</b> {len(gtin_groups)}<br>"
            f"<b>Всего КИЗов:</b> {total_codes}<br>"
            f"<b>SSCC (коробов):</b> {len(self.sscc_data)}"
        )

    def _update_pdf_info(self):
        if not self.sscc_data:
            self.lbl_pdf_info.setText("—")
            return

        gtin_set = set()
        for data in self.sscc_data.values():
            gtin_set.add(data.get("gtin", "UNKNOWN"))

        split_val = self.spin_split_threshold.value()

        if self.current_mode == self.MODE_TEMPLATE:
            # Режим шаблона
            template_name = self.template_pdf_path.name if self.template_pdf_path else "не выбран"
            if split_val > 0:
                self.lbl_pdf_info.setText(
                    f"Шаблон: {template_name}\n"
                    f"Разбивка: по {split_val} КИЗов"
                )
            else:
                self.lbl_pdf_info.setText(f"Шаблон: {template_name}")
        else:
            # Стандартный режим
            print_mode = self.template_editor.right_panel.print_mode_data
            mode_str = "сетка" if print_mode == "fill" else "один"

            if split_val > 0:
                self.lbl_pdf_info.setText(
                    f"Будет создано: {len(gtin_set)} PDF ({mode_str})"
                    f"Разбивка: по {split_val} КИЗов"
                )
            else:
                self.lbl_pdf_info.setText(
                    f"Будет создано: {len(gtin_set)} PDF ({mode_str})"
                )

    def _generate_pdf(self):
        if self.current_mode == self.MODE_TEMPLATE:
            self._generate_template_pdf()
        else:
            self._generate_standard_pdf()

    def _generate_template_pdf(self):
        """Генерация PDF в режиме шаблона."""
        # Валидация
        if not self.template_pdf_path:
            QMessageBox.warning(self, "Внимание", "Загрузите PDF-шаблон")
            return

        if not self.sscc_data:
            QMessageBox.warning(self, "Внимание", "Загрузите Excel с КИЗами")
            return

        if not self.template_pdf_editor.state.dm_element:
            QMessageBox.warning(self, "Внимание", "Разместите DM на шаблоне")
            return

        try:
            # Собираем все КИЗы
            all_codes = []
            idx = 1
            for sscc, data in self.sscc_data.items():
                for code in data["codes"]:
                    code_copy = dict(code)
                    code_copy["article"] = data.get("article", "UNKNOWN")
                    code_copy["gtin"] = data.get("gtin", "UNKNOWN")
                    code_copy["global_index"] = idx
                    all_codes.append(code_copy)
                    idx += 1

            # Конфигурация
            config = self.template_pdf_editor.get_config()
            config["split_threshold"] = self.spin_split_threshold.value()

            # Имя файла
            base_name = self.template_pdf_path.stem + "_КИЗ"

            # Генерация
            self.btn_generate.setEnabled(False)
            self.btn_load.setEnabled(False)

            self._progress_dialog = ProgressDialog("Генерация PDF...", parent=self)
            self._progress_dialog.set_operation("Наложение DM на шаблон...")
            self._progress_dialog.set_progress(0, 100)
            self._progress_dialog.show()

            generator = TemplateOverlayGenerator(
                self.template_pdf_path,
                quiet_zone_mm=config.get("quiet_zone_mm", 2)
            )

            split_threshold = self.spin_split_threshold.value()

            def progress_cb(current, total, msg):
                if self._progress_dialog:
                    self._progress_dialog.set_progress(current, total)
                    self._progress_dialog.set_details(msg)

            output_paths = generator.generate_split(
                codes=all_codes,
                config=config,
                output_dir=self.output_dir,
                base_name=base_name,
                split_threshold=split_threshold,
                progress_callback=progress_cb,
            )

            # Завершение
            self.btn_generate.setEnabled(True)
            self.btn_load.setEnabled(True)

            if self._progress_dialog:
                self._progress_dialog.set_progress(100, 100)
                self._progress_dialog.set_finished(True)
                self._progress_dialog.set_operation("✓ Генерация завершена!")
                self._progress_dialog.set_details(
                    f"Создано файлов: {len(output_paths)}"
                )

            self.status_bar.showMessage(f"Создано {len(output_paths)} PDF")

            QMessageBox.information(
                self,
                "Готово",
                f"<b>PDF успешно сгенерированы!</b><br><br>"
                f"Файлов: {len(output_paths)}<br>"
                f"Папка: {self.output_dir}",
            )

            self._close_progress_dialog()

        except Exception as e:
            self.btn_generate.setEnabled(True)
            self.btn_load.setEnabled(True)
            self._close_progress_dialog()
            QMessageBox.critical(self, "Ошибка", f"Ошибка генерации PDF:{e}")
            self.status_bar.showMessage("Ошибка генерации")

    def _generate_standard_pdf(self):
        """Стандартная генерация PDF."""
        try:
            template_config = self.template_editor.get_template_config()
            template_config["print_mode"] = (
                self.template_editor.right_panel.print_mode_data
            )
            template_config["with_aggregates"] = self.chk_with_aggregates.isChecked()
            template_config["split_threshold"] = self.spin_split_threshold.value()

            mode_tuple = template_config.get("label_size", (15, 15))
            dm_n = mode_tuple[0]
            mode = f"{int(dm_n)}x{int(dm_n)}"
            print_mode = template_config.get("print_mode", "fill")

            self.btn_generate.setEnabled(False)
            self.btn_load.setEnabled(False)

            self._progress_dialog = ProgressDialog("Генерация PDF...", parent=self)
            self._progress_dialog.set_operation("Подготовка к генерации PDF...")
            self._progress_dialog.set_progress(0, 100)
            self._progress_dialog.set_details("Инициализация генератора...")

            output_dir = self.output_dir

            self._pdf_thread = PDFGenerationThread(
                self.sscc_data, template_config, output_dir, mode, print_mode
            )
            self._pdf_thread.progress.connect(self._on_pdf_progress)
            self._pdf_thread.details.connect(self._progress_dialog.set_details)
            self._pdf_thread.finished_ok.connect(self._on_pdf_finished)
            self._pdf_thread.error.connect(self._on_pdf_error)

            self._progress_dialog.cancelled.connect(self._pdf_thread.cancel)

            self._progress_dialog.show()
            self._pdf_thread.start()

        except Exception as e:
            self._on_pdf_error(str(e))

    def _on_pdf_progress(self, current: int, total: int):
        if self._progress_dialog:
            self._progress_dialog.set_progress(current, total)

    def _on_pdf_finished(self, output_paths: list):
        self.btn_generate.setEnabled(True)
        self.btn_load.setEnabled(True)
        count = len(output_paths)

        config = self.template_editor.get_template_config()
        print_mode = config.get("print_mode", "fill")

        mode_str = "сетка" if print_mode == "fill" else "один"

        if self._progress_dialog:
            self._progress_dialog.set_progress(100, 100)
            self._progress_dialog.set_finished(True)
            self._progress_dialog.set_operation("✓ Генерация завершена!")
            self._progress_dialog.set_details(
                f"Создано файлов: {count}<br>Режим: {mode_str}<br>"
                f"Папка: {self.output_dir}"
            )

        self.status_bar.showMessage(f"Создано {count} PDF")

        QMessageBox.information(
            self,
            "Готово",
            f"<b>PDF успешно сгенерированы!</b><br><br>"
            f"Режим: {mode_str}<br>"
            f"Файлов: {count}<br>"
            f"Папка: {self.output_dir}",
        )

        self._close_progress_dialog()

    def _on_pdf_error(self, error_msg: str):
        self.btn_generate.setEnabled(True)
        self.btn_load.setEnabled(True)

        self._close_progress_dialog()

        clean_msg = error_msg.replace("", "<br>")
        QMessageBox.critical(self, "Ошибка", f"Ошибка генерации PDF:<br>{clean_msg}")
        self.status_bar.showMessage("Ошибка генерации")

    def _close_progress_dialog(self):
        if self._progress_dialog:
            try:
                self._progress_dialog.close()
            except Exception:
                pass
            self._progress_dialog = None

    def _show_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def _save_template(self):
        config = self.template_editor.get_template_config()

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить шаблон",
            str(self.template_manager.TEMPLATES_DIR / "template_Новый шаблон.json"),
            "JSON (*.json);;All Files (*)",
        )

        if not file_path:
            return

        try:
            path = Path(file_path)
            if path.suffix != ".json":
                path = path.with_suffix(".json")

            name = path.stem
            if name.startswith("template_"):
                name = name[9:]

            import json
            data = {
                "name": name,
                "config": config,
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.status_bar.showMessage(f"Шаблон сохранён: {path.name}")
            QMessageBox.information(self, "Готово", f'Шаблон "{name}" сохранён!')
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить шаблон:{e}")

    def _load_template(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Загрузить шаблон",
            str(self.template_manager.TEMPLATES_DIR),
            "JSON (*.json);;All Files (*)",
        )

        if not file_path:
            return

        try:
            path = Path(file_path)
            config = self.template_manager.load_template_by_path(path)

            if not config:
                QMessageBox.warning(self, "Ошибка", "Не удалось загрузить шаблон")
                return

            self._apply_template_config(config)
            self.status_bar.showMessage(f"Шаблон загружен: {path.name}")
            QMessageBox.information(self, "Готово", f'Шаблон "{path.stem}" загружен!')
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить шаблон:{e}")

    def _apply_template_config(self, config: dict):
        panel = self.template_editor.right_panel

        if "label_size_mm" in config:
            panel.spin_dm_label_size.setValue(config["label_size_mm"])
        if "aggregate_label_size_mm" in config:
            panel.spin_agg_label_size.setValue(config["aggregate_label_size_mm"])

        if "dm_size_mm" in config:
            panel.spin_dm_size.setValue(config["dm_size_mm"])
        if "quiet_zone_mm" in config:
            panel.spin_quiet_zone.setValue(config["quiet_zone_mm"])

        if "bottom_field_type" in config:
            mapping = {"none": 0, "gtin": 1, "index": 2, "article": 3}
            btn_id = mapping.get(config["bottom_field_type"], 2)
            btn = panel.bottom_field_group.button(btn_id)
            if btn:
                btn.setChecked(True)

        if "gtin_size" in config:
            panel.spin_gtin_size.setValue(config["gtin_size"])
        if "index_size" in config:
            panel.spin_index_size.setValue(config["index_size"])
        if "article_size" in config:
            panel.spin_article_size.setValue(config["article_size"])

        if "aggregate_size_mm" in config:
            panel.spin_agg_size.setValue(config["aggregate_size_mm"])
        if "sscc_size" in config:
            panel.spin_sscc_size.setValue(config["sscc_size"])

        if "page_width_mm" in config:
            panel.spin_paper_w.setValue(config["page_width_mm"])
        if "page_height_mm" in config:
            panel.spin_paper_h.setValue(config["page_height_mm"])

        if "print_mode" in config:
            idx = 0 if config["print_mode"] == "fill" else 1
            panel.cmb_print_mode.setCurrentIndex(idx)

        if "single_mode_type" in config:
            idx = 0 if config["single_mode_type"] == "with_elements" else 1
            panel.cmb_single_mode.setCurrentIndex(idx)

        if "page_limit" in config:
            panel.spin_limit.setValue(config["page_limit"])

        if "split_threshold" in config:
            self.spin_split_threshold.setValue(config["split_threshold"])

        if "elements" in config:
            self.template_editor.canvas.set_elements(config["elements"])
        if "aggregate_elements" in config:
            self.template_editor.aggregate_editor.set_elements(config["aggregate_elements"])

        self.template_editor._on_settings_changed()

        # Если в режиме шаблона — синхронизируем настройки
        if self.current_mode == self.MODE_TEMPLATE:
            self._sync_dm_settings_to_template_editor()
