"""chiron/skills.py: starter cards, matching, mastery, attempts."""
import os
import tempfile
import unittest
from unittest.mock import patch

from chiron import paths, skills


class SkillsTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory(); self.addCleanup(root.cleanup)
        p = patch.dict(os.environ, {'CHIRON_DIR': root.name}); p.start(); self.addCleanup(p.stop)

    def test_five_starters_ship_valid_and_bilingual(self):
        cards = skills.starters()
        self.assertEqual(sorted(cards), ['open-photo', 'video-call-link', 'whatsapp-photo', 'word-open-save-print', 'youtube-play'])
        for card in cards.values():
            self.assertEqual(skills.validate(card), '', card['id'])

    def test_on_screen_names_stay_in_latin_script_in_hindi(self):
        for card in skills.starters().values():
            for step in card['steps']:
                label = step['target']['label']
                if label in ('Photos', 'Library', 'File', 'Print', 'Send', 'Allow', 'Google Chrome', 'Microsoft Word', 'Search'):
                    self.assertRegex(label, r'^[A-Za-z ]+$')
        self.assertIn('Google Chrome', skills.starters()['youtube-play']['steps'][0]['say']['hi'])
        self.assertIn('Allow', skills.starters()['video-call-link']['steps'][1]['say']['hi'])

    def test_validation_refuses_a_half_card(self):
        card = skills.starters()['open-photo']
        for broken in ({**card, 'title': {'en': 'x'}}, {**card, 'steps': []}, {**card, 'steps': card['steps'] * 4},
                       {**card, 'steps': [{**card['steps'][0], 'say': {'en': 'x', 'hi': 'latin only'}}]},
                       {**card, 'steps': [{**card['steps'][0], 'expect': ''}]}, {**card, 'steps': [{**card['steps'][0], 'concept': 'magic'}]}):
            self.assertNotEqual(skills.validate(broken), '')

    def test_find_matches_any_script_and_fills_slots(self):
        for said, q in (('play bhajan on youtube', 'bhajan'), ('यूट्यूब पर भजन लगाओ', 'bhajan'), ('YouTube pe news lagao', 'news')):
            card, slots = skills.find(said)
            self.assertEqual((card['id'], slots), ('youtube-play', {'q': q}), said)
        self.assertEqual(skills.find('teach me to print a word document')[0]['id'], 'word-open-save-print')
        self.assertIsNone(skills.find('what is the capital of France')[0])

    def test_fill_keeps_a_command_shell_safe(self):
        self.assertEqual(skills.fill("open 'x?q={q}'", {'q': "a'; rm -rf ~"}), "open 'x?q=a+rm+-rf'")

    def test_mastery_rules(self):
        self.assertEqual(skills.mastery_after(2, 5, 0, False), 2, 'unfinished changes nothing')
        self.assertEqual(skills.mastery_after(1, 0, 0, True), 1, 'Chiron did it: no credit')
        self.assertEqual(skills.mastery_after(0, 2, 4, True), 1, 'many hints')
        self.assertEqual(skills.mastery_after(0, 3, 2, True), 2, 'one or two hints')
        self.assertEqual(skills.mastery_after(0, 5, 0, True), 3, 'alone once')
        self.assertEqual(skills.mastery_after(3, 5, 0, True), 4)
        self.assertEqual(skills.mastery_after(4, 5, 0, True), 5)
        self.assertEqual(skills.mastery_after(5, 5, 0, True), 5)

    def test_a_finished_lesson_saves_a_card_and_an_attempt(self):
        card = skills.starters()['open-photo']
        row = skills.record(card, [{'id': 's1', 'result': 'correct', 'hints': 1}], usd=0.001, score=3)
        self.assertEqual((row['mastery_before'], row['mastery_after']), (0, 2))
        self.assertEqual(paths.read_jsonl(skills.ATTEMPTS)[0]['skill'], 'open-photo')
        self.assertEqual(skills.home(), [{'id': 'open-photo', 'app': 'Photos', 'title': card['title'], 'mastery': 2}])
        self.assertEqual(skills.suggestion('en')['skill'], 'youtube-play')

    def test_stopping_saves_the_attempt_but_no_star(self):
        skills.record(skills.starters()['open-photo'], [{'id': 's1', 'result': 'stopped', 'hints': 0}], finished=False)
        self.assertEqual(paths.read_jsonl(skills.ATTEMPTS)[0]['finished'], False)
        self.assertEqual(skills.home(), [])


if __name__ == '__main__':
    unittest.main()
