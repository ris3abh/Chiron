"""chiron/router.py: thirty asks in English, Hindi and mixed, with a fake Jev."""
import os
import tempfile
import unittest
from collections import namedtuple
from unittest.mock import patch

from chiron import jev, paths, router, skills

A = jev.Answer
CASES = [
    # (ask, mode, source): the order is the point
    ('Open YouTube for me', 'do', None), ('YouTube khol ke batao', 'do', None), ('YouTube chalu karna', 'do', None), ('यूट्यूब खोल के बताओ', 'do', None),
    ('play bhajan', 'do', 'jev'), ('भजन चलाओ', 'do', 'jev'), ('send this to Asha', 'do', 'jev'), ('close Notes', 'do', 'jev'), ('search the weather', 'do', 'jev'), ('just book the tickets', 'do', 'words'),
    ('teach me to print a word document', 'teach', 'card'), ('how do I play a video on YouTube', 'teach', 'card'), ('YouTube पर वीडियो चलाना सिखाओ', 'teach', 'card'),
    ('teach me how to make a new folder on the desktop', 'teach', 'words'), ('naya folder kaise banate hain', 'teach', 'words'), ('नया फ़ोल्डर बनाना सिखाओ', 'teach', 'words'),
    ('how to attach a file in mail', 'teach', 'words'), ('show me how to zoom in', 'teach', 'words'), ('sikhao mujhe email bhejna', 'teach', 'words'), ('kaise karte hain screenshot', 'teach', 'words'),
    ('play a video on youtube', 'teach', 'card'), ('just play a video on youtube', 'do', 'card'), ('play bhajan on youtube', 'teach', 'card'), ('यूट्यूब पर भजन लगाओ', 'teach', 'card'), ('join the call', 'teach', 'card'),
    ('Mujhe settings, Mein, Bluetooth, Chalu Karna Shikhao', 'teach', 'words'), ('what is a PDF', 'question', 'words'), ('पीडीएफ क्या होता है', 'question', 'words'), ('what time is it in London', 'question', 'words'), ('mera wifi kyun nahi chal raha', 'question', 'words'), ('tell me a joke', 'question', 'jev'),
]


def fake(state, questions, purpose=''):
    return {'route_mode': A('choice', 'question', 0.9, False, 'jev'), 'route_risky': A('noul', False, 0.9, False, 'jev')}


class RouterTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory(); self.addCleanup(root.cleanup)
        p = patch.dict(os.environ, {'CHIRON_DIR': root.name}); p.start(); self.addCleanup(p.stop)

    def test_thirty_asks(self):
        self.assertEqual(len(CASES), 31)
        for ask, mode, source in CASES:
            r = router.route(ask, judge=fake)
            self.assertEqual(r['mode'], mode, ask)
            if source: self.assertEqual(r['source'], source, ask)

    def test_a_card_or_an_instruction_never_spends_a_request(self):
        for ask in ('Open YouTube for me', 'teach me to print a word document', 'what is a PDF', 'mera wifi kyun nahi chal raha'):
            router.route(ask, judge=lambda *a, **k: self.fail(f'{ask} reached Jev'))

    def test_the_real_mishearing_routes_to_a_lesson(self):
        # 2026-10-31: heard for "Bluetooth chalu karna dikhao"; "dikhao" alone looked like "show" and went to the main model for 111 s.
        for said in ('Mujhe, Lo, Tu, Chalu, Karna, Dikhao', 'Bluetooth chalu karna dikhao', 'mujhe bluetooth chalu kar ke dikhao', 'ब्लूटूथ चालू करना दिखाओ'):
            r = router.route(said, judge=lambda *a, **k: self.fail(f'{said} needs no request'))
            self.assertEqual(r['mode'], 'teach', said)

    def test_youtube_chalu_karna_is_done_even_through_jev(self):
        self.assertEqual(router.route('YouTube chalu karna', judge=fake)['mode'], 'do', 'fast() opens it first; here it still is not a question')

    def test_an_instruction_asks_jev_but_is_never_a_question(self):
        calls = []
        r = router.route('play bhajan', judge=lambda s, q, purpose='': calls.append(s) or fake(s, q))
        self.assertEqual((len(calls), r['mode']), (1, 'do'))
        self.assertIn('play bhajan', calls[0], 'sent as said, not normalised')

    def test_jev_can_turn_an_instruction_into_a_lesson(self):
        answers = {'route_mode': A('choice', 'teach', 0.9, False, 'jev'), 'route_risky': A('noul', False, 0.9, False, 'jev')}
        self.assertEqual(router.route('show me the bluetooth switch', judge=lambda *a, **k: answers)['mode'], 'teach')

    def test_one_request_with_both_questions(self):
        calls = []
        router.route('tell me a joke', judge=lambda s, q, purpose='': calls.append(set(q)) or fake(s, q))
        self.assertEqual(calls, [{'route_mode', 'route_risky'}])

    def test_haiku_fallback_is_the_same_path(self):
        answers = {'route_mode': A('choice', 'do', 0.9, False, 'haiku-fallback'), 'route_risky': A('noul', True, 0.9, False, 'haiku-fallback')}
        r = router.route('pay the electricity bill', judge=lambda *a, **k: answers)
        self.assertEqual((r['mode'], r['risky'], r['source']), ('do', True, 'haiku-fallback'))

    def test_unsure_or_down_is_an_ordinary_question(self):
        unsure = {'route_mode': A('choice', 'do', 0.4, True, 'jev'), 'route_risky': A('noul', False, 0.6, True, 'jev')}
        self.assertEqual(router.route('hmm that thing', judge=lambda *a, **k: unsure)['mode'], 'question')
        def down(*a, **k): raise jev.JevError('rejected')
        self.assertEqual(router.route('hmm that thing', judge=down)['mode'], 'question')

    def test_an_outage_of_both_engines_never_crashes_the_ask(self):
        from chiron import providers
        def down(*a, **k): raise providers.ProviderError('server')
        self.assertEqual(router.route('hmm that thing', judge=down)['mode'], 'question')

    def test_mastered_skills_and_settings(self):
        card = {**skills.starters()['open-photo'], 'mastery': 5}
        self.assertEqual(router.route('open a photo', {'open-photo': card}, fake)['mode'], 'do')
        self.assertEqual(router.route('teach me to open a photo', {'open-photo': card}, fake)['mode'], 'teach')
        paths.private_json(paths.PREFS, {'teachMode': 'always-do'})
        self.assertEqual(router.route('open a photo', None, fake)['mode'], 'do')
        paths.private_json(paths.PREFS, {'teachMode': 'always-teach'})
        self.assertEqual(router.route('open a photo', None, fake)['mode'], 'teach')


if __name__ == '__main__':
    unittest.main()
