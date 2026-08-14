from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from el_animal_fm.ui.widgets.calendar_date_edit import CalendarDateEdit


class NewsEnrichmentView(QWidget):
    """Operational layout for normalization, enrichment and CMF downloads."""

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        workflow = QHBoxLayout()
        workflow.setSpacing(10)
        workflow.addWidget(self._build_normalization_panel(), stretch=1)
        workflow.addWidget(self._build_enrichment_panel(), stretch=1)
        workflow.addWidget(self._build_cmf_panel(), stretch=1)

        layout.addLayout(workflow, stretch=3)
        layout.addWidget(self._build_console(), stretch=2)

    def _build_normalization_panel(self) -> QFrame:
        panel, body = self._build_panel("01", "NORMALIZAR NOTICIAS")

        body.addWidget(self._field_label("FUENTES"))
        source_row = QHBoxLayout()
        source_row.setSpacing(12)
        source_row.addWidget(self._checkbox("BIO BIO CHILE", checked=True))
        source_row.addWidget(self._checkbox("EL MOSTRADOR", checked=True))
        source_row.addStretch(1)
        body.addLayout(source_row)

        body.addWidget(self._field_label("ARCHIVO DE ENTRADA"))
        body.addWidget(self._line_edit("noticias_dia.txt"))

        overwrite = self._checkbox("SOBRESCRIBIR ORIGINAL", checked=True)
        body.addWidget(overwrite)

        body.addWidget(self._field_label("ARCHIVO DE SALIDA (ALTERNATIVO)"))
        body.addWidget(self._line_edit("noticias_dia_normalizado.txt"))

        body.addWidget(self._separator())
        body.addWidget(self._field_label("ESTADO"))
        stats = QGridLayout()
        stats.setSpacing(6)
        for column, (label, value) in enumerate(
            (("TOTAL", "1.195"), ("PROCESADAS", "1.195"), ("NORMALIZADAS", "1.195"), ("ERRORES", "0"))
        ):
            stats.addWidget(self._stat(label, value, error=label == "ERRORES"), 0, column)
        body.addLayout(stats)
        body.addStretch(1)
        body.addWidget(self._primary_button("▶  EJECUTAR NORMALIZACION"))
        body.addWidget(self._script_label("03_normalizador_noticias.py"))
        return panel

    def _build_enrichment_panel(self) -> QFrame:
        panel, body = self._build_panel("02", "ENRIQUECER NOTICIAS")

        dates = QGridLayout()
        dates.setHorizontalSpacing(10)
        dates.setVerticalSpacing(5)
        end_date = date.today()
        dates.addWidget(self._field_label("DESDE"), 0, 0)
        dates.addWidget(self._field_label("HASTA"), 0, 1)
        dates.addWidget(self._date_edit(end_date - timedelta(days=2)), 1, 0)
        dates.addWidget(self._date_edit(end_date), 1, 1)
        body.addLayout(dates)

        options = QGridLayout()
        options.setHorizontalSpacing(10)
        options.setVerticalSpacing(6)
        options.addWidget(self._field_label("FUENTE"), 0, 0)
        source = QComboBox()
        source.setObjectName("NewsInput")
        source.addItems(("AMBAS FUENTES", "BIO BIO CHILE", "EL MOSTRADOR"))
        options.addWidget(source, 1, 0)
        options.addWidget(self._field_label("WORKERS"), 0, 1)
        workers = QSpinBox()
        workers.setObjectName("NewsInput")
        workers.setRange(1, 32)
        workers.setValue(4)
        options.addWidget(workers, 1, 1)
        body.addLayout(options)

        body.addWidget(self._field_label("VERSION DE DICCIONARIO"))
        body.addWidget(self._line_edit("v2026-06-25"))

        toggle_row = QHBoxLayout()
        toggle_row.addWidget(self._checkbox("USAR CANDIDATOS", checked=True))
        toggle_row.addWidget(self._checkbox("SOBRESCRIBIR"))
        body.addLayout(toggle_row)

        files = QGridLayout()
        files.setHorizontalSpacing(10)
        files.setVerticalSpacing(5)
        files.addWidget(self._field_label("ARCHIVO DE ENTRADA"), 0, 0)
        files.addWidget(self._field_label("ARCHIVO DE SALIDA"), 0, 1)
        files.addWidget(self._line_edit("noticias_dia.txt"), 1, 0)
        files.addWidget(self._line_edit("noticias_dia_enriquecidas.txt"), 1, 1)
        body.addLayout(files)

        body.addStretch(1)
        body.addWidget(self._primary_button("▶  EJECUTAR ENRIQUECIMIENTO"))
        body.addWidget(self._script_label("06_enriquecer_noticias.py"))
        return panel

    def _build_cmf_panel(self) -> QFrame:
        panel, body = self._build_panel("03", "DESCARGAR VALORES CMF")

        body.addWidget(self._field_label("FONDOS / SERIES"))
        funds = QGridLayout()
        funds.setHorizontalSpacing(10)
        funds.setVerticalSpacing(5)
        labels = ("CARTERA BALANCEADO", "NATIONAL EQUITY", "TOESCA EQUITY", "AHORRO UF ITAU")
        for index, label in enumerate(labels):
            funds.addWidget(self._checkbox(label, checked=True), index // 2, index % 2)
        body.addLayout(funds)

        dates = QGridLayout()
        dates.setHorizontalSpacing(10)
        dates.setVerticalSpacing(5)
        today = date.today()
        dates.addWidget(self._field_label("FECHA INICIAL"), 0, 0)
        dates.addWidget(self._field_label("FECHA FINAL"), 0, 1)
        dates.addWidget(self._date_edit(today - timedelta(days=30)), 1, 0)
        dates.addWidget(self._date_edit(today), 1, 1)
        body.addLayout(dates)

        request_options = QGridLayout()
        request_options.setHorizontalSpacing(10)
        request_options.addWidget(self._field_label("MAX. DIAS / TRAMO"), 0, 0)
        max_days = QSpinBox()
        max_days.setObjectName("NewsInput")
        max_days.setRange(1, 31)
        max_days.setValue(31)
        request_options.addWidget(max_days, 1, 0)
        request_options.addWidget(self._checkbox("OMITIR EXISTENTES"), 1, 1)
        body.addLayout(request_options)

        body.addWidget(self._separator())
        body.addWidget(self._field_label("CAPTCHA"))
        captcha_row = QHBoxLayout()
        captcha = QLabel("A 7 K 2")
        captcha.setObjectName("NewsCaptcha")
        captcha.setAlignment(Qt.AlignmentFlag.AlignCenter)
        captcha_row.addWidget(captcha, stretch=1)
        captcha_status = QLabel("ESTADO: LISTO\nRENOVACION AUTO: 02:47")
        captcha_status.setObjectName("NewsSuccess")
        captcha_row.addWidget(captcha_status, stretch=2)
        body.addLayout(captcha_row)

        body.addStretch(1)
        body.addWidget(self._primary_button("▶  INICIAR DESCARGA CMF"))
        body.addWidget(self._script_label("08_descarga_fondos_mutuos.py"))
        return panel

    def _build_console(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("NewsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(7)

        toolbar = QHBoxLayout()
        title = QLabel("CONSOLA DE EJECUCION")
        title.setObjectName("NewsPanelTitle")
        toolbar.addWidget(title)
        toolbar.addStretch(1)

        stop = self._secondary_button("DETENER")
        clear = self._secondary_button("LIMPIAR CONSOLA")
        toolbar.addWidget(stop)
        toolbar.addWidget(clear)
        layout.addLayout(toolbar)

        console = QTextEdit()
        console.setObjectName("NewsConsole")
        console.setReadOnly(True)
        console.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        console.setPlainText(_CONSOLE_TEXT)
        clear.clicked.connect(console.clear)
        layout.addWidget(console, stretch=1)
        return panel

    @staticmethod
    def _build_panel(index: str, title_text: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("NewsPanel")
        panel.setMinimumWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 9, 12, 10)
        layout.setSpacing(7)

        heading = QHBoxLayout()
        index_label = QLabel(index)
        index_label.setObjectName("NewsPanelIndex")
        title = QLabel(title_text)
        title.setObjectName("NewsPanelTitle")
        heading.addWidget(index_label)
        heading.addWidget(title)
        heading.addStretch(1)
        layout.addLayout(heading)
        layout.addWidget(NewsEnrichmentView._separator())
        return panel, layout

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("NewsFieldLabel")
        return label

    @staticmethod
    def _line_edit(text: str) -> QLineEdit:
        field = QLineEdit(text)
        field.setObjectName("NewsInput")
        return field

    @staticmethod
    def _date_edit(value: date) -> QDateEdit:
        field = CalendarDateEdit(QDate(value.year, value.month, value.day))
        field.setObjectName("NewsInput")
        field.setCalendarPopup(True)
        field.setDisplayFormat("yyyy-MM-dd")
        return field

    @staticmethod
    def _checkbox(text: str, checked: bool = False) -> QCheckBox:
        checkbox = QCheckBox(text)
        checkbox.setObjectName("NewsCheck")
        checkbox.setChecked(checked)
        return checkbox

    @staticmethod
    def _separator() -> QFrame:
        separator = QFrame()
        separator.setObjectName("NewsSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        return separator

    @staticmethod
    def _primary_button(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("NewsPrimaryButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(42)
        return button

    @staticmethod
    def _secondary_button(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("NewsButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(30)
        return button

    @staticmethod
    def _script_label(text: str) -> QLabel:
        label = QLabel("CODE  " + text)
        label.setObjectName("NewsScriptLabel")
        return label

    @staticmethod
    def _stat(label_text: str, value_text: str, *, error: bool = False) -> QFrame:
        frame = QFrame()
        frame.setObjectName("NewsErrorStat" if error else "NewsStat")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 5, 4, 5)
        layout.setSpacing(2)
        label = QLabel(label_text)
        label.setObjectName("NewsStatLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value = QLabel(value_text)
        value.setObjectName("NewsStatValue")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        layout.addWidget(value)
        return frame


_CONSOLE_TEXT = """21:04:13  [INFO]  [01] Normalizacion iniciada: noticias_dia.txt | fuentes: Bio Bio Chile, El Mostrador
21:04:24  [OK]    [01] Normalizacion completada | procesadas: 1195 | normalizadas: 1195 | errores: 0
21:04:25  [INFO]  [02] Enriquecimiento iniciado | diccionario: v2026-06-25 | workers: 4
21:04:33  [INFO]  [02] Enriqueciendo lotes 1/4 (300/1195) ------------------------- 25%
21:04:41  [INFO]  [02] Enriqueciendo lotes 2/4 (600/1195) ------------------------- 50%
21:04:58  [OK]    [02] Enriquecimiento completado | enriquecidas: 1195 | sin match: 87
21:04:59  [INFO]  [03] Descarga CMF iniciada | 4 fondos | tramo: 31 dias
21:05:28  [OK]    [03] Descarga completada | archivos nuevos: 124 | omitidos: 31 | errores: 0
21:05:28  [OK]    Flujo completo finalizado correctamente."""
