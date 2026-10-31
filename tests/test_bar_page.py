"""ui/bar.html: every state has its words in both languages, and the page keeps the app's rules. WebKit half: each state renders."""
import json
from pathlib import Path
import re
import unittest

from tests import run_swift

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / 'ui' / 'bar.html').read_text(encoding='utf-8')
MOCK = (ROOT / 'tests' / 'bar.html').read_text(encoding='utf-8')
EN, HI = (json.loads((ROOT / 'ui' / 'strings' / f'{l}.json').read_text(encoding='utf-8')) for l in ('en', 'hi'))
STATES = ['idle', 'listening', 'thinking', 'speaking', 'done', 'message', 'teaching', 'practice', 'guardian']


class BarPageTests(unittest.TestCase):
    def test_states_match_the_mock_and_the_plan(self):
        for source in (PAGE, MOCK):
            self.assertEqual(re.search(r"const STATES = \[([^\]]+)\]", source)[1].replace("'", '').split(', '), STATES)

    def test_every_label_exists_in_both_languages(self):
        keys = re.findall(r"'(bar\.\w+)'", PAGE)
        self.assertEqual(len(keys), 7, 'all but idle and message, which carry their own words')
        for key in keys:
            self.assertTrue(EN.get(key) and HI.get(key), key)
            self.assertRegex(HI[key], '[ऀ-ॿ]', key)

    def test_no_network_and_motion_rules(self):
        self.assertIn("default-src 'self'", PAGE)
        self.assertIsNone(re.search(r'https?://', PAGE))
        for rule in ('prefers-reduced-motion', 'prefers-reduced-transparency', 'min-height: 44px', '17px'):
            self.assertIn(rule, PAGE)

    def test_card_covers_what_the_old_window_did(self):
        for kind in ('answer', 'allow', 'pick', 'rewrite', 'draft', 'failed'):
            self.assertRegex(PAGE, rf'\b{kind}: \(', kind)
        self.assertIn("act({ allow: false })", PAGE, 'Allow always comes with a way to refuse')
        self.assertIn("act({ allow: true })", PAGE)
        for key in re.findall(r"T\('(card\.\w+)'\)", PAGE):
            self.assertTrue(EN.get(key) and HI.get(key), key)

    def test_the_old_window_is_never_shown(self):
        swift = (ROOT / 'Chiron.swift').read_text()
        show = swift[swift.index('    func show() {'):swift.index('    func hide(after')]
        self.assertNotIn('orderFront', show)
        self.assertNotIn('panel.makeKey', swift[swift.index('    func practice('):swift.index('    func practice(') + 300])
        bar = (ROOT / 'app' / 'VoiceBar.swift').read_text()
        for card in ('case "pick"', 'case "ask"', 'case "rewrite"', 'case "draft"', 'case "workerFailed"'):
            self.assertIn(card, bar, 'every card the old window drew still reaches the person')

    def test_it_is_installed(self):
        self.assertIn('cp ui/*.html', (ROOT / 'build.sh').read_text())


class VoiceNativeLogicTests(unittest.TestCase):
    """The pure parts of app/SpeechLocale.swift and app/VoiceBar.swift."""
    def source(self):
        locale = (ROOT / 'app' / 'SpeechLocale.swift').read_text()
        choose = locale[locale.index('    static func choose('):locale.index('    // At launch and when the language')]
        bar = (ROOT / 'app' / 'VoiceBar.swift').read_text()
        request = bar[bar.index('func dictationRequest('):]
        return 'import Foundation\nenum L {\n' + choose + '\n}\n' + request

    def test_engine_choice_and_type_prefix(self):
        out = run_swift(self, self.source() + r'''
let en = ["en-IN", "en-US"], hi = ["hi-IN"]
// This Mac on 2026-10-30: Hindi supported by both engines, installed by neither; en-IN installed for speech only.
let s: Set<String> = ["en-IN", "en-US", "hi-IN"], si: Set<String> = ["en-IN", "en-US"], d: Set<String> = ["en-US", "hi-IN"], di: Set<String> = ["en-US"]
print(L.choose(en, speech: s, speechInstalled: si, dictation: d, dictationInstalled: di)!)
print(L.choose(hi, speech: s, speechInstalled: si, dictation: d, dictationInstalled: di)!)
print(L.choose(hi, speech: [], speechInstalled: [], dictation: hi.reduce(into: Set<String>()) { $0.insert($1) }, dictationInstalled: ["hi-IN"])!)
print(L.choose(hi, speech: si, speechInstalled: si, dictation: di, dictationInstalled: di) == nil)
for said in ["type hello there", "Type, hello", "likho namaste", "लिखो नमस्ते", "टाइप करो नमस्ते", "typewriter repair near me", "type", "open type settings"] { print(dictationRequest(said) ?? "-") }
''')
        self.assertEqual(out.strip().splitlines(), [
            '(tag: "en-IN", engine: "speech", state: "ready")', '(tag: "hi-IN", engine: "speech", state: "downloading")',
            '(tag: "hi-IN", engine: "dictation", state: "ready")', 'true',
            'hello there', 'hello', 'namaste', 'नमस्ते', 'नमस्ते', '-', '-', '-'])


if __name__ == '__main__':
    unittest.main()
