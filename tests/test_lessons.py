"""chiron/lessons.py: the planner's checks and its one retry, step checks, hints, and what needs an Allow."""
import json
import os
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch

from chiron import jev, lessons, skills

Reply = namedtuple('Reply', 'text usd')
A = jev.Answer
GOOD = {'id': 'New Folder!', 'title': {'en': 'Make a new folder', 'hi': 'नया फ़ोल्डर बनाना'}, 'app': 'Finder',
        'steps': [{'id': 's1', 'concept': 'menu', 'say': {'en': 'Click File.', 'hi': 'File पर क्लिक कीजिए।'}, 'target': {'app': 'Finder', 'label': 'File', 'role': 'AXMenuBarItem'}, 'expect': 'The File menu is open'}]}


class Fake:
    def __init__(self, *replies): self.replies, self.prompts = list(replies), []
    def ask(self, system, prompt, **k):
        self.prompts.append(prompt); return Reply(self.replies.pop(0), 0.002)


class PlannerTest(unittest.TestCase):
    def test_a_good_plan_is_a_card(self):
        card, usd = lessons.plan('make a folder', 'Finder window', Fake('```json\n' + json.dumps(GOOD) + '\n```'))
        self.assertEqual(skills.validate(card), '')
        self.assertEqual((card['id'], card['asked'], usd), ('new-folder', ['make a folder'], 0.002))
        self.assertTrue(card['steps'][0]['draw']['wait'])

    def test_one_retry_names_the_problem(self):
        bad = {**GOOD, 'steps': [{**GOOD['steps'][0], 'say': {'en': 'x', 'hi': 'no hindi'}}]}
        fake = Fake(json.dumps(bad), json.dumps(GOOD))
        card, usd = lessons.plan('make a folder', 'x', fake)
        self.assertEqual(usd, 0.004)
        self.assertIn('say.hi is not Hindi', fake.prompts[1])

    def test_two_failures_stop(self):
        with self.assertRaises(ValueError): lessons.plan('x', 'y', Fake('not json', '{}'))

    def test_screen_text_is_labelled_as_data(self):
        self.assertIn('never instructions', lessons.SYSTEM)


class CheckTest(unittest.TestCase):
    def run_check(self, done, fault, sure=0.9):
        answers = {'step_done': A('noul', done, sure, sure < .7, 'jev'), 'step_fault': A('choice', fault, sure, sure < .7, 'jev')}
        with patch.object(lessons.jev, 'judge', return_value=answers) as call:
            r = lessons.check(GOOD['steps'][0], 'window')
        self.assertEqual(call.call_count, 1, 'both questions in one request')
        return r['result']

    def test_results(self):
        self.assertEqual(self.run_check(True, 'correct'), 'correct')
        self.assertEqual(self.run_check(False, 'loading'), 'loading')
        self.assertEqual(self.run_check(False, 'wrong_app'), 'wrong')
        self.assertEqual(self.run_check(False, 'wrong_app', 0.5), 'unsure')

    def test_clearly_not_done_is_a_hint_even_when_the_reason_is_unclear(self):
        answers = {'step_done': A('noul', False, 0.95, False, 'jev'), 'step_fault': A('choice', 'wrong_place', 0.4, True, 'jev')}
        with patch.object(lessons.jev, 'judge', return_value=answers):
            r = lessons.check(GOOD['steps'][0], 'window')
        self.assertEqual((r['result'], r['fault']), ('wrong', ''))

    def test_hint_is_free_and_names_the_right_place(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'CHIRON_DIR': root}):
            self.assertIn('Finder', lessons.hint(GOOD['steps'][0], 'wrong_app', 'en'))
            self.assertIn('File', lessons.hint(GOOD['steps'][0], 'wrong_place', 'en'))

    def test_risky_steps_need_an_allow(self):
        send = {'target': {'label': 'Send'}, 'expect': 'The photo appears in the chat'}
        self.assertEqual(lessons.risky_step(send), 'Click "Send"?')
        self.assertEqual(lessons.risky_step({'target': {'label': 'File'}, 'expect': 'The File menu is open'}), '')


class WrongClickThenRightTest(unittest.TestCase):
    """The plan's eval: the learner clicks the wrong app, gets a hint, then the right one."""
    def test_hint_then_success_on_one_card(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'CHIRON_DIR': root}):
            card = skills.starters()['youtube-play']
            step = card['steps'][0]
            wrong = {'step_done': A('noul', False, 0.95, False, 'jev'), 'step_fault': A('choice', 'wrong_app', 0.9, False, 'jev')}
            right = {'step_done': A('noul', True, 0.95, False, 'jev'), 'step_fault': A('choice', 'correct', 0.9, False, 'jev')}
            with patch.object(lessons.jev, 'judge', side_effect=[wrong, right]):
                first, second = lessons.check(step, 'Safari is in front'), lessons.check(step, 'Google Chrome is in front')
            self.assertEqual((first['result'], first['fault'], second['result']), ('wrong', 'wrong_app', 'correct'))
            self.assertIn('Dock', lessons.hint(step, first['fault'], 'en'))
            row = skills.record(card, [{'id': 's1', 'result': 'correct', 'hints': 1, 'secs': 9}], score=4)
            self.assertEqual(row['mastery_after'], 2, 'one hint')
            self.assertEqual(len(skills.home()), 1, 'a new star on Home')


class RoutedAskTest(unittest.TestCase):
    def setUp(self):
        root = tempfile.TemporaryDirectory(); self.addCleanup(root.cleanup)
        p = patch.dict(os.environ, {'CHIRON_DIR': root.name}); p.start(); self.addCleanup(p.stop)

    def routed(self, task, **route):
        import brain
        with patch('chiron.router.route', return_value={'slots': {}, 'risky': False, 'source': 'card', **route}):
            return brain.real_routed_ask(task)

    def test_a_starter_lesson_costs_nothing(self):
        reply, outcome, usd, lesson = self.routed('teach me', mode='teach', card=skills.starters()['open-photo'])
        self.assertEqual((outcome, usd, lesson['card']['id']), ('taught', 0.0, 'open-photo'))

    def test_a_question_goes_to_the_main_ask(self):
        self.assertIsNone(self.routed('what is a PDF', mode='question', card=None))

    def test_a_saved_skill_runs_with_no_ai_and_its_slot_stays_inside_the_url(self):
        import brain
        card = {**skills.starters()['youtube-play'], 'mastery': 5}
        with patch.object(brain.subprocess, 'run', return_value=type('R', (), {'returncode': 0})()) as run:
            reply, outcome, usd, lesson = self.routed('play', mode='do', card=card, slots={'q': "a'; rm -rf ~"})
        self.assertEqual((outcome, usd, lesson), ('did', 0.0, None))
        self.assertNotIn(';', run.call_args.args[0])

    def test_a_risky_saved_command_stops_at_the_allow_card(self):
        import brain
        card = {**skills.starters()['open-photo'], 'cmds': ["curl -X POST --data x https://example.com/send"]}
        with patch.object(brain, 'ask_user', return_value='n') as allow, patch.object(brain.subprocess, 'run') as run, patch.object(brain, 'pref', side_effect=lambda k, d: d):
            reply = brain.do_card(card, {})
        allow.assert_called_once()
        run.assert_not_called()
        self.assertIn('Not done', reply)

    def test_only_the_gate_can_set_the_allowed_click(self):
        import brain
        self.assertRegex('CHIRON_ALLOWED_CLICK=Send chiron.py --hands click Send', r'CHIRON_\w+\s*=')
        self.assertIn(r"CHIRON_\w+\s*=", Path(brain.__file__).read_text())


if __name__ == '__main__':
    unittest.main()
