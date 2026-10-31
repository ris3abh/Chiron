"""Devanagari, romanised Hindi and English requests reach one form (chiron/normalize.py)."""
import unittest

from chiron import normalize

PAIRS = [   # same ask, however it was said
    ('open calculator', 'कैलकुलेटर खोलो'), ('open calculator', 'calculator kholo'), ('open calculator', 'कैलकुलेटर ओपन करो'), ('open calculator', 'calculator ko open karo'),
    ('open notes', 'नोट्स खोलो'), ('open notes', 'notes khol do'), ('open safari', 'सफ़ारी खोलिए'), ('open safari', 'safari kholiye'),
    ('open whatsapp', 'व्हाट्सएप खोलो'), ('open whatsapp', 'whatsapp kholo'), ('open whatsapp', 'कृपया व्हाट्सऐप खोल दीजिए'), ('open mail', 'मेल खोलो'),
    ('open calendar', 'कैलेंडर खोलो'), ('open chrome', 'क्रोम खोलो'), ('open chrome', 'zara chrome kholo'), ('open settings', 'सेटिंग्स खोलो'),
    ('open photos', 'फोटो खोलो'), ('open finder', 'फाइंडर खोलो'), ('open facetime', 'फेसटाइम खोलो'), ('open zoom', 'ज़ूम खोलो'),
    ('close notes', 'नोट्स बंद करो'), ('close notes', 'notes band karo'), ('close safari', 'सफ़ारी बंद कर दो'), ('close safari', 'safari band kar do'),
    ('close chrome', 'क्रोम बंद कीजिए'), ('close zoom', 'zoom close karo'),
    ('play news on youtube', 'youtube pe news lagao'), ('play news on youtube', 'यूट्यूब पे न्यूज़ लगाओ'), ('play news on youtube', 'youtube par news chalao'), ('play news on youtube', 'यूट्यूब पर समाचार चलाओ'),
    ('play bhajan on youtube', 'यूट्यूब पर भजन लगाओ'), ('play bhajan', 'भजन बजाओ'), ('play songs', 'गाने चला दो'), ('play songs', 'songs bajao'),
    ('search weather on google', 'गूगल पर मौसम खोजो'), ('search weather on google', 'google pe weather dhundo'), ('search weather', 'मौसम ढूंढो'), ('show photos', 'फोटो दिखाओ'),
    ('show photos', 'photo dikhao'), ('search weather on google', 'Google par Mausam khojo'), ('open safari', 'safari Kholo'), ('close notes', 'notes band karo'),
    ('play bhajan on youtube', 'YouTube par bhajan lagao'),   # heard this way from Apple's hi-IN engine, 2026-10-30
    ('say that again', 'फिर से बोलो'), ('say that again', 'dobara bolo'), ('say that again', 'phir se bolo'), ('say that again', 'repeat that'),
]


class NormalizeTests(unittest.TestCase):
    def test_forty_pairs_reach_one_key(self):
        self.assertGreaterEqual(len(PAIRS), 40)
        for want, said in PAIRS:
            self.assertEqual(normalize.key(said), want, said)

    def test_english_commands_are_their_own_key(self):
        for text in ('open calculator', 'close notes', 'Play news on YouTube', 'open Calculator.'):
            self.assertEqual(normalize.key(text), normalize.clean(text))

    def test_plain_english_passes_through_untouched(self):
        for text in ('What is a PDF?', 'open Calculator', 'send the file to Asha', 'please close the window on my main screen', 'do it again'):
            self.assertEqual(normalize.command(text), text)

    def test_hindi_commands_become_english_for_fast(self):
        self.assertEqual(normalize.command('कैलकुलेटर खोलो'), 'open calculator')
        self.assertEqual(normalize.command('safari band karo'), 'close safari')
        self.assertEqual(normalize.command('YouTube pe news lagao'), 'play news on youtube')

    def test_a_hindi_question_is_left_for_the_model(self):
        said = 'पीडीएफ क्या होता है'
        self.assertEqual(normalize.command(said), normalize.key(said), 'romanised, not mangled into a command')
        self.assertNotIn('open', normalize.command(said))

    def test_household_dictionary_matches_spellings(self):
        self.assertEqual(normalize.key('आशा को भेजो', ['Asha']), 'send asha')
        self.assertEqual(normalize.skeleton('आशा'), normalize.skeleton('Asha'))
        self.assertEqual(normalize.skeleton('कुलकर्णी'), normalize.skeleton('Kulkarni'))

    def test_roman_keeps_real_sounds(self):
        self.assertEqual(normalize.roman('नमस्ते'), 'namaste')
        self.assertEqual(normalize.roman('खर्च'), 'kharch')
        self.assertEqual(normalize.roman('ख़र्च'), 'kharch')

    def test_digits_and_noise(self):
        self.assertEqual(normalize.clean('  Open   NOTES!! ३ '), 'open notes 3')
        self.assertEqual(normalize.command(''), '')
        self.assertEqual(normalize.key('   '), '')


if __name__ == '__main__':
    unittest.main()
