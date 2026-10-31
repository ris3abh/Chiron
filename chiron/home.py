"""The Home page's one state object (`chiron.py --home-state`) and the Python half of its bridge (`--home-do`).

Built only from local files, so opening Home costs nothing. A key a phase has not built yet is left out
and the page hides its tile."""
import os
import pwd
import time
from datetime import datetime, timedelta

from chiron import conversations, i18n, jev, paths, providers, tts, usage

RECENT = 10
ACTIVITY_DAYS = 112   # 16 weeks: the Insights heatmap


def name():
    """First name for the greeting: what the user told Chiron (me.json), else the Mac account's full name."""
    me = paths.read_json('me.json', {})
    me = me if isinstance(me, dict) else {}
    found = me.get('name') if isinstance(me.get('name'), str) else ''
    facts = [f for f in me.get('facts', []) if isinstance(f, dict)] if isinstance(me.get('facts'), list) else []
    for source in ('you', 'contacts', 'mail', 'learned'):   # same priority as the native profileName()
        hit = next((f.get('value') for f in facts if f.get('category') == 'basics' and str(f.get('kind', '')).lower() == 'name'
                    and f.get('source') == source and isinstance(f.get('value'), str)), None)
        if hit: found = hit; break
    if not found:
        try: found = pwd.getpwuid(os.getuid()).pw_gecos.split(',')[0]
        except (KeyError, OSError): found = ''
    return (found.split() or [''])[0][:40]


def history():
    d = paths.read_json(paths.DICTATION, {})
    rows = d.get('history') if isinstance(d, dict) and isinstance(d.get('history'), list) else []
    return [h for h in rows if isinstance(h, dict) and isinstance(h.get('timestamp'), (int, float)) and isinstance(h.get('text'), str)]


def dictations():
    """The latest dictations, newest first, for Home's activity list. Empty when the user turned history off."""
    out = []
    for h in sorted(history(), key=lambda h: h['timestamp'], reverse=True)[:RECENT]:
        text = ' '.join(h['text'].split())[:280]
        if text: out.append({'at': datetime.fromtimestamp(h['timestamp']).astimezone().isoformat(timespec='seconds'),
                             'text': text, 'app': str(h.get('app') or '')[:60]})
    return out


def activity():
    """Asks plus dictations per local day, for the Insights heatmap and streak."""
    start = (datetime.now() - timedelta(days=ACTIVITY_DAYS - 1)).strftime('%Y-%m-%d')
    days, seen = {}, set()
    for row in paths.read_jsonl(paths.LOG):
        if not row.get('task') or 'reply' not in row: continue
        key = row.get('id') or f"{row.get('at')}|{row.get('task')}"
        day = str(row.get('at', ''))[:10]
        if key in seen or day < start or len(day) != 10: continue
        seen.add(key); days[day] = days.get(day, 0) + 1
    for h in history():
        day = datetime.fromtimestamp(h['timestamp']).strftime('%Y-%m-%d')
        if day >= start: days[day] = days.get(day, 0) + 1
    return days


def words():
    d = paths.read_json(paths.DICTATION, {})
    num = lambda k: d.get(k) if isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool) else 0
    today = num('todayWords') if d.get('day') == time.strftime('%Y-%m-%d') else 0
    week_start = time.time() - 7 * 86400
    history = [h for h in d.get('history', []) if isinstance(h, dict)] if isinstance(d.get('history'), list) else []
    # History is kept only when the user allows it; without it, a week can't be counted, so it falls back to today.
    week = sum(len(str(h.get('text', '')).split()) for h in history if isinstance(h.get('timestamp'), (int, float)) and h['timestamp'] >= week_start)
    total = int(num('words'))
    today, week, total = int(today), int(max(week, today)), total
    langs, saved = {'en': total, 'hi': 0}, num('seconds')   # dictation listens in English
    day, start = time.strftime('%Y-%m-%d'), datetime.fromtimestamp(week_start).strftime('%Y-%m-%d %H:%M:%S')
    for row in voice_rows():
        said, at = row['words'], row['at']
        total += said; langs[row['lang']] += said
        if at[:10] == day: today += said
        if at >= start: week += said
        saved += max(0, said / 40 * 60 - row['seconds'])   # the same 40 wpm typing baseline as dictation
    return {'today': today, 'week': week, 'all': total, 'minutes_saved': int(saved // 60), 'langs': langs}


def voice_rows():
    """One row per voice ask from voice.jsonl; a later row with the same id replaces it (an ask marked not understood counts no words)."""
    rows = {}
    for r in paths.read_jsonl(paths.VOICE):
        if not isinstance(r.get('at'), str) or not isinstance(r.get('words'), int) or isinstance(r.get('words'), bool): continue
        seconds = r.get('seconds') if isinstance(r.get('seconds'), (int, float)) and not isinstance(r.get('seconds'), bool) else 0
        rows[r.get('id') or r['at']] = {'at': r['at'], 'words': max(0, r['words']) if r.get('understood', True) else 0,
                                        'seconds': seconds, 'lang': r.get('lang') if r.get('lang') in i18n.LANGS else 'en'}
    return list(rows.values())


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
            # Never tested means never set up: Settings saves a Jev key only after its test passes.
            'jev': {'ok': bool(entry('jev').get('ok', False)), 'missing': not entry('jev'), 'fallback': not entry('jev').get('ok', False)},
            'speech': {'engine': 'apple', 'ok': True}}


def state():
    code = i18n.lang()
    return {
        'lang': code,
        'name': name(),
        'today': {'kind': 'none'},   # Practice fills this from Phase 4
        'words': words(),
        'spend': {'month_usd': usage.month_total(), 'cap_usd': usage.cap(), 'by_engine': usage.by_engine(), 'over': usage.over_cap()},
        'recent': recent(),
        'dictations': dictations(),
        'activity': activity(),
        'connections': connections(),
        'openai_only': providers.brain() == 'openai',
    }


def remember(name, result):
    saved = paths.read_json(paths.CONNECTIONS, {})
    saved[name] = {'ok': bool(result.get('ok')), 'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'ms': result.get('ms', 0)}
    try: paths.private_json(paths.CONNECTIONS, saved)
    except OSError: pass


ERRORS = {'rejected': 'conn.result.rejected', 'offline': 'conn.result.offline', 'server': 'conn.result.server',
          'nokey': 'conn.result.nokey', 'missing': 'conn.result.missing', 'retry': 'conn.result.offline', 'voice': 'conn.result.voice'}


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
        elif name == 'google':
            key = value if value is not None else paths.secret('google')
            if not key: raise jev.JevError('nokey')
            r = tts.test(key)
            result = {'ok': True, 'detail': i18n.t('conn.result.ok'), 'ms': r['ms'], 'usd': r['usd']}
        elif name == 'claude-code':
            reply = providers.ClaudeCodeProvider().ask('Reply with the single word OK.', 'Test', max_tokens=5, purpose='test', timeout=60)
            result = {'ok': True, 'detail': i18n.t('conn.result.ok'), 'ms': reply.ms, 'usd': reply.usd}
        else:
            return {'ok': False, 'detail': i18n.t('conn.result.server'), 'ms': 0, 'usd': 0.0}
    except (providers.ProviderError, jev.JevError, tts.TTSError) as e:
        result = {'ok': False, 'detail': i18n.t(ERRORS.get(e.kind, 'conn.result.server')), 'ms': int((time.monotonic() - started) * 1000), 'usd': 0.0,
                  'kind': e.kind}
    if value is None or result['ok']: remember(name, result)
    return result


def do(method, args):
    """Bridge methods whose answer lives in Python. Native ones (Keychain, permissions, windows) stay in Swift."""
    args = args if isinstance(args, dict) else {}
    if method == 'state.get': return state()
    if method == 'conn.test': return test(str(args.get('name', '')), args.get('value'))
    if method == 'conversations.list': return {'items': conversations.listing()}
    if method == 'conversations.delete': return conversations.delete(str(args.get('id', '')))
    if method == 'conversations.clear': return conversations.clear()
    if method == 'usage.month': return {'month_usd': usage.month_total(), 'cap_usd': usage.cap(), 'by_engine': usage.by_engine()}
    raise KeyError(method)

