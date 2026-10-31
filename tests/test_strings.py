"""ui/strings/en.json and hi.json: one key set, no gaps, matching placeholders, no English left in Hindi."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
STRINGS = ROOT / 'ui' / 'strings'
PAGE = ROOT / 'ui' / 'home.html'
# Words that stay in Latin script in Hindi: brand names, product names and technical tokens a Hindi speaker sees as-is.
ALLOWED_LATIN = {
    'Chiron', 'Claude', 'Code', 'Anthropic', 'OpenAI', 'Jev', 'TypeSafe', 'API', 'AI', 'fn', 'URL', 'Keychain', 'macOS', 'Mac',
    'YouTube', 'WhatsApp', 'Ollama', 'LM', 'Studio', 'OK',
    # On-screen names are copied exactly as the Mac shows them (System Settings labels, app names).
    'Accessibility', 'Automation', 'Notes', 'Safari', 'Microphone', 'Screen', 'Recording', 'Speech', 'Recognition', 'System', 'Settings',
}
PLACEHOLDER = re.compile(r'\{(\w+)\}')


def load(lang):
    return json.loads((STRINGS / f'{lang}.json').read_text(encoding='utf-8'))


def latin_words(text):
    """Latin-alphabet words left after removing placeholders and anything that looks like an address."""
    text = PLACEHOLDER.sub(' ', text)
    text = re.sub(r'\S+\.(?:ai|com|org|net|local)\S*|\S*localhost\S*|https?://\S+', ' ', text)
    return re.findall(r'[A-Za-z][A-Za-z\'’-]*', text)


class StringsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.en, cls.hi = load('en'), load('hi')

    def test_files_are_flat_string_maps(self):
        for lang, table in (('en', self.en), ('hi', self.hi)):
            for key, value in table.items():
                self.assertIsInstance(value, str, f'{lang}:{key} must be a string')
                self.assertRegex(key, r'^[a-z][a-zA-Z0-9]*(\.[a-zA-Z0-9_]+)+$', f'{lang}:{key} is not a flat dotted key')

    def test_same_keys_in_both_languages(self):
        self.assertEqual(sorted(set(self.en) - set(self.hi)), [], 'missing in hi.json')
        self.assertEqual(sorted(set(self.hi) - set(self.en)), [], 'missing in en.json')

    def test_no_empty_values(self):
        for lang, table in (('en', self.en), ('hi', self.hi)):
            empty = [k for k, v in table.items() if not v.strip()]
            self.assertEqual(empty, [], f'empty values in {lang}.json')

    def test_placeholders_match(self):
        for key, value in self.en.items():
            self.assertEqual(sorted(PLACEHOLDER.findall(value)), sorted(PLACEHOLDER.findall(self.hi.get(key, ''))), f'placeholders differ for {key}')

    def test_no_english_left_in_hindi(self):
        leftovers = {}
        for key, value in self.hi.items():
            words = [w for w in latin_words(value) if w not in ALLOWED_LATIN]
            if words:
                leftovers[key] = words
        self.assertEqual(leftovers, {}, 'Latin words in hi.json outside the brand allowlist')

    def test_hindi_is_actually_hindi(self):
        # Pure brand strings (app.name, Jev titles) may be all Latin; everything else needs Devanagari.
        brand_only = [k for k, v in self.hi.items() if not re.search(r'[ऀ-ॿ]', v)]
        for key in brand_only:
            self.assertTrue(all(w in ALLOWED_LATIN for w in latin_words(self.hi[key])), f'{key} has no Hindi')
        self.assertLess(len(brand_only), 11, f'too many untranslated lines: {brand_only}')

    def test_nukta_spellings_stay_consistent(self):
        # ख़र्च, like ज़्यादा and हफ़्ते: the nukta form everywhere, so Home and Settings never spell one word two ways.
        for key, value in self.hi.items():
            self.assertNotRegex(value, 'ख(?!\u093c)र्च', f'{key}: write ख़र्च with the nukta')

    def test_review_file_points_at_real_keys(self):
        review = json.loads((STRINGS / 'hi.review.json').read_text(encoding='utf-8'))
        for key, entry in review.items():
            self.assertIn(key, self.hi)
            self.assertIs(entry.get('_review'), True)
            self.assertTrue(entry.get('note'))

    def test_every_key_the_page_uses_exists(self):
        page = PAGE.read_text(encoding='utf-8')
        used = set(re.findall(r'data-i18n(?:-placeholder|-aria|-title)?="([a-zA-Z0-9_.]+)"', page))
        used |= set(re.findall(r"\bt\('([a-zA-Z0-9_.]+)'", page))
        # Keys built from a prefix: t('home.recent.kind.' + kind), t('footer.' + s), t('settings.perms.' + s).
        for prefix, names in {'home.recent.kind.': ['lesson', 'do', 'practice', 'guardian', 'paper', 'ask'],
                              'footer.': ['ok', 'warn', 'off', 'brain', 'jev', 'speech'],
                              'settings.perms.': ['granted', 'denied', 'unknown']}.items():
            used |= {prefix + n for n in names}
        used = {k for k in used if not k.endswith('.')}
        self.assertGreater(len(used), 50)
        self.assertEqual(sorted(used - set(self.en)), [], 'keys used in ui/home.html but missing from en.json')

    def test_native_labels_present(self):
        for key in ('menu.openHome', 'menu.settings', 'menu.quit'):
            self.assertIn(key, self.en)
        self.assertEqual(self.en['menu.openHome'], 'Open Home')
        self.assertEqual(self.en['menu.settings'], 'Settings…')

    def test_phase_one_copy(self):
        self.assertEqual(self.en['home.today.empty.title'] + ' ' + self.en['home.today.empty.body'], 'Nothing due today. Hold fn and ask me anything.')
        self.assertEqual(self.en['settings.key.rejected'], 'That key was rejected. Check you copied all of it.')
        self.assertIn('open-ended Mac tasks need Claude', self.en['settings.conn.openai.note'])


if __name__ == '__main__':
    unittest.main()
