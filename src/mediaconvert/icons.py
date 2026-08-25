"""Shared SVG icon rendering: guarantees pixel-perfect sizing, unlike
theme icon lookup where the available pixmap size may be smaller than
requested and just gets centered with padding instead of filling it."""

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def svg_pixmap(svg_template: str, color: str, size: int) -> QPixmap:
    svg_data = svg_template.format(color=color).encode("utf-8")
    renderer = QSvgRenderer(QByteArray(svg_data))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap
