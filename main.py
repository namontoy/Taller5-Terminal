"""
Serial Terminal — entry point.
Run with:  python main.py
"""
import sys

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

from serial_terminal import __version__, logging_setup
from serial_terminal.main_window import MainWindow


def main() -> None:
    # ── Logging first, so anything below is captured ───────────────────────
    log = logging_setup.setup()
    logging_setup.install_excepthooks()
    logging_setup.install_qt_message_handler()
    log.info('Serial Terminal %s starting up', __version__)

    app = QApplication(sys.argv)
    app.setApplicationName('Serial Terminal')
    app.setOrganizationName('Taller5')

    # Try to use JetBrains Mono; fall back gracefully to system monospace
    preferred = QFont('JetBrains Mono')
    preferred.setStyleHint(QFont.StyleHint.Monospace)
    preferred.setPointSize(11)
    app.setFont(preferred)

    try:
        window = MainWindow()
        window.show()
    except Exception:
        log.critical('Failed to build main window', exc_info=True)
        raise

    exit_code = app.exec()
    log.info('Serial Terminal exited with code %d', exit_code)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
