from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class HeaderBar(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("HeaderBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(16)

        title_block = QWidget()
        title_layout = QVBoxLayout(title_block)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        title = QLabel("EL ANIMAL - Centro de Decisiones")
        title.setObjectName("AppTitle")
        subtitle = QLabel("LIVE PREDICTIONS / TAB 01")
        subtitle.setObjectName("AppSubtitle")

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        layout.addWidget(title_block, stretch=1)
        layout.addWidget(self._build_header_chip("---- -- --"))
        layout.addWidget(self._build_header_button("UPDATE DATE"))
        layout.addWidget(self._build_header_button("RUN LIVE PREDICTION", primary=True))

    def _build_header_chip(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("HeaderChip")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumWidth(170)
        return label

    def _build_header_button(self, text: str, *, primary: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("PrimaryHeaderButton" if primary else "HeaderButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(42)
        button.setMinimumWidth(180 if primary else 150)
        return button

