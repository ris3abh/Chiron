"""Every single-shot model call behind one interface: Provider.ask(...) -> Reply.

The open-ended main ask (chiron.py's tool loop) still runs through Claude Code; these are for JSON tasks,
lessons, papers and the Settings Test buttons. Each call is logged to usage.jsonl with its cost."""
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import namedtuple

from chiron import paths, usage

Reply = namedtuple('Reply', 'text usd input_tokens output_tokens ms')
KINDS = ('claude-code', 'anthropic', 'openai', 'custom')
ANTHROPIC_MODEL, OPENAI_MODEL = 'claude-haiku-4-5', 'gpt-5-mini'


class ProviderError(Exception):
    """kind is one of rejected | offline | server | nokey | missing, so Settings can say it in plain words."""
    def __init__(self, kind, detail=''):
        super().__init__(detail or kind)
        self.kind, self.detail = kind, detail


def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', **headers}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read(2000).decode('utf-8', 'replace'); e.close()
        raise ProviderError('rejected' if e.code in (401, 403) else 'server', f'HTTP {e.code}: {detail[:300]}')
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ProviderError('offline', str(e))
    except ValueError as e:
        raise ProviderError('server', 'not JSON: ' + str(e))


def _jpeg(image):
    """An image is a path or raw bytes; both go as base64 JPEG."""
    import base64
    data = image if isinstance(image, (bytes, bytearray)) else open(image, 'rb').read()
    return base64.b64encode(data).decode()


class Provider:
    engine = ''

    def __init__(self, key='', model='', base=''):
        self.key, self.model, self.base = key, model, base

    def ask(self, system, messages, model=None, images=(), max_tokens=1024, json=False, purpose='', timeout=60, log_as=None):
        if isinstance(messages, str): messages = [{'role': 'user', 'content': messages}]
        model = model or self.model
        started = time.monotonic()
        try:
            reply = self._ask(system, list(messages), model, images, max_tokens, json, timeout)
        except ProviderError:
            usage.record(log_as or self.engine, model, ms=(time.monotonic() - started) * 1000, purpose=purpose, ok=False)
            raise
        ms = int((time.monotonic() - started) * 1000)
        reply = reply._replace(ms=ms)
        usage.record(log_as or self.engine, model, reply.input_tokens, reply.output_tokens, reply.usd, purpose, ms)
        return reply

    def _ask(self, system, messages, model, images, max_tokens, json_mode, timeout):
        raise NotImplementedError


class AnthropicProvider(Provider):
    engine = 'anthropic'

    def __init__(self, key='', model=ANTHROPIC_MODEL, base='https://api.anthropic.com'):
        super().__init__(key, model, base)

    def headers(self):
        return {'x-api-key': self.key, 'anthropic-version': '2023-06-01'}

    def request(self, system, messages, model, images, max_tokens, json_mode):
        if json_mode: system += '\nReply with one JSON object only, no prose, no code fences.'
        # The system block is cached: lessons and papers resend the same long prompt many times a session.
        body = {'model': model, 'max_tokens': max_tokens, 'messages': messages,
                'system': [{'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'}}]}
        if images:
            last = dict(messages[-1])
            text = last['content'] if isinstance(last['content'], list) else [{'type': 'text', 'text': last['content']}]
            last['content'] = [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': _jpeg(i)}} for i in images] + text
            body['messages'] = messages[:-1] + [last]
        return body

    def _ask(self, system, messages, model, images, max_tokens, json_mode, timeout):
        if not self.key: raise ProviderError('nokey')
        out = _post(self.base.rstrip('/') + '/v1/messages', self.request(system, messages, model, images, max_tokens, json_mode), self.headers(), timeout)
        return self.parse(out, model)

    def parse(self, out, model):
        text = ''.join(b.get('text', '') for b in out.get('content', []) if isinstance(b, dict) and b.get('type') == 'text')
        u = out.get('usage') or {}
        tokens_in = int(u.get('input_tokens') or 0)
        read, write = int(u.get('cache_read_input_tokens') or 0), int(u.get('cache_creation_input_tokens') or 0)
        usd = usage.cost(out.get('model') or model, tokens_in, int(u.get('output_tokens') or 0), read, write)
        return Reply(text, usd, tokens_in + read + write, int(u.get('output_tokens') or 0), 0)


class CustomServerProvider(AnthropicProvider):
    """Settings → Custom server: the same Claude-style API chiron.py's server() points Claude Code at (Ollama, LM Studio, DeepSeek)."""
    engine = 'custom'

    def __init__(self, key='', model='', base=''):
        Provider.__init__(self, key or 'none', model, base)   # local servers take any key

    def headers(self):
        return {**super().headers(), 'Authorization': f'Bearer {self.key}'}

    def _ask(self, system, messages, model, images, max_tokens, json_mode, timeout):
        try: u = urllib.parse.urlparse(self.base)
        except ValueError: u = None
        if not u or u.scheme not in ('http', 'https') or not u.hostname: raise ProviderError('missing', 'no server address')
        out = _post(self.base.rstrip('/') + '/v1/messages', self.request(system, messages, model, images, max_tokens, json_mode), self.headers(), timeout)
        return self.parse(out, model)


class OpenAIProvider(Provider):
    engine = 'openai'

    def __init__(self, key='', model=OPENAI_MODEL, base='https://api.openai.com/v1'):
        super().__init__(key, model, base)

    def request(self, system, messages, model, images, max_tokens, json_mode):
        if json_mode: system += '\nReply with one JSON object only.'
        messages = [{'role': 'system', 'content': system}] + messages
        if images:
            last = dict(messages[-1])
            last['content'] = [{'type': 'text', 'text': last['content']}] + [
                {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + _jpeg(i)}} for i in images]
            messages = messages[:-1] + [last]
        body = {'model': model, 'messages': messages, 'max_completion_tokens': max_tokens}
        if json_mode: body['response_format'] = {'type': 'json_object'}
        return body

    def _ask(self, system, messages, model, images, max_tokens, json_mode, timeout):
        if not self.key: raise ProviderError('nokey')
        out = _post(self.base.rstrip('/') + '/chat/completions', self.request(system, messages, model, images, max_tokens, json_mode),
                    {'Authorization': f'Bearer {self.key}'}, timeout)
        return self.parse(out, model)

    def parse(self, out, model):
        choice = (out.get('choices') or [{}])[0]
        text = (choice.get('message') or {}).get('content') or ''
        u = out.get('usage') or {}
        prompt, done = int(u.get('prompt_tokens') or 0), int(u.get('completion_tokens') or 0)
        cached = int((u.get('prompt_tokens_details') or {}).get('cached_tokens') or 0)
        return Reply(text, usage.cost(out.get('model') or model, prompt - cached, done, cached), prompt, done, 0)


class ClaudeCodeProvider(Provider):
    """`claude -p` single-shot with no tools, for JSON tasks on a Claude plan. Same flags as chiron/llm.py's tool-free calls."""
    engine = 'claude-code'

    def __init__(self, key='', model='haiku', base=''):
        super().__init__(key, model, base)

    def _ask(self, system, messages, model, images, max_tokens, json_mode, timeout):
        claude = os.environ.get('CHIRON_CLAUDE') or shutil.which('claude') or os.path.join(paths.HOME, '.local/bin/claude')
        if not os.path.exists(claude) and not shutil.which(claude): raise ProviderError('missing', 'Claude Code is not installed')
        if json_mode: system += '\nReply with one JSON object only, no prose, no code fences.'
        text = '\n\n'.join(m['content'] if isinstance(m['content'], str) else json.dumps(m['content']) for m in messages)
        content = [{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': _jpeg(i)}} for i in images] + [{'type': 'text', 'text': text}]
        payload = json.dumps({'type': 'user', 'message': {'role': 'user', 'content': content}}) + '\n'
        try:
            r = subprocess.run([claude, '-p', '--model', model, '--effort', 'low', '--system-prompt', system, '--tools', '',
                                '--setting-sources', '', '--settings', '{"disableAllHooks":true}', '--strict-mcp-config',
                                '--mcp-config', '{"mcpServers":{}}', '--disable-slash-commands', '--no-session-persistence',
                                '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose'],
                               input=payload, capture_output=True, text=True, timeout=timeout, cwd=tempfile.gettempdir(), env=claude_env())
        except subprocess.TimeoutExpired:
            raise ProviderError('offline', 'Claude Code took too long')
        except OSError as e:
            raise ProviderError('missing', str(e))
        rows = []
        for line in r.stdout.splitlines():
            try: rows.append(json.loads(line))
            except ValueError: pass
        result = next((row for row in reversed(rows) if isinstance(row, dict) and row.get('type') == 'result'), None)
        if not result or result.get('is_error') or r.returncode:
            detail = (result or {}).get('result') or r.stderr[-300:]
            raise ProviderError('rejected' if 'login' in str(detail).lower() or 'auth' in str(detail).lower() else 'server', str(detail))
        u = result.get('usage') or {}
        tokens_in = sum(int(u.get(k) or 0) for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
        return Reply(str(result.get('result') or ''), float(result.get('total_cost_usd') or 0), tokens_in, int(u.get('output_tokens') or 0), 0)


def brain():
    kind = paths.pref('brain', '')
    if kind in KINDS: return kind
    return 'custom' if str(paths.pref('apiBase', '')).strip() else 'claude-code'   # same rule as chiron.py's brain_kind()


def claude_env(kind=None):
    """Env for any `claude` run: an Anthropic-key brain hands its Keychain key to Claude Code (billed per use);
    otherwise the key is dropped so Claude Code uses the signed-in plan."""
    env = dict(os.environ)
    if (kind or brain()) == 'anthropic':
        key = paths.secret('anthropic')
        if key: env['ANTHROPIC_API_KEY'] = key
    else:
        env.pop('ANTHROPIC_API_KEY', None)
    return env


def provider(kind=None, model=None):
    """The configured brain as a single-shot provider."""
    kind = kind or brain()
    if kind == 'anthropic': return AnthropicProvider(paths.secret('anthropic'), model or ANTHROPIC_MODEL)
    if kind == 'openai': return OpenAIProvider(paths.secret('openai'), model or paths.pref('openaiModel', OPENAI_MODEL))
    if kind == 'custom':
        return CustomServerProvider(paths.secret('custom'), model or str(paths.pref('apiModel', '')).strip(), str(paths.pref('apiBase', '')).strip())
    return ClaudeCodeProvider(model=model or 'haiku')


def cheap(model_hint='haiku'):
    """The cheapest Claude for small JSON jobs (Jev fallback): an Anthropic key if saved, else Claude Code's Haiku."""
    key = paths.secret('anthropic')
    return AnthropicProvider(key, ANTHROPIC_MODEL) if key else ClaudeCodeProvider(model=model_hint)
