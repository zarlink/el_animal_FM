from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class SimpleChartPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("EmptySurface")
        self.setMinimumHeight(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        self._layout = layout

    def set_rows(self, rows: Sequence[tuple[str, str]]) -> None:
        for label_text, value_text in rows:
            label = QLabel(f"{label_text:<12} {value_text}")
            label.setObjectName("ChartRow")
            self._layout.addWidget(label)

        self._layout.addStretch(1)
