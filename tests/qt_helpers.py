"""
Shared helpers for tests that need Qt (not collected as a test module).

Tests run without a screen: the offscreen platform is selected unless the
caller already chose one.
"""
import os
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication  # noqa: E402

_app: QApplication | None = None


def get_app() -> QApplication:
    """The single QApplication for this test process."""
    global _app
    _app = QApplication.instance() or QApplication([])
    return _app


def wait_until(condition, timeout: float = 3.0) -> bool:
    """Process Qt events until *condition()* is true or *timeout* seconds pass.

    Needed for signals emitted from worker threads, which are delivered
    through the event loop.
    """
    app = get_app()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    app.processEvents()
    return bool(condition())
