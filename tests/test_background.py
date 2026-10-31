"""Background tasks use fake workers; no user apps, windows, or configuration."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import brain
from tests import scratch_dir


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        root = scratch_dir(self)
        for p in [patch.dict(os.environ, {'CHIRON_ASK': str(root)}, clear=True),
                  patch.object(brain, 'WORKED', str(root / 'worked.json')),
                  patch.object(brain, 'wait_commit', return_value=True)]:
            p.start(); self.addCleanup(p.stop)
        self.target = {'pid': 123, 'windowID': '42', 'windowFrame': [0, 0, 300, 200], 'app': 'Notes', 'window': 'Fixture'}

    def gate(self, cmd):
        with patch('sys.stdin', io.StringIO(json.dumps({'tool_input': {'command': cmd}}))), patch('sys.stdout', new_callable=io.StringIO) as out, patch.object(brain, 'preview_app'):
            brain.gate()
        return json.loads(out.getvalue())['hookSpecificOutput']['permissionDecision'] if out.getvalue() else 'allow'

    def test_instant_open_tells_the_focus_guard_it_was_asked(self):
        calls = []
        run = lambda cmd, **_: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, '', '')
        with patch.object(brain, 'LAST', os.path.join(os.environ['CHIRON_ASK'], 'last')), \
             patch.object(brain, 'app_named', return_value='Fixture'), patch.object(brain, 'skills', return_value={}), \
             patch.object(brain, 'pref', side_effect=lambda k, v=None: v), patch.object(brain.subprocess, 'run', side_effect=run):
            for words in ('launch fixture', 'open fixture'):
                calls.clear()
                with self.subTest(words=words):
                    self.assertEqual(brain.fast(words), 'Opened Fixture.')
                    self.assertEqual(calls[-1], ['open', '-a', 'Fixture'])
                    self.assertEqual(calls[:-1], [[brain.APP, '--raise', 'user']] if words.startswith('launch') else [])   # "open" was freed by allow_focus already
            calls.clear()
            with patch.object(brain, 'move_target', return_value=('Fixture', 'left', 'current')), \
                 patch.object(brain, 'place', return_value='Fixture window -> left of Main'):
                self.assertEqual(brain.fast('launch fixture on the left'), 'Fixture: left.')
            self.assertEqual(calls[:2], [[brain.APP, '--raise', 'user'], ['open', '-a', 'Fixture']])   # the inner "open" must not hide that the user asked

    def test_settings_and_tool_hints_never_steer_to_focus(self):
        self.assertIn('System settings: shell, defaults or AppleScript first; else open the pane with --bg', brain.system_prompt(brain.ASK_FIRST))
        self.assertTrue(brain.hands_valid(['click', 'Night Shift…', 'front']) and brain.hands_valid(['click', 'Done', 'near', 'Sheet', 'double', 'front']))
        self.assertFalse(brain.hands_valid(['click', 'Done', 'front', 'front']))
        swift = Path(brain.ME).with_name('Chiron.swift').read_text()
        # --front grants focus for the rest of the ask; a tool reply suggesting it made System Settings stay in front for "is Night Shift on?"
        self.assertNotIn('--front', swift); self.assertNotIn('Bring the window forward', swift)
        self.assertIn('case "front": guard !front', swift)

    def test_recursive_ask_and_unrequested_activation_are_denied(self):
        self.assertEqual(self.gate(f'env -u CHIRON_ASK -u CLAUDECODE python3 {brain.ME} ask again'), 'deny')
        self.assertEqual(self.gate(f'python3 {brain.ME} --wait'), 'deny')
        self.assertEqual(self.gate(f'env -u CHIRON_ASK {brain.ME} ask again'), 'deny')
        self.assertEqual(self.gate(f'cd {os.path.dirname(brain.ME)} && env -u CHIRON_ASK sh chiron.py ask again'), 'deny')   # the sh header makes sh a launcher
        self.assertEqual(self.gate(f'xargs {brain.ME} ask again'), 'deny')
        self.assertEqual(self.gate(f'printf again | xargs {brain.ME} ask'), 'deny')
        self.assertEqual(self.gate(f'echo ready && env {brain.ME} ask again'), 'deny')
        self.assertEqual(self.gate(f'python3 {brain.ME} --hands see Notes'), 'allow')
        self.assertEqual(self.gate(f'A={brain.ME}; $A --front Fixture && $A --hands see Fixture'), 'allow')
        self.assertEqual(self.gate(f'A={brain.ME}; $A ask again'), 'deny')
        self.assertEqual(self.gate('osascript -e \'tell application "Notes" to activate\''), 'deny')
        for separator in (';', '&&', '|', '\n', '\n\n'):
            with self.subTest(separator=separator):
                self.assertEqual(self.gate('true' + separator + 'open -a Fixture'), 'deny')
                self.assertEqual(self.gate('true' + separator + 'open -g -a Fixture'), 'allow')
        self.assertEqual(self.gate('open -a Notes'), 'deny')
        self.assertEqual(self.gate('env open -a Notes'), 'deny')
        self.assertEqual(self.gate('xargs open -a Notes'), 'deny')
        self.assertEqual(self.gate('printf Notes | xargs open -a'), 'deny')
        self.assertEqual(self.gate('xargs open -g -a Notes'), 'allow')
        self.assertEqual(self.gate('open -g -a Notes'), 'allow')
        self.assertEqual(self.gate('echo open'), 'allow')
        self.assertEqual(self.gate('printf open'), 'allow')
        self.assertEqual(self.gate(f'{brain.HANDS} type Field activate'), 'allow')
        self.assertEqual(self.gate(f'{brain.HANDS} type Field chiron.py'), 'allow')
        self.assertFalse(brain.wants_focus('Do not show the window, just tell me whether it is open'))
        self.assertFalse(brain.wants_focus('Do not open Notes; add a note'))
        self.assertFalse(brain.wants_focus("Don't focus Notes"))
        self.assertFalse(brain.wants_focus('Open Notes in the background'))
        brain.save_request(os.environ['CHIRON_ASK'], 'Show Notes')
        self.assertEqual(self.gate('osascript -e \'tell application "Notes" to activate\''), 'allow')
        self.assertEqual(self.gate('printf Notes | xargs open -a'), 'allow')

    def test_one_helper_targets_every_app_and_records_last_window(self):
        with patch.object(brain.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(self.target))) as run:
            for app in ['Spotify', 'Notes', 'Reminders', 'Finder']:
                brain.preview_commands(f'osascript -e \'tell application "{app}" to make new item\'')
                self.assertEqual(run.call_args.args[0], [brain.APP, '--window-target', app, ''])
        self.assertEqual(json.loads(Path(brain.WORKED).read_text())['window'], 'Fixture')
        self.assertEqual(list(Path(os.environ['CHIRON_ASK']).glob('hands-*')), [])   # nothing for the app to show

    def test_background_open_handles_apps_files_and_schemes(self):
        with patch.object(brain, 'front', return_value=('Editor', 'Work')), patch.object(brain, 'osa', return_value='Editor'), patch.object(brain, 'preview_app',return_value=None) as preview, patch.object(brain.time, 'sleep'), patch.object(brain.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'Notes.app')) as run:
            brain.show('Notes', bg=True)
            self.assertEqual(run.call_args.args[0], ['open', '-g', '-a', 'Notes'])
            preview.assert_called_with('Notes', 'open')
            self.assertFalse(any('set frontmost' in str(c) for c in brain.osa.call_args_list))   # Notes stayed behind: nothing to give back
            brain.show('spotify:search:jazz', bg=True)
            self.assertEqual(run.call_args.args[0], ['open', '-g', 'spotify:search:jazz'])
            brain.show(os.environ['CHIRON_ASK'], bg=True)
            self.assertEqual(run.call_args.args[0], ['open', '-g', os.environ['CHIRON_ASK']])


    def test_restore_does_not_interrupt_a_new_unrelated_app(self):
        with patch.object(brain, 'osa', return_value='Editor') as osa:
            brain.restore_focus('Finder', 'make a note', ['tell application "Notes" to make new note'])
            self.assertEqual(osa.call_count, 1)

    def test_restore_ignores_a_window_an_earlier_task_worked_in(self):
        Path(brain.WORKED).write_text(json.dumps({'app': 'Editor', 'window': 'Draft'}))
        started = os.path.getmtime(brain.WORKED)
        for start, calls in ((started + 1, 1), (started, 2)):   # written before this ask began: the user switched there themselves
            with self.subTest(start=start), patch.dict(brain.TURN, {'_started': start}), patch.object(brain, 'osa', return_value='Editor') as osa:
                brain.restore_focus('Finder', 'what time is it', [])
                self.assertEqual(osa.call_count, calls)

    def test_work_mode_covers_non_browser_apps(self):
        for mode in ('back', 'front'):
            with self.subTest(mode=mode), patch.object(brain, 'pref', side_effect=lambda k, d: mode if k == 'workIn' else d), \
                 patch.object(brain, 'osa', return_value='Editor') as osa, patch.object(brain, 'preview_app', return_value={'app': 'Fixture'}), \
                 patch.object(brain, 'keep_behind') as behind, patch.object(brain.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertEqual(brain.show('Fixture', bg=True), 'opened Fixture ' + ('in front' if mode == 'front' else 'in the background'))
                self.assertEqual(run.call_args.args[0], ['open'] + ([] if mode == 'front' else ['-g']) + ['-a', 'Fixture'])
                self.assertEqual(behind.call_count, int(mode == 'back'))
                osa.reset_mock()
                osa.return_value = 'Fixture'
                brain.restore_focus('Editor', 'work in Fixture', ['tell application "Fixture" to work'])
                self.assertEqual(osa.call_count, 0 if mode == 'front' else 2)

    def test_preview_passes_explicit_focus_intent_to_native_apps(self):
        for requested in (False, True):
            with self.subTest(requested=requested), patch.object(brain, 'wants_focus', return_value=requested), \
                 patch.object(brain, 'emit'), patch.object(brain.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(self.target))) as run:
                brain.preview_app('Fixture')
                self.assertEqual(run.call_args.kwargs['env']['CHIRON_FOCUS_REQUESTED'], '1' if requested else '0')

    def test_explicit_focus_is_not_undone_by_the_shared_fallback(self):
        with patch.dict(os.environ, {'CHIRON_REQUEST': 'focus Fixture'}), patch.object(brain, 'osa') as osa:
            brain.keep_behind('Editor', 'Fixture')
            osa.assert_not_called()


    def test_agent_front_stays_background_and_show_respects_user_intent(self):
        with patch.dict(os.environ, {'CHIRON_AGENT': 'fixture'}), patch.object(brain, 'preview_app',return_value=None) as preview, patch.object(brain, 'hands_map', return_value={'description': 'Notes map'}) as mapped, \
             patch.object(brain, 'window_target', return_value=self.target), patch.object(brain, 'look', return_value=[('/fake.jpg', 'Screen 1')]) as looked, \
             patch.object(brain, 'osa') as osa, patch('sys.argv', ['chiron.py', '--front', 'Notes', '--asked']), patch('sys.stdout', new_callable=io.StringIO) as out:
            brain.main()   # the model's --asked never brings an agent forward: only the user's words do
            osa.assert_not_called(); self.assertEqual(out.getvalue().strip(), 'Notes map\nScreen 1: /fake.jpg')
            preview.assert_called_once(); mapped.assert_called_once_with('Notes', target=self.target); looked.assert_called_once_with(cleanup=False, window=self.target)
        with patch.object(brain, 'show') as show, patch('sys.stdout', new_callable=io.StringIO), patch('sys.argv', ['chiron.py', '--show', 'Notes']):
            brain.main(); show.assert_called_with('Notes', True)
            brain.save_request(os.environ['CHIRON_ASK'], 'Open Notes')
            brain.main(); show.assert_called_with('Notes', False)


    def test_front_carries_model_intent_in_any_language(self):
        marker = Path(os.environ['CHIRON_ASK'], 'focus-requested')
        with patch.object(brain.shutil, 'which', return_value='/fake/claude'), \
             patch.object(brain.subprocess, 'Popen') as popen, patch.object(brain.signal, 'signal'), \
             patch.object(brain.atexit, 'register'):
            worker = brain.start_claude()
            self.assertEqual(worker.ask, os.environ['CHIRON_ASK'])
            self.assertEqual(popen.call_args.kwargs['env']['CHIRON_ASK'], worker.ask)
            worker.errors.close()
        for request in ('메모 앱 열어줘', '打开微信'):
            with self.subTest(request=request):
                marker.unlink(missing_ok=True)
                brain.save_request(os.environ['CHIRON_ASK'], request)
                self.assertFalse(brain.wants_focus())
                with patch.object(brain, 'osa') as osa, patch.object(brain, 'free_focus') as free, patch.object(brain, 'window_target', return_value=self.target), \
                     patch.object(brain, 'look', return_value=[('/fake.jpg', 'Screen')]), \
                     patch.object(brain.time, 'sleep'), patch('sys.stdout', new_callable=io.StringIO) as out, \
                     patch('sys.argv', ['chiron.py', '--front', 'Fixture']):
                    brain.main()   # no focus words found (they are English-only): a picture in place, and how to say the user asked
                    osa.assert_not_called(); self.assertIn(f'{brain.ME} --front Fixture --asked', out.getvalue())
                    with patch('sys.argv', ['chiron.py', '--front', 'Fixture', '--asked']): brain.main()
                    osa.assert_called_once_with('tell application "Fixture" to activate')
                    free.assert_called_once_with(user=True)
                self.assertTrue(brain.wants_focus(request))
                with patch.object(brain, 'free_focus') as free, patch.object(brain, 'osa') as osa:
                    brain.allow_focus(request)
                    free.assert_called_once_with(user=True)
                    brain.restore_focus('Editor', request, ['Fixture'])
                    osa.assert_not_called()
                with patch.object(brain.subprocess, 'Popen') as popen:
                    popen.return_value.communicate.return_value = ('', '')
                    brain.hands_call(['see'])
                    self.assertEqual(popen.call_args.kwargs['env']['CHIRON_FOCUS_REQUESTED'], '1')
                marker.unlink(missing_ok=True)   # this fixture's agent gate folder is the ask folder itself
                with patch.dict(os.environ, {'CHIRON_AGENT': 'fixture'}):
                    self.assertFalse(brain.wants_focus())
                    self.assertTrue(brain.wants_focus(sites=True))

    def test_front_works_on_a_window_in_any_state_without_raising_it(self):
        # Oct 21: a page on his second display, not key, was raised by --front although he kept working on the laptop. Any app, any state.
        marker = Path(os.environ['CHIRON_ASK'], 'focus-requested')
        unfocused, covered, minimized = {**self.target, 'visible': True}, {**self.target, 'visible': False}, {**self.target, 'minimized': True}
        for request, target, extra, raised in (('play it', unfocused, [], False), ('play it', covered, [], False), ('keep going', minimized, [], True),
                                               ('play it', {}, [], True), ('show me it', unfocused, [], True), ('play it', unfocused, ['--asked'], True)):
            with self.subTest(request=request, target=target, extra=extra):
                brain.save_request(os.environ['CHIRON_ASK'], request); marker.unlink(missing_ok=True)
                with patch.object(brain, 'window_target', return_value=target), patch.object(brain, 'osa') as osa, \
                     patch.object(brain, 'free_focus') as free, patch.object(brain, 'look', return_value=[('/fake.jpg', 'Screen 2')]) as looked, \
                     patch.object(brain.time, 'sleep'), patch('sys.stdout', new_callable=io.StringIO) as out, \
                     patch('sys.argv', ['chiron.py', '--front', 'Fixture App', 'Board', *extra]):
                    brain.main()
                self.assertEqual(osa.called, raised); self.assertEqual(free.called, raised); self.assertEqual(marker.exists(), raised)
                self.assertIn('Screen 2: /fake.jpg', out.getvalue())
                if not raised:
                    looked.assert_called_once_with(cleanup=False, window=target)   # the window itself, painted where it sits
                    self.assertIn("--front 'Fixture App' Board --asked", out.getvalue())
        with patch.object(brain.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(covered), '')) as run:
            self.assertEqual(brain.window_target('Fixture App', 'Board'), covered)
            self.assertEqual(run.call_args.args[0], [brain.APP, '--window-target', 'Fixture App', 'Board'])
            self.assertEqual(run.call_args.kwargs['env']['CHIRON_FOCUS_REQUESTED'], '0')   # the lookup itself never activates
        for failure in (OSError(), subprocess.TimeoutExpired('x', 2)):
            with patch.object(brain.subprocess, 'run', side_effect=failure): self.assertEqual(brain.window_target('Fixture App'), {})
        with patch.object(brain.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '[]', '')): self.assertEqual(brain.window_target('Fixture App'), {})
        self.assertIn('pictures that window in place, even covered; raises only if asked.', brain.system_prompt(brain.ASK_FIRST))
        with patch.object(brain, 'pref', side_effect=lambda k, d: 'front' if k == 'workIn' else d):
            self.assertNotIn('pictures that window in place', brain.system_prompt(brain.ASK_FIRST))

    def test_look_paints_the_target_window_on_its_own_display(self):
        calls = []
        def run(cmd, **_):
            calls.append(cmd)
            if cmd[:2] == [brain.APP, '--look']: Path(cmd[3]).write_bytes(b'jpg')
            return subprocess.CompletedProcess(cmd, 0, 'window\n' if len(cmd) == 5 and painted[0] else '', '')
        painted = [True]
        displays = [('Built-in', 0, 0, 1512, 982, True), ('Monitor', 1512, 0, 2560, 1440, False)]
        window = {**self.target, 'app': 'Fixture App', 'window': 'Board', 'windowFrame': [1900, 200, 1100, 800], 'visible': False}
        with patch.object(brain, 'screens', return_value=displays), patch.object(brain.subprocess, 'run', side_effect=run), \
             patch.object(brain, 'pref', side_effect=lambda k, d: False if k == 'draw' else d):
            shots = brain.look(cleanup=False, window=window)
            self.assertEqual([c[:3] + c[4:] for c in calls], [[brain.APP, '--look', '2', '42']])   # only its display, with its window id
            self.assertEqual(len(shots), 1)
            self.assertIn('Fixture App "Board" painted where it sits (hidden from the user); click spots as 2:x,y', shots[0][1])
            painted[0] = False; calls.clear()   # the window could not be captured: the label never claims it
            self.assertNotIn('painted', brain.look(cleanup=False, window=window)[0][1])
            calls.clear()
            labels = [label for _, label in brain.look(cleanup=False)]
            self.assertEqual(len(calls), 2); self.assertTrue(labels[0].endswith('click spots as 1:x,y in picture pixels)'))
        for path in Path(os.environ['CHIRON_ASK']).glob('chiron-screen-*'): path.unlink()

    def test_old_foreground_shortcuts_upgrade_to_background_open(self):
        saved={'cmds':['open -a Notes'],'reply':'Done.'}
        with patch.object(brain,'skills',return_value={'study':saved}),patch.object(brain,'show',return_value='opened Notes in the background') as show:
            self.assertEqual(brain.replay('study'),'Done.');show.assert_called_once_with('Notes',True)

    def test_open_preview_expands_shell_home_and_restore_uses_current_app(self):
        with patch.object(brain,'preview_app') as preview:
            brain.preview_commands('open -g ~/Documents/fixture.pdf')
            preview.assert_called_with(os.path.expanduser('~/Documents/fixture.pdf'),'open',directory=None)
        with patch.dict(os.environ,{'CHIRON_FRONT':'Old Mail'}),patch.object(brain,'osa',side_effect=['Editor','com.fixture.browser','Browser','Browser','']) as osa,patch.object(brain,'preview_app',return_value={'app':'Browser'}),patch.object(brain.time,'sleep'),patch.object(brain.subprocess,'run',return_value=subprocess.CompletedProcess([],0)):
            brain.show('https://fixture.invalid',bg=True)
            self.assertEqual(osa.call_args.args[1],'Editor')


    def test_applescript_ids_and_named_windows_use_the_same_target_helper(self):
        with patch.object(brain,'preview_app') as preview:
            brain.preview_commands('osascript -e \'tell application id "com.apple.Notes" to set name of window "Pilot" to "Pilot"\'')
            preview.assert_called_once_with('com.apple.Notes',title='Pilot',directory=None)
