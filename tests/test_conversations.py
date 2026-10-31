"""chiron/conversations.py: grouping, outcomes, and deleting words without touching spend."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from chiron import conversations, paths, usage


class ConversationsTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory(); self.addCleanup(root.cleanup)
        p = patch.dict(os.environ, {'CHIRON_DIR': root.name}); p.start(); self.addCleanup(p.stop)
        self.dir = root.name
        month = __import__('time').strftime('%Y-%m')
        self.rows = [
            {'id': 'a', 'at': f'{month}-01 10:00:00', 'task': 'open Notes', 'reply': 'Opened Notes.', 'usd': 0, 'model': 'instant', 'path': 'instant'},
            {'id': 'b', 'at': f'{month}-01 10:03:00', 'task': 'what is a PDF', 'reply': 'A file.', 'usd': 0.01, 'model': 'haiku', 'steps': ['Reading the window']},
            {'id': 'c', 'at': f'{month}-01 12:00:00', 'task': 'what is RAM', 'reply': 'Memory.', 'usd': 0.02, 'model': 'haiku', 'steps': []},
            {'id': 'd', 'at': f'{month}-01 13:00:00', 'task': 'play a song', 'reply': 'Playing.', 'usd': 0.03, 'model': 'haiku', 'steps': ['Clicking “Play”']},
            {'id': 'd', 'at': f'{month}-01 13:00:00', 'task': 'play a song', 'status': 'running'},   # checkpoint: not an ask
        ]
        with open(os.path.join(root.name, 'log.jsonl'), 'w') as f:
            f.write('\n'.join(map(json.dumps, self.rows)) + '\nnot json\n')

    def test_groups_by_gap_newest_first_with_outcome_and_cost(self):
        out = conversations.listing()
        self.assertEqual([g['title'] for g in out], ['play a song', 'what is RAM', 'open Notes'])
        self.assertEqual([g['outcome'] for g in out], ['did', 'question', 'did'])
        self.assertEqual(out[2]['usd'], 0.01)
        self.assertEqual([t['q'] for t in out[2]['turns']], ['open Notes', 'what is a PDF'])
        self.assertEqual(out[0]['turns'][0]['steps'], ['Clicking “Play”'])

    def test_the_log_rows_own_outcome_wins_over_any_guess(self):
        paths.append_jsonl(paths.LOG, {'id': 'z', 'at': '2030-01-01 09:00:00', 'task': 'teach me', 'reply': 'Done', 'outcome': 'taught', 'model': 'instant'})
        paths.append_jsonl(paths.LOG, {'id': 'y', 'at': '2030-01-02 09:00:00', 'task': 'send it', 'reply': 'No', 'outcome': 'failed', 'steps': ['Clicking “Send”']})
        out = conversations.listing()
        self.assertEqual([g['outcome'] for g in out[:2]], ['failed', 'taught'])

    def test_old_chats_join_without_repeating_logged_asks(self):
        paths.private_json('chats.json', [{'id': 'x', 'created': 1700000000, 'turns': [{'q': 'old question', 'a': 'old answer'}]},
                                          {'id': 'y', 'created': 1700000000, 'turns': [{'q': 'what is RAM', 'a': 'Memory.'}]}, 'garbage'])
        out = conversations.listing()
        self.assertEqual([g['title'] for g in out], ['play a song', 'what is RAM', 'open Notes', 'old question'])

    def test_delete_removes_words_but_never_the_spend(self):
        before = usage.month_total()
        self.assertEqual(before, 0.06)
        self.assertTrue(conversations.delete(conversations.listing()[0]['id'])['ok'])
        self.assertEqual([g['title'] for g in conversations.listing()], ['what is RAM', 'open Notes'])
        self.assertEqual(usage.month_total(), before, 'deleting a conversation must not lower the month against the cap')
        with open(os.path.join(self.dir, 'log.jsonl')) as f: text = f.read()
        self.assertNotIn('play a song', text); self.assertNotIn('Playing.', text); self.assertIn('not json', text)
        self.assertFalse(conversations.delete('nope')['ok'])

    def test_clear_all(self):
        paths.private_json('chats.json', [{'id': 'x', 'created': 1700000000, 'turns': [{'q': 'old', 'a': 'a'}]}])
        with open(os.path.join(self.dir, 'recent.jsonl'), 'w') as f: f.write('{"task": "secret"}\n')
        before = usage.month_total()
        conversations.clear()
        self.assertEqual(conversations.listing(), [])
        self.assertEqual(usage.month_total(), before)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'recent.jsonl')))
        with open(os.path.join(self.dir, 'log.jsonl')) as f: self.assertNotIn('what is RAM', f.read())


if __name__ == '__main__':
    unittest.main()
