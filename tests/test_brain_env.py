"""Which ANTHROPIC_* env each brain hands to Claude Code. A stray key must never move a Claude plan user onto API billing."""
import os
import unittest
from unittest.mock import patch

import brain


class BrainEnvTest(unittest.TestCase):
    def env(self, prefs, inherited=None, secrets=None):
        secrets = {'CHIRON_SECRET_ANTHROPIC': 'sk-ant-keychain', 'CHIRON_SECRET_CUSTOM': 'custom-key', **(secrets or {})}
        with patch.object(brain, 'pref', side_effect=lambda k, d: prefs.get(k, d)), patch.dict(os.environ, secrets):
            return brain.claude_env(base={'PATH': '/bin', **(inherited or {})})

    def test_plan_brain_drops_any_inherited_key(self):
        env = self.env({'brain': 'claude-code'}, {'ANTHROPIC_API_KEY': 'sk-ant-from-shell'})
        self.assertNotIn('ANTHROPIC_API_KEY', env)
        self.assertNotIn('ANTHROPIC_BASE_URL', env)

    def test_anthropic_brain_uses_the_keychain_key_only(self):
        env = self.env({'brain': 'anthropic'}, {'ANTHROPIC_API_KEY': 'sk-ant-from-shell'})
        self.assertEqual(env['ANTHROPIC_API_KEY'], 'sk-ant-keychain')
        env = self.env({'brain': 'anthropic'}, {'ANTHROPIC_API_KEY': 'sk-ant-from-shell'}, {'CHIRON_SECRET_ANTHROPIC': ''})
        self.assertNotIn('ANTHROPIC_API_KEY', env)   # no saved key: never fall back to a shell one

    def test_openai_brain_never_gets_an_anthropic_key(self):
        self.assertNotIn('ANTHROPIC_API_KEY', self.env({'brain': 'openai'}, {'ANTHROPIC_API_KEY': 'x'}))

    def test_custom_brain_points_at_its_server_with_its_own_key(self):
        env = self.env({'brain': 'custom', 'apiBase': 'http://localhost:11434', 'apiModel': 'qwen3'}, {'ANTHROPIC_API_KEY': 'x'})
        self.assertEqual((env['ANTHROPIC_BASE_URL'], env['ANTHROPIC_AUTH_TOKEN'], env['ANTHROPIC_API_KEY']), ('http://localhost:11434', 'custom-key', ''))
        self.assertEqual(env['ANTHROPIC_DEFAULT_HAIKU_MODEL'], 'qwen3')

    def test_a_saved_server_address_only_counts_when_custom_is_chosen(self):
        self.assertNotIn('ANTHROPIC_BASE_URL', self.env({'brain': 'anthropic', 'apiBase': 'http://localhost:11434'}))
        self.assertNotIn('ANTHROPIC_BASE_URL', self.env({'brain': 'claude-code', 'apiBase': 'http://localhost:11434'}))
        # An older install with a server and no brain choice yet keeps using its server.
        self.assertEqual(self.env({'apiBase': 'http://localhost:11434'})['ANTHROPIC_BASE_URL'], 'http://localhost:11434')

    def test_every_claude_spawn_goes_through_claude_env(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        source = (root / 'chiron.py').read_text() + (root / 'chiron' / 'llm.py').read_text()
        self.assertEqual(source.count('env.update(server('), 1, 'only claude_env() may add the custom server env')
        self.assertNotIn("**server()", source)
        self.assertNotIn("**B.server()", source)
        self.assertIn("env=B.claude_env()", source)
        self.assertIn("['claude', 'auth', 'status'], capture_output=True, text=True, timeout=20, env=claude_env()", source)


class LanguageAndOpenAITest(unittest.TestCase):
    def test_system_prompt_replies_in_the_app_language(self):
        for lang, name in (('en', 'English'), ('hi', 'Hindi'), ('fr', 'English')):
            with patch.object(brain, 'pref', side_effect=lambda k, d, lang=lang: lang if k == 'lang' else d):
                self.assertIn(f'Reply in {name}.', brain.system_prompt(brain.ASK_FIRST))

    def test_openai_brain_warms_no_claude(self):
        with patch.object(brain, 'pref', side_effect=lambda k, d: 'openai' if k == 'brain' else d), \
             patch.object(brain, 'start_claude', side_effect=AssertionError('no Claude for an OpenAI brain')):
            self.assertIsNone(brain.start_ai())

    def test_openai_answer_is_tool_free_logged_once_and_in_the_app_language(self):
        from chiron import providers
        said, logged = [], []
        reply = providers.Reply('Paris is sunny today.', 0.0004, 300, 20, 800)
        with patch.object(brain, 'pref', side_effect=lambda k, d: {'brain': 'openai', 'lang': 'hi'}.get(k, d)), \
             patch.object(providers.OpenAIProvider, 'ask', return_value=reply) as ask, \
             patch.object(brain, 'say', side_effect=lambda tag, text: said.append((tag, text))), \
             patch.object(brain, 'log_turn', side_effect=lambda *a, **k: logged.append((a, k))), \
             patch.object(brain, 'remember_turn'):
            brain.openai_answer('weather in paris', 'Context: Safari', 'weather in paris', 0.0)
        system, message = ask.call_args[0][:2]
        self.assertIn('Reply in Hindi.', system)
        self.assertIn('cannot click', system)
        self.assertTrue(message.endswith('Request: weather in paris'))
        self.assertEqual(said, [('✓', 'Paris is sunny today.')])
        self.assertEqual(logged[0][0][3], 0)   # the provider already logged $0.0004 to usage.jsonl; log.jsonl must not count it again

    def test_openai_errors_are_plain_words(self):
        from chiron import providers
        said = []
        with patch.object(providers.OpenAIProvider, 'ask', side_effect=providers.ProviderError('nokey')), \
             patch.object(brain, 'say', side_effect=lambda tag, text: said.append((tag, text))), \
             patch.object(brain, 'log_turn'), patch.object(brain, 'end_turn'):
            brain.openai_answer('hi', '', 'hi', 0.0)
        self.assertEqual(said, [('!', 'Add your OpenAI key in Settings first.')])


if __name__ == '__main__':
    unittest.main()
