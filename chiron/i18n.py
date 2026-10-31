"""Spoken and printed lines in the app language, from the same ui/strings files the page uses."""
import json
import os

from chiron import paths

LANGS = ('en', 'hi')
NAMES = {'en': 'English', 'hi': 'Hindi'}   # for the system prompt's "Reply in {lang_name}."
LOCALES = {'en': 'en-IN', 'hi': 'hi-IN'}
_CACHE = {}


def lang():
    value = paths.pref('lang', 'en')
    return value if value in LANGS else 'en'


def strings(code):
    if code not in _CACHE:
        try:
            with open(os.path.join(paths.UI, 'strings', f'{code}.json'), encoding='utf-8') as f: _CACHE[code] = json.load(f)
        except (OSError, ValueError):
            _CACHE[code] = {}
    return _CACHE[code]


def t(key, code=None, **values):
    """The line for key in the given (or current) language; English, then the key itself, if a string is missing."""
    code = code if code in LANGS else lang()
    text = strings(code).get(key) or strings('en').get(key) or key
    try: return text.format(**values) if values else text
    except (KeyError, IndexError, ValueError): return text


def pick(value, code=None):
    """A bilingual {en, hi} field from state or a skill card, in the current language."""
    if not isinstance(value, dict): return str(value or '')
    code = code if code in LANGS else lang()
    return str(value.get(code) or value.get('en') or next(iter(value.values()), ''))
