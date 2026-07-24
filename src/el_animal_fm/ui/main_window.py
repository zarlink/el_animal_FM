from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from el_animal_fm.ui.dev.mock_dashboard_data import MOCK_SECONDARY_VIEWS
from el_animal_fm.ui.theme.styles import BASE_STYLESHEET
from el_animal_fm.ui.views.dictionary_lab_view import DictionaryLabView
from el_animal_fm.ui.views.live_predictions_view import LivePredictionsView
from el_animal_fm.ui.views.mock_detail_view import MockDetailView
from el_animal_fm.ui.views.news_enrichment_view import NewsEnrichmentView
from el_animal_fm.ui.views.pipeline_monitor_view import PipelineMonitorView
from el_animal_fm.ui.widgets.header_bar import HeaderBar


class MainWindow(QMainWindow):
    """Main shell for the El Animal FM desktop dashboard."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("El Animal FM Dashboard")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)

        self._tabs = QTabBar()
        self._stack = QStackedWidget()

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 14, 16, 14)
        root_layout.setSpacing(10)

        root_layout.addWidget(HeaderBar())
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
        self._stack.addWidget(LivePredictionsView())
        self._stack.addWidget(PipelineMonitorView())
        self._stack.addWidget(NewsEnrichmentView())
        self._stack.addWidget(DictionaryLabView())

        for label in _VIEW_LABELS[4:]:
            self._stack.addWidget(MockDetailView(label, MOCK_SECONDARY_VIEWS[label]))

        return self._stack

    def _connect_signals(self) -> None:
        self._tabs.currentChanged.connect(self._stack.setCurrentIndex)

_VIEW_LABELS: Sequence[str] = (
    "Live Predictions",
    "Pipeline Monitor",
    "News Enrichment",
    "Dictionary Lab",
    "Models",
)
