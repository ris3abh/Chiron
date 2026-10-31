# Phase 1 report — Foundation and Home

**Read this first: none of the Swift in this phase has ever been compiled.** This Mac (macOS 15.3.2, Command Line Tools with Swift 6.1, no Xcode) can't build Chiron: the app needs the macOS 26 SDK, and the installed toolchain is broken anyway (its compiler doesn't match its SDK; even a hello-world `swiftc` fails with `redefinition of module 'SwiftBridging'`). The Python, the page and the tests that don't compile Swift were all run here. Everything native has been written carefully and checked by reading, symbol by symbol, but the first real compile happens on macOS 26 or in CI (`.github/workflows/dev-dmg.yml`). Expect to fix a few compile errors there.

## Built

- **Fork and rename:** the base app (v1.5.3, `dac5448`) is now Chiron: `Chiron.swift`, `chiron.py`, `Chiron.app`, `com.chiron.app`, `~/.config/chiron`, `CHIRON_*`, `chiron.raise`, LaunchAgents `com.chiron.app` and `com.chiron.practice.<id>`. The upstream remote stays for future fixes. `LICENSE` carries Chiron's copyright; the base app's MIT notice is in `CREDITS.md`. (files: everything; `build.sh`, `README.md`, `LICENSE`, `install.sh`)
- **Removed features**, each with its tests, prefs, menu items and UI:
  - PostHog telemetry, failure reports and the feedback reporter.
  - Gumroad licensing, the Ko-fi tip jar and "Ideas when I'm away". The "Say remember…" usage tips are kept.
  - Devin and Pi.
  - Spotify helpers, and the web.js page adapter. The `--web` tool went with it, because it only worked through web.js. Window text, `--read`, `--search`, `--show` and Hands still cover web pages.
  - Meeting Copilot. Its model-call helpers moved to `chiron/llm.py` first; `MeetingFrame` and the calendar helper are kept.
  - The MiniScreen UI. Its window helpers are kept as `enum WindowTarget`.
  - Agents. Routines are rewired first (below).
  - Nix, devbox, the git updater (now a stub until Sparkle) and FUNDING.yml.
- **Routines → Practice prompts:** a due routine now opens the normal box with its ask as a typed draft and the status "Practice · <label>". Nothing runs until the user presses Return. (`chiron.py --routine-due`, `App.practice`, `RoutineWake`)
- **Home and Settings, the one page:** `ui/home.html` holds both the Home view and the Settings view.
  - Home: Today card, Words spoken, AI spend, Recent, and the connection status dots.
  - Settings: Brain (Claude Code, Anthropic key, OpenAI key, custom server), Jev, Budget, Voice and language, Permissions, About.
  - Behaviour: English and Hindi, light and dark, reduced motion and transparency, more contrast, and narrow widths. A Test passes before a key is saved, so a wrong key is never stored. Remove takes two presses.
  - Styled as Apple-style glassmorphism at the user's request (see "Decisions").
  - (files: `ui/home.html`, `ui/strings/en.json`, `ui/strings/hi.json`, `ui/strings/hi.review.json`, `ui/fonts/`, `tests/home.html`)
- **Windows and bridge:**
  - Home is 880×720 and Settings is 560×680. Both remember their frame, and the Dock icon shows only while one is open.
  - Native vibrancy sits behind a transparent web view, under a transparent title bar.
  - All Phase 1 bridge methods are implemented, plus `strings.get`, `app.info`, `link.open` and `window.*`. State refreshes every 5 s while visible and after every ask.
  - The menu bar has Open Home and Settings…, with every label through `L()`.
  - The old Settings window and `ui/settings.html` are gone. The class behind them stays only to apply preference changes (voice, setup and shortcut recording use it). The voice-settable switch list moved into `chiron.py`.
  - (files: `app/HomeWindow.swift`, `app/HomeBridge.swift`, `app/Strings.swift`, `Chiron.swift`)
- **Keychain:** keys live only in the login Keychain (service `com.chiron.app`, accounts `anthropic`, `openai`, `jev`, `sarvam`, `custom`).
  - `Chiron --secret get|set|delete <name>`; `set` reads the value from stdin so it never shows in `ps`.
  - On launch, an older `apiKey` moves from `settings.json` to the Keychain and is removed from the file.
  - Onboarding's custom-server form saves its key to the Keychain too.
  - (files: `app/Keychain.swift`, `Prefs.remove` in `Chiron.swift`)
- **Providers:** `Provider.ask(system, messages, model, images, max_tokens, json) -> Reply(text, usd, input_tokens, output_tokens, ms)` for Anthropic, OpenAI, custom server and Claude Code.
  - Anthropic caches the system block. Costs come from a dated, editable price table.
  - Errors are sorted into `rejected`, `offline`, `server`, `nokey` or `missing`, so Settings can say them in plain words.
  - (files: `chiron/providers.py`, `chiron/prices.json`)
- **Which brain gets which key:** every `claude` run goes through `claude_env()`. The Keychain key is passed only when the brain is "Anthropic API key"; every other brain drops any inherited `ANTHROPIC_API_KEY`, so a plan user can't be moved onto API billing by accident. The custom server is used only when the brain is "custom". (`chiron.py`, `chiron/llm.py`)
- **OpenAI-only brain:** no Claude worker starts. The instant path still runs, and anything else gets one answer without tools in the app language; asking for a Mac task gets a one-line note that it needs Claude. The Today card shows the same note. (`openai_answer` in `chiron.py`)
- **Jev:** `judge(state, questions)` sends all questions about one state in one request to `POST https://api.typesafe.ai/v1/systemone` (more than 16 are split).
  - It has a 3 s timeout and one retry, logs cost, and treats answers below 0.7 confidence as unsure.
  - With no key, or Jev down after the retry, Claude Haiku answers in one JSON prompt, logged as `haiku-fallback`.
  - A rejected key is reported, not hidden behind the fallback.
  - The base URL is configurable.
  - (file: `chiron/jev.py`)
- **Usage and cap:** every model or Jev call adds one row to `usage.jsonl`. Claude Code asks are read from `log.jsonl`, so each dollar counts once. `month_total()`, `by_engine()` and `over_cap()` exist; this phase only warns. (file: `chiron/usage.py`)
- **Home state:** `chiron.py --home-state` and `chiron.py --home-do <method>` build the state from `dictation.json`, `log.jsonl`, `usage.jsonl` and `connections.json`, skipping corrupted lines. (files: `chiron/home.py`, `chiron/paths.py`, `chiron/i18n.py`)
- **Language:** pref `lang` (default `en`). `L()` handles native labels and `t()` handles Python's lines. The system prompt ends with "Reply in English." or "Reply in Hindi.".
- **Test DMG in CI:** `.github/workflows/dev-dmg.yml` runs on a macOS 26 runner. It typechecks the Swift, builds with `./build.sh --package`, and attaches an unsigned `Chiron-<branch>-<sha>.dmg` to every push of a `phase-*` branch.

## Decisions I made

- **Look:** Apple-style glassmorphism.
  - Translucent cards over native window vibrancy, a transparent title bar, and SF Pro with Inter and Noto Sans Devanagari as fallbacks.
  - Apple system colours, with button blue darkened to keep 4.5:1 contrast.
  - Reduced transparency and more contrast switch to near-opaque cards.
  - Screenshots of the page against the mock (light, dark, Hindi, Settings, narrow, empty) were taken with headless Chrome. In the real app the backdrop is the desktop's vibrancy, not the painted wallpaper.

- **Glassmorphism instead of the plan's warm paper:** the user asked for an Apple-style, premium glass look on 2026-10-28. The plan's design tokens were updated to match.
- **On-screen Mac names stay in Latin script in the Hindi UI** ("Accessibility", "Notes", "System Settings"), per the user's rule. Chiron's own feature names are translated (Guardian → सुरक्षा). Durations show seconds, not ms.
- **The brain test module is called `brain`:** `chiron.py` and the `chiron/` package share a folder, so `import chiron` gets the package. Tests load the script as `brain`.
- **Swift files are compiled as one module:** build.sh copies `Chiron.swift` to `main.swift` and compiles it with `app/*.swift` and `-module-name Chiron`. Only `main.swift` may hold top-level code, and existing code says `Chiron.settings`.
- **The old SettingsWindow class stays as a controller with no window:** deleting it blind would have broken voice settings, onboarding and shortcut recording.
- **Dictation History… left the menu,** because Home has no history view yet.
- **An older install with a saved server and no brain choice keeps using its server** (brain = custom). Everyone else defaults to Claude Code.
- **The Test button checks a typed key before saving it.** Swift stores it only if the test passes.
- **"Remove key" takes two presses,** so a stray click can't delete a key someone set up for a parent.
- **Feedback reporting was removed** (plan §14). The Apps grant list and `install.sh` are kept for now; `install.sh` now clones `ris3abh/Chiron`.

## How to install this build

You need macOS 26 with the Xcode 26 command line tools, and Python 3. The app won't run on macOS 15.

1. `git checkout phase-1 && ./build.sh`
2. Or, once the branch is pushed, download the DMG from GitHub → Actions → dev-dmg → latest run → Artifacts. Then right-click Chiron → Open the first time.

## Test it now (do these in order)

| # | Do this | You should see | Pass? |
|---|---------|----------------|-------|
| 1 | `git checkout phase-1 && ./build.sh` | "Chiron is running"; a waveform icon in the menu bar; the menu has Open Home and Settings…, and no Meetings or Agents | |
| 2 | Menu bar → Open Home | A glass window: Today says "Nothing due today. Hold fn and ask me anything."; Words spoken, AI spend, Recent; three status dots at the bottom | |
| 3 | Click **हिं** in the header | Every label switches to Hindi at once, with no reload; click EN to switch back | |
| 4 | Gear → Settings → Brain → Claude Code | Installed / signed in / plan lines; **Set up** opens a Terminal with the Claude login if not | |
| 5 | Brain → Anthropic key → paste a real key → Test | "✓ Working · 0.x s · $0.0000x" (under $0.001), then the key shows as `•••• last4` | |
| 6 | Paste a wrong key → Test | "That key was rejected. Check you copied all of it."; nothing saved (the field still offers Save) | |
| 7 | Jev → key → Test | ✓ and the Jev dot turns green; with no key the dot shows the Haiku fallback note | |
| 8 | Keychain Access → search "chiron" | One "Chiron: <name>" item per saved key; `grep -i key ~/.config/chiron/settings.json` shows no key (an older `apiKey` moved on first launch) | |
| 9 | ⌃⌥Space → "open Notes" | Notes opens at once (no AI); Home → Recent shows it within 5 s | |
| 10 | ⌃⌥Space → "what's the weather like in Paris?" | Answer arrives; AI spend rises by that ask's cost | |
| 11 | Hold fn and dictate into TextEdit | Text lands; Words spoken today goes up | |
| 12 | Resize Home to 560 pt wide; toggle dark mode | Tiles stack to one column; the dark glass stays readable | |
| 13 | Settings → Brain → OpenAI → save a key → ⌃⌥Space "what is a PDF?" | An answer with no tools; Today shows the "open-ended Mac tasks need Claude" note | |
| 14 | Brain → Claude Code; `ps eww $(pgrep -f "claude -p" \| head -1) \| tr ' ' '\n' \| grep ANTHROPIC_API_KEY` during an ask | No `ANTHROPIC_API_KEY` (plan billing only) | |
| 15 | `python3 -m unittest tests.test_keychain_native` with `CHIRON_ALLOW_HOST_UI=1` | 2 tests pass (round trip on the `sarvam` account; it restores whatever was there) | |

## Automated tests

- Command: `python3 -m unittest discover -s tests -v` (host-UI guard on).
- Result on this Mac: 577 tests, 62 failures, 4 errors, 22 skipped. Every failure is a Swift test that can't compile here.
- Baseline (the untouched base app v1.5.3, same Mac, see `docs/reports/phase-1-baseline.md`): 844 tests, 98 failures, 6 errors, 23 skipped.

Compared by test name against the baseline:

| Group | Count | What |
|---|---|---|
| Already failing, still failing | 61 | All Swift toolchain failures: `test_native`, `test_dictation`, `test_swift_review_fixes`, `test_prefs_native`, `test_audio_native`, `test_screen_draw`, `test_main_thread`, `test_hands`, `test_fixtures`, `test_dictation_data`, `test_routing_native`, and setUpClass of `test_bg_send_native`, `test_hands_native`, `test_onboarding_page` |
| Fixed by Phase 1 | 4 | All four prompt-budget tests. The system prompt went from 11,103 to 8,286 characters once the agent, Spotify and web.js rules left |
| Removed with their feature | 39 | Agents, agent shelf and agent pages (22), meetings (6), ideas, telemetry, feedback, MiniScreen, the old Settings page, the old box page harness, conversation rename and web frames |
| Introduced by Phase 1 in existing tests | **0** | |
| New tests that can't run here | 5 | `test_key_migration_native` (all 5): they compile Swift, so they fail here with the toolchain error and must pass on macOS 26 / in CI |

New Python tests, all passing here:
- `test_usage`, `test_providers`, `test_jev`, `test_home_state`, `test_llm` and `test_brain_env` (key rule, language rule, OpenAI path).
- `test_strings`, and the static half of `test_home_page`.

Native tests that skip here:
- `test_keychain_native` is host-gated.
- The WebKit half of `test_home_page` needs a working compiler.

## Costs measured

- No paid calls were made while building this phase. No real keys were used, and the provider and Jev tests use recorded responses.
- Cost maths are tested against the price table:
  - The Settings test ask (Haiku, about 20 tokens in, 1 out) costs about $0.00003.
  - One Jev request of about 120 input tokens costs about $0.000005.
- Measure real numbers during steps 5, 7 and 10 above; AI spend on Home shows them.

## Known gaps and risks

- **Swift is uncompiled** (see the top). The riskiest spots:
  - `HomeBridge` and `HomeWindow`, which are new.
  - RoutineWake's new `practice` path.
  - The leftover control flow in `SettingsWindow.apply` after the meeting block left.
  - `Delegate` now returning `.terminateNow`.
  - `WindowTarget`, a text replacement of MiniScreen.
  - `web.underPageBackgroundColor`.
  - `-module-name Chiron`, which is assumed everywhere.
- **The CI workflow has never run.** The `macos-26` runner label and an `Xcode_26*.app` on it are assumptions.
- **Controls with no screen yet:** shortcut recording, the dictation word list, saved memory and dictation history. These still work by voice and through setup, and come back as Settings sections in later phases.
- **Strings may not load under `file://`:** if WebKit refuses XHR there, the page falls back to the `strings.get` bridge call, which is implemented. Fonts fall back to system fonts if blocked; SF Pro is first in the stack anyway.
- **Keychain access after rebuilds:** a rebuild with an ad hoc signature may make macOS ask once before `Chiron --secret get` reads a key. The "Chiron Local Signing" identity from `build.sh` avoids that; the unsigned CI DMG doesn't.
- **Hindi:** the 11 reviewed lines are applied. Two new menu lines are flagged in `ui/strings/hi.review.json` ("Paste Last Dictation", the press-to-talk hint).
- **Jev:** the request shape follows TypeSafe's public docs, but it hasn't been tried with a real key. Noul answers carry no confidence, so distance from 0.5 is used instead.
- **OpenAI-only asks don't see the screen** unless a screenshot was already taken for the ask. Mac tasks need Claude.

## Ready for Phase 2?

- **Not yet.** Phase 2 builds on these windows, the bridge and the speech path, so `./build.sh` should succeed and steps 1–15 should pass on macOS 26 first. The Python side and the page are ready.

---

## Addendum, 2026-10-30: compiled on macOS 27, then redesigned

### Compiled and run
- Mac: macOS 27.2 (arm64), Command Line Tools for Xcode 27.2, Swift 6.4.2, SDK 27.2. (The macOS 15 Mac's toolchain was the only blocker.)
- `swiftc -typecheck …` passes with **no errors and no Swift changes**; 4 harmless warnings (unused results, one deprecation).
- `./build.sh --package /tmp/chiron-pkg` builds and links; `./build.sh` installs `~/Applications/Chiron.app`, signs it with "Chiron Local Signing", adds the LaunchAgent and starts it. Home opened with real data (asks, spend, activity).

### Test fixes (harness bugs, not app bugs)
- `test_key_migration_native`: sliced `Prefs` out of `Chiron.swift` but never put it in the generated program.
- `test_prefs_native.test_settings_are_private_and_usage_counts_final_rows`: needed an `L()` stub, and still expected the agents cost Phase 1 removed; now expects `Today: $0.01`.
- `tests/__init__.py`: every `CHIRON_SECRET_<NAME>` defaults to empty. Once the app is installed, `paths.secret()` would otherwise ask the real app and read the user's Keychain from the test suite (this made `test_chiron.BrainTests.test_custom_server_replaces_claude_sign_in_and_models` fail only on a Mac with Chiron installed).

### Redesign (asked for by Rishabh: "like Wispr Flow", a new logo)
- **Logo:** a C holding a gold guiding star. Source `docs/icon.svg`; `scripts/make-icon.sh` renders `ui/AppIcon.icns` and `docs/icon.png` (needs Chrome). The menu bar icon draws the same mark as a template image (`MenuBar.mark()`).
- **Page (`ui/home.html`):** one page, Home, in a sidebar and one rounded panel, with Settings as a sheet; flat surfaces, the gold accent, serif display type; light/dark with a toggle (pref `theme`: system/light/dark). This replaces the glass design of 2026-10-28.
  - Home: greeting with the real ask shortcut as a keycap, hero card with **Ask Chiron** (`ask.start`), a stats column (words dictated, spend and its limit, connections), the 16-week activity heatmap as the Streak tile, the skills, weak-spots, Guardian and papers tiles (hidden until Phase 4), and asks and dictations in one list grouped by day.
  - Settings: a sheet inside the window (General, Voice and language, Connections, Budget, Permissions, About). The dictionary lives in Voice and language: add, remove (two presses), heard forms shown. The separate Settings window is gone; the menu's Settings… opens the sheet (`bridge.push('settings')`).
- **Bridge:** `dictionary.list/add/remove`, `ask.start`; `prefs.get` also returns the shortcut labels; `theme` is writable and sets the window's appearance.
- **Brain (`chiron/home.py`):** state gains `name` (me.json, else the Mac account's first name), `dictations` (last 10) and `activity` (asks + dictations per day, 16 weeks). Tests in `test_home_state`.
- **Window (`app/HomeWindow.swift`):** one 1180×780 window (min 760×560, saved as `ChironMain`); a transparent `DragStrip` over the page's title strip moves it.
- 63 new strings in `en.json`/`hi.json`; three Hindi lines added to `hi.review.json`.

### Review fixes after the redesign
- "Words" read 0 after 8 voice asks because only dictation counts: the label is now **Words dictated / बोलकर लिखे शब्द** until Phase 2 counts voice asks.
- `VERSION` is 0.1.0 (it was the base app's number); Settings shows "Chiron 0.1.0". `test_repo_fixes` updated.
- Devanagari has no italic: `:lang(hi) em` is upright, and Hindi emphasis is colour and weight.
- ख़र्च everywhere, with a test that flags the spelling without the nukta.
- Three views went back to the plan's one page: the Stats and Dictionary views are gone (first draft of this redesign), see above.
- Jev with no test yet reads "not set up / सेट नहीं है" (`connections.jev.missing`); a failing connection reads "not working / काम नहीं कर रहा". Clicking any status opens Settings → Connections.

### Automated tests now
- `python3 -m unittest discover -s tests -v`: **599 tests, 0 failures, 0 errors, 113 skipped** (host guard on).
- By name against `phase-1-baseline.md`: of the 104 baseline failures/errors, 4 pass, 46 left with their features, 54 now compile but their binaries skip under the host guard.
- **Still unrun on a real screen:** the 106 host-guarded native tests and the WebKit half of `test_home_page` need `CHIRON_ALLOW_HOST_UI=1` (they open windows) or the VM.

### Unverified natively
- The drag strip (moving and double-click zoom) and the menu bar mark were compiled but not looked at; the theme switching the traffic lights likewise.
- Steps 2–15 of "Test it now" still need real keys and permissions; Settings now lives in the sheet, not a separate window.

### Ready for Phase 2?
- **Yes**, per Rishabh on 2026-10-30. Carry the unverified items above into Phase 2's first run.
