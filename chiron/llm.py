"""One tool-free Claude Code call: a fixed system prompt, one request, the text back. Dictation cleanup reuses it, and so will lessons and papers.

chiron.py runs as __main__ (tests load it as `brain`), so this module cannot import it by name. chiron.py calls
bind(sys.modules[__name__]) when it loads, and these functions look up main_model(), server(), log_turn, stop_claude
and DIR on it at call time, so a test that patches brain.server or brain.DIR is seen here too.
"""
import atexit
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

B = None   # the brain module (chiron.py), set by bind()


def bind(module):
    global B
    B = module


def llm_process(system, model=None):
    """`claude -p` with no tools, hooks, MCP servers, slash commands or saved session, waiting for one stream-json request."""
    with tempfile.TemporaryFile(mode='w+') as errors:
        return subprocess.Popen(['claude', '-p', '--model', model or B.main_model(), '--effort', 'low', '--system-prompt', system,
                                 '--tools', '', '--setting-sources', '', '--settings', '{"disableAllHooks":true}',
                                 '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}', '--disable-slash-commands',
                                 '--no-session-persistence', '--input-format', 'stream-json', '--output-format', 'stream-json', '--verbose',
                                 '--include-partial-messages'],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, text=True,
                                cwd=tempfile.gettempdir(), start_new_session=True, env=B.claude_env())


def llm_payload(request, image=None):
    """One stream-json user message: an optional base64 JPEG, then the request text."""
    content = ([{'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': image}}] if image else []) + [{'type': 'text', 'text': request}]
    return json.dumps({'type': 'user', 'message': {'role': 'user', 'content': content}}) + '\n'


def llm_call(system, request, model=None, label='Chiron'):
    """Run one request to the end (45 s cap) -> (text, {secs, usd, usage, modelUsage}). The cost goes to log.jsonl under label."""
    started = time.monotonic()
    p = llm_process(system) if model is None else llm_process(system, model)
    atexit.register(B.stop_claude, p)
    signal.signal(signal.SIGTERM, lambda *_: (B.stop_claude(p), sys.exit(0)))
    try:
        out, err = p.communicate(llm_payload(request), timeout=45)
        if p.returncode:
            raise RuntimeError('Could not answer. Check Claude in Settings.')
        results = [json.loads(line) for line in out.splitlines() if line.strip()]
        result = next((row for row in reversed(results) if row.get('type') == 'result'), {})
        if result.get('is_error'):
            raise RuntimeError('Could not answer. Try again.')
        metrics = {'secs': round(time.monotonic() - started, 3), 'usd': result.get('total_cost_usd', 0),
                   'usage': result.get('usage', {}), 'modelUsage': result.get('modelUsage', {})}
        os.makedirs(B.DIR, exist_ok=True)
        B.log_turn(label, '', time.time() - metrics['secs'], metrics['usd'], model=model or B.main_model(),
                   attempt_usage=[{k: metrics[k] for k in ('usage', 'modelUsage') if metrics[k]}])
        return result['result'], metrics
    finally:
        B.stop_claude(p)
