"""
MainWindow: assembles all widgets, owns the char buffer, manages the
serial worker thread and demo mode timer.
"""
from __future__ import annotations

import math
import os
import random
import sys
import time
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QCloseEvent, QColor, QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFrame, QApplication, QMessageBox,
    QDialog, QLabel,
)

from serial_terminal import Char, __version__
from serial_terminal.config import load as cfg_load, save as cfg_save
from serial_terminal.logging_setup import get_logger
from serial_terminal.protocol import chars_to_text, encode_command, terminator_bytes
from serial_terminal.serial_worker import SerialWorker

_log = get_logger('main')
from serial_terminal.themes import THEMES, build_qss

from serial_terminal.widgets.toolbar     import ToolbarWidget
from serial_terminal.widgets.status_bar  import StatusBarWidget
from serial_terminal.widgets.terminal_view import TerminalView
from serial_terminal.widgets.ascii_strip import AsciiStrip
from serial_terminal.widgets.hex_panel   import HexPanel
from serial_terminal.widgets.chart_panel import ChartPanel
from serial_terminal.widgets.bottom_bar  import BottomBar
from serial_terminal.widgets.sidebar     import Sidebar


# ── Demo stream generators ────────────────────────────────────────────────

def _demo_sensor() -> str:
    t = time.monotonic()
    # V: fast sine (~8 s period) + moderate noise
    v    = 60.0 + 12.0 * math.sin(t * 0.75) + random.uniform(-2.0, 2.0)
    # T: slow sine (~2 min period) + small noise
    temp = 40.0 +  8.0 * math.sin(t * 0.05) + random.uniform(-0.4, 0.4)
    # H: medium sine (~30 s period) + medium noise, centre between T and V
    h    = 50.0 + 15.0 * math.sin(t * 0.21 + 1.0) + random.uniform(-1.2, 1.2)
    return f'T:{temp:.1f} V:{v:.1f} H:{h:.1f}\r\n'


def _demo_random() -> str:
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 '
    n = random.randint(3, 10)
    return ''.join(random.choice(chars) for _ in range(n)) + '\r\n'


def _demo_hex() -> str:
    return ' '.join(f'{random.randint(0, 255):02X}' for _ in range(16)) + '\r\n'


_DEMO_STREAMS = {
    'sensor': _demo_sensor,
    'random': _demo_random,
    'hex':    _demo_hex,
}


# ── About dialog ──────────────────────────────────────────────────────────

class _AboutDialog(QDialog):

    def __init__(self, colors: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('About Serial Terminal')
        self.setFixedWidth(420)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )
        c = colors

        py   = sys.version_info
        try:
            from PyQt6.QtCore import PYQT_VERSION_STR as qt_ver
        except ImportError:
            qt_ver = 'unknown'
        try:
            import matplotlib
            mpl_ver = matplotlib.__version__
        except ImportError:
            mpl_ver = 'not installed'

        self.setStyleSheet(
            f'QDialog{{background:{c["bg2"]};border:1px solid {c["border"]};}} '
            f'QLabel{{background:transparent;color:{c["fg_dim"]};'
            f'font-family:"IBM Plex Mono",monospace;font-size:10px;}} '
            f'QPushButton{{background:transparent;border:1px solid {c["border"]};'
            f'color:{c["fg_dim"]};padding:5px 20px;border-radius:2px;'
            f'font-family:"IBM Plex Mono",monospace;font-size:10px;}} '
            f'QPushButton:hover{{border-color:{c["fg_dim"]};color:{c["fg"]};'
            f'background:{c["fg_ghost"]};}}'
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(0)

        def title(text: str) -> QLabel:
            lbl = QLabel(text)
            font = QFont('IBM Plex Mono')
            font.setPointSize(16)
            font.setWeight(QFont.Weight.Medium)
            lbl.setFont(font)
            lbl.setStyleSheet(f'color:{c["fg"]};font-size:16px;font-weight:500;')
            return lbl

        def section(text: str) -> QLabel:
            lbl = QLabel(text.upper())
            lbl.setStyleSheet(
                f'color:{c["fg_faint"]};font-size:8px;letter-spacing:1px;'
                f'margin-top:16px;margin-bottom:4px;')
            return lbl

        def row(text: str, value: str) -> QWidget:
            w   = QWidget()
            w.setStyleSheet('background:transparent;')
            lay = QHBoxLayout(w)
            lay.setContentsMargins(0, 2, 0, 2)
            lay.setSpacing(8)
            lbl_k = QLabel(text)
            lbl_k.setStyleSheet(f'color:{c["fg_faint"]};font-size:10px;')
            lbl_k.setFixedWidth(110)
            lbl_v = QLabel(value)
            lbl_v.setStyleSheet(f'color:{c["fg"]};font-size:10px;')
            lbl_v.setWordWrap(True)
            lay.addWidget(lbl_k)
            lay.addWidget(lbl_v, 1)
            return w

        def divider() -> QFrame:
            f = QFrame()
            f.setFrameShape(QFrame.Shape.HLine)
            f.setStyleSheet(f'background:{c["border2"]};margin-top:12px;')
            f.setFixedHeight(1)
            return f

        # ── App title ──────────────────────────────────────────────────────
        root.addWidget(title('Serial Terminal'))
        lbl_sub = QLabel('Real-time serial monitor with live chart')
        lbl_sub.setStyleSheet(f'color:{c["fg_dim"]};font-size:10px;margin-top:4px;')
        root.addWidget(lbl_sub)
        lbl_ver = QLabel(f'Version {__version__}')
        lbl_ver.setObjectName('about_version')
        lbl_ver.setStyleSheet(f'color:{c["fg_faint"]};font-size:10px;margin-top:2px;')
        root.addWidget(lbl_ver)

        root.addWidget(divider())

        # ── Course ─────────────────────────────────────────────────────────
        root.addWidget(section('Academic context'))
        root.addWidget(row('Course',
            'Taller V — Microcontroladores y Lenguaje C'))
        root.addWidget(row('Institution',
            'Universidad Nacional de Colombia\nSede Medellín'))

        root.addWidget(divider())

        # ── Author ─────────────────────────────────────────────────────────
        root.addWidget(section('Author'))
        root.addWidget(row('Designed by', 'Nerio Andrés Montoya G.'))
        root.addWidget(row('Guidance',
            'Conceived and programmed under the direction and guidance of '
            'Nerio A. Montoya G.'))

        root.addWidget(divider())

        # ── Built with ─────────────────────────────────────────────────────
        root.addWidget(section('Built with'))
        root.addWidget(row('AI assistant', 'Claude (Anthropic)'))
        root.addWidget(row('Tooling', 'Claude Code'))
        root.addWidget(row('Programmed with', 'Claude Sonnet 4.6'))
        root.addWidget(row('Reviewed with',
            'Claude Opus 4.8 (check and bugs fixing)'))

        root.addWidget(divider())

        # ── Runtime ────────────────────────────────────────────────────────
        root.addWidget(section('Runtime'))
        root.addWidget(row('Python',
            f'{py.major}.{py.minor}.{py.micro}'))
        root.addWidget(row('PyQt6', qt_ver))
        root.addWidget(row('matplotlib', mpl_ver))

        root.addSpacing(20)

        # ── Close button ───────────────────────────────────────────────────
        btn_close = QPushButton('Close')
        btn_close.clicked.connect(self.accept)
        root.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignRight)


# ── Panel tab bar ─────────────────────────────────────────────────────────

class _TabBar(QWidget):
    """Minimal tab bar for Terminal / Chart."""

    def __init__(self, tabs: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('panel_tabs')
        self.setFixedHeight(28)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._buttons: list[QPushButton] = []
        self._callbacks: list = []
        for tab in tabs:
            btn = QPushButton(tab.upper())
            btn.setCheckable(True)
            btn.setObjectName('panel_tab')
            self._buttons.append(btn)
            layout.addWidget(btn)
        layout.addStretch()
        if self._buttons:
            self._set_active(0)

    def on_change(self, cb) -> None:
        self._callbacks.append(cb)
        for i, btn in enumerate(self._buttons):
            btn.clicked.connect(lambda _, idx=i: self._set_active(idx))

    def _set_active(self, idx: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == idx)
        for cb in self._callbacks:
            cb(idx)

    def apply_theme(self, c: dict[str, str]) -> None:
        for btn in self._buttons:
            btn.setStyleSheet(
                f'QPushButton{{padding:0 14px;font-family:"IBM Plex Mono",monospace;'
                f'font-size:9px;font-weight:500;letter-spacing:1px;'
                f'color:{c["fg_faint"]};border:none;border-bottom:2px solid transparent;'
                f'background:transparent;border-radius:0;}}'
                f'QPushButton:hover{{color:{c["fg_dim"]};}}'
                f'QPushButton:checked{{color:{c["fg"]};'
                f'border-bottom:2px solid {c["fg"]};}}'
            )


# ── MainWindow ────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Serial Terminal')
        self.resize(1280, 780)
        self.setMinimumSize(800, 500)

        # Config
        self._cfg        = cfg_load()
        self._theme_key  = self._cfg.get('theme', 'matrix')
        self._colors     = THEMES[self._theme_key]

        # App state
        self._chars:       list[Char] = []
        self._byte_count:  int        = 0
        self._tx_count:    int        = 0
        self._buf_size:    int        = self._cfg.get('buf_size', 10000)
        self._connected:   bool       = False
        self._demo_active: bool       = False
        self._demo_stream: str        = 'sensor'
        self._auto_save:   bool       = False
        self._active_terms: list[str] = list(
            self._cfg.get('active_terms', ['0x0D 0x0A']))

        self._worker:     SerialWorker | None = None
        self._demo_timer: QTimer | None       = None
        # Workers that have been asked to stop but may still be winding down.
        # Holding a Python reference here prevents a *running* QThread from
        # being garbage-collected (which makes Qt abort the process).
        self._graveyard:  list[SerialWorker]  = []

        # ── Build UI ──────────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Toolbar
        self._toolbar = ToolbarWidget(self._cfg)
        root.addWidget(self._toolbar)

        # Status bar
        self._statusbar = StatusBarWidget()
        root.addWidget(self._statusbar)

        # Body
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        root.addWidget(body, 1)

        # ── Left column ───────────────────────────────────────────────────
        left_col = QWidget()
        left_col.setObjectName('left_col')
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Tab bar
        self._tabs = _TabBar(['Terminal', 'Chart'])
        self._tabs.on_change(self._on_tab_change)
        left_layout.addWidget(self._tabs)

        # Terminal panel wrapper (panel_chars)
        self._panel_chars = QWidget()
        self._panel_chars.setObjectName('panel_chars')
        pc_layout = QVBoxLayout(self._panel_chars)
        pc_layout.setContentsMargins(0, 0, 0, 0)
        self._terminal_view = TerminalView(
            font_size=self._cfg.get('font_size', 13))
        self._chart_panel = ChartPanel()
        pc_layout.addWidget(self._terminal_view)
        pc_layout.addWidget(self._chart_panel)
        self._chart_panel.setVisible(False)
        left_layout.addWidget(self._panel_chars, 1)

        # ASCII strip
        self._ascii_strip = AsciiStrip()
        left_layout.addWidget(self._ascii_strip)

        # Bottom bar
        self._bottom_bar = BottomBar(self._cfg)
        left_layout.addWidget(self._bottom_bar)

        body_layout.addWidget(left_col, 1)

        # ── Hex panel ─────────────────────────────────────────────────────
        self._hex_panel = HexPanel()
        body_layout.addWidget(self._hex_panel)

        # ── Sidebar ───────────────────────────────────────────────────────
        self._sidebar = Sidebar(self._cfg)
        body_layout.addWidget(self._sidebar)

        # ── Wire signals ──────────────────────────────────────────────────
        self._connect_signals()

        # ── Apply initial theme ───────────────────────────────────────────
        self._apply_theme(self._theme_key)

        # ── Initial status bar update ─────────────────────────────────────
        self._update_status()

    # ── Signal wiring ─────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        tb = self._toolbar
        tb.connect_clicked.connect(self._on_connect_clicked)
        tb.demo_clicked.connect(self._on_demo_clicked)
        tb.about_clicked.connect(self._on_about)
        tb.port_changed.connect(lambda v: self._update_cfg('port', v))
        tb.baud_changed.connect(lambda v: self._update_cfg('baud', v))
        tb.data_bits_changed.connect(lambda v: self._update_cfg('data_bits', v))
        tb.parity_changed.connect(lambda v: self._update_cfg('parity', v))
        tb.stop_bits_changed.connect(lambda v: self._update_cfg('stop_bits', v))
        tb.flow_changed.connect(lambda v: self._update_cfg('flow', v))
        tb.local_echo_changed.connect(self._on_local_echo_changed)

        bb = self._bottom_bar
        bb.clear_clicked.connect(self._on_clear)
        bb.auto_scroll_changed.connect(self._terminal_view.set_auto_scroll)
        self._terminal_view.auto_scroll_changed.connect(bb.set_auto_scroll)
        bb.buf_size_changed.connect(self._on_buf_size_changed)
        bb.save_clicked.connect(self._on_save_file)
        bb.auto_save_changed.connect(lambda v: setattr(self, '_auto_save', v))

        sb = self._sidebar
        sb.send_command.connect(self._on_send_command)
        sb.send_preset.connect(self._on_send_command)
        sb.send_keypad.connect(self._on_send_ascii)
        sb.terms_changed.connect(self._on_terms_changed)
        sb.theme_changed.connect(self._apply_theme)
        sb.presets_changed.connect(
            lambda p: self._update_cfg('presets', p))
        sb.hex_presets_changed.connect(
            lambda p: self._update_cfg('hex_presets', p))
        sb.custom_terms_changed.connect(
            lambda t: self._update_cfg('custom_terms', t))

    # ── Theme ──────────────────────────────────────────────────────────────

    def _apply_theme(self, key: str) -> None:
        self._theme_key = key
        self._colors = THEMES.get(key, THEMES['matrix'])
        c = self._colors
        QApplication.instance().setStyleSheet(build_qss(c))
        self._toolbar.apply_theme(c)
        self._statusbar.apply_theme(c)
        self._tabs.apply_theme(c)
        self._terminal_view.apply_theme(c)
        self._ascii_strip.apply_theme(c)
        self._hex_panel.apply_theme(c)
        self._chart_panel.apply_theme(c)
        self._bottom_bar.apply_theme(c)
        self._sidebar.apply_theme(c)
        self._update_cfg('theme', key)

    # ── Tab switching ──────────────────────────────────────────────────────

    def _on_tab_change(self, idx: int) -> None:
        self._terminal_view.setVisible(idx == 0)
        self._chart_panel.setVisible(idx == 1)

    # ── Config helpers ─────────────────────────────────────────────────────

    def _update_cfg(self, key: str, value) -> None:
        self._cfg[key] = value
        cfg_save(self._cfg)

    # ── Connection ─────────────────────────────────────────────────────────

    def _on_about(self) -> None:
        dlg = _AboutDialog(self._colors, parent=self)
        dlg.exec()

    def _on_connect_clicked(self) -> None:
        if self._connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        if self._toolbar.current_port() is None:
            # Otherwise we'd try the stale saved port and show a cryptic
            # pyserial error — the common case of a missing USB driver.
            _log.warning('Connect clicked with no serial port detected')
            QMessageBox.warning(
                self, 'No serial port',
                'No serial port detected.\n\n'
                'Plug in the board and click ↺ next to PORT.\n'
                'If it still does not appear, the USB driver may be missing '
                '(see INSTALL.md → Troubleshooting).')
            return

        if self._demo_active:
            self._stop_demo()

        port = self._cfg.get('port', '/dev/ttyUSB0')
        _log.info('Connecting to %s', port)
        self._worker = SerialWorker(
            port      = port,
            baud      = self._cfg.get('baud', 9600),
            data_bits = self._cfg.get('data_bits', 8),
            parity    = self._cfg.get('parity', 'none'),
            stop_bits = self._cfg.get('stop_bits', 1),
            flow      = self._cfg.get('flow', 'none'),
        )
        self._worker.data_received.connect(self._on_data)
        self._worker.connected.connect(self._on_worker_connected)
        self._worker.disconnected.connect(self._on_worker_disconnected)
        self._worker.error_occurred.connect(self._on_worker_error)
        # Reap the QThread object only once it has truly finished.
        self._worker.finished.connect(
            lambda w=self._worker: self._reap_worker(w))
        self._worker.start()

    def _disconnect(self) -> None:
        _log.info('Disconnecting')
        self._retire_worker()
        self._set_connected(False)

    def _retire_worker(self) -> None:
        """Ask the active worker to stop without ever GC-ing it while alive."""
        w = self._worker
        if w is None:
            return
        self._worker = None
        if w not in self._graveyard:
            self._graveyard.append(w)   # keep a reference until 'finished'
        w.stop()

    def _reap_worker(self, w: SerialWorker) -> None:
        if w in self._graveyard:
            self._graveyard.remove(w)
        w.deleteLater()

    @pyqtSlot()
    def _on_worker_connected(self) -> None:
        self._set_connected(True)

    @pyqtSlot()
    def _on_worker_disconnected(self) -> None:
        self._set_connected(False)

    @pyqtSlot(str)
    def _on_worker_error(self, msg: str) -> None:
        _log.error('Serial error reported to UI: %s', msg)
        self._set_connected(False)
        QMessageBox.critical(self, 'Serial Error', msg)

    def _set_connected(self, value: bool) -> None:
        self._connected = value
        self._toolbar.set_connected(value)
        self._sidebar.set_connected(value)
        self._update_status()

    # ── Demo mode ──────────────────────────────────────────────────────────

    def _on_demo_clicked(self) -> None:
        if self._demo_active:
            self._stop_demo()
        elif not self._connected:
            self._start_demo()

    def _start_demo(self) -> None:
        self._demo_active = True
        self._toolbar.set_demo_active(True)
        baud = self._cfg.get('baud', 9600)
        interval = max(80, int(50_000 / baud) * 10)
        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._demo_tick)
        self._demo_timer.start(interval)
        self._update_status()

    def _stop_demo(self) -> None:
        if self._demo_timer:
            self._demo_timer.stop()
            self._demo_timer = None
        self._demo_active = False
        self._toolbar.set_demo_active(False)
        self._update_status()

    def _demo_tick(self) -> None:
        text = _DEMO_STREAMS.get(self._demo_stream, _demo_sensor)()
        raw = text.encode('latin-1', errors='replace')
        self._on_data(raw)

    # ── Incoming data ──────────────────────────────────────────────────────

    @pyqtSlot(bytes)
    def _on_data(self, raw: bytes) -> None:
        new_chars = [Char(code=b, sent=False) for b in raw]
        self._chars.extend(new_chars)
        self._byte_count += len(new_chars)

        # Trim buffer
        if len(self._chars) > self._buf_size:
            self._chars = self._chars[-self._buf_size:]

        # Update widgets
        self._terminal_view.push_chars(new_chars)
        self._chart_panel.push_chars(new_chars)
        self._ascii_strip.update_chars(self._chars)
        self._hex_panel.update_chars(self._chars)
        self._update_status()

    # ── Sending ────────────────────────────────────────────────────────────

    @pyqtSlot(str, str)
    def _on_send_command(self, text: str, mode: str) -> None:
        out_bytes = encode_command(text, mode, terminator_bytes(self._active_terms))
        if out_bytes is None:
            return   # invalid HEX token — send nothing

        if self._worker:
            self._worker.send(out_bytes)

        self._tx_count += len(out_bytes)

        if not self._cfg.get('local_echo', True):
            return   # device output only — see toolbar ECHO checkbox

        # Echo to terminal
        echo_chars = [Char(code=b, sent=True) for b in out_bytes]
        self._chars.extend(echo_chars)
        self._terminal_view.push_chars(echo_chars)
        self._ascii_strip.update_chars(self._chars)
        self._hex_panel.update_chars(self._chars)

    @pyqtSlot(bool)
    def _on_local_echo_changed(self, enabled: bool) -> None:
        self._update_cfg('local_echo', enabled)

    @pyqtSlot(str)
    def _on_send_ascii(self, text: str) -> None:
        self._on_send_command(text, 'ASCII')

    # ── Terminators ────────────────────────────────────────────────────────

    @pyqtSlot(list)
    def _on_terms_changed(self, terms: list[str]) -> None:
        self._active_terms = terms
        self._update_cfg('active_terms', terms)
        self._update_status()

    # ── Buffer / file ──────────────────────────────────────────────────────

    def _on_clear(self) -> None:
        self._chars.clear()
        self._byte_count = 0
        self._tx_count   = 0
        self._terminal_view.clear_buffer()
        self._chart_panel.clear_buffer()
        self._ascii_strip.update_chars([])
        self._hex_panel.update_chars([])
        self._update_status()

    def _on_buf_size_changed(self, size: int) -> None:
        self._buf_size = size
        self._update_cfg('buf_size', size)

    def _timestamped_filename(self) -> str:
        base = os.path.splitext(self._bottom_bar.get_filename())[0] or 'capture'
        ts   = datetime.now().strftime('%d%m%y_%H%M%S')
        return f'{base}_{ts}.txt'

    def _on_save_file(self, filename: str) -> None:
        if not self._chars:
            return
        fname = filename.strip() or 'capture.txt'
        text = chars_to_text(self._chars[-self._buf_size:])
        try:
            with open(fname, 'w', encoding='utf-8') as fh:
                fh.write(text)
        except OSError as exc:
            QMessageBox.warning(self, 'Save Failed', str(exc))

    # ── Status bar ─────────────────────────────────────────────────────────

    def _update_status(self) -> None:
        self._statusbar.update_status(
            connected    = self._connected,
            demo         = self._demo_active,
            byte_count   = self._byte_count,
            tx_count     = self._tx_count,
            port         = self._cfg.get('port', '/dev/ttyUSB0'),
            baud         = self._cfg.get('baud', 9600),
            data_bits    = self._cfg.get('data_bits', 8),
            parity       = self._cfg.get('parity', 'none'),
            stop_bits    = self._cfg.get('stop_bits', 1),
            active_terms = self._active_terms,
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        _log.info('Application closing')
        if self._auto_save and self._chars:
            self._on_save_file(self._timestamped_filename())
        self._stop_demo()
        # Stop the active worker and any still winding down, so no running
        # QThread is destroyed on shutdown (which would abort the process).
        self._retire_worker()
        for w in list(self._graveyard):
            w.stop()
        self._cfg['presets']     = self._sidebar.get_presets()
        self._cfg['hex_presets'] = self._sidebar.get_hex_presets()
        cfg_save(self._cfg)
        event.accept()
