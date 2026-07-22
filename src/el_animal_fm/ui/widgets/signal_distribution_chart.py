from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


_COUNT_PATTERN = re.compile(r"-?\d+")


@dataclass(frozen=True)
class SignalSlice:
    label: str
    count: int
    color: QColor


class PieChartCanvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._slices: tuple[SignalSlice, ...] = ()
        self.setMinimumSize(140, 140)

    def set_slices(self, slices: Sequence[SignalSlice]) -> None:
        self._slices = tuple(slice_ for slice_ in slices if slice_.count > 0)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height()) - 12
        if side <= 0:
            return

        chart_rect = QRectF(
            (self.width() - side) / 2,
            (self.height() - side) / 2,
            side,
            side,
        )
        total = sum(slice_.count for slice_ in self._slices)

        if total <= 0:
            self._draw_empty_state(painter, chart_rect)
            return

        painter.setPen(QPen(QColor("#050a0c"), 2))
        start_angle = 90 * 16
        for slice_ in self._slices:
            span_angle = round(-360 * 16 * slice_.count / total)
            painter.setBrush(slice_.color)
            painter.drawPie(chart_rect, start_angle, span_angle)
            start_angle += span_angle

        inner = chart_rect.adjusted(side * 0.27, side * 0.27, -side * 0.27, -side * 0.27)
        painter.setBrush(QColor("#050a0c"))
        painter.setPen(QPen(QColor("#173238"), 1))
        painter.drawEllipse(inner)

        painter.setPen(QColor("#d7faff"))
        font = QFont(painter.font())
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(inner, Qt.AlignmentFlag.AlignCenter, str(total))

    def _draw_empty_state(self, painter: QPainter, chart_rect: QRectF) -> None:
        painter.setBrush(QColor("#061012"))
        painter.setPen(QPen(QColor("#173238"), 1))
        painter.drawEllipse(chart_rect)
        painter.setPen(QColor("#4d5358"))
        painter.drawText(chart_rect, Qt.AlignmentFlag.AlignCenter, "0")


class SignalDistributionChart(QFrame):
    _PALETTE = {
        "ROJO": QColor("#ff4d4d"),
        "AMARILLO": QColor("#ffcc19"),
        "VERDE": QColor("#65ff5f"),
        "SIN SENAL": QColor("#78909c"),
    }
    _FALLBACK_COLORS = (
        QColor("#18dce8"),
        QColor("#ff9500"),
        QColor("#b86400"),
        QColor("#d7faff"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("EmptySurface")
        self.setMinimumHeight(150)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self._chart = PieChartCanvas()
        self._legend = QVBoxLayout()
        self._legend.setContentsMargins(0, 0, 0, 0)
        self._legend.setSpacing(5)

        layout.addWidget(self._chart, stretch=2)
        layout.addLayout(self._legend, stretch=1)

    def set_rows(self, rows: Sequence[tuple[str, str]]) -> None:
        self._clear_legend()

        slices = tuple(
            SignalSlice(label=label, count=count, color=self._color_for(label, index))
            for index, (label, value) in enumerate(rows)
            if (count := self._extract_count(value)) > 0
        )
        total = sum(slice_.count for slice_ in slices)

        self._chart.set_slices(slices)

        for slice_ in slices:
            percent = round(slice_.count * 100 / total) if total else 0
            self._legend.addWidget(self._build_legend_row(slice_, percent))

        self._legend.addStretch(1)

    def _build_legend_row(self, slice_: SignalSlice, percent: int) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        swatch = QLabel()
        swatch.setFixedSize(10, 10)
        swatch.setStyleSheet(f"background: {slice_.color.name()}; border: 1px solid #050a0c;")

        label = QLabel(f"{slice_.label} {slice_.count} ({percent}%)")
        label.setObjectName("ChartRow")
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        row_layout.addWidget(swatch)
        row_layout.addWidget(label, stretch=1)
        return row

    def _clear_legend(self) -> None:
        while self._legend.count():
            item = self._legend.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _color_for(self, label: str, index: int) -> QColor:
        normalized = label.strip().upper()
        return self._PALETTE.get(normalized, self._FALLBACK_COLORS[index % len(self._FALLBACK_COLORS)])

    def _extract_count(self, value: str) -> int:
        match = _COUNT_PATTERN.search(value)
        return int(match.group(0)) if match else 0
