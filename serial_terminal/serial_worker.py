"""
QThread that owns a pyserial port and emits received bytes via signal.
Sending is done thread-safely through a bytes queue.
"""
import queue
import time

import serial
from PyQt6.QtCore import QThread, pyqtSignal

from serial_terminal.logging_setup import get_logger

_log = get_logger('serial')


class SerialWorker(QThread):
    data_received  = pyqtSignal(bytes)   # raw bytes from the port
    error_occurred = pyqtSignal(str)     # human-readable error string
    connected      = pyqtSignal()        # port opened successfully
    disconnected   = pyqtSignal()        # port closed (normal or error)

    def __init__(
        self,
        port: str,
        baud: int,
        data_bits: int,
        parity: str,
        stop_bits: float,
        flow: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._port      = port
        self._baud      = baud
        self._data_bits = data_bits
        self._parity    = self._map_parity(parity)
        self._stop_bits = self._map_stopbits(stop_bits)
        self._flow      = flow
        self._send_queue: queue.Queue[bytes] = queue.Queue()
        self._running   = False

    # ── pyserial enum mapping ──────────────────────────────────────────────
    @staticmethod
    def _map_parity(p: str) -> str:
        return {
            'none':  serial.PARITY_NONE,
            'even':  serial.PARITY_EVEN,
            'odd':   serial.PARITY_ODD,
            'mark':  serial.PARITY_MARK,
            'space': serial.PARITY_SPACE,
        }.get(p.lower(), serial.PARITY_NONE)

    @staticmethod
    def _map_stopbits(s: float):
        return {
            1:   serial.STOPBITS_ONE,
            1.5: serial.STOPBITS_ONE_POINT_FIVE,
            2:   serial.STOPBITS_TWO,
        }.get(s, serial.STOPBITS_ONE)

    # ── Public API ─────────────────────────────────────────────────────────
    def send(self, data: bytes) -> None:
        """Queue bytes to be written to the port."""
        self._send_queue.put(data)

    def stop(self) -> None:
        """Signal the thread to stop and wait for it to finish."""
        self._running = False
        if not self.wait(3000):
            _log.warning('Serial thread for %s did not stop within 3 s',
                         self._port)

    # ── Thread body ────────────────────────────────────────────────────────
    def run(self) -> None:
        rtscts = self._flow == 'RTS/CTS'
        xonxoff = self._flow == 'XON/XOFF'

        try:
            ser = serial.Serial(
                port=self._port,
                baudrate=self._baud,
                bytesize=self._data_bits,
                parity=self._parity,
                stopbits=self._stop_bits,
                rtscts=rtscts,
                xonxoff=xonxoff,
                timeout=0.05,        # non-blocking read with short timeout
                write_timeout=2.0,   # never block the loop forever on write
            )
        except (serial.SerialException, OSError, ValueError) as exc:
            _log.error('Failed to open %s @ %d baud: %s',
                       self._port, self._baud, exc)
            self.error_occurred.emit(str(exc))
            return

        _log.info('Opened %s @ %d baud (%d%s%s)', self._port, self._baud,
                  self._data_bits, self._parity, self._stop_bits)
        self._running = True
        self.connected.emit()

        try:
            while self._running:
                try:
                    # Read incoming bytes
                    waiting = ser.in_waiting
                    if waiting:
                        raw = ser.read(waiting)
                        if raw:
                            self.data_received.emit(raw)
                    else:
                        # Nothing to read — short sleep to avoid busy-loop
                        time.sleep(0.01)

                    # Flush outgoing queue
                    while not self._send_queue.empty():
                        try:
                            chunk = self._send_queue.get_nowait()
                        except queue.Empty:
                            break
                        ser.write(chunk)
                # OSError covers device unplug ([Errno 5] I/O error etc.);
                # SerialException covers pyserial-reported failures.
                except (serial.SerialException, OSError) as exc:
                    _log.error('Serial I/O error on %s: %s', self._port, exc)
                    self.error_occurred.emit(str(exc))
                    break
        except Exception:
            # Last-resort guard so an unexpected bug never escapes run()
            # (which would let PyQt abort the whole process).
            _log.exception('Unexpected error in serial worker loop for %s',
                           self._port)
            self.error_occurred.emit('internal serial error (see log)')
        finally:
            try:
                ser.close()
            except Exception:
                _log.debug('Error closing %s', self._port, exc_info=True)
            _log.info('Closed %s', self._port)
            self.disconnected.emit()
