from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget


SEMAFORO_STYLES = {
    "ROJO": {
        "accent": "#ff3b33",
        "fill": QColor(42, 8, 8, 220),
        "card_fill": QColor(28, 6, 6, 185),
    },
    "AMARILLO": {
        "accent": "#ffcc19",
        "fill": QColor(54, 44, 4, 220),
        "card_fill": QColor(31, 27, 4, 185),
    },
    "VERDE": {
        "accent": "#48d94a",
        "fill": QColor(11, 48, 19, 220),
        "card_fill": QColor(6, 28, 15, 185),
    },
    "SIN SENAL": {
        "accent": "#18dce8",
        "fill": QColor(8, 36, 42, 180),
        "card_fill": QColor(6, 22, 25, 210),
    },
}


class SemaforoLight(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._status = "SIN SENAL"
        self.setFixedSize(42, 42)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(42, 42)

    def set_status(self, status: str) -> None:
        self._status = _normalize_semaforo(status)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)

        style = _semaforo_style(self._status)
        accent = QColor(style["accent"])
        fill = style["fill"]

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(5, 5, -5, -5)
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 2
        points = []
        for step in range(8):
            angle = 22.5 + step * 45
            rad = math.radians(angle)
            x = center.x() + radius * 0.95 * math.cos(rad)
            y = center.y() + radius * 0.95 * math.sin(rad)
            points.append(QPointF(x, y))

        polygon = QPolygonF(points)
        painter.setBrush(fill)
        painter.setPen(QPen(accent, 2.4))
        painter.drawPolygon(polygon)
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 90), 5.5))
        painter.drawPolygon(polygon)


def _normalize_semaforo(semaforo: str) -> str:
    status = semaforo.upper().replace("\u00d1", "N").strip()
    if status in {"SIN SE\u00d1AL", "SIN SENAL", "NO SIGNAL", "NO DATA", "--"}:
        return "SIN SENAL"
    return status if status in SEMAFORO_STYLES else "SIN SENAL"


def _semaforo_style(semaforo: str) -> dict[str, object]:
    return SEMAFORO_STYLES[_normalize_semaforo(semaforo)]


class FundSignalCard(QFrame):
    def __init__(self, index: str, title: str) -> None:
        super().__init__()
        self.setObjectName("FundSignalCard")
        self.setMinimumHeight(205)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._metric_values: dict[str, QLabel] = {}
        self._semaforo_title_label: QLabel | None = None
        self._semaforo_label: QLabel | None = None
        self._semaforo_light: SemaforoLight | None = None
        self._out_decision_label: QLabel | None = None
        self._in_decision_label: QLabel | None = None
        self._semaforo_status = "SIN SENAL"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 18, 26, 18)
        layout.setSpacing(10)

        layout.addLayout(self._build_header(index, title))
        layout.addLayout(self._build_body())

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(5, 5, -5, -5)
        cut = 34
        notch = 22

        frame = QPolygonF(
            [
                QPointF(rect.left() + cut, rect.top()),
                QPointF(rect.right() - notch, rect.top()),
                QPointF(rect.right(), rect.top() + notch),
                QPointF(rect.right(), rect.bottom() - cut),
                QPointF(rect.right() - cut, rect.bottom()),
                QPointF(rect.left() + notch, rect.bottom()),
                QPointF(rect.left(), rect.bottom() - notch),
                QPointF(rect.left(), rect.top() + cut),
            ]
        )

        style = _semaforo_style(self._semaforo_status)
        glow_color = QColor(style["accent"])
        fill_color = style["card_fill"]
        painter.setBrush(fill_color)
        painter.setPen(QPen(QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 140), 1.4))
        painter.drawPolygon(frame)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(glow_color, 1.8))
        painter.drawPolyline(frame + QPolygonF([frame.first()]))

        painter.setPen(QPen(QColor("#ff9500"), 1.2))
        painter.drawLine(rect.left() + cut + 10, rect.top() + 10, rect.left() + 145, rect.top() + 10)
        painter.drawLine(rect.right() - 165, rect.bottom() - 10, rect.right() - cut - 10, rect.bottom() - 10)

        tab = QPainterPath()
        tab.moveTo(rect.left() + 18, rect.top() + 12)
        tab.lineTo(rect.left() + 110, rect.top() + 12)
        tab.lineTo(rect.left() + 88, rect.top() + 50)
        tab.lineTo(rect.left() + 18, rect.top() + 50)
        tab.closeSubpath()
        painter.setPen(QPen(QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 130), 1.1))
        painter.setBrush(style["fill"])
        painter.drawPath(tab)

        painter.setPen(QPen(QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 65), 1))
        painter.drawLine(rect.left() + 22, rect.top() + 58, rect.right() - 24, rect.top() + 58)

    def _build_header(self, index: str, title: str) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        index_label = QLabel(index)
        index_label.setObjectName("CardIndex")
        index_label.setFixedWidth(48)

        title_label = QLabel(title.upper())
        title_label.setObjectName("CardTitle")

        layout.addWidget(index_label)
        layout.addWidget(title_label, stretch=1)
        return layout

    def _build_body(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(18)

        metric_grid = QGridLayout()
        metric_grid.setHorizontalSpacing(14)
        metric_grid.setVerticalSpacing(7)

        metrics = (
            "pred_prob_up",
            "pred_up",
            "momentum_10",
            "vs_ma20",
            "drawdown_20",
            "entry_score",
        )

        for row, metric in enumerate(metrics):
            name = QLabel(metric)
            name.setObjectName("MetricName")
            value = QLabel("--")
            value.setObjectName("MetricValue")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._metric_values[metric] = value
            metric_grid.addWidget(name, row, 0)
            metric_grid.addWidget(value, row, 1)

        decision_block = QWidget()
        decision_layout = QVBoxLayout(decision_block)
        decision_layout.setContentsMargins(0, 0, 0, 0)
        decision_layout.setSpacing(8)

        semaforo_row = QHBoxLayout()
        semaforo_row.setContentsMargins(0, 0, 0, 0)
        semaforo_row.setSpacing(8)

        semaforo_light = SemaforoLight()
        self._semaforo_light = semaforo_light

        semaforo_text = QVBoxLayout()
        semaforo_text.setContentsMargins(0, 0, 0, 0)
        semaforo_text.setSpacing(0)

        semaforo_title = QLabel("SEMAFORO")
        semaforo_title.setObjectName("SemaforoTitle")
        semaforo_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._semaforo_title_label = semaforo_title

        semaforo = QLabel("--")
        semaforo.setObjectName("SemaforoResult")
        semaforo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._semaforo_label = semaforo

        semaforo_row.addWidget(semaforo_light)
        semaforo_text.addWidget(semaforo_title)
        semaforo_text.addWidget(semaforo)
        semaforo_row.addLayout(semaforo_text, stretch=1)

        out_row = self._build_decision_row("OUT")
        out_decision = out_row.itemAt(1).widget()
        assert isinstance(out_decision, QLabel)
        self._out_decision_label = out_decision

        in_row = self._build_decision_row("IN")
        in_decision = in_row.itemAt(1).widget()
        assert isinstance(in_decision, QLabel)
        self._in_decision_label = in_decision

        decision_layout.addLayout(semaforo_row)
        decision_layout.addLayout(out_row)
        decision_layout.addLayout(in_row)

        layout.addLayout(metric_grid, stretch=2)
        layout.addWidget(decision_block, stretch=1)
        return layout

    def _build_decision_row(self, title: str) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("DecisionTitle")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        title_label.setFixedWidth(34)

        result_label = QLabel("--")
        result_label.setObjectName("DecisionLabel")
        result_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        result_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(result_label, stretch=1)
        return layout

    def set_signal(
        self,
        *,
        metrics: dict[str, str],
        semaforo: str,
        decision_if_out: str,
        decision_if_in: str,
    ) -> None:
        for metric, value in metrics.items():
            if metric in self._metric_values:
                self._metric_values[metric].setText(value)

        self._semaforo_status = _normalize_semaforo(semaforo)
        accent = _semaforo_style(self._semaforo_status)["accent"]

        if self._semaforo_light is not None:
            self._semaforo_light.set_status(self._semaforo_status)
        if self._semaforo_title_label is not None:
            self._semaforo_title_label.setStyleSheet("color: #18dce8;")
        if self._semaforo_label is not None:
            self._semaforo_label.setText(self._semaforo_status)
            self._semaforo_label.setStyleSheet(f"color: {accent};")
        if self._out_decision_label is not None:
            self._out_decision_label.setText(decision_if_out)
            self._out_decision_label.setStyleSheet(f"color: {accent};")
        if self._in_decision_label is not None:
            self._in_decision_label.setText(decision_if_in)
            self._in_decision_label.setStyleSheet(f"color: {accent};")
        self.update()
