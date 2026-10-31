# Chiron

A Mac tutor that teaches, then checks. Hold <kbd>⌃ control</kbd> <kbd>⌥ option</kbd> <kbd>space</kbd>, say what you need, let go.

Chiron does tasks for people new to computers, teaches them to do the tasks themselves, and checks later that the skill stuck. Under the hood: on-device speech, an instant path and learned shortcuts, Hands, drawing on screen, memory, routines and a safety gate. The plan is in [docs/PRODUCT_PLAN.md](docs/PRODUCT_PLAN.md) and [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md); where the work stands is in [docs/HANDOFF.md](docs/HANDOFF.md).

## Build

You need macOS 26 or later, Apple's command line tools (`xcode-select --install`), Python 3, and [Claude Code](https://claude.com/claude-code) on a paid Claude plan (or a custom server through Claude Code).

```
./build.sh
```

It builds `~/Applications/Chiron.app` (bundle id `com.chiron.app`), keeps its data in `~/.config/chiron`, and starts it at login. Run it again after any change.

## Test

```
python3 -m unittest discover -s tests -v
```

Tests load `chiron.py` as the module `brain` (the `chiron/` package owns the name `chiron`). Tests that compile or drive the native app need a working Swift toolchain; window-driving tests run only with `CHIRON_VM=1` or `CHIRON_ALLOW_HOST_UI=1`.

## Remove

`launchctl bootout gui/$(id -u)/com.chiron.app`, then delete `~/Applications/Chiron.app`, `~/.config/chiron` and `~/Library/LaunchAgents/com.chiron.app.plist`.

## License

MIT, see [LICENSE](LICENSE). Open-source credits and their notices: [CREDITS.md](CREDITS.md). `ui/orbs.js` is from [thinking-orbs](https://github.com/Jakubantalik/thinking-orbs), also MIT. Hands: ideas and some logic adapted from Plip (github.com/hussainn7/plip-oss, MIT, see [LICENSE-Plip](LICENSE-Plip)). Background key authentication and menu-shortcut presses follow Cua Driver (github.com/trycua/cua, MIT).
