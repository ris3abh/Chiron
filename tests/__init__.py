"""Isolate config before importing any Chiron test module."""
import atexit
import os
import tempfile

config = tempfile.TemporaryDirectory(prefix='chiron-test-config-')
os.environ['CHIRON_DIR'] = config.name
atexit.register(config.cleanup)
# Keys in tests come only from CHIRON_SECRET_<NAME>. Without these, paths.secret() would ask an installed Chiron.app,
# so the suite would read the user's real Keychain once the app is built on this Mac. A test that needs a key sets its own.
for _name in ('anthropic', 'openai', 'jev', 'custom', 'google'):
    os.environ.setdefault('CHIRON_SECRET_' + _name.upper(), '')

# The brain is chiron.py, but the package chiron/ beside it owns the name `chiron`, so tests load the script as `brain`.
import importlib.util as _util, sys as _sys
from pathlib import Path as _Path
ROOT = _Path(__file__).resolve().parents[1]
if 'brain' not in _sys.modules:
    _spec = _util.spec_from_file_location('brain', ROOT / 'chiron.py')
    _brain = _util.module_from_spec(_spec)
    _sys.modules['brain'] = _brain
    _spec.loader.exec_module(_brain)

# The router may call Jev or Haiku, and tests make no network calls: asks go straight to the main path unless a test opts in.
_sys.modules['brain'].real_routed_ask = _sys.modules['brain'].routed_ask
_sys.modules['brain'].routed_ask = lambda task: None

# A test subprocess has no tests/__init__: this line, first in its -c code, loads the brain as `brain` too.
LOAD_BRAIN = ("import importlib.util as _u,sys as _s;_p=_u.spec_from_file_location('brain',%r);brain=_s.modules['brain']=_u.module_from_spec(_p);"
              "_p.loader.exec_module(brain)\n" % str(ROOT / 'chiron.py'))


def app_sources(stage):
    """swiftc arguments for the whole app, as build.sh compiles it: Chiron.swift as main.swift (only main.swift may hold
    top-level code once there are several files) plus app/*.swift, in module Chiron so `Chiron.settings` resolves."""
    import shutil
    main = _Path(stage) / 'main.swift'
    shutil.copy(ROOT / 'Chiron.swift', main)
    return ['-module-name', 'Chiron', str(main), *map(str, sorted((ROOT / 'app').glob('*.swift')))]


def scratch_dir(test):
    """A temp brain.DIR with default prefs for one test, undone at cleanup; returns the folder."""
    from pathlib import Path
    from unittest.mock import patch
    import brain
    root = tempfile.TemporaryDirectory(); test.addCleanup(root.cleanup)
    for p in (patch.object(brain, 'DIR', root.name), patch.object(brain, 'pref', side_effect=lambda k, d: d)):
        p.start(); test.addCleanup(p.stop)
    return Path(root.name)


def run_swift(test, source, timeout=10):
    """Compile Swift source to a temp binary, run it, assert both succeed; returns its stdout."""
    import subprocess, sys
    from pathlib import Path
    if sys.platform != 'darwin': test.skipTest('needs macOS frameworks (Cocoa, AppKit)')
    with tempfile.TemporaryDirectory() as root:
        path, binary = Path(root) / 'test.swift', Path(root) / 'test'
        path.write_text(source)
        result = subprocess.run(['swiftc', str(path), '-o', str(binary)], capture_output=True, text=True)
        test.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=timeout)
        test.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout


# Host guard: window/app-driving tests run only in the VM (run.sh sets CHIRON_VM=1). On a developer's Mac, launching a
# compiled fixture/harness, osascript, `open` or the Chiron binary skips the test instead of taking over the screen.
if not os.environ.get('CHIRON_VM') and not os.environ.get('CHIRON_ALLOW_HOST_UI'):
    import subprocess, unittest
    _popen_init = subprocess.Popen.__init__
    _tmp = os.path.realpath(tempfile.gettempdir())

    def _guarded(self, args, *a, **k):
        first = args if isinstance(args, (str, bytes, os.PathLike)) else (args[0] if args else '')
        exe = os.path.realpath(str(first).split()[0]) if first else ''
        name = os.path.basename(exe)
        if exe.startswith(_tmp) or name in ('osascript', 'open', 'Chiron', 'swift') or '/Chiron.app/' in exe:
            raise unittest.SkipTest(f'host guard: {name} runs only in the VM (run.sh)')
        _popen_init(self, args, *a, **k)
    subprocess.Popen.__init__ = _guarded


# The app runs one ask per process. A test's in-process brain.main() left its ask folder, env and relay thread behind;
# the relay polls time.sleep until the folder goes, so a later test's fake clock or sleep mock counted its naps.
import shutil
import brain
_main = brain.main


def _one_ask(*a, **k):
    env = dict(os.environ)
    try:
        return _main(*a, **k)
    finally:
        state = os.path.dirname(os.environ.get('CHIRON_HANDS_STATE', ''))
        if os.environ.get('CHIRON_HANDS_STATE') != env.get('CHIRON_HANDS_STATE') and os.path.basename(state).startswith('chiron-hands-'):
            shutil.rmtree(state, True)
        os.environ.clear(); os.environ.update(env)
brain.main = _one_ask
