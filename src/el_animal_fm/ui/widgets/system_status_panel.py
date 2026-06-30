from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QWidget


class SystemStatusPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._values: dict[str, QLabel] = {}

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(12)

        rows = (
            "Model loaded",
            "BioBio sources",
            "Mostrador sources",
            "Feature sets",
            "Funds analyzed",
            "Live signals",
            "Warnings",
        )

        for row, label_text in enumerate(rows):
            label = QLabel(label_text.upper())
            label.setObjectName("StatusLabel")
            value = QLabel("--")
            value.setObjectName("StatusValue")
            self._values[label_text] = value
            layout.addWidget(label, row, 0)
            layout.addWidget(value, row, 1)

    def set_status(self, values: dict[str, str]) -> None:
        for key, value in values.items():
            if key in self._values:
                self._values[key].setText(value)
