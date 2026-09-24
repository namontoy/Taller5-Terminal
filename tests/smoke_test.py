"""
Start-up smoke test: builds the real main window without a screen and
exercises the parts that don't need serial hardware.

It also fails on Qt stylesheet warnings. A widget stylesheet Qt cannot parse
is silently ignored (the app looks wrong but keeps running), so the only
trace is a warning — this test turns that warning into a failure.

    QT_QPA_PLATFORM=offscreen python tests/smoke_test.py

Exits with a non-zero code on failure. Used by the GitHub Actions workflow
on Linux, Windows and macOS; also handy locally before a push.
"""
import logging
import os
import re
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest import mock

# Isolated home folder *before* importing the app: config and log paths are
# computed at import time, and a real user config must never be touched.
_HOME = tempfile.mkdtemp(prefix='serial_terminal_smoke_')
os.environ['HOME'] = _HOME          # Linux / macOS
os.environ['USERPROFILE'] = _HOME   # Windows
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6 import sip  # noqa: E402
from PyQt6.QtCore import qInstallMessageHandler  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

from serial_terminal import logging_setup, main_window  # noqa: E402
from serial_terminal.themes import THEMES  # noqa: E402
from serial_terminal.widgets import toolbar  # noqa: E402

# A port name of the kind this OS really produces
_FAKE_PORT = {'win32': 'COM7', 'darwin': '/dev/cu.usbserial-SMOKE'}.get(
    sys.platform, '/dev/ttyUSB7')

_failures: list[str] = []

# Qt messages meaning "a stylesheet was ignored". Other Qt warnings (e.g. the
# offscreen platform's propagateSizeHints notice, macOS font-alias notices)
# are printed but don't fail the test.
_STYLE_ERROR_RE = re.compile(
    r'Could not parse (application )?stylesheet|Unknown property')
_qt_messages: list[str] = []
_culprits: dict[str, str] = {}   # style error message -> widget description


def _describe_widget(message: str) -> str:
    """Turn 'Could not parse stylesheet of object QLabel(0x55…)' into the
    widget's name, text and parent, so a failure says where to look."""
    m = re.search(r'\((0x[0-9a-fA-F]+)', message)
    app = QApplication.instance()
    if not (m and app):
        return ''
    address = int(m.group(1), 16)
    for w in app.allWidgets():
        if sip.unwrapinstance(w) == address:
            text = getattr(w, 'text', lambda: '')()
            parent = type(w.parent()).__name__ if w.parent() else '-'
            return (f'{type(w).__name__} name={w.objectName()!r} '
                    f'text={text[:30]!r} parent={parent} '
                    f'sheet={w.styleSheet()[:90]!r}')
    return ''


def _record_qt_message(mode, context, message: str) -> None:
    _qt_messages.append(message)
    if _STYLE_ERROR_RE.search(message) and message not in _culprits:
        _culprits[message] = _describe_widget(message)


def style_errors() -> list[str]:
    return [m for m in _qt_messages if _STYLE_ERROR_RE.search(m)]


def check(label: str, condition: bool) -> None:
    print(('PASS  ' if condition else 'FAIL  ') + label, flush=True)
    if not condition:
        _failures.append(label)


def pump(app: QApplication, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    print(f'platform={sys.platform}  home={_HOME}', flush=True)
    logging_setup.setup()
    # Deliberately no install_excepthooks(): an exception in a slot must
    # abort the process so this test fails loudly.
    qInstallMessageHandler(_record_qt_message)
    app = QApplication(sys.argv)

    # ── The guard itself works on this OS: a broken sheet must be caught ──
    # (bare declarations mixed with a selector rule: the Connect-button bug)
    probe = QLabel('probe')
    probe.setStyleSheet('color: red; QLabel:hover { color: blue; }')
    probe.show()
    pump(app, 0.1)
    check('stylesheet guard detects a broken stylesheet', bool(style_errors()))
    # Delete the probe for good: a merely hidden widget is re-polished on
    # every theme change and would report its broken sheet again.
    probe.setStyleSheet('')
    sip.delete(probe)   # immediately; deleteLater needs a running event loop
    _qt_messages.clear()
    _culprits.clear()

    with mock.patch.object(toolbar._list_ports, 'comports', return_value=[]):
        w = main_window.MainWindow()
    w.resize(1280, 800)
    w.show()
    pump(app, 0.5)
    tb = w._toolbar

    # ── No port: Connect must explain instead of trying a stale port ──────
    check('no port detected -> current_port() is None',
          tb.current_port() is None)
    with mock.patch.object(main_window.QMessageBox, 'warning') as warn:
        w._on_connect_clicked()
    check('Connect with no port shows a warning', warn.called)
    check('Connect with no port starts no serial thread', w._worker is None)

    # ── A port of this OS's kind appears and is selectable ────────────────
    with mock.patch.object(toolbar._list_ports, 'comports',
                           return_value=[SimpleNamespace(device=_FAKE_PORT)]):
        tb._scan_ports()
    check(f'rescan finds {_FAKE_PORT}', tb.current_port() == _FAKE_PORT)
    check('selected port saved to config', w._cfg.get('port') == _FAKE_PORT)

    # ── Demo data flows through every view ────────────────────────────────
    w._on_demo_clicked()
    pump(app, 2.0)
    check('demo mode receives data', w._byte_count > 0)
    w._tabs._set_active(1)          # chart tab
    pump(app, 0.6)
    w._tabs._set_active(0)
    w._on_demo_clicked()            # stop demo
    check('demo mode stops', not w._demo_active)

    # ── Sending with and without local echo ───────────────────────────────
    before = len(w._chars)
    w._on_send_command('PING', 'ASCII')
    check('local echo on: sent bytes shown', len(w._chars) > before)
    tb._echo.setChecked(False)
    before = len(w._chars)
    w._on_send_command('PING', 'ASCII')
    check('local echo off: sent bytes hidden', len(w._chars) == before)

    # ── Every styled state, in every theme: no stylesheet may be ignored ──
    sb = w._sidebar
    sb._custom_term_input.setText('@')
    sb._add_custom_term()                       # custom terminator chip
    for key in THEMES:
        sb._select_theme(key)
        for connected in (True, False):
            w._set_connected(connected)         # Connect button, keypad, …
            for mode in ('HEX', 'ASCII'):
                sb._set_mode(mode)              # command box mode
                sb._switch_preset_tab(1 if mode == 'HEX' else 0)
                pump(app, 0.05)
        w._on_demo_clicked()                    # Demo button + [DEMO] label
        pump(app, 0.2)
        w._on_demo_clicked()
        w._hex_panel._btn_toggle.click()        # collapse / reopen hex dump
        pump(app, 0.4)
        w._hex_panel._btn_toggle.click()
        pump(app, 0.4)
        about = main_window._AboutDialog(w._colors, parent=w)
        about.show()
        pump(app, 0.1)
        about.close()
    errors = style_errors()
    check('no ignored stylesheets in any theme or state', not errors)
    for m in sorted(set(errors)):
        print(f'      stylesheet error: {m}', flush=True)
        print(f'        widget: {_culprits.get(m) or "(already deleted)"}',
              flush=True)
    for m in sorted(set(_qt_messages) - set(errors)):
        print(f'INFO  other Qt message: {m[:120]}', flush=True)

    w.close()
    pump(app, 0.3)
    print(f'{len(_failures)} failure(s)' if _failures else 'ALL PASSED',
          flush=True)
    return 1 if _failures else 0


if __name__ == '__main__':
    code = main()
    logging.shutdown()   # release the log file so the folder can be removed
    shutil.rmtree(_HOME, ignore_errors=True)
    # Skip interpreter teardown of Qt objects; the result is already decided.
    os._exit(code)
