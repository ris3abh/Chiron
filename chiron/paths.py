"""Where Chiron keeps its files, and the private-file helpers every module shares."""
import json
import os
import subprocess
import tempfile

HOME = os.path.expanduser('~')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repo, or Contents/Resources once built
UI = os.path.join(ROOT, 'ui')


def folder():
    # Read on every call: tests point CHIRON_DIR at a temp folder after import.
    return os.environ.get('CHIRON_DIR') or os.path.join(HOME, '.config/chiron')


def path(name):
    return os.path.join(folder(), name)


PREFS, LOG, USAGE, DICTATION, CONNECTIONS, VOICE = 'settings.json', 'log.jsonl', 'usage.jsonl', 'dictation.json', 'connections.json', 'voice.jsonl'


def ensure():
    os.makedirs(folder(), mode=0o700, exist_ok=True)
    os.chmod(folder(), 0o700)


def private_json(name_or_path, data):
    """Atomic 0600 write, so a crash never leaves half a file and other Mac accounts never read it."""
    target = name_or_path if os.path.isabs(name_or_path) else path(name_or_path)
    os.makedirs(os.path.dirname(target), mode=0o700, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=os.path.dirname(target), delete=False) as f:
        os.fchmod(f.fileno(), 0o600); json.dump(data, f, ensure_ascii=False); tmp = f.name
    try: os.replace(tmp, target)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def read_json(name, default):
    try:
        with open(path(name)) as f: value = json.load(f)
    except (OSError, ValueError):
        return default
    return value if isinstance(value, type(default)) else default


def append_jsonl(name, row):
    ensure()
    fd = os.open(path(name), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try: os.fchmod(fd, 0o600); os.write(fd, (json.dumps(row, ensure_ascii=False) + '\n').encode())
    finally: os.close(fd)


def read_jsonl(name):
    """Rows of a .jsonl file; a corrupted line (a crash mid-write) is skipped, never fatal."""
    rows = []
    try:
        with open(path(name), encoding='utf-8', errors='replace') as f:
            for line in f:
                try: row = json.loads(line)
                except ValueError: continue
                if isinstance(row, dict): rows.append(row)
    except OSError:
        pass
    return rows


def pref(key, default):
    value = read_json(PREFS, {}).get(key, default)
    return default if value is None else value


def app_binary():
    return os.environ.get('CHIRON_APP') or os.path.join(HOME, 'Applications/Chiron.app/Contents/MacOS/Chiron')


SECRETS = ('anthropic', 'openai', 'jev', 'custom', 'google')


def secret(name):
    """A key from the Keychain, through the native app (`Chiron --secret get <name>`); keys never live in files.
    CHIRON_SECRET_<NAME> overrides it, for tests and for CI runs without a Keychain."""
    if name not in SECRETS: return ''
    override = os.environ.get('CHIRON_SECRET_' + name.upper())
    if override is not None: return override.strip()
    if not os.path.exists(app_binary()): return ''   # not built yet (tests, CI): there is no Keychain helper to ask
    try:
        # macOS re-checks a freshly built app on its first run (8 s measured): a short limit here reads as "no key" and silently loses Jev.
        r = subprocess.run([app_binary(), '--secret', 'get', name], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return ''
    return r.stdout.strip() if r.returncode == 0 else ''
