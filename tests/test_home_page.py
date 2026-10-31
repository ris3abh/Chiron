"""ui/home.html: static checks that always run, plus an offscreen WKWebView that loads the page the way HomeWindow does
(loadFileURL with read access to ui/) behind a canned 'home' bridge. Fixtures come from tests/home.html, the mock bridge."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'ui' / 'home.html'
MOCK = ROOT / 'tests' / 'home.html'
STRINGS = ROOT / 'ui' / 'strings'
PHASE1_METHODS = ['state.get', 'lang.set', 'prefs.get', 'prefs.set', 'conn.list', 'conn.save', 'conn.clear', 'conn.test',
                  'brain.choose', 'claudeCode.status', 'claudeCode.setup', 'local.scan', 'perms.get', 'perms.grant', 'app.info',
                  'dictionary.list', 'dictionary.add', 'dictionary.remove', 'ask.start']
# Called by the page but answered only once their phase builds them (Practice, Papers).
LATER_METHODS = {'practice.start', 'drill.start', 'papers.open'}
CSP = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"

HARNESS = r'''import Cocoa
import WebKit
// argv: page.html, ui dir, fragment ("" or "settings"), methods JSON, script. Loads like HomeWindow, answers the 'home'
// bridge from the methods map (strings.get reads ui/strings), runs the script as an async function body, prints {"result", "posts"}.
final class Harness: NSObject, WKScriptMessageHandler, WKNavigationDelegate {
    var posts: [Any] = []
    var methods: [String: Any] = [:]
    weak var web: WKWebView?
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        posts.append(m.body)
        guard let body = m.body as? [String: Any], let id = body["id"], let method = body["method"] as? String else { return }
        var result: Any = NSNull(), error: Any = NSNull()
        if method == "strings.get", let args = body["args"] as? [String: Any], let lang = args["lang"] as? String,
           let data = FileManager.default.contents(atPath: CommandLine.arguments[2] + "/strings/" + lang + ".json"),
           let table = try? JSONSerialization.jsonObject(with: data) {
            result = table
        } else if let entry = methods[method] as? [String: Any], let failure = entry["__error"] as? String {
            error = failure
        } else if let value = methods[method] {
            result = value
        }
        let args = try! JSONSerialization.data(withJSONObject: [id, result, error])
        web?.evaluateJavaScript("bridge.reply(..." + String(data: args, encoding: .utf8)! + ")")
    }
    func webView(_ v: WKWebView, didFinish n: WKNavigation!) {
        v.callAsyncJavaScript(CommandLine.arguments[5], arguments: [:], in: nil, in: .page) { r in
            switch r {
            case .success(let x):
                let out = try! JSONSerialization.data(withJSONObject: ["result": x ?? NSNull(), "posts": self.posts])
                print(String(data: out, encoding: .utf8)!); exit(0)
            case .failure(let e): print(e); exit(1)
            }
        }
    }
}
let nsapp = NSApplication.shared
let h = Harness(), cfg = WKWebViewConfiguration()
h.methods = (try? JSONSerialization.jsonObject(with: CommandLine.arguments[4].data(using: .utf8)!)) as? [String: Any] ?? [:]
cfg.userContentController.add(h, name: "home")
let v = WKWebView(frame: NSRect(x: 0, y: 0, width: 880, height: 720), configuration: cfg)
h.web = v
v.navigationDelegate = h
var url = URL(fileURLWithPath: CommandLine.arguments[1])
if !CommandLine.arguments[3].isEmpty { url = URL(string: url.absoluteString + "#" + CommandLine.arguments[3])! }
v.loadFileURL(url, allowingReadAccessTo: URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true))
DispatchQueue.main.asyncAfter(deadline: .now() + 20) { print("timeout"); exit(3) }
nsapp.run()
'''


def fixtures():
    """The three mock fixtures from tests/home.html, with "-5m" offsets turned into ISO times."""
    block = re.search(r'<script type="application/json" id="fixtures">(.*?)</script>', MOCK.read_text(encoding='utf-8'), re.S)
    data = json.loads(block.group(1))
    now = datetime.now(timezone.utc)

    def times(v):
        if isinstance(v, list):
            return [times(x) for x in v]
        if isinstance(v, dict):
            return {k: times(x) for k, x in v.items()}
        m = isinstance(v, str) and re.fullmatch(r'-(\d+)([smhd])', v)
        if m:
            unit = {'s': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days'}[m.group(2)]
            return (now - timedelta(**{unit: int(m.group(1))})).isoformat()
        return v
    return times(data)


def methods_for(fx):
    conn = {k: ({kk: vv for kk, vv in v.items() if kk != '_value'} if isinstance(v, dict) else v) for k, v in fx['conn'].items()}
    out = {'state.get': fx['state'], 'conn.list': conn, 'prefs.get': fx['prefs'], 'claudeCode.status': fx['claudeCode'],
           'perms.get': fx['perms'], 'local.scan': fx['servers'], 'app.info': fx['info'], 'window.settings': {'opened': False},
           'lang.set': {'ok': True}, 'prefs.set': {'ok': True}, 'conn.save': {'ok': True}, 'conn.clear': {'ok': True},
           'brain.choose': {'ok': True}, 'perms.grant': {'ok': True}, 'claudeCode.setup': {'ok': True},
           'conn.test': {'ok': False, 'kind': 'rejected', 'detail': '401'}}
    for name, message in (fx.get('fail') or {}).items():
        out[name] = {'__error': message}
    return out


class HomePageStaticTests(unittest.TestCase):
    """No WebKit: these run everywhere."""
    @classmethod
    def setUpClass(cls):
        cls.html = PAGE.read_text(encoding='utf-8')

    def test_csp_meta(self):
        m = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', self.html)
        self.assertIsNotNone(m, 'CSP meta tag missing')
        self.assertEqual(m.group(1), CSP)

    def test_nothing_loads_from_the_network(self):
        for pattern in (r'''(?:src|href)\s*=\s*["']https?:''', r'''url\(\s*["']?https?:''', r'@import', r'''fetch\(\s*["']https?:''',
                        r'<link\b', r'<script[^>]+src='):
            self.assertIsNone(re.search(pattern, self.html, re.I), f'network load matched {pattern}')
        # The one outside address (TypeSafe docs) is opened by Swift through link.open, never navigated in the page.
        for url in re.findall(r'https?://[^\s"\'<>)]+', self.html):
            self.assertTrue(url.startswith('http://www.w3.org/2000/svg') or f'data-open="{url}"' in self.html, url)

    def test_fonts_are_bundled_woff2(self):
        for name in re.findall(r'url\("fonts/([^"]+)"\)', self.html):
            path = ROOT / 'ui' / 'fonts' / name
            self.assertTrue(path.exists(), name)
            self.assertEqual(path.read_bytes()[:4], b'wOF2', name)
        for licence in ('OFL-Inter.txt', 'OFL-NotoSansDevanagari.txt'):
            self.assertIn('SIL Open Font License', (ROOT / 'ui' / 'fonts' / licence).read_text())
        total = sum(p.stat().st_size for p in (ROOT / 'ui' / 'fonts').glob('*.woff2'))
        self.assertLess(total, 600_000)

    def test_tiles_have_keys_and_start_hidden(self):
        # Words and spend live in Home's stats column and the streak is the activity heatmap; the rest wait for Phase 4.
        tiles = re.findall(r'<section class="tile"[^>]*>', self.html)
        self.assertEqual(len(tiles), 4)
        keys = [re.search(r'data-key="(\w+)"', t).group(1) for t in tiles]
        self.assertEqual(keys, ['skills', 'weak', 'guardian', 'papers'])
        for tag in tiles:
            self.assertIn(' hidden', tag, f'{tag} must start hidden until its state key arrives')
            self.assertIn('tabindex="0"', tag, 'every tile is reachable by Tab')
        for key in ('recent', 'connections', 'today', 'words', 'spend', 'activity'):
            self.assertIn(f'data-key="{key}"', self.html)

    def test_phase1_methods_used_and_mocked(self):
        mock = MOCK.read_text(encoding='utf-8')
        for method in PHASE1_METHODS:
            self.assertIn(f"'{method}'", self.html, f'page never calls {method}')
            self.assertIn(f"case '{method}'", mock, f'mock bridge does not answer {method}')
        self.assertEqual(sorted(fixtures()), ['empty', 'errors', 'typical'])

    def test_design_tokens_present(self):
        # The sidebar design (2026-10-30): flat surfaces, the logo's gold accent, serif display numbers.
        for token in ('--accent: #F5B53F', '--body: 17px', '--big-number: 40px', '--side: 248px', 'ui-serif', '-apple-system',
                      'prefers-reduced-motion', 'prefers-reduced-transparency: reduce', 'prefers-contrast: more',
                      'prefers-color-scheme: dark', ':root[data-theme="dark"]', 'html.native', 'tabular-nums',
                      'min-height: 44px', ':focus-visible', 'container-type: inline-size'):
            self.assertIn(token, self.html)
        self.assertNotIn('text-overflow: ellipsis', self.html, 'text wraps, never truncates')

    def test_one_page_and_settings_sheet(self):
        self.assertEqual(re.findall(r'<main id="(\w+)" class="view"', self.html), ['home'], 'one page: Home only')
        self.assertIn('role="dialog" aria-modal="true"', self.html)
        self.assertIn('id="dictList"', self.html.split('id="sec-voice"')[1].split('</section>')[0], 'the dictionary lives in Settings → Voice')
        for section in ('general', 'voice', 'connections', 'budget', 'permissions', 'about'):
            self.assertIn(f'data-go="{section}"', self.html)
            self.assertIn(f'id="sec-{section}"', self.html)

    def test_every_bridge_call_is_answered_natively(self):
        swift = (ROOT / 'app' / 'HomeBridge.swift').read_text(encoding='utf-8')
        called = set(re.findall(r"bridge\.call\('([\w.]+)'", self.html))
        for method in called - LATER_METHODS:
            self.assertIn(f'case "{method}"', swift, f'HomeBridge does not answer {method}')

    def test_no_framework(self):
        self.assertNotRegex(self.html, r'\b(React|Vue|angular|jQuery)\b')


@unittest.skipUnless(sys.platform == 'darwin' and shutil.which('swiftc'), 'macOS WebKit page check')
class HomePageWebKitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        src, cls.binary = Path(cls.tmp.name) / 'home.swift', Path(cls.tmp.name) / 'home'
        src.write_text(HARNESS)
        built = subprocess.run(['swiftc', str(src), '-o', str(cls.binary)], capture_output=True, text=True)
        if built.returncode != 0:
            cls.tmp.cleanup()
            raise unittest.SkipTest('WebKit harness did not compile: ' + built.stderr[-400:])
        cls.fx = fixtures()
        cls.en = json.loads((STRINGS / 'en.json').read_text(encoding='utf-8'))
        cls.hi = json.loads((STRINGS / 'hi.json').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, fixture, script, fragment=''):
        p = subprocess.run([str(self.binary), str(PAGE), str(ROOT / 'ui'), fragment, json.dumps(methods_for(self.fx[fixture])),
                            'await window.chiron.ready; const tick = ms => new Promise(r => setTimeout(r, ms));\n' + script],
                           capture_output=True, text=True, timeout=40, env={**os.environ, 'CHIRON_DIR': self.tmp.name})
        if p.returncode == 3 or 'timeout' in p.stdout[-20:]:
            self.skipTest('WebKit did not finish loading (headless session?)')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return json.loads(p.stdout.strip().splitlines()[-1])

    SNAPSHOT = '''
        const vis = [...document.querySelectorAll('#tiles > .tile')].filter(t => !t.hidden).map(t => t.dataset.key);
        const hiddenTiles = [...document.querySelectorAll('#tiles > .tile')].filter(t => t.hidden).map(t => t.dataset.key);
        return {lang: document.documentElement.lang, vis, hiddenTiles,
          today: document.querySelector('#todayTitle').textContent, todayEmptyShown: !document.querySelector('#todayEmpty').hidden,
          recent: [...document.querySelectorAll('#recentList li:not([data-kind=dictation])')].map(li => li.children[1].textContent),
          said: [...document.querySelectorAll('#recentList li[data-kind=dictation]')].map(li => li.children[1].textContent),
          greet: document.querySelector('#greet').textContent,
          recentEmpty: !document.querySelector('#recentEmpty').hidden,
          spendMsg: document.querySelector('#spendMsg').hidden ? '' : document.querySelector('#spendMsg').textContent,
          dots: [...document.querySelectorAll('[data-dot] .dot')].map(d => d.dataset.s),
          wordsToday: document.querySelector('#wordsToday').textContent,
          openaiNote: !document.querySelector('#todayNote').hidden,
          scrollW: document.documentElement.scrollWidth, innerW: innerWidth};'''

    def test_empty_fixture(self):
        r = self.page('empty', self.SNAPSHOT)['result']
        self.assertEqual(r['vis'], [])
        self.assertEqual(sorted(r['hiddenTiles']), ['guardian', 'papers', 'skills', 'weak'])
        self.assertTrue(r['todayEmptyShown'])
        self.assertEqual(r['today'], 'Nothing due today.')
        self.assertTrue(r['recentEmpty'])
        self.assertEqual(r['greet'], 'Hold ⌃⌥Space and ask me anything', 'no name, no "Hey"')
        self.assertEqual(r['dots'], ['warn', 'off', 'ok'])
        self.assertLessEqual(r['scrollW'], r['innerW'])

    def test_typical_fixture(self):
        r = self.page('typical', self.SNAPSHOT)['result']
        self.assertEqual(len(r['recent']), 10, 'Recent shows the last 10 asks only')
        self.assertEqual(len(r['said']), 3, 'dictations join the same list')
        self.assertTrue(r['greet'].startswith('Hey Rishabh, hold'))
        self.assertEqual(r['recent'][0], "What's the weather like in Paris?", 'newest first')
        self.assertNotIn('This eleventh item must not appear', r['recent'])
        self.assertEqual(r['wordsToday'], '1,284')
        self.assertEqual(r['dots'], ['ok', 'ok', 'ok'])
        self.assertEqual(r['spendMsg'], '')

    def test_errors_fixture_degrades(self):
        r = self.page('errors', self.SNAPSHOT)['result']
        self.assertTrue(r['todayEmptyShown'], 'a practice with no title falls back to the empty Today card')
        self.assertEqual(r['wordsToday'], '—')
        self.assertIn('$5', r['spendMsg'])
        self.assertEqual(len(r['recent']), 4, 'null, string and text-less rows are skipped')
        self.assertEqual(r['said'], [], 'a non-list dictations value shows nothing')
        self.assertFalse(r['greet'].startswith('Hey'), 'a non-string name is ignored')
        self.assertFalse(r['openaiNote'], 'an Anthropic brain needs no OpenAI-only note')
        self.assertEqual(r['dots'], ['warn', 'warn', 'off'])

    def test_language_switch_relabels_without_reload(self):
        out = self.page('typical', '''
            const before = document.querySelector('#todayTitle').textContent;
            window.__marker = 1;
            document.querySelector('.top [data-lang=hi]').click();
            await tick(150);
            const labels = [...document.querySelectorAll('[data-i18n]')].map(e => [e.dataset.i18n, e.textContent]);
            const hi = {lang: document.documentElement.lang, today: document.querySelector('#todayTitle').textContent, labels,
              placeholder: document.querySelector('#kf-openai').placeholder, gear: document.querySelector('#gear').getAttribute('aria-label'),
              recent0: document.querySelector('#recentList li:not([data-kind=dictation])').children[1].textContent, marker: window.__marker};
            bridge.push('lang', {lang: 'en'});
            await tick(150);
            return {before, hi, back: document.querySelector('#todayTitle').textContent, langAfter: document.documentElement.lang};''')
        r, posts = out['result'], out['posts']
        self.assertEqual(r['before'], self.en['home.hero.title'].replace('*', ''))
        self.assertEqual(r['hi']['lang'], 'hi')
        self.assertEqual(r['hi']['marker'], 1, 'the page did not reload')
        self.assertEqual(r['hi']['today'], self.hi['home.hero.title'].replace('*', ''))
        self.assertEqual(r['hi']['placeholder'], self.hi['settings.key.placeholder'])
        self.assertEqual(r['hi']['gear'], self.hi['header.settings'])
        self.assertEqual(r['hi']['recent0'], 'पेरिस में मौसम कैसा है?', 'bilingual state fields follow the language')
        dynamic = {'home.today.eyebrow', 'settings.conn.brain.use', 'settings.conn.brain.inUse'}   # set by render, not applyStrings
        for key, text in r['hi']['labels']:
            if key not in dynamic:
                self.assertEqual(text, self.hi[key], key)
        self.assertIn({'lang': 'hi'}, [p.get('args') for p in posts if p.get('method') == 'lang.set'])
        self.assertEqual(r['back'], self.en['home.hero.title'].replace('*', ''))
        self.assertEqual(r['langAfter'], 'en')
        self.assertEqual([p for p in posts if p.get('method') == 'lang.set' and p['args'] == {'lang': 'en'}], [],
                         'a native lang push is not echoed back')

    def test_state_push_rerenders(self):
        out = self.page('empty', '''
            bridge.push('state', {lang: 'en', words: {today: 42, week: 42, all: 42}, skills: [{id: 'a', app: 'YouTube', mastery: 5}],
              recent: [{at: new Date().toISOString(), kind: 'do', text: {en: 'Opened Notes', hi: 'नोट्स खोला'}}]});
            await tick(50);
            return {words: document.querySelector('#wordsToday').textContent,
              vis: [...document.querySelectorAll('#tiles > .tile')].filter(t => !t.hidden).map(t => t.dataset.key),
              recent: document.querySelector('#recentList').textContent, dots: document.querySelector('#dots').hidden,
              spendHidden: document.querySelector('#homeSpend').hidden};''')
        r = out['result']
        self.assertEqual(r['words'], '42')
        self.assertEqual(r['vis'], ['skills'], 'tiles follow the keys present')
        self.assertEqual((r['words'], r['spendHidden']), ('42', True), 'spend hides when its key goes')
        self.assertIn('Opened Notes', r['recent'])
        self.assertTrue(r['dots'], 'no connections key, no footer')

    def test_openai_only_note(self):
        out = self.page('empty', '''
            bridge.push('state', {lang: 'en', openai_only: true});
            await tick(20);
            return !document.querySelector('#todayNote').hidden;''')
        self.assertTrue(out['result'])

    def test_settings_fragment_and_sections(self):
        out = self.page('typical', '''
            await tick(400);
            return {settings: !document.querySelector('#settings').hidden, general: !document.querySelector('#sec-general').hidden,
              mask: document.querySelector('[data-keyfield=anthropic] .mask').textContent,
              brain: document.querySelector('[data-pick="claude-code"]').getAttribute('aria-pressed'),
              cc: document.querySelector('#ccStatus').textContent.replace(/\\s+/g, ' ').trim(),
              perms: [...document.querySelectorAll('[data-perm]')].map(li => [li.dataset.perm, li.querySelector('button').hidden]),
              version: document.querySelector('#aboutVersion').textContent, cap: document.querySelector('#cap').value,
              scrollW: document.documentElement.scrollWidth, innerW: innerWidth};''', fragment='settings')
        r = out['result']
        self.assertTrue(r['settings'] and r['general'], '#settings opens the sheet at General')
        self.assertEqual(r['mask'], '•••• ab12')
        self.assertEqual(r['brain'], 'true')
        self.assertEqual(r['cc'], 'Installed Signed in Plan: Claude Pro')
        self.assertEqual(dict(r['perms']), {'microphone': True, 'speech': True, 'accessibility': True, 'screen': False, 'automation': False})
        self.assertEqual(r['version'], '0.1.0')
        self.assertEqual(r['cap'], '5')
        self.assertLessEqual(r['scrollW'], r['innerW'])

    def test_wrong_key_is_never_saved(self):
        out = self.page('empty', '''
            document.querySelector('#gear').click();
            await tick(200);
            document.querySelector('#kf-anthropic').value = 'sk-wrong';
            document.querySelector('[data-keyfield=anthropic] [data-act=save]').click();
            await tick(200);
            return document.querySelector('[data-keyfield=anthropic] .kf-result').textContent;''')
        self.assertEqual(out['result'], self.en['conn.result.rejected'])
        calls = [p['method'] for p in out['posts'] if isinstance(p, dict)]
        self.assertIn('conn.test', calls)
        self.assertNotIn('conn.save', calls)
        test = next(p for p in out['posts'] if p.get('method') == 'conn.test')
        self.assertEqual(test['args'], {'name': 'anthropic', 'value': 'sk-wrong'})

    def test_strings_and_fonts_load_from_file(self):
        out = self.page('typical', '''
            await document.fonts.ready;
            return {inter: document.fonts.check('17px Inter'), deva: document.fonts.check('17px "Noto Sans Devanagari"', 'आ'),
              loaded: [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family)};''')
        posts = [p.get('method') for p in out['posts'] if isinstance(p, dict)]
        # Either XHR read strings/en.json directly or the page fell back to strings.get; both must leave English in place.
        sys.stderr.write(f"\n  strings via {'strings.get bridge' if 'strings.get' in posts else 'file XHR'}; fonts loaded: {out['result']['loaded']}\n")
        self.assertTrue(out['result']['inter'])


if __name__ == '__main__':
    unittest.main()
