#!/usr/bin/env python3
"""Smoke test: one window at the C given on the command line, prove + verify chunk 0 only."""
import json, pathlib, subprocess, sys, time
here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here))
import window as W
C = int(sys.argv[1]); d = here / 'work' / f'smoke-C{C}'
man = W.build_window(1, C, d)
ch = man['chunks'][0]; b = here / 'work' / 'chunk.bin'
for mode in ('prove', 'verify'):
    t = time.monotonic()
    p = subprocess.run([str(b), mode, str(d / ch['fixture']), str(d / ch['header']), str(d / ch['proof'])], capture_output=True, text=True)
    print(mode, p.returncode, round(time.monotonic() - t, 2), p.stdout.strip(), p.stderr[-500:])
