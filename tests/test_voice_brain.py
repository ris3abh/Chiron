"""The brain's half of Phase 2: Hindi commands reach fast(), instant replies speak the app language, "say that again"
costs nothing, and voice.jsonl counts on Home."""
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

import brain
from chiron import home, paths


class VoiceBrainTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory(); self.addCleanup(root.cleanup)
        p = patch.dict(os.environ, {'CHIRON_DIR': root.name}); p.start(); self.addCleanup(p.stop)
        self.dir = root.name

    def write(self, name, rows):
        with open(os.path.join(self.dir, name), 'w') as f: f.write('\n'.join(map(json.dumps, rows)) + '\n')

    def test_hindi_reaches_the_same_instant_command(self):
        seen = []
        with patch.object(brain, 'named_shortcut', side_effect=lambda t: seen.append(t)), patch.object(brain, 'fast_hands', return_value='handled'):
            for said in ('कैलकुलेटर खोलो', 'calculator kholo', 'open calculator'):
                self.assertEqual(brain.fast(said), 'handled')
        self.assertEqual(seen, ['open calculator'] * 3)

    def test_say_that_again_replays_the_last_reply_with_no_ai(self):
        self.write('log.jsonl', [{'task': 'a', 'reply': 'first'}, {'task': 'b', 'reply': 'Opened Notes.'}, {'task': 'c', 'status': 'running'}])
        self.assertEqual(brain.fast('फिर से बोलो'), 'Opened Notes.')
        self.assertEqual(brain.fast('say that again'), 'Opened Notes.')
        with patch.dict(os.environ, {'CHIRON_LIVE': '1'}):
            self.assertIsNone(brain.fast('say that again'), 'mid-speech it waits for confirmed words')
        self.write('log.jsonl', [{'task': 'a', 'status': 'running'}])
        self.assertIsNone(brain.fast('say that again'))

    def test_instant_replies_follow_the_app_language(self):
        self.assertEqual(brain.fast_line('Opened Calculator.'), 'Opened Calculator.')
        paths.private_json(paths.PREFS, {'lang': 'hi'})
        self.assertEqual(brain.fast_line('Opened Calculator.'), 'Calculator खोल दिया।')
        self.assertEqual(brain.fast_line('Closed Notes.'), 'Notes बंद कर दिया।')
        self.assertEqual(brain.fast_line('Searched news on YouTube.'), 'YouTube पर news खोज दिया।')
        self.assertEqual(brain.fast_line('Some other line.'), 'Some other line.')

    def test_voice_words_count_on_home_by_language(self):
        now, day = time.time(), time.strftime('%Y-%m-%d %H:%M:%S')
        old = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now - 86400 * 20))
        self.write('dictation.json', [])
        with open(os.path.join(self.dir, 'dictation.json'), 'w') as f:
            json.dump({'words': 100, 'todayWords': 10, 'day': time.strftime('%Y-%m-%d'), 'seconds': 0}, f)
        self.write('voice.jsonl', [
            {'id': 'a', 'at': day, 'lang': 'hi', 'engine': 'speech', 'words': 40, 'seconds': 10, 'understood': True},
            {'id': 'b', 'at': day, 'lang': 'en', 'engine': 'speech', 'words': 5, 'seconds': 2, 'understood': True},
            {'id': 'b', 'at': day, 'lang': 'en', 'engine': 'speech', 'words': 5, 'seconds': 2, 'understood': False},   # cancelled at once
            {'id': 'c', 'at': old, 'lang': 'en', 'engine': 'speech', 'words': 80, 'seconds': 30, 'understood': True},
            {'at': 5, 'words': 'x'}, {'id': 'd', 'at': day, 'words': True}])
        w = home.state()['words']
        self.assertEqual((w['today'], w['week'], w['all']), (50, 50, 220))
        self.assertEqual(w['langs'], {'en': 180, 'hi': 40})
        self.assertEqual(w['minutes_saved'], 2, '120 words at 40 wpm, less 40 s talking')


if __name__ == '__main__':
    unittest.main()
