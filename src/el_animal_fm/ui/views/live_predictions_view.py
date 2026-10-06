from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from el_animal_fm.news.application.enrichment.enrichment_config import (
    DEFAULT_DICTIONARY_VERSION,
    DEFAULT_SOURCES,
    FAMILIES,
)
from el_animal_fm.prediction.application.config.prediction_config import (
    FUND_CONFIG,
    FUND_MODEL_CONFIG,
    XGB_MODEL_CONFIG,
)
from el_animal_fm.ui.widgets.entry_score_chart import EntryScoreChart
from el_animal_fm.ui.widgets.event_log_panel import EventLogPanel
from el_animal_fm.ui.widgets.execution_console import ExecutionConsole
from el_animal_fm.ui.widgets.fund_signal_card import FundSignalCard
from el_animal_fm.ui.widgets.section_panel import SectionPanel
from el_animal_fm.ui.widgets.signal_distribution_chart import SignalDistributionChart
from el_animal_fm.ui.widgets.system_status_panel import SystemStatusPanel


class LivePredictionsView(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addLayout(self._build_main_band(), stretch=3)
        layout.addLayout(self._build_bottom_band(), stretch=1)

    def _build_main_band(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        cards_surface = QWidget()
        cards_surface.setObjectName("FundCardsSurface")

        cards = QGridLayout(cards_surface)
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setHorizontalSpacing(10)
        cards.setVerticalSpacing(10)

        for position, (fund_key, configuration) in enumerate(FUND_CONFIG.items()):
            card = FundSignalCard(
                f"{position + 1:02d}", configuration["label"], configuration=configuration,
            )
            card.setProperty("fund_key", fund_key)
            card.set_signal(
                metrics={},
                semaforo="SIN SENAL",
                decision_if_out="Pendiente de predicción",
                decision_if_in="Pendiente de predicción",
            )
            cards.addWidget(card, position // 2, position % 2)

        if not FUND_CONFIG:
            empty = QLabel("No hay fondos configurados.")
            empty.setObjectName("MetricName")
            cards.addWidget(empty, 0, 0, 1, 2)

        cards_scroll = QScrollArea()
        cards_scroll.setObjectName("FundCardsScroll")
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cards_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        cards_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        cards_scroll.setWidget(cards_surface)

        fund_count = len(FUND_CONFIG)
        decision_count = sum(key in FUND_MODEL_CONFIG for key in FUND_CONFIG)
        xgb_count = sum(key in XGB_MODEL_CONFIG for key in FUND_CONFIG)
        status_values = {
            "Fondos Configurados": str(fund_count),
            "Fondos con Configuración de Decisión": f"{decision_count} de {fund_count}",
            "Fondos con Configuración XGBoost": f"{xgb_count} de {fund_count}",
            "Fuentes de Noticias Configuradas": str(len(DEFAULT_SOURCES)),
            "Familias de Enriquecimiento": str(len(FAMILIES)),
            "Versión del Diccionario Configurada": DEFAULT_DICTIONARY_VERSION,
            "Modelos Cargados": "Pendiente",
            "Fondos Analizados": "Pendiente",
            "Señales en VIVO": "Pendiente",
        }
        status = SystemStatusPanel(rows=tuple(status_values))
        status.set_status(status_values)
        status.setToolTip("Fuentes de noticias configuradas: " + ", ".join(DEFAULT_SOURCES))

        status_panel = SectionPanel("Estado General de la Aplicación", status)
        status_panel.setMinimumWidth(270)

        layout.addWidget(cards_scroll, stretch=4)
        layout.addWidget(status_panel, stretch=1)
        return layout

    def _build_bottom_band(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        event_log = EventLogPanel()
        event_log.set_events((f"Configuración cargada: {len(FUND_CONFIG)} fondo(s).",))

        console = ExecutionConsole()
        console.set_lines(("Pendiente de ejecución de predicción.",))

        signal_distribution = SignalDistributionChart()
        signal_distribution.set_rows(())

        entry_score = EntryScoreChart()
        entry_score.set_rows(())

        layout.addWidget(SectionPanel("Log de Eventos", event_log), stretch=2)
        layout.addWidget(SectionPanel("Consola de Ejecución", console), stretch=3)
        layout.addWidget(SectionPanel("Distribución de Señales", signal_distribution), stretch=1)
        layout.addWidget(SectionPanel("Mayores Repeticiones", entry_score), stretch=1)

        return layout
