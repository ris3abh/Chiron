"""Skill cards: what a person has learned, the five starters that ship with Chiron, and every attempt at them.

Cards the person earned live in cards.json (`skills.json` stays the base app's instant shortcuts) and never expire. Attempts go
to attempts.jsonl. Matching is free: it runs on normalize.key(), so "यूट्यूब पर भजन लगाओ" finds the card "play {q} on youtube"."""
import glob
import json
import os
import re
import time

from chiron import jev, normalize, paths, providers

CARDS = 'cards.json'
ATTEMPTS = 'attempts.jsonl'
CONCEPTS = ('open-app', 'address-bar', 'search-box', 'click-result', 'scroll', 'back', 'type-text', 'menu', 'save', 'print', 'attach-file', 'close-window')
ORDER = ('youtube-play', 'open-photo', 'whatsapp-photo', 'video-call-link', 'word-open-save-print')   # easiest and most wanted first
STARTER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'starter')
QUIET = {'a', 'an', 'the', 'my', 'me', 'to', 'how', 'do', 'i', 'of', 'on', 'in', 'for', 'some', 'teach', 'show', 'just', 'it', 'please', 'can', 'you', 'sikhao'}
# How independently it went (Product Plan, Mastery and practice schedule).
SCORE_LEVELS = ['Could not do it even with help', 'Needed Chiron to do most steps', 'Needed many hints', 'Needed one or two hints', 'Hesitated but needed no hints', 'Did every step alone and quickly']


def validate(card):
    """The first problem with a card, or ''. Every step needs both languages, a target and something to check."""
    if not isinstance(card, dict): return 'not a card'
    title = card.get('title')
    if not isinstance(title, dict) or not title.get('en') or not title.get('hi'): return 'title needs en and hi'
    if not isinstance(card.get('id'), str) or not re.fullmatch(r'[a-z0-9-]{1,60}', card['id']): return 'bad id'
    steps = card.get('steps')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 12: return 'use 1-12 steps'
    for s in steps:
        if not isinstance(s, dict): return 'bad step'
        say = s.get('say')
        if not isinstance(say, dict) or not str(say.get('en', '')).strip() or not str(say.get('hi', '')).strip(): return 'say needs en and hi'
        if not re.search('[ऀ-ॿ]', str(say['hi'])): return 'say.hi is not Hindi'
        if not str(s.get('expect', '')).strip(): return 'step needs expect'
        if s.get('concept') not in CONCEPTS: return f"unknown concept {s.get('concept')}"
        target = s.get('target')
        if not isinstance(target, dict) or not target.get('app') or not target.get('label'): return 'step needs target app and label'
    return ''


def starters():
    out = {}
    for path in sorted(glob.glob(os.path.join(STARTER, '*.json'))):
        try:
            with open(path, encoding='utf-8') as f: card = json.load(f)
        except (OSError, ValueError):
            continue
        if not validate(card): out[card['id']] = {**card, 'starter': True}
    return out


def mine():
    cards = paths.read_json(CARDS, {})
    return {k: v for k, v in cards.items() if isinstance(v, dict) and not validate(v)} if isinstance(cards, dict) else {}


def cards():
    """Everything Chiron can teach: starters, overlaid by the person's own copies."""
    return {**starters(), **mine()}


def save(card):
    all_cards = paths.read_json(CARDS, {})
    all_cards = all_cards if isinstance(all_cards, dict) else {}
    all_cards[card['id']] = {k: v for k, v in card.items() if k != 'starter'}
    paths.private_json(CARDS, all_cards)


def forms(card):
    """Everything a card answers to, normalised."""
    title = card.get('title') or {}
    return [normalize.key(str(a).replace('{q}', 'slotq')).replace('slotq', '{q}') for a in list(card.get('asked') or []) + [title.get('en', ''), title.get('hi', '')] if a]


def find(ask, every=None):
    """(card, slots) for an exact or close match, or (None, {}). Free: no AI."""
    every = cards() if every is None else every
    said = normalize.key(ask)
    words = {w for w in said.split() if w not in QUIET}
    best, score = None, 0.0
    for card in every.values():
        for form in forms(card):
            if '{q}' in form:
                m = re.fullmatch(re.escape(form).replace(r'\{q\}', '(.+)'), said)
                if m: return card, {'q': m[1]}
                continue
            if said == form: return card, {}
            theirs = {w for w in form.split() if w not in QUIET}
            if not theirs or not words: continue
            overlap = len(words & theirs) / len(words | theirs)
            if overlap > score: best, score = card, overlap
    return (best, {}) if score >= 0.6 else (None, {})


def fill(cmd, slots):
    return re.sub(r'\{(\w+)\}', lambda m: re.sub(r'[^\w-]+', '+', str(slots.get(m[1], ''))).strip('+'), cmd)


def mastery_after(before, score, hints, finished):
    """The Product Plan's table: 1 with many hints, 2 with one or two, 3 alone once, then one level per clean run. Chiron doing it, or stopping, changes nothing."""
    if not finished or score < 1: return before
    if hints > 2: return max(before, 1)
    if hints: return max(before, 2)
    return min(5, max(3, before + 1))


def score_attempt(card, steps):
    """Jev's attempt.score, 0-5. Below its confidence bar, a count of hints stands in."""
    hints = sum(int(s.get('hints') or 0) for s in steps)
    guess = max(0.0, 5.0 - hints)
    try:
        answer = jev.judge(json.dumps({'task': card['title'].get('en'), 'steps': steps}, ensure_ascii=False),
                           {'attempt_score': jev.score('How independently did the learner complete this task?', SCORE_LEVELS)}, purpose='attempt.score')['attempt_score']
    except (jev.JevError, providers.ProviderError, OSError, ValueError):
        return guess
    return guess if answer.unsure else float(answer.value)


def record(card, steps, mode='lesson', finished=True, usd=0.0, score=None):
    """Saves the attempt, and the card with its new mastery. -> the attempt row."""
    before = int(card.get('mastery') or 0)
    hints = sum(int(s.get('hints') or 0) for s in steps)
    score = (score_attempt(card, steps) if finished else 0.0) if score is None else score
    after = mastery_after(before, score, hints, finished)
    row = {'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'skill': card['id'], 'mode': mode, 'finished': bool(finished), 'steps': steps,
           'score': score, 'mastery_before': before, 'mastery_after': after, 'usd': round(float(usd or 0), 6)}
    paths.append_jsonl(ATTEMPTS, row)
    if finished or not card.get('starter'):
        save({**card, 'mastery': after, 'created': card.get('created') or time.strftime('%Y-%m-%d'), 'learned': bool(card.get('learned') or finished)})
    return row


def home():
    """For Home's constellation: the skills someone has actually finished."""
    return [{'id': c['id'], 'app': c.get('app') or '', 'title': c.get('title'), 'mastery': int(c.get('mastery') or 0)} for c in mine().values() if c.get('learned')]


def suggestion(code):
    """Today's starter when nothing is due: the first one not yet learned."""
    done, ready = set(mine()), starters()
    for name in ORDER:
        if name in ready and name not in done:
            return {'kind': 'lesson', 'skill': name, 'title': ready[name]['title']}
    return {'kind': 'none'}
