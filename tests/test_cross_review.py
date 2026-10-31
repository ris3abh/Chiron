"""Offline cross-review regressions; Swift snippets use no windows or real apps."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def swift_check(test, code):
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / 'check.swift'
        source.write_text('import Foundation\n' + code)
        result = subprocess.run(['swift', str(source)], capture_output=True, text=True,
                                env={**os.environ, 'CHIRON_DIR': folder}, timeout=60)
        test.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class CrossReviewTests(unittest.TestCase):


    def test_speculative_launch_failure_keeps_listening_until_confirmed(self):
        source = (ROOT / 'Chiron.swift').read_text()
        failure = source[source.index('        guard let w = warm ?? spawn()'):source.index('        warm = nil; proc = w.p')]
        swift_check(self, 'final class Fixture { var warm:Int?, busy=true, pinned=false, ahead="draft", calls=0\n'
                    + 'func spawn()->Int? { nil }; func js(_ s:String) { calls+=1 }; func show() {}\n'
                    + 'func run(_ speculative:Bool) { let point:[String:Any]?=nil\n' + failure + ' _=w\n}\n}\n'
                    + 'let f=Fixture(); f.run(true); precondition(f.ahead.isEmpty && !f.busy && !f.pinned && f.calls==0)\n'
                    + 'f.run(false); precondition(f.pinned && f.calls==1)\n')

    def test_failed_resume_does_not_apply_success_effects(self):
        source = (ROOT / 'Chiron.swift').read_text()
        resume = source[source.index('            if b["resume"] != nil'):source.index('            if b["replace"]')]
        swift_check(self, 'enum Prefs { static func bool(_ k:String)->Bool { true }; static func set(_ k:String,_ v:Bool)->Bool { false } }\n'
                    + 'final class Settings { func apply(_ k:String,_ v:Bool) {}; func push() {} }\n'
                    + 'enum Chiron { static let settings=Settings() }\n'
                    + 'func js(_ c:String,_ v:Bool) { fatalError("resume success shown") }; func hide(after:Double) { fatalError() }\n'
                    + 'let b:[String:Bool]=["resume":true]\n' + resume)
