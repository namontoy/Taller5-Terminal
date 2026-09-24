"""
Byte/text conversions used when sending commands and saving captures.

Pure functions with no Qt dependency, so they can be unit-tested directly
(see tests/test_protocol.py). Widgets call these instead of doing the
conversion inline.
"""
from __future__ import annotations

from collections.abc import Iterable

from serial_terminal import Char
from serial_terminal.logging_setup import get_logger
from serial_terminal.themes import BUILT_IN_TERMS

_log = get_logger('protocol')

_HEX_DIGITS = '0123456789ABCDEF'


def format_hex_input(text: str) -> str:
    """Normalise what the user types in a HEX field: 'aa5501' -> 'AA 55 01'.

    Non-hex characters are dropped and digits are grouped in pairs; an odd
    trailing digit stays on its own ('AAB' -> 'AA B').
    """
    raw = ''.join(ch for ch in text.upper() if ch in _HEX_DIGITS)
    return ' '.join(raw[i:i + 2] for i in range(0, len(raw), 2))


def terminator_bytes(active_terms: Iterable[str]) -> bytes:
    """Bytes appended to every command, in the order the terminators were
    activated. Built-ins are matched by key ('0x0D 0x0A'); custom ones are a
    single character ('@') or one hex byte ('0x03'). Invalid entries are
    skipped.
    """
    result: list[int] = []
    for key in active_terms:
        t = next((t for t in BUILT_IN_TERMS if t['key'] == key), None)
        if t:
            result.extend(t['bytes'])
            continue
        # custom term — guard against malformed user input (e.g. '0xZZ')
        key = key.strip()
        if key.lower().startswith('0x'):
            try:
                v = int(key, 16)
            except ValueError:
                _log.warning('Ignoring invalid hex terminator %r', key)
                continue
            if 0 <= v <= 255:
                result.append(v)
        elif len(key) == 1:
            result.append(ord(key))
    return bytes(result)


def encode_command(text: str, mode: str, terminator: bytes = b'') -> bytes | None:
    """Bytes to put on the wire for a command typed in *mode* ('ASCII'/'HEX').

    ASCII is encoded as latin-1 (unencodable characters become '?'). HEX is a
    space-separated list of byte values; values above FF are skipped. Returns
    None when a HEX token is not a number, so nothing is sent.
    """
    if mode == 'HEX':
        try:
            byte_vals = [int(h, 16) for h in text.split()
                         if h and 0 <= int(h, 16) <= 255]
        except ValueError:
            return None
        return bytes(byte_vals) + terminator
    return text.encode('latin-1', errors='replace') + terminator


def chars_to_text(chars: Iterable[Char]) -> str:
    """Text written by Save: LF ends a line, CR is dropped, and a trailing
    unterminated line is kept."""
    lines: list[str] = []
    cur = ''
    for ch in chars:
        if ch.code == 10:
            lines.append(cur)
            cur = ''
        elif ch.code != 13:
            cur += chr(ch.code)
    if cur:
        lines.append(cur)
    return '\n'.join(lines)
