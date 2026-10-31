# Phase 3 report — Teach Me and Do It

Status: **built, not accepted, and the lesson runner has never run on a real screen.** The brain is tested and was checked against the live Jev service. Everything Swift compiled but no lesson has been seen working. Do step 1 before anything else.

## Built
- **Router** (`chiron/router.py`): `fast()` and `normalize.py`, then a skill card, then plain wording (instructions and questions cost nothing), then one Jev request, then Haiku.
- **Skill cards** (`chiron/skills.py`, `chiron/starter/`): 5 hand-written bilingual starters, your own in `cards.json`, `attempts.jsonl`, mastery from the Product Plan's table. `{q}` slots are made safe before they reach a command.
- **Lesson planner and checks** (`chiron/lessons.py`, `chiron.py --lesson`): Haiku plans once as JSON and is re-asked once; every step checked by Jev.
- **Lesson runner** (`app/Lesson.swift`, hooks in `ScreenDrawing`): amber ring, large captions, Back, Show me, Next, Stop, hints, a redraw on the right target, "Shall I do this step?" after 3 hints. Voice commands in English and Hindi. A target it can't find falls back to the caption on the card.
- **Do It:** a saved skill runs with no AI through the same `risky()` gate and Allow card. With no saved command it goes to the main model, which is gated as ever.
- **Home:** starter lesson in Today, skill constellation with focusable stars, Teach me again and Just do it. **Settings → Teaching:** mode, caption size.
- **`outcome` on every log row:** did, taught, practiced, question, failed. Conversations reads it; only rows older than the field are worked out from what they ran.
- **Speech:** Google or silence, with the words on the bar. Apple's voice is an off-by-default switch. Lesson captions use the same cached path. Only characters past the free tier count toward the cap.
- **`docs/BUILD_PLAN.md`** updated to match what exists.

## Safety fix found on the way
`Hands` treated a plain Return as harmless, so pressing it in a message box could send with **no Allow card**: only clicking Send was gated. Return in a multi-line box or a filled field now asks. Multi-line boxes count even when they read empty, because web message boxes often report no text. Search and address boxes are exempt.

## Decisions I made
- **A new instruction is done, not taught.** The plan says a new skill goes to Teach Me, but your note says instructions must reach Do It, and someone saying "play bhajan" wants it played. Teach Me starts from "teach me", "how do I", "sikhao", or a known card below mastery 5.
- **Plain questions skip the request.** "what…", "kyun…" and similar are clear from their words. It saves money, and Haiku through Claude Code takes about 8 seconds.
- **Mastery follows the plan's table,** not the story in the Product Plan where one hint reaches 3: the two disagree. Chiron doing a step earns nothing.
- **Cards live in `cards.json`,** because `skills.json` is the base app's instant shortcuts.
- **Deleted the old `drawing.sayArguments`** in favour of `speakStep`, so captions share the cached voice.
- **No TEACH block in the system prompt:** lessons have their own planner, so the main prompt stays as it was.
- **WaveNet is priced at the safer figures,** $16 per million and 1 million free, because sources disagree. Chirp 3 HD: $30 per million after 1 million free. That is about 1,600 full spoken answers a month for free.

## How to install this build
1. `git checkout phase-3 && ./build.sh`
2. Quit Wispr Flow first: it also holds fn.

## Test it now (do these in order)
| # | Do this | You should see | Pass? |
|---|---------|----------------|-------|
| 1 | Ask Chiron to send a message (Messages or WhatsApp Web), then press **Don't Allow**. Ask again and press **Allow** | The Allow card appears above the bar and nothing is sent until you press Allow; Don't Allow sends nothing | |
| 2 | Home → **Start** (starter YouTube lesson) | Ring on Google Chrome in the Dock, caption, step 1 spoken if Google has a key, otherwise silent | |
| 3 | Click Safari instead | A gentle hint and the ring back on Chrome | |
| 4 | Finish the lesson | Praise; one star under YouTube; Conversations shows it as Taught | |
| 5 | Hold fn: "just play a video on YouTube" | Done by itself, no ring, $0 | |
| 6 | Hold fn: "teach me how to make a new folder on the desktop" | Planned once (about $0.0003), lesson runs, new card saved | |
| 7 | Halfway through, tap हिं on Home | Next caption is Hindi, no AI cost | |
| 8 | Press Show me three times on one step | Chiron offers to do the step; anything risky shows Allow | |
| 9 | Say "stop" | Marks clear; Conversations shows Didn't finish; no new star | |
| 10 | Remove the Jev key in Settings → Connections, repeat 2 and 3, then put it back | Lesson still works through Haiku, slower, at the higher cost below | |
| 11 | Run `python3 -m unittest discover -s tests -v` and `python3 -m tests.evals.harness --dry` | Suite green; see Automated tests for the eval | |

## Costs measured
Real requests on 2026-10-31, in a throwaway folder.

| | With Jev | Without Jev (Haiku fallback) |
|---|---|---|
| One route | $0.00002, about 0.8 s (0.7 s is the Keychain read) | about $0.0002, about 8 s |
| One step check | $0.00002 | about $0.0002 |
| Starter lesson, 6 steps | about $0.00012 | about $0.0012 |
| Planning a new lesson | $0.00024 to $0.00055 (Haiku either way) | the same |

These are measured per request. **A full lesson, and tests 2 to 10, have not been run**, so the whole-lesson lines are arithmetic, not a measurement.

Live Jev checks: 10 of 10 right on the tuned questions: money, booking and deleting flagged; wrong app, not done yet and still loading told apart.

## Automated tests
- `python3 -m unittest discover -s tests -v`: **674 tests, 0 failures, 114 skipped** (host guard on). Phase 2 ended at 640.
- New: `test_router` (30 asks), `test_skills`, `test_lessons` (including wrong click then right, and a risky saved command stopping at Allow).
- **`tests/evals/harness.py --dry` could not run here:** it stops at the host guard, so the plan's eval is covered by `test_lessons` instead.
- `tests/lesson_preview.swift` was not built.

## Known gaps and risks
- **Never seen working:** the lesson runner, its callout, wrong-click hints, voice commands, Show me, and "Shall I do this step?". All compile; none has run.
- **Test 1 is unproven.** The Return fix and the Allow card are in, but no real message has been tried.
- **Starter labels are from memory,** not read off this Mac. A label that differs falls back to the caption, so the lesson continues without a ring.
- **Fast failures:** if a step's target sits behind another window, the ring may still be drawn on it.
- **Hindi speech recognition** is still the Phase 2 problem: app names, and the TV room.
- **The cloud voice still hasn't spoken:** no Google key yet.
- **Rebuilds:** the first Keychain read after a rebuild takes about 8 s. The limit is now 15 s so Jev isn't silently lost.
- **Haiku fallback is slow:** about 8 s through Claude Code, before the answer starts, for asks that need it.
- **Practice** is Phase 4: no reminders yet, and the "explain it back" switch is disabled.

## Ready for Phase 4?
- **No.** Needs tests 1 to 10 by a person, and learners finishing 4 of 5 starter lessons.
