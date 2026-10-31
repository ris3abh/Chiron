"""chiron/tts.py with recorded responses: no network, no sound."""
import base64
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from chiron import paths, tts, usage

AUDIO = {'audioContent': base64.b64encode(b'mp3-bytes').decode()}


class SpokenVersionTests(unittest.TestCase):
    def test_markdown_and_symbols_become_speech(self):
        said = tts.spoken_version('## Steps\n\n- **Open** [Notes](https://x.com)\n- Press `⌘S`\n\nIt costs $5 & saves 50%.', 'en')
        self.assertEqual(said, ['Steps', 'Open Notes', 'Press ⌘S', 'It costs five dollars and saves fifty percent.'])

    def test_numbers_as_words_in_both_languages(self):
        self.assertEqual(tts.spoken_version('I have 21 mails and 1,250 photos.', 'en'), ['I have twenty one mails and one thousand two hundred and fifty photos.'])
        self.assertEqual(tts.spoken_version('आपके पास 21 मेल हैं, 3 लाख नहीं।', 'hi'), ['आपके पास इक्कीस मेल हैं, तीन लाख नहीं।'])
        self.assertEqual(tts.spoken_version('₹1,50,000 और 3.14', 'hi'), ['एक लाख पचास हज़ार रुपये और तीन दशमलव एक चार'])
        self.assertEqual(tts.number(99, 'hi'), 'निन्यानवे')
        self.assertEqual(len(tts.HI_UNDER_100), 100)

    def test_times_and_codes_are_left_for_the_voice(self):
        self.assertEqual(tts.spoken_version('Meet at 10:30 with code 007', 'en'), ['Meet at 10:30 with code 007'])

    def test_sentences_split_on_danda_and_long_ones_break(self):
        self.assertEqual(tts.sentences('पहला वाक्य। दूसरा वाक्य! Third one?'), ['पहला वाक्य।', 'दूसरा वाक्य!', 'Third one?'])
        long = ', '.join(['this is a clause of some words'] * 12)
        self.assertTrue(all(len(s) <= 220 for s in tts.sentences(long)))

    def test_long_answers_stop_near_the_limit(self):
        items, left = tts.script(' '.join(['This sentence has exactly six words.'] * 40), 'en')
        self.assertEqual(len(items), 20)
        self.assertTrue(left.startswith('This sentence'))
        self.assertEqual(tts.script('Short.', 'en')[1], '')


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory(); self.addCleanup(root.cleanup)
        p = patch.dict(os.environ, {'CHIRON_DIR': root.name}); p.start(); self.addCleanup(p.stop)
        self.dir = root.name

    def test_chirp_uses_markup_and_the_speed_setting(self):
        with patch.object(tts, 'request', return_value=AUDIO) as call:
            path = tts.audio_for('Hello there.', 'hi', 'Aoede', 0.85, 'k')
        body = call.call_args[0][0]
        self.assertEqual(body['input'], {'markup': 'Hello there.'})
        self.assertEqual(body['voice'], {'languageCode': 'hi-IN', 'name': 'hi-IN-Chirp3-HD-Aoede'})
        self.assertEqual(body['audioConfig'], {'audioEncoding': 'MP3', 'speakingRate': 0.85})
        with open(path, 'rb') as f: self.assertEqual(f.read(), b'mp3-bytes')

    def test_repeats_are_free_and_logged_once(self):
        with patch.object(tts, 'request', return_value=AUDIO) as call:
            for _ in range(3): tts.audio_for('Same caption.', 'en', None, 0.85, 'k')
        self.assertEqual(call.call_count, 1)
        rows = paths.read_jsonl(paths.USAGE)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]['engine'], rows[0]['model'], rows[0]['chars']), ('google-tts', 'chirp3-hd', 13))
        self.assertEqual(rows[0]['usd'], 0, 'inside the free tier')
        with patch.object(tts, 'request', return_value=AUDIO) as call:
            tts.audio_for('Same caption.', 'en', None, 1.0, 'k')
        self.assertEqual(call.call_count, 1, 'another speed is other audio')

    def test_chain_falls_to_wavenet_then_apple(self):
        calls = []
        def chirp_gone(body, key):
            calls.append(body['voice']['name'])
            if 'Chirp' in body['voice']['name']: raise tts.TTSError('voice')
            return AUDIO
        with patch.object(tts, 'request', side_effect=chirp_gone):
            self.assertIsNotNone(tts.audio_for('Hi.', 'en', None, 1, 'k'))
        self.assertEqual(calls, ['en-IN-Chirp3-HD-Kore', 'en-IN-Wavenet-A'])
        self.assertEqual(paths.read_jsonl(paths.USAGE)[0]['model'], 'wavenet')
        with patch.object(tts, 'request', side_effect=tts.TTSError('offline')):
            self.assertIsNone(tts.audio_for('Offline now.', 'en', None, 1, 'k'))

    def test_over_the_cap_only_cached_audio_plays(self):
        with patch.object(tts, 'request', return_value=AUDIO): tts.audio_for('Cached.', 'en', None, 1, 'k')
        with patch.object(tts.usage, 'over_cap', return_value=True), patch.object(tts, 'request') as call:
            self.assertIsNotNone(tts.audio_for('Cached.', 'en', None, 1, 'k'))
            self.assertIsNone(tts.audio_for('New words.', 'en', None, 1, 'k'))
        call.assert_not_called()

    def test_speak_plays_in_order_and_uses_apple_with_no_key(self):
        played = []
        class P:
            def __init__(self, cmd): played.append(cmd)
            def wait(self): return 0
            def terminate(self): pass
        with patch.object(tts.subprocess, 'Popen', P), patch.object(tts, 'request', return_value=AUDIO), patch.object(tts, 'PAUSE', 0), patch('signal.signal'):
            self.assertEqual(tts.speak('One here. Two here.', 'en', key='k'), 2)
            self.assertTrue(all(c[0] == '/usr/bin/afplay' for c in played))
            played.clear()
            tts.speak('No key.', 'en', key='', say_args=['-v', 'Rishi', '-r', '160'])
        self.assertEqual(played, [['/usr/bin/say', '-v', 'Rishi', '-r', '160', '--', 'No key.']], 'only when Settings turned Apple on')

    def test_with_google_unavailable_chiron_stays_silent_by_default(self):
        with patch.object(tts.subprocess, 'Popen') as started, patch.object(tts, 'request', side_effect=tts.TTSError('offline')), patch.object(tts, 'PAUSE', 0), patch('signal.signal'):
            self.assertEqual(tts.speak('One here. Two here.', 'en', key='k'), 0)
            self.assertEqual(tts.speak('No key at all.', 'en', key=''), 0)
        started.assert_not_called()

    def test_long_answer_saves_the_rest_and_asks(self):
        spoken = []
        with patch.object(tts, 'audio_for', side_effect=lambda s, *a: spoken.append(s) or 'clip.mp3'), patch.object(tts.subprocess, 'Popen'), patch.object(tts, 'PAUSE', 0), patch('signal.signal'):
            tts.speak(' '.join(['This sentence has exactly six words.'] * 40), 'en', key='k')
        self.assertEqual(spoken[-1], 'Shall I go on?')
        self.assertIn('This sentence', tts.pending_rest()['text'])
        tts.clear_rest()
        self.assertIsNone(tts.pending_rest())

    def test_a_rejected_key_says_so(self):
        import urllib.error
        with patch('urllib.request.urlopen', side_effect=urllib.error.HTTPError(tts.URL, 403, 'no', {}, None)):
            with self.assertRaises(tts.TTSError) as e: tts.test('bad')
        self.assertEqual(e.exception.kind, 'rejected')

    def test_only_characters_past_the_free_tier_count_toward_the_cap(self):
        usage.record('google-tts', 'chirp3-hd', purpose='speak', chars=999_900)
        self.assertEqual(usage.month_total(), 0)
        with patch.object(tts, 'request', return_value=AUDIO): tts.audio_for('x' * 1000, 'en', None, 1, 'k')
        self.assertAlmostEqual(usage.month_total(), 900 * 0.00003)
        self.assertEqual(usage.billable_chars('chirp3-hd', 10), 10, 'past the tier every character counts')
        self.assertEqual(usage.billable_chars('wavenet', 10), 0, 'each voice has its own allowance')

    def test_lesson_captions_are_free_on_repeat(self):
        with patch.object(tts, 'request', return_value=AUDIO) as call:
            for _ in range(2):
                for sentence, _end in tts.script('Click the round Chrome icon at the bottom.', 'en')[0]: tts.audio_for(sentence, 'en', None, 0.85, 'k')
        self.assertEqual(call.call_count, 1)


if __name__ == '__main__':
    unittest.main()
