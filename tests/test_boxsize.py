"""Bubble geometry only; no windows, preferences, or display access."""
from pathlib import Path
import unittest

from tests import run_swift


class BoxSizeTests(unittest.TestCase):
    def test_saved_width_and_frame_fit_current_screen(self):
        source = (Path(__file__).resolve().parents[1] / 'Chiron.swift').read_text()
        width = source[source.index('func boxWidth('):source.index('final class App:')]
        clamp = source[source.index('    static func clamp(', source.index('enum MeetingFrame')):source.index('    // The same frame on another display:')]
        harness = 'import Cocoa\n' + width + '\nenum MeetingFrame {\n' + clamp + '}\n' + r'''
for bounds in [NSRect(x: 0, y: 0, width: 1024, height: 700),
               NSRect(x: -600, y: 200, width: 480, height: 360)] {
    precondition(boxWidth(500, bounds) == min(500, bounds.width - 16))
    precondition(boxWidth(720, bounds) == min(720, bounds.width - 16))
    precondition(boxWidth(99999, bounds) == min(900, bounds.width - 16))
    precondition(boxWidth(.nan, bounds) == min(500, bounds.width - 16))
    let fitted = MeetingFrame.clamp(NSRect(x: 9000, y: -9000,
        width: boxWidth(900, bounds), height: 1000), bounds.insetBy(dx: 8, dy: 8))
    precondition(bounds.insetBy(dx: 8, dy: 8).contains(fitted))
}
print("bubble fits")
'''
        self.assertIn('bubble fits', run_swift(self, harness))
