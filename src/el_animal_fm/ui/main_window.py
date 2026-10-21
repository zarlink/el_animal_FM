from __future__ import annotations

from collections.abc import Sequence
import codecs
import json
import os
import sys
from datetime import date

from PySide6.QtCore import Qt, QThread, Signal, QProcess, QProcessEnvironment
from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from el_animal_fm.ui.theme.styles import BASE_STYLESHEET
from el_animal_fm.ui.views.dictionary_lab_view import DictionaryLabView
from el_animal_fm.ui.views.live_predictions_view import LivePredictionsView
from el_animal_fm.ui.views.models_view import ModelsView
from el_animal_fm.ui.views.news_enrichment_view import NewsEnrichmentView
from el_animal_fm.ui.views.pipeline_monitor_view import PipelineMonitorView
from el_animal_fm.ui.widgets.header_bar import HeaderBar
from el_animal_fm.ui.services.available_prediction_date import latest_available_prediction_date


class _DateCheck(QThread):
    result = Signal(object, str)

    def run(self) -> None:
        try:
            self.result.emit(latest_available_prediction_date(), "")
        except Exception as exc:
            self.result.emit(None, str(exc))


class MainWindow(QMainWindow):
    """Main shell for the El Animal FM desktop dashboard."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("El Animal FM Dashboard")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)

        self._tabs = QTabBar()
        self._stack = QStackedWidget()
        self._date_check = None
        self._prediction_date = None
        self._prediction_process = QProcess(self)
        self._prediction_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._prediction_process.readyReadStandardOutput.connect(self._read_prediction)
        self._prediction_process.finished.connect(self._prediction_finished)
        self._prediction_process.errorOccurred.connect(self._prediction_error)
        self._prediction_buffer = ""
        self._prediction_result = None
        self._prediction_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(10)

        self._header = HeaderBar()
        root_layout.addWidget(self._header)
        root_layout.addWidget(self._build_navigation())
        root_layout.addWidget(self._build_stack(), stretch=1)

        self.setCentralWidget(root)
        self.setStyleSheet(BASE_STYLESHEET)

    def _build_navigation(self) -> QTabBar:
        self._tabs.setObjectName("MainNavigation")
        self._tabs.setDrawBase(False)
        self._tabs.setExpanding(False)

        for label in _VIEW_LABELS:
            self._tabs.addTab(label)

        return self._tabs

    def _build_stack(self) -> QStackedWidget:
        self._live_view = LivePredictionsView()
        self._stack.addWidget(self._live_view)
        self._stack.addWidget(PipelineMonitorView())
        self._stack.addWidget(NewsEnrichmentView())
        self._stack.addWidget(DictionaryLabView())
        self._stack.addWidget(ModelsView())

        return self._stack

    def _connect_signals(self) -> None:
        self._tabs.currentChanged.connect(self._stack.setCurrentIndex)
        self._header.refresh_date_requested.connect(self._refresh_date)
        self._header.prediction_requested.connect(self._run_prediction)

    def _run_prediction(self) -> None:
        if self._prediction_process.state() != QProcess.ProcessState.NotRunning:
            return
        if self._date_check is not None and self._date_check.isRunning():
            self.statusBar().showMessage("Espera a que termine la comprobación de fecha.")
            return
        self._prediction_buffer = ""
        self._prediction_result = None
        self._prediction_decoder.reset()
        self._header.set_predicting(True)
        self.statusBar().showMessage("Generando predicciones con la configuración de cada fondo…")
        from el_animal_fm.prediction.infrastructure.output_paths import BASE_DIR
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONPATH", str(BASE_DIR / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""))
        self._prediction_process.setProcessEnvironment(environment)
        self._prediction_process.setWorkingDirectory(str(BASE_DIR))
        self._prediction_process.start(sys.executable, ["-u", "-m", "el_animal_fm.ui.services.live_prediction"])

    def _read_prediction(self) -> None:
        self._prediction_buffer += self._prediction_decoder.decode(bytes(self._prediction_process.readAllStandardOutput()))
        lines = self._prediction_buffer.split("\n")
        self._prediction_buffer = lines.pop()
        for line in lines:
            if line.startswith("[LIVE_RESULT] "):
                try:
                    result = json.loads(line[len("[LIVE_RESULT] "):])
                    from el_animal_fm.prediction.application.config.prediction_config import FUND_CONFIG
                    if (result.get("schema_version") != 2
                            or set(result["funds"]) | set(result["errors"]) != set(FUND_CONFIG)
                            or set(result["funds"]) & set(result["errors"])):
                        raise ValueError("Resultado incompleto")
                    date.fromisoformat(result["date"])
                    self._prediction_result = result
                except (ValueError, KeyError, TypeError):
                    self._live_view.append_prediction_log("ERROR: resultado de predicción inválido.")
            elif line.strip():
                self._live_view.append_prediction_log(line)

    def _prediction_finished(self, code: int, status) -> None:
        self._read_prediction()
        self._header.set_predicting(False)
        if code == 0 and status == QProcess.ExitStatus.NormalExit and self._prediction_result is not None:
            result = self._prediction_result
            self._live_view.apply_prediction(result)
            self._prediction_date = date.fromisoformat(result["date"])
            self._header.set_date(self._prediction_date.strftime("%d-%m-%Y"), "Corte de noticias según cada fondo")
            self.statusBar().showMessage(
                f"Predicción terminada · {len(result['funds'])} fondos con señal · "
                f"{len(result['errors'])} pendientes. Revisar consola.")
        else:
            self.statusBar().showMessage("No se pudo completar la predicción. Revisa la consola de Análisis en Directo.")

    def _prediction_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._header.set_predicting(False)
            self.statusBar().showMessage(self._prediction_process.errorString())

    def _refresh_date(self) -> None:
        if self._prediction_process.state() != QProcess.ProcessState.NotRunning:
            return
        if self._date_check is not None and self._date_check.isRunning():
            return
        self._header.set_refreshing(True)
        self.statusBar().showMessage("Comprobando valores CMF y noticias enriquecidas…")
        self._date_check = _DateCheck(self)
        self._date_check.result.connect(self._date_checked)
        self._date_check.finished.connect(lambda: self._header.set_refreshing(False))
        self._date_check.start()

    def _date_checked(self, available, error: str) -> None:
        self._prediction_date = available
        if available is None:
            self._header.set_date("SIN FECHA", error)
            self.statusBar().showMessage(error)
        else:
            detail = "Última fecha común con valores CMF y noticias enriquecidas."
            self._header.set_date(available.strftime("%d-%m-%Y"), detail)
            self.statusBar().showMessage(detail)

    def closeEvent(self, event) -> None:
        if self._prediction_process.state() != QProcess.ProcessState.NotRunning:
            self._prediction_process.kill()
            self._prediction_process.waitForFinished(1000)
        if self._date_check is not None and self._date_check.isRunning():
            self.statusBar().showMessage("Espera a que termine la comprobación de fecha para cerrar.")
            event.ignore()
            return
        super().closeEvent(event)

_VIEW_LABELS: Sequence[str] = (
    "Análisis en Directo",
    "Gestor de Noticias - Monitor",
    "Enriquecedor Noticias",
    "Laboratorio de Palabras",
    "Modelos",
)
