from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ExecutionConsole(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("EmptySurface")
        self.setMinimumHeight(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        self._layout = layout

    def set_lines(self, lines: Sequence[str]) -> None:
        for line in lines:
            label = QLabel(line)
            label.setObjectName("ConsoleLine")
            label.setWordWrap(False)
            self._layout.addWidget(label)

        self._layout.addStretch(1)
