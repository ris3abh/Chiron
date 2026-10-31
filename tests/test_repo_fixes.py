"""Source-only regressions for release repository wiring."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.evals import fake_mac
from tests.evals.scenarios import by_id, initial_state

ROOT = Path(__file__).resolve().parents[1]


class RepoFixTests(unittest.TestCase):
    def test_long_dry_eval_is_opt_in(self):
        source = (ROOT / 'tests/evals/test_dry.py').read_text()
        self.assertIn("CHIRON_RUN_DRY_EVALS') == '1'", source)

    def test_chrome_native_test_keeps_host_and_vm_guards(self):
        source = (ROOT / 'tests/test_chrome_background_native.py').read_text()
        self.assertIn("os.environ.get('CHIRON_VM') == '1' and sys.platform == 'darwin' and CHROME.exists()", source)


    def test_release_metadata_has_one_version_source(self):
        version = (ROOT / 'VERSION').read_text().strip()
        self.assertEqual(version, '1.5.3')
        major, minor, patch_version = map(int, version.split('.'))
        self.assertEqual(major * 1_000_000 + minor * 1_000 + patch_version, 1_005_003)
        build = (ROOT / 'build.sh').read_text()
        self.assertIn('VERSION=$(tr -d', build)
        self.assertIn('<string>$BUILD</string>', build)
        self.assertIn('<string>$VERSION</string>', build)
        self.assertIn('command -v python3', build)
        self.assertIn('Could not add Chiron to Login Items; opening it directly instead.', build)
        self.assertIn('open "$APP"', build)


    def test_onboarding_fixture_waits_for_state(self):
        source = (ROOT / 'tests/onboarding.html').read_text()
        self.assertIn('transition:none!important', source)
        self.assertEqual(source.count('await wait('), 1)  # only the polling helper yields


if __name__ == '__main__':
    unittest.main()
