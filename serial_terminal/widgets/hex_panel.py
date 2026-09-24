"""
Collapsible hex-dump panel.  Uses QPropertyAnimation to smoothly
animate width between 22 px (collapsed) and 310 px (expanded).

The dump is rendered as three scroll-locked columns — offset | hex | ascii —
where only the hex column is selectable.  A drag-select + Ctrl+C therefore
copies *only* the hex values (no offsets, no ASCII), and there is still a
"Copy all bytes as hex" action for grabbing the whole buffer as clean
space-separated hex for use in other software.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QApplication,
)

from serial_terminal import Char
from serial_terminal.logging_setup import get_logger

_log = get_logger('hex')

_OPEN_W  = 310
_CLOSE_W = 22
_HEX_COLS = 8
_MAX_DUMP_BYTES = 4096   # cap the rendered dump so rebuilds stay snappy
                         # (512 rows). Copy-all-hex still grabs the full
                         # buffer, so this only limits the on-screen window.


_OFFSET_W = 44   # px — fixed width of the offset (line-number) column
_ASCII_W  = 70   # px — fixed width of the ASCII column


class _Pane(QTextEdit):
    """One column of the hex dump.

    Three of these sit side by side (offset | hex | ascii).  Only the hex pane
    is selectable, so a drag-select + Ctrl+C copies *only* the hex values —
    the offset and ASCII columns can't be selected at all.  The three panes are
    scroll-locked so they always line up row-for-row.
    """

    def __init__(self, owner: '_HexView', selectable: bool) -> None:
        super().__init__()
        self._owner      = owner
        self._selectable = selectable
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(3)
        if not selectable:
            # No cursor, no selection, no context menu — purely a display column.
            self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        f = QFont('JetBrains Mono')
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPointSize(10)
        self.setFont(f)

    def wheelEvent(self, event) -> None:
        # Route every wheel scroll through the hex pane so all three columns
        # move together (the offset/ascii panes have no scrollbar of their own).
        if self is self._owner.hex_pane:
            super().wheelEvent(event)
        else:
            self._owner.hex_pane.wheelEvent(event)

    def contextMenuEvent(self, event) -> None:
        if not self._selectable:
            event.ignore()
            return
        menu = self.createStandardContextMenu()   # native Copy / Select All …
        menu.addSeparator()
        act = menu.addAction('Copy all bytes as hex')
        act.setEnabled(bool(self._owner._chars))
        act.triggered.connect(self._owner._copy_all_hex)
        menu.exec(event.globalPos())


class _HexView(QWidget):
    """Three scroll-locked columns: offset | hex | ascii.

    Only the hex column is selectable, so selecting + copying yields clean hex
    with no offsets or ASCII mixed in.  A context-menu action still copies the
    entire buffer as space-separated hex.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('hex_view')

        self._chars:  list[Char]      = []
        self._colors: dict[str, str]  = {}
        self._dirty:  bool            = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._offset = _Pane(self, selectable=False)
        self.hex_pane = _Pane(self, selectable=True)
        self._ascii  = _Pane(self, selectable=False)

        self._offset.setFixedWidth(_OFFSET_W)
        self._ascii.setFixedWidth(_ASCII_W)
        # Only the hex pane shows a vertical scrollbar; the others are slaved.
        self._offset.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._ascii.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hex_pane.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        lay.addWidget(self._offset)
        lay.addWidget(self.hex_pane, 1)
        lay.addWidget(self._ascii)

        # Keep the slaved columns aligned with the hex column as it scrolls.
        self.hex_pane.verticalScrollBar().valueChanged.connect(self._sync_scroll)

        # Coalesce updates: incoming serial fragments only mark the view dirty;
        # this timer does at most one (expensive) full document rebuild per
        # tick.  Without it, a full multi-line rich-text rebuild ran on every
        # fragment and saturated the GUI thread once the buffer filled up.
        self._refresh = QTimer(self)
        self._refresh.setInterval(200)
        self._refresh.timeout.connect(self._maybe_rebuild)
        self._refresh.start()

    # ── Public API ───────────────────────────────────────────────────────────
    def set_chars(self, chars: list[Char]) -> None:
        # Just stash the latest data + flag dirty; the refresh timer rebuilds.
        self._chars = chars
        self._dirty = True

    def _maybe_rebuild(self) -> None:
        if not self._dirty:
            return
        # Don't blow away an in-progress selection while the user is trying to
        # copy — keep the dirty flag set and redraw once they're done.
        if self.hex_pane.textCursor().hasSelection():
            return
        # Nothing to do while the panel is collapsed (width squeezed to ~0);
        # the rebuild is forced when it reopens.
        if self.width() < 40:
            return
        self._dirty = False
        self._rebuild()

    def apply_theme(self, c: dict[str, str]) -> None:
        self._colors = c
        plain = f'QTextEdit{{background:{c["bg4"]};border:none;}}'
        self._offset.setStyleSheet(plain)
        self._ascii.setStyleSheet(plain)
        self.hex_pane.setStyleSheet(
            f'QTextEdit{{background:{c["bg4"]};border:none;'
            f'selection-background-color:{c["fg_ghost"]};'
            f'selection-color:{c["fg"]};}}'
        )
        self._rebuild()

    def _copy_all_hex(self) -> None:
        hex_str = ' '.join(f'{ch.code:02X}' for ch in self._chars)
        QApplication.clipboard().setText(hex_str)
        _log.debug('Copied %d bytes as hex to clipboard', len(self._chars))

    # ── Scroll sync ──────────────────────────────────────────────────────────
    def _sync_scroll(self, value: int) -> None:
        self._offset.verticalScrollBar().setValue(value)
        self._ascii.verticalScrollBar().setValue(value)

    def _at_bottom(self) -> bool:
        sb = self.hex_pane.verticalScrollBar()
        return sb.value() >= sb.maximum() - 4

    # ── Rendering ────────────────────────────────────────────────────────────
    @staticmethod
    def _fill(pane: QTextEdit, runs: list[list]) -> None:
        """Replace a pane's document with the given colour runs."""
        pane.clear()
        cursor = QTextCursor(pane.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for color, text in runs:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.insertText(text, fmt)

    def _rebuild(self) -> None:
        c = self._colors
        if not c:
            return

        sb    = self.hex_pane.verticalScrollBar()
        stick = self._at_bottom()
        saved = sb.value()

        # One run list per column; merge adjacent same-colour runs.
        off_runs: list[list] = []
        hex_runs: list[list] = []
        asc_runs: list[list] = []

        def emit(runs: list[list], text: str, color: str) -> None:
            if runs and runs[-1][0] == color:
                runs[-1][1] += text
            else:
                runs.append([color, text])

        chars = self._chars[-_MAX_DUMP_BYTES:]

        if not chars:
            emit(off_runs, '', c['fg_ghost'])
            emit(hex_runs, '— no data —', c['fg_ghost'])
            emit(asc_runs, '', c['fg_ghost'])
        else:
            n_rows = (len(chars) + _HEX_COLS - 1) // _HEX_COLS
            for ri in range(n_rows):
                row = chars[ri * _HEX_COLS:(ri + 1) * _HEX_COLS]
                nl  = '\n' if ri < n_rows - 1 else ''

                # Offset column
                emit(off_runs, f'{ri * _HEX_COLS:04X}{nl}', c['hex_offset'])

                # Hex column — bytes separated by single spaces, no padding
                # (each column is its own pane, so nothing needs to line up).
                for bi, ch in enumerate(row):
                    if ch.sent:
                        color = c['amber']
                    elif ch.code == 0:
                        color = c['fg_ghost']
                    elif ch.code < 32 or ch.code == 127:
                        color = c['hex_ctrl']
                    else:
                        color = c['fg']
                    emit(hex_runs, f'{ch.code:02X}', color)
                    if bi < len(row) - 1:
                        emit(hex_runs, ' ', c['fg'])
                emit(hex_runs, nl, c['fg'])

                # ASCII column
                for ch in row:
                    if 32 <= ch.code < 127:
                        emit(asc_runs, chr(ch.code),
                             c['amber_dim'] if ch.sent else c['fg_dim'])
                    else:
                        emit(asc_runs, '·', c['fg_ghost'])
                emit(asc_runs, nl, c['fg'])

        self._fill(self._offset, off_runs)
        self._fill(self.hex_pane, hex_runs)
        self._fill(self._ascii, asc_runs)

        if stick:
            sb.setValue(sb.maximum())
        else:
            sb.setValue(min(saved, sb.maximum()))
        self._sync_scroll(sb.value())


class HexPanel(QWidget):

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('hex_panel')
        self._open = True
        self._colors: dict[str, str] = {}

        # Fixed width via animation
        self.setMinimumWidth(_CLOSE_W)
        self.setMaximumWidth(_OPEN_W)
        self.setFixedWidth(_OPEN_W)

        self._anim = QPropertyAnimation(self, b'maximumWidth')
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # ── Toggle strip (always visible) ─────────────────────────────────
        self._toggle_strip = QWidget(self)
        self._toggle_strip.setFixedWidth(_CLOSE_W)
        self._toggle_strip.setGeometry(0, 0, _CLOSE_W, 9999)

        self._btn_toggle = QPushButton('>>', self._toggle_strip)
        self._btn_toggle.setFixedSize(20, 20)
        self._btn_toggle.setObjectName('hex_toggle_btn')
        self._btn_toggle.clicked.connect(self._toggle)

        # ── Content area ──────────────────────────────────────────────────
        self._content = QWidget(self)
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(26)
        header.setObjectName('hex_header')
        hl = QHBoxLayout(header)
        hl.setContentsMargins(6, 0, 8, 0)
        hl.setSpacing(0)
        self._hdr_title = QLabel('HEX DUMP')
        self._hdr_title.setObjectName('hex_header_title')
        hl.addWidget(self._hdr_title)
        hl.addStretch()
        # Legend
        for key, display in (('rx', 'RX'), ('tx', 'TX'), ('off', 'OFF')):
            dot = QLabel('●')
            dot.setObjectName(f'hex_legend_{key}')
            dot.setContentsMargins(0, 0, 2, 0)
            lbl = QLabel(display)
            lbl.setObjectName(f'hex_legend_lbl_{key}')
            lbl.setContentsMargins(0, 0, 8, 0)
            hl.addWidget(dot)
            hl.addWidget(lbl)

        content_layout.addWidget(header)

        # Selectable hex-dump view
        self._view = _HexView()
        content_layout.addWidget(self._view)

        # ── Position content area ──────────────────────────────────────────
        self.resizeEvent(None)

    def resizeEvent(self, event) -> None:
        h = self.height() if self.height() > 0 else 600
        self._toggle_strip.setGeometry(0, 0, _CLOSE_W, h)

        # Place toggle button in center of strip
        by = max(0, h // 2 - 24)
        self._btn_toggle.move(1, by)

        # Content area sits to the right of toggle strip
        self._content.setGeometry(_CLOSE_W, 0, max(0, self.width() - _CLOSE_W), h)

    # ── Toggle ─────────────────────────────────────────────────────────────
    def _toggle(self) -> None:
        self._open = not self._open
        target = _OPEN_W if self._open else _CLOSE_W
        self._anim.stop()
        self._anim.setStartValue(self.maximumWidth())
        self._anim.setEndValue(target)
        self._anim.start()
        # Also animate minimumWidth so the widget actually shrinks
        self._anim2 = QPropertyAnimation(self, b'minimumWidth')
        self._anim2.setDuration(220)
        self._anim2.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim2.setStartValue(self.minimumWidth())
        self._anim2.setEndValue(target)
        self._anim2.start()
        self._btn_toggle.setText('>>' if not self._open else '<<')
        if self._open:
            # Re-render whatever streamed in while we were collapsed.
            self._view._dirty = True

    @staticmethod
    def _make_header_font(size: int) -> QFont:
        f = QFont('IBM Plex Mono')
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPointSize(size)
        return f

    # ── Public API ─────────────────────────────────────────────────────────
    def update_chars(self, chars: list[Char]) -> None:
        self._view.set_chars(chars)

    def apply_theme(self, c: dict[str, str]) -> None:
        self._colors = c
        self._view.apply_theme(c)
        self._toggle_strip.setStyleSheet(f'background:{c["bg4"]};')
        self._btn_toggle.setStyleSheet(
            f'background:{c["bg3"]};border:1px solid {c["border"]};'
            f'color:{c["fg_dim"]};font-size:9px;border-radius:2px;'
        )
        self._hdr_title.setStyleSheet(
            f'color:{c["fg_dim"]};font-family:"IBM Plex Mono",monospace;'
            f'font-size:11px;letter-spacing:1px;'
        )
        self._hdr_title.setFont(self._make_header_font(11))
        # Legend colors
        legend_colors = {'rx': c['fg'], 'tx': c['amber'], 'off': c['hex_offset']}
        for key, color in legend_colors.items():
            dot = self.findChild(QLabel, f'hex_legend_{key}')
            lbl = self.findChild(QLabel, f'hex_legend_lbl_{key}')
            if dot:
                dot.setStyleSheet(
                    f'color:{color};font-size:10px;background:transparent;')
            if lbl:
                lbl.setStyleSheet(
                    f'color:{c["fg_dim"]};font-family:"IBM Plex Mono",monospace;'
                    f'font-size:11px;background:transparent;')
                lbl.setFont(self._make_header_font(11))

        header = self._hdr_title.parent()
        header.setStyleSheet(
            f'background:{c["bg4"]};border-bottom:1px solid {c["border2"]};')
