"""The version shown in About, written to the log and matched against
release tags by CI (see .github/workflows/smoke.yml)."""
import re
import unittest

import serial_terminal


class VersionTest(unittest.TestCase):

    def test_semantic_version_format(self):
        self.assertRegex(serial_terminal.__version__, r'^\d+\.\d+\.\d+$')

    def test_changelog_has_an_entry_for_this_version(self):
        from pathlib import Path
        changelog = Path(__file__).resolve().parent.parent / 'CHANGELOG.md'
        if not changelog.exists():
            self.skipTest('no CHANGELOG.md yet')
        text = changelog.read_text(encoding='utf-8')
        self.assertTrue(
            re.search(rf'^## \[{re.escape(serial_terminal.__version__)}\]', text,
                      re.M),
            f'CHANGELOG.md has no "## [{serial_terminal.__version__}]" section')


if __name__ == '__main__':
    unittest.main()
