"""
Chart input: the line formats promised in the README "Plotting data from
your microcontroller" section, and the chart's signal/point limits.
"""
import unittest

from qt_helpers import get_app

from serial_terminal import Char
from serial_terminal.widgets import chart_panel
from serial_terminal.widgets.chart_panel import _parse_line


class ParseLineTest(unittest.TestCase):
    """One test per row of the README formats table, plus edge cases."""

    def test_readme_named_colon_pairs(self):
        self.assertEqual(_parse_line('T:23.5 V:3.28 H:61.4'),
                         (['T', 'V', 'H'], [23.5, 3.28, 61.4]))

    def test_readme_named_equals_pairs(self):
        self.assertEqual(_parse_line('rpm=1500 duty=42'),
                         (['rpm', 'duty'], [1500.0, 42.0]))

    def test_readme_csv_columns(self):
        self.assertEqual(_parse_line('23.5,3.28,61.4'),
                         (['0', '1', '2'], [23.5, 3.28, 61.4]))

    def test_readme_semicolon_and_space_columns(self):
        self.assertEqual(_parse_line('23.5;3.28'), (['0', '1'], [23.5, 3.28]))
        self.assertEqual(_parse_line('23.5 3.28'), (['0', '1'], [23.5, 3.28]))

    def test_readme_non_numeric_named_value_is_skipped(self):
        self.assertEqual(_parse_line('T:23.5 status=OK count:42'),
                         (['T', 'count'], [23.5, 42.0]))

    def test_csv_with_spaces_after_commas(self):
        self.assertEqual(_parse_line('1.23, 4.56, 7.89'),
                         (['0', '1', '2'], [1.23, 4.56, 7.89]))

    def test_number_formats(self):
        self.assertEqual(_parse_line('a:-0.7 b:1.5e-3 c:42'),
                         (['a', 'b', 'c'], [-0.7, 0.0015, 42.0]))

    def test_space_after_colon(self):
        self.assertEqual(_parse_line('T: 23.5'), (['T'], [23.5]))

    def test_names_are_case_sensitive(self):
        labels, _ = _parse_line('Temp:1 temp:2')
        self.assertEqual(labels, ['Temp', 'temp'])

    def test_lines_without_numbers_are_ignored(self):
        self.assertIsNone(_parse_line('System ready'))
        self.assertIsNone(_parse_line(''))
        self.assertIsNone(_parse_line('   '))


class ChartPanelTest(unittest.TestCase):

    def setUp(self):
        get_app()
        self.panel = chart_panel.ChartPanel()

    def push(self, data: bytes, sent: bool = False):
        self.panel.push_chars([Char(code=b, sent=sent) for b in data])

    def test_complete_lines_become_series(self):
        self.push(b'T:1 V:2\r\nT:3 V:4\r\n')
        self.assertEqual({k: list(v) for k, v in self.panel._series.items()},
                         {'T': [1.0, 3.0], 'V': [2.0, 4.0]})

    def test_incomplete_line_waits_for_lf(self):
        self.push(b'T:1')
        self.assertEqual(self.panel._series, {})
        self.push(b'\n')
        self.assertEqual(list(self.panel._series['T']), [1.0])

    def test_sent_bytes_are_not_plotted(self):
        self.push(b'T:99\r\n', sent=True)
        self.assertEqual(self.panel._series, {})

    def test_at_most_eight_signals(self):
        names = ' '.join(f's{i}:{i}' for i in range(10))
        self.push(names.encode() + b'\n')
        self.assertEqual(list(self.panel._series),
                         [f's{i}' for i in range(chart_panel._MAX_SERIES)])
        self.assertEqual(chart_panel._MAX_SERIES, 8)

    def test_rolling_window_keeps_last_200_points(self):
        for i in range(250):
            self.push(f'T:{i}\n'.encode())
        data = list(self.panel._series['T'])
        self.assertEqual(len(data), 200)
        self.assertEqual((data[0], data[-1]), (50.0, 249.0))

    def test_clear_buffer(self):
        self.push(b'T:1\nT:')
        self.panel.clear_buffer()
        self.push(b'2\n')        # the partial "T:" before clear is gone,
        # so "2" is read as a bare number (column 0), not as T:2
        self.assertEqual({k: list(v) for k, v in self.panel._series.items()},
                         {'0': [2.0]})


if __name__ == '__main__':
    unittest.main()
