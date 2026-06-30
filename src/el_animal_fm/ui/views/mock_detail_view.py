from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from el_animal_fm.ui.widgets.section_panel import SectionPanel


class MockDetailView(QWidget):
    def __init__(self, title: str, rows: Sequence[str]) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)

        for row in rows:
            label = QLabel(row)
            label.setObjectName("MockRow")
            label.setWordWrap(True)
            body_layout.addWidget(label)

        body_layout.addStretch(1)
        layout.addWidget(SectionPanel(title, body), stretch=1)

