"""One row per model or Jev call in usage.jsonl, and the month's spend against the cap.

Claude Code asks are already logged by chiron.py's log_turn() in log.jsonl with their cost; they are read from there,
never copied into usage.jsonl, so each dollar counts once."""
import json
import os
import time

from chiron import paths

DEFAULT_CAP = 5.0
_PRICES = None


def prices():
    global _PRICES
    if _PRICES is None:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prices.json')) as f: _PRICES = json.load(f)
        except (OSError, ValueError):
            _PRICES = {}
    return _PRICES


def price_for(model):
    model = str(model or '').lower()
    keys = [k for k in prices() if not k.startswith('_') and model.startswith(k)]
    return prices()[max(keys, key=len)] if keys else None


def cost(model, input_tokens=0, output_tokens=0, cache_read=0, cache_write=0):
    """USD for one call from the price table; 0 for a model it does not list (a local server is free)."""
    p = price_for(model)
    if not p: return 0.0
    usd = (input_tokens * p.get('input', 0) + output_tokens * p.get('output', 0) +
           cache_read * p.get('cache_read', p.get('input', 0)) + cache_write * p.get('cache_write', p.get('input', 0))) / 1e6
    return round(usd, 7)


def record(engine, model, input_tokens=0, output_tokens=0, usd=0.0, purpose='', ms=0, ok=True):
    row = {'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'engine': engine, 'model': model, 'input_tokens': int(input_tokens or 0),
           'output_tokens': int(output_tokens or 0), 'usd': round(float(usd or 0), 7), 'purpose': purpose, 'ms': int(ms or 0), 'ok': bool(ok)}
    try: paths.append_jsonl(paths.USAGE, row)
    except OSError: pass   # a full disk must not fail the ask that already happened
    return row


def _month(at):
    return str(at or '')[:7]


def _claude_code_rows():
    """Final rows of log.jsonl with a cost. Checkpoint rows carry no usd; a turn logged twice keeps its last row."""
    turns, loose = {}, []
    for row in paths.read_jsonl(paths.LOG):
        usd = row.get('usd')
        if not isinstance(usd, (int, float)) or isinstance(usd, bool) or usd <= 0: continue
        (turns.__setitem__(row['id'], row) if row.get('id') else loose.append(row))
    return list(turns.values()) + loose


def month_rows(month=None):
    month = month or time.strftime('%Y-%m')
    rows = [r for r in paths.read_jsonl(paths.USAGE) if _month(r.get('at')) == month and isinstance(r.get('usd'), (int, float))]
    rows += [{'at': r.get('at'), 'engine': 'claude-code', 'model': r.get('model', ''), 'usd': float(r['usd']), 'purpose': 'ask'}
             for r in _claude_code_rows() if _month(r.get('at')) == month]
    return rows


def month_total(month=None):
    return round(sum(max(0.0, r['usd']) for r in month_rows(month)), 5)


def by_engine(month=None):
    out = {}
    for r in month_rows(month):
        engine = str(r.get('engine') or 'other')
        out[engine] = round(out.get(engine, 0.0) + max(0.0, r['usd']), 5)
    return out


def cap():
    try: value = float(paths.pref('cap', DEFAULT_CAP))
    except (TypeError, ValueError): return DEFAULT_CAP
    return min(50.0, max(1.0, value))


def over_cap(month=None):
    """Phase 1 only warns; Phase 5 starts holding back paid features near the cap."""
    return month_total(month) >= cap()
