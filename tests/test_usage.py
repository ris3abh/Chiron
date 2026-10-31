import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from chiron import paths, usage


class UsageTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory(); self.addCleanup(root.cleanup)
        p = patch.dict(os.environ, {'CHIRON_DIR': root.name}); p.start(); self.addCleanup(p.stop)
        self.dir = root.name

    def test_cost_uses_longest_price_prefix(self):
        self.assertAlmostEqual(usage.cost('claude-haiku-4-5-20251001', 1_000_000, 0), 1.0)
        self.assertAlmostEqual(usage.cost('claude-haiku-4-5', 0, 1_000_000), 5.0)
        self.assertAlmostEqual(usage.cost('claude-haiku-4-5', 0, 0, cache_read=1_000_000), 0.1)
        self.assertAlmostEqual(usage.cost('jev-latest', 1_000_000, 500), 0.042)
        self.assertEqual(usage.cost('llama3:8b', 10_000, 10_000), 0.0)   # local models are free

    def test_month_total_counts_usage_and_claude_code_once(self):
        month = time.strftime('%Y-%m')
        usage.record('jev', 'jev-latest', 1000, 0, 0.001, 'test')
        usage.record('anthropic', 'claude-haiku-4-5', 10, 5, 0.002, 'test')
        with open(paths.path(paths.USAGE), 'a') as f: f.write('{broken\n')
        rows = [{'id': 'a', 'at': f'{month}-01 10:00:00', 'task': 'x', 'status': 'running'},   # checkpoint: no usd
                {'id': 'a', 'at': f'{month}-01 10:00:00', 'task': 'x', 'reply': 'y', 'usd': 0.01},
                {'id': 'a', 'at': f'{month}-01 10:00:00', 'task': 'x', 'reply': 'y', 'usd': 0.01},   # logged twice: counts once
                {'at': '2001-01-01 10:00:00', 'task': 'old', 'reply': 'y', 'usd': 9},
                {'at': f'{month}-02 10:00:00', 'task': 'open notes', 'reply': '', 'usd': 0, 'model': 'instant'}]
        with open(paths.path(paths.LOG), 'w') as f: f.write('\n'.join(map(json.dumps, rows)) + '\n')
        self.assertAlmostEqual(usage.month_total(), 0.013)
        self.assertEqual(usage.by_engine(), {'jev': 0.001, 'anthropic': 0.002, 'claude-code': 0.01})

    def test_cap_and_over_cap(self):
        self.assertEqual(usage.cap(), 5.0)
        paths.private_json(paths.PREFS, {'cap': 1})
        self.assertFalse(usage.over_cap())
        usage.record('anthropic', 'claude-haiku-4-5', usd=1.5)
        self.assertTrue(usage.over_cap())
        paths.private_json(paths.PREFS, {'cap': 500})
        self.assertEqual(usage.cap(), 50.0)

    def test_files_are_private(self):
        usage.record('jev', 'jev-latest')
        self.assertEqual(os.stat(paths.path(paths.USAGE)).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(self.dir).st_mode & 0o777, 0o700)


if __name__ == '__main__':
    unittest.main()
