"""The app icon, drawn in code (no image files to ship)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap


def make_pixmap(accent: str, size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(accent))
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.26, size * 0.26)
    font = QFont("Segoe UI", int(size * 0.5))
    font.setWeight(QFont.Black)
    p.setFont(font)
    p.setPen(QColor("#FFFFFF"))
    p.drawText(QRectF(0, -size * 0.03, size, size), Qt.AlignCenter, "V")
    p.setBrush(QColor(255, 255, 255, 220))
    p.setPen(Qt.NoPen)
    d = size * 0.13
    p.drawEllipse(QRectF(size * 0.74, size * 0.14, d, d))
    p.end()
    return pm


def make_icon(accent: str) -> QIcon:
    icon = QIcon()
    for s in (16, 20, 24, 32, 48, 64, 256):
        icon.addPixmap(make_pixmap(accent, s))
    return icon
