# Credits

Chiron stands on open-source work. This file is the one place it is credited; the notices below are kept as their licenses require.

## The base app: Atticus

Chiron began as a fork of **Atticus** (version 1.5.3), a voice-driven Mac helper by SaarthurR: https://github.com/SaarthurR/atticus-mac. Atticus's idea came from Caleb Writes Code's "Atticus". Chiron keeps its process model and core (on-device speech, the instant path and learned shortcuts, Hands, drawing on screen, memory, routines and the safety gate), renames it, removes what a tutor doesn't need, and adds Home, Settings, Jev and the teaching features.

**Using it:** Atticus's upstream repository is the place to look for the original design and history, and for fixes worth bringing over. Keep it as a git remote (`git remote add upstream https://github.com/SaarthurR/atticus-mac.git`), cherry-pick or port changes by hand, and keep this notice whenever Atticus code ships with Chiron.

Atticus is released under the MIT License:

```
MIT License

Copyright (c) 2026 SaarthurR (Atticus)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Other components

- **thinking-orbs** (`ui/orbs.js`), MIT: https://github.com/Jakubantalik/thinking-orbs
- **Plip** (ideas and some Hands logic), MIT: https://github.com/hussainn7/plip-oss; full notice in [LICENSE-Plip](LICENSE-Plip)
- **Cua Driver** (background key authentication and menu-shortcut technique), MIT: https://github.com/trycua/cua
- **Inter** and **Noto Sans Devanagari** fonts (`ui/fonts/`), SIL Open Font License 1.1; licences in `ui/fonts/OFL-*.txt`
