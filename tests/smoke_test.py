"""
Start-up smoke test: builds the real main window without a screen and
exercises the parts that don't need serial hardware.

    QT_QPA_PLATFORM=offscreen python tests/smoke_test.py

Exits with a non-zero code on failure. Used by the GitHub Actions workflow
on Linux, Windows and macOS; also handy locally before a push.
"""
import logging
import os
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

from PyQt6.QtWidgets import QApplication  # noqa: E402

from serial_terminal import logging_setup, main_window  # noqa: E402
from serial_terminal.themes import THEMES  # noqa: E402
from serial_terminal.widgets import toolbar  # noqa: E402

# A port name of the kind this OS really produces
_FAKE_PORT = {'win32': 'COM7', 'darwin': '/dev/cu.usbserial-SMOKE'}.get(
    sys.platform, '/dev/ttyUSB7')

_failures: list[str] = []


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
    app = QApplication(sys.argv)

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

    # ── Every theme applies ───────────────────────────────────────────────
    for key in THEMES:
        w._sidebar._select_theme(key)
        pump(app, 0.1)
    check('all themes applied', True)

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
