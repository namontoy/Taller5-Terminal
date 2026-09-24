"""
Port-list filtering per operating system.

Run from the project root:  python -m unittest discover tests -v
No serial hardware and no display are needed: pyserial's comports() is
replaced with fake port lists, and sys.platform is patched per test.
"""
import unittest
from types import SimpleNamespace
from unittest import mock

from serial_terminal.widgets import toolbar
from serial_terminal.widgets.toolbar import _is_user_port, _scan_serial_ports


def _fake_ports(*devices):
    return [SimpleNamespace(device=d) for d in devices]


class ScanPortsTest(unittest.TestCase):

    def _scan(self, platform, *devices):
        with mock.patch('sys.platform', platform), \
             mock.patch.object(toolbar._list_ports, 'comports',
                               return_value=_fake_ports(*devices)):
            return _scan_serial_ports()

    def test_linux_keeps_usb_adapters_and_hides_legacy_ports(self):
        self.assertEqual(
            self._scan('linux',
                       '/dev/ttyS0', '/dev/ttyS1', '/dev/ttyAP0',
                       '/dev/ttyUSB0', '/dev/ttyACM0', '/dev/ttyAMA0',
                       '/dev/ttyXRUSB0', '/dev/rfcomm0'),
            ['/dev/rfcomm0', '/dev/ttyACM0', '/dev/ttyAMA0',
             '/dev/ttyUSB0', '/dev/ttyXRUSB0'])

    def test_windows_shows_every_com_port_in_numeric_order(self):
        self.assertEqual(self._scan('win32', 'COM10', 'COM3', 'COM1'),
                         ['COM1', 'COM3', 'COM10'])

    def test_macos_shows_callout_devices_but_not_builtin_ones(self):
        self.assertEqual(
            self._scan('darwin',
                       '/dev/cu.Bluetooth-Incoming-Port',
                       '/dev/cu.debug-console',
                       '/dev/cu.wlan-debug',
                       '/dev/cu.usbserial-A50285BI',
                       '/dev/cu.usbmodem1101',
                       '/dev/cu.HC-05'),
            ['/dev/cu.HC-05', '/dev/cu.usbmodem1101',
             '/dev/cu.usbserial-A50285BI'])

    def test_natural_sort_on_linux(self):
        self.assertEqual(self._scan('linux', '/dev/ttyUSB10', '/dev/ttyUSB2'),
                         ['/dev/ttyUSB2', '/dev/ttyUSB10'])

    def test_no_ports(self):
        for platform in ('linux', 'win32', 'darwin'):
            with self.subTest(platform=platform):
                self.assertEqual(self._scan(platform), [])


class IsUserPortTest(unittest.TestCase):

    def test_explicit_platform_argument(self):
        self.assertTrue(_is_user_port('COM4', 'win32'))
        self.assertFalse(_is_user_port('COM4', 'linux'))
        self.assertFalse(_is_user_port('/dev/tty.usbserial-X', 'darwin'))
        self.assertTrue(_is_user_port('/dev/ttyU0', 'freebsd14'))


if __name__ == '__main__':
    unittest.main()
