# Chiron: A Mac Tutor That Teaches, Then Checks — Product Plan

Oct 28, 2026 · @Rishabh Sharma

Chiron is built on an MIT-licensed open-source base app; see [CREDITS.md](../CREDITS.md).

## Summary

Chiron turns a Mac into a patient tutor for people who are new to computers: it does tasks for them, teaches them to do the tasks themselves, and checks a few days later that the skill stuck. It is named after Chiron, the centaur who taught Achilles, Asclepius and Jason.

Four features carry the product:

1. **Teach Me and Do It.** A spoken request ("play some devotional songs on YouTube") becomes either a guided, click-by-click lesson with arrows on screen, or a finished task. Every lesson is saved as a skill card.
2. **Practice.** Chiron brings each skill back on a spaced schedule, watches the user do it alone, and corrects only the step that goes wrong.
3. **Paper Studio.** A teacher asks for a test paper by voice and gets a Word draft in her own format, learned from her past papers.
4. **Guardian.** Pop-ups, pages and messages are screened for scams, and the screen is stopped before anyone calls a fake support number or shares a code.

The app has three surfaces: an always-on **Voice Bar** at the bottom of the screen (hold fn to talk), a one-page **Home** with a progress dashboard, and a **Settings** window for connecting Claude, Claude Code, OpenAI and Jev. A switch on Home flips the entire app, including the spoken voice, between English and Hindi.

**Cost target:** about $3 to $5 a month of AI spend for normal family use, with a hard $5 monthly cap. Learned tasks replay with no AI, Jev makes the fast yes/no checks for a fraction of a cent, and Claude is called only for new tasks and paper writing.

The companion **Technical Build Plan** turns this into 5 phases plus a DMG release that can be handed to Claude Code.

Technical Build Plan: Chiron — Technical Build Plan for Claude Code

## Goals, non-goals and principles

Chiron succeeds when a first-time user can do their top 10 Mac tasks without calling anyone, and a teacher makes a week's test paper in under 15 minutes.

**Goals**

- Understand natural speech in English or Hindi, including mixed sentences.
- Do or teach common tasks: YouTube, WhatsApp Web, Word, Google Docs, printing, photos, files, video calls.
- Track what has been learned, find weak spots, and bring skills back for practice until they stick.
- Draft test papers, worksheets and answer keys in the teacher's own format.
- Stop scams before they cause harm.
- Show progress on a clear Home dashboard.
- Install from one DMG with no Terminal, and keep AI costs under the monthly cap.

**Non-goals (v1)**

- No remote dashboard or remote control. Everything lives on the one Mac.
- No separate user profiles; one shared profile.
- No Windows, iPhone or web version; no meeting copilot.
- No fixed exam templates; paper format is learned from the teacher.

**Principles**

- **One way in.** Hold fn and talk, or click the Voice Bar.
- **Speak and show.** Every instruction is spoken and shown in large text (20 pt minimum) in the chosen language.
- **Never rush.** Each step waits. No timeouts that fail a lesson, no error screens.
- **One step at a time.** One arrow, one sentence, one action.
- **Praise, then correct.** A wrong click gets a gentle nudge to the right spot.
- **Ask before anything risky.** Sending, buying and deleting need a spoken yes.
- **One page.** Home and Settings are the only screens; nothing else to learn.

## The app at a glance

Chiron has exactly three surfaces: the Voice Bar that is always on screen, a one-page Home that shows progress, and a Settings window for connections; all three are built into the app and installed by the DMG.

### Voice Bar

A small pill fixed at the bottom centre of the screen, modelled on Wispr Flow's Flow Bar and built from the base app's dictation pill.

- **Hold fn to talk, let go to send.** Double-tap fn to lock it on for long requests. Clicking the bar works too. On keyboards without fn, hold Control+Option.
- Floats above every app and Space, including full-screen apps, and never steals keyboard focus. Draggable; double-click to reset.
- States: idle, listening (live wave and live words), thinking, teaching ("Step 2 of 6"), practice due (a small dot), Guardian alert (red ring), done (green check).
- Right-click menu: Open Home, Pause, Settings, Quit.

### Home (the dashboard)

One scrolling page in a normal Mac window, opened from the Voice Bar, the menu bar or the Dock.

| Tile | Shows | Source |
| --- | --- | --- |
| Today | The next practice and a big Start button; "Nothing due" when clear | Practice scheduler |
| Words spoken | Today, this week, all time; time saved versus typing | The base app's `DictationData` counters, extended to all voice asks |
| Skills learned | Skill constellation (see Design) with counts per mastery level | Skill cards |
| Weak spots | The 3 steps with the most hints or mistakes in 14 days, each with a "Practice this" button | Attempt history |
| Streak | Days in a row with a lesson or practice | Attempt history |
| Guardian | Scams stopped this month and the latest one | Guardian log |
| Papers | Papers made, last one with an Open button | Paper Studio |
| AI spend | This month against the cap, as a thin bar | Budget tracker (the base app's `log_turn()` costs) |
| Recent | The last 10 things Chiron did or taught | History |

### Settings

A separate small window, opened from Home's gear or the Voice Bar menu. Sections:

- **Connections:** the brain (Claude Code on a Claude plan, Anthropic API key, OpenAI API key, or a custom server such as Ollama), Jev (TypeSafe key), cloud speech (Sarvam key, optional), each with a status light and a **Test** button.
- **Budget:** monthly cap ($1 to $50, default $5) and what happens at the cap.
- **Voice and language:** app language, spoken voice, speaking speed, fn or Control+Option.
- **Practice:** maximum practices per day (default 2), quiet hours.
- **Guardian:** on or off, strictness.
- **Privacy:** export everything, delete everything.
- **About:** version, check for updates.

Keys are saved in the macOS Keychain.

### English and Hindi switch

A segmented switch at the top right of Home reads **EN | हिं**. One tap changes everything at once:

- Every label on Home, Settings and the Voice Bar (strings come from one `strings.en.json` / `strings.hi.json` pair).
- The spoken voice and its speed.
- Lesson captions and step instructions, which are stored in both languages on each skill card, so switching needs no new AI call.
- The language Claude replies in, and the default listening language. Mixed speech is still understood in either mode.

The choice is saved and also reachable by voice ("switch to Hindi").

## How it feels: five walkthroughs

Every request lands in **Teach Me** or **Do It**; Chiron picks Teach Me for any skill not yet mastered, and the user can always say "just do it".

### 1. Teach Me: "Play some devotional songs on YouTube"

1. The user holds fn and speaks. The Voice Bar shows the words as they are heard.
2. Jev classifies the intent (*play a YouTube video*) and the mode (*Teach Me*, because this skill card is new). No Claude call yet.
3. Claude Haiku plans the steps once, from the window's accessibility text and a screenshot if needed: open Chrome, click the address bar, type youtube.com, click search, say or type the search, click a video.
4. Chiron says: *"Let's do it together. First, click the round Chrome icon at the bottom."* An arrow and a ring point at the icon.
5. The user clicks. Jev checks the new screen against the expected result (*"Chrome is open and in front"*). Correct: *"Well done. Now click the long bar at the top."*
6. At the search box, Chiron offers: *"You can say it instead: hold fn and say what to search."*
7. The video plays. Chiron saves a skill card, *Play a video on YouTube*: 6 steps, 1 hint, mastery 2 of 5, practice due in 2 days. Home's Skills tile gains a star.

### 2. Practice, two days later

1. The Voice Bar shows a small dot; Home's Today tile says *Play a video on YouTube*. Chiron asks: *"Want to show me how you play a video on YouTube?"*
2. The user says yes. This time there are no arrows; Chiron only watches.
3. The user opens Safari instead of Chrome. Jev's check returns *wrong app* with high confidence. Chiron: *"That's Safari. Chrome is the round, colourful one, here."* One arrow appears, for that step only.
4. The user finishes. Mastery rises to 3 (one hint), the next practice is set 5 days out, and "opening the right browser" appears under Weak spots until it is done cleanly twice.
5. "Not now" moves the practice to tomorrow. Chiron never asks more than twice a day.

### 3. Do It: "Just play it"

For a tired evening or a mastered skill, Chiron replays the saved steps with no AI at all (the base app's shortcut replay) and says what it did: *"Done. You can also do this yourself next time."* A skill at mastery 5 stops asking for practice.

### 4. Paper Studio: a teacher's test paper

1. *"Class 7 science, chapter 4, heat. 20 marks, 5 multiple choice, 4 short answers, 1 diagram question."*
2. Chiron repeats the plan in one line and asks one question: *"Answer key too?"*
3. Claude Sonnet writes the paper from her saved style note. Chiron builds a .docx and opens it in Word.
4. She edits by voice: *"Make question 3 easier"*, *"marks on the right"*. The open document updates.
5. *"Looks good, print it"*: Chiron confirms once, then prints. Her edits are folded into the style note.
6. *"Teach me how to make a table"* becomes a normal Teach Me lesson.

### 5. Guardian: a fake virus alert

1. A full-screen page says *"Your Mac is infected. Call support now."*
2. The Guardian sees a new window; local rules flag it and Jev scores it as a scam with high confidence.
3. A large card covers the page: *"Stop. This is a scam. Don't call that number. I'll close this page."* One tap closes the tab.
4. The site is blocked from then on, and Home's Guardian tile counts it.

## Design and innovation

Chiron should feel like a calm study room rather than a control panel: warm paper colours, large type, one accent colour, and one obvious next action on every screen.

&#91;embedded content: Home wireframe · one page, nine tiles\]

The Today tile is the only accented element, so the eye lands on the next action first; every other tile is a quiet summary with one action at most.

### Visual language

- **Palette:** warm paper background, deep ink text, one amber accent for the next action, green for done, red only for Guardian. Full dark mode, and the macOS Increase Contrast setting is respected.
- **Type:** Inter for Latin text and Noto Sans Devanagari for Hindi, bundled in the app (no web fonts, works offline). Body 17 pt minimum, headings 24 pt, captions over lessons 20 pt.
- **Shape:** rounded cards (12 pt radius), 24 pt gaps, no dense tables, at most one button per tile.
- **Motion:** slow and soft (200 to 300 ms), and none when Reduce Motion is on, as the base app already does.
- **Voice:** short, warm sentences. Praise first. No jargon ("the long bar at the top", not "the URL field").

### What is new here

1. **Skill constellation.** Each skill is a star; its brightness is its mastery. Skills for one app form a constellation (YouTube, WhatsApp, Word), and a constellation's lines draw in when all its stars are mastered. Progress that reads at a glance, and a quiet nod to the name.
2. **Ghost hand.** When a learner is stuck in Practice, a translucent pointer moves to the right spot and taps without clicking, built on the base app's animated pointer from Draw on screen. They see the move, then make it themselves.
3. **Weak-spot drills.** "Practice this" on a weak spot runs a 60-second drill of only that step, three times, instead of the whole task.
4. **Instant language switch.** Captions are stored in both languages on each skill card, so flipping EN to हिं mid-lesson changes the words and the voice immediately, with no AI call.
5. **Explain it back.** After a lesson, Chiron can ask "How would you do this next time?" and Jev scores the spoken answer. Understanding counts toward mastery, not only clicks.
6. **Cost you can see.** AI spend sits on Home next to progress, so the cost cap is never a surprise.
7. **Style card.** Paper Studio shows the teacher's learned format as a plain card she can correct, rather than hidden settings.

## What we take from the base app

Chiron builds on the base app, v1.5.3 (MIT) and keeps its hands, eyes, ears and safety gate; it replaces the goal of the brain (from "do it fast" to "teach, then check") and replaces its many settings tabs with one Home page. The Technical Build Plan maps every part with file and line references.

The base app is three pieces: `upstream.swift` (7,535 lines: menu-bar app, overlay, speech, hotkeys, drawing, accessibility "hands", onboarding, settings), `upstream.py` (7,874 lines: a brain started as a fresh subprocess for every ask, which drives `claude -p` and prints tagged lines back to Swift), and WKWebView pages in `ui/`. Settings live in `~/.config/chiron/settings.json`, read and written by both the Swift app and the Python brain.

| Keep | Why Chiron needs it |
| --- | --- |
| Speech capture (`Mic`, `SpeechAnalyzer`, `SpeechTranscriber` / `DictationTranscriber`) | On-device listening; the hardcoded `en-US` becomes a probed locale |
| fn handling (NSEvent monitors, `chironFnKey`, the "Press 🌐 key" check) | fn as the only talk key |
| Dictation pill and `DictationData` counters (words, sessions, time saved) | Voice Bar and the Words spoken tile |
| Draw on screen (`ScreenDrawing`, `DrawingStep` with `wait`, `hit`, `target`, `say`) | Every lesson step |
| Hands (`enum Hands`: accessibility map, click, type, menus, background input) | Do It, step checks, Ghost hand |
| `look()`, `window_text()`, `--text` OCR | What Jev and Claude see |
| `fast()`, `learn()`, `replay()`, `skills.json` | Free Do It replays; skill card steps |
| Memory (`memory.md`, `me.json`) | Household facts, style note |
| `gate()`, `risky()`, `DENIED`, safe mode | Ask-first and blocked actions |
| Routines (launchd plists) and `watch()` | Practice reminders and Guardian polling at no cost |
| `log.jsonl` costs and `--budget` | AI spend tile and the monthly cap |
| Onboarding permission flow | First launch |
| Tests and mock-bridge pages | Safety net for every phase |

**Change:** speech locale; system prompt (teaching, bilingual); skill card schema; Voice Bar replaces the box as the default surface; one Home page replaces `settings.html`; provider layer adds Anthropic and OpenAI keys beside Claude Code; Jev client; Keychain for keys; build moves to CI; git updater becomes Sparkle.

**Remove:** Meeting Copilot, background agents and named agents (routines are rewired off them), MiniScreen preview UI (its window-target helpers stay), Devin and Pi, Spotify helpers, Gumroad and tip jar, "ideas", PostHog telemetry, Nix files.

## Architecture

Chiron has one input path, four modes, four shared services and one page of UI; Jev makes every fast decision, and Claude is called only to plan something new or to write.

&#91;embedded content: Chiron architecture · input, four modes, shared services, Home\]

Speech becomes text, Jev picks the skill and mode, and the mode uses the shared services. Guardian runs on its own, triggered by new windows. Home and Settings read the same local files the modes write.

| Decision | Engine | Typical time and cost |
| --- | --- | --- |
| Which skill, which mode | Jev Choice | Under 0.5 s, about $0.0001 |
| Did this step succeed | Jev Noul + Choice | Under 0.5 s, about $0.0001 |
| How well did they do | Jev Score | Under 0.5 s, about $0.0001 |
| Is this page a scam | Local rules, then Jev | Free, or about $0.0001 |
| Steps for a new task | Claude Haiku | 2 to 5 s, about $0.008 |
| Writing a paper | Claude Sonnet | 15 to 40 s, about $0.10 |

Jev times come from the reported 70 to 500 ms per decision; Claude times are estimates to measure in Phase 1.

## Learning engine

Every lesson becomes a skill card with its steps, a mastery level from 0 to 5 and a next practice date; Jev grades each step, the practice gap grows only after success without help, and repeated trouble on a step makes it a weak spot.

### Skill card

A skill card extends a base-app's `skills.json` entry and lives in `~/.config/chiron/skills.json`.

```json
{
  "id": "youtube-play",
  "title": {"en": "Play a video on YouTube", "hi": "YouTube पर वीडियो चलाना"},
  "app": "YouTube",
  "asked": ["play some devotional songs on youtube"],
  "steps": [
    {"say": {"en": "Click the round Chrome icon at the bottom", "hi": "नीचे क्रोम का गोल आइकन दबाइए"},
     "target": "Dock > Google Chrome", "expect": "Google Chrome is open and frontmost"},
    {"say": {"en": "Click the long bar at the top", "hi": "ऊपर वाली लंबी पट्टी पर क्लिक कीजिए"},
     "target": "Chrome > address bar", "expect": "The address bar is focused"}
  ],
  "cmds": ["open -a 'Google Chrome' 'https://www.youtube.com/results?search_query={q}'"],
  "slots": {"q": "devotional songs"},
  "mastery": 2,
  "attempts": [{"at": "2026-10-28", "mode": "teach", "hints": 1, "wrong": [{"step": 0, "kind": "wrong_app"}]}],
  "next_practice": "2026-10-30"
}
```

- `steps` drive Teach Me and Practice: what to say (both languages), where to point, what the screen should show afterwards.
- `cmds` are the base app's replayable commands for Do It, saved only when the base app's `learn()` filters accept them (no deletes, no risky or one-off commands).
- `slots` let one card serve many asks ("devotional songs", "old Hindi film songs", "the news").

### Teaching loop, per step

1. Draw the target with the base app's `draw()` and speak `say` in the current language.
2. Wait for a click, a typed value or a spoken "next" (the drawing step's existing `wait` and `hit` behaviour).
3. Send one Jev request: Noul *"is it true that {expect}?"* and Choice *wrong app / wrong place / nothing happened / still loading / correct*.
4. Correct (Noul above 0.8): praise, next step. Still loading: wait 2 s and ask again. Wrong with high confidence: one gentle hint and a redraw. Low confidence: ask the user a yes/no question instead of guessing.
5. After three hints on one step, Chiron offers the Ghost hand, then offers to do the step itself.

### Mastery and practice schedule

After each attempt Jev scores it (5 = no hints, no mistakes; 0 = Chiron did it), and code combines that with the old level so the rule stays tunable.

| Mastery | Meaning | Next practice |
| --- | --- | --- |
| 0 | Seen once; Chiron did most of it | Next day |
| 1 | Done with many hints | 1 day |
| 2 | Done with 1 or 2 hints | 2 days |
| 3 | Done alone once | 5 days |
| 4 | Done alone twice in a row | 12 days |
| 5 | Mastered | No more practice; Do It by default |

A mistake in practice drops the level by one, never to zero. Practice reminders use the base app's routine system (launchd wake, no cost while waiting) and appear only when the Mac is in use and no call or full-screen video is running.

### Weak spots

A step becomes a weak spot when it needs a hint or goes wrong in 2 of the last 3 attempts, across any skill. Steps are grouped by what they teach ("open the right app", "find the address bar", "scroll", "use the back button"), so trouble that shows up in several skills is caught once. Home lists the top 3, each with a 60-second drill; a weak spot clears after two clean attempts.

### Memory

The base app's memory (`remember_rule()`, profile facts) keeps what Chiron learns about the household: favourite singers and channels, the school and classes taught, preferred browser, speaking pace. If most steps need hints, Chiron speaks slower and draws larger arrows.

## Paper Studio

Paper Studio learns a teacher's paper format from her own past papers and drafts every new paper in that format as a Word .docx; there are no built-in exam templates.

### Learn the style (once, about 10 minutes)

1. Drop 3 to 6 old papers on Home's Papers tile, or say "look at my old papers" and point at a folder. Accepted: .docx, .pdf, photos of printed papers.
2. Chiron reads them (python-docx for Word, pdfplumber for PDF, Claude vision for photos), and Claude Sonnet writes a **style note**: structured JSON plus plain rules.
3. The style note appears as a **style card** to confirm or correct: "Your header has school name, class, subject, marks and time. Right?"

The style note records: header fields and order; section names and numbering; question numbering; where marks go; option format for multiple choice; the usual mix of question types; medium of instruction; font, size, margins, spacing, answer space; instructions and footer; answer key format.

### Make a paper by voice

1. The teacher gives topic, class, marks and mix; anything missing comes from the style note, with at most one question.
2. Claude Sonnet writes the paper as JSON (sections, questions, marks), with the style note cached in the prompt.
3. Code checks the total marks and question counts.
4. A python-docx builder turns the JSON into a .docx in that style, saves it to *Documents/Chiron Papers/\<class>/\<subject>/\<date> \<topic>.docx*, and opens Word. The answer key goes on a last page or its own file.
5. Voice edits change the JSON and rebuild; small edits can be typed in place with the base app's hands.

### Keep learning

When she saves a hand-edited paper, Chiron compares it with its draft and asks Claude Haiku what rule the change suggests. A new rule joins the style note after one confirmation.

### Word and Google Docs

- **Word (default):** .docx built locally; no account needed.
- **Google Docs (optional):** upload the .docx to Drive and open it in Docs through Chrome. No Google API keys in v1.
- **Formatting lessons:** tables, bold, page numbers, pictures, printing two copies are ordinary Teach Me lessons with skill cards.

## Guardian

Guardian screens every new window, tab and on-screen message in three layers and interrupts only when fairly sure; most checks never reach an AI.

**Layer 1, local rules, free.** Phrase lists in English and Hindi ("your computer is infected", "call support", "account blocked", "verify your account", "share the OTP", "you have won"), support phone numbers on alarming pages, prompts to install remote-control apps (AnyDesk, TeamViewer, QuickSupport, RustDesk), full-screen pages that block closing, and look-alike domains for common banks and government sites. Runs on the base app's `watch()` polling pattern with `window_text()` and `window_summary()`.

**Layer 2, Jev, only on a red flag.** One request with the page text and three questions in parallel: Noul *"the page pushes the user to call, install software or share a code"*, Noul *"the page pretends to be an organisation it is not"*, Score 0 to 5 *"how likely is this a scam aimed at a new computer user"*. Score 4 or more with high confidence: block. Score 2 to 3, or low confidence: one Claude Haiku check with a screenshot. Below 2: nothing.

**Layer 3, the warning.** A large calm card covers the page and gives the reason in one line ("Real companies never ask you to call from a pop-up"). Two buttons: **Close it** (default) and **I know this site, continue**, which needs a spoken yes. The site joins a local block list and Home's Guardian tile.

**Always on.** Chiron never types passwords, one-time codes, card, bank or ID numbers; never installs remote-access apps; keeps the base app's ask-first gate for send, buy and delete; blocks payments in v1; and warns about money requests from unknown numbers in messaging apps.

## Speech and languages

Chiron listens with Apple's free on-device speech first and falls back to a cloud recogniser only when the chosen language is missing or keeps mishearing; English and Hindi are supported in v1, and the language layer is built so more can be added.

The base app uses `SpeechAnalyzer` with `SpeechTranscriber` locked to `en-US`. Apple's [SpeechTranscriber docs](https://developer.apple.com/documentation/speech/speechtranscriber.md) say to check `supportedLocales` and `installedLocales`, and to consider `DictationTranscriber` when `SpeechTranscriber` cannot serve a device. Hindi support on macOS 26 is not stated there, so Chiron probes it at launch and shows the result in Settings.

| Order | Engine | Cost | Used when |
| --- | --- | --- | --- |
| 1 | Apple `SpeechTranscriber`, current app language | Free, on-device | The locale is supported |
| 2 | Apple `DictationTranscriber`, same locale | Free, on-device | 1 is unavailable |
| 3 | [Sarvam Saaras](https://docs.sarvam.ai/api-reference-docs/getting-started/models/saaras.md), `codemix` mode | About ₹0.49 a minute ([pricing](https://docs.sarvam.ai/api-reference-docs/pricing.md)) | On-device Hindi is missing or weak; key added in Settings |
| 4 | Apple `en-US` (today) | Free | Offline fallback |

Saaras handles mixed-language speech: its `codemix` mode writes English words in Latin script and Hindi words in Devanagari, across 23 languages. Audio goes to the cloud only while fn is held.

**Understanding.** A normaliser maps Devanagari, romanised Hindi and English to one form before routing, and the base app's dictation dictionary (`dictate_hints()`, `dictate_spellings()`) fixes names and app words.

**Speaking.** Apple's built-in voices for each language through the base app's `ReadAloudVoice` picker (free, offline); Sarvam Bulbul optional at about ₹1 per 1,000 characters. Default speed 0.85x, and every spoken line also appears on screen. "Say that again" repeats the last line with no AI.

## Cost plan

Expected AI spend is about $3 to $5 a month on pay-as-you-go keys, with a hard cap that stops cloud calls at $5; most of the saving comes from never calling an AI for something Chiron already knows.

**Cheapest first.** (1) No AI: instant commands, learned replays, "say that again", practice reminders, Guardian layer 1, marks checks. (2) Jev: every yes/no or pick-one decision, at $0.042 per million input tokens with free output ([eesel summary of TypeSafe pricing](https://www.eesel.ai/blog/typesafe-jev-pricing)) and a reported 70 to 500 ms per decision. (3) Claude Haiku 4.5 for new lesson plans and questions, at $1 per million input, $5 per million output, $0.10 per million cached input ([pricepertoken](https://pricepertoken.com/pricing-page/model/anthropic-claude-haiku-4.5)). (4) Claude Sonnet only for papers and style notes.

Assumptions: 20 asks a day (half free replays), 2 new lessons a day, 20 Guardian checks a day reaching Jev, 3 papers a week, 10 minutes of speech a day.

| Item | Volume a month | Estimated cost |
| --- | --- | --- |
| Jev (steps, routing, Guardian) | about 9 million input tokens | about $0.40 |
| Claude Haiku (lessons, questions) | about 300 asks | about $1.20 |
| Claude Sonnet (papers, edits) | about 13 papers | about $1.50 (approximate) |
| Apple speech | 300 minutes | $0 |
| Sarvam speech, only if needed | 300 minutes | about $1.70 |
| **Total** |  | **about $3.10, or $4.80 with Sarvam** |

**Plan or key.** API keys are cheapest for light use. Claude Code on an existing Claude Pro or Max plan (the base app's default) adds no cost if the household already pays for one. Local models through Ollama or LM Studio are free but weaker at tool use.

**Guards in code.** Prompt caching on the system prompt and style note; the base app's system-prompt budget test (under 10,000 characters) and `--budget` report kept; accessibility text first, a 1,024-px screenshot only when needed; one batched Jev request per step; a monthly cap tracked from each call's cost, with papers moving to Haiku at 80% and only free features at 100%; no telemetry and no AI while idle.

## Install: one DMG, keys later

Chiron installs by downloading `Chiron.dmg` from GitHub Releases and dragging it to Applications; free features work immediately, and keys are added later in Settings.

The base app installs with `curl … install.sh | bash`, which clones the source and compiles it with `swiftc` on the user's Mac, needing Xcode command line tools and Python. Chiron moves all of that to GitHub Actions: a universal Swift build, a bundled relocatable Python with its packages, the Home page and fonts inside the app bundle, Developer ID signing and notarisation (Apple Developer Program, $99 a year), a DMG with a drag-to-Applications background, and Sparkle auto-updates in place of the base app's git updater.

**First launch, about 15 minutes:** a welcome screen with the language switch; permissions one at a time (Microphone, Speech Recognition, Accessibility, Screen Recording, Automation) using the base app's drag-to-grant help; a one-click fix so fn does not open the emoji picker; a check for on-device speech and voices; Settings connections (skippable); optional old papers for Paper Studio; then a two-minute first lesson.

## Privacy and safety

Everything Chiron learns stays in `~/.config/chiron/` on the Mac with owner-only file modes, keys stay in the Keychain, and only the text or screenshot needed for one decision leaves the machine.

- **Stored locally:** skill cards, memory and style note, history with costs (no audio, no screenshots), the Guardian block list, Home's counters.
- **Sent to Claude:** the ask, window text or a downscaled screenshot, and at most 15 relevant memory lines (the base app's `relevant_rules()`).
- **Sent to Jev:** text only, plus the questions.
- **Sent to Sarvam (if enabled):** audio while fn is held.
- **Safety:** The base app's Safe mode sandbox stays on; `rm`, `sudo`, disk tools and shutdown stay blocked, plus settings changes, app installs, payments and remote-access apps; send, delete, move, print and upload ask first by voice; "Chiron, stop" pauses everything.
- **No telemetry:** The base app's PostHog calls and failure reports are removed.
- **Your data, your call:** Settings exports or deletes everything.

## Roadmap

Five two-week phases build the tutor from 2 November, and week 11 ships the DMG; each phase builds its slice of the Home page first, then the backend behind it, and ends with one report and a test checklist.

&#91;embedded content: Chiron roadmap · 5 phases, 5 gates, then the DMG release\]

Each diamond is a go or no-go check run on the real Mac. The Technical Build Plan holds the full task list, file changes and test steps for every phase. Dates assume part-time work.

## Risks and open questions

The two biggest risks are Hindi recognition quality and Jev access; Phase 1 tests both before anything else depends on them.

| Risk | Effect | Plan |
| --- | --- | --- |
| On-device Hindi or mixed speech is missing or weak | Wrong asks | Locale probe in Phase 1; Sarvam `codemix` fallback; household dictionary |
| Jev is behind a waitlist ([eesel](https://www.eesel.ai/blog/typesafe-jev-pricing) found no self-serve tier) | No fast checks at launch | Join now; try Cloudflare Workers AI (`typesafe/jev`); Haiku fallback behind the same interface |
| Jev pricing changes | Higher cost | Monthly cap; Haiku fallback; batched checks |
| A wrong correction | Learner loses trust | Act only on high confidence; otherwise ask a yes/no question |
| macOS 26 required (the base app's speech APIs) | Older Macs cannot run it | Check the Mac first |
| No paid Apple developer account | Unsigned DMG shows a warning | $99 a year Developer Program, or right-click, Open once |
| App layouts change (YouTube, WhatsApp, Word) | Saved steps stop matching | Targets by accessibility label, not coordinates; a failed replay re-plans once, as the base app does |
| Too many reminders | Annoyance | At most two practices a day; "not now" always works |
| Claude plan used through Claude Code inside another app | Plan terms may limit this | API keys by default; Claude Code optional, as in the base app |

**Open questions:** Which Mac and macOS version? Chrome or Safari as the main browser? Is Microsoft Word installed? Which subjects and classes this year? Which 10 tasks come up most?

## Sources

- The base app's repository and README (see `CREDITS.md`; code read from version 1.5.3, 28 Oct 2026)
- [TypeSafe docs: Introduction to Jev](https://docs.typesafe.ai/introduction)
- [eesel: TypeSafe Jev pricing (2026)](https://www.eesel.ai/blog/typesafe-jev-pricing)
- [Wispr Flow: navigating the app and the Flow Bar](https://docs.wisprflow.ai/articles/5096240724-navigating-the-wispr-flow-app-desktop-ios-and-android)
- [Wispr Flow: supported keyboard shortcuts](https://docs.wisprflow.ai/articles/2612050838-supported-unsupported-keyboard-hotkey-shortcuts)
- [Apple: SpeechTranscriber](https://developer.apple.com/documentation/speech/speechtranscriber.md)
- [Sarvam: Saaras speech-to-text](https://docs.sarvam.ai/api-reference-docs/getting-started/models/saaras.md)
- [Sarvam: API pricing](https://docs.sarvam.ai/api-reference-docs/pricing.md)
- [Price Per Token: Claude Haiku 4.5](https://pricepertoken.com/pricing-page/model/anthropic-claude-haiku-4.5)
