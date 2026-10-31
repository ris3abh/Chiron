"""chiron/speech_eval.py scoring, with a fake engine: tests make no audio and open no app."""
import json
import os
import tempfile
import unittest

from chiron import speech_eval


class SpeechEvalTests(unittest.TestCase):
    def test_same_command_counts_however_it_was_written(self):
        self.assertTrue(speech_eval.score('कैलकुलेटर खोलो', 'calculator kholo')[0])
        self.assertTrue(speech_eval.score('open Calculator', 'Open calculator.')[0])

    def test_wrong_words_do_not(self):
        understood, accuracy = speech_eval.score('open calculator', 'open the garage door')
        self.assertFalse(understood)
        self.assertLess(accuracy, 0.8)
        self.assertEqual(speech_eval.score('', 'anything'), (False, 0.0))

    def test_report_groups_by_language_and_engine(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, 'expected.json'), 'w', encoding='utf-8') as f:
                json.dump([{'file': 'a.wav', 'lang': 'hi', 'text': 'नोट्स खोलो'}, {'file': 'b.wav', 'lang': 'hi', 'text': 'नोट्स बंद करो'},
                           {'file': 'c.wav', 'lang': 'en', 'text': 'open notes'}], f, ensure_ascii=False)
            heard = {'a.wav': 'नोट्स खोलो', 'b.wav': 'कुछ और', 'c.wav': 'open notes'}
            out = speech_eval.report(root, lambda path, lang: {'ok': True, 'text': heard[os.path.basename(path)], 'engine': 'speech'})
        self.assertIn('hi / speech: 1 of 2 understood', out)
        self.assertIn('en / speech: 1 of 1 understood, 100% of words right', out)

    def test_no_recordings_says_so(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIn('No recordings yet', speech_eval.report(root))


if __name__ == '__main__':
    unittest.main()
