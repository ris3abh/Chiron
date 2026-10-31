"""Which way an ask goes, after fast() and normalize.py's instant opens have had it. Skill cards are free; everything else takes
one Jev request, which falls back to Haiku with no key. -> {'mode': 'do'|'teach'|'question', 'card', 'slots', 'risky', 'source'}."""
import json
import re

from chiron import jev, normalize, paths, providers, skills

# "chalu karna dikhao": a verb in its -na form with show or tell is "show me how", not "show".
TEACH = re.compile(r"\b(\w+na (dikhao|dikha do|dikhaiye|dikha dijiye|batao|bataiye|sikhao|shikhao)|\w+ ke dikhao|\w+ kar ke dikhao|teach me|teach|show me how|how do i|how can i|how to|sikhao|shikhao|sikha do|shikha do|sikhaiye|shikhaiye|sikhana|shikhana|batao kaise|kaise kare|kaise karte|kaise karna|kaise banate|kaise banaye)\b|सिखाओ|सिखा दो|सिखाइए|कैसे|करना दिखाओ|करके दिखाओ|करना बताओ", re.I)
DO = re.compile(r"\b(just do it|just|do it for me|for me|for you|on your own|kar do|kar dijiye|khud kar|tum kar|aap kar)\b|कर दो|कर दीजिए|खुद कर", re.I)
QUESTION = re.compile(r"^(what|why|who|when|where|which)\b|\b(kya|kyun|kyon|kaun|kab|kahan|hota hai)\b|क्या|क्यों|कौन|कब|कहाँ", re.I)
ACTION = ('open ', 'close ', 'play ', 'show ', 'search ', 'send ', 'type ')
MODES = {'do': 'The person wants Chiron to do something on the Mac for them', 'teach': 'The person wants to be shown or taught how to do something themselves',
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
    task = normalize.repair(task)
    said = normalize.key(task)
    plain = normalize.clean(task)   # the recogniser scatters commas: "Chalu, Karna, Dikhao"
    teach, do = bool(TEACH.search(plain)), bool(DO.search(plain) and not TEACH.search(plain))
    if choose() == 'always-teach' and not do: teach = True
    # 2. A skill card: free. A person who says "just do it" still gets the card's saved way.
    card, slots = skills.find(task, every)
    if card: return {'mode': card_mode(card, teach, do), 'card': card, 'slots': slots, 'risky': False, 'source': 'card'}
    if teach: return {'mode': 'teach', 'card': None, 'slots': {}, 'risky': False, 'source': 'words'}
    if do: return {'mode': 'do', 'card': None, 'slots': {}, 'risky': bool(re.match('send ', said)), 'source': 'words'}
    # A plain question needs no request: free, and the Haiku fallback takes seconds through Claude Code.
    if QUESTION.search(task): return {'mode': 'question', 'card': None, 'slots': {}, 'risky': False, 'source': 'words'}
    # 3 and 4. One request, batched: Jev, or Haiku inside jev.judge() when there is no key or it is down.
    questions = {'route_mode': jev.choice('What does this request want?', MODES),
                 'route_risky': jev.noul('Does this request involve money leaving, a message leaving, something being deleted, or private data being shared?',
                                         'Yes: it pays, buys, books, sends, posts, deletes or shares something', 'No: it only looks, reads, opens or changes a setting')}
    # An instruction is sent as it was said: normalising "chalu karna dikhao" to "show ..." would hide what it means.
    action = said.startswith(ACTION)
    try:
        if action and judge is None and not paths.secret('jev'):   # Haiku takes 8 s here: with no Jev an instruction is simply done
            return {'mode': 'do', 'card': None, 'slots': {}, 'risky': bool(re.match('send ', said)), 'source': 'words'}
        answers = (judge or jev.judge)(json.dumps({'ask': task}, ensure_ascii=False), questions, purpose='route')
    except (jev.JevError, providers.ProviderError, OSError, ValueError):   # neither could answer: the main ask still can
        return {'mode': 'do' if action else 'question', 'card': None, 'slots': {}, 'risky': False, 'source': 'none'}
    mode = answers['route_mode']
    chosen = mode.value if mode.value in MODES and not mode.unsure else 'question'
    if action and chosen == 'question': chosen = 'do'   # an instruction is never a question
    return {'mode': chosen, 'card': None, 'slots': {}, 'risky': answers['route_risky'].value is True, 'source': mode.engine}
