# Hand-off: where Chiron stands

Written 2026-10-30 for whoever picks this up next, most likely Claude Code on a Mac running macOS 27. Read `CLAUDE.md` for how to work here, then this file, then `docs/reports/phase-1.md` for the detail.

## Update, 2026-10-30

Phase 1 now compiles and runs on macOS 27.2 (Command Line Tools 27.2), the full suite is green (599 tests, 0 failures), and Home was redesigned as one page in a sidebar window with a new logo. Details: the addendum at the end of `docs/reports/phase-1.md`. Phase 1 is accepted; **next is Phase 2** (Voice Bar and speech). Steps 1–5 below are done except the hands-on test list, which needs real keys and permissions.

## Update, Phase 2 (2026-10-30)

Phase 2 (Voice Bar and on-device speech) is built on branch `phase-2` and running, not yet accepted. Read `docs/reports/phase-2.md`: it needs a person holding fn, and real recordings for the 8 of 10 gate. There is no cloud speech.

## In one paragraph

Phase 1 (Foundation and Home) is built and committed on `main`, but **the app has never been compiled or run.** It was written on a macOS 15.3 Mac whose Swift toolchain is broken (even hello-world fails), and Chiron needs the macOS 26+ SDK. Everything that could be checked there was: the Python brain, the Home/Settings page (rendered in Chrome against the mock), and every test that doesn't compile Swift. The next job is to **compile it, fix what breaks, run it, and walk the Phase 1 test list**, then start Phase 2.

## Where things are

| What | Where |
|---|---|
| Native app | `Chiron.swift` (main file, top-level code) + `app/HomeWindow.swift`, `app/HomeBridge.swift`, `app/Keychain.swift`, `app/Strings.swift` |
| Brain | `chiron.py` (CLI entry, the ask loop) + `chiron/` (`providers`, `jev`, `usage`, `home`, `i18n`, `paths`, `llm`, `prices.json`) |
| The one page | `ui/home.html` (Home + Settings), `ui/strings/{en,hi}.json`, `ui/strings/hi.review.json`, `ui/fonts/` |
| Mock bridge | `tests/home.html` (`?fixture=empty|typical|errors&lang=en|hi&theme=light|dark&view=home|settings&width=…&native=1&chrome=0`) |
| Logo | `docs/icon.svg` → `scripts/make-icon.sh` → `ui/AppIcon.icns`, `docs/icon.png` |
| Box (old overlay, kept until Phase 2) | `ui/ui.html`; setup: `ui/onboarding.html` |
| Plans | `docs/BUILD_PLAN.md`, `docs/PRODUCT_PLAN.md` |
| Reports | `docs/reports/phase-1.md`, `docs/reports/phase-1-baseline.md` |
| CI | `.github/workflows/checks.yml` (Python tests on Ubuntu), `.github/workflows/dev-dmg.yml` (macOS 26 typecheck, build, unsigned DMG artifact) |
| Credits | `CREDITS.md` (the only place the base app is named) |

Data at runtime: `~/.config/chiron/` (`settings.json`, `log.jsonl`, `usage.jsonl`, `dictation.json`, `connections.json`); keys in the login Keychain under `com.chiron.app`.

## What Phase 1 did

- Renamed the base app to Chiron everywhere, and removed telemetry, feedback reports, licensing, the tip jar, ideas, Devin/Pi, Spotify, the web.js adapter, Meeting Copilot, the MiniScreen UI, agents, Nix and the git updater (a stub stays until Sparkle).
- Routines now open a Practice prompt in the box (typed draft; nothing runs until Return).
- Home and Settings in one page, Apple-style glass, English/Hindi, light/dark, live data from `chiron.py --home-state` and `--home-do`.
- Menu bar: Open Home and Settings…, every label through `L()`. The old Settings window and `ui/settings.html` are gone; `SettingsWindow` stays as a windowless controller because voice, setup and shortcut recording call its `apply()`/`record()`/`handle()`.
- Keychain + `Chiron --secret get|set|delete`; the old `apiKey` migrates out of `settings.json` on launch.
- Providers (Claude Code, Anthropic, OpenAI, custom server), Jev client with Haiku fallback, `usage.jsonl` with a monthly cap (warn only).
- Claude Code gets an Anthropic key only when that's the chosen brain; OpenAI-only brain answers without tools.
- Test results at commit time (macOS 15, broken toolchain): 577 tests, 62 failures + 4 errors, **all Swift compiles**; 0 introduced versus the baseline; 4 fixed; 39 removed with their features.

## Do this next, in order

### 1. Get a working toolchain (macOS 27)

```
xcode-select -p                 # should point at Xcode or CLT for Xcode 26 or later
swiftc -version
xcrun --show-sdk-version        # 26.x or later
```
If not: install Xcode (26 or later) from the App Store or developer.apple.com, then `sudo xcode-select -s /Applications/Xcode.app`. `build.sh` requires macOS 26 or later, so 27 passes; it targets `macos26.0`.

### 2. Typecheck and fix compile errors

```
cp Chiron.swift /tmp/main.swift
swiftc -typecheck -module-name Chiron -target "$(uname -m)-apple-macos26.0" /tmp/main.swift app/*.swift
```
Expect some errors: about 1,800 lines of Swift were removed and four files added without a compiler. Most likely spots, from the reports:
- `app/HomeBridge.swift`, `app/HomeWindow.swift` (new): globals `home`, `app`, `onboarding` come from `main.swift`; `web.underPageBackgroundColor`; `Onboarding.plan`, `onboarding.fixPlan()`, `onboarding.grant()`, `detectLocalServers`.
- `SettingsWindow.apply` (meeting block removed), `SettingsWindow.open` (now one line), unused leftovers in that class.
- `RoutineWake` / `App.practice` (new), `WindowTarget` (text replacement of the old MiniScreen class), `Delegate` returning `.terminateNow`, removed hotkey ids 3–5.
- Unused-variable warnings (`dictateFellBack`, `dictateTimedOut`, `dictateReleased`) are fine.
Fix with the smallest change that keeps behaviour, and note each fix for the report.

### 3. Run the full suite on the real toolchain

```
python3 -m unittest discover -s tests -v > /tmp/chiron-tests.txt 2>&1; tail -3 /tmp/chiron-tests.txt
```
On a working toolchain the ~61 Swift tests that failed on the old Mac should now really run. Any that still fail are real: fix them or explain them. Also the 5 tests in `tests/test_key_migration_native.py` (they prove `apiKey` leaves `settings.json`) and the WebKit half of `tests/test_home_page.py` run for the first time. Then, on a Mac where windows may open: `CHIRON_ALLOW_HOST_UI=1 python3 -m unittest tests.test_keychain_native -v`.

macOS 27 notes: the window-sharing test expects `.readOnly` sharing on 27+ (already handled), and menus use `preferredImageVisibility` on 27. Watch for any other 27-only behaviour change and note it.

### 4. Build, run, walk the Phase 1 test list

`./build.sh` installs `~/Applications/Chiron.app`, a LaunchAgent (`com.chiron.app`, starts at login) and a "Chiron Local Signing" identity so permissions survive rebuilds. Then do steps 1–15 in `docs/reports/phase-1.md` ("Test it now"). Things only a person can do: grant Microphone, Speech Recognition, Accessibility, Screen Recording and Automation; paste real Anthropic / OpenAI / Jev keys for steps 5–7 and 13.

Check the glass on real vibrancy (screens were only ever rendered in Chrome with a painted backdrop): if light-mode cards read too white over the desktop, lower `--glass` in `ui/home.html`.

### 5. Report and commit

Update `docs/reports/phase-1.md`: the Swift fixes, real test numbers (compare by name with `docs/reports/phase-1-baseline.md`), measured costs from steps 5, 7, 10, and whether Phase 2 can start. Commit per `CLAUDE.md` (Rishabh's identity, no AI co-author line). Push when Rishabh says so; CI then builds the test DMG (Actions → dev-dmg → Artifacts). The CI workflow has never run: the `macos-26` runner label and `Xcode_26*.app` path are assumptions, so fix it on its first run if needed.

### 6. Then Phase 2 (Voice Bar and speech)

Only when asked: "start-a-phase" for Phase 2, per `docs/BUILD_PLAN.md`. Frontend first (Voice Bar `ui/bar.html` against mocks), then speech locale/normaliser, then wiring.

## Open items for Rishabh

- Two Hindi lines to review in `ui/strings/hi.review.json`: "Paste Last Dictation" and the press-to-talk menu hint.
- Controls that lost their screen with the old Settings window: shortcut recording, the dictation word list, saved memory, dictation history (menu item removed). They still work by voice and in setup; later phases add Settings sections.
- Real keys are needed to measure costs and confirm the Jev request shape (`POST https://api.typesafe.ai/v1/systemone`, from TypeSafe's public docs, never tried live).

## History

`main` starts from a single squashed commit, so the base app's commit history is not in this repository. To pull a fix from upstream, add it as a remote (see `CREDITS.md`) and port the change by hand.
