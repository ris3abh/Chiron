"""`chiron.py --speech-eval [folder]`: run recorded asks through the app's own on-device speech and print accuracy per
language and engine. The folder holds audio files and expected.json: [{"file": "hi-01.wav", "lang": "hi", "text": "कैलकुलेटर खोलो"}]."""
import json
import os
import subprocess

from chiron import normalize, paths

FOLDER = os.path.join(paths.ROOT, 'tests', 'audio')


def words(text):
    return normalize.tokens(text)


def distance(a, b):
    """Words to change to turn a into b."""
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        now = [i]
        for j, y in enumerate(b, 1):
            now.append(min(row[j] + 1, now[-1] + 1, row[j - 1] + (x != y)))
        row = now
    return row[-1]


def score(expected, heard):
    """(understood, word accuracy). Understood means the ask reaches the same command, or at most one word in five differs."""
    want, got = words(expected), words(heard)
    if not want: return False, 0.0
    accuracy = max(0.0, 1 - distance(want, got) / len(want))
    return normalize.key(expected) == normalize.key(heard) or accuracy >= 0.8, accuracy


def transcribe(path, lang):
    r = subprocess.run([paths.app_binary(), '--speech-file', path, lang], capture_output=True, text=True, timeout=120)
    try: return json.loads(r.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError): return {'ok': False, 'text': '', 'engine': ''}


def report(folder=None, run=transcribe):
    folder = folder or FOLDER
    manifest = os.path.join(folder, 'expected.json')
    try:
        with open(manifest, encoding='utf-8') as f: cases = [c for c in json.load(f) if isinstance(c, dict)]
    except (OSError, ValueError):
        return f'No recordings yet: add audio and expected.json to {folder}.'
    totals, lines = {}, []
    for c in cases:
        lang = c.get('lang') if c.get('lang') in ('en', 'hi') else 'en'
        r = run(os.path.join(folder, str(c.get('file'))), lang)
        understood, accuracy = score(str(c.get('text', '')), str(r.get('text', '')))
        t = totals.setdefault((lang, r.get('engine') or 'none'), [0, 0, 0.0])
        t[0] += 1; t[1] += understood; t[2] += accuracy
        lines.append(f"{'✓' if understood else '✗'} {c.get('file')}: heard “{r.get('text', '')}”, wanted “{c.get('text', '')}”")
    lines.append('')
    for (lang, engine), (n, ok, acc) in sorted(totals.items()):
        lines.append(f'{lang} / {engine}: {ok} of {n} understood, {acc / n:.0%} of words right')
    return '\n'.join(lines)
