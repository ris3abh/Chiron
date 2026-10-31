"""Past conversations for Home's Conversations tab, from log.jsonl (every ask, its steps and cost) and chats.json.

A conversation is a run of asks with under five minutes between them, the same window Chiron keeps a chat open for.
Deleting removes the words but keeps each row's cost: log.jsonl is also the spend ledger, so dropping a row would
quietly lower the month's AI spend against the cap."""
import json
import os
import re
from datetime import datetime

from chiron import paths

GAP = 300
ANSWER = 6000
READING = re.compile(r'^(?:Reading|Searching|Looking|Taking a screenshot|Checking|Working on it)')
KEEP = ('id', 'pid', 'at', 'usd', 'attempt_usd', 'status', 'model', 'path', 'secs')   # what a deleted row still needs for the ledger
CHATS = 'chats.json'


def when(at):
    try: return datetime.strptime(str(at)[:19], '%Y-%m-%d %H:%M:%S')
    except ValueError: return None


def asks():
    """One final row per ask, oldest first. Checkpoint rows and deleted rows carry no reply."""
    turns = {}
    for row in paths.read_jsonl(paths.LOG):
        if not row.get('task') or 'reply' not in row: continue
        turns[row.get('id') or f"{row.get('at')}|{row.get('task')}"] = row
    return sorted(turns.items(), key=lambda kv: str(kv[1].get('at', '')))


def outcome(row):
    """did: Chiron acted on the Mac. taught: a lesson (Phase 3). question: it only answered."""
    if row.get('kind') == 'lesson' or row.get('lesson'): return 'taught'
    if row.get('model') == 'instant' or row.get('path') in ('instant', 'shortcut'): return 'did'
    steps = row.get('steps') if isinstance(row.get('steps'), list) else []
    return 'did' if any(isinstance(s, str) and not READING.match(s) for s in steps) else 'question'


def turn(key, row):
    usd = row.get('usd') if isinstance(row.get('usd'), (int, float)) and not isinstance(row.get('usd'), bool) else 0
    steps = row.get('steps') if isinstance(row.get('steps'), list) else []
    return {'key': key, 'at': str(row.get('at', '')), 'q': ' '.join(str(row['task']).split()), 'a': str(row.get('reply') or '')[:ANSWER],
            'steps': [s for s in steps if isinstance(s, str)][:40], 'usd': round(max(0, usd), 5), 'outcome': outcome(row)}


def saved_chats(seen):
    """Older chats that log.jsonl no longer has."""
    chats = paths.read_json(CHATS, [])
    out = []
    for chat in chats if isinstance(chats, list) else []:
        if not isinstance(chat, dict) or not isinstance(chat.get('turns'), list): continue
        at = chat.get('created')
        stamp = datetime.fromtimestamp(at).strftime('%Y-%m-%d %H:%M:%S') if isinstance(at, (int, float)) and not isinstance(at, bool) else ''
        turns = [{'key': '', 'at': stamp, 'q': ' '.join(str(t.get('q', '')).split()), 'a': str(t.get('a') or '')[:ANSWER], 'steps': [], 'usd': 0, 'outcome': 'question'}
                 for t in chat['turns'] if isinstance(t, dict) and str(t.get('q', '')).strip()]
        turns = [t for t in turns if t['q'] not in seen]
        if turns: out.append({'id': 'chat-' + str(chat.get('id')), 'chat': str(chat.get('id')), 'turns': turns})
    return out


def listing():
    """Newest first: {id, at, title, outcome, usd, turns}."""
    groups, last = [], None
    for key, row in asks():
        at = when(row.get('at'))
        if groups and at and last and (at - last).total_seconds() < GAP: groups[-1]['turns'].append(turn(key, row))
        else: groups.append({'id': key, 'turns': [turn(key, row)]})
        last = at or last
    groups += saved_chats({t['q'] for g in groups for t in g['turns']})
    for g in groups:
        kinds = {t['outcome'] for t in g['turns']}
        first = g['turns'][0]
        g.update(at=first['at'], title=first['q'][:160], usd=round(sum(t['usd'] for t in g['turns']), 5),
                 outcome='taught' if 'taught' in kinds else 'did' if 'did' in kinds else 'question')
    return sorted(groups, key=lambda g: g['at'], reverse=True)


def scrub(keys):
    """Blanks the words of these asks in log.jsonl, in place and atomically. Lines that aren't ours are kept as they are."""
    path = paths.path(paths.LOG)
    try:
        with open(path, encoding='utf-8', errors='replace') as f: lines = f.readlines()
    except OSError:
        return
    out = []
    for line in lines:
        try: row = json.loads(line)
        except ValueError: out.append(line); continue
        key = isinstance(row, dict) and (row.get('id') or f"{row.get('at')}|{row.get('task')}")
        if isinstance(row, dict) and (keys is None or key in keys):
            line = json.dumps({**{k: row[k] for k in KEEP if k in row}, 'deleted': True}, ensure_ascii=False) + '\n'
        out.append(line)
    tmp = path + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f: f.writelines(out)
    os.replace(tmp, path)


def delete(conversation_id):
    found = next((g for g in listing() if g['id'] == conversation_id), None)
    if not found: return {'ok': False}
    keys = {t['key'] for t in found['turns'] if t['key']}
    if keys: scrub(keys)
    words = {t['q'] for t in found['turns']}
    chats = paths.read_json(CHATS, [])
    if isinstance(chats, list):
        kept = [c for c in chats if not (isinstance(c, dict) and (str(c.get('id')) == found.get('chat') or
                any(isinstance(t, dict) and ' '.join(str(t.get('q', '')).split()) in words for t in c.get('turns') or [])))]
        if len(kept) != len(chats): paths.private_json(CHATS, kept)
    return {'ok': True}


def clear():
    scrub(None)
    paths.private_json(CHATS, [])
    try: os.remove(paths.path('recent.jsonl'))   # the short memory of the last asks goes too
    except OSError: pass
    return {'ok': True}
