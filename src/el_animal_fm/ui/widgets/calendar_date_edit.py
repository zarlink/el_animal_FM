from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QDateEdit


class CalendarDateEdit(QDateEdit):
    """Date selector with a dashboard-style calendar glyph."""

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#18dce8"), 1.4))

        icon = QRectF(self.width() - 22, (self.height() - 14) / 2, 14, 13)
        painter.drawRoundedRect(icon, 1.2, 1.2)
        painter.drawLine(icon.left(), icon.top() + 4, icon.right(), icon.top() + 4)
        painter.drawLine(icon.left() + 4, icon.top() - 2, icon.left() + 4, icon.top() + 2)
        painter.drawLine(icon.right() - 4, icon.top() - 2, icon.right() - 4, icon.top() + 2)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#18dce8"))
        for row in range(2):
            for column in range(3):
                painter.drawRect(
                    QRectF(icon.left() + 3 + column * 4, icon.top() + 6 + row * 3, 1.5, 1.5)
                )
