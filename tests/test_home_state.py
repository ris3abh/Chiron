import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from chiron import home, paths


class HomeStateTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory(); self.addCleanup(root.cleanup)
        p = patch.dict(os.environ, {'CHIRON_DIR': root.name}); p.start(); self.addCleanup(p.stop)
        self.dir = root.name

    def write(self, name, text):
        with open(os.path.join(self.dir, name), 'w') as f: f.write(text)

    def test_empty(self):
        s = home.state()
        self.assertEqual(s['lang'], 'en')
        self.assertEqual(s['today'], {'kind': 'none'})
        self.assertEqual(s['words'], {'today': 0, 'week': 0, 'all': 0, 'minutes_saved': 0, 'langs': {'en': 0, 'hi': 0}})
        self.assertEqual(s['spend']['month_usd'], 0)
        self.assertEqual(s['spend']['cap_usd'], 5.0)
        self.assertEqual(s['recent'], [])
        self.assertEqual(s['connections']['brain']['kind'], 'claude-code')
        self.assertEqual(s['connections']['speech'], {'engine': 'apple', 'ok': True})
        for later in ('skills', 'weak', 'streak', 'guardian', 'papers'):
            self.assertNotIn(later, s)   # their tiles stay hidden until their phase
        json.dumps(s)

    def test_typical(self):
        now, today = time.time(), time.strftime('%Y-%m-%d')
        self.write('dictation.json', json.dumps({'words': 1200, 'todayWords': 40, 'day': today, 'seconds': 1830, 'sessions': 30,
                                                 'history': [{'id': '1', 'timestamp': now - 3600, 'app': 'TextEdit', 'text': 'one two three'},
                                                             {'id': '2', 'timestamp': now - 86400 * 2, 'app': 'Notes', 'text': ' '.join(['w'] * 60)},
                                                             {'id': '3', 'timestamp': now - 86400 * 20, 'app': 'Notes', 'text': 'old words'}]}))
        stamp = lambda secs: time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now - secs))
        rows = [{'id': f'r{i}', 'at': stamp(1000 - i), 'task': f'ask {i}', 'reply': 'ok', 'usd': 0.001, 'model': 'haiku'} for i in range(12)]
        rows.append({'at': stamp(10), 'task': 'open Notes', 'reply': 'Opened Notes', 'usd': 0, 'model': 'instant'})
        rows.append({'id': 'r99', 'at': stamp(5), 'task': 'partial', 'status': 'running'})   # checkpoint only: not in Recent
        self.write('log.jsonl', '\n'.join(map(json.dumps, rows)) + '\n')
        self.write('usage.jsonl', json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'engine': 'jev', 'model': 'jev', 'usd': 0.0001}) + '\n')
        paths.private_json(paths.PREFS, {'lang': 'hi', 'cap': 3})
        paths.private_json(paths.CONNECTIONS, {'jev': {'ok': True}, 'claude-code': {'ok': True}})
        s = home.state()
        self.assertEqual(s['lang'], 'hi')
        self.assertEqual(s['words']['today'], 40)
        self.assertEqual(s['words']['week'], 63)
        self.assertEqual(s['words']['all'], 1200)
        self.assertEqual(s['words']['minutes_saved'], 30)
        self.assertEqual(len(s['recent']), 10)
        self.assertEqual(s['recent'][0]['text']['en'], 'open Notes')
        self.assertEqual(s['recent'][0]['kind'], 'do')
        self.assertEqual(s['recent'][1]['kind'], 'ask')
        self.assertAlmostEqual(s['spend']['month_usd'], 0.0121)
        self.assertEqual(s['spend']['cap_usd'], 3.0)
        self.assertEqual(s['spend']['by_engine'], {'jev': 0.0001, 'claude-code': 0.012})
        self.assertTrue(s['connections']['jev']['ok'])
        self.assertTrue(s['connections']['brain']['ok'])

    def test_corrupted_lines_and_files_are_skipped(self):
        self.write('dictation.json', '{"words": "many", "todayWords": tru')
        self.write('log.jsonl', 'not json\n[1,2]\n{"at": "2026-10-28 10:00:00", "task": "fine", "reply": "ok", "usd": "free"}\n\x00\x00\n')
        self.write('usage.jsonl', '{"at": 5, "usd": "x"}\n{"half": \n')
        self.write('connections.json', '[]')
        s = home.state()
        self.assertEqual(s['words']['all'], 0)
        self.assertEqual([r['text']['en'] for r in s['recent']], ['fine'])
        self.assertEqual(s['spend']['month_usd'], 0)
        self.assertFalse(s['connections']['jev']['ok'])

    def test_conn_test_reports_plain_language_and_caches_health(self):
        from chiron import providers
        with patch.object(providers.AnthropicProvider, 'ask', side_effect=providers.ProviderError('rejected')):
            r = home.do('conn.test', {'name': 'anthropic', 'value': 'bad-key'})
        self.assertFalse(r['ok'])
        self.assertEqual(r['detail'], 'That key was rejected. Check you copied all of it.')
        self.assertNotIn('anthropic', paths.read_json(paths.CONNECTIONS, {}))   # an unsaved bad key is not "the connection"
        with patch.object(providers.AnthropicProvider, 'ask', return_value=providers.Reply('OK', 0.00002, 20, 1, 640)):
            r = home.do('conn.test', {'name': 'anthropic', 'value': 'good-key'})
        self.assertEqual((r['ok'], r['ms'], r['usd']), (True, 640, 0.00002))
        self.assertTrue(paths.read_json(paths.CONNECTIONS, {})['anthropic']['ok'])
        with patch.dict(os.environ, {'CHIRON_SECRET_JEV': ''}):
            r = home.do('conn.test', {'name': 'jev'})
        self.assertFalse(r['ok'])
        self.assertEqual(r['kind'], 'nokey')

    def test_name_prefers_what_the_user_said_then_the_mac_account(self):
        self.write('me.json', json.dumps({'version': 2, 'facts': [
            {'category': 'basics', 'kind': 'name', 'value': 'Asha Verma', 'source': 'contacts'},
            {'category': 'basics', 'kind': 'name', 'value': 'Ashu', 'source': 'you'}]}))
        self.assertEqual(home.state()['name'], 'Ashu')
        self.write('me.json', json.dumps({'name': 'Legacy Name'}))
        self.assertEqual(home.name(), 'Legacy')
        self.write('me.json', '[]')
        with patch('pwd.getpwuid', return_value=type('P', (), {'pw_gecos': 'Rishabh Sharma,,,'})()):
            self.assertEqual(home.name(), 'Rishabh')

    def test_dictations_and_activity(self):
        now = time.time()
        self.write('dictation.json', json.dumps({'history': [
            {'id': '1', 'timestamp': now - 60, 'app': 'Notes', 'text': '  hello   there  '},
            {'id': '2', 'timestamp': now - 86400, 'app': 'Mail', 'text': 'yesterday'},
            {'id': '3', 'timestamp': now - 86400 * 200, 'app': 'Mail', 'text': 'too old for the heatmap'},
            {'id': '4', 'timestamp': 'bad', 'text': 'skipped'}, 'garbage']}))
        stamp = lambda secs: time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now - secs))
        rows = [{'id': 'a', 'at': stamp(30), 'task': 'ask', 'reply': 'ok'}, {'id': 'a', 'at': stamp(30), 'task': 'ask', 'reply': 'ok'},
                {'id': 'b', 'at': stamp(20), 'task': 'running', 'status': 'running'}]
        self.write('log.jsonl', '\n'.join(map(json.dumps, rows)) + '\n')
        s = home.state()
        self.assertEqual([d['text'] for d in s['dictations']], ['hello there', 'yesterday', 'too old for the heatmap'])
        self.assertEqual(s['dictations'][0]['app'], 'Notes')
        today, yesterday = time.strftime('%Y-%m-%d'), time.strftime('%Y-%m-%d', time.localtime(now - 86400))
        self.assertEqual(s['activity'].get(today), 2, 'one dictation + one ask (the repeated row is one turn)')
        self.assertEqual(s['activity'].get(yesterday), 1)
        self.assertEqual(len(s['activity']), 2, 'nothing older than 16 weeks')

    def test_unknown_method_raises(self):
        with self.assertRaises(KeyError):
            home.do('nope', {})


if __name__ == '__main__':
    unittest.main()
