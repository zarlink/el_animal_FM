from __future__ import annotations

import codecs
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QProcess, QTimer, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
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

from el_animal_fm.news.application.enrichment.enrichment_config import (
    DEFAULT_DICTIONARY_VERSION, DEFAULT_INPUT_NAME, DEFAULT_OUTPUT_NAME,
)
from el_animal_fm.news.infrastructure.dates import today_chile
from el_animal_fm.ui.widgets.calendar_date_edit import CalendarDateEdit


PROJECT_ROOT = Path(__file__).resolve().parents[4]


class NewsEnrichmentView(QWidget):
    """Operational layout for normalization, enrichment and CMF downloads."""

    def __init__(self) -> None:
        super().__init__()
        self._process = QProcess(self)
        self._active_step: str | None = None
        self._stopping = False
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._output_buffer = ""

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
        self._process.setWorkingDirectory(str(PROJECT_ROOT))
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_process_output)
        self._process.finished.connect(self._process_finished)
        self._process.errorOccurred.connect(self._process_error)
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._process.kill)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown)

    def _build_normalization_panel(self) -> QFrame:
        panel, body = self._build_panel("01", "NORMALIZAR NOTICIAS")

        body.addWidget(self._field_label("FUENTES"))
        source_row = QHBoxLayout()
        source_row.setSpacing(12)
        self._normal_biobio = self._checkbox("BIO BIO CHILE", checked=True)
        self._normal_mostrador = self._checkbox("EL MOSTRADOR", checked=True)
        source_row.addWidget(self._normal_biobio)
        source_row.addWidget(self._normal_mostrador)
        source_row.addStretch(1)
        body.addLayout(source_row)

        body.addWidget(self._field_label("ARCHIVO DE ENTRADA"))
        self._normal_input = self._line_edit(DEFAULT_INPUT_NAME)
        body.addWidget(self._normal_input)
        body.addWidget(self._field_label("TODOS LOS DIAS DESCARGADOS"))

        self._normal_overwrite = overwrite = self._checkbox("SOBRESCRIBIR ORIGINAL", checked=True)
        body.addWidget(overwrite)

        body.addWidget(self._field_label("ARCHIVO DE SALIDA (ALTERNATIVO)"))
        self._normal_output = self._line_edit("noticias_dia_normalizado.txt")
        self._normal_output.setEnabled(False)
        overwrite.toggled.connect(lambda checked: self._normal_output.setEnabled(not checked))
        body.addWidget(self._normal_output)

        body.addWidget(self._separator())
        body.addWidget(self._field_label("ESTADO (ARCHIVOS DIARIOS)"))
        stats = QGridLayout()
        stats.setSpacing(6)
        self._normal_stats: dict[str, QLabel] = {}
        for column, (key, label) in enumerate((
            ("total", "TOTAL"), ("processed", "PROCESADOS"),
            ("normalized", "NORMALIZADOS"), ("errors", "ERRORES"),
        )):
            stat = self._stat(label, "--", error=key == "errors")
            self._normal_stats[key] = stat.findChild(QLabel, "NewsStatValue")
            stats.addWidget(stat, 0, column)
        self._normal_status = self._field_label("PENDIENTE")
        body.addWidget(self._normal_status)
        body.addLayout(stats)
        body.addStretch(1)
        self._normal_button = self._primary_button("▶  EJECUTAR NORMALIZACION")
        self._normal_button.clicked.connect(self._run_normalization)
        body.addWidget(self._normal_button)
        body.addWidget(self._script_label("03_normalizador_noticias.py"))
        return panel

    def _build_enrichment_panel(self) -> QFrame:
        panel, body = self._build_panel("02", "ENRIQUECER NOTICIAS")

        dates = QGridLayout()
        dates.setHorizontalSpacing(10)
        dates.setVerticalSpacing(5)
        end_date = today_chile()
        dates.addWidget(self._field_label("DESDE"), 0, 0)
        dates.addWidget(self._field_label("HASTA"), 0, 1)
        self._date_from = self._date_edit(end_date - timedelta(days=2))
        self._date_to = self._date_edit(end_date)
        dates.addWidget(self._date_from, 1, 0)
        dates.addWidget(self._date_to, 1, 1)
        body.addLayout(dates)

        options = QGridLayout()
        options.setHorizontalSpacing(10)
        options.setVerticalSpacing(6)
        options.addWidget(self._field_label("FUENTE"), 0, 0)
        self._sources = source = QComboBox()
        source.setObjectName("NewsInput")
        source.addItems(("AMBAS FUENTES", "BIO BIO CHILE", "EL MOSTRADOR"))
        options.addWidget(source, 1, 0)
        options.addWidget(self._field_label("WORKERS"), 0, 1)
        self._workers = workers = QSpinBox()
        workers.setObjectName("NewsInput")
        workers.setRange(1, 32)
        workers.setValue(4)
        options.addWidget(workers, 1, 1)
        body.addLayout(options)

        body.addWidget(self._field_label("VERSION DE DICCIONARIO"))
        self._dictionary_version = self._line_edit(DEFAULT_DICTIONARY_VERSION)
        body.addWidget(self._dictionary_version)

        toggle_row = QHBoxLayout()
        self._use_candidates = self._checkbox("USAR CANDIDATOS", checked=True)
        self._enrich_overwrite = self._checkbox("SOBRESCRIBIR")
        toggle_row.addWidget(self._use_candidates)
        toggle_row.addWidget(self._enrich_overwrite)
        body.addLayout(toggle_row)

        files = QGridLayout()
        files.setHorizontalSpacing(10)
        files.setVerticalSpacing(5)
        files.addWidget(self._field_label("ARCHIVO DE ENTRADA"), 0, 0)
        files.addWidget(self._field_label("ARCHIVO DE SALIDA"), 0, 1)
        self._enrich_input = self._line_edit(DEFAULT_INPUT_NAME)
        self._enrich_output = self._line_edit(DEFAULT_OUTPUT_NAME)
        files.addWidget(self._enrich_input, 1, 0)
        files.addWidget(self._enrich_output, 1, 1)
        body.addLayout(files)

        body.addStretch(1)
        self._enrich_status = self._field_label("PENDIENTE")
        body.addWidget(self._enrich_status)
        self._enrich_button = self._primary_button("▶  EJECUTAR ENRIQUECIMIENTO")
        self._enrich_button.clicked.connect(self._run_enrichment)
        body.addWidget(self._enrich_button)
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

        self._stop = stop = self._secondary_button("DETENER")
        stop.setEnabled(False)
        stop.clicked.connect(self._stop_process)
        clear = self._secondary_button("LIMPIAR CONSOLA")
        toolbar.addWidget(stop)
        toolbar.addWidget(clear)
        layout.addLayout(toolbar)

        self._console = console = QTextEdit()
        console.setObjectName("NewsConsole")
        console.setReadOnly(True)
        console.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        console.setPlainText("[INFO] Listo para normalizar o enriquecer noticias.")
        console.document().setMaximumBlockCount(10_000)
        clear.clicked.connect(console.clear)
        layout.addWidget(console, stretch=1)
        return panel

    @staticmethod
    def _file_name(field: QLineEdit) -> str:
        name = field.text().strip()
        if not name or Path(name).name != name or name in {".", ".."}:
            raise ValueError("Indica nombres de archivo sin directorios para la entrada y salida.")
        return name

    def _normalization_arguments(self) -> list[str]:
        sources = [source for source, control in (
            ("biobio", self._normal_biobio), ("mostrador", self._normal_mostrador),
        ) if control.isChecked()]
        if not sources:
            raise ValueError("Selecciona al menos una fuente para normalizar.")
        input_name = self._file_name(self._normal_input)
        args = ["--base-dir", str(PROJECT_ROOT), "--media", *sources,
                "--input-name", input_name, "--progress-json"]
        if not self._normal_overwrite.isChecked():
            output_name = self._file_name(self._normal_output)
            if input_name == output_name:
                raise ValueError("El archivo alternativo debe ser distinto del original.")
            args.extend(["--no-overwrite", "--output-name", output_name])
        return args

    def _enrichment_arguments(self) -> list[str]:
        if self._date_from.date() > self._date_to.date():
            raise ValueError("La fecha inicial no puede ser posterior a la fecha final.")
        version = self._dictionary_version.text().strip()
        if not version:
            raise ValueError("Indica una versión de diccionario.")
        input_name = self._file_name(self._enrich_input)
        output_name = self._file_name(self._enrich_output)
        if input_name == output_name:
            raise ValueError("El archivo enriquecido debe ser distinto del archivo de entrada.")
        sources = (("biobio", "mostrador"), ("biobio",), ("mostrador",))[self._sources.currentIndex()]
        args = [
            "--base-dir", str(PROJECT_ROOT), "--sources", *sources,
            "--date-from", self._date_from.date().toString("yyyy-MM-dd"),
            "--date-to", self._date_to.date().toString("yyyy-MM-dd"),
            "--workers", str(self._workers.value()), "--dictionary-version", version,
            "--input-name", input_name, "--output-name", output_name,
        ]
        if self._enrich_overwrite.isChecked():
            args.append("--overwrite")
        if not self._use_candidates.isChecked():
            args.append("--no-candidates")
        return args

    def _run_normalization(self) -> None:
        try:
            args = self._normalization_arguments()
        except ValueError as exc:
            self._append_console(f"[WARN] {exc}\n")
            return
        self._start_process("normalización", PROJECT_ROOT / "03_normalizador_noticias.py", args)

    def _run_enrichment(self) -> None:
        try:
            args = self._enrichment_arguments()
        except ValueError as exc:
            self._append_console(f"[WARN] {exc}\n")
            return
        self._start_process("enriquecimiento", PROJECT_ROOT / "06_enriquecer_noticias.py", args)

    def _start_process(self, step: str, script: Path, args: list[str]) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._append_console("[WARN] Ya hay un proceso en ejecución.\n")
            return
        self._active_step = step
        self._stopping = False
        self._decoder.reset()
        self._output_buffer = ""
        if step == "normalización":
            for label in self._normal_stats.values():
                label.setText("0")
        self._step_status().setText("EN EJECUCION")
        self._set_running(True)
        self._append_console(f"\n[INFO] Iniciando {step}.\n")
        self._process.start(sys.executable, ["-u", "-X", "utf8", str(script), *args])

    def _step_status(self) -> QLabel:
        return self._normal_status if self._active_step == "normalización" else self._enrich_status

    def _set_running(self, running: bool) -> None:
        self._normal_button.setEnabled(not running)
        self._enrich_button.setEnabled(not running)
        self._stop.setEnabled(running)
        for control in (
            self._normal_biobio, self._normal_mostrador, self._normal_input,
            self._normal_overwrite, self._date_from, self._date_to, self._sources,
            self._workers, self._dictionary_version, self._use_candidates,
            self._enrich_overwrite, self._enrich_input, self._enrich_output,
        ):
            control.setEnabled(not running)
        self._normal_output.setEnabled(not running and not self._normal_overwrite.isChecked())

    def _append_console(self, text: str) -> None:
        cursor = self._console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._console.setTextCursor(cursor)
        self._console.ensureCursorVisible()

    def _consume_output(self, output: str, *, final: bool = False) -> None:
        self._output_buffer += output
        lines = self._output_buffer.split("\n")
        self._output_buffer = lines.pop()
        if final and self._output_buffer:
            lines.append(self._output_buffer)
            self._output_buffer = ""
        for line in lines:
            prefix = "[NORMALIZATION_PROGRESS] "
            if line.startswith(prefix):
                try:
                    counters = json.loads(line[len(prefix):])
                    for key, label in self._normal_stats.items():
                        label.setText(str(counters[key]))
                except (ValueError, KeyError, TypeError):
                    self._append_console("[WARN] No se pudo leer el progreso de normalización.\n")
            else:
                self._append_console(line + "\n")

    def _read_process_output(self) -> None:
        self._consume_output(self._decoder.decode(bytes(self._process.readAllStandardOutput())))

    def _process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._kill_timer.stop()
        self._read_process_output()
        self._consume_output(self._decoder.decode(b"", final=True), final=True)
        if self._stopping:
            status, message = "DETENIDO", f"[INFO] {self._active_step}: proceso detenido."
        elif exit_code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            status, message = "TERMINADO", f"[OK] {self._active_step}: proceso terminado."
        else:
            status, message = "ERROR", f"[ERROR] {self._active_step}: código {exit_code}. Revisa la salida anterior."
        self._step_status().setText(status)
        self._append_console(message + "\n")
        self._active_step = None
        self._stopping = False
        self._set_running(False)

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if self._stopping and error == QProcess.ProcessError.Crashed:
            return
        self._append_console(f"[ERROR] {self._process.errorString()}\n")
        if error == QProcess.ProcessError.FailedToStart:
            self._step_status().setText("ERROR")
            self._active_step = None
            self._set_running(False)

    def _stop_process(self) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning or self._stopping:
            return
        self._stopping = True
        self._stop.setEnabled(False)
        self._append_console(f"[INFO] Deteniendo {self._active_step}...\n")
        self._process.terminate()
        self._kill_timer.start(3_000)

    def _shutdown(self) -> None:
        self._kill_timer.stop()
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._stopping = True
            self._process.kill()
            self._process.waitForFinished(1_000)

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
