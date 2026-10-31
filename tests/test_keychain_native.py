"""Chiron --secret set/get/delete round trip against the real login Keychain. Host-gated: it writes a Keychain item."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

APP = os.environ.get('CHIRON_APP') or str(Path.home() / 'Applications/Chiron.app/Contents/MacOS/Chiron')


@unittest.skipUnless(sys.platform == 'darwin' and (os.environ.get('CHIRON_VM') or os.environ.get('CHIRON_ALLOW_HOST_UI')),
                     'writes to the login Keychain; runs only in the VM or with CHIRON_ALLOW_HOST_UI=1')
@unittest.skipUnless(os.path.exists(APP), 'needs a built Chiron.app (./build.sh)')
class KeychainNativeTest(unittest.TestCase):
    name = 'sarvam'   # the one account Phase 1 never uses, so a run never clobbers a real key

    def secret(self, *args, data=None):
        return subprocess.run([APP, '--secret', *args], input=data, capture_output=True, text=True, timeout=20)

    def setUp(self):
        before = self.secret('get', self.name)
        self.addCleanup(lambda: self.secret('set', self.name, data=before.stdout.strip()) if before.returncode == 0 else self.secret('delete', self.name))

    def test_round_trip(self):
        self.assertEqual(self.secret('set', self.name, data='test-key-1234\n').returncode, 0)
        got = self.secret('get', self.name)
        self.assertEqual((got.returncode, got.stdout.strip()), (0, 'test-key-1234'))
        self.assertEqual(self.secret('set', self.name, data='test-key-5678').returncode, 0)   # replace, not duplicate
        self.assertEqual(self.secret('get', self.name).stdout.strip(), 'test-key-5678')
        self.assertEqual(self.secret('delete', self.name).returncode, 0)
        self.assertEqual(self.secret('get', self.name).returncode, 1)

    def test_unknown_names_are_refused(self):
        self.assertEqual(self.secret('get', 'login').returncode, 2)
        self.assertEqual(self.secret('get').returncode, 2)


if __name__ == '__main__':
    unittest.main()
