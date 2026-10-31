"""The Home page's one state object (`chiron.py --home-state`) and the Python half of its bridge (`--home-do`).

Built only from local files, so opening Home costs nothing. A key a phase has not built yet is left out
and the page hides its tile."""
import time
from datetime import datetime

from chiron import i18n, jev, paths, providers, usage

RECENT = 10


def words():
    d = paths.read_json(paths.DICTATION, {})
    num = lambda k: d.get(k) if isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool) else 0
    today = num('todayWords') if d.get('day') == time.strftime('%Y-%m-%d') else 0
    week_start = time.time() - 7 * 86400
    history = [h for h in d.get('history', []) if isinstance(h, dict)] if isinstance(d.get('history'), list) else []
    # History is kept only when the user allows it; without it, a week can't be counted, so it falls back to today.
    week = sum(len(str(h.get('text', '')).split()) for h in history if isinstance(h.get('timestamp'), (int, float)) and h['timestamp'] >= week_start)
    total = int(num('words'))
    return {'today': int(today), 'week': int(max(week, today)), 'all': total, 'minutes_saved': int(num('seconds') // 60),
            'langs': {'en': total, 'hi': 0}}   # per-language counts arrive with the Hindi speech path (Phase 2)


def kind(row):
    if row.get('model') == 'instant' or row.get('path') == 'instant': return 'do'
    return 'ask'


def recent():
    turns = {}
    for row in paths.read_jsonl(paths.LOG):
        if not row.get('task') or 'reply' not in row: continue   # checkpoint rows are partial
        key = row.get('id') or f"{row.get('at')}|{row.get('task')}"
        turns[key] = row
    rows = sorted(turns.values(), key=lambda r: str(r.get('at', '')))[-RECENT:][::-1]
    out = []
    for r in rows:
        try: at = datetime.strptime(str(r['at'])[:19], '%Y-%m-%d %H:%M:%S').astimezone().isoformat(timespec='seconds')
        except ValueError: at = str(r.get('at'))
        text = ' '.join(str(r['task']).split())[:140]
        out.append({'at': at, 'kind': kind(r), 'text': {'en': text, 'hi': text}, 'usd': r.get('usd') or 0,
                    'ok': r.get('status', 'completed') == 'completed'})
    return out


def connections():
    """Last known health per connection, cached by the Test buttons and status checks; never probed here."""
    saved = paths.read_json(paths.CONNECTIONS, {})
    brain = providers.brain()
    entry = lambda name: saved.get(name) if isinstance(saved.get(name), dict) else {}
    return {'brain': {'kind': brain, 'ok': bool(entry(brain).get('ok', brain == 'claude-code' and entry('claude-code').get('ok', True)))},
            'jev': {'ok': bool(entry('jev').get('ok', False)), 'fallback': not entry('jev').get('ok', False)},
            'speech': {'engine': 'apple', 'ok': True}}


def state():
    code = i18n.lang()
    return {
        'lang': code,
        'today': {'kind': 'none'},   # Practice fills this from Phase 4
        'words': words(),
        'spend': {'month_usd': usage.month_total(), 'cap_usd': usage.cap(), 'by_engine': usage.by_engine(), 'over': usage.over_cap()},
        'recent': recent(),
        'connections': connections(),
        'openai_only': providers.brain() == 'openai',
    }


def remember(name, result):
    saved = paths.read_json(paths.CONNECTIONS, {})
    saved[name] = {'ok': bool(result.get('ok')), 'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'ms': result.get('ms', 0)}
    try: paths.private_json(paths.CONNECTIONS, saved)
    except OSError: pass


ERRORS = {'rejected': 'conn.result.rejected', 'offline': 'conn.result.offline', 'server': 'conn.result.server',
          'nokey': 'conn.result.nokey', 'missing': 'conn.result.missing', 'retry': 'conn.result.offline'}


def test(name, value=None):
    """Settings → Test. value is a key typed but not yet saved: it is checked first, and Swift saves it only on ok."""
    started = time.monotonic()
    try:
        if name == 'jev':
            key = value if value is not None else paths.secret('jev')
            if not key: raise jev.JevError('nokey')
            r = jev.ping(key, str(paths.pref('jevBase', '') or jev.BASE).strip().rstrip('/'))
            result = {'ok': r['ok'], 'detail': i18n.t('conn.result.ok'), 'ms': r['ms'], 'usd': 0.0}
        elif name in ('anthropic', 'openai', 'custom'):
            p = providers.provider(name)
            if value is not None: p.key = value
            reply = p.ask('Reply with the single word OK.', 'Test', max_tokens=5, purpose='test', timeout=20)
            result = {'ok': True, 'detail': i18n.t('conn.result.ok'), 'ms': reply.ms, 'usd': reply.usd}
        elif name == 'claude-code':
            reply = providers.ClaudeCodeProvider().ask('Reply with the single word OK.', 'Test', max_tokens=5, purpose='test', timeout=60)
            result = {'ok': True, 'detail': i18n.t('conn.result.ok'), 'ms': reply.ms, 'usd': reply.usd}
        else:
            return {'ok': False, 'detail': i18n.t('conn.result.server'), 'ms': 0, 'usd': 0.0}
    except (providers.ProviderError, jev.JevError) as e:
        result = {'ok': False, 'detail': i18n.t(ERRORS.get(e.kind, 'conn.result.server')), 'ms': int((time.monotonic() - started) * 1000), 'usd': 0.0,
                  'kind': e.kind}
    if value is None or result['ok']: remember(name, result)
    return result


def do(method, args):
    """Bridge methods whose answer lives in Python. Native ones (Keychain, permissions, windows) stay in Swift."""
    args = args if isinstance(args, dict) else {}
    if method == 'state.get': return state()
    if method == 'conn.test': return test(str(args.get('name', '')), args.get('value'))
    if method == 'usage.month': return {'month_usd': usage.month_total(), 'cap_usd': usage.cap(), 'by_engine': usage.by_engine()}
    raise KeyError(method)

