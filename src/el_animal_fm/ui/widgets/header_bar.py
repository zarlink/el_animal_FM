from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class HeaderBar(QFrame):
    refresh_date_requested = Signal()
    prediction_requested = Signal()

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
        subtitle = QLabel("Analisis Directo / Versión 0.8 (10212026)")
        subtitle.setObjectName("AppSubtitle")

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        layout.addWidget(title_block, stretch=1)
        self._date_chip = self._build_header_chip("---- -- --")
        self._refresh_button = self._build_header_button("Actualizar Fecha")
        self._refresh_button.clicked.connect(self.refresh_date_requested.emit)
        layout.addWidget(self._date_chip)
        layout.addWidget(self._refresh_button)
        self._predict_button = self._build_header_button("Ejecutar Predicción", primary=True)
        self._predict_button.clicked.connect(self.prediction_requested.emit)
        layout.addWidget(self._predict_button)

    def set_predicting(self, predicting: bool) -> None:
        self._predict_button.setEnabled(not predicting)
        self._refresh_button.setEnabled(not predicting)
        self._predict_button.setText("Prediciendo…" if predicting else "Ejecutar Predicción")

    def set_date(self, text: str, detail: str = "") -> None:
        self._date_chip.setText(text)
        self._date_chip.setToolTip(detail)

    def set_refreshing(self, refreshing: bool) -> None:
        self._refresh_button.setEnabled(not refreshing)
        self._refresh_button.setText("Comprobando…" if refreshing else "Actualizar Fecha")

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

