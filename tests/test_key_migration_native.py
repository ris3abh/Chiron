"""Older installs kept the custom server's key as apiKey in settings.json. On first launch Chiron moves it to the Keychain and
the file must no longer hold it. Runs the real Prefs and the real Keychain.migrate() against an in-memory Keychain stub,
so the test never touches the user's login Keychain (test_keychain_native covers the real one)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def migrate_source():
    source = (ROOT / 'app' / 'Keychain.swift').read_text()
    start = source.index('    static func migrate() {')
    return source[start:source.index('\n    }\n', start) + 7]


@unittest.skipUnless(sys.platform == 'darwin', 'macOS Swift regression')
class KeyMigrationNativeTests(unittest.TestCase):
    def run_migration(self, saved, keychain_works=True, runs=1):
        chiron = (ROOT / 'Chiron.swift').read_text()
        prefs = chiron[chiron.index('enum Prefs'):chiron.index('func applySharing(')]
        swift = f"""import Cocoa
let controlKey = 1, optionKey = 2
{prefs}
enum Keychain {{
    static var store: [String: String] = [:]
    @discardableResult static func set(_ name: String, _ value: String) -> Bool {{
        guard {'true' if keychain_works else 'false'} else {{ return false }}
        store[name] = value; return true
    }}
{migrate_source()}
}}
for _ in 0..<{runs} {{ Keychain.migrate() }}
print(Keychain.store["custom"] ?? "<none>")
"""
        with tempfile.TemporaryDirectory() as root:
            settings = Path(root) / 'settings.json'
            settings.write_text(json.dumps(saved)); os.chmod(settings, 0o600)
            path, binary = Path(root) / 'migrate.swift', Path(root) / 'migrate'
            path.write_text(swift)
            compiled = subprocess.run(['swiftc', str(path), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, env={**os.environ, 'CHIRON_DIR': root})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout.strip(), settings.read_text(), os.stat(settings).st_mode & 0o777

    def test_saved_key_moves_to_keychain_and_leaves_the_file(self):
        stored, text, mode = self.run_migration({'apiKey': 'sk-local-1234', 'apiBase': 'http://localhost:11434', 'lang': 'hi'})
        self.assertEqual(stored, 'sk-local-1234')
        self.assertNotIn('apiKey', json.loads(text))
        self.assertNotIn('sk-local-1234', text)   # not under any other name either
        self.assertEqual(json.loads(text)['apiBase'], 'http://localhost:11434')
        self.assertEqual(json.loads(text)['lang'], 'hi')
        self.assertEqual(mode, 0o600)

    def test_running_it_again_changes_nothing(self):
        stored, text, _ = self.run_migration({'apiKey': 'sk-local-1234'}, runs=2)
        self.assertEqual(stored, 'sk-local-1234')
        self.assertNotIn('apiKey', json.loads(text))

    def test_an_empty_key_is_just_dropped(self):
        stored, text, _ = self.run_migration({'apiKey': '  ', 'apiBase': 'http://localhost:1234'})
        self.assertEqual(stored, '<none>')
        self.assertNotIn('apiKey', json.loads(text))

    def test_a_keychain_failure_keeps_the_key_rather_than_losing_it(self):
        stored, text, _ = self.run_migration({'apiKey': 'sk-local-1234'}, keychain_works=False)
        self.assertEqual(stored, '<none>')
        self.assertEqual(json.loads(text)['apiKey'], 'sk-local-1234')   # retried next launch

    def test_no_key_no_write(self):
        stored, text, _ = self.run_migration({'lang': 'en'})
        self.assertEqual((stored, json.loads(text)), ('<none>', {'lang': 'en'}))


if __name__ == '__main__':
    unittest.main()
