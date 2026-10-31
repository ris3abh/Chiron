#!/usr/bin/env python3
"""Builds a stand-in for the family Mac: the asks in tests/audio/asks.json spoken by macOS voices, then made slower, softer,
further away and over a TV, and scored with `chiron.py --speech-eval`. Needs ffmpeg. It is a rehearsal: real voices decide the gate.
    scripts/speech-rooms.py <empty folder>"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICES = {'hi': 'Lekha', 'en': 'Rishi'}
TV = ('Good evening. Here are the headlines. The finance minister spoke to reporters in Delhi this morning about the new budget. '
      'Rain is expected across Maharashtra over the next three days. In cricket, India won the second match by six wickets. ') * 4
ROOMS = {   # ffmpeg filters on the spoken ask; "tv" also mixes the news under it
    'close': ('', False, 175),
    'slow': ('', False, 115),
    'soft': ('volume=-20dB', False, 175),
    'far': ('highpass=f=180,lowpass=f=3200,aecho=0.8:0.7:35|70:0.35|0.2,volume=-12dB', False, 175),
    'tv': ('', True, 175),
    'parents': ('highpass=f=180,lowpass=f=3200,aecho=0.8:0.7:35|70:0.35|0.2,volume=-16dB', True, 115),   # all of it at once
}


def run(*args): subprocess.run(args, check=True, capture_output=True)


def main(out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    asks = json.loads((ROOT / 'tests' / 'audio' / 'asks.json').read_text(encoding='utf-8'))
    run('say', '-v', 'Daniel', '-o', str(out / 'tv.aiff'), '--', TV)
    for room, (chain, tv, rate) in ROOMS.items():
        folder = out / room; folder.mkdir(exist_ok=True); rows = []
        for i, ask in enumerate(asks, 1):
            name, voice = f"{ask['lang']}-{i:02}", ask.get('voice') or VOICES[ask['lang']]
            raw = folder / f'{name}.aiff'
            run('say', '-v', voice, '-r', str(rate), '-o', str(raw), '--', ask['say'])
            filters = (chain + ',' if chain else '') + 'apad=pad_dur=0.4'
            if tv:   # the set is about as loud as a person across a room, measured at the Mac
                cmd = ['ffmpeg', '-y', '-i', str(raw), '-ss', str(i * 2), '-i', str(out / 'tv.aiff'), '-filter_complex',
                       f'[0:a]{filters}[a];[1:a]lowpass=f=5000,volume=-20dB[b];[a][b]amix=inputs=2:duration=first:normalize=0,aresample=16000',
                       '-ac', '1', '-c:a', 'pcm_s16le', str(folder / f'{name}.wav')]
            else:
                cmd = ['ffmpeg', '-y', '-i', str(raw), '-af', filters + ',aresample=16000', '-ac', '1', '-c:a', 'pcm_s16le', str(folder / f'{name}.wav')]
            run(*cmd); raw.unlink()
            rows.append({'file': f'{name}.wav', 'lang': ask['lang'], 'text': ask['text']})
        (folder / 'expected.json').write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
        r = subprocess.run([sys.executable, str(ROOT / 'chiron.py'), '--speech-eval', str(folder)], capture_output=True, text=True)
        (folder / 'result.txt').write_text(r.stdout, encoding='utf-8')
        print(room.ljust(8), ' | '.join(l for l in r.stdout.splitlines() if 'understood' in l), flush=True)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]) if len(sys.argv) == 2 else print(__doc__))
