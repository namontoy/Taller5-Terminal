"""
The serial thread, end to end, without hardware.

pyserial's 'loop://' port returns every byte written to it, so these tests
send real bytes through the real SerialWorker thread on any OS.
"""
import unittest
from unittest import mock

import serial

from qt_helpers import get_app, wait_until

from serial_terminal.serial_worker import SerialWorker


def make_worker(port: str = 'loop://', **overrides) -> SerialWorker:
    settings = dict(port=port, baud=115200, data_bits=8, parity='none',
                    stop_bits=1, flow='none')
    settings.update(overrides)
    return SerialWorker(**settings)


class WorkerTestCase(unittest.TestCase):
    """Starts a worker and records everything it emits."""

    def setUp(self):
        get_app()
        self.received = bytearray()
        self.errors: list[str] = []
        self.events: list[str] = []

    def start(self, worker: SerialWorker) -> SerialWorker:
        worker.data_received.connect(self.received.extend)
        worker.error_occurred.connect(self.errors.append)
        worker.connected.connect(lambda: self.events.append('connected'))
        worker.disconnected.connect(lambda: self.events.append('disconnected'))
        # Never leave a running thread behind, even if the test fails
        self.addCleanup(lambda: (worker.stop(), worker.wait(3000)))
        worker.start()
        return worker


class LoopbackTest(WorkerTestCase):

    def test_bytes_sent_come_back(self):
        w = self.start(make_worker())
        self.assertTrue(wait_until(lambda: 'connected' in self.events),
                        'worker never reported connected')
        w.send(b'PING\r\n')
        self.assertTrue(wait_until(lambda: bytes(self.received) == b'PING\r\n'),
                        f'received {bytes(self.received)!r}')
        self.assertEqual(self.errors, [])

    def test_all_byte_values_survive(self):
        w = self.start(make_worker())
        self.assertTrue(wait_until(lambda: 'connected' in self.events))
        payload = bytes(range(256))
        w.send(payload)
        self.assertTrue(wait_until(lambda: len(self.received) >= 256))
        self.assertEqual(bytes(self.received), payload)

    def test_stop_ends_thread_and_reports_disconnected(self):
        w = self.start(make_worker())
        self.assertTrue(wait_until(lambda: 'connected' in self.events))
        w.stop()
        self.assertTrue(w.isFinished())
        self.assertTrue(wait_until(lambda: 'disconnected' in self.events))

    def test_every_toolbar_setting_opens(self):
        # Each value offered by the toolbar is accepted by pyserial
        for data_bits in (5, 6, 7, 8):
            for parity in ('none', 'even', 'odd', 'mark', 'space'):
                for stop_bits in (1, 1.5, 2):
                    for flow in ('none', 'RTS/CTS', 'XON/XOFF'):
                        w = make_worker(data_bits=data_bits, parity=parity,
                                        stop_bits=stop_bits, flow=flow)
                        with self.subTest(data=data_bits, parity=parity,
                                          stop=stop_bits, flow=flow):
                            opened, errors = [], []
                            w.connected.connect(lambda: opened.append(1))
                            w.error_occurred.connect(errors.append)
                            w.start()
                            wait_until(lambda: opened or errors, 2.0)
                            w.stop()
                            self.assertEqual(errors, [])
                            self.assertTrue(opened)


class FailureTest(WorkerTestCase):

    def test_missing_port_reports_error_and_never_connects(self):
        w = self.start(make_worker(port='no-such-serial-port-xyz'))
        self.assertTrue(wait_until(lambda: self.errors, 5.0),
                        'no error reported for a missing port')
        w.wait(3000)
        self.assertNotIn('connected', self.events)

    def test_unplugged_device_reports_error_and_disconnects(self):
        class UnpluggedPort:
            """Opens fine, then fails like a USB adapter being pulled out."""
            closed = False

            @property
            def in_waiting(self):
                raise OSError(5, 'Input/output error')

            def close(self):
                UnpluggedPort.closed = True

        with mock.patch.object(serial, 'serial_for_url',
                               return_value=UnpluggedPort()):
            w = self.start(make_worker(port='/dev/ttyUSB0'))
            self.assertTrue(wait_until(lambda: 'disconnected' in self.events),
                            'worker did not report the disconnect')
        self.assertEqual(self.events, ['connected', 'disconnected'])
        self.assertEqual(len(self.errors), 1)
        self.assertIn('Input/output error', self.errors[0])
        self.assertTrue(UnpluggedPort.closed)
        self.assertTrue(w.wait(3000))


class SettingsMappingTest(unittest.TestCase):

    def test_parity(self):
        expected = {'none': serial.PARITY_NONE, 'even': serial.PARITY_EVEN,
                    'odd': serial.PARITY_ODD, 'mark': serial.PARITY_MARK,
                    'space': serial.PARITY_SPACE}
        for name, value in expected.items():
            self.assertEqual(SerialWorker._map_parity(name), value)
        self.assertEqual(SerialWorker._map_parity('EVEN'), serial.PARITY_EVEN)
        self.assertEqual(SerialWorker._map_parity('bogus'), serial.PARITY_NONE)

    def test_stop_bits(self):
        self.assertEqual(SerialWorker._map_stopbits(1), serial.STOPBITS_ONE)
        self.assertEqual(SerialWorker._map_stopbits(1.5),
                         serial.STOPBITS_ONE_POINT_FIVE)
        self.assertEqual(SerialWorker._map_stopbits(2), serial.STOPBITS_TWO)
        self.assertEqual(SerialWorker._map_stopbits(3), serial.STOPBITS_ONE)


if __name__ == '__main__':
    unittest.main()
