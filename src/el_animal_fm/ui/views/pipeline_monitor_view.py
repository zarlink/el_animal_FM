from __future__ import annotations

import codecs
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from el_animal_fm.news.infrastructure.dates import today_chile

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class PipelineMonitorView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._process = QProcess(self)
        self._stopping = False
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addLayout(self._build_control_band())
        layout.addWidget(self._build_console(), stretch=1)
        self._process.setWorkingDirectory(str(PROJECT_ROOT))
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        environment = QProcessEnvironment.systemEnvironment()
        source_path = str(PROJECT_ROOT / "src")
        existing_path = environment.value("PYTHONPATH")
        environment.insert("PYTHONPATH", source_path + (os.pathsep + existing_path if existing_path else ""))
        environment.insert("PYTHONIOENCODING", "utf-8")
        self._process.setProcessEnvironment(environment)
        self._process.readyReadStandardOutput.connect(self._read_process_output)
        self._process.finished.connect(self._process_finished)
        self._process.errorOccurred.connect(self._process_error)
        self._process.started.connect(lambda: self._log("[INFO] Proceso de descarga iniciado."))
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self._kill_process)
        self._range_timer = QTimer(self)
        self._range_timer.timeout.connect(self._update_date_range)
        self._range_timer.start(60_000)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown)
        self._update_date_range()

    def _build_control_band(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        layout.addWidget(self._build_execution_config(), stretch=2)
        layout.addWidget(self._build_options(), stretch=1)
        layout.addWidget(self._build_actions(), stretch=1)
        return layout

    def _build_execution_config(self) -> QFrame:
        panel = self._build_inner_panel("CONFIGURACION DE EJECUCION")

        body = QGridLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setHorizontalSpacing(16)
        body.setVerticalSpacing(10)

        source_title = QLabel("FUENTE DE NOTICIAS")
        source_title.setObjectName("PipelineFieldLabel")
        body.addWidget(source_title, 0, 0, 1, 2)

        self._biobio = biobio = QCheckBox("BIO BIO CHILE")
        biobio.setObjectName("PipelineCheck")
        biobio.setChecked(True)
        self._mostrador = mostrador = QCheckBox("EL MOSTRADOR")
        mostrador.setObjectName("PipelineCheck")
        mostrador.setChecked(True)

        body.addWidget(biobio, 1, 0, 1, 2)
        body.addWidget(mostrador, 2, 0, 1, 2)

        days_label = QLabel("CANTIDAD DE DIAS")
        days_label.setObjectName("PipelineFieldLabel")
        self._days = days = QSpinBox()
        days.setObjectName("PipelineInput")
        days.setRange(1, 30)
        days.setValue(3)

        self._include_today = include_today = QCheckBox("INCLUIR HOY")
        include_today.setObjectName("PipelineCheck")
        include_today.setChecked(True)

        body.addWidget(days_label, 0, 2)
        body.addWidget(days, 1, 2)
        body.addWidget(include_today, 2, 2)

        separator = QFrame()
        separator.setObjectName("PipelineSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        body.addWidget(separator, 3, 0, 1, 3)

        range_title = QLabel("RANGO ESTIMADO")
        range_title.setObjectName("PipelineFieldLabel")
        self._range_value = range_value = QLabel()
        range_value.setObjectName("PipelineValue")
        days.valueChanged.connect(self._update_date_range)
        include_today.toggled.connect(self._update_date_range)

        body.addWidget(range_title, 4, 0, 1, 3)
        body.addWidget(range_value, 5, 0, 1, 3)

        panel.layout().addLayout(body)
        return panel

    def _build_options(self) -> QFrame:
        panel = self._build_inner_panel("OPCIONES")

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)

        dedupe_label = QLabel("DEDUPLICACION")
        dedupe_label.setObjectName("PipelineFieldLabel")
        dedupe = QCheckBox("ACTIVADA")
        dedupe.setObjectName("PipelineCheck")
        dedupe.setChecked(True)
        dedupe.setEnabled(False)
        dedupe.setToolTip("El motor siempre evita guardar noticias duplicadas por URL.")

        pause_label = QLabel("PAUSA ENTRE NOTICIAS (SEC)")
        pause_label.setObjectName("PipelineFieldLabel")
        self._pause = pause = QDoubleSpinBox()
        pause.setObjectName("PipelineInput")
        pause.setRange(0.0, 10.0)
        pause.setSingleStep(0.1)
        pause.setValue(0.5)

        cache_label = QLabel("CONSERVAR NOTICIAS EXISTENTES")
        cache_label.setObjectName("PipelineFieldLabel")
        self._keep_existing = cache = QCheckBox("ACTIVADO")
        cache.setObjectName("PipelineCheck")
        cache.setChecked(True)
        cache.setToolTip("Conserva las noticias guardadas y descarga solo URLs nuevas. Desactivado: redescarga el día.")

        for widget in (dedupe_label, dedupe, pause_label, pause, cache_label, cache):
            body.addWidget(widget)

        body.addStretch(1)
        panel.layout().addLayout(body)
        return panel

    def _build_actions(self) -> QFrame:
        panel = self._build_inner_panel("ACCION")

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        self._start = start = QPushButton("INICIAR DESCARGA")
        start.setObjectName("PipelinePrimaryButton")
        self._stop = stop = QPushButton("DETENER")
        stop.setObjectName("PipelineButton")
        self._clear = clear = QPushButton("LIMPIAR CONSOLA")
        clear.setObjectName("PipelineButton")
        start.clicked.connect(self._start_download)
        stop.clicked.connect(self._stop_download)
        clear.clicked.connect(self._clear_console)
        stop.setEnabled(False)

        for button in (start, stop, clear):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(42)
            body.addWidget(button)

        body.addStretch(1)
        panel.layout().addLayout(body)
        return panel

    def _build_console(self) -> QFrame:
        panel = self._build_inner_panel("CONSOLA DE EJECUCION")

        self._console = console = QTextEdit()
        console.setObjectName("PipelineConsole")
        console.setReadOnly(True)
        console.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        console.setPlainText("[INFO] Listo para iniciar una descarga.")
        console.document().setMaximumBlockCount(10_000)

        panel.layout().addWidget(console, stretch=1)
        return panel

    def _date_range(self) -> tuple[date, date]:
        end = today_chile()
        if not self._include_today.isChecked():
            end -= timedelta(days=1)
        return end - timedelta(days=self._days.value() - 1), end

    def _update_date_range(self) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            return
        start, end = self._date_range()
        self._range_value.setText(f"DESDE: {start.isoformat()}    HASTA: {end.isoformat()}")

    def _command_arguments(self, sources: list[str], end_date: str) -> list[str]:
        args = [
            "-u", "-m", "el_animal_fm.cli.download_news",
            "--sources", *sources,
            "--date", end_date,
            "--days-back", str(self._days.value()),
            "--base-dir", str(PROJECT_ROOT),
            "--sleep", str(self._pause.value()),
        ]
        if not self._keep_existing.isChecked():
            args.append("--overwrite-existing")
        return args

    def _start_download(self) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            return
        sources = [name for name, control in (
            ("biobio", self._biobio), ("mostrador", self._mostrador),
        ) if control.isChecked()]
        if not sources:
            self._log("[WARN] Selecciona al menos una fuente de noticias.")
            return
        self._update_date_range()
        start, end = self._date_range()
        self._stopping = False
        self._decoder.reset()
        self._log(f"[INFO] Iniciando descarga: {', '.join(sources)}.")
        self._log(f"[INFO] Rango: {start.isoformat()} a {end.isoformat()} ({self._days.value()} días).")
        self._log(f"[INFO] Pausa: {self._pause.value()} s. Conservar noticias existentes: {self._keep_existing.isChecked()}.")
        self._set_running(True)
        self._process.start(sys.executable, self._command_arguments(sources, end.isoformat()))

    def _set_running(self, running: bool) -> None:
        self._start.setEnabled(not running)
        self._stop.setEnabled(running)
        for control in (self._biobio, self._mostrador, self._days, self._include_today, self._pause, self._keep_existing):
            control.setEnabled(not running)

    def _append_console(self, text: str) -> None:
        cursor = self._console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._console.setTextCursor(cursor)
        self._console.ensureCursorVisible()

    def _log(self, message: str) -> None:
        if self._console.toPlainText() and not self._console.toPlainText().endswith("\n"):
            self._append_console("\n")
        self._append_console(message + "\n")

    def _read_process_output(self) -> None:
        output = self._decoder.decode(bytes(self._process.readAllStandardOutput()))
        if output:
            self._append_console(output)

    def _process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._kill_timer.stop()
        self._read_process_output()
        self._append_console(self._decoder.decode(b"", final=True))
        if self._stopping:
            self._log("[INFO] Descarga detenida.")
        elif exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0:
            self._log("[OK] Descarga completada.")
        else:
            self._log(f"[ERROR] Descarga finalizada con errores (código {exit_code}). Revisa la salida anterior.")
        self._stopping = False
        self._set_running(False)
        self._update_date_range()

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if self._stopping and error == QProcess.ProcessError.Crashed:
            return
        self._log(f"[ERROR] Proceso de descarga: {self._process.errorString()}")
        if error == QProcess.ProcessError.FailedToStart:
            self._set_running(False)

    def _stop_download(self) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning or self._stopping:
            return
        self._stopping = True
        self._stop.setEnabled(False)
        self._log("[INFO] Deteniendo descarga...")
        self._process.terminate()
        self._kill_timer.start(3_000)

    def _kill_process(self) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()

    def _clear_console(self) -> None:
        self._console.clear()

    def _shutdown(self) -> None:
        self._kill_timer.stop()
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._stopping = True
            self._process.kill()
            self._process.waitForFinished(1_000)

    def _build_inner_panel(self, title_text: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PipelineInnerPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)

        title = QLabel(title_text)
        title.setObjectName("PipelinePanelTitle")
        layout.addWidget(title)

        separator = QFrame()
        separator.setObjectName("PipelineSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(separator)

        return panel
