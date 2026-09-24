"""
Terminal text view: renders the char stream with per-character styling.

New chars are buffered and flushed into the QTextEdit every ~50 ms via a
timer, so high baud-rate data doesn't stall the UI.
"""
from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QTextCharFormat, QTextCursor, QTextBlockFormat, QTextOption,
)
from PyQt6.QtWidgets import QTextEdit

from serial_terminal import Char
from serial_terminal.themes import CTRL_NAMES


class TerminalView(QTextEdit):

    # Emitted when scroll state changes due to user dragging to the bottom
    auto_scroll_changed = pyqtSignal(bool)

    def __init__(self, font_size: int = 13, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('terminal_view')
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        self.document().setMaximumBlockCount(4000)  # ~4000 lines max

        self._pending: list[Char] = []
        self._auto_scroll = True
        self._font_size   = font_size
        self._colors: dict[str, str] = {}

        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(50)
        self._flush_timer.timeout.connect(self._flush)
        self._flush_timer.start()

        # Re-enable auto-scroll when user manually drags scrollbar to the bottom.
        # sliderMoved only fires on user interaction, not programmatic setValue calls,
        # so it won't create a feedback loop.
        self.verticalScrollBar().sliderMoved.connect(self._on_slider_moved)

        # Apply line-height to the initial empty block so the first line has
        # the same spacing as every subsequent line (which get it via insertBlock).
        self._apply_initial_block_fmt()

    # ── Scroll tracking ────────────────────────────────────────────────────
    def _on_slider_moved(self, value: int) -> None:
        sb = self.verticalScrollBar()
        at_bottom = value >= sb.maximum() - 4
        if at_bottom and not self._auto_scroll:
            self._auto_scroll = True
            self.auto_scroll_changed.emit(True)

    # ── Public API ─────────────────────────────────────────────────────────
    def push_chars(self, chars: list[Char]) -> None:
        """Enqueue new chars for rendering."""
        self._pending.extend(chars)

    def clear_buffer(self) -> None:
        self._pending.clear()
        self.clear()
        # clear() resets the document to a single bare block; re-apply spacing.
        self._apply_initial_block_fmt()

    def _apply_initial_block_fmt(self) -> None:
        """Set 170 % line-height on the document's initial empty block."""
        fmt = QTextBlockFormat()
        fmt.setLineHeight(170, 1)
        cursor = QTextCursor(self.document())   # starts at block 0
        cursor.setBlockFormat(fmt)

    def set_font_size(self, size: int) -> None:
        self._font_size = size
        font = self.font()
        font.setPointSize(size)
        self.setFont(font)

    def set_auto_scroll(self, value: bool) -> None:
        self._auto_scroll = value
        if value:
            sb = self.verticalScrollBar()
            sb.setValue(sb.maximum())

    def apply_theme(self, c: dict[str, str]) -> None:
        self._colors = c
        self.setStyleSheet(
            f'background-color:{c["bg"]};'
            f'color:{c["fg"]};'
            f'border:none;'
        )

    # ── Internal flush ─────────────────────────────────────────────────────
    def _flush(self) -> None:
        if not self._pending or not self._colors:
            return

        batch = self._pending[:]
        self._pending.clear()
        c = self._colors

        sb = self.verticalScrollBar()
        saved_scroll = sb.value()

        # Use a document-level cursor instead of the widget cursor.
        # self.setTextCursor() would force the view to scroll to the cursor
        # position regardless of _auto_scroll — using QTextCursor(document)
        # and never calling setTextCursor() keeps the viewport stationary.
        cursor = QTextCursor(self.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Formats (created once per flush)
        def fmt(color: str, size: float = 1.0) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            f.setFont(self._make_font(self._font_size * size))
            return f

        fmt_normal  = fmt(c['fg'])
        fmt_sent    = fmt(c['amber'])
        fmt_ctrl    = fmt(c['amber'], 0.77)
        fmt_nl      = fmt(c['fg_ghost'], 0.80)

        block_fmt = QTextBlockFormat()
        block_fmt.setLineHeight(170, 1)  # 170% line height

        for ch in batch:
            code = ch.code

            if code == 10:  # LF
                cursor.insertText('↵', fmt_nl)
                cursor.insertBlock(block_fmt)
            elif code == 13:  # CR — skip
                pass
            elif code < 32 or code == 127:  # control char
                name = CTRL_NAMES.get(code, f'^{code}')
                cursor.insertText(f'[{name}]', fmt_ctrl)
            else:
                cursor.insertText(chr(code), fmt_sent if ch.sent else fmt_normal)

        # Explicitly control scroll position — do NOT call setTextCursor()
        if self._auto_scroll:
            sb.setValue(sb.maximum())
        else:
            sb.setValue(saved_scroll)

    def _make_font(self, size: float) -> QFont:
        f = QFont('JetBrains Mono')
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPointSizeF(size)
        return f
