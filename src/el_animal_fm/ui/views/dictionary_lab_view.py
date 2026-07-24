from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QProcess, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from el_animal_fm.news.application.enrichment.enrichment_config import (
    DEFAULT_DICTIONARY_VERSION,
    DEFAULT_SEED_TERMS,
    FAMILIES,
)
from el_animal_fm.ui.views.news_enrichment_view import NewsEnrichmentView


PROJECT_ROOT = Path(__file__).resolve().parents[4]


class DictionaryLabView(QWidget):
    """Operational UI for the dictionary preparation and enrichment pipeline."""

    def __init__(self) -> None:
        super().__init__()
        self._process = QProcess(self)
        self._active_step: str | None = None
        self._buttons: list[QPushButton] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        workflow = QHBoxLayout()
        workflow.setSpacing(10)
        workflow.addWidget(self._build_unification_panel(), stretch=3)
        workflow.addWidget(self._build_dictionary_panel(), stretch=4)
        workflow.addWidget(self._build_enrichment_panel(), stretch=6)
        layout.addLayout(workflow, stretch=5)
        layout.addWidget(self._build_console(), stretch=2)

        self._process.setWorkingDirectory(str(PROJECT_ROOT))
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_process_output)
        self._process.started.connect(self._process_started)
        self._process.finished.connect(self._process_finished)
        self._process.errorOccurred.connect(self._process_error)

    def _build_unification_panel(self) -> QFrame:
        panel, body = NewsEnrichmentView._build_panel("04", "UNIFICAR NOTICIAS")
        body.addWidget(self._muted_label("Consolida noticias normalizadas en un archivo maestro."))
        body.addWidget(self._field_label("FUENTES DE ENTRADA"))
        summary = QLabel(self._source_summary())
        summary.setObjectName("DictionarySummary")
        summary.setWordWrap(True)
        body.addWidget(summary)

        self._unify_button = self._primary_button("▶  EJECUTAR UNIFICACION")
        self._unify_button.clicked.connect(self._run_unification)
        body.addWidget(self._unify_button)
        body.addWidget(NewsEnrichmentView._separator())
        body.addWidget(self._field_label("PROGRESO EN VIVO"))

        self._unify_progress = QProgressBar()
        self._unify_progress.setObjectName("DictionaryProgress")
        self._unify_progress.setRange(0, 100)
        self._unify_progress.setValue(0)
        self._unify_progress.setFormat("%p%")
        body.addWidget(self._unify_progress)

        self._unify_stage = QLabel("LISTO PARA EJECUTAR")
        self._unify_stage.setObjectName("DictionaryStatus")
        body.addWidget(self._unify_stage)
        body.addStretch(1)
        body.addWidget(NewsEnrichmentView._script_label("04_unificador_noticias_diccionario.py"))
        return panel

    def _build_dictionary_panel(self) -> QFrame:
        panel, body = NewsEnrichmentView._build_panel("05", "CONSTRUIR DICCIONARIO")

        body.addWidget(self._field_label("FUENTE UNIFICADA"))
        self._candidate_input = self._line_edit("noticias_unificadas.txt")
        body.addWidget(self._candidate_input)

        options = QGridLayout()
        options.setHorizontalSpacing(8)
        options.addWidget(self._field_label("WORKERS"), 0, 0)
        options.addWidget(self._field_label("EXCLUIR STOPWORDS"), 0, 1)
        self._candidate_workers = QSpinBox()
        self._candidate_workers.setObjectName("NewsInput")
        self._candidate_workers.setRange(1, 32)
        self._candidate_workers.setValue(4)
        self._stopwords = QCheckBox("ACTIVO")
        self._stopwords.setObjectName("NewsCheck")
        self._stopwords.setChecked(True)
        self._stopwords.setEnabled(False)
        options.addWidget(self._candidate_workers, 1, 0)
        options.addWidget(self._stopwords, 1, 1)
        body.addLayout(options)

        body.addWidget(self._field_label("VISTA PREVIA DE CANDIDATOS"))
        self._candidate_table = QTableWidget(0, 3)
        self._candidate_table.setObjectName("DictionaryTable")
        self._candidate_table.setHorizontalHeaderLabels(("PALABRA", "FRECUENCIA", "ESTADO"))
        self._candidate_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._candidate_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._candidate_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._candidate_table.verticalHeader().setVisible(False)
        self._candidate_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        body.addWidget(self._candidate_table, stretch=1)
        self._load_candidate_preview()

        self._dictionary_button = self._primary_button("▶  GENERAR LISTA DE PALABRAS")
        self._dictionary_button.clicked.connect(self._run_dictionary)
        body.addWidget(self._dictionary_button)
        body.addWidget(self._field_label("ARCHIVO DE SALIDA"))
        self._candidate_output = self._line_edit("candidatos_diccionario.json")
        body.addWidget(self._candidate_output)
        body.addWidget(NewsEnrichmentView._script_label("05_creador_diccionario_adicional.py"))
        return panel

    def _build_enrichment_panel(self) -> QFrame:
        panel, body = NewsEnrichmentView._build_panel("06", "ENRIQUECER NOTICIAS")

        top = QHBoxLayout()
        top.setSpacing(10)

        controls = QVBoxLayout()
        controls.setSpacing(6)
        dates = QGridLayout()
        today = date.today()
        dates.addWidget(self._field_label("DESDE"), 0, 0)
        dates.addWidget(self._field_label("HASTA"), 0, 1)
        self._date_from = self._date_edit(today - timedelta(days=7))
        self._date_to = self._date_edit(today)
        dates.addWidget(self._date_from, 1, 0)
        dates.addWidget(self._date_to, 1, 1)
        controls.addLayout(dates)

        controls.addWidget(self._field_label("FUENTE"))
        self._sources = QComboBox()
        self._sources.setObjectName("NewsInput")
        self._sources.addItems(("AMBAS FUENTES", "BIO BIO CHILE", "EL MOSTRADOR"))
        controls.addWidget(self._sources)

        controls.addWidget(self._field_label("VERSION DE DICCIONARIO"))
        self._dictionary_version = self._line_edit(DEFAULT_DICTIONARY_VERSION)
        controls.addWidget(self._dictionary_version)

        workers_row = QHBoxLayout()
        workers_row.addWidget(self._field_label("WORKERS"))
        self._enrich_workers = QSpinBox()
        self._enrich_workers.setObjectName("NewsInput")
        self._enrich_workers.setRange(1, 32)
        self._enrich_workers.setValue(4)
        workers_row.addWidget(self._enrich_workers)
        controls.addLayout(workers_row)

        self._overwrite = QCheckBox("SOBRESCRIBIR EXISTENTES")
        self._overwrite.setObjectName("NewsCheck")
        controls.addWidget(self._overwrite)
        controls.addStretch(1)
        top.addLayout(controls, stretch=2)

        config = QVBoxLayout()
        config.setSpacing(5)
        config.addWidget(self._field_label("EXPLORADOR ENRICHMENT_CONFIG"))
        self._config_search = QLineEdit()
        self._config_search.setObjectName("NewsInput")
        self._config_search.setPlaceholderText("Buscar termino o categoria...")
        self._config_search.textChanged.connect(self._filter_config)
        config.addWidget(self._config_search)

        self._config_table = QTableWidget(0, 4)
        self._config_table.setObjectName("DictionaryTable")
        self._config_table.setHorizontalHeaderLabels(("TERMINO", "CATEGORIA", "PESO", "ACTIVO"))
        self._config_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._config_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._config_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._config_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._config_table.verticalHeader().setVisible(False)
        self._config_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        config.addWidget(self._config_table, stretch=1)
        config.addWidget(self._muted_label("CODE  news/application/enrichment/enrichment_config.py"))
        top.addLayout(config, stretch=5)
        body.addLayout(top, stretch=1)

        self._load_config_terms()
        self._enrich_button = self._primary_button("▶  EJECUTAR ENRIQUECIMIENTO")
        self._enrich_button.clicked.connect(self._run_enrichment)
        body.addWidget(self._enrich_button)
        body.addWidget(NewsEnrichmentView._script_label("06_enriquecer_noticias.py"))
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
        stop.clicked.connect(self._stop_process)
        clear = self._secondary_button("LIMPIAR CONSOLA")
        toolbar.addWidget(stop)
        toolbar.addWidget(clear)
        layout.addLayout(toolbar)

        self._console = QTextEdit()
        self._console.setObjectName("NewsConsole")
        self._console.setReadOnly(True)
        self._console.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._console.setPlainText(
            "[READY] Dictionary Lab preparado.\n"
            "[INFO] Ejecute los pasos 04, 05 y 06 de forma secuencial."
        )
        clear.clicked.connect(self._console.clear)
        layout.addWidget(self._console, stretch=1)
        return panel

    def _run_unification(self) -> None:
        self._unify_progress.setRange(0, 0)
        self._unify_stage.setText("UNIFICANDO FUENTES · EN PROCESO")
        self._start_process("04", PROJECT_ROOT / "04_unificador_noticias_diccionario.py", [])

    def _run_dictionary(self) -> None:
        args = [
            "--input", self._candidate_input.text().strip(),
            "--output", self._candidate_output.text().strip(),
            "--record-workers", str(self._candidate_workers.value()),
        ]
        self._start_process("05", PROJECT_ROOT / "05_creador_diccionario_adicional.py", args)

    def _run_enrichment(self) -> None:
        source_map = {
            "AMBAS FUENTES": ["biobio", "mostrador"],
            "BIO BIO CHILE": ["biobio"],
            "EL MOSTRADOR": ["mostrador"],
        }
        args = [
            "--date-from", self._date_from.date().toString("yyyy-MM-dd"),
            "--date-to", self._date_to.date().toString("yyyy-MM-dd"),
            "--sources", *source_map[self._sources.currentText()],
            "--dictionary-version", self._dictionary_version.text().strip(),
            "--workers", str(self._enrich_workers.value()),
        ]
        if self._overwrite.isChecked():
            args.append("--overwrite")
        self._start_process("06", PROJECT_ROOT / "06_enriquecer_noticias.py", args)

    def _start_process(self, step: str, script: Path, args: list[str]) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._append_console("[WARN] Ya existe un proceso en ejecucion.")
            return
        self._active_step = step
        self._append_console(f"\n[INFO] [{step}] Iniciando {script.name}")
        self._set_buttons_enabled(False)
        self._process.start(sys.executable, [str(script), *args])

    def _process_started(self) -> None:
        self._append_console(f"[INFO] [{self._active_step}] Proceso iniciado.")

    def _read_process_output(self) -> None:
        output = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if output:
            self._append_console(output.rstrip())

    def _process_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        step = self._active_step or "--"
        if step == "04":
            self._unify_progress.setRange(0, 100)
            self._unify_progress.setValue(100 if exit_code == 0 else 0)
            self._unify_stage.setText("COMPLETADO · OK" if exit_code == 0 else "ERROR")
        if step == "05" and exit_code == 0:
            self._load_candidate_preview()
        status = "OK" if exit_code == 0 else f"ERROR {exit_code}"
        self._append_console(f"[{status}] [{step}] Proceso finalizado.")
        self._active_step = None
        self._set_buttons_enabled(True)

    def _process_error(self, error: QProcess.ProcessError) -> None:
        self._append_console(f"[ERROR] No fue posible ejecutar el proceso: {error.name}")
        self._set_buttons_enabled(True)

    def _stop_process(self) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            self._append_console("[INFO] No hay procesos activos.")
            return
        self._append_console(f"[WARN] [{self._active_step}] Deteniendo proceso...")
        self._process.terminate()

    def _load_candidate_preview(self) -> None:
        path = PROJECT_ROOT / "candidatos_diccionario.json"
        rows: list[tuple[str, str]] = []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = self._extract_candidate_rows(payload)
        except (OSError, json.JSONDecodeError):
            rows = []
        self._candidate_table.setRowCount(len(rows[:8]))
        for row, (term, frequency) in enumerate(rows[:8]):
            self._candidate_table.setItem(row, 0, QTableWidgetItem(term))
            self._candidate_table.setItem(row, 1, QTableWidgetItem(frequency))
            self._candidate_table.setItem(row, 2, QTableWidgetItem("● LISTA"))

    @staticmethod
    def _extract_candidate_rows(payload: object) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []

        def visit(value: object) -> None:
            if len(found) >= 20:
                return
            if isinstance(value, dict):
                term = value.get("term") or value.get("palabra") or value.get("token")
                freq = value.get("frequency") or value.get("frecuencia") or value.get("count")
                if isinstance(term, str) and isinstance(freq, (int, float)):
                    found.append((term, f"{freq:,.0f}".replace(",", ".")))
                for nested in value.values():
                    visit(nested)
            elif isinstance(value, list):
                for nested in value:
                    visit(nested)

        visit(payload)
        return found

    def _load_config_terms(self) -> None:
        rows = [
            (term.replace("_", " "), family, weight)
            for family in FAMILIES
            for term, weight in DEFAULT_SEED_TERMS.get(family, {}).items()
        ]
        self._config_table.setRowCount(len(rows))
        for row, (term, family, weight) in enumerate(rows):
            self._config_table.setItem(row, 0, QTableWidgetItem(term))
            self._config_table.setItem(row, 1, QTableWidgetItem(family.upper()))
            self._config_table.setItem(row, 2, QTableWidgetItem(f"{weight:.2f}"))
            self._config_table.setItem(row, 3, QTableWidgetItem("● SI"))

    def _filter_config(self, query: str) -> None:
        needle = query.strip().casefold()
        for row in range(self._config_table.rowCount()):
            haystack = " ".join(
                self._config_table.item(row, column).text()
                for column in (0, 1)
                if self._config_table.item(row, column) is not None
            ).casefold()
            self._config_table.setRowHidden(row, bool(needle and needle not in haystack))

    def _source_summary(self) -> str:
        files = 0
        articles = 0
        for media in ("biobio", "mostrador"):
            paths = list((PROJECT_ROOT / media).glob("*/noticias_dia.txt"))
            files += len(paths)
            for path in paths:
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    articles += len(payload.get("articles", [])) if isinstance(payload, dict) else 0
                except (OSError, json.JSONDecodeError):
                    continue
        return f"▣  {files} archivos normalizados\n    {articles:,} noticias".replace(",", ".")

    def _set_buttons_enabled(self, enabled: bool) -> None:
        for button in self._buttons:
            button.setEnabled(enabled)

    def _append_console(self, text: str) -> None:
        self._console.append(text)
        self._console.verticalScrollBar().setValue(self._console.verticalScrollBar().maximum())

    def _primary_button(self, text: str) -> QPushButton:
        button = NewsEnrichmentView._primary_button(text)
        self._buttons.append(button)
        return button

    @staticmethod
    def _secondary_button(text: str) -> QPushButton:
        return NewsEnrichmentView._secondary_button(text)

    @staticmethod
    def _field_label(text: str) -> QLabel:
        return NewsEnrichmentView._field_label(text)

    @staticmethod
    def _line_edit(text: str) -> QLineEdit:
        return NewsEnrichmentView._line_edit(text)

    @staticmethod
    def _date_edit(value: date) -> QDateEdit:
        field = QDateEdit(QDate(value.year, value.month, value.day))
        field.setObjectName("NewsInput")
        field.setCalendarPopup(True)
        field.setDisplayFormat("yyyy-MM-dd")
        return field

    @staticmethod
    def _muted_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("DictionaryMuted")
        label.setWordWrap(True)
        return label
