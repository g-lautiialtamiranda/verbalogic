"""The VerbaLogic mark, drawn in code (no image files to ship): an italic serif "V" in ivory on a
round seal of the accent colour, like a bookplate. Sitka's optical sizes keep it crisp from the
16-px tray to the 256-px Start menu tile; the hairline ring only appears where there's room for it."""
from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

ICON_VERSION = 2   # part of the .ico file name: bump it when the drawing changes, so Windows reloads it
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 256)
IVORY = QColor("#F5EFE2")


def _serif(size: int) -> QFont:
    """Sitka in the optical size meant for this many pixels, italic and semibold."""
    family = "Sitka Small" if size < 32 else "Sitka Heading" if size < 96 else "Sitka Banner"
    font = QFont()
    font.setFamilies([f"{family} Semibold", family, "Sitka", "Georgia"])
    font.setPixelSize(max(1, round(size * (0.8 if size < 32 else 0.72 if size < 64 else 0.64))))
    font.setItalic(True)
    font.setWeight(QFont.DemiBold)
    return font


def make_pixmap(accent: str, size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    color = QColor(accent)
    shade = QLinearGradient(0, 0, 0, size)  # lit from above, like a pressed seal
    shade.setColorAt(0, color.lighter(116))
    shade.setColorAt(1, color.darker(118))
    p.setPen(Qt.NoPen)
    p.setBrush(shade)
    p.drawEllipse(QRectF(0, 0, size, size))
    if size >= 40:
        ring = QColor(IVORY)
        ring.setAlpha(105)
        pen = QPen(ring)
        pen.setWidthF(max(1.0, size / 64))
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        inset = size * 0.08
        p.drawEllipse(QRectF(inset, inset, size - 2 * inset, size - 2 * inset))
    # Centre the V by its outline, not its line box: italic capitals lean and sit high in the em square.
    font = _serif(size)
    v = QPainterPath()
    v.addText(0, QFontMetricsF(font).ascent(), font, "V")
    box = v.boundingRect()
    v.translate(size / 2 - box.center().x(), size * 0.52 - box.center().y())
    p.setPen(Qt.NoPen)
    p.setBrush(IVORY)
    p.drawPath(v)
    p.end()
    return pm


def mark_pixmap(accent: str, px: int, ratio: float) -> QPixmap:
    """The mark for a label px logical pixels wide, sharp on high-DPI screens."""
    pm = make_pixmap(accent, round(px * ratio))
    pm.setDevicePixelRatio(ratio)
    return pm


def make_icon(accent: str) -> QIcon:
    icon = QIcon()
    for s in ICO_SIZES:
        icon.addPixmap(make_pixmap(accent, s))
    return icon


def write_ico(accent: str, path: Path) -> None:
    """A real multi-size .ico (PNG entries), so the taskbar and Start menu pick a sharp size
    instead of shrinking one 256-px image. Qt's own ICO writer stores a single size."""
    images = []
    for s in ICO_SIZES:
        buf = QBuffer()
        buf.open(QBuffer.WriteOnly)
        make_pixmap(accent, s).save(buf, "PNG")
        images.append((s, bytes(buf.data())))
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for s, png in images:
        dim = 0 if s >= 256 else s  # 0 means 256 in an ICO directory entry
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(blobs))
        blobs += png
    path.write_bytes(header + entries + blobs)
