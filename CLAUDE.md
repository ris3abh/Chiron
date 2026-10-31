# Working on Chiron

Chiron is a Mac tutor for people new to computers: a Swift menu-bar app (`Chiron.swift` + `app/*.swift`) that runs a Python brain (`chiron.py` + `chiron/`) for every ask, with one web page for Home and Settings (`ui/home.html`). Read `docs/HANDOFF.md` first: it says where the work stands and what to do next. The plans are `docs/BUILD_PLAN.md` (wins for code) and `docs/PRODUCT_PLAN.md` (wins for behaviour).

## How a phase runs

- **One phase per run.** Start one only when asked ("start-a-phase" means: follow "Prompt to start a phase" in `docs/BUILD_PLAN.md`). Never start the next one on your own.
- **Frontend first, then backend, then wire them.** Build the phase's part of `ui/home.html` against the mock bridge (`tests/home.html`, fixtures `empty`, `typical`, `errors`) with fake data, so the design can be seen before any backend exists. Then the backend, then swap the mock for real data. A phase is done only when the page shows real data.
- **Don't stop for sub-steps.** Make sensible choices and list them in the report. Stop only for what a person must do: a missing key, a macOS permission, an unavailable API, a toolchain problem.
- **The report is the hand-off.** Finish with `docs/reports/phase-N.md` (template: BUILD_PLAN Appendix F) using real file names, commands, clicks and expected results.
- **Branch `phase-N`**, merged into `main` when the phase is accepted.

## Testing

- Full suite: `python3 -m unittest discover -s tests -v`. Save the full output (no `tail`) and compare failures **by test name** against the previous report or `docs/reports/phase-1-baseline.md`. A phase may introduce **zero** new failures; deleted tests count as removed, not fixed.
- Fast loop while working: run only the modules you touched (`python3 -m unittest tests.test_x`).
- Swift: typecheck before claiming anything works: `cp Chiron.swift /tmp/main.swift && swiftc -typecheck -module-name Chiron -target "$(uname -m)-apple-macos26.0" /tmp/main.swift app/*.swift`. Only `main.swift` may hold top-level code, and code says `Chiron.settings`, so the module name matters. `build.sh` does the same copy.
- Every new Python module gets a test file; every new bridge method gets a mock-bridge case. Tests make no network calls (use recorded responses).
- Tests load `chiron.py` as the module **`brain`** (`import brain`, patch `'brain.x'`), because the `chiron/` package owns the name `chiron`. Keys in tests come from `CHIRON_SECRET_<NAME>` env vars, never the Keychain.
- Window-driving tests skip unless `CHIRON_VM=1` or `CHIRON_ALLOW_HOST_UI=1`. Don't set those on a Mac someone is using.
- Visual check of the page: serve the repo (`python3 -m http.server 8817`) and open `tests/home.html?fixture=typical&lang=en&theme=light&native=1`; check light and dark, EN and हिं, 1280/880/560 wide.

## Committing

- Commit as **Rishabh Sharma <rishabh.sharma1103@gmail.com>** (author and committer):
  `git -c user.name="Rishabh Sharma" -c user.email=rishabh.sharma1103@gmail.com commit …`
- **No `Co-Authored-By: Claude` trailer** and no other AI attribution in commits or PRs.
- Commit at the end of a phase (or a meaningful, tested step) with a summary message. Check `git log -1 --format='%an <%ae> | %cn <%ce>%n%b'`.
- Before committing, scan for secrets: no real keys, `settings.json`, `.env` or runtime `*.jsonl` files.
- Push only when the user says so. Pushing `phase-*` or `main` runs `.github/workflows/dev-dmg.yml` (Swift typecheck + unsigned test DMG).

## Code rules

- **One page only:** all UI lives in `ui/home.html` (Home and Settings views), plus the Voice Bar overlay (`ui/bar.html`, Phase 2) and overlays Swift draws. No other pages. Plain JS, no framework, no build step, no network (CSP in the page).
- **Look:** Apple-style glassmorphism: translucent cards with `backdrop-filter`, SF Pro first, Apple system colours, native vibrancy behind a transparent web view (`html.native`). Keep it premium *and* legible for older users: 17 px body minimum, 44 px controls, visible focus rings, text wraps and never truncates, 4.5:1 contrast. Respect reduced transparency, reduced motion and more contrast.
- **Every user-facing string goes through i18n:** `ui/strings/en.json` and `hi.json` (same keys), `L("key")` in Swift, `t("key")` in Python. Hindi should be natural, not word-for-word; mark uncertain lines in `ui/strings/hi.review.json` for the user to check. On-screen Mac names (apps, menus, System Settings labels) are copied exactly as the Mac shows them, in Latin script. Chiron's feature names are translated in the Hindi UI but stay English in code. Durations show seconds.
- **Keys live only in the Keychain** (service `com.chiron.app`). Only `keys/ChironKeys` touches them: `chiron/paths.secret` and `app/Keychain.swift` both call it, and `build.sh` reuses one signed copy so macOS asks for permission once, not after every build. Change that file as rarely as possible. Don't read keys in loops while testing: an unapproved read puts a password prompt on the user's screen. Never write a key to a file.
- **Claude Code gets `ANTHROPIC_API_KEY` only when the brain is "Anthropic API key".** Every `claude` launch goes through `claude_env()` in `chiron.py`; `tests/test_brain_env.py` enforces it.
- **Keep it cheap:** no AI call where code or a saved skill can answer. Batch Jev questions. The system prompt stays under 10,000 characters (a test enforces it).
- **Understand before changing:** read a function and its tests before editing it; keep existing behaviour the plan doesn't mention.
- **Style:** match the surrounding code: dense, comments say *why*, not what.
- **No upstream names in the code.** The base app is credited only in `CREDITS.md`; don't add its name elsewhere.
- **Native risk:** anything Swift that hasn't been compiled must be called out in the report as unverified.
