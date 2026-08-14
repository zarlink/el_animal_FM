from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from el_animal_fm.prediction.application.config.prediction_config import (
    FUND_CONFIG,
    FUND_MODEL_CONFIG,
    THRESHOLD_SEARCH_SPACE,
    XGB_MODEL_CONFIG,
)
from el_animal_fm.ui.views.news_enrichment_view import NewsEnrichmentView
from el_animal_fm.ui.widgets.calendar_date_edit import CalendarDateEdit


class ModelsView(QWidget):
    """Visual editor for fund presets and Optuna settings."""

    def __init__(self) -> None:
        super().__init__()
        self._fund_checks: dict[str, QCheckBox] = {}
        self._fund_cards: dict[str, QFrame] = {}
        self._strategy_fields: dict[str, QWidget] = {}
        self._xgb_fields: dict[str, QWidget] = {}
        self._selected_fund = "national_equity"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("ModelsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        surface = QWidget()
        surface.setObjectName("ModelsScrollSurface")
        surface.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        surface_layout = QVBoxLayout(surface)
        surface_layout.setContentsMargins(0, 0, 4, 8)
        surface_layout.setSpacing(10)

        upper = QHBoxLayout()
        upper.setSpacing(10)
        upper.addWidget(self._build_funds_panel(), stretch=3)
        upper.addWidget(self._build_configuration_panel(), stretch=5)
        upper.addWidget(self._build_optuna_panel(), stretch=4)
        upper_container = QWidget()
        upper_container.setLayout(upper)
        upper_container.setMinimumHeight(535)
        surface_layout.addWidget(upper_container)
        surface_layout.addWidget(self._build_training_panel())
        surface_layout.addWidget(self._build_console())
        surface_layout.addStretch(1)

        scroll.setWidget(surface)
        layout.addWidget(scroll)

        self._select_fund(self._selected_fund)

    def _build_funds_panel(self) -> QFrame:
        panel = self._panel()
        layout = panel.layout()
        layout.addWidget(self._title("FONDOS / MODELOS"))

        toolbar = QHBoxLayout()
        selection = QComboBox()
        selection.setObjectName("NewsInput")
        selection.addItems(("TODOS", "ACTIVOS", "CON MODELO"))
        toolbar.addWidget(selection, stretch=1)
        add = self._button("+  AGREGAR FONDO", primary=True)
        toolbar.addWidget(add)
        layout.addLayout(toolbar)

        for fund_key, config in FUND_CONFIG.items():
            card = QFrame()
            card.setObjectName("ModelFundCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(4)

            heading = QHBoxLayout()
            checkbox = QCheckBox()
            checkbox.setObjectName("NewsCheck")
            checkbox.setChecked(True)
            heading.addWidget(checkbox)
            name = QPushButton(config["label"].upper())
            name.setObjectName("ModelFundName")
            name.setCursor(Qt.CursorShape.PointingHandCursor)
            name.clicked.connect(lambda _checked=False, key=fund_key: self._select_fund(key))
            heading.addWidget(name, stretch=1)
            card_layout.addLayout(heading)

            detail = QLabel(
                f"RUN {config['run_fm']}    |    {config['horizon_business_days']} "
                f"{'DIA' if config['horizon_business_days'] == 1 else 'DIAS'}"
            )
            detail.setObjectName("ModelMuted")
            card_layout.addWidget(detail)
            status = QLabel("●  MODELO LISTO")
            status.setObjectName("ModelSuccess")
            card_layout.addWidget(status)

            self._fund_checks[fund_key] = checkbox
            self._fund_cards[fund_key] = card
            layout.addWidget(card)

        layout.addStretch(1)
        return panel

    def _build_configuration_panel(self) -> QFrame:
        panel = self._panel()
        layout = panel.layout()
        layout.addWidget(self._title("CONFIGURACION DEL MODELO"))

        self._fund_tabs = QTabBar()
        self._fund_tabs.setObjectName("ModelFundTabs")
        for fund_key, config in FUND_CONFIG.items():
            index = self._fund_tabs.addTab(config["label"].upper())
            self._fund_tabs.setTabData(index, fund_key)
        self._fund_tabs.currentChanged.connect(self._tab_changed)
        layout.addWidget(self._fund_tabs)

        groups = QHBoxLayout()
        groups.setSpacing(8)

        strategy = self._subpanel("ESTRATEGIA Y UMBRALES")
        strategy_grid = QGridLayout()
        strategy_grid.setHorizontalSpacing(7)
        strategy_grid.setVerticalSpacing(6)
        mode = QComboBox()
        mode.setObjectName("NewsInput")
        mode.addItems(("strict_lag", "night_partial", "same_day_close"))
        decision_time = QLineEdit()
        decision_time.setObjectName("NewsInput")
        probability = self._double_field(0, 1, 6)
        target = self._double_field(0, 1, 6)
        strict = self._check("STRICT RETURN LAG")
        preset = self._check("USAR PRESET DEL FONDO", checked=True)
        strategy_values = (
            ("decision_mode", mode),
            ("decision_time", decision_time),
            ("probability_threshold", probability),
            ("target_threshold", target),
        )
        for row, (label, field) in enumerate(strategy_values):
            strategy_grid.addWidget(self._field_label(label), row, 0)
            strategy_grid.addWidget(field, row, 1)
            self._strategy_fields[label] = field
        strategy_grid.addWidget(strict, len(strategy_values), 0, 1, 2)
        strategy_grid.addWidget(preset, len(strategy_values) + 1, 0, 1, 2)
        self._strategy_fields["strict_return_lag"] = strict
        strategy.layout().addLayout(strategy_grid)
        strategy.layout().addStretch(1)
        groups.addWidget(strategy, stretch=2)

        xgb = self._subpanel("HIPERPARAMETROS XGBOOST")
        xgb_grid = QGridLayout()
        xgb_grid.setHorizontalSpacing(7)
        xgb_grid.setVerticalSpacing(6)
        specs = (
            ("n_estimators", True),
            ("learning_rate", False),
            ("max_depth", True),
            ("min_child_weight", False),
            ("gamma", False),
            ("subsample", False),
            ("colsample_bytree", False),
            ("reg_lambda", False),
            ("reg_alpha", False),
        )
        for index, (name, integer) in enumerate(specs):
            row, column = divmod(index, 2)
            label_column = column * 2
            field = self._integer_field() if integer else self._double_field(0, 100, 6)
            xgb_grid.addWidget(self._field_label(name), row, label_column)
            xgb_grid.addWidget(field, row, label_column + 1)
            self._xgb_fields[name] = field
        xgb.layout().addLayout(xgb_grid)
        xgb.layout().addStretch(1)
        groups.addWidget(xgb, stretch=3)
        layout.addLayout(groups, stretch=1)

        footer = QHBoxLayout()
        path = QLabel("CODE  prediction_config.py / XGB_MODEL_CONFIG")
        path.setObjectName("NewsScriptLabel")
        footer.addWidget(path, stretch=1)
        footer.addWidget(self._button("RESTABLECER PRESET"))
        footer.addWidget(self._button("GUARDAR PARAMETROS", primary=True))
        layout.addLayout(footer)
        return panel

    def _build_optuna_panel(self) -> QFrame:
        panel = self._panel()
        layout = panel.layout()
        layout.addWidget(self._title("OPTUNA · FINE TUNING"))

        self._optuna_tabs = QTabBar()
        self._optuna_tabs.setObjectName("ModelOptunaTabs")
        self._optuna_tabs.addTab("UMBRALES")
        self._optuna_tabs.addTab("XGBOOST")
        layout.addWidget(self._optuna_tabs)

        scope = QHBoxLayout()
        self._optuna_fund = QComboBox()
        self._optuna_fund.setObjectName("NewsInput")
        for key, config in FUND_CONFIG.items():
            self._optuna_fund.addItem(config["label"].upper(), key)
        scope.addWidget(self._optuna_fund, stretch=1)
        scope.addWidget(self._check("APLICAR A SELECCIONADOS", checked=True))
        layout.addLayout(scope)

        settings = QGridLayout()
        settings.setHorizontalSpacing(8)
        settings.setVerticalSpacing(6)
        self._trials = self._integer_field(1, 10000, 80)
        self._timeout = self._integer_field(0, 999999, 3600)
        self._metric = QComboBox()
        self._metric.setObjectName("NewsInput")
        self._metric.addItems(("risk_adjusted", "strategy_return", "improvement", "balanced_accuracy"))
        for column, (label, widget) in enumerate(
            (("TRIALS", self._trials), ("TIMEOUT (S)", self._timeout), ("METRICA", self._metric))
        ):
            settings.addWidget(self._field_label(label), 0, column)
            settings.addWidget(widget, 1, column)
        layout.addLayout(settings)

        layout.addWidget(self._field_label("MODOS DE DECISION"))
        modes = QHBoxLayout()
        for mode in ("strict_lag", "night_partial", "same_day_close"):
            modes.addWidget(self._check(mode, checked=True))
        layout.addLayout(modes)

        ranges = self._subpanel("ESPACIO DE BUSQUEDA")
        ranges.setMinimumHeight(106)
        range_grid = QGridLayout()
        self._target_min = self._double_field(0, 1, 6)
        self._target_max = self._double_field(0, 1, 6)
        self._prob_min = self._double_field(0, 1, 4)
        self._prob_max = self._double_field(0, 1, 4)
        range_grid.addWidget(self._field_label("TARGET"), 0, 0)
        range_grid.addWidget(self._target_min, 0, 1)
        range_grid.addWidget(QLabel("—"), 0, 2)
        range_grid.addWidget(self._target_max, 0, 3)
        range_grid.addWidget(self._field_label("PROBABILIDAD"), 1, 0)
        range_grid.addWidget(self._prob_min, 1, 1)
        range_grid.addWidget(QLabel("—"), 1, 2)
        range_grid.addWidget(self._prob_max, 1, 3)
        ranges.layout().addLayout(range_grid)
        layout.addWidget(ranges)

        signals = QGridLayout()
        signals.addWidget(self._field_label("SEÑALES SUBE MIN."), 0, 0)
        signals.addWidget(self._field_label("SEÑALES BAJA MIN."), 0, 1)
        signals.addWidget(self._integer_field(0, 100, 2), 1, 0)
        signals.addWidget(self._integer_field(0, 100, 2), 1, 1)
        layout.addLayout(signals)

        xgb_space = QLabel("ESPACIO XGBOOST\n9 parametros · rangos especificos por fondo")
        xgb_space.setObjectName("ModelSearchSpace")
        layout.addWidget(xgb_space)
        layout.addStretch(1)
        layout.addWidget(self._button("▶  INICIAR BUSQUEDA OPTUNA", primary=True))
        self._optuna_fund.currentIndexChanged.connect(self._optuna_fund_changed)
        self._optuna_fund_changed()
        return panel

    def _build_training_panel(self) -> QFrame:
        panel = self._panel()
        panel.setObjectName("ModelTrainingPanel")
        panel.setMinimumHeight(188)
        layout = panel.layout()
        layout.addWidget(self._title("ENTRENAMIENTO Y EVALUACION"))

        content = QHBoxLayout()
        content.setSpacing(12)

        schedule = QVBoxLayout()
        schedule.setSpacing(4)
        dates = QGridLayout()
        dates.setHorizontalSpacing(8)
        date_specs = (
            ("INICIO ENTRENAMIENTO", date(2025, 4, 4)),
            ("FIN ENTRENAMIENTO", date(2026, 5, 30)),
            ("INICIO PRUEBA", date(2026, 5, 31)),
            ("FIN PRUEBA", date(2026, 6, 9)),
        )
        date_fields: list[QDateEdit] = []
        for column, (label, value) in enumerate(date_specs):
            dates.addWidget(self._field_label(label), 0, column)
            field = self._date_field(value)
            dates.addWidget(field, 1, column)
            date_fields.append(field)
        schedule.addLayout(dates)

        split_control = QFrame()
        split_control.setObjectName("ModelTimeline")
        split_layout = QVBoxLayout(split_control)
        split_layout.setContentsMargins(8, 4, 8, 4)
        split_layout.setSpacing(2)

        self._data_split = QSlider(Qt.Orientation.Horizontal)
        self._data_split.setObjectName("ModelDataSplit")
        self._data_split.setRange(50, 95)
        self._data_split.setValue(80)
        self._data_split.setSingleStep(1)
        self._data_split.setPageStep(5)
        self._data_split.setToolTip("Porcentaje de datos destinado al entrenamiento")
        split_layout.addWidget(self._data_split)

        split_labels = QHBoxLayout()
        self._training_split_label = QLabel()
        self._training_split_label.setObjectName("ModelTimelineTrain")
        self._evaluation_split_label = QLabel()
        self._evaluation_split_label.setObjectName("ModelTimelineTest")
        split_labels.addWidget(self._training_split_label)
        split_labels.addStretch(1)
        split_labels.addWidget(self._evaluation_split_label)
        split_layout.addLayout(split_labels)
        schedule.addWidget(split_control)

        self._training_start, self._training_end, self._evaluation_start, self._evaluation_end = date_fields
        self._data_split.valueChanged.connect(self._update_data_split)
        self._training_start.dateChanged.connect(self._update_data_split)
        self._evaluation_end.dateChanged.connect(self._update_data_split)
        self._update_data_split()

        script = QLabel("CODE  09_xgboost_prediction.py")
        script.setObjectName("ModelScriptLabel")
        schedule.addWidget(script)
        content.addLayout(schedule, stretch=6)

        options = QGridLayout()
        options.setHorizontalSpacing(8)
        options.addWidget(self._field_label("MODALIDAD"), 0, 0, 1, 2)
        modality = QComboBox()
        modality.setObjectName("NewsInput")
        modality.addItems(("3 MODALIDADES", "strict_lag", "night_partial", "same_day_close"))
        options.addWidget(modality, 1, 0, 1, 2)
        options.addWidget(self._check("USAR PRESETS POR FONDO", checked=True), 2, 0)
        options.addWidget(self._check("USAR XGB_MODEL_CONFIG", checked=True), 2, 1)
        options.addWidget(self._check("SOLO PREDICCION LIVE"), 3, 0, 1, 2)
        options_frame = QFrame()
        options_frame.setObjectName("ModelTrainingOptions")
        options_frame.setLayout(options)
        content.addWidget(options_frame, stretch=3)

        actions = QVBoxLayout()
        actions.addWidget(self._button("▶  ENTRENAR MODELOS SELECCIONADOS", primary=True))
        actions.addWidget(self._button("EVALUAR MODELOS"))
        actions.addStretch(1)
        content.addLayout(actions, stretch=2)
        layout.addLayout(content, stretch=1)
        return panel

    def _update_data_split(self) -> None:
        """Apply the selected train/evaluation percentage to the full date range."""
        training_percentage = self._data_split.value()
        self._training_split_label.setText(f"ENTRENAMIENTO  {training_percentage}%")
        self._evaluation_split_label.setText(f"EVALUACION  {100 - training_percentage}%")

        start = self._training_start.date()
        end = self._evaluation_end.date()
        total_days = start.daysTo(end)
        if total_days < 1:
            return

        training_days = max(1, round((total_days + 1) * training_percentage / 100))
        split_date = start.addDays(min(training_days - 1, total_days - 1))
        evaluation_start = split_date.addDays(1)
        self._training_end.setDate(split_date)
        self._evaluation_start.setDate(evaluation_start)

    def _build_console(self) -> QFrame:
        panel = self._panel()
        panel.setObjectName("ModelConsolePanel")
        panel.setMinimumHeight(230)
        layout = panel.layout()

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._title("CONSOLA DE EJECUCION"))
        toolbar.addStretch(1)
        toolbar.addWidget(self._button("DETENER"))
        clear = self._button("LIMPIAR CONSOLA")
        toolbar.addWidget(clear)
        layout.addLayout(toolbar)

        console = QTextEdit()
        console.setObjectName("NewsConsole")
        console.setReadOnly(True)
        console.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        console.setPlainText(
            "10:47:31  [READY]  Modulo de modelos preparado · MOCKUP\n"
            "10:47:32  [INFO]   Fondos seleccionados: 4\n"
            "10:47:32  [INFO]   Train: 2025-04-04 → 2026-05-30 | Eval: 2026-05-31 → 2026-06-09\n"
            "10:47:33  [INFO]   Configuracion por fondo y espacios Optuna cargados\n"
            "10:47:33  [WAIT]   Esperando una futura conexion con 09_xgboost_prediction.py"
        )
        clear.clicked.connect(console.clear)
        layout.addWidget(console, stretch=1)
        return panel

    def _select_fund(self, fund_key: str) -> None:
        self._selected_fund = fund_key
        for key, card in self._fund_cards.items():
            card.setProperty("selected", key == fund_key)
            card.style().unpolish(card)
            card.style().polish(card)
        for index in range(self._fund_tabs.count()):
            if self._fund_tabs.tabData(index) == fund_key:
                self._fund_tabs.blockSignals(True)
                self._fund_tabs.setCurrentIndex(index)
                self._fund_tabs.blockSignals(False)
                break
        optuna_index = self._optuna_fund.findData(fund_key)
        if optuna_index >= 0:
            self._optuna_fund.setCurrentIndex(optuna_index)
        self._load_fund_values(fund_key)

    def _tab_changed(self, index: int) -> None:
        fund_key = self._fund_tabs.tabData(index)
        if fund_key:
            self._select_fund(str(fund_key))

    def _load_fund_values(self, fund_key: str) -> None:
        strategy = FUND_MODEL_CONFIG[fund_key]
        mode = self._strategy_fields["decision_mode"]
        if isinstance(mode, QComboBox):
            mode.setCurrentText(str(strategy["decision_mode"]))
        decision_time = self._strategy_fields["decision_time"]
        if isinstance(decision_time, QLineEdit):
            decision_time.setText(str(strategy.get("decision_time") or "N/A"))
        for key in ("probability_threshold", "target_threshold"):
            field = self._strategy_fields[key]
            if isinstance(field, QDoubleSpinBox):
                field.setValue(float(strategy[key]))
        strict = self._strategy_fields["strict_return_lag"]
        if isinstance(strict, QCheckBox):
            strict.setChecked(bool(strategy["strict_return_lag"]))

        for key, value in XGB_MODEL_CONFIG[fund_key].items():
            field = self._xgb_fields[key]
            if isinstance(field, QSpinBox):
                field.setValue(int(value))
            elif isinstance(field, QDoubleSpinBox):
                field.setValue(float(value))

    def _optuna_fund_changed(self) -> None:
        fund_key = self._optuna_fund.currentData()
        if not fund_key:
            return
        search = THRESHOLD_SEARCH_SPACE[str(fund_key)]
        self._target_min.setValue(float(search["target_min"]))
        self._target_max.setValue(float(search["target_max"]))
        self._prob_min.setValue(float(search["prob_min"]))
        self._prob_max.setValue(float(search["prob_max"]))

    @staticmethod
    def _panel() -> QFrame:
        panel = QFrame()
        panel.setObjectName("NewsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        return panel

    @staticmethod
    def _subpanel(title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ModelSubPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(9, 8, 9, 8)
        layout.setSpacing(7)
        layout.addWidget(ModelsView._field_label(title))
        return frame

    @staticmethod
    def _title(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("NewsPanelTitle")
        return label

    @staticmethod
    def _field_label(text: str) -> QLabel:
        return NewsEnrichmentView._field_label(text)

    @staticmethod
    def _check(text: str, checked: bool = False) -> QCheckBox:
        checkbox = QCheckBox(text)
        checkbox.setObjectName("NewsCheck")
        checkbox.setChecked(checked)
        return checkbox

    @staticmethod
    def _button(text: str, *, primary: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("NewsPrimaryButton" if primary else "NewsButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(32)
        return button

    @staticmethod
    def _integer_field(minimum: int = 0, maximum: int = 100000, value: int = 0) -> QSpinBox:
        field = QSpinBox()
        field.setObjectName("NewsInput")
        field.setRange(minimum, maximum)
        field.setValue(value)
        return field

    @staticmethod
    def _double_field(minimum: float, maximum: float, decimals: int) -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setObjectName("NewsInput")
        field.setRange(minimum, maximum)
        field.setDecimals(decimals)
        field.setSingleStep(0.001)
        return field

    @staticmethod
    def _date_field(value: date) -> QDateEdit:
        field = CalendarDateEdit(QDate(value.year, value.month, value.day))
        field.setObjectName("NewsInput")
        field.setCalendarPopup(True)
        field.setDisplayFormat("yyyy-MM-dd")
        return field
