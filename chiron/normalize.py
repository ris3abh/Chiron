"""Devanagari, romanised Hindi and English requests in one comparable form, so fast(), like() and routing treat
"कैलकुलेटर खोलो", "calculator kholo" and "open calculator" as the same ask. No AI: tables and a little word order."""
import re
import unicodedata

# Words a Hindi recogniser writes in Devanagari, mostly English names; checked before any transliteration.
LEXICON = {
    'कैलकुलेटर': 'calculator', 'नोट्स': 'notes', 'नोट': 'notes', 'सफ़ारी': 'safari', 'सफारी': 'safari', 'क्रोम': 'chrome', 'गूगल': 'google', 'जीमेल': 'gmail',
    'मेल': 'mail', 'व्हाट्सऐप': 'whatsapp', 'व्हाट्सएप': 'whatsapp', 'वॉट्सऐप': 'whatsapp', 'वॉट्सएप': 'whatsapp', 'यूट्यूब': 'youtube', 'कैलेंडर': 'calendar',
    'फ़ोटो': 'photos', 'फोटो': 'photos', 'फ़ोटोज़': 'photos', 'म्यूज़िक': 'music', 'म्यूजिक': 'music', 'फ़ाइंडर': 'finder', 'फाइंडर': 'finder', 'मैसेज': 'messages',
    'मैसेजेस': 'messages', 'सेटिंग्स': 'settings', 'सेटिंग': 'settings', 'फ़ेसटाइम': 'facetime', 'फेसटाइम': 'facetime', 'मैप्स': 'maps', 'मैप': 'maps', 'क्लॉक': 'clock',
    'घड़ी': 'clock', 'रिमाइंडर': 'reminders', 'रिमाइंडर्स': 'reminders', 'ज़ूम': 'zoom', 'जूम': 'zoom', 'वर्ड': 'word', 'एक्सेल': 'excel', 'टर्मिनल': 'terminal',
    'न्यूज़': 'news', 'न्यूज': 'news', 'समाचार': 'news', 'गाने': 'songs', 'गाना': 'song', 'भजन': 'bhajan', 'मौसम': 'weather', 'फ़िल्म': 'movie', 'फिल्म': 'movie',
    'ओपन': 'open', 'क्लोज़': 'close', 'क्लोज': 'close', 'प्ले': 'play', 'सर्च': 'search', 'टाइप': 'type', 'सेंड': 'send', 'शो': 'show',
    'कृपया': 'kripya', 'ज़रा': 'zara', 'जरा': 'zara', 'जी': 'ji', 'थोड़ा': 'thoda', 'को': 'ko', 'पे': 'pe', 'पर': 'par', 'में': 'mein', 'मे': 'mein',
    'खोलो': 'kholo', 'खोलिए': 'kholiye', 'खोलिये': 'kholiye', 'खोल': 'khol', 'दो': 'do', 'दीजिए': 'dijiye', 'दीजिये': 'dijiye', 'बंद': 'band', 'बन्द': 'band', 'करो': 'karo', 'कर': 'kar', 'करना': 'karna', 'के': 'ke', 'बताओ': 'batao', 'बताइए': 'bataiye', 'करिए': 'kijiye',
    'कीजिए': 'kijiye', 'कीजिये': 'kijiye', 'चालू': 'chalu', 'बजाओ': 'bajao', 'बजा': 'baja', 'चलाओ': 'chalao', 'चला': 'chala', 'लगाओ': 'lagao', 'लगा': 'laga', 'सुनाओ': 'sunao', 'दिखाओ': 'dikhao',
    'दिखा': 'dikha', 'दिखाइए': 'dikhaiye', 'ढूंढो': 'dhundo', 'ढूँढो': 'dhundo', 'ढूंढ़ो': 'dhundo', 'खोजो': 'khojo', 'भेजो': 'bhejo', 'भेज': 'bhej', 'लिखो': 'likho', 'लिख': 'likh',
    'फिर': 'phir', 'से': 'se', 'बोलो': 'bolo', 'दोबारा': 'dobara', 'दुबारा': 'dobara',
}
# Apple's hi-IN engine writes romanised Hindi ("notes band karo"), so these meet the same words the lexicon gives.
ROMAN = {'photo': 'photos', 'foto': 'photos', 'mausam': 'weather', 'samachar': 'news', 'gana': 'song', 'gaana': 'song', 'gane': 'songs', 'gaane': 'songs', 'film': 'movie', 'filmein': 'movies'}
FILLER = {'please', 'kripya', 'zara', 'jara', 'ji', 'thoda', 'ko', 'kindly', 'bhai', 'batao', 'batav', 'bataiye', 'na', 'tu', 'zaroor'}
LOCATIVE = {'pe', 'par', 'mein', 'me', 'main'}
# Longest first, so "band kar do" wins over "band".
VERBS = {
    'open': ('khol ke', 'khol kar', 'khol do', 'khol dijiye', 'kholo', 'kholiye', 'kholna', 'khol', 'open karo', 'open kar do', 'open kijiye', 'open karna', 'chalu karna', 'chalu karo', 'chalu kar do', 'chalu kijiye', 'chalu kar', 'open'),
    'close': ('band kar do', 'band kar dijiye', 'band karo', 'band kijiye', 'band karna', 'close karo', 'close kar do', 'close'),
    'play': ('chala ke', 'chala kar', 'chalage', 'chalake', 'laga ke', 'laga kar', 'lagake', 'baja ke', 'baja do', 'bajao', 'chala do', 'chalao', 'chalaiye', 'laga do', 'lagao', 'lagaiye', 'sunao', 'suna do', 'play karo', 'play kar do', 'play karna', 'play'),
    'show': ('dikha do', 'dikhao', 'dikhaiye', 'show karo', 'show'),
    'search': ('search karo', 'search kar do', 'dhundo', 'dhundho', 'dhoondo', 'khojo', 'search'),
    'send': ('bhej do', 'bhejo', 'send karo', 'send kar do', 'send'),
    'type': ('likh do', 'likho', 'type karo', 'type kar do', 'type'),
}
GO_ON = re.compile(r'yes|yes please|go on|continue|carry on|haan|ha|haan ji|aage bolo|aage batao|bolte raho|हाँ|हां|हाँ जी|आगे बोलो|आगे बताओ')
PHRASES = {'phir se bolo': 'say that again', 'fir se bolo': 'say that again', 'dobara bolo': 'say that again', 'wapas bolo': 'say that again',
           'repeat that': 'say that again', 'say it again': 'say that again', 'say that again': 'say that again'}
ALL_VERBS = sorted(((form, verb) for verb, forms in VERBS.items() for form in forms), key=lambda v: -len(v[0]))
# "on" joins what plays or is searched to the place it happens: "youtube pe news lagao" → "play news on youtube".
PLACED = {'play', 'search', 'show'}

CONSONANTS = dict(zip('कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह', 'k kh g gh n ch chh j jh n t th d dh n t th d dh n p ph b bh m y r l v sh sh s h'.split()))
CONSONANTS.update({'ड़': 'r', 'ढ़': 'rh', 'ज़': 'z', 'फ़': 'f', 'क़': 'k', 'ख़': 'kh', 'ग़': 'g'})
VOWELS = {'अ': 'a', 'आ': 'a', 'इ': 'i', 'ई': 'i', 'उ': 'u', 'ऊ': 'u', 'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au', 'ऑ': 'o', 'ऋ': 'ri'}
MATRAS = {'ा': 'a', 'ि': 'i', 'ी': 'i', 'ु': 'u', 'ू': 'u', 'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au', 'ॉ': 'o', 'ृ': 'ri'}
DEVANAGARI = re.compile('[ऀ-ॿ]')


def roman(word):
    """A rough Latin spelling of a Devanagari word: the inherent a is kept between consonants and dropped at the end."""
    word = unicodedata.normalize('NFC', word)
    word = re.sub('(.)़', lambda m: unicodedata.normalize('NFC', m[0]), word)
    out, i = [], 0
    while i < len(word):
        two, c = word[i:i + 2], word[i]
        if two in CONSONANTS: sound, i = CONSONANTS[two], i + 2
        elif c in CONSONANTS: sound, i = CONSONANTS[c], i + 1
        elif c in VOWELS: out.append(VOWELS[c]); i += 1; continue
        elif c in 'ंँ': out.append('n'); i += 1; continue
        else:
            if not 0x0900 <= ord(c) <= 0x097f: out.append(c)
            i += 1; continue
        out.append(sound)
        following = word[i] if i < len(word) else ''
        if following in MATRAS: out.append(MATRAS[following]); i += 1
        elif following == '्': i += 1
        elif following and (following in CONSONANTS or following in VOWELS): out.append('a')
    return ''.join(out)


def skeleton(word):
    """Spelling-proof form for matching names: consonants, with the sounds romanisation blurs folded together."""
    word = roman(word) if DEVANAGARI.search(word) else word.lower()
    word = re.sub(r'[^a-z0-9]', '', word).replace('ph', 'f').replace('v', 'w').replace('sh', 's').replace('ee', 'i')
    word = re.sub(r'(?<=[kgcjtdpb])h', '', word)
    return re.sub(r'(.)\1+', r'\1', word[0] + re.sub('[aeiou]', '', word[1:])) if word else ''


def clean(text):
    """Lower case, no punctuation, one space, Devanagari digits as 0-9."""
    text = unicodedata.normalize('NFC', str(text)).lower().translate({0x0966 + d: str(d) for d in range(10)})
    return ' '.join(re.sub(r'[^\w\sऀ-ॿ.@-]', ' ', text).replace('।', ' ').split()).strip(' .')


def tokens(text, words=()):
    """clean() split into words, Devanagari ones through the lexicon, the household dictionary, then roman()."""
    household = {skeleton(w): w.lower() for w in words if isinstance(w, str) and w.strip() and ' ' not in w.strip()}
    out = []
    for w in clean(text).split():
        if not DEVANAGARI.search(w):
            out.append(ROMAN.get(w, w)); continue
        form = unicodedata.normalize('NFC', w)
        out.append(LEXICON.get(form) or LEXICON.get(unicodedata.normalize('NFD', form)) or household.get(skeleton(form)) or roman(form))
    return out


def key(text, words=()):
    """The one comparable form: "open calculator", "play news on youtube". Unknown requests keep their (romanised) words."""
    t = [w for w in tokens(text, words) if w not in FILLER]
    joined = ' '.join(t)
    if joined in PHRASES: return PHRASES[joined]
    for form, verb in ALL_VERBS:
        parts = form.split()
        if t[-len(parts):] == parts and len(t) > len(parts): rest = t[:-len(parts)]
        elif t[:len(parts)] == parts and len(t) > len(parts): rest = t[len(parts):]
        else: continue
        at = next((i for i, w in enumerate(rest) if w in LOCATIVE), None)
        if verb in PLACED and at and at < len(rest) - 1:
            return f"{verb} {' '.join(rest[at + 1:])} on {' '.join(rest[:at])}"
        return f"{verb} {' '.join(rest)}"
    return joined


def command(text, words=()):
    """What fast() should read: the English form when this was a Hindi or mixed command, else the text untouched,
    so plain English keeps its exact wording for everything downstream."""
    plain = clean(text)
    if not plain: return text
    made = key(text, words)
    hindi = DEVANAGARI.search(text) or set(plain.split()) & HINDI_WORDS or plain in PHRASES
    return made if hindi and made != plain else text


HINDI_WORDS = {w for forms in VERBS.values() for form in forms for w in form.split() if w not in VERBS and w != 'do'} | LOCATIVE | {'ko', 'kripya', 'zara', 'jara'}
HINDI_WORDS |= {'batao', 'batav', 'bataiye', 'karna'}
HINDI_WORDS -= {'main', 'me', 'par', 'close', 'open', 'play', 'show', 'search', 'send', 'type'}   # also English words
