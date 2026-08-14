from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from el_animal_fm.ui.dev.mock_dashboard_data import (
    MOCK_CONSOLE_LINES,
    MOCK_ENTRY_SCORE_MAP,
    MOCK_EVENT_LOG,
    MOCK_FUND_SIGNALS,
    MOCK_SIGNAL_DISTRIBUTION,
    MOCK_SYSTEM_STATUS,
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

        for position, signal in enumerate(MOCK_FUND_SIGNALS):
            card = FundSignalCard(signal.index, signal.title)
            card.set_signal(
                metrics=signal.metrics,
                semaforo=signal.semaforo,
                decision_if_out=signal.decision_if_out,
                decision_if_in=signal.decision_if_in,
            )
            cards.addWidget(card, position // 2, position % 2)

        cards_scroll = QScrollArea()
        cards_scroll.setObjectName("FundCardsScroll")
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cards_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        cards_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        cards_scroll.setWidget(cards_surface)

        status = SystemStatusPanel()
        status.set_status(MOCK_SYSTEM_STATUS)

        status_panel = SectionPanel("Estado General de la Aplicación", status)
        status_panel.setMinimumWidth(270)

        layout.addWidget(cards_scroll, stretch=4)
        layout.addWidget(status_panel, stretch=1)
        return layout

    def _build_bottom_band(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        event_log = EventLogPanel()
        event_log.set_events(MOCK_EVENT_LOG)

        console = ExecutionConsole()
        console.set_lines(MOCK_CONSOLE_LINES)

        signal_distribution = SignalDistributionChart()
        signal_distribution.set_rows(MOCK_SIGNAL_DISTRIBUTION)

        entry_score = EntryScoreChart()
        entry_score.set_rows(MOCK_ENTRY_SCORE_MAP)

        layout.addWidget(SectionPanel("Log de Eventos", event_log), stretch=2)
        layout.addWidget(SectionPanel("Consola de Ejecución", console), stretch=3)
        layout.addWidget(SectionPanel("Distribución de Señales", signal_distribution), stretch=1)
        layout.addWidget(SectionPanel("Mayores Repeticiones", entry_score), stretch=1)

        return layout
