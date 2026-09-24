"""
Central logging configuration.

Writes rotating log files to ~/.config/serial_terminal/logs/ and installs
hooks so that *uncaught* exceptions — in the main thread, in worker threads,
and inside Qt slots — are recorded instead of silently killing the app.

PyQt note: by default PyQt6 aborts the whole process (via qFatal) when a
Python exception escapes a slot or a QThread.run(). Installing a custom
sys.excepthook — as done here — both records the traceback AND prevents that
abort, so a stray bug logs an error and the app keeps running instead of
vanishing with no explanation.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
import threading
from pathlib import Path

LOG_DIR  = Path.home() / '.config' / 'serial_terminal' / 'logs'
LOG_FILE = LOG_DIR / 'serial_terminal.log'

_MAX_BYTES = 1_000_000   # 1 MB per file before rotation
_BACKUPS   = 5           # keep 5 old files

_configured = False


# ── Setup ──────────────────────────────────────────────────────────────────

def setup(level: int = logging.INFO) -> logging.Logger:
    """Configure the 'serial_terminal' logger. Safe to call more than once."""
    global _configured
    root = logging.getLogger('serial_terminal')
    if _configured:
        return root

    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        '%(asctime)s %(levelname)-7s [%(threadName)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    # File handler (rotating) — full DEBUG detail
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUPS,
            encoding='utf-8',
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass  # file logging unavailable — console handler below still works

    # Console handler — quieter
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    _configured = True
    root.info('──────── logging started — file: %s ────────', LOG_FILE)
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a child logger, e.g. get_logger('serial') → serial_terminal.serial."""
    return logging.getLogger(f'serial_terminal.{name}')


# ── Exception hooks ─────────────────────────────────────────────────────────

def install_excepthooks() -> None:
    """
    Route uncaught exceptions to the log instead of the default handler.

    Replacing sys.excepthook also stops PyQt6 from calling qFatal() on an
    unhandled slot/thread exception, so the application survives bugs that
    would otherwise close it silently.
    """
    log = logging.getLogger('serial_terminal')

    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical('Uncaught exception',
                     exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = _excepthook

    # Python 3.8+: exceptions escaping a threading.Thread.run()
    if hasattr(threading, 'excepthook'):
        def _thread_excepthook(args):
            if args.exc_type is SystemExit:
                return
            name = args.thread.name if args.thread else '?'
            log.critical('Uncaught exception in thread %s', name,
                         exc_info=(args.exc_type, args.exc_value,
                                   args.exc_traceback))
        threading.excepthook = _thread_excepthook


def install_qt_message_handler() -> None:
    """Funnel Qt's own messages (warnings, fatal errors) into the log.

    This captures C++-side conditions such as
    'QThread: Destroyed while thread is still running' that Python hooks
    cannot see — invaluable for diagnosing a hard crash on exit.
    """
    try:
        from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
    except ImportError:
        return

    log = logging.getLogger('serial_terminal.qt')
    levels = {
        QtMsgType.QtDebugMsg:    logging.DEBUG,
        QtMsgType.QtInfoMsg:     logging.INFO,
        QtMsgType.QtWarningMsg:  logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg:    logging.CRITICAL,
    }

    def _handler(msg_type, context, message):
        log.log(levels.get(msg_type, logging.INFO), 'Qt: %s', message)

    qInstallMessageHandler(_handler)
