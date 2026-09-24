"""
Horizontal ASCII strip: shows the last N characters with their decimal and hex
values, rendered via QPainter for pixel-perfect fidelity.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QRect, QSize, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QAbstractScrollArea, QSizePolicy

from serial_terminal import Char
from serial_terminal.themes import CTRL_NAMES

_CELL_W    = 30   # px per character cell
_MAX_SHOW  = 180  # number of chars displayed
_LEGEND_W  = 48   # px reserved for the fixed row-labels on the left


class AsciiStrip(QAbstractScrollArea):

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('ascii_strip')
        self.setFixedHeight(72)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.horizontalScrollBar().setFixedHeight(3)
        self.viewport().setAutoFillBackground(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._chars: list[Char] = []
        self._colors: dict[str, str] = {}
        self._pending: list[Char] | None = None

        # Coalesce updates the same way the hex panel does: serial fragments
        # only stash the latest buffer, and this timer refilters/repaints at a
        # fixed cadence instead of on every fragment (which re-scanned the whole
        # buffer each time).
        self._refresh = QTimer(self)
        self._refresh.setInterval(100)
        self._refresh.timeout.connect(self._apply_pending)
        self._refresh.start()

    # ── Public API ─────────────────────────────────────────────────────────
    def update_chars(self, chars: list[Char]) -> None:
        # Stash the latest buffer; the refresh timer does the actual work.
        self._pending = chars

    def _apply_pending(self) -> None:
        if self._pending is None:
            return
        chars, self._pending = self._pending, None
        # Filter CR/LF, take last _MAX_SHOW
        self._chars = [c for c in chars if c.code not in (10, 13)][-_MAX_SHOW:]
        n = len(self._chars)
        total_w = max(n * _CELL_W + _LEGEND_W, self.viewport().width())
        self.horizontalScrollBar().setRange(0, total_w - self.viewport().width())
        self.horizontalScrollBar().setPageStep(self.viewport().width())
        # Auto-scroll to end
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().maximum())
        self.viewport().update()

    def apply_theme(self, c: dict[str, str]) -> None:
        self._colors = c
        self.viewport().update()

    # ── Painting ───────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        self.viewport().update()

    def viewportEvent(self, event) -> bool:
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.Paint:
            self._paint_viewport()
            return True
        return super().viewportEvent(event)

    def _paint_viewport(self) -> None:
        c = self._colors
        if not c:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        vp = self.viewport().rect()
        painter.fillRect(vp, QColor(c['bg2']))

        if not self._chars:
            painter.setPen(QColor(c['fg_ghost']))
            painter.setFont(self._font(9, 'IBM Plex Mono'))
            painter.drawText(vp, Qt.AlignmentFlag.AlignCenter, '— no data —')
            return

        scroll_x = self.horizontalScrollBar().value()
        y_top    = 8     # top padding

        # ── Fixed left legend (not scrolled) ──────────────────────
        lf = self._font(8, 'IBM Plex Mono')
        painter.setFont(lf)
        legend_r = QRect(0, 0, _LEGEND_W - 4, vp.height())

        row_labels = [
            (y_top,      16, c['fg_dim'],    'char'),
            (y_top + 20, 14, c['fg_dim'],    'dec'),
            (y_top + 36, 12, c['fg_faint'],  'hex'),
        ]
        for y, h, color, text in row_labels:
            painter.setPen(QColor(color))
            painter.drawText(
                QRect(6, y, _LEGEND_W - 6, h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )

        # Thin vertical separator between legend and data area
        painter.setPen(QPen(QColor(c['border2']), 1))
        painter.drawLine(_LEGEND_W - 1, y_top + 2, _LEGEND_W - 1, y_top + 46)

        # ── Character cells (scrolled, start at _LEGEND_W) ────────
        for i, ch in enumerate(self._chars):
            x = _LEGEND_W + i * _CELL_W - scroll_x
            if x + _CELL_W < _LEGEND_W or x > vp.width():
                continue  # skip off-screen cells

            is_ctrl = ch.code < 32 or ch.code == 127

            # Character symbol
            if is_ctrl:
                painter.setPen(QColor(c['amber']))
                painter.setFont(self._font(8, 'JetBrains Mono'))
                label = CTRL_NAMES.get(ch.code, '?')[:3]
            else:
                painter.setPen(QColor(c['fg']))
                painter.setFont(self._font(11, 'JetBrains Mono'))
                label = chr(ch.code)

            r_ch = QRect(x, y_top, _CELL_W, 16)
            painter.drawText(r_ch, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, label)

            # Decimal value
            painter.setPen(QColor(c['fg_dim']))
            painter.setFont(self._font(9, 'IBM Plex Mono'))
            r_dec = QRect(x, y_top + 20, _CELL_W, 14)
            painter.drawText(r_dec, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                             str(ch.code))

            # Hex value
            painter.setPen(QColor(c['fg_faint']))
            painter.setFont(self._font(8, 'IBM Plex Mono'))
            r_hex = QRect(x, y_top + 36, _CELL_W, 12)
            painter.drawText(r_hex, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                             f'0x{ch.code:02X}')

            # Group separator every 16 chars
            if (i + 1) % 16 == 0 and i < len(self._chars) - 1:
                sep_x = _LEGEND_W + (i + 1) * _CELL_W - scroll_x
                painter.setPen(QPen(QColor(c['border2']), 1))
                painter.drawLine(sep_x + 3, y_top + 5, sep_x + 3, y_top + 46)

    @staticmethod
    def _font(size: int, family: str = 'JetBrains Mono') -> QFont:
        f = QFont(family)
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPointSize(size)
        return f
