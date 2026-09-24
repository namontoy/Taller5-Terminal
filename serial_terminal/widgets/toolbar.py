"""
Top toolbar: port, baud, data bits, parity, stop bits, flow, local echo,
connect button.
"""
import re
import sys

from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QColor, QPainter, QBrush
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel,
    QCheckBox, QComboBox, QPushButton, QFrame, QSizePolicy,
)

from serial_terminal.themes import BAUDS

try:
    from serial.tools import list_ports as _list_ports
    _SERIAL_TOOLS_OK = True
except ImportError:
    _SERIAL_TOOLS_OK = False

# Linux whitelist: only USB serial and ACM adapters (Arduino, FTDI, CH340,
# CP210x, etc.). Hides legacy /dev/ttyS* ports, which pyserial still lists.
_LINUX_PORT_RE = re.compile(
    r'^/dev/(ttyUSB|ttyACM|ttyAMA|ttyXRUSB|rfcomm)\d+$'
)

# macOS built-in pseudo ports. Hidden by name (not by "has a USB VID") so
# paired Bluetooth serial modules such as an HC-05 remain selectable.
_MACOS_HIDDEN = ('Bluetooth-Incoming-Port', 'debug-console', 'wlan-debug')

_NO_PORT = '(none detected)'


def _is_user_port(device: str, platform: str | None = None) -> bool:
    """True if *device* is a port a user would want to pick on *platform*
    (default: the running system)."""
    platform = platform or sys.platform
    if platform.startswith('linux'):
        return bool(_LINUX_PORT_RE.match(device))
    if platform == 'darwin':
        # pyserial reports only the callout devices (/dev/cu.*) on macOS
        return (device.startswith('/dev/cu.')
                and not any(h in device for h in _MACOS_HIDDEN))
    # Windows (COMn) and other systems: pyserial lists only ports that exist
    return True


def _natural_key(device: str) -> list:
    """Sort key so COM2 < COM10 and ttyUSB2 < ttyUSB10."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r'(\d+)', device)]


def _scan_serial_ports() -> list[str]:
    """Return the selectable serial ports on this system, naturally sorted."""
    if not _SERIAL_TOOLS_OK:
        return []
    return sorted(
        (p.device for p in _list_ports.comports() if _is_user_port(p.device)),
        key=_natural_key,
    )


class _DotWidget(QWidget):
    """Animated status dot (blinking when connected)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(8, 8)
        self._connected = False
        self._blink_on  = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._colors: dict[str, str] = {}

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        if connected:
            self._blink_on = True
            self._timer.start(1000)   # 2-state blink: 1 s per phase
        else:
            self._timer.stop()
            self._blink_on = False
        self.update()

    def apply_theme(self, c: dict[str, str]) -> None:
        self._colors = c
        self.update()

    def _tick(self) -> None:
        self._blink_on = not self._blink_on
        self.update()

    def paintEvent(self, event) -> None:
        if not self._colors:
            return
        c = self._colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._connected and self._blink_on:
            color = QColor(c['fg'])
        elif self._connected:
            color = QColor(c['fg_faint'])
        else:
            color = QColor(c['fg_dim'])
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 8, 8)


class _Divider(QFrame):
    """Thin vertical separator between toolbar groups."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setFixedWidth(1)


class ToolbarWidget(QWidget):
    """Main toolbar row."""

    connect_clicked    = pyqtSignal()
    port_changed       = pyqtSignal(str)
    baud_changed       = pyqtSignal(int)
    data_bits_changed  = pyqtSignal(int)
    parity_changed     = pyqtSignal(str)
    stop_bits_changed  = pyqtSignal(float)
    flow_changed       = pyqtSignal(str)
    local_echo_changed = pyqtSignal(bool)
    demo_clicked       = pyqtSignal()
    about_clicked      = pyqtSignal()

    def __init__(self, cfg: dict, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('toolbar')
        self.setFixedHeight(40)
        self._colors: dict[str, str] = {}
        self._connected   = False
        self._demo_active = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        def group(*widgets):
            w = QWidget()
            w.setObjectName('toolbar')
            w.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            h = QHBoxLayout(w)
            h.setContentsMargins(9, 0, 9, 0)
            h.setSpacing(5)
            for ww in widgets:
                h.addWidget(ww)
            layout.addWidget(w)
            layout.addWidget(_Divider())
            return w

        # Port — dropdown populated from detected serial ports
        self._port = QComboBox()
        self._port.setFixedWidth(148)
        self._port.setToolTip('Select serial port')
        self._port.currentTextChanged.connect(self._on_port_selected)

        self._btn_refresh = QPushButton('↺')
        self._btn_refresh.setFixedSize(22, 22)
        self._btn_refresh.setToolTip('Rescan serial ports')
        self._btn_refresh.clicked.connect(self._scan_ports)

        self._saved_port = cfg.get('port', '/dev/ttyUSB0')
        self._scan_ports()   # populate on startup

        group(QLabel('PORT'), self._port, self._btn_refresh)

        # Baud
        self._baud = QComboBox()
        for b in BAUDS:
            self._baud.addItem(f'{b:,}', b)
        self._baud.setCurrentIndex(
            BAUDS.index(cfg.get('baud', 9600)) if cfg.get('baud', 9600) in BAUDS else 4)
        self._baud.currentIndexChanged.connect(
            lambda: self.baud_changed.emit(self._baud.currentData()))
        group(QLabel('BAUD'), self._baud)

        # Data bits
        self._data = QComboBox()
        for b in [5, 6, 7, 8]:
            self._data.addItem(str(b), b)
        self._data.setCurrentText(str(cfg.get('data_bits', 8)))
        self._data.setFixedWidth(44)
        self._data.currentIndexChanged.connect(
            lambda: self.data_bits_changed.emit(self._data.currentData()))
        group(QLabel('DATA'), self._data)

        # Parity
        self._parity = QComboBox()
        for p in ['none', 'even', 'odd', 'mark', 'space']:
            self._parity.addItem(p, p)
        self._parity.setCurrentText(cfg.get('parity', 'none'))
        self._parity.currentIndexChanged.connect(
            lambda: self.parity_changed.emit(self._parity.currentData()))
        group(QLabel('PARITY'), self._parity)

        # Stop bits
        self._stop = QComboBox()
        for s in [1, 1.5, 2]:
            self._stop.addItem(str(s), s)
        self._stop.setCurrentText(str(cfg.get('stop_bits', 1)))
        self._stop.setFixedWidth(48)
        self._stop.currentIndexChanged.connect(
            lambda: self.stop_bits_changed.emit(self._stop.currentData()))
        group(QLabel('STOP'), self._stop)

        # Flow control
        self._flow = QComboBox()
        for f in ['none', 'RTS/CTS', 'XON/XOFF']:
            self._flow.addItem(f, f)
        self._flow.setCurrentText(cfg.get('flow', 'none'))
        self._flow.currentIndexChanged.connect(
            lambda: self.flow_changed.emit(self._flow.currentData()))
        group(QLabel('FLOW'), self._flow)

        # Local echo — show sent bytes in the terminal. Display-only, so it
        # stays enabled while connected (unlike the port settings above).
        self._echo = QCheckBox()
        self._echo.setChecked(bool(cfg.get('local_echo', True)))
        self._echo.setToolTip(
            'Local echo: show sent commands in the terminal.\n'
            'Turn off when the device echoes commands back itself.')
        self._echo.toggled.connect(self.local_echo_changed)
        echo_lbl = QLabel('ECHO')
        echo_lbl.setToolTip(self._echo.toolTip())
        echo_lbl.setBuddy(self._echo)
        group(echo_lbl, self._echo)

        layout.addStretch()

        # Demo button
        self._btn_demo = QPushButton('Demo')
        self._btn_demo.setObjectName('btn_demo')
        self._btn_demo.setToolTip('Simulate data without hardware')
        self._btn_demo.setFixedHeight(28)
        self._btn_demo.clicked.connect(self.demo_clicked)

        # About button
        self._btn_about = QPushButton('About')
        self._btn_about.setObjectName('btn_about')
        self._btn_about.setToolTip('About this application')
        self._btn_about.setFixedHeight(28)
        self._btn_about.clicked.connect(self.about_clicked)

        # Connect button + dot
        self._dot = _DotWidget()
        self._btn_connect = QPushButton('Connect')
        self._btn_connect.setObjectName('btn_connect')
        self._btn_connect.setFixedHeight(28)
        self._btn_connect.clicked.connect(self.connect_clicked)

        right = QWidget()
        right.setObjectName('toolbar')
        rh = QHBoxLayout(right)
        rh.setContentsMargins(9, 0, 9, 0)
        rh.setSpacing(8)
        rh.addWidget(self._btn_demo)
        rh.addWidget(self._btn_about)
        rh.addWidget(self._dot)
        rh.addWidget(self._btn_connect)
        layout.addWidget(right)

    # ── Public API ─────────────────────────────────────────────────────────
    def set_connected(self, connected: bool) -> None:
        self._dot.set_connected(connected)
        self._btn_connect.setText('Disconnect' if connected else 'Connect')
        for w in [self._port, self._btn_refresh, self._baud, self._data,
                  self._parity, self._stop, self._flow]:
            w.setEnabled(not connected)

        self._connected = connected
        self._apply_state_styles()

    def set_demo_active(self, active: bool) -> None:
        self._demo_active = active
        self._apply_state_styles()

    def _apply_state_styles(self) -> None:
        """Colour the Connect/Demo buttons for the current state and theme.

        Per-widget sheets must use full selector rules: mixing bare
        declarations with a `QPushButton:hover {…}` rule is unparseable and
        Qt silently drops the whole sheet.
        """
        c = self._colors
        if self._connected and c:
            red = c['red']
            self._btn_connect.setStyleSheet(
                f'QPushButton {{ border-color:{red}; color:{red}; }}'
                f'QPushButton:hover {{ border-color:{red}; color:{red};'
                f' background-color:rgba(220,50,50,30); }}'
            )
        else:
            self._btn_connect.setStyleSheet('')

        if self._demo_active and c:
            self._btn_demo.setStyleSheet(
                f'border-color:{c["amber"]};color:{c["amber"]};')
        else:
            self._btn_demo.setStyleSheet('')

    def _scan_ports(self) -> None:
        """Rescan for available serial ports and repopulate the dropdown."""
        ports = _scan_serial_ports()
        self._port.blockSignals(True)
        self._port.clear()
        if ports:
            for p in ports:
                self._port.addItem(p)
            idx = self._port.findText(self._saved_port)
            self._port.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self._port.addItem(_NO_PORT)
        self._port.blockSignals(False)

        # Long names (e.g. macOS /dev/cu.usbserial-A50285BI) overflow the
        # fixed-width combo: widen only the drop-down list, not the toolbar.
        # Measure with the combo's own font: the view's size hint ignores the
        # stylesheet font and underestimates.
        fm = self._port.fontMetrics()
        longest = max((fm.horizontalAdvance(p) for p in ports), default=0)
        self._port.view().setMinimumWidth(max(self._port.width(), longest + 32))

        selected = self._port.currentText()
        self._port.setToolTip(selected if ports else 'No serial port detected')
        if ports:
            self.port_changed.emit(selected)

    def _on_port_selected(self, text: str) -> None:
        if text and text != _NO_PORT:
            self._saved_port = text
            self._port.setToolTip(text)
            self.port_changed.emit(text)

    def current_port(self) -> str | None:
        """The selected port, or None when no port was detected."""
        text = self._port.currentText()
        return text if text and text != _NO_PORT else None

    def apply_theme(self, c: dict[str, str]) -> None:
        self._colors = c
        self._dot.apply_theme(c)
        for child in self.findChildren(_Divider):
            child.setStyleSheet(f'color: {c["border2"]};')
        self._apply_state_styles()
