"""
Persistent configuration stored in ~/.config/serial_terminal/config.json.
"""
import json
from pathlib import Path

# Number of rows in each Saved commands tab (ASCII and HEX).
PRESET_COUNT = 12

_CONFIG_PATH = Path.home() / '.config' / 'serial_terminal' / 'config.json'

DEFAULTS: dict = {
    'port':         '/dev/ttyUSB0',
    'baud':         9600,
    'data_bits':    8,
    'parity':       'none',
    'stop_bits':    1,
    'flow':         'none',
    'theme':        'matrix',
    'font_size':    13,
    'buf_size':     10000,
    'save_filename':'capture.txt',
    'active_terms': ['0x0D 0x0A'],
    'presets':      [''] * PRESET_COUNT,
    'local_echo':   True,
}


def load() -> dict:
    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        # Merge with defaults so new keys are always present
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def save(cfg: dict) -> None:
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_PATH, 'w', encoding='utf-8') as fh:
            json.dump(cfg, fh, indent=2)
    except OSError:
        pass  # Non-fatal — just skip saving
