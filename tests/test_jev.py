import json
import os
import socket
import tempfile
import unittest
from unittest.mock import patch

from chiron import jev, paths, providers


def reply(answers, tokens=120):
    return {'model': 'jev-1.13.0', 'answers': answers, 'usage': {'input_tokens': tokens, 'output_tokens': 0}}


class JevTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory(); self.addCleanup(root.cleanup)
        p = patch.dict(os.environ, {'CHIRON_DIR': root.name, 'CHIRON_SECRET_JEV': 'jev-key', 'CHIRON_SECRET_ANTHROPIC': ''}); p.start(); self.addCleanup(p.stop)
        self.questions = {'done': jev.noul('It is true that Chrome is in front', 'Chrome is frontmost', 'Another app is frontmost'),
                          'fault': jev.choice('What went wrong?', {'wrong_app': 'Another app', 'correct': 'Nothing'}),
                          'score': jev.score('How independent?', ['Chiron did it', 'Many hints', 'No help'])}

    def test_one_request_carries_every_question(self):
        calls = []
        def post(body, key, base, timeout):
            calls.append((body, key, base, timeout))
            return reply({'done': {'type': 'noul', 'noul': 0.95},
                          'fault': {'type': 'choice', 'choice': 'correct', 'confidence': 0.9, 'probabilities': {}},
                          'score': {'type': 'score', 'score': 1.4, 'confidence': 0.5, 'probabilities': {}}})
        with patch.object(jev, '_post', post):
            out = jev.judge('Front app: Google Chrome', self.questions, 'step')
        self.assertEqual(len(calls), 1)
        body, key, base, timeout = calls[0]
        self.assertEqual((key, base, timeout, body['model']), ('jev-key', 'https://api.typesafe.ai/v1', 3, 'jev-latest'))
        self.assertEqual(set(body['questions']), {'done', 'fault', 'score'})
        self.assertEqual(body['questions']['done']['criteria'], {'true': 'Chrome is frontmost', 'false': 'Another app is frontmost'})
        self.assertEqual(out['done'], jev.Answer('noul', True, 0.95, False, 'jev'))
        self.assertEqual(out['fault'].value, 'correct')
        self.assertTrue(out['score'].unsure)   # confidence 0.5 < 0.7
        row = paths.read_jsonl(paths.USAGE)[-1]
        self.assertEqual((row['engine'], row['input_tokens'], row['purpose']), ('jev', 120, 'step'))
        self.assertAlmostEqual(row['usd'], 120 * 0.042 / 1e6)

    def test_many_questions_split_into_parts(self):
        many = {f'q{i}': jev.noul('x', 'a', 'b') for i in range(jev.MOST + 3)}
        calls = []
        def post(body, *a):
            calls.append(body)
            return reply({n: {'noul': 0.1} for n in body['questions']})
        with patch.object(jev, '_post', post):
            out = jev.judge('s', many)
        self.assertEqual([len(c['questions']) for c in calls], [jev.MOST, 3])
        self.assertEqual(len(out), jev.MOST + 3)
        self.assertFalse(out['q0'].value)

    def test_timeout_retries_once_then_falls_back_to_haiku(self):
        calls = []
        def post(*a):
            calls.append(1); raise jev.JevError('retry', 'timed out')
        fake = providers.Reply('{"done": {"noul": 0.2}, "fault": {"choice": "wrong_app", "confidence": 0.8}, "score": {"score": 2, "confidence": 0.9}}', 0.0003, 400, 40, 900)
        with patch.object(jev, '_post', post), patch.object(providers.ClaudeCodeProvider, 'ask', return_value=fake) as ask:
            out = jev.judge('s', self.questions)
        self.assertEqual(len(calls), 2)
        self.assertEqual(ask.call_args.kwargs['log_as'], 'haiku-fallback')
        self.assertTrue(ask.call_args.kwargs['json'])
        self.assertEqual(out['fault'], jev.Answer('choice', 'wrong_app', 0.8, False, 'haiku-fallback'))
        self.assertFalse(out['done'].value)

    def test_no_key_goes_straight_to_fallback(self):
        fake = providers.Reply('not json at all', 0, 0, 0, 0)
        with patch.object(jev, '_post', side_effect=AssertionError('no Jev call without a key')), \
             patch.object(providers.ClaudeCodeProvider, 'ask', return_value=fake):
            out = jev.judge('s', self.questions, key='')
        self.assertTrue(all(a.engine == 'haiku-fallback' for a in out.values()))
        self.assertTrue(out['done'].unsure)   # an unreadable reply is a coin flip, never a confident yes

    def test_rejected_key_is_not_hidden(self):
        with patch.object(jev, '_post', side_effect=jev.JevError('rejected', 'HTTP 401')):
            with self.assertRaises(jev.JevError):
                jev.judge('s', self.questions)

    def test_post_maps_socket_timeout_to_retry(self):
        with patch('urllib.request.urlopen', side_effect=socket.timeout('slow')):
            with self.assertRaises(jev.JevError) as e:
                jev._post({}, 'k', 'https://api.typesafe.ai/v1', 3)
        self.assertEqual(e.exception.kind, 'retry')

    def test_base_url_is_configurable(self):
        paths.private_json(paths.PREFS, {'jevBase': 'https://gateway.example/typesafe/jev/'})
        self.assertEqual(jev.base_url(), 'https://gateway.example/typesafe/jev')


if __name__ == '__main__':
    unittest.main()
