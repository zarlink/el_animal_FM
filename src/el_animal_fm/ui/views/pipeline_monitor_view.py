from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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


class PipelineMonitorView(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addLayout(self._build_control_band())
        layout.addWidget(self._build_console(), stretch=1)

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

        biobio = QCheckBox("BIO BIO CHILE")
        biobio.setObjectName("PipelineCheck")
        biobio.setChecked(True)
        mostrador = QCheckBox("EL MOSTRADOR")
        mostrador.setObjectName("PipelineCheck")
        mostrador.setChecked(True)

        body.addWidget(biobio, 1, 0, 1, 2)
        body.addWidget(mostrador, 2, 0, 1, 2)

        days_label = QLabel("CANTIDAD DE DIAS")
        days_label.setObjectName("PipelineFieldLabel")
        days = QSpinBox()
        days.setObjectName("PipelineInput")
        days.setRange(1, 30)
        days.setValue(3)

        include_today = QCheckBox("INCLUIR HOY")
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
        range_value = QLabel("DESDE: 2026-06-23    HASTA: 2026-06-25")
        range_value.setObjectName("PipelineValue")

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

        pause_label = QLabel("PAUSA ENTRE REQUESTS (SEC)")
        pause_label.setObjectName("PipelineFieldLabel")
        pause = QDoubleSpinBox()
        pause.setObjectName("PipelineInput")
        pause.setRange(0.0, 10.0)
        pause.setSingleStep(0.1)
        pause.setValue(0.5)

        cache_label = QLabel("USAR CACHE")
        cache_label.setObjectName("PipelineFieldLabel")
        cache = QCheckBox("ACTIVADO")
        cache.setObjectName("PipelineCheck")
        cache.setChecked(True)

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

        start = QPushButton("INICIAR DESCARGA")
        start.setObjectName("PipelinePrimaryButton")
        stop = QPushButton("DETENER")
        stop.setObjectName("PipelineButton")
        clear = QPushButton("LIMPIAR CONSOLA")
        clear.setObjectName("PipelineButton")

        for button in (start, stop, clear):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(42)
            body.addWidget(button)

        body.addStretch(1)
        panel.layout().addLayout(body)
        return panel

    def _build_console(self) -> QFrame:
        panel = self._build_inner_panel("CONSOLA DE EJECUCION")

        console = QTextEdit()
        console.setObjectName("PipelineConsole")
        console.setReadOnly(True)
        console.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        console.setPlainText(_CONSOLE_TEXT)

        panel.layout().addWidget(console, stretch=1)
        return panel

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


_CONSOLE_TEXT = """================================================================================
DESCARGA DE NOTICIAS - BIO BIO CHILE Y EL MOSTRADOR
================================================================================
[INFO] Iniciando descarga de noticias...
[INFO] Rango de fechas: 2026-06-23 a 2026-06-25 (3 dias)
[INFO] Fuentes seleccionadas: Bio Bio Chile, El Mostrador

--------------------------------------------------------------------------------
[1/2] BIO BIO CHILE
--------------------------------------------------------------------------------
[INFO] Descargando noticias de Bio Bio Chile...
[INFO] Procesando dia: 2026-06-23
  - Sitemap:    OK  (28 articulos)
  - Lo Ultimo:  OK  (34 articulos)
  - Categorias: OK  (95 articulos)     Total dia 2026-06-23: 257 articulos
[INFO] Procesando dia: 2026-06-24
  - Sitemap:    OK  (130 articulos)
  - Lo Ultimo:  OK  (36 articulos)
  - Categorias: OK  (96 articulos)     Total dia 2026-06-24: 262 articulos
[INFO] Procesando dia: 2026-06-25
  - Sitemap:    OK  (123 articulos)
  - Lo Ultimo:  OK  (35 articulos)
  - Categorias: OK  (96 articulos)     Total dia 2026-06-25: 249 articulos
[OK] Bio Bio Chile completado. Total: 768 articulos

--------------------------------------------------------------------------------
[2/2] EL MOSTRADOR
--------------------------------------------------------------------------------
[INFO] Descargando noticias de El Mostrador...
[INFO] Procesando dia: 2026-06-23
  - /dia/:      OK  (74 articulos)
  - Secciones:  OK  (31 articulos)     Total dia 2026-06-23: 147 articulos
[INFO] Procesando dia: 2026-06-24
  - /dia/:      OK  (70 articulos)
  - Secciones:  OK  (29 articulos)     Total dia 2026-06-24: 140 articulos
[INFO] Procesando dia: 2026-06-25
  - /dia/:      OK  (71 articulos)
  - Secciones:  OK  (29 articulos)     Total dia 2026-06-25: 140 articulos
[OK] El Mostrador completado. Total: 427 articulos

[OK] DESCARGA DE NOTICIAS COMPLETADA
[OK] Total articulos descargados: 1195
[OK] Tiempo total: 00:01:47
================================================================================"""
