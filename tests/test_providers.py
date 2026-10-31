"""Request shapes and cost maths against recorded responses; nothing reaches the network."""
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from chiron import paths, providers

ANTHROPIC_REPLY = {'id': 'msg_1', 'type': 'message', 'model': 'claude-haiku-4-5-20251001', 'role': 'assistant',
                   'content': [{'type': 'text', 'text': 'OK'}],
                   'usage': {'input_tokens': 12, 'output_tokens': 2, 'cache_read_input_tokens': 2000, 'cache_creation_input_tokens': 0}}
OPENAI_REPLY = {'id': 'chatcmpl-1', 'model': 'gpt-5-mini-2025-08-07', 'choices': [{'message': {'role': 'assistant', 'content': '{"ok": true}'}}],
                'usage': {'prompt_tokens': 1000, 'completion_tokens': 100, 'prompt_tokens_details': {'cached_tokens': 400}}}


class Recorder:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def __call__(self, url, body, headers, timeout):
        self.calls.append((url, body, headers))
        if isinstance(self.reply, Exception): raise self.reply
        return self.reply


class ProvidersTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory(); self.addCleanup(root.cleanup)
        p = patch.dict(os.environ, {'CHIRON_DIR': root.name}); p.start(); self.addCleanup(p.stop)

    def usage_rows(self):
        return paths.read_jsonl(paths.USAGE)

    def test_anthropic_request_caches_system_and_costs_tokens(self):
        rec = Recorder(ANTHROPIC_REPLY)
        with patch.object(providers, '_post', rec):
            reply = providers.AnthropicProvider('sk-ant-test').ask('Be brief.', 'Hi', max_tokens=5, json=True, purpose='test')
        url, body, headers = rec.calls[0]
        self.assertEqual(url, 'https://api.anthropic.com/v1/messages')
        self.assertEqual(headers['x-api-key'], 'sk-ant-test')
        self.assertEqual(headers['anthropic-version'], '2023-06-01')
        self.assertEqual(body['system'][0]['cache_control'], {'type': 'ephemeral'})
        self.assertIn('JSON', body['system'][0]['text'])
        self.assertEqual(body['messages'], [{'role': 'user', 'content': 'Hi'}])
        self.assertEqual(reply.text, 'OK')
        self.assertAlmostEqual(reply.usd, (12 * 1 + 2 * 5 + 2000 * 0.1) / 1e6)
        self.assertEqual(reply.input_tokens, 2012)
        row = self.usage_rows()[-1]
        self.assertEqual((row['engine'], row['purpose'], row['ok']), ('anthropic', 'test', True))

    def test_anthropic_images_go_first_in_last_message(self):
        rec = Recorder(ANTHROPIC_REPLY)
        with patch.object(providers, '_post', rec):
            providers.AnthropicProvider('k').ask('s', 'What is this?', images=[b'\xff\xd8jpeg'])
        content = rec.calls[0][1]['messages'][-1]['content']
        self.assertEqual(content[0]['type'], 'image')
        self.assertEqual(content[-1], {'type': 'text', 'text': 'What is this?'})

    def test_openai_json_mode_and_cached_cost(self):
        rec = Recorder(OPENAI_REPLY)
        with patch.object(providers, '_post', rec):
            reply = providers.OpenAIProvider('sk-test').ask('Be brief.', 'Hi', json=True, max_tokens=50)
        url, body, headers = rec.calls[0]
        self.assertEqual(url, 'https://api.openai.com/v1/chat/completions')
        self.assertEqual(headers['Authorization'], 'Bearer sk-test')
        self.assertEqual(body['response_format'], {'type': 'json_object'})
        self.assertEqual(body['messages'][0]['role'], 'system')
        self.assertEqual(body['max_completion_tokens'], 50)
        self.assertAlmostEqual(reply.usd, (600 * 0.25 + 100 * 2.0 + 400 * 0.025) / 1e6)

    def test_custom_server_uses_its_address_and_is_free(self):
        rec = Recorder({**ANTHROPIC_REPLY, 'model': 'qwen3:8b'})
        with patch.object(providers, '_post', rec):
            reply = providers.CustomServerProvider('', 'qwen3:8b', 'http://localhost:11434').ask('s', 'Hi')
        self.assertEqual(rec.calls[0][0], 'http://localhost:11434/v1/messages')
        self.assertEqual(rec.calls[0][2]['Authorization'], 'Bearer none')
        self.assertEqual(reply.usd, 0.0)
        with self.assertRaises(providers.ProviderError) as e:
            providers.CustomServerProvider('', 'm', 'not a url').ask('s', 'Hi')
        self.assertEqual(e.exception.kind, 'missing')

    def test_errors_are_kinded_and_logged(self):
        with self.assertRaises(providers.ProviderError) as e:
            providers.AnthropicProvider('').ask('s', 'Hi')
        self.assertEqual(e.exception.kind, 'nokey')
        with patch.object(providers, '_post', Recorder(providers.ProviderError('rejected', 'HTTP 401'))):
            with self.assertRaises(providers.ProviderError) as e:
                providers.OpenAIProvider('bad').ask('s', 'Hi')
        self.assertEqual(e.exception.kind, 'rejected')
        self.assertFalse(self.usage_rows()[-1]['ok'])

    def test_http_status_maps_to_kind(self):
        import io, urllib.error
        def fail(code):
            return urllib.error.HTTPError('u', code, 'x', {}, io.BytesIO(b'{"error":"no"}'))
        for code, kind in ((401, 'rejected'), (403, 'rejected'), (500, 'server'), (400, 'server')):
            with patch('urllib.request.urlopen', side_effect=fail(code)):
                with self.assertRaises(providers.ProviderError) as e:
                    providers._post('https://x', {}, {}, 1)
                self.assertEqual(e.exception.kind, kind)
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError('down')):
            with self.assertRaises(providers.ProviderError) as e:
                providers._post('https://x', {}, {}, 1)
            self.assertEqual(e.exception.kind, 'offline')

    def test_claude_code_parses_result_row(self):
        out = '\n'.join(json.dumps(r) for r in ({'type': 'system'}, {'type': 'result', 'result': 'OK', 'is_error': False, 'total_cost_usd': 0.0004,
                                                                                    'usage': {'input_tokens': 5, 'cache_read_input_tokens': 100, 'output_tokens': 1}}))
        done = subprocess.CompletedProcess([], 0, out, '')
        with patch.dict(os.environ, {'CHIRON_CLAUDE': '/bin/echo'}), patch.object(providers.subprocess, 'run', return_value=done) as run:
            reply = providers.ClaudeCodeProvider().ask('Reply OK', 'Test')
        args = run.call_args[0][0]
        self.assertIn('--tools', args); self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertEqual(args[args.index('--model') + 1], 'haiku')
        self.assertEqual((reply.text, reply.usd, reply.input_tokens), ('OK', 0.0004, 105))
        self.assertEqual(self.usage_rows()[-1]['engine'], 'claude-code')

    def test_claude_env_passes_key_only_for_anthropic_brain(self):
        with patch.dict(os.environ, {'CHIRON_SECRET_ANTHROPIC': 'sk-ant-1', 'ANTHROPIC_API_KEY': 'stale'}):
            self.assertEqual(providers.claude_env('anthropic')['ANTHROPIC_API_KEY'], 'sk-ant-1')
            self.assertNotIn('ANTHROPIC_API_KEY', providers.claude_env('claude-code'))

    def test_provider_factory_follows_brain_pref(self):
        with patch.dict(os.environ, {'CHIRON_SECRET_OPENAI': 'sk-o', 'CHIRON_SECRET_CUSTOM': ''}):
            paths.private_json(paths.PREFS, {'brain': 'openai'})
            self.assertIsInstance(providers.provider(), providers.OpenAIProvider)
            self.assertEqual(providers.provider().key, 'sk-o')
            paths.private_json(paths.PREFS, {'brain': 'custom', 'apiBase': 'http://localhost:1234', 'apiModel': 'm'})
            p = providers.provider()
            self.assertEqual((type(p), p.base, p.model), (providers.CustomServerProvider, 'http://localhost:1234', 'm'))
            paths.private_json(paths.PREFS, {'brain': 'nonsense'})
            self.assertIsInstance(providers.provider(), providers.ClaudeCodeProvider)


if __name__ == '__main__':
    unittest.main()
