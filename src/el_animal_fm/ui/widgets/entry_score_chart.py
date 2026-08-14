from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget


_COUNT_PATTERN = re.compile(r"-?\d+")


@dataclass(frozen=True)
class EntryScoreBar:
    score: str
    count: int


class EntryScoreCanvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._bars: tuple[EntryScoreBar, ...] = ()
        self.setMinimumHeight(150)

    def set_bars(self, bars: Sequence[EntryScoreBar]) -> None:
        self._bars = tuple(bars)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._bars:
            self._draw_empty_state(painter)
            return

        max_count = max((bar.count for bar in self._bars), default=0)
        left_pad = 28
        right_pad = 34
        top_pad = 12
        row_gap = 8
        available_height = max(1, self.height() - top_pad * 2)
        row_height = max(18, (available_height - row_gap * (len(self._bars) - 1)) / len(self._bars))
        track_width = max(1, self.width() - left_pad - right_pad)

        label_font = QFont(painter.font())
        label_font.setBold(True)
        painter.setFont(label_font)

        for index, bar in enumerate(self._bars):
            y = top_pad + index * (row_height + row_gap)
            track_rect = QRectF(left_pad, y, track_width, row_height)
            fill_width = 0 if max_count <= 0 else track_width * bar.count / max_count
            fill_rect = QRectF(left_pad, y, fill_width, row_height)

            painter.setPen(QColor("#18dce8"))
            painter.drawText(
                QRectF(0, y, left_pad - 8, row_height),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                bar.score,
            )

            painter.setBrush(QColor("#061012"))
            painter.setPen(QPen(QColor("#173238"), 1))
            painter.drawRoundedRect(track_rect, 3, 3)

            if bar.count > 0:
                painter.setBrush(self._color_for_score(bar.score))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(fill_rect, 3, 3)

            painter.setPen(QColor("#d7faff"))
            painter.drawText(
                QRectF(left_pad + track_width + 8, y, right_pad - 8, row_height),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                str(bar.count),
            )

    def _draw_empty_state(self, painter: QPainter) -> None:
        painter.setPen(QColor("#4d5358"))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "0")

    def _color_for_score(self, score: str) -> QColor:
        colors = {
            "3": QColor("#65ff5f"),
            "2": QColor("#ffcc19"),
            "1": QColor("#ff9500"),
            "0": QColor("#ff4d4d"),
        }
        return colors.get(score.strip(), QColor("#18dce8"))


class EntryScoreChart(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("EmptySurface")
        self.setMinimumHeight(150)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)

        self._canvas = EntryScoreCanvas()
        layout.addWidget(self._canvas)

    def set_rows(self, rows: Sequence[tuple[str, str]]) -> None:
        bars = tuple(
            EntryScoreBar(score=score, count=self._extract_count(value))
            for score, value in rows
        )
        self._canvas.set_bars(bars)

    def _extract_count(self, value: str) -> int:
        match = _COUNT_PATTERN.search(value)
        return int(match.group(0)) if match else 0
