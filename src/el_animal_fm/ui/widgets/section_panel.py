from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class SectionPanel(QFrame):
    def __init__(self, title: str, body: QWidget | None = None) -> None:
        super().__init__()
        self.setObjectName("Panel")

        self.body_container = QWidget()
        self.body_layout = QVBoxLayout(self.body_container)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(8)

        if body is not None:
            self.body_layout.addWidget(body)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        heading = QLabel(title.upper())
        heading.setObjectName("PanelTitle")

        layout.addWidget(heading)
        layout.addWidget(self.body_container, stretch=1)

