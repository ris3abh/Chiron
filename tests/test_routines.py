"""Scheduled routines: scratch files and a fake clock."""
import json
import os
import plistlib
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import brain


class RoutineTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory(); self.addCleanup(self.root.cleanup)
        self.env = patch.dict(os.environ, {'CHIRON_DIR': self.root.name}); self.env.start(); self.addCleanup(self.env.stop)
        self.code = patch.multiple(brain, DIR=self.root.name, HOME=self.root.name, PREFS=str(Path(self.root.name) / 'settings.json'))
        self.code.start(); self.addCleanup(self.code.stop)
        Path(brain.PREFS).write_text('{}')

    def monday(self, hour, minute):
        return time.mktime((2026, 10, 19, hour, minute, 0, 0, 0, -1))

    def test_saved_weekday_job_fires_at_the_right_fake_time(self):
        row = brain.routine_add('time', '08:00', 'Summarize my calendar', now=self.monday(7, 0), days='weekdays')
        self.assertEqual(brain.routines(), [row])
        with open(brain.routine_job_path(row['id']), 'rb') as f: job = plistlib.load(f)
        self.assertEqual([r['Weekday'] for r in job['StartCalendarInterval']], [1, 2, 3, 4, 5])
        self.assertFalse(brain.routine_fire(row['id'], self.monday(7, 59)))
        self.assertTrue(brain.routine_fire(row['id'], self.monday(8, 0)))
        self.assertEqual(brain.routine_pop(), [row['id']])

    def test_late_calendar_delivery_runs_once_within_grace(self):
        row = brain.routine_add('time', '08:00', 'Check once after wake', now=self.monday(7, 0), days='daily')
        self.assertTrue(brain.routine_fire(row['id'], self.monday(8, 5)))
        self.assertFalse(brain.routine_fire(row['id'], self.monday(8, 6)))
        self.assertEqual(brain.routine_pop(), [row['id']])
        tomorrow = self.monday(24 + 8, 16)
        self.assertFalse(brain.routine_fire(row['id'], tomorrow))
        created_late = brain.routine_add('time', '08:00', 'Not before creation', now=self.monday(8, 2), days='daily')
        self.assertFalse(brain.routine_fire(created_late['id'], self.monday(8, 5)))

    def test_startup_repairs_existing_weekday_job(self):
        row = brain.routine_add('time', '08:00', 'Repair weekdays', now=self.monday(7, 0), days='weekdays')
        path = brain.routine_job_path(row['id'])
        with open(path, 'rb') as f: job = plistlib.load(f)
        for interval, day in zip(job['StartCalendarInterval'], range(2, 7)): interval['Weekday'] = day
        with open(path, 'wb') as f: plistlib.dump(job, f)
        self.assertEqual(brain.routine_pop(), [])
        with open(path, 'rb') as f: repaired = plistlib.load(f)
        self.assertEqual([r['Weekday'] for r in repaired['StartCalendarInterval']], [1, 2, 3, 4, 5])

    def test_interval_is_cheapest_removed_and_never_runs_while_paused(self):
        row = brain.routine_add('interval', 3600, 'Check the fixture', now=self.monday(8, 0))
        self.assertEqual(row['mode'], 'cheapest')
        Path(brain.PREFS).write_text('{"paused":true}')
        self.assertFalse(brain.routine_fire(row['id'], self.monday(9, 0)))
        self.assertEqual(brain.routine_pop(), [])
        self.assertTrue(brain.routine_remove(row['id']))
        self.assertEqual(brain.routines(), [])
        self.assertFalse(Path(brain.routine_job_path(row['id'])).exists())

    def test_restart_cannot_queue_the_same_occurrence_twice(self):
        row = brain.routine_add('time', '08:00', 'Check once', now=self.monday(7, 0), days='daily')
        self.assertTrue(brain.routine_fire(row['id'], self.monday(8, 0)))
        self.assertFalse(brain.routine_fire(row['id'], self.monday(8, 0)))
        self.assertEqual(brain.routine_pop(), [row['id']])
        self.assertEqual(brain.routines()[0]['lastSlot'], '2026-10-19@08:00')

    def test_failed_launchd_install_does_not_leave_a_saved_routine(self):
        results = [subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 1)]
        with patch.dict(os.environ, {}, clear=True), patch.object(brain.subprocess, 'run', side_effect=results), patch.object(brain.time, 'sleep'):
            with self.assertRaisesRegex(OSError, 'Could not start'):
                brain.routine_add('interval', 3600, 'Never saved')
        self.assertEqual(brain.routines(), [])

    def test_malformed_saved_rows_cannot_break_routine_list_or_fire(self):
        row = brain.routine_add('interval', 3600, 'Still valid', now=self.monday(8, 0))
        malformed = [None, 'bad', {'id': 1}, {'id': 'f' * 12},
                     {'id': 'e' * 12, 'kind': 'interval', 'every': 0, 'ask': 'Bad interval',
                      'mode': 'cheapest', 'created': self.monday(8, 0)}]
        Path(self.root.name, 'routines.json').write_text(json.dumps(malformed + [row]))
        self.assertEqual(brain.routines(), [row])
        self.assertIn(row['id'], brain.routine_command(['list']))
        self.assertFalse(brain.routine_fire('f' * 12, self.monday(9, 0)))

    def test_due_routine_becomes_one_practice_prompt_for_the_box(self):
        kept = brain.routine_add('interval', 3600, 'Practice: rename a file in Finder', now=self.monday(8, 0))
        gone = brain.routine_add('interval', 3600, 'Removed later', now=self.monday(8, 0))
        self.assertTrue(brain.routine_fire(kept['id'], self.monday(9, 1)))
        self.assertTrue(brain.routine_fire(gone['id'], self.monday(9, 1)))
        brain.routine_remove(gone['id'])
        due = brain.routine_due()
        self.assertEqual(due, [{'id': kept['id'], 'ask': 'Practice: rename a file in Finder', 'label': 'Every hour'}])
        self.assertEqual(brain.routine_due(), [])   # drained: a launchd retry never posts it twice
        self.assertTrue(brain.routine_job_path(kept['id']).endswith(f'com.chiron.practice.{kept["id"]}.plist'))


if __name__ == '__main__':
    unittest.main()
