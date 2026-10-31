# Chiron — Technical Build Plan for Claude Code

Oct 28, 2026 · @Rishabh Sharma

Chiron is built on an MIT-licensed open-source base app; see [CREDITS.md](../CREDITS.md).

## How to use this plan

Give Claude Code one phase at a time; it builds the whole phase, frontend first and backend second, without stopping for sub-steps, and comes back once with a Phase Report that says what was built and exactly how to test it.

The product behind this plan is in the companion doc, *Chiron: A Mac Tutor That Teaches, Then Checks — Product Plan*. When the two disagree, this plan wins for code; the product plan wins for behaviour.

Product plan: Chiron: A Mac Tutor That Teaches, Then Checks — Product Plan. Export both docs as Markdown into the repo as `docs/BUILD_PLAN.md` and `docs/PRODUCT_PLAN.md` before the first run.

### Prompt to start a phase

```text
Read docs/BUILD_PLAN.md (this plan) and docs/PRODUCT_PLAN.md.
Build Phase N completely, following its Frontend, Backend and Integration tasks in order.
Do not stop to ask about sub-steps; make sensible choices and list them in the report.
Stop only if a step is blocked by something you cannot do (a missing key, a macOS
permission only a person can grant, an unavailable API). When Phase N meets its
"Done when" list, write docs/reports/phase-N.md using the Phase Report template
and reply with its contents.
```

### Rules for Claude Code

1. **One phase per run.** Never start the next phase without being asked.
2. **Frontend first, then backend, then wire them.** Every phase begins by building its part of the one page (`ui/home.html`) against a mock bridge with fake data, so the design can be seen before any backend exists. Then the backend lands and the mock is swapped for real data. Frontend and backend are one feature: a phase is not done until the page shows real data.
3. **One page only.** All UI lives in `ui/home.html` (Home view and Settings view) plus the Voice Bar overlay (`ui/bar.html`, from the base app's `ui.html`) and the lesson/warning overlays drawn by Swift. Do not add other pages.
4. **Understand before changing.** Before editing an existing function, read it and its tests. Keep existing behaviour that the plan does not mention.
5. **Keep the tests green.** Run the offline suite (`python3 -m unittest discover -s tests -v`) and the UI mock-bridge pages after every phase. Add tests for every new module. Remove tests only together with the feature they test.
6. **Keep it cheap.** No AI call where code or a saved skill can answer. Batch Jev questions. Respect the system-prompt budget test.
7. **Every user-facing string goes through i18n** (`ui/strings/en.json`, `ui/strings/hi.json`, and `chiron/i18n.py` for spoken lines). No hard-coded English in UI or speech.
8. **No secrets in files.** Keys go to the macOS Keychain only. Never commit keys, personal settings or runtime state.
9. **Commit at the end of each phase** on a branch `phase-N`, with a summary commit message.
10. **The report is the hand-off.** Be specific: real file names, real commands, real clicks, real expected results.

## Upstream map

The base app (v1.5.3) is a native Swift menu-bar app that starts a fresh Python subprocess for every ask; Python drives `claude -p`, prints one tagged line per event, and calls back into the Swift binary through CLI flags. Line numbers below are `file:line` in the upstream source at v1.5.3: `upstream.swift` is its Swift source and `upstream.py` its Python brain, now `Chiron.swift` and `chiron.py` (Phase 1 renamed and trimmed them, so line numbers have moved). Env vars, folders and labels are given with their Chiron names.

### 1. Process model and wire protocol

- **Swift starts Python** with `py(args, extra)` (`upstream.swift:606`): `/bin/sh <Resources>/upstream.py <args>`, PATH prefixed with Homebrew, `CHIRON_APP=<native binary>`. No long-lived brain, except the agents supervisor `--agents`.
- **Main ask:** `App.spawn()` (`:3262`) starts `upstream.py --wait` at key-down, so Claude boots while the user talks (`start_ai()` in `main()`, `upstream.py:7501`). When the transcript is final, `App.run()` (`:3367`) writes `go` to the `CHIRON_COMMIT` file and sends one stdin JSON line `{front, task, remaining?, done?, point?, drawing?, agentCard?}`. `wait_commit()` (`upstream.py:653`) holds every tool until then (up to 90 s).
- **Output:** `say(tag, text)` (`upstream.py:3556`) prints `"<tag> <text>"`; Swift parses lines at `upstream.swift:3269-3340`.

| Tag | Meaning | Swift does |
| --- | --- | --- |
| `✓` | Final answer | `ui.line`, then speak or copy |
| `…` | Streaming partial | `ui.line` |
| `▸` / `·` / `i` | Step label / status / tip | `ui.line` |
| `✎ <json>` | Drawing request (or memory receipt) | `drawing.receive` |
| `@ x y` | Point at a spot | ring and leader |
| `? q\tcmd\tfile…` | Allow card | `ui.ask`, answer written to `answers/<uuid>` |
| `◇ <json>` | Choices card | `ui.pick` |
| `⚙ key value` | Change a pref (never `paused`; `safe` only on) | `settings.apply` |
| `▣ <json>` | MiniScreen frame | `mini.receive` |
| `⇢`, `⤴`, `▤` | Agent hand-off | agents UI |
| `! setup` / `! <text>` | Open onboarding / error | onboarding / `ui.msg` |

- **Python → native:** Python runs the app binary with flags: `--hands <verb…>` (`:7262`), `--look N path [windowID]` (ScreenCaptureKit, `:4318`), `--text app [words]` (Vision OCR, `:4349`), `--type` (`:7316`), `--draw-target` (`:7263`), `--window-target` / `--target-app` (`:7283`), `--calendar` (`:7253`), `--raise` (`:7250`), `--selftest` (`:7307`).
- **Python CLI** (`main()`, `upstream.py:7195-7497`): `--wait`, `--fast`, `--draw`, `--look`, `--hands`, `--window`, `--type`, `--show`, `--state`, `--budget`, `--gate`, `--set`, `--pick`, `--remember`/`--rule`/`--forget`, `--me …`, `--shortcut`/`--unlearn`, `--routine …`, `--watch`/`--unwatch`, `--models`, `--local-servers`, `--check`, `--dictate-cleanup[-wait]`, meeting and agent flags, `--selftest`. Unknown flags exit 2.

### 2. WebView bridge

- `callJS(web, fn, args)` (`:636`) evaluates `fn(...json)`. `loadPage` (`:642`) inlines `orbs.js` at `/*ORBS*/` and loads with `baseURL: nil`.
- **Overlay `ui.html`:** handlers `h` (height or `[w,h]` for the pill) and `c` (commands, `:2175-2258`). Swift calls `window.ui.*` (`ui.html:743`): `listen, words, think, line, msg, ask, pick, dictate, locked, level, finishing, dictated, learned, point, reset, …`.
- **`settings.html`:** handler `st` (`:4746`), page posts `{do: …}` handled in `SettingsWindow.handle` (`:4952-5054`): `set{k,v}`, `record`, `unlearn`, `me`, `remember`, `models`, `localServers`, `grant`, `globeKey`, `checkUpdate`, … Swift calls `st.load`, `st.state`, `st.dictation`, `st.perms`, `st.models`, … (`settings.html:903-990`). Ten tabs (`settings.html:274-493`): dictation, general, brain, memory, usage, apps, account, meetings, about, feedback.
- **`onboarding.html`:** handler `ob`; pages `welcome perms agents try mac text dictate point work meeting improve tip done`.

### 3. Prefs and data files

- **Prefs** are JSON in `~/.config/chiron/settings.json`, not UserDefaults: Swift `Prefs.set` (atomic, `0600`, `:186-230`, defaults `:188-199`), Python `pref()` / `save_pref()` (`upstream.py:397-411`). UserDefaults `com.chiron.app` holds only `onboarded`, `askedAX`, `askedScreen`, `allowedApps`, window autosave.
- **Files** in `DIR` (`upstream.py:38`, overridable with `CHIRON_DIR`):

| File | Writer | Use in Chiron |
| --- | --- | --- |
| `dictation.json` | `DictationData` (`:23-74`): `{history, words, sessions, todayWords, day, seconds}`; time saved = 40 wpm typing baseline (`:55-65`) | Words spoken tile (extend to voice asks) |
| `log.jsonl` | `log_turn()` (`upstream.py:3624`): `id, at, task, reply, usd, secs, steps, model, path(model/instant/shortcut), escalated, status…` | Recent tile, AI spend, cap |
| `skills.json` | `save_skills()` (`:1789`): `{task: {cmds, reply, at, used?, asked?, mine?}}`; non-`mine` entries expire in 30 days | Extended into skill cards |
| `memory.md`, `me.json` | `remember_rule()` (`:6012`), `profile_*` (`:245-344`) | Household memory |
| `routines.json`, `routine-queue.jsonl` | `routine_add/fire/pop` (`:3208-3315`) | Practice reminders |
| `recent.jsonl`, `chats.json`, `workflows.json` | `remember_turn`, `update_chats`, `workflows` | Keep |
| `meetings/`, `agents/`, `answers/` | Meeting, agents, cards | Remove first two; keep `answers/` |

### 4. Hotkeys

- Carbon `RegisterEventHotKey` (`:7426-7434`): id 1 talk, 2 Esc, 3/4 Return, 5 ⌃⌥↩ move-to-agent, 6 dictation, 7 ⌃⌘V.
- fn and modifier-only chords use `NSEvent` global plus local monitors on `.flagsChanged/.keyDown/.keyUp` (`refreshSpecialHotkeys` `:7484`, `updateSpecialHotkey` `:7457`); no CGEventTap. `chironFnKey = 1<<20` (`:541`).
- Default dictation key is fn alone (`:212-215`). `globeKeyTaken()` (`:563`) reads `AppleFnUsageType` from `com.apple.HIToolbox`.
- Talk mode `hold|toggle` (`:2710`); hold stops 0.15 s after release; taps under 0.3 s close quietly; 60 s cap.

### 5. Speech and voice

- `App.speechModule(dictate:)` (`:1804`): `SpeechTranscriber` (presets `.progressiveTranscription`) or `DictationTranscriber` when pref `speechModel == "dictation"`. Assets via `AssetInventory` (`prepareSpeech`, `:1813`).
- **Locale hardcoded** to `en-US` at `:1805` (and meetings `:5524`), with the comment that the Mac's own locale was rejected as unsupported in 1.5.0.
- `beginSpeechSegment` (`:2610`) passes contextual strings (dictionary, names, skills, apps, `:1907`); finals and volatiles stitched in `speechPiece` (`:2639`); `heard()` (`:2770`) drives live words, `tryFast` and `startAhead`; `stop()` (`:2862`) finalises with a 2 s timeout.
- **TTS:** `/usr/bin/say` with `readAloudArguments` (`:533`); voice from the `voice` pref, else Spoken Content selection by `NLLanguageRecognizer` language, else best English voice (`:472-512`). `spoken()` (`:453`) strips Markdown.

### 6. Overlay and pill

- Main panel (`:1791`, `:2082-2087`): `KeyPanel`, `[.nonactivatingPanel, .borderless]`, level `.statusBar`, `[.canJoinAllSpaces, .fullScreenAuxiliary]`, HUD blur. App is `.accessory` with `LSUIElement`.
- `show()` (`:2296`) opens at the top corner of the pointer's screen; `followPointerScreen` (`:1970`) follows displays.
- `pill(on)` (`:2372`) shrinks the panel to a pill sized by the page; states in `ui.html` `pill()` (`:441`): listening, finishing, done, said.

### 7. Draw on screen

- Schema: Swift `:862-878`, Python validator `drawing()` (`upstream.py:6079`). `{steps: [1..12]}`; step `{id, say, target, shapes[1..40], wait, hit[x,y,w,h], screen, timeout 5–120}`; shape kinds `rect circle arrow line path label pointer text`; colours red, blue, green, yellow, white.
- `draw()` (`upstream.py:6153`) emits `✎ <json>` and waits 5 s for a receipt; `ScreenDrawing.receive` (`:1277`) shows one `DrawingPanel` per screen.
- Advance: mouse-down monitors (`:1281-1296`) count clicks only on the target window; `clicked()` (`:1508`) requires a hit inside `hit` when `wait`; `tick()` (`:1520`) also advances when an AX value changes; `drawing.next()` (`:3203`) on voice "next". `target` labels resolve each step via `Hands.drawAnchor` (`:6344`). Callouts: `DrawingCalloutView` (`:1011`) with Back, Next, Close.

### 8. Hands

- `enum Hands` (`:5952-7247`): `capture()` (`:6271`) builds an accessibility map with secrets masked; `resolve()` (`:6386`) by label, id or point; click via AX actions first, else SkyLight background mouse (`:6517-6560`); keys (`:6499`); menus (`:6451`); scroll, drag, type, type-after, wait.
- Python syntax (`hands()`, `upstream.py:2890`): `see | menu <app> "A > B" | click <target> [near] [double] [right] [front] | scroll … | press "cmd+t" | drag | type <field> "text" [submit] | type-after | wait`. Native side prints a check JSON; Python authorises risky actions (`hands_action`, `:2849`).

### 9. Model calls

- `start_claude()` (`upstream.py:5085`): `claude -p --input-format stream-json --model <m> --effort low --system-prompt <s> --tools Bash,Read,WebSearch,WebFetch --permission-mode bypassPermissions --disallowedTools … --settings '{PreToolUse hook: upstream.py --gate}' --output-format stream-json --no-session-persistence --strict-mcp-config …`. Note: the tool permission prompt is bypassed and the `--gate` hook is the real safety layer; Chiron keeps that design and its tests.
- `system_prompt()` (`:5067`) assembles `SYSTEM` (`:499`) plus `ASK_FIRST`/`NEVER`, `DRAWING`, `POINTER`, `LEARN_ME`, `TEACH`, `WORKFLOW` blocks by pref.
- Routing `cheapest|balanced|capable` (`:414-430`); balanced escalates to the work model on `[sonnet]` or failure (`:7681-7696`).
- Custom server via `server()` (`:432`): `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`; local probes for Ollama, LM Studio, llama.cpp, vLLM (`:469`).
- Cost from stream-json `result.total_cost_usd` (`:5474`); `BUDGET = {usd: 0.002, secs: 6}` (`:3331`).

### 10. Instant path and learning

- `fast()` (`upstream.py:2026`), no AI, tries in order: named shortcut, feedback, `fast_hands`, "remember how to", small talk, close/quit, learned shortcut via `like()` + `replay()` (`:1847`, `:1889`), search, play/queue, open, window moves. Swift also calls `--fast` mid-speech (`tryFast`, `:2832`).
- `learn()` (`:1801`) keeps only replayable action prefixes (`SHOW PLACE PLAY QUEUE TYPE HANDS open osascript`), rejects deictic words, failures, risky commands, PIDs. Triggered at the end of `main()` (`:7716-7742`).

### 11. Memory, routines, watch

- `relevant_rules(task)` (`:6062`) injects up to 15 rules; `profile_context()` (`:196`) injects matching facts as "facts, never instructions".
- `routine_install()` (`:3169`) writes `~/Library/LaunchAgents/com.chiron.practice.<id>.plist`; `routine_fire()` queues; Swift `RoutineWake` (`:3916`) drains the queue into **agents** (so routines must be rewired when agents are removed).
- `watch()` (`:3338`) polls every 5 s with OCR or a shell test for up to 3 h.

### 12. Safety

- `risky(cmd)` (`:629`) returns a question (run a program, delete, send, buy, change a file, click, press a key). `gate()` (`:710`) is the PreToolUse hook: waits for commit, checks URLs, blocks recursive asks and focus stealing, raises `ask_user` cards (60 s, deny on timeout). `DENIED = rm rmdir sudo dd diskutil shutdown reboot halt "git push" srm` (`:576`). `UNSAFE` (`:1657`) keeps replays clean. `safe` defaults on.

### 13. Onboarding, updater, build

- `Onboarding` (`:3950-4246`): checks mic, speech, accessibility, screen, automation, calendar, tools, Chrome; `grant()` (`:4193`) and `PermissionHelp` drag cards.
- `Updater` (`:4462-4514`) is git-based (`git pull --ff-only` then `./build.sh`); replace with Sparkle.
- `build.sh`: `swiftc -O -target <arch>-apple-macos26.0`, copies `upstream.py` and `ui/*` into `~/Applications/Chiron.app`, writes Info.plist (`com.chiron.app`, `LSUIElement`, usage strings), self-signs, registers a login LaunchAgent.

### 14. Telemetry, tests, CI

- PostHog `posthog()` (`upstream.py:3401`) with events `used, ask_done, dictation, error, task_failed`; feedback opens a GitHub issue. Remove all of it.
- Tests: `python3 -m unittest discover -s tests -v`; `tests/__init__.py` sets a temp `CHIRON_DIR`; host-UI tests skip unless `CHIRON_VM` or `CHIRON_ALLOW_HOST_UI`; page tests load real `ui/*.html` in an off-screen WKWebView; `tests/ui.html` and `tests/settings.html` are mock bridges; `tests/evals/` has a scripted-Claude harness. CI (`checks.yml`) runs the suite on Ubuntu plus `bash -n` on scripts.

### 15. Keep, change, remove

| Area | Decision | Notes |
| --- | --- | --- |
| Speech, hotkeys, Hands, Draw on screen, `look`, `fast`/`learn`, gate/risky, Prefs, wire protocol | Keep | Core; change the speech locale only |
| `DictationData`, `log.jsonl`, `--state`, `--budget` | Keep and extend | Feed Home |
| Overlay `ui.html` | Change | Becomes the Voice Bar (`ui/bar.html`) |
| `settings.html`, `onboarding.html` | Replace | By `ui/home.html` (Home and Settings views) and a slimmer onboarding |
| Routines | Keep, rewire | Drain the queue into a Practice prompt, not agents |
| Updater (git), Nix, `install.sh` | Replace | Sparkle and DMG |
| Meeting Copilot (`:5080-5950`, `upstream.py:6492-7177`, `ui/meeting.html`) | Remove | Keep `meeting_call()` logic, because dictation cleanup reuses it: move it to `chiron/llm.py`. Keep `MeetingFrame.clamp/follow`, used by other panels |
| Agents (`class Agents` `:4463`, `AgentPanels` `:3424`, `ui/agents.html`, `⇢ ⤴ ▤` tags) | Remove | After rewiring routines; Paper Studio runs in the main worker |
| MiniScreen UI (`:1539-1783`) | Remove UI | Keep `windowTarget`/`bounds` helpers used by `--draw-target` and Hands |
| Devin, Pi, Spotify helpers, `web.js` adapter, Gumroad, Ko-fi, ideas, Apps grant list, PostHog | Remove | Delete with their tests |

## Target layout and conventions

Chiron keeps the base app's process model and wire protocol unchanged, renames everything user-visible, and puts new code in new files so the core stays easy to diff against upstream.

### Names

| Thing | Upstream | Chiron |
| --- | --- | --- |
| Repo | upstream repository | `Chiron` (keep the upstream remote) |
| App | upstream app and bundle id | `Chiron.app`, `com.chiron.app` |
| Native source | `upstream.swift` | `Chiron.swift` (the trimmed core) + new files in `app/` |
| Brain | `upstream.py` | `chiron.py` (the trimmed core) + package `chiron/` |
| Data folder | upstream data folder and env var | `~/.config/chiron`, `CHIRON_DIR` |
| Env vars | upstream prefix | `CHIRON_*` (one mechanical sweep in Phase 1, tests updated in the same commit) |
| Distributed notification | upstream name | `chiron.raise` |
| LaunchAgents | upstream app and routine labels | `com.chiron.app`, `com.chiron.practice.<id>` |

### Repository layout

```text
chiron-mac/
├── Chiron.swift              # upstream.swift minus removed features
├── app/
│   ├── HomeWindow.swift      # NSWindow + WKWebView for ui/home.html (Home and Settings views)
│   ├── HomeBridge.swift      # 'home' message handler: request/response + push events
│   ├── Keychain.swift        # SecItem wrapper + `Chiron --secret get|set|delete <name>`
│   ├── Strings.swift         # L("key") from ui/strings/<lang>.json for native labels
│   ├── VoiceBar.swift        # always-on bar panel (Phase 2)
│   ├── SpeechLocale.swift    # locale probe + cloud fallback recorder (Phase 2)
│   ├── Lesson.swift          # lesson runner on top of ScreenDrawing (Phase 3)
│   ├── GhostHand.swift       # demonstration pointer (Phase 4)
│   └── GuardianWatch.swift   # new-window observer + warning card (Phase 4)
├── chiron.py                 # upstream.py minus removed features; CLI entry
├── chiron/
│   ├── __init__.py
│   ├── paths.py              # CHIRON_DIR, file names, private_json helpers
│   ├── i18n.py               # t(key, lang, **vars) from ui/strings
│   ├── providers.py          # ClaudeCode, Anthropic, OpenAI, CustomServer behind one interface
│   ├── jev.py                # TypeSafe client, batching, Haiku fallback
│   ├── usage.py              # usage.jsonl, month totals, cap
│   ├── home.py               # builds the Home state JSON
│   ├── speech_cloud.py       # Sarvam client (Phase 2)
│   ├── normalize.py          # language normaliser + household dictionary (Phase 2)
│   ├── router.py             # Jev routing (Phase 3)
│   ├── skills.py             # skill cards, attempts (Phase 3)
│   ├── lessons.py            # plan, run, check, hint (Phase 3)
│   ├── practice.py           # schedule, mastery, weak spots, drills (Phase 4)
│   ├── guardian.py           # rules, Jev scoring, block list (Phase 4)
│   └── papers.py             # style note, paper JSON, docx builder (Phase 5)
├── ui/
│   ├── home.html             # THE one page: Home view + Settings view
│   ├── bar.html              # Voice Bar (from ui.html)
│   ├── onboarding.html       # slimmed upstream onboarding
│   ├── strings/en.json, strings/hi.json
│   ├── fonts/                # Inter, Noto Sans Devanagari (woff2, OFL)
│   └── orbs.js
├── tests/                    # upstream tests kept + test_home_page.py, tests/home.html mock, new module tests
├── docs/BUILD_PLAN.md, docs/PRODUCT_PLAN.md, docs/reports/
├── build.sh                  # local dev build (compiles Chiron.swift + app/*.swift)
└── .github/workflows/checks.yml, release.yml
```

`build.sh` changes from `swiftc upstream.swift` to `swiftc -O -target <arch>-apple-macos26.0 Chiron.swift app/*.swift`, and copies `chiron.py`, `chiron/`, `ui/` (including `strings/` and `fonts/`) into `Contents/Resources`.

### Bridge between `ui/home.html` and Swift

One handler, `home`, registered by `HomeWindow`. The page never talks to Python directly.

- **Request/response:** the page calls `bridge.call(method, args)`, which posts `{id, method, args}` and returns a Promise. Swift answers with `callJS(web, "bridge.reply", [id, result, error])`.
- **Push:** Swift sends live updates with `callJS(web, "bridge.push", [event, data])`. Events: `state` (full Home state), `lang`, `connection`, `voice`, `lesson`, `guardian`.
- **Python side:** Swift runs `chiron.py --home-state` (prints one JSON object) and `chiron.py --home-do <method>` (JSON args on stdin, JSON result on stdout), using the existing `py()` helper. Methods that only touch native things (Keychain, permissions, opening System Settings) stay in Swift.
- **Mock bridge:** `tests/home.html` loads `ui/home.html` in an iframe and fakes `window.webkit.messageHandlers.home` with canned state, the same way `tests/settings.html` mocks the base app Settings today. Every phase's frontend is built and reviewed against it first.

### Loading the page

The base app's `loadPage` (`upstream.swift:642`) loads HTML with `baseURL: nil` and inlines `orbs.js`. Chiron extends it: load `home.html` with `baseURL` set to `Contents/Resources/ui/` so `strings/*.json` and `fonts/*.woff2` load as relative files, and keep the page free of any network access (add a CSP meta tag: `default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'`).

### Keys and secrets

- Keys are stored only in the Keychain (service `com.chiron.app`, accounts `anthropic`, `openai`, `jev`, `sarvam`, `custom`).
- Python reads a key by running `Chiron --secret get <name>` (new native CLI flag beside `--hands`), never from `settings.json`.
- Migration: the base app kept `apiKey` in `settings.json`; Phase 1 moves any value found into the Keychain and deletes it from the file.

### Coding rules

- Swift: no new third-party dependencies except Sparkle (Release). Python: standard library plus `httpx`, `python-docx`, `pdfplumber` (vendored into the bundle at Release).
- Every new Python module has a unit test file; every new bridge method has a mock-bridge test.
- Keep the base app's comment style: say *why*, not what.

## The one page: Home and Settings

`ui/home.html` is a single self-contained file with two views, Home and Settings; it grows one tile or section per phase, always renders from one state object, and is translated by swapping one strings file.

### Windows

- **Home window:** a normal titled `NSWindow` (880 × 720 pt default, min 640 × 560, remembers its frame), opened from the menu bar item, the Dock icon (switch the activation policy to `.regular` while it is open, back to `.accessory` when closed), the Voice Bar menu, or by voice ("open Home").
- **Settings window:** the same page loaded in a second, smaller window (560 × 680 pt) with `#settings` in the URL, so it opens straight to the Settings view. A gear on Home opens it. Only one instance of each.

### Layout of the Home view (top to bottom)

1. **Header:** Chiron wordmark (left); language switch **EN | हिं** and gear (right).
2. **Today card** (full width, the only accented element): next practice or "Nothing due today", one primary button.
3. **Row of three tiles:** Words spoken · Skills learned (constellation) · Weak spots.
4. **Row of four small tiles:** Streak · Guardian · Papers · AI spend.
5. **Recent:** last 10 events, newest first.
6. **Footer:** connection health dots (Brain, Jev, Speech) that open Settings when clicked.

Tiles that a phase has not built yet are hidden, not greyed out. Below 720 pt wide the rows stack into two columns, below 560 pt into one.

### Settings view sections

Connections · Budget · Voice and language · Practice · Guardian · Permissions · Privacy · About. A left list on wide windows, a single scrolling column on narrow ones. Every control saves immediately (no Save button) and shows a quiet "Saved" tick.

### Design tokens

The look is Apple-style glassmorphism (macOS Tahoe "Liquid Glass"): translucent layered panels over native vibrancy. The user chose this over the earlier warm-paper look on 2026-10-28.

```css
:root {
  --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", "Noto Sans Devanagari", system-ui, sans-serif;
  --body: 17px;  --small: 15px;  --title: 26px;  --big-number: 44px;
  --radius: 22px;  --radius-sm: 12px;  --gap: 22px;  --pad: 24px;
  --blur: blur(30px) saturate(180%);  --ease: cubic-bezier(.2,.8,.2,1);  --dur: 220ms;
  --ink: #1D1D1F;  --ink-2: #48484D;  --ink-3: #6E6E73;
  --glass: rgba(255,255,255,.58);  --glass-strong: rgba(255,255,255,.80);  --glass-hero: rgba(255,255,255,.72);
  --hairline: rgba(255,255,255,.55);  --highlight: inset 0 1px 0 rgba(255,255,255,.75);
  --accent: #007AFF;  --accent-fill: #0068DA;  --accent-text: #0062CC;   /* fill/text tints keep ≥ 4.5:1 */
  --good: #34C759;  --good-text: #1E7F3A;  --warn: #FF9F0A;  --warn-text: #9A5700;
  --danger: #FF3B30;  --danger-text: #C4271C;
}
/* Dark (prefers-color-scheme, or [data-theme="dark"] on <html>, which overrides the media query) */
:root[data-theme="dark"] {
  --ink: #F5F5F7;  --ink-2: #C7C7CC;  --glass: rgba(38,38,44,.55);  --glass-strong: rgba(58,58,64,.78);
  --hairline: rgba(255,255,255,.12);  --accent: #0A84FF;  --accent-fill: #0064D2;  --accent-text: #4DA3FF;
  --good: #30D158;  --danger: #FF453A;  --danger-text: #FF6961;
}
@media (prefers-reduced-transparency: reduce), (prefers-contrast: more) {
  :root { --glass: var(--solid-card); --hairline: var(--solid-line); --blur: none; }   /* near-opaque, firm edges */
}
@media (prefers-reduced-motion: reduce) { :root { --dur: 0ms; } }
```

- Every surface is one glass recipe: `--glass` fill, `backdrop-filter: var(--blur)` (plus `-webkit-`), 1 px `--hairline` border, `--highlight` inner top edge, soft layered shadow. The Today card is the hero: more opaque glass with a gentle accent glow. Segmented controls are macOS pills with a raised glass thumb; switches are iOS-style; status dots glow softly.
- In the app, `HomeWindow` adds `html.native`, puts an `NSVisualEffectView` behind a transparent WKWebView (`drawsBackground = false`) and uses a full-size transparent title bar. Under `html.native` the page draws no background and the header gets ~30 px top padding to clear the traffic lights. Anywhere else (browser, mock, screenshots) the page paints a soft mesh-gradient wallpaper so the glass reads. The mock's `native=1` simulates the window.
- Body 17 px minimum; buttons at least 44 px tall; focus rings always visible; every tile reachable by Tab.
- Hindi strings run about 20% longer: no fixed-width labels; text wraps, never truncates.
- Big numbers use tabular figures and the locale's digit grouping (`Intl.NumberFormat(lang)`).

### Components

`Tile(title, body, action?)`, `BigNumber(value, label)`, `Constellation(skills[])` (inline SVG; star radius 3–7 px by mastery; lines between stars of one app when all are mastery 5), `WeakSpot(concept, count, action)`, `SpendBar(spent, cap)`, `StatusDot(ok|warn|off, label)`, `KeyField(name, masked, onSave, onTest)`, `Switch`, `Segmented`, `Toast`. Plain JS, no framework, no build step.

### Strings and the language switch

- `ui/strings/en.json` and `ui/strings/hi.json` hold every label as flat keys (`home.today.title`, `settings.conn.jev.help`). Keys must match; a test fails on any missing key.
- The switch calls `bridge.call("lang.set", {lang})`. Swift saves pref `lang`, re-labels native menus and the Voice Bar via `L()`, and pushes `lang` to every open page. Python reads `pref("lang")` for spoken lines and Claude's reply language.
- Switching never reloads the page: `applyStrings(lang)` replaces text in every `[data-i18n]` element, and the state is re-rendered.
- Numbers, dates and relative times use `Intl` with `en-IN` or `hi-IN`.
- On-screen names (apps, menus, buttons, System Settings labels) are copied exactly as the Mac displays them, in its script: "Accessibility", "Notes", "System Settings" stay in Latin letters in the Hindi UI unless the Mac itself shows a Hindi label, in which case copy that label exactly. `test_strings.py` allows these words in `hi.json`.
- Chiron's own feature names are translated in the Hindi UI (Guardian → सुरक्षा) but keep their English names in code, keys and file names.
- Durations show seconds, not milliseconds, in both languages ("Working · 0.6 s · $0.0001").

### Home state (`chiron.py --home-state`)

```json
{
  "lang": "en",
  "today": {"kind": "practice", "skill": "youtube-play", "title": {"en": "…", "hi": "…"}, "minutes": 2},
  "words": {"today": 0, "week": 0, "all": 0, "minutes_saved": 0, "langs": {"en": 0, "hi": 0}},
  "skills": [{"id": "youtube-play", "app": "YouTube", "title": {}, "mastery": 2}],
  "weak": [{"concept": "open-app", "label": {}, "misses": 3}],
  "streak": 0,
  "guardian": {"month": 0, "last": null},
  "papers": {"count": 0, "last": null},
  "spend": {"month_usd": 0.0, "cap_usd": 5.0, "by_engine": {}},
  "recent": [{"at": "…", "kind": "lesson|do|practice|guardian|paper|ask", "text": {}}],
  "connections": {"brain": {"kind": "claude-code", "ok": true}, "jev": {"ok": false}, "speech": {"engine": "apple", "ok": true}}
}
```

Each phase fills its own keys; missing keys hide their tile.

### Bridge methods

| Method | Args → result | Handled in | Phase |
| --- | --- | --- | --- |
| `state.get` | → Home state | Python `--home-state` | 1 |
| `lang.set` | `{lang}` → `{ok}` | Swift + Python | 1 |
| `prefs.get` / `prefs.set` | `{k, v}` → `{ok}` | Swift `Prefs` | 1 |
| `conn.list` | → status per connection | Swift + Python | 1 |
| `conn.save` / `conn.clear` | `{name, value?}` → `{ok}` | Swift Keychain | 1 |
| `conn.test` | `{name}` → `{ok, detail, ms, usd}` | Python `--home-do conn.test` | 1 |
| `brain.choose` | `{kind: claude-code \| anthropic \| openai \| custom}` | Swift `Prefs` | 1 |
| `claudeCode.status` / `claudeCode.setup` | → `{installed, signedIn, plan}` / opens login script | Python `claude_plan()` + the base app's `fixPlan` | 1 |
| `local.scan` | → local servers | Python `local_servers()` | 1 |
| `perms.get` / `perms.grant` | `{id}` | Swift `Onboarding` checks | 1 |
| `voice.test` | → records 5 s, returns transcript + engine | Swift | 2 |
| `voices.list` / `voice.preview` | `{lang}` | Swift | 2 |
| `lesson.start` | `{skill?, ask?}` | Swift + Python | 3 |
| `practice.start` / `drill.start` | `{skill}` / `{concept}` | Swift + Python | 4 |
| `guardian.list` / `guardian.unblock` | `{domain}` | Python | 4 |
| `papers.addSamples` / `papers.open` / `style.get` / `style.set` | files, path, rules | Swift picker + Python | 5 |
| `data.export` / `data.delete` | → zip path / `{ok}` | Python | 5 |
| `updates.check` | → Sparkle | Swift | Release |

## Phase 1 — Foundation and Home

Phase 1 turns the base app into Chiron: renamed, trimmed of everything not needed, with the Home page and Settings window live, the English/Hindi switch working end to end, and every connection (Claude Code, Anthropic, OpenAI, custom server, Jev) saved in the Keychain and testable.

### Frontend (build first, against the mock bridge)

1. Create `ui/home.html` with the header, Today card (empty state: "Nothing due today. Hold fn and ask me anything."), and these tiles: **Words spoken** (from the base app's dictation counters), **AI spend**, **Recent**, plus the footer connection dots. Other tiles stay hidden.
2. Build the **Settings** view with these sections:
   - **Connections → Brain:** a four-option chooser with one card per option.
     - *Claude Code (uses your Claude plan):* status lines for installed, signed in and plan; a **Set up** button.
     - *Anthropic API key:* key field, **Test**.
     - *OpenAI API key:* key field, **Test**, plus the note "Lessons, papers and questions work; open-ended Mac tasks need Claude".
     - *Custom server:* address, key, model picker, **Find local servers**.
   - **Connections → Jev:** key field, base URL (advanced, collapsed), **Test**, and a link to TypeSafe.
   - **Budget:** monthly cap slider ($1–$50, default $5) and "spent this month".
   - **Voice and language:** the app language (same as the header switch).
   - **Permissions:** Microphone, Speech Recognition, Accessibility, Screen Recording, Automation, each with a status and a **Grant** button.
   - **About:** version and build.
3. Key fields show `•••• last 4` once saved, with **Replace** and **Remove**. **Test** shows a spinner, then ✓ with latency and cost, or a plain-language error ("That key was rejected. Check you copied all of it.").
4. Write `ui/strings/en.json` and `ui/strings/hi.json` for every Phase 1 string. Hindi must be natural, not word-for-word; mark any uncertain line with `"_review": true` in a side file `ui/strings/hi.review.json`.
5. Add `tests/home.html` (mock bridge) with three fixtures (`empty`, `typical`, `errors`), and a fixture switcher at the top. Review the design in a browser at 1280, 880 and 560 px wide, light and dark.
6. Bundle Inter and Noto Sans Devanagari as woff2 in `ui/fonts/` with their OFL licences.

### Backend

1. **Fork and rename.** Fork into this repository; rename files, bundle id, data folder, env vars, notification and LaunchAgent labels as in *Target layout*. Keep `LICENSE-Plip`; `LICENSE` carries Chiron's copyright, and the base app's MIT notice lives in `CREDITS.md`.
2. **Strip removed features** in this order, running tests after each: PostHog and failure reports → Gumroad, Ko-fi, tips, ideas → Devin and Pi → Spotify helpers and `web.js` adapter → Meeting Copilot (move `meeting_call()` / `meeting_process()` into `chiron/llm.py` first, because dictation cleanup uses them; keep `MeetingFrame.clamp/follow`) → MiniScreen UI (keep `windowTarget` / `bounds`) → agents (first rewire `RoutineWake` to post a Practice prompt into the Voice Bar flow instead of `agentsUI`; remove `MainMove` and the `⇢ ⤴ ▤` tags) → Nix files and the git `Updater` (leave a stub; Sparkle comes in Release). Delete each feature's tests with it.
3. **Keychain.** Add `app/Keychain.swift` and the native flag `Chiron --secret get|set|delete <name>`. On first launch, move any `apiKey` from `settings.json` into the Keychain and remove the key from the file.
4. **Providers.** `chiron/providers.py` with `Provider.ask(system, messages, model, images=(), max_tokens, json=False) -> Reply(text, usd, input_tokens, output_tokens, ms)`:
   - `AnthropicProvider`: HTTPS Messages API, prompt caching on the system block, cost computed from a price table in `chiron/prices.json` (editable, dated).
   - `OpenAIProvider`: HTTPS API, JSON mode, same price table.
   - `CustomServerProvider`: wraps the base app's `server()` settings.
   - `ClaudeCodeProvider`: `claude -p` single-shot for JSON tasks.
   - The **open-ended main ask** (the base app's `start_claude()` tool loop) keeps running through Claude Code. When the brain is an Anthropic key, start Claude Code with `ANTHROPIC_API_KEY` from the Keychain (upstream blanked it in `server()` and popped it before `claude` ran — Phase 1 changed both). When the brain is OpenAI-only, the main ask uses `fast()` and the single-shot provider without tools, and the Today card shows the note from Settings.
5. **Jev.** `chiron/jev.py`: `judge(state, questions) -> answers` with batching, a 3 s timeout, one retry, cost logging, and the Haiku fallback from Appendix D. Read TypeSafe's quickstart at docs.typesafe.ai for the exact request shape; keep the base URL configurable (TypeSafe console, or Cloudflare Workers AI `typesafe/jev`).
6. **Usage.** `chiron/usage.py` appends one row per model or Jev call to `usage.jsonl`. The base app's `log_turn()` keeps writing `log.jsonl`; `usage.py` also reads `usd` from it so Claude Code costs count once. Add `month_total()` and `over_cap()` (warn only in this phase).
7. **Home state.** `chiron/home.py` builds the state JSON from `dictation.json`, `log.jsonl` and `usage.jsonl`; add the `--home-state` and `--home-do <method>` CLI entries in `chiron.py`.
8. **Windows and bridge.** `app/HomeWindow.swift` and `app/HomeBridge.swift`: load with `loadFileURL(_:allowingReadAccessTo:)` on the `ui/` folder, register the `home` handler, implement the Phase 1 bridge methods, and push `state` every 5 s while visible and after each ask. Add **Open Home** and **Settings…** to the menu bar menu; remove the old Settings window and `settings.html`.
9. **Language.** Add pref `lang` (`en` default). `app/Strings.swift` provides `L(key)` for native labels (menu bar, callouts, permission help). `chiron/i18n.py` provides `t(key)` for spoken and printed lines. Add one rule to the system prompt: "Reply in {lang\_name}."
10. **Keep the old box** (⌃⌥Space) working for now; the Voice Bar replaces it in Phase 2.

### Wire it together

Replace the mock with the real bridge, open Home after a real ask, and check that Words spoken, AI spend and Recent match the files on disk.

### Tests to add

- `test_strings.py`: same keys in both files, no empty values, no English left in `hi.json` outside brand names.
- `test_home_state.py`: state from fixture files (empty, typical, corrupted lines skipped).
- `test_providers.py`: request shapes and cost maths against recorded responses (no network).
- `test_jev.py`: batching, timeout, fallback path.
- `test_keychain_native.py` (host-gated): set, get, delete round-trip.
- `test_home_page.py`: load `ui/home.html` in the off-screen WKWebView harness, switch language, render each fixture.

### Done when

- [ ] `./build.sh` installs `~/Applications/Chiron.app`; the menu bar shows Chiron; nothing outside Chiron's own paths is touched.
- [ ] The full test suite passes; removed features leave no menu items, prefs or files.
- [ ] Home and Settings render real data in both languages, light and dark.
- [ ] Every connection type saves to the Keychain and its Test passes with a valid key and fails clearly with an invalid one.
- [ ] An ask through Claude Code with an Anthropic key works and its cost appears in AI spend.

### What the Phase 1 report must let you test

| # | Do this | You should see |
| --- | --- | --- |
| 1 | `git checkout phase-1 && ./build.sh` | Chiron opens; menu bar icon; no menus for Meetings or Agents |
| 2 | Menu bar → Open Home | Home with Words spoken, AI spend, Recent; Today says nothing is due |
| 3 | Click **हिं** | Every label on Home switches to Hindi at once; switch back to EN |
| 4 | Gear → Settings → Brain → Claude Code | Installed, signed in, plan shown; **Set up** opens the login script if not |
| 5 | Brain → Anthropic key → paste → Test | ✓ with time and cost under $0.001 |
| 6 | Paste a wrong key → Test | Plain-language error, nothing saved |
| 7 | Jev key → Test | ✓ and the Jev footer dot turns green (or the fallback note if no key) |
| 8 | Open Keychain Access, search "chiron" | One item per saved key; `~/.config/chiron/settings.json` contains no keys |
| 9 | ⌃⌥Space → "open Notes" | Notes opens instantly (no AI); Recent shows it |
| 10 | ⌃⌥Space → "what's the weather like in Paris?" | Answer arrives; AI spend rises by the logged cost |
| 11 | Hold fn and dictate into TextEdit | Text lands; Words spoken today increases |
| 12 | Resize Home to 560 px, toggle dark mode | Tiles stack to one column; dark theme readable |

## Phase 2 — Voice Bar and speech

Phase 2 makes the always-on Voice Bar the way into Chiron: hold fn anywhere to talk, in English or Hindi, with Apple's on-device speech first and Sarvam as the fallback, spoken replies in the chosen language, and every word counted on Home.

### Frontend (build first, against mocks)

1. **Voice Bar** `ui/bar.html`, built from the pill parts of the base app's `ui.html` (`pill()`, `#dictwave`, `ui.dictate/level/finishing/dictated`). States: idle (about 120 × 28 pt, soft orb, 60% opacity), listening (wider, live wave, live words), thinking, speaking, done (green check, fades after 2 s), plus placeholders for teaching, practice due and Guardian alert that Phases 3–4 switch on. Every label from strings. Add `tests/bar.html` with a state switcher.
2. **Answer card:** answers appear in a card that grows upward from the bar (reuse the base app's `#thread` rendering for Markdown, steps and Allow cards), large text, closes on Esc or after 20 s of no interaction.
3. **Home → Words spoken** now counts voice asks as well as dictation, split by language, with time saved.
4. **Settings → Voice and language:**
   - Listening engine status per language: "On-device (free)", "Downloading…" with a progress bar, "Not available on this Mac — using cloud".
   - **Test my voice**: records 5 s, shows the transcript and which engine heard it.
   - Sarvam key field with **Test** and the per-minute price.
   - Spoken voice per language with **Preview**, and a speed slider (0.7–1.1, default 0.85).
   - Talk key: fn (default) or Control+Option, with the "Set 🌐 key to Do Nothing" fix button (the base app's `globeKey`).
   - Household dictionary: add or remove names and words (the base app's dictation dictionary).
   - Reset the Voice Bar position.

### Backend

1. **`app/VoiceBar.swift`.** A `KeyPanel`-style panel with `[.nonactivatingPanel, .borderless]`, level `.statusBar`, behaviour `[.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]`, never key unless the user clicks into a typed reply. Bottom centre of the screen under the pointer at launch; draggable; frame remembered per display (reuse `MeetingFrame.clamp`); double-click resets; right-click menu (Open Home, Pause, Settings, Quit) using `L()`. The bar is always visible unless paused.
2. **Talk key.** Repoint the fn special hotkey (`updateSpecialHotkey`, `upstream.swift:7457`) to start a normal ask (`App.start(dictate: false)`) instead of dictation. Hold to talk, release to send, double-tap to lock; keep the 60 s cap and the quiet-tap rule. If the user says "type …" or "likho …" first, route to the base app's dictation insert path instead. Retire ⌃⌥Space as the default (keep it recordable in Settings).
3. **`app/SpeechLocale.swift`.** At launch and when `lang` changes:
   - Check `SpeechTranscriber.supportedLocales` / `installedLocales` and `DictationTranscriber` for `hi-IN`, `en-IN`, `en-US`.
   - Request missing assets with `AssetInventory`.
   - Pick the engine per language, and replace the hardcoded `Locale(identifier: "en-US")` at `upstream.swift:1805` with the result.
   - Write the probe to `speech.json` for Settings.
   - If creating the analyzer fails with "unsupported locale" (the 1.5.0 failure), fall back without breaking the ask.
4. **Cloud fallback.** While fn is held and the engine is cloud, also write the converted 16 kHz mono buffers to a temp WAV. On release, run `chiron.py --transcribe <wav> <lang>`. `chiron/speech_cloud.py` calls Sarvam Saaras REST (audio up to 30 s) with `mode: codemix`, logs minutes and cost to `usage.jsonl`, and returns text. Target under 2 s for a 5 s ask. If the cloud fails, use the on-device English transcript.
5. **Auto-fallback rule:** if Hindi is on-device but 2 of the last 3 Hindi asks end in "I didn't catch that" or an immediate repeat, offer once to switch Hindi listening to the cloud.
6. **`chiron/normalize.py`.** Normalises Devanagari, romanised Hindi and English into one comparable form for `fast()`, `like()` and routing: a transliteration table, a synonym list (bajao/chalao/play → play; kholo/open → open), and the household dictionary. Feed dictionary words into `contextualStrings` (`upstream.swift:1907`).
7. **Speaking.** Extend `readAloudArguments` / voice selection (`:472-533`): pick the voice for the app language (from the `voice.<lang>` pref, else the best installed `hi_IN` / `en_*` voice), and pass `-r` for speed. Every spoken line comes from `i18n.t()` or the model reply in the app language. Add "say that again" to `fast()` (replays the last spoken line, no AI).
8. **Logging.** `voice.jsonl` row per ask: language, engine, words, seconds, understood (an ask that was not repeated or cancelled within 10 s). `home.py` merges it with `dictation.json`.

### Wire it together

The Voice Bar is now the default surface. The old top-corner box only opens for long answers or typed replies, and it docks above the bar.

### Tests to add

- `test_normalize.py`: Devanagari, roman and English requests normalise to the same key (40 pairs).
- `test_speech_cloud.py`: request shape, cost, timeout and fallback with a recorded response.
- `test_bar_page.py`: each bar state renders in both languages.
- Native, host-gated: locale probe returns a result; the fn hold starts and ends a session.
- A recorded audio set `tests/audio/` (20 English, 20 Hindi, 10 mixed WAVs, recorded by you) with expected text, plus `chiron.py --speech-eval` to print accuracy per engine.

### Done when

- [ ] Holding fn in any app, including full screen, shows the bar listening; releasing sends; the bar never steals focus.
- [ ] English and Hindi asks are understood at least 8 of 10 times each on the real Mac (the gate).
- [ ] Settings shows exactly which engine serves each language; the cloud path works when a key is set.
- [ ] Replies are spoken in the chosen language at the chosen speed.
- [ ] Words spoken on Home counts both voice asks and dictation, per language.

### What the Phase 2 report must let you test

| # | Do this | You should see |
| --- | --- | --- |
| 1 | Install `phase-2` build | Voice Bar at bottom centre on every desktop and in a full-screen video |
| 2 | Hold fn, say "open Calculator", release | Calculator opens instantly; bar shows done |
| 3 | Switch to हिं, hold fn, say "कैलकुलेटर खोलो" | Same result; reply spoken in Hindi |
| 4 | Say a mixed sentence: "YouTube pe news lagao" | YouTube search for news opens |
| 5 | Settings → Voice → Test my voice (both languages) | Transcript and engine name shown |
| 6 | Remove the Sarvam key, set Hindi to cloud | Clear message; falls back to on-device or asks to add a key |
| 7 | Double-tap fn, speak for 20 s, press fn | Locked listening, then sent |
| 8 | Drag the bar to the left edge, quit, reopen | Bar returns to the same spot; double-click resets it |
| 9 | Run `python3 chiron.py --speech-eval` | Accuracy per language and engine printed |
| 10 | Open Home | Words spoken shows today's asks split by language |

## Phase 3 — Teach Me and Do It

Phase 3 delivers the core of Chiron: every request is routed to Do It or Teach Me; Teach Me plans a lesson once, guides the user click by click with drawn arrows and bilingual captions, checks each step with Jev, and saves a skill card that Do It can later replay for free.

### Frontend (build first, against mocks)

1. **Lesson callout redesign.** Restyle the base app's `DrawingCalloutView` (`upstream.swift:1011`) to the Chiron tokens:
   - Warm card, 20 pt caption in the current language, step counter "Step 2 of 6", buttons **Back**, **Next**, **Stop**, **Show me**.
   - A soft amber ring instead of red marks; a short praise state ("Well done") between steps.
   - Build a static Swift preview harness (`tests/lesson_preview.swift`) that renders the callout for screenshots in both languages.
2. **Home → Skills learned tile:** the constellation (inline SVG). One star per skill card, sized and lit by mastery, grouped by app. Hover or focus shows the skill name and mastery; click offers **Teach me again** or **Just do it**.
3. **Home → Today card** shows a starter lesson when nothing is due ("Learn: play a video on YouTube" with **Start**).
4. **Home → Recent** shows lessons and Do It runs with their outcome icons.
5. **Settings → Teaching:**
   - Default mode: "Teach me unless I know it" (default), "Always just do it", "Always teach me".
   - Caption size.
   - Toggle: "Ask me to explain it back" (off until Phase 4).
6. **Voice Bar:** teaching state with step counter; "Say *next*, *back*, *show me* or *stop*".

### Backend

1. **`chiron/router.py`.** Order:
   1. The base app's `fast()` (free).
   2. Exact or close skill-card match via `normalize.py` + `like()` (free).
   3. One Jev request with `route.skill`, `route.mode` and `route.risky` (Appendix D).
   4. If no Jev, Claude Haiku with the same questions.

   The mode rule: mastery 5 or "just do it" → Do It; known skill below 5 → Teach Me (or Practice in Phase 4); new skill → Teach Me; a general question → the base app's main ask.
2. **`chiron/lessons.py` — planning.** Gather `window_summary()` and the accessibility map (`hands see`), plus a 1,024-px screenshot (`look()`) only if the map has fewer than 5 labelled controls. Ask Claude Haiku (provider layer, JSON mode, cached system prompt) for a lesson in the skill card step shape: `say{en,hi}`, `target{app,label,role}`, `expect`, `concept`, `draw`. Validate with the base app's `drawing()` plus checks for bilingual `say`, an `expect` on every step, 1–12 steps and known concepts. Re-ask once on failure.
3. **Starter pack.** Ship 5 hand-written skill cards in `chiron/starter/` (YouTube video, WhatsApp Web photo, join a video call link, open a photo, open-save-print a Word file) so first lessons cost nothing and are reliable.
4. **`app/Lesson.swift` — running.** For each step, send a `DrawingRequest` through `ScreenDrawing.receive` with `wait`, `hit` and `target` so the base app's click detection (`clicked()`, `tick()`) advances it. After each advance (or a 6 s pause), the runner:
   - captures the window summary;
   - runs `chiron.py --check-step` (Jev `step.done` + `step.fault`);
   - acts on the result:
     - correct → praise, next step;
     - loading → wait 2 s, check again;
     - wrong with confidence ≥ 0.7 → spoken hint and a redraw on the right target;
     - unsure → ask a yes/no question ("Did YouTube open?") and use the spoken answer.

   After 3 hints on a step, offer "Shall I do this step?" and run it with Hands. Voice commands *next, back, show me, stop* map to `drawing.next()` and friends.
5. **Do It.** Use the skill card's `cmds` with the base app's `replay()` when present. Otherwise run the steps with Hands in order, re-resolving each target by label. A failed replay re-plans once (the base app already unlearns on failure).
6. **`chiron/skills.py`.** Create or update a card at the end of every lesson. Add `cmds` when the base app's `learn()` filters accept the commands Hands used; record each step's outcome in `attempts.jsonl`; set mastery from Jev `attempt.score` (Appendix D) with the mastery table; write `history.jsonl`. Cards are `mine` and never expire (unlike the base app's 30-day rule).
7. **System prompt.** Add a compact TEACH block: when a lesson is requested, return lesson JSON only; never act in Teach Me mode. Keep the 10,000-character test green.
8. **Home state:** `skills`, `today` (starter suggestion), lesson rows in `recent`.

### Tests to add

- `test_router.py`: 30 asks in English, Hindi and mixed, with expected route, using a fake Jev.
- `test_lessons.py`: planner output validation, re-ask path, starter cards load and validate.
- `test_skills.py`: card creation, update, mastery maths, attempts.
- An eval scenario in `tests/evals/` with `fake_mac.py`: a lesson where the user clicks the wrong app, then the right one.
- `test_home_page.py`: constellation renders 0, 1, 12 and 40 skills.

### Done when

- [ ] "Teach me to play a video on YouTube" runs a full lesson with arrows, bilingual captions, Jev checks and praise.
- [ ] A wrong click gets a hint and a redrawn arrow, not a failure.
- [ ] The lesson saves a skill card; Home shows a new star; "just do it" then replays it with no AI.
- [ ] Switching EN ↔ हिं mid-lesson changes the caption and voice on the next step with no AI call.
- [ ] Learners finish 4 of 5 starter lessons (the gate).

### What the Phase 3 report must let you test

| # | Do this | You should see |
| --- | --- | --- |
| 1 | Home → Today → **Start** (starter YouTube lesson) | Arrow on Chrome in the Dock, caption, spoken step 1 |
| 2 | Click Safari instead | Gentle hint and the arrow moves back to Chrome |
| 3 | Finish the lesson | Praise; Home shows 1 star under YouTube; Recent shows the lesson |
| 4 | Hold fn: "just play some music on YouTube" | Done by itself, no arrows, cost $0 in AI spend |
| 5 | Hold fn: "teach me how to make a new folder on the desktop" (not a starter) | Claude plans it once (cost shown), lesson runs, a new card is saved |
| 6 | Halfway through, tap हिं on Home | Next caption and voice are Hindi |
| 7 | Say "show me" three times on one step | Chiron offers to do the step, then does it |
| 8 | Say "stop" | Drawing clears; attempt saved as unfinished |
| 9 | Disconnect Jev in Settings and repeat step 1 | Lesson still works (Haiku fallback); AI spend shows the higher cost |
| 10 | Run the test suite and `tests/evals/harness.py --dry` | All green; lesson scenario passes |

## Phase 4 — Practice and Guardian

Phase 4 makes the learning stick and keeps the Mac safe: skills come back on a spaced schedule, Chiron watches the user do them alone and corrects only the wrong step, weak spots get short drills, and Guardian stops scam pages before harm.

### Frontend (build first, against mocks)

1. **Today card:** the due practice ("Show me how you play a video on YouTube · about 2 minutes") with **Start** and **Not now**; after the last practice of the day, "All done for today" with the streak.
2. **Weak spots tile:** top 3 concepts with a plain label ("Opening the right app"), the miss count over 14 days, and **Practice this** (a 60-second drill).
3. **Streak tile** and **Guardian tile** (scams stopped this month, latest one with domain and date).
4. **Constellation:** practice raises a star's brightness with a short glow; a fully mastered app draws its constellation lines.
5. **Guardian warning card:** a native panel, centred over the offending window. It shows a red-orange ring, a large title ("Stop. This looks like a scam."), one reason line, **Close it** (primary) and **I trust this site** (secondary, needs a spoken "yes"). Build a Swift preview with 5 sample reasons in both languages.
6. **Voice Bar:** practice-due dot; Guardian red ring.
7. **Settings → Practice:** maximum per day (1–5, default 2), quiet hours, "Ask me to explain it back" toggle.
8. **Settings → Guardian:** on/off, strictness (Gentle, Normal, Strict), the block list with **Unblock**.

### Backend

1. **`chiron/practice.py` — schedule and mastery.** Use the mastery table from the product plan. A mistake drops mastery by one, never to zero. Write `schedule.json`. Pick today's practice by the most overdue skill, then the lowest mastery.
2. **Reminders.** Reuse the base app's routines (`routine_install`, launchd `StartCalendarInterval`) as one plist `com.chiron.practice`, checking 3 times a day. `RoutineWake` (rewired in Phase 1) shows the dot and, if the Mac is in use and no call or full-screen video is running, speaks one invitation. "Not now" defers to the next slot; the daily limit is enforced.
3. **Practice run.** Same runner as Teach Me with `mode: practice`:
   - no arrows by default;
   - after each user action, Jev `step.done` + `step.fault`;
   - on a confident fault, an arrow and a hint for that step only;
   - after 20 s of no progress, offer the Ghost hand.
4. **`app/GhostHand.swift`.** A translucent pointer built from the `pointer` shape and the animated leader in `DrawingView`. It glides from the current mouse position to the target, does a tap animation and a ripple, never posts a click, then fades. It is ignored by mouse events (`PassView`).
5. **Weak spots.** `practice.weak_spots()`: concepts with a hint or fault in 2 of the last 3 attempts that used them, over 14 days, across all skills. A drill builds a 3-repetition mini-lesson of only steps with that concept, taken from the user's own skill cards. Two clean attempts clear it.
6. **Explain it back** (optional, off by default). After a lesson or practice, ask "How would you do this next time?", score the spoken answer with Jev `explain.score`, and add 0.5 to mastery when the score is 4 or more.
7. **Streak** from `attempts.jsonl` in local time.
8. **`app/GuardianWatch.swift` — triggers.** Observe:
   - `NSWorkspace` app activation;
   - AX window-created and title-changed notifications for the frontmost app;
   - in browsers, the front tab title and URL every 3 s through Hands `see`, only while a browser is frontmost.

   On a new window or page, run `chiron.py --guard` with title, URL and the first 4,000 characters of text (`window_text()`).
9. **`chiron/guardian.py` — the three layers.**
   1. Local rules, free: phrase lists in `chiron/guardian/phrases.en.txt` and `.hi.txt`; a phone-number regex near "support" or "helpline"; remote-access app names; full-screen browser plus beeping; look-alike domains by edit distance ≤ 2 against `chiron/guardian/brands.txt`.
   2. On any red flag, one Jev request with `guard.push`, `guard.pretend` and `guard.scam`.
   3. A score of 2 to 3, or low confidence, gets one Haiku check with a screenshot.

   Strictness moves the block threshold: Gentle 5, Normal 4, Strict 3. Write `guardian.jsonl` and `blocklist.json`. A blocked domain is closed on sight (⌘W through Hands after showing the card).
10. **Never-type rule.** In `gate()` and Hands `authorize`, refuse typing into secure fields and refuse text that matches card, bank, OTP or ID-number patterns, and say why. The base app already masks secure fields in the map; this adds the refusal.

### Tests to add

- `test_practice.py`: schedule maths, daily limit, quiet hours, weak-spot detection, drills from fixtures.
- `test_guardian.py`: 10 scam pages and 20 normal pages in `tests/guardian/pages/`. Expected verdicts per strictness, with a fake Jev. No false alarm on the normal set at Normal.
- Host-gated: GuardianWatch fires on a new Safari window serving a local test page.
- `test_home_page.py`: Today, Weak spots, Streak and Guardian tiles across fixtures.

### Done when

- [ ] A skill learned in Phase 3 comes back at the right time; practising it changes mastery and the next date as the table says.
- [ ] A deliberate mistake in practice gets one arrow for that step only; the Ghost hand demonstrates without clicking.
- [ ] Weak spots appear after repeated trouble and clear after two clean drills.
- [ ] Guardian stops 10 of 10 local scam pages and raises no alarm on 20 normal pages (the gate).
- [ ] Chiron refuses to type a card number or OTP, kindly.

### What the Phase 4 report must let you test

| # | Do this | You should see |
| --- | --- | --- |
| 1 | Run `python3 chiron.py --practice-now youtube-play` (test helper that makes a skill due) | Dot on the bar; spoken invitation; Today card shows it |
| 2 | Start, then open Safari instead of Chrome | One arrow to Chrome and a hint; nothing else drawn |
| 3 | Wait 20 s without acting on a step | Ghost hand glides to the target and taps without clicking |
| 4 | Finish | Mastery goes up; next practice date in Settings → Practice → skill list matches the table |
| 5 | Make the same mistake in 2 lessons | "Opening the right app" appears under Weak spots; **Practice this** runs a 60-second drill |
| 6 | Say "not now" to a practice | Moves to the next slot; no more than 2 invitations today |
| 7 | Open `tests/guardian/pages/fake-virus.html` in Safari | Warning card in under 2 s; **Close it** closes the tab; Guardian tile counts it |
| 8 | Reopen the same page | Closed at once as blocked |
| 9 | Browse 5 normal sites (news, YouTube, bank homepage) | No warnings |
| 10 | Ask Chiron to type "my card number is 4111 1111 1111 1111" into a form | Refuses kindly and explains |
| 11 | Run `python3 -m unittest tests.test_guardian -v` | 30 page verdicts, all as expected |

## Phase 5 — Paper Studio and budget

Phase 5 adds Paper Studio, which learns a teacher's format from her own old papers and drafts new ones by voice as Word files, and it turns the cost cap from a warning into a hard limit with a clear spend breakdown on Home.

### Frontend (build first, against mocks)

1. **Papers tile on Home:** count this month, the last paper with **Open**, and a drop zone: "Drop old papers here to teach me your style" (.docx, .pdf, .jpg, .png, .heic).
2. **Style card** (an in-page sheet over Home, not a new page). It shows the learned rules in plain words, grouped as Header, Sections, Questions, Marks, Layout and Answer key. Each rule has an edit pencil and a remove ×. **Relearn from my papers** starts over.
3. **Paper progress** in the Voice Bar: "Writing your paper…" with a determinate bar (outline, questions, formatting, saving).
4. **AI spend tile:** this month against the cap, a thin bar, and on click a small breakdown by engine (Jev, Haiku, Sonnet, speech) and by feature (lessons, papers, questions, Guardian).
5. **Settings → Budget:**
   - The cap.
   - Two behaviours, shown as text: "At 80%: papers use the cheaper model" and "At 100%: only free features until the 1st".
   - A one-off **Allow $2 more this month** button that needs a spoken "yes".
6. **Settings → Privacy:**
   - **Export everything** saves a zip to Downloads.
   - **Delete everything** needs a typed confirmation and keeps the keys unless a box is ticked.
7. **Settings → Papers:** the default save folder, Word or Google Docs, and the answer key on the last page or as a separate file.

### Backend

1. **Ingest.** `chiron/papers.py`:
   - Read .docx with `python-docx`: paragraphs, runs, styles, tables, section margins, header and footer.
   - Read .pdf with `pdfplumber`: text with positions and font sizes.
   - Read photos with Claude vision.
   - Normalise everything to one intermediate form: blocks with text, size, weight, alignment and indent.
2. **Style note.** Send that intermediate form for up to 6 papers to Claude Sonnet once, and get `style.json` back:
   - header fields and order;
   - section names and numbering;
   - question numbering;
   - marks placement;
   - multiple-choice option format;
   - the usual mix of question types;
   - language or medium;
   - font, size, margins and spacing;
   - answer space;
   - instructions and footer;
   - answer-key format;
   - plus plain-language `rules[]`.

   Validate the result against a JSON schema. Keep it as the cached system block for every later paper call.
3. **Paper JSON.**
   - Schema: `{meta{class, subject, topic, marks, time}, sections[{title, instructions, questions[{n, type, text, options?, marks, answer, diagram?}]}]}`.
   - Claude Sonnet writes it from the request plus the style note. At 80% of the cap, Haiku writes it instead.
   - Code checks totals, counts and numbering. If they don't add up, the model gets one repair call that names the exact mismatch.
4. **Builder.**
   - `python-docx` turns paper JSON plus `style.json` into a .docx: header table or lines, section headings, numbered questions, right-aligned marks with a tab stop, options in the chosen layout, answer lines or boxes, a page break before the answer key, page numbers in the footer.
   - Save to `~/Documents/Chiron Papers/<class>/<subject>/<YYYY-MM-DD> <topic>.docx`.
   - Open with `open -a "Microsoft Word"`, falling back to Pages, then TextEdit.
5. **Voice edits.** While the paper's document is frontmost, an edit request ("make question 3 easier", "add one more MCQ", "marks on the right") becomes a JSON patch from Claude Haiku. The patch is applied, the paper rebuilt, and the file reopened in place (Word reloads it). Small text fixes can use the base app Hands `type` instead.
6. **Learning from edits.**
   - When she saves a hand-edited paper (detected through `watch()` on the file's modification time), diff the docx text and format against the draft.
   - Ask Jev `paper.rule` for each change.
   - Offer each likely lasting rule once, by voice, before adding it to `style.json`.
7. **Google Docs path.** "Put it in Google Docs" runs a Do It sequence in Chrome: drive.google.com, New, File upload, pick the file, then Open with Google Docs. It is saved as a skill card, so it can also be taught.
8. **Budget.**
   - `usage.py` enforces the cap in `providers.py` and `jev.py`: every call checks `over_cap()` first.
   - At 100% of the cap: model calls raise a friendly "limit reached" reply; `fast()`, replays, Guardian layer 1 and on-device speech keep working.
   - The count resets on the 1st of the month (local time).
   - `chiron.py --costs` prints the breakdown.
9. **Export and delete:** zip `~/.config/chiron` (excluding locks), or wipe it. "Also remove keys" deletes the Keychain items.

### Tests to add

- `test_papers_ingest.py`: 3 sample .docx and 2 .pdf fixtures (make synthetic ones) parse to the intermediate form.
- `test_papers_build.py`: paper JSON plus style builds a .docx; re-read it and check numbering, marks alignment, page break and totals.
- `test_papers_validate.py`: wrong totals trigger the repair path.
- `test_usage_cap.py`: 80% and 100% behaviour, monthly reset, the one-off top-up.
- `test_home_page.py`: Papers tile, style card sheet, spend breakdown.

### Done when

- [ ] Dropping 3 old papers produces a style card that matches them closely.
- [ ] "Class 7 science, heat, 20 marks…" produces a correct .docx in her format, opened in Word, with totals that add up.
- [ ] Voice edits change the open paper within about 10 s.
- [ ] A hand edit she keeps making becomes a rule after one confirmation.
- [ ] At 100% of the cap, paid calls stop with a friendly message and free features keep working.
- [ ] Paper accepted with fewer than 5 edits (the gate).

### What the Phase 5 report must let you test

| # | Do this | You should see |
| --- | --- | --- |
| 1 | Drop 3 of Mummy's old papers on the Papers tile | Progress, then the style card with her header, sections and marks style |
| 2 | Remove one rule, edit another | Card updates; `style.json` matches |
| 3 | Hold fn: "Class 7 science, heat, 20 marks, 5 MCQ, 4 short answer, 1 diagram, with answer key" | One confirming question, then Word opens a paper in her format; totals equal 20 |
| 4 | Say "make question 3 easier" | Question 3 changes in the open document |
| 5 | Edit the margins by hand in Word, save, close | Next day, Chiron asks once whether to keep the new margins |
| 6 | Say "put it in Google Docs" | Chrome uploads it and opens it in Google Docs |
| 7 | Set the cap to $1 and run `python3 chiron.py --simulate-spend 0.85` | Papers switch to the cheaper model; Home shows 85% |
| 8 | `--simulate-spend 1.0`, then ask a new question | Friendly limit message; "open Calculator" still works |
| 9 | Settings → Privacy → Export | A zip in Downloads with all local data and no keys |
| 10 | Run the full suite | All green |

## Release — the DMG

The release turns the Phase 5 build into `Chiron.dmg` on GitHub Releases: built and signed in CI, Python bundled, notarised, auto-updating, with a first-launch setup that needs no Terminal; installing it on a clean Mac takes under 15 minutes.

### Frontend (build first)

1. **Onboarding** (`ui/onboarding.html`, slimmed from the base app's 13 pages to 6):
   - **Welcome:** the language switch is the first control.
   - **Permissions:** one at a time, with the base app's drag-to-grant help (`PermissionHelp`).
   - **fn key:** a one-click "Press 🌐 key to Do Nothing" fix.
   - **Speech:** downloads on-device speech assets and voices, with progress.
   - **Connections:** a short form of the Settings Connections, skippable.
   - **First lesson.**

   Same tokens and strings as Home.
2. **DMG window art:** a 660 × 400 background with the app icon, an arrow to Applications, and "Drag Chiron to Applications" in English and Hindi.
3. **App icon:** a new Chiron mark replacing the base app's (`ui/AppIcon.icns`), with menu-bar template images.
4. **Settings → About:** version, **Check for updates**, and an automatic-updates switch.

### Backend

1. **Login item:** replace the hand-written LaunchAgent in `build.sh` with `SMAppService.mainApp.register()`. The Settings "Open at login" switch toggles it.
2. **Bundled Python:**
   - Download a relocatable universal2 CPython 3.12 from python-build-standalone in CI.
   - Put it in `Contents/Resources/python/`.
   - Install `httpx`, `python-docx`, `pdfplumber` and their dependencies into `Contents/Resources/site-packages/`.
   - Change the base app's `py()` (`upstream.swift:606`), which runs `/bin/sh upstream.py`, to run the bundled interpreter on `chiron.py` with `PYTHONHOME` and `PYTHONPATH` set.
   - Keep a dev fallback to system `python3` when the bundle is missing.
3. **Claude Code is not bundled.** Settings **Set up** runs the official installer and `claude auth login` in Terminal (the base app's `fixPlan`). An Anthropic or OpenAI key needs no install.
4. **`.github/workflows/release.yml`** runs on a tag `v*`, on a macOS runner with the macOS 26 SDK:
   1. Run the test suite.
   2. `swiftc` for arm64 and x86\_64, then `lipo -create`.
   3. Assemble `Chiron.app`: Info.plist with `com.chiron.app`, the version from `VERSION`, usage strings, `LSUIElement`, and Sparkle keys.
   4. Sign every Mach-O inside, deepest first (Python binary, `.so` and `.dylib` files, Sparkle), then the app. Use `codesign --options runtime --timestamp` with entitlements for audio input and Apple Events. The bundled interpreter may need `com.apple.security.cs.disable-library-validation`. No App Sandbox, because Accessibility and background input need it off, as in the base app.
   5. `xcrun notarytool submit --wait`, then `xcrun stapler staple`.
   6. `create-dmg` with the background, then sign and notarise the DMG.
   7. Sparkle: `generate_appcast` with the EdDSA key from repo secrets; publish `appcast.xml` to GitHub Pages; attach the DMG to the release.

   Secrets needed: Developer ID certificate (p12 and password), App Store Connect API key for notarisation, Sparkle EdDSA private key.
5. **Updates:** Sparkle 2 replaces the stubbed git `Updater`; check daily and install when idle (the base app's `restartWhenIdle` idea).
6. **Without a paid Apple account:** the workflow still builds an ad-hoc signed DMG, and the README explains right-click → Open once. Do not ship that to the family Mac unless needed.
7. **README for Chiron:** download, first launch, connections, costs, privacy, credits (`CREDITS.md`: the MIT base app, Plip and Cua Driver).

### Tests to add

- CI job that mounts the DMG, verifies signatures (`codesign --verify --deep --strict`, `spctl -a -vv`), and runs `Chiron --selftest` and `chiron.py --selftest` with the bundled Python.
- A clean-account checklist (below) run by hand on a fresh macOS 26 user account or VM.

### Done when

- [ ] Tagging `v1.0.0` produces a notarised `Chiron.dmg` on GitHub Releases with no manual steps.
- [ ] On a clean Mac account: download, drag to Applications, open, finish onboarding, and complete the first lesson in under 15 minutes, with no Terminal.
- [ ] Version 1.0.1 installs itself through Sparkle.

### What the Release report must let you test

| # | Do this | You should see |
| --- | --- | --- |
| 1 | Open the GitHub Release page | `Chiron.dmg` and release notes |
| 2 | On a fresh macOS user account, download and open the DMG | Background art; drag to Applications |
| 3 | Open Chiron from Applications | No security warning; onboarding in English with the switch to Hindi |
| 4 | Grant each permission as guided | Each step turns green; no restart surprise |
| 5 | Skip Connections, try "open Calculator" | Works with no keys |
| 6 | Add an Anthropic key in Settings, start the starter YouTube lesson | Full lesson works |
| 7 | Restart the Mac | Chiron starts at login; Voice Bar returns |
| 8 | Publish `v1.0.1` with a visible change | Chiron updates itself when idle |
| 9 | Run `spctl -a -vv /Applications/Chiron.app` | "accepted, source=Notarized Developer ID" |
| 10 | Install on the family Mac and hand it over | You are done |

## Appendix

These schemas, question shapes and templates are shared by every phase; change them here first, then in code.

### A. Data files in `~/.config/chiron/` (all `0600`, folder `0700`)

| File | Written by | Phase |
| --- | --- | --- |
| `prefs.json` | Settings view (language, voice, cap, practice limits) | 1 |
| `usage.jsonl` | Every model or Jev call: time, engine, model, tokens, USD, purpose | 1 |
| `voice.jsonl` | Every voice ask: time, language, engine, words, seconds, understood? | 2 |
| `skills.json` | Skill cards (extends the base app's `skills.json`) | 3 |
| `attempts.jsonl` | Every lesson or practice attempt, step by step | 3 |
| `history.jsonl` | Every ask and its outcome (Recent tile) | 3 |
| `schedule.json` | Next practice per skill, drills | 4 |
| `guardian.jsonl`, `blocklist.json` | Guardian checks and blocks | 4 |
| `style.json` | Paper Studio style note | 5 |
| `papers.jsonl` | Papers made, paths, costs | 5 |
| `memory.json` | The base app's memory rules and profile facts (kept) | 1 |

### B. Skill card

```json
{
  "id": "youtube-play",
  "title": {"en": "Play a video on YouTube", "hi": "YouTube पर वीडियो चलाना"},
  "app": "YouTube",
  "asked": ["play some devotional songs on youtube"],
  "steps": [
    {"id": "s1", "concept": "open-app",
     "say": {"en": "Click the round Chrome icon at the bottom", "hi": "नीचे क्रोम का गोल आइकन दबाइए"},
     "target": {"app": "Dock", "label": "Google Chrome", "role": "AXDockItem"},
     "expect": "Google Chrome is open and frontmost",
     "draw": {"shapes": [{"kind": "ring"}], "wait": true, "hit": true}}
  ],
  "cmds": ["open -a 'Google Chrome' 'https://www.youtube.com/results?search_query={q}'"],
  "slots": {"q": "devotional songs"},
  "mastery": 2,
  "next_practice": "2026-10-30",
  "created": "2026-10-28",
  "version": 1
}
```

`concept` groups steps across skills for weak spots: `open-app`, `address-bar`, `search-box`, `click-result`, `scroll`, `back`, `type-text`, `menu`, `save`, `print`, `attach-file`, `close-window`.

### C. Attempt row

```json
{"at": "2026-10-30T18:02:11+05:30", "skill": "youtube-play", "mode": "practice",
 "steps": [{"id": "s1", "result": "wrong_app", "hints": 1, "secs": 14},
           {"id": "s2", "result": "correct", "hints": 0, "secs": 6}],
 "score": 3, "mastery_before": 2, "mastery_after": 3, "usd": 0.0006}
```

### D. Jev question catalog

Every Jev call goes through `chiron/jev.py`, which batches questions per request and logs cost. Answers below 0.7 confidence are treated as unsure.

| Name | Type | State sent | Question | Used in |
| --- | --- | --- | --- | --- |
| `route.skill` | Choice | Normalised ask + top 10 skill titles | Which saved skill matches this request, or *new*? | 3 |
| `route.mode` | Choice | Ask + skill mastery | Do It, Teach Me, Practice, Paper, Question, Settings | 3 |
| `route.risky` | Noul | Ask | The request asks to send, buy, delete, pay or share private data | 3 |
| `step.done` | Noul | Window summary after the action | It is true that: {expect} | 3, 4 |
| `step.fault` | Choice | Same | wrong\_app, wrong\_place, nothing\_happened, loading, correct | 3, 4 |
| `attempt.score` | Score 0–5 | Attempt row | How independently did the learner complete this task? | 3, 4 |
| `explain.score` | Score 0–5 | Lesson steps + spoken explanation | How well does this explanation describe the steps? | 4 |
| `guard.push` | Noul | Page text | The page pushes the user to call, install software or share a code | 4 |
| `guard.pretend` | Noul | Page text + domain | The page pretends to be an organisation it is not | 4 |
| `guard.scam` | Score 0–5 | Page text + domain | How likely is this a scam aimed at a new computer user? | 4 |
| `paper.rule` | Noul | Draft vs edited text diff | This change reflects a lasting formatting preference | 5 |

Fallback: if no Jev key is set, `jev.py` asks Claude Haiku the same questions in one JSON-only prompt and logs it as `engine: haiku-fallback`.

### E. Prompt rules

- System prompt for Chiron's brain under 10,000 characters, enforced by the existing test.
- Lesson planning returns JSON only, validated by the base app's `drawing()` validator plus a `steps[].expect` and bilingual `say` check.
- Replies in the current app language; short sentences; no jargon.
- Prompt caching on the system prompt and the style note.

### F. Phase Report template (`docs/reports/phase-N.md`)

```markdown
# Phase N report — <phase name>

## Built
- <feature>: <one line> (files: ...)

## Decisions I made
- <choice> because <reason>

## How to install this build
1. git checkout phase-N && ./build.sh   (Release phase: open the DMG)

## Test it now (do these in order)
| # | Do this | You should see | Pass? |
|---|---------|----------------|-------|

## Automated tests
- Command: ...   Result: N passed, 0 failed

## Costs measured
- Calls made during testing, total USD, median per ask

## Known gaps and risks
- ...

## Ready for Phase N+1?
- Yes / No, because ...
```
