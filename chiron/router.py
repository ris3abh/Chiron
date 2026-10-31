"""Which way an ask goes, after fast() and normalize.py's instant opens have had it. Skill cards are free; everything else takes
one Jev request, which falls back to Haiku with no key. -> {'mode': 'do'|'teach'|'question', 'card', 'slots', 'risky', 'source'}."""
import json
import re

from chiron import jev, normalize, paths, providers, skills

TEACH = re.compile(r"\b(teach me|teach|show me how|how do i|how can i|how to|sikhao|shikhao|sikha do|shikha do|sikhaiye|shikhaiye|sikhana|shikhana|batao kaise|kaise kare|kaise karte|kaise karna|kaise banate|kaise banaye)\b|सिखाओ|सिखा दो|सिखाइए|कैसे", re.I)
DO = re.compile(r"\b(just do it|just|do it for me|for me|for you|on your own|kar do|kar dijiye|khud kar|tum kar|aap kar)\b|कर दो|कर दीजिए|खुद कर", re.I)
QUESTION = re.compile(r"^(what|why|who|when|where|which)\b|\b(kya|kyun|kyon|kaun|kab|kahan|hota hai)\b|क्या|क्यों|कौन|कब|कहाँ", re.I)
ACTION = ('open ', 'close ', 'play ', 'show ', 'search ', 'send ', 'type ')
MODES = {'do': 'The person wants Chiron to do something on the Mac', 'teach': 'The person wants to learn how to do something',
         'question': 'The person is asking for information, or anything else'}


def choose():
    return str(paths.pref('teachMode', 'teach-unless-known'))


def card_mode(card, teach, do):
    """Mastery 5 or "just do it" does it; a known skill below that teaches. Settings can pin either."""
    pinned = choose()
    if teach: return 'teach'
    if do or pinned == 'always-do' or int(card.get('mastery') or 0) >= 5: return 'do'
    return 'teach'


def route(task, every=None, judge=None):
    said = normalize.key(task)
    teach, do = bool(TEACH.search(task)), bool(DO.search(task) and not TEACH.search(task))
    if choose() == 'always-teach' and not do: teach = True
    # 2. A skill card: free. A person who says "just do it" still gets the card's saved way.
    card, slots = skills.find(task, every)
    if card: return {'mode': card_mode(card, teach, do), 'card': card, 'slots': slots, 'risky': False, 'source': 'card'}
    if teach: return {'mode': 'teach', 'card': None, 'slots': {}, 'risky': False, 'source': 'words'}
    # An instruction fast() couldn't finish ("play bhajan") is still something to do, never a question: no request needed.
    if do or said.startswith(ACTION): return {'mode': 'do', 'card': None, 'slots': {}, 'risky': bool(re.match('send ', said)), 'source': 'words'}
    # A plain question needs no request: free, and the Haiku fallback takes seconds through Claude Code.
    if QUESTION.search(task): return {'mode': 'question', 'card': None, 'slots': {}, 'risky': False, 'source': 'words'}
    # 3 and 4. One request, batched: Jev, or Haiku inside jev.judge() when there is no key or it is down.
    questions = {'route_mode': jev.choice('What does this request want?', MODES),
                 'route_risky': jev.noul('Does this request involve money leaving, a message leaving, something being deleted, or private data being shared?',
                                         'Yes: it pays, buys, books, sends, posts, deletes or shares something', 'No: it only looks, reads, opens or changes a setting')}
    try: answers = (judge or jev.judge)(json.dumps({'ask': said}, ensure_ascii=False), questions, purpose='route')
    except (jev.JevError, providers.ProviderError, OSError, ValueError):   # neither could answer: the main ask still can
        return {'mode': 'question', 'card': None, 'slots': {}, 'risky': False, 'source': 'none'}
    mode = answers['route_mode']
    return {'mode': mode.value if mode.value in MODES and not mode.unsure else 'question', 'card': None, 'slots': {},
            'risky': answers['route_risky'].value is True, 'source': mode.engine}
