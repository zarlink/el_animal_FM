from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QFrame, QPlainTextEdit, QVBoxLayout


class ExecutionConsole(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("EmptySurface")
        self.setMinimumHeight(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self._text = QPlainTextEdit()
        self._text.setObjectName("ExecutionConsoleText")
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._text.setMaximumBlockCount(10_000)
        layout.addWidget(self._text)

    def set_lines(self, lines: Sequence[str]) -> None:
        for line in lines:
            self._text.appendPlainText(line)
