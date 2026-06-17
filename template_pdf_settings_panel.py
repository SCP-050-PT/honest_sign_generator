# gui/components/template_pdf_settings_panel.py

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QButtonGroup,
    QRadioButton,
    QGroupBox,
)
from PyQt6.QtCore import pyqtSignal


class TemplatePdfSettingsPanel(QWidget):
    """Панель настроек DM для режима шаблона PDF (размещается снизу редактора)."""

    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(180)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 8, 10, 8)

        # === Группа Размер DM ===
        dm_size_group = QGroupBox("Размер DM")
        dm_size_layout = QVBoxLayout(dm_size_group)

        dm_size_hbox = QHBoxLayout()
        dm_size_hbox.addWidget(QLabel("Размер:"))
        self.spin_dm_size = QSpinBox()
        self.spin_dm_size.setRange(5, 99)
        self.spin_dm_size.setValue(16)
        self.spin_dm_size.setSuffix(" мм")
        self.spin_dm_size.valueChanged.connect(self._emit_changed)
        dm_size_hbox.addWidget(self.spin_dm_size)
        dm_size_layout.addLayout(dm_size_hbox)

        qz_hbox = QHBoxLayout()
        qz_hbox.addWidget(QLabel("Quiet Zone:"))
        self.spin_quiet_zone = QSpinBox()
        self.spin_quiet_zone.setRange(0, 5)
        self.spin_quiet_zone.setValue(2)
        self.spin_quiet_zone.setSuffix(" мм")
        self.spin_quiet_zone.valueChanged.connect(self._emit_changed)
        qz_hbox.addWidget(self.spin_quiet_zone)
        dm_size_layout.addLayout(qz_hbox)

        layout.addWidget(dm_size_group)

        # === Группа Нижнее поле DM ===
        bottom_group = QGroupBox("Нижнее поле DM")
        bottom_layout = QVBoxLayout(bottom_group)

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
        self.bottom_field_group.idClicked.connect(self._emit_changed)

        bottom_layout.addWidget(self.radio_none)
        bottom_layout.addWidget(self.radio_gtin)
        bottom_layout.addWidget(self.radio_index)
        bottom_layout.addWidget(self.radio_article)

        layout.addWidget(bottom_group)

        # === Группа Размеры шрифтов ===
        font_group = QGroupBox("Размеры шрифтов")
        font_layout = QVBoxLayout(font_group)

        gtin_hbox = QHBoxLayout()
        gtin_hbox.addWidget(QLabel("GTIN:"))
        self.spin_gtin_size = QSpinBox()
        self.spin_gtin_size.setRange(5, 16)
        self.spin_gtin_size.setValue(8)
        self.spin_gtin_size.setSuffix(" пт")
        self.spin_gtin_size.valueChanged.connect(self._emit_changed)
        gtin_hbox.addWidget(self.spin_gtin_size)
        font_layout.addLayout(gtin_hbox)

        idx_hbox = QHBoxLayout()
        idx_hbox.addWidget(QLabel("№пп:"))
        self.spin_index_size = QSpinBox()
        self.spin_index_size.setRange(5, 16)
        self.spin_index_size.setValue(5)
        self.spin_index_size.setSuffix(" пт")
        self.spin_index_size.valueChanged.connect(self._emit_changed)
        idx_hbox.addWidget(self.spin_index_size)
        font_layout.addLayout(idx_hbox)

        art_hbox = QHBoxLayout()
        art_hbox.addWidget(QLabel("Артикул:"))
        self.spin_article_size = QSpinBox()
        self.spin_article_size.setRange(5, 16)
        self.spin_article_size.setValue(8)
        self.spin_article_size.setSuffix(" пт")
        self.spin_article_size.valueChanged.connect(self._emit_changed)
        art_hbox.addWidget(self.spin_article_size)
        font_layout.addLayout(art_hbox)

        layout.addWidget(font_group)
        layout.addStretch()

    def _emit_changed(self):
        self.settings_changed.emit()

    # Геттеры
    @property
    def dm_size(self):
        return self.spin_dm_size.value()

    @property
    def quiet_zone(self):
        return self.spin_quiet_zone.value()

    @property
    def bottom_field_type(self) -> str:
        mapping = {0: "none", 1: "gtin", 2: "index", 3: "article"}
        return mapping.get(self.bottom_field_group.checkedId(), "index")

    @property
    def gtin_size(self):
        return self.spin_gtin_size.value()

    @property
    def article_size(self):
        return self.spin_article_size.value()

    @property
    def index_size(self):
        return self.spin_index_size.value()
