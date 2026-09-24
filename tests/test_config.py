"""
Settings file handling: defaults, damaged files, upgrades from older
versions, and saved-command slots (6 in old configs, 12 now).
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from serial_terminal import config
from serial_terminal.config import PRESET_COUNT
from serial_terminal.widgets.sidebar import _pad_presets


class ConfigFileTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / 'serial_terminal' / 'config.json'
        patcher = mock.patch.object(config, '_CONFIG_PATH', self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def write(self, text: str):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text, encoding='utf-8')

    def test_missing_file_gives_defaults(self):
        self.assertEqual(config.load(), config.DEFAULTS)

    def test_damaged_file_gives_defaults(self):
        self.write('{"baud": 115200,,,')
        self.assertEqual(config.load(), config.DEFAULTS)

    def test_old_file_gets_new_keys_with_defaults(self):
        # A config written before the ECHO switch existed
        self.write(json.dumps({'baud': 115200, 'theme': 'light'}))
        cfg = config.load()
        self.assertEqual(cfg['baud'], 115200)
        self.assertEqual(cfg['theme'], 'light')
        self.assertIs(cfg['local_echo'], True)

    def test_save_then_load_round_trip(self):
        cfg = dict(config.DEFAULTS, baud=57600, local_echo=False,
                   presets=['LED ON'] + [''] * (PRESET_COUNT - 1))
        config.save(cfg)
        self.assertEqual(config.load(), cfg)

    def test_save_creates_the_folder(self):
        config.save(dict(config.DEFAULTS))
        self.assertTrue(self.path.exists())

    def test_defaults_are_not_modified_by_callers(self):
        cfg = config.load()
        cfg['baud'] = 1
        self.assertNotEqual(config.DEFAULTS['baud'], 1)


class PadPresetsTest(unittest.TestCase):

    def test_old_six_slot_config_grows_to_twelve_keeping_commands(self):
        old = ['R', 'p', '+', '0', '2', '']
        padded = _pad_presets(old)
        self.assertEqual(len(padded), PRESET_COUNT)
        self.assertEqual(padded[:6], old)
        self.assertEqual(set(padded[6:]), {''})

    def test_missing_list(self):
        self.assertEqual(_pad_presets(None), [''] * PRESET_COUNT)

    def test_never_truncates(self):
        many = [f'cmd{i}' for i in range(PRESET_COUNT + 2)]
        self.assertEqual(_pad_presets(many), many)

    def test_twelve_slots(self):
        self.assertEqual(PRESET_COUNT, 12)


if __name__ == '__main__':
    unittest.main()
