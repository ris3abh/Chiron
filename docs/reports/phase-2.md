# Phase 2 report — Voice Bar and speech

Status: **built and running, not yet accepted.** Everything a machine could check passes. The "Done when" list needs a person holding fn, so it is still open.

## Built
- **Voice Bar:** an always-on pill at the bottom centre, on every desktop, never taking focus. States: idle, listening with live wave and words, thinking, speaking, done, message, plus placeholders for teaching, practice and Guardian. Drag to move (remembered per display), double-click to reset, right-click menu. (`ui/bar.html`, `tests/bar.html`, `app/VoiceBar.swift`)
- **The box:** existing listening and answering are unchanged; every box call also reaches the bar (`VoiceBar.mirror`). Short answers stay on the bar. Long answers, cards and typed replies open the box docked above it.
- **Talk key:** fn by default, or Control + Option from Settings. Hold, release to send, double-tap to lock. The 60 s limit and quiet-tap rule stay. fn+arrow or fn+Delete with nothing said goes away quietly.
- **Dictation by voice:** saying "type …" or "likho …" first sends the rest to the app you are in. (`dictationRequest`, `App.routeToDictation`)
- **On-device speech per language:** probes Apple's engines at launch, picks `en-IN` and `hi-IN`, downloads what's missing, writes `speech.json`. Replaces the hardcoded `en-US`. (`app/SpeechLocale.swift`)
- **Normaliser:** Devanagari, romanised Hindi and English reach one form before `fast()`. (`chiron/normalize.py`)
- **Speaking:** a voice per language, speed 0.7–1.1 (default 0.85), replies on by default, instant replies in the app language, "say that again" with no AI. (`Chiron.swift`, `chiron.py`)
- **Settings → Voice and language:** engine status with download progress, Test my voice, talk key, 🌐 key fix, bar reset, voices with Preview, speed, dictionary.
- **Words spoken on Home:** voice asks plus dictation, split by language, with time saved. (`voice.jsonl`, `chiron/home.py`)
- **`chiron.py --speech-eval`:** accuracy per language and engine over recordings, through the app's own engine. (`chiron/speech_eval.py`, `Chiron --speech-file`)

## Decisions I made
- No cloud speech (Rishabh, 2026-10-30): if a language is missing, Chiron listens in English and says so. The plan's Sarvam key field, cloud fallback and auto-fallback rule are gone.
- `en-IN` before `en-US`, because it matches the accent Chiron will hear.
- The bar sits on top of the box rather than replacing it, so nothing that worked was rewritten.
- A one-time migration moves existing installs: fn stops dictating and becomes the talk key, ⌃⌥Space stops being the default, replies are spoken. A shortcut someone recorded themselves stays. It saves on the next preference write.
- Boxes open for answers over 90 characters, or messages over 140.
- `--speech-eval` counts an ask as understood if it reaches the same command, or at most one word in five differs.

## How to install this build
1. `git checkout phase-2 && ./build.sh`
2. **Turn off Wispr Flow's fn shortcut, or quit Flow.** Both listen to fn, and its bar sits in the same spot as Chiron's.

## Test it now (do these in order)
| # | Do this | You should see | Pass? |
|---|---------|----------------|-------|
| 1 | Look at the bottom centre on another desktop and in a full-screen video | The small bar in each | |
| 2 | Hold fn, say "open Calculator", release | Calculator opens; the bar shows done | |
| 3 | Click हिं, hold fn, say "कैलकुलेटर खोलो" | Same result; reply spoken in Hindi | |
| 4 | Hold fn, say "YouTube pe news lagao" | YouTube or a reply about news, in Hindi or English | |
| 5 | Settings → Voice and language → Test my voice, both languages | Words and engine name within about 7 s | |
| 6 | Double-tap fn, speak for 20 s, press fn | Stays listening, then sends | |
| 7 | Click into TextEdit, hold fn, say "type hello from Chiron" | The words land in TextEdit | |
| 8 | Ask something with a long answer | The box opens above the bar | |
| 9 | Drag the bar to the left, quit, reopen; then double-click it | Same spot; then back to centre | |
| 10 | Settings → Speaking: choose Lekha, Preview, change speed | Hindi voice at the new speed | |
| 11 | Press Esc while it answers | It stops | |
| 12 | Open Home | Words spoken rises, split by language | |
| 13 | Add recordings to `tests/audio/` with `expected.json`, run `python3 chiron.py --speech-eval` | At least 8 of 10 per language (the gate) | |

## Automated tests
- Command: `python3 -m unittest discover -s tests -v` (host guard on). Result: **620 tests, 0 failures, 0 errors, 114 skipped.** Previous report: 599, 0, 113.
- New: `test_normalize` (45 pairs), `test_voice_brain`, `test_bar_page`, `test_speech_eval`.
- Updated, not removed, for the new behaviour: `test_audio_native`, `test_dictation`, `test_native`, `test_onboarding_copy`, `test_prefs_native`, `test_strings`, `test_home_page`.
- Run directly on this Mac, outside the guard: engine choice and "type" detection gave the expected output, including "typewriter repair near me" not counting as "type".
- Bar and Settings seen in Chrome (mock); idle bar seen on the real screen.

## Speech results (real engine, synthetic voices)
macOS voices Lekha and Rishi spoke 10 asks each into `--speech-eval`. This is a stand-in, not the gate.
- English (`en-IN`): 9 of 10, 95% of words.
- Hindi (`hi-IN`): 7 of 10, 74% of words. Misses were app names: Calculator, WhatsApp, Chrome.
- **Apple's Hindi engine writes romanised Hindi ("notes band karo"), not Devanagari**, which is why the normaliser's roman path matters most.

## Costs measured
- No paid calls in this phase. Speech is on-device and free; the normaliser and "say that again" use no AI.

## Known gaps and risks
- **Native, compiled but unverified:** nobody has held fn yet. The talk key, double-tap, "type …", Test my voice, drag and remember, box docking, Esc while the box is quiet, and the bar in full screen have not been exercised live.
- **The 109 host-guarded native tests still have not run on a screen.**
- **Wispr Flow** also holds fn and the same spot.
- **Hindi app names are the weak point.** Fix ideas if the gate fails: fuzzy-match heard words against installed apps, or add common misheard forms.
- **Answer card:** long answers use the existing box. Its larger text and the 20 s auto-close from the plan are not built.
- **Dictation counts as English** on Home unless it came through a voice ask.
- **CI** for these pushes has not been checked (`gh` isn't installed).
- `bar.listening` and similar Hindi lines use the masculine "रहा हूँ"; flagged for review.

## Ready for Phase 3?
- **Not yet.** Needs steps 1–12 by a person, and the 8 of 10 gate on real recordings in both languages.

---

## Addendum: real failures, rooms, card (Rishabh's review)

### Changed
- **Real Recent-list failures:** `, bhajan, chalage, batav.`, `YouTube Khol Ke Batao?`, `YouTube chalu Karna` and `Open YouTube for me.` were all paid model calls. They now resolve with no AI. Everyday sites (`SITES` in `chiron.py`: YouTube, Google, Gmail and others) open instantly, and "play X on YouTube" opens its results page.
- **App names in both scripts:** `SpeechLocale.hints` gives a Hindi ask each installed app's English name, Devanagari spelling and a spoken form, on the live path and in `--speech-file`.
- **Pill:** idle 56 × 20 pt (was 120 × 28); active at most 380 wide and 36 tall.
- **Old chat window removed from the screen.** `App.show()` no longer orders it front. The card above the pill (`ui/bar.html`) shows long answers (closes on ✕, Esc, or 20 s after it ends), Allow, choices, rewrite actions, typed replies and a retry. Allow keeps its refuse button; voice replies and the 60 s expiry still work through `ui/ui.html`, which stays loaded off screen as App's state machine.

### Room test (`scripts/speech-rooms.py`, 27 asks, macOS voices)
| Room | English | Hindi |
|---|---|---|
| Close | 11 of 12 | 11 of 15 |
| Slow | 11 of 12 | 9 of 15 * |
| Soft | 11 of 12 | 10 of 15 * |
| Far | 11 of 12 | 10 of 15 * |
| TV | 11 of 12 | 10 of 15 * |
| **All together** | **0 of 12** | **1 of 15** |

\* Scored before the `करना` fix, which added one in Close; the others may gain one.

- **All together fails outright:** the engine transcribed the TV news, not the person. Each condition alone holds up; the slow, soft, far voice under a TV does not.
- **The two-script hints fixed none of the misses.** Calculator, WhatsApp and Chrome are heard wrongly with them too, and Calendar missed as well. This is a robot Hindi voice saying English names, so real voices may differ; there is no evidence yet that the hints help.
- Everything here is a rehearsal. The gate is still real people.

### Lost with the old window
- The "point at your screen" button, picture previews and the typed "something else" in choices, maths rendering in answers, and Undo on a learned word (remove it in Dictionary). The model picker and Full access chip went too.

### Compiled but unverified
- No card has been opened by a real ask: Allow, choices, typed replies, Esc and the 20 s close were seen only in the mock. **Check Allow first.**

### Tests
- `python3 -m unittest discover -s tests -v`: **623 tests, 0 failures, 114 skipped.** Two assertions that the box follows the pointer went with that feature.
