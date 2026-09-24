"""
What actually goes on the wire, and what Save writes.

These lock in the behavior the README documents for the Command box,
End of command, Saved commands (HEX) and the Save button.
"""
import unittest

from serial_terminal import Char
from serial_terminal.protocol import (
    chars_to_text, encode_command, format_hex_input, terminator_bytes,
)

CRLF = '0x0D 0x0A'   # built-in terminator keys, as stored in the config
LF, CR, NUL = '0x0A', '0x0D', '0x00'


class FormatHexInputTest(unittest.TestCase):

    def test_groups_digits_in_pairs_and_uppercases(self):
        self.assertEqual(format_hex_input('aa5501'), 'AA 55 01')

    def test_already_formatted_input_is_unchanged(self):
        self.assertEqual(format_hex_input('AA 55 01'), 'AA 55 01')

    def test_odd_trailing_digit_stays_alone(self):
        self.assertEqual(format_hex_input('AAB'), 'AA B')

    def test_non_hex_characters_are_dropped(self):
        self.assertEqual(format_hex_input('AA, 55; zz 01'), 'AA 55 01')

    def test_empty(self):
        self.assertEqual(format_hex_input(''), '')

    def test_c_style_0x_prefixes_are_accepted(self):
        self.assertEqual(format_hex_input('0xAA'), 'AA')
        self.assertEqual(format_hex_input('0xAA 0x55 0x01'), 'AA 55 01')
        self.assertEqual(format_hex_input('0XAA,0x0d'), 'AA 0D')

    def test_typing_0x_clears_it(self):
        # The field is reformatted on every keystroke: '0' then '0x'
        self.assertEqual(format_hex_input('0'), '0')
        self.assertEqual(format_hex_input('0x'), '')

    def test_zero_bytes_are_not_mistaken_for_prefixes(self):
        self.assertEqual(format_hex_input('00 10 A0'), '00 10 A0')
        self.assertEqual(format_hex_input('A0x5'), 'A0 5')   # mid-token x


class TerminatorBytesTest(unittest.TestCase):

    def test_each_built_in(self):
        self.assertEqual(terminator_bytes([LF]), b'\n')
        self.assertEqual(terminator_bytes([CR]), b'\r')
        self.assertEqual(terminator_bytes([CRLF]), b'\r\n')
        self.assertEqual(terminator_bytes([NUL]), b'\x00')

    def test_none_active(self):
        self.assertEqual(terminator_bytes([]), b'')

    def test_several_active_in_activation_order(self):
        self.assertEqual(terminator_bytes([LF, CR]), b'\n\r')
        self.assertEqual(terminator_bytes([CR, LF]), b'\r\n')

    def test_custom_single_character(self):
        self.assertEqual(terminator_bytes(['@']), b'@')

    def test_custom_hex_byte(self):
        self.assertEqual(terminator_bytes(['0x03']), b'\x03')

    def test_invalid_custom_entries_are_skipped(self):
        with self.assertLogs('serial_terminal.protocol', level='WARNING'):
            self.assertEqual(terminator_bytes(['0xZZ', CR]), b'\r')
        self.assertEqual(terminator_bytes(['0x1FF']), b'')   # above FF
        self.assertEqual(terminator_bytes(['ab']), b'')      # not one char


class EncodeCommandTest(unittest.TestCase):

    def test_ascii_with_crlf(self):
        self.assertEqual(encode_command('hello', 'ASCII', b'\r\n'),
                         b'hello\r\n')

    def test_ascii_without_terminator(self):
        self.assertEqual(encode_command('LED ON', 'ASCII'), b'LED ON')

    def test_ascii_latin1_characters_are_kept(self):
        self.assertEqual(encode_command('año', 'ASCII'), 'año'.encode('latin-1'))

    def test_ascii_unencodable_characters_become_question_marks(self):
        self.assertEqual(encode_command('5€', 'ASCII'), b'5?')

    def test_hex_sends_exactly_those_bytes_plus_terminator(self):
        self.assertEqual(encode_command('AA 55 01', 'HEX', b'\n'),
                         b'\xaa\x55\x01\n')

    def test_hex_values_above_ff_are_skipped(self):
        self.assertEqual(encode_command('AA 1FF 01', 'HEX'), b'\xaa\x01')

    def test_hex_with_invalid_token_sends_nothing(self):
        self.assertIsNone(encode_command('AA ZZ', 'HEX', b'\n'))

    def test_hex_empty_sends_only_terminator(self):
        self.assertEqual(encode_command('', 'HEX', b'\r'), b'\r')


class CharsToTextTest(unittest.TestCase):

    @staticmethod
    def chars(data: bytes, sent: bool = False) -> list[Char]:
        return [Char(code=b, sent=sent) for b in data]

    def test_crlf_lines(self):
        self.assertEqual(chars_to_text(self.chars(b'T:1\r\nT:2\r\n')), 'T:1\nT:2')

    def test_lf_only_lines(self):
        self.assertEqual(chars_to_text(self.chars(b'a\nb\n')), 'a\nb')

    def test_trailing_partial_line_is_kept(self):
        self.assertEqual(chars_to_text(self.chars(b'done\npart')), 'done\npart')

    def test_empty_lines_are_kept(self):
        self.assertEqual(chars_to_text(self.chars(b'a\n\nb\n')), 'a\n\nb')

    def test_sent_and_received_are_both_saved(self):
        data = self.chars(b'PING\r\n', sent=True) + self.chars(b'PONG\r\n')
        self.assertEqual(chars_to_text(data), 'PING\nPONG')

    def test_nothing(self):
        self.assertEqual(chars_to_text([]), '')


if __name__ == '__main__':
    unittest.main()
