"""keys/ChironKeys: the one program with Keychain permission, kept unchanged across builds so macOS asks once."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from chiron import paths

ROOT = Path(__file__).resolve().parents[1]


class KeysHelperTests(unittest.TestCase):
    def test_python_reads_through_the_helper_never_the_app(self):
        with tempfile.TemporaryDirectory() as root:
            helper = Path(root) / 'ChironKeys'; helper.write_text('')
            with patch.dict(os.environ, {'CHIRON_APP': str(Path(root) / 'Chiron')}), patch.dict(os.environ, {}, clear=False):
                os.environ.pop('CHIRON_SECRET_JEV', None)
                with patch('subprocess.run', return_value=type('R', (), {'returncode': 0, 'stdout': 'value\n'})()) as run:
                    self.assertEqual(paths.secret('jev'), 'value')
            self.assertEqual(run.call_args.args[0], [str(helper), 'get', 'jev'])

    def test_the_app_never_calls_the_keychain_itself(self):
        swift = (ROOT / 'Chiron.swift').read_text() + ''.join(p.read_text() for p in (ROOT / 'app').glob('*.swift'))
        self.assertNotIn('SecItem', swift, 'a key read from the app asks again after every build')

    def test_build_reuses_one_signed_helper(self):
        build = (ROOT / 'build.sh').read_text()
        self.assertIn('shasum -a 256 keys/ChironKeys.swift', build)
        self.assertIn('if [ ! -x "$KEYS_KEPT" ]', build)
        self.assertIn('cp -p "$KEYS_KEPT"', build)
        self.assertEqual(build.count('--force --deep'), 1, 'only the CI package: --deep on the installed app would re-sign the helper and lose its permission')

    @unittest.skipUnless(shutil.which('swiftc'), 'needs swiftc')
    def test_helper_compiles_on_its_own(self):
        with tempfile.TemporaryDirectory() as root:
            built = subprocess.run(['swiftc', str(ROOT / 'keys' / 'ChironKeys.swift'), '-o', str(Path(root) / 'k')], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)


if __name__ == '__main__':
    unittest.main()
