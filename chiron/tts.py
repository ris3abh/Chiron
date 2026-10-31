"""Spoken replies with a cloud voice: Google Cloud Text-to-Speech, Chirp 3 HD first, then WaveNet, then Apple's `say`.

`chiron.py --speak <lang>` reads an answer on stdin, turns it into a spoken version, and plays sentence by sentence while the
rest is fetched, so the first words start after one request. Google's true streaming is gRPC only and this app has no gRPC
client, so "streaming" here is one REST request per sentence. Audio is cached by (text, voice, speed): a repeated caption is free.
Only the words of the reply leave the Mac. Tests never reach the network: `request` is the one place that does."""
import base64
import hashlib
import json
import os
import queue
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

from chiron import i18n, paths, usage

URL = 'https://texttospeech.googleapis.com/v1/text:synthesize'
LOCALES = {'en': 'en-IN', 'hi': 'hi-IN'}
DEFAULT_VOICE = 'Kore'
WAVENET = {'en': 'en-IN-Wavenet-A', 'hi': 'hi-IN-Wavenet-A'}
WORD_LIMIT = 120     # about 50 s of speech: then "Shall I go on?"
CACHE_LIMIT = 200 * 1024 * 1024
PAUSE = 0.35         # seconds between paragraphs
REST = 'tts_rest.json'
REST_LIFE = 300


class TTSError(Exception):
    def __init__(self, kind): super().__init__(kind); self.kind = kind


def price(model):
    """USD per character, from prices.json ("per_char"): the Chirp and WaveNet rates are not per token."""
    entry = usage.price_for(model) or {}
    return float(entry.get('per_char', 0))


# ---- The spoken version ----
EN_ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
EN_TENS = 'zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()
HI_UNDER_100 = ('शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस '
                'तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस चालीस इकतालीस बयालीस तैंतालीस चौवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास '
                'पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ साठ इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर '
                'सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उनासी अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी नवासी '
                'नब्बे इक्यानवे बानवे तिरानवे चौरानवे पचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे').split()


def number_en(n):
    if n < 20: return EN_ONES[n]
    if n < 100: return EN_TENS[n // 10] + ('' if n % 10 == 0 else ' ' + EN_ONES[n % 10])
    if n < 1000: return EN_ONES[n // 100] + ' hundred' + ('' if n % 100 == 0 else ' and ' + number_en(n % 100))
    for size, word in ((10 ** 7, 'crore'), (10 ** 5, 'lakh'), (1000, 'thousand')):
        if n >= size: return number_en(n // size) + ' ' + word + ('' if n % size == 0 else ' ' + number_en(n % size))


def number_hi(n):
    if n < 100: return HI_UNDER_100[n]
    for size, word in ((10 ** 7, 'करोड़'), (10 ** 5, 'लाख'), (1000, 'हज़ार'), (100, 'सौ')):
        if n >= size: return number_hi(n // size) + ' ' + word + ('' if n % size == 0 else ' ' + number_hi(n % size))


def number(n, lang):
    return number_hi(n) if lang == 'hi' else number_en(n)


def say_digits(text, lang):
    """Whole numbers up to 99 crore as words; a decimal reads its digits, a time or a long code stays for the voice."""
    point = {'en': 'point', 'hi': 'दशमलव'}[lang]
    def whole(m):
        raw = m[0].replace(',', '')
        return number(int(raw), lang) if len(raw) < 10 and (raw == '0' or raw[0] != '0') else m[0]
    def decimal(m):
        return number(int(m[1].replace(',', '')), lang) + f' {point} ' + ' '.join(number(int(d), lang) for d in m[2])
    text = re.sub(r'(?<![\w:.])(\d[\d,]*)\.(\d{1,3})(?![\w:])', decimal, text)
    return re.sub(r'(?<![\w:.])\d[\d,]*(?![\w:]|\.\d)', whole, text)


SYMBOLS = {'en': {'%': ' percent', '&': ' and ', '+': ' plus ', '=': ' equals ', '@': ' at ', '₹': ' rupees ', '$': ' dollars ', '→': ' then ', '×': ' times '},
           'hi': {'%': ' प्रतिशत', '&': ' और ', '+': ' जमा ', '=': ' बराबर ', '@': ' एट ', '₹': ' रुपये ', '$': ' डॉलर ', '→': ' फिर ', '×': ' गुना '}}


def clean_markdown(text):
    text = re.sub(r'```.*?```', ' ', str(text), flags=re.S)
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', ' ', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'https?://\S+', ' ', text)
    text = re.sub(r'^\s{0,3}#{1,6}\s*', '', text, flags=re.M)
    text = re.sub(r'^\s*(?:[-*•]|\d+[.)])\s+', '', text, flags=re.M)
    text = re.sub(r'^\s*>\s?', '', text, flags=re.M)
    return re.sub(r'[*_`~|]+', '', text)


def spoken_version(text, lang='en'):
    """Paragraphs of plain speech: no Markdown, symbols and numbers as words."""
    text = clean_markdown(text).replace(' ', '\n')
    money = {'en': lambda m: f"{m[2]} {'rupees' if m[1] in '₹' else 'dollars'}", 'hi': lambda m: f"{m[2]} {'रुपये' if m[1] in '₹' else 'डॉलर'}"}[lang]
    text = re.sub(r'([₹$])\s?(\d[\d,.]*\d|\d)', money, text)
    for symbol, word in SYMBOLS[lang].items(): text = text.replace(symbol, word)
    text = say_digits(text, lang)
    paragraphs = [' '.join(p.split()) for p in re.split(r'\n\s*\n|\n(?=\S)', text)]
    return [p for p in paragraphs if re.search(r'\w', p)]


def sentences(paragraph):
    """Splits on ., !, ? and the danda; a long sentence breaks at a comma so the first audio comes back quickly."""
    parts = [s.strip() for s in re.split(r'(?<=[.!?।])\s+', paragraph) if s.strip()]
    out = []
    for s in parts:
        while len(s) > 220:
            cut = max(s.rfind(', ', 0, 220), s.rfind(' ', 0, 220))
            if cut < 40: break
            out.append(s[:cut + 1].strip()); s = s[cut + 1:].strip()
        out.append(s)
    return out


def script(text, lang='en', limit=WORD_LIMIT):
    """(items to speak, the words left over). An item is (sentence, ends a paragraph). Stops at a sentence end past `limit` words."""
    items, left, count = [], [], 0
    for paragraph in spoken_version(text, lang):
        said = sentences(paragraph)
        for i, s in enumerate(said):
            if count >= limit: left.append(s); continue
            items.append((s, i == len(said) - 1)); count += len(s.split())
    return items, ' '.join(left)


# ---- Google ----
def request(body, key):
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': key})
    try:
        with urllib.request.urlopen(req, timeout=8) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        raise TTSError('rejected' if e.code in (401, 403) else 'voice' if e.code in (400, 404) else 'server')
    except (OSError, ValueError):
        raise TTSError('offline')


def voice_name(lang, voice):
    return f'{LOCALES[lang]}-Chirp3-HD-{voice or DEFAULT_VOICE}'


def rate(speed):
    try: return max(0.25, min(2.0, float(speed)))
    except (TypeError, ValueError): return 0.85


def synthesize(text, lang, name, speed, key):
    """MP3 bytes. Chirp reads [pause] from `markup`, and that field is its alone."""
    field = {'markup': text} if 'Chirp' in name else {'text': text.replace('[pause]', ' ')}
    body = {'input': field, 'voice': {'languageCode': LOCALES[lang], 'name': name}, 'audioConfig': {'audioEncoding': 'MP3', 'speakingRate': rate(speed)}}
    audio = request(body, key).get('audioContent')
    if not audio: raise TTSError('server')
    return base64.b64decode(audio)


def cache_path(text, name, speed):
    digest = hashlib.sha256(f'{text}\0{name}\0{rate(speed):.2f}'.encode()).hexdigest()
    return paths.path(os.path.join('tts-cache', digest + '.mp3'))


def prune():
    folder = paths.path('tts-cache')
    try: files = sorted((e for e in os.scandir(folder) if e.is_file()), key=lambda e: e.stat().st_mtime)
    except OSError: return
    total = sum(e.stat().st_size for e in files)
    for e in files:
        if total <= CACHE_LIMIT: break
        total -= e.stat().st_size
        try: os.remove(e.path)
        except OSError: pass


def audio_for(text, lang, voice, speed, key):
    """A file path for this sentence, from the cache or Google: Chirp, then WaveNet. None sends the caller to Apple's voice."""
    for name in (voice_name(lang, voice), WAVENET[lang]):
        path = cache_path(text, name, speed)
        if os.path.exists(path):
            os.utime(path); return path
        if usage.over_cap(): return None   # cached audio is free; new audio stops at the cap
        started = time.monotonic()
        try: data = synthesize(text, lang, name, speed, key)
        except TTSError as e:
            if e.kind == 'voice' and name != WAVENET[lang]: continue
            return None
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
        with os.fdopen(fd, 'wb') as f: f.write(data)
        os.replace(tmp, path)
        model = 'chirp3-hd' if 'Chirp' in name else 'wavenet'
        usage.record('google-tts', model, usd=len(text) * price(model), purpose='speak', ms=int((time.monotonic() - started) * 1000), chars=len(text))
        return path
    return None


# ---- Speaking ----
def fallback(words, arguments):
    """Apple's on-device voice, with the voice and speed Swift chose."""
    return subprocess.Popen(['/usr/bin/say', *arguments, '--', words])


def speak(text, lang, voice=None, speed=0.85, key=None, say_args=(), player='/usr/bin/afplay'):
    """Plays the reply. Fetching runs ahead on a thread, so the first sentence starts while the rest arrives."""
    key = paths.secret('google') if key is None else key
    items, left = script(text, lang)
    if not items: return 0
    if left:
        paths.private_json(REST, {'at': time.time(), 'lang': lang, 'text': left})
        items.append((i18n.t('tts.goOn', lang), True))
    else:
        clear_rest()
    current = [None]
    def stop(*_):
        if current[0]:
            try: current[0].terminate()
            except OSError: pass
        os._exit(0)
    signal.signal(signal.SIGTERM, stop)   # the talk key and Esc end this process: the sound must end with it
    ready = queue.Queue(maxsize=3)
    def fetch():
        for sentence, end in items:
            ready.put((sentence, end, audio_for(sentence, lang, voice, speed, key) if key else None))
        ready.put(None)
    threading.Thread(target=fetch, daemon=True).start()
    spoken = 0
    while True:
        got = ready.get()
        if got is None: return spoken
        sentence, end, path = got
        current[0] = subprocess.Popen([player, path]) if path else fallback(sentence, say_args)
        current[0].wait(); current[0] = None; spoken += 1
        if end: time.sleep(PAUSE)


def pending_rest():
    """The words after "Shall I go on?", if the question is recent."""
    rest = paths.read_json(REST, {})
    return rest if isinstance(rest, dict) and rest.get('text') and time.time() - float(rest.get('at') or 0) < REST_LIFE else None


def clear_rest():
    try: os.remove(paths.path(REST))
    except OSError: pass


def test(key):
    """Settings → Test: one short word at full price, cached like any other."""
    started = time.monotonic()
    name, text = voice_name('en', DEFAULT_VOICE), 'OK'
    synthesize(text, 'en', name, 1.0, key)
    usd = len(text) * price('chirp3-hd')
    usage.record('google-tts', 'chirp3-hd', usd=usd, purpose='test', chars=len(text))
    return {'ok': True, 'ms': int((time.monotonic() - started) * 1000), 'usd': usd}


def main(args):
    """--speak <lang> [voice] [speed]: answer on stdin; CHIRON_SAY_ARGS holds Apple's arguments for the fallback."""
    lang = args[0] if args and args[0] in LOCALES else i18n.lang()
    voice = args[1] if len(args) > 1 and args[1] else None
    speed = args[2] if len(args) > 2 else 0.85
    try: say_args = json.loads(os.environ.get('CHIRON_SAY_ARGS') or '[]')
    except ValueError: say_args = []
    speak(sys.stdin.read(), lang, voice, speed, say_args=[str(a) for a in say_args])
