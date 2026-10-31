"""chiron/llm.py: the one tool-free Claude Code call dictation cleanup (and later lessons) share."""
import json
import subprocess
import unittest
from unittest.mock import patch

import brain
from chiron import llm


class LlmTests(unittest.TestCase):
    def setUp(self):
        # An eval run loads a second brain module and binds llm to it; these tests patch this one.
        llm.bind(brain)

    def test_brain_binds_itself_and_reexports_the_calls(self):
        self.assertIs(brain.llm, llm)
        self.assertIs(brain.llm_call, llm.llm_call)
        self.assertIs(brain.llm_process, llm.llm_process)
        self.assertIs(brain.llm_payload, llm.llm_payload)

    def test_payload_is_one_stream_json_line_with_an_optional_image(self):
        line = llm.llm_payload('Hello')
        self.assertTrue(line.endswith('\n'))
        self.assertEqual(json.loads(line), {'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'text', 'text': 'Hello'}]}})
        content = json.loads(llm.llm_payload('Look', 'QUJD'))['message']['content']
        self.assertEqual(content[0]['source'], {'type': 'base64', 'media_type': 'image/jpeg', 'data': 'QUJD'})
        self.assertEqual(content[1], {'type': 'text', 'text': 'Look'})

    def test_process_follows_routing_and_the_custom_server(self):
        for mode, want in [('cheapest', 'haiku'), ('balanced', 'haiku'), ('capable', 'opus')]:
            with self.subTest(mode=mode), patch.object(brain, 'pref', side_effect=lambda k, d: {'routing': mode, 'model': 'opus'}.get(k, d)), \
                 patch.object(brain, 'server', return_value={}), patch.object(llm.subprocess, 'Popen') as launch:
                llm.llm_process('Fixture')
                args = launch.call_args.args[0]
                self.assertEqual(args[args.index('--model') + 1], want)
        with patch.object(brain, 'server', return_value={'ANTHROPIC_BASE_URL': 'http://localhost:1'}), patch.object(llm.subprocess, 'Popen') as launch:
            llm.llm_process('Fixture')
            self.assertEqual(launch.call_args.kwargs['env']['ANTHROPIC_BASE_URL'], 'http://localhost:1')
        with patch.object(llm.subprocess, 'Popen') as launch:
            llm.llm_process('Fixture', 'sonnet')
            args = launch.call_args.args[0]
            self.assertEqual(args[args.index('--model') + 1], 'sonnet')

    def test_call_is_tool_free_and_logs_its_cost_under_its_label(self):
        class Worker:
            pid = 12345
            returncode = 0
            def communicate(self, payload, timeout):
                self.payload = json.loads(payload)
                return json.dumps({'type': 'result', 'result': 'November 12.', 'total_cost_usd': .001}), ''
        worker = Worker()
        with patch.object(llm.subprocess, 'Popen', return_value=worker) as start, patch.object(brain, 'stop_claude'), \
             patch.object(llm.signal, 'signal'), patch.object(llm.atexit, 'register'), patch.object(brain, 'log_turn') as log, \
             patch.object(brain, 'pref', side_effect=lambda k, d: d):
            answer, metrics = brain.llm_call('Stable prefix', 'A question')
        args = start.call_args.args[0]
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertEqual(args[args.index('--model') + 1], 'haiku')
        self.assertIn('--no-session-persistence', args)
        self.assertEqual(args[args.index('--setting-sources') + 1], '')
        self.assertEqual(json.loads(args[args.index('--settings') + 1]), {'disableAllHooks': True})
        self.assertEqual(args[args.index('--system-prompt') + 1], 'Stable prefix')
        self.assertEqual(worker.payload['message']['content'][-1]['text'], 'A question')
        self.assertEqual(log.call_args.args[:2], ('Chiron', ''))
        self.assertEqual((answer, metrics['usd']), ('November 12.', .001))
        self.assertTrue(start.call_args.kwargs['start_new_session'])

    def test_errors_raise_and_always_stop_the_worker(self):
        class Failed:
            pid, returncode = 1, 1
            def communicate(self, payload, timeout): return '', 'boom'
        class ErrorResult:
            pid, returncode = 2, 0
            def communicate(self, payload, timeout): return json.dumps({'type': 'result', 'is_error': True, 'result': 'x'}), ''
        class Slow:
            pid = 3
            def communicate(self, payload, timeout): raise subprocess.TimeoutExpired('claude', 45)
        for worker, error in ((Failed(), RuntimeError), (ErrorResult(), RuntimeError), (Slow(), subprocess.TimeoutExpired)):
            with self.subTest(worker=type(worker).__name__), patch.object(llm.subprocess, 'Popen', return_value=worker), \
                 patch.object(brain, 'stop_claude') as stop, patch.object(llm.signal, 'signal'), patch.object(llm.atexit, 'register'):
                with self.assertRaises(error):
                    brain.llm_call('prefix', 'question', label='Dictation cleanup')
                stop.assert_called_once_with(worker)


if __name__ == '__main__':
    unittest.main()
