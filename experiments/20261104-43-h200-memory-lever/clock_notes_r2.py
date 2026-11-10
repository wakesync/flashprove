#!/usr/bin/env python3
"""Descriptive check of the clock-disagreement NOTE lines in the two rental-2 session logs (added 2026-11-10).

measure_rate.py prints, per batch, three readings of the machine's clock at the release (RELEASE, stamp, seen)
and a NOTE when two of them lie more than 2 s apart. The registered figures use RELEASE only. This script counts
the NOTE lines, reports the RELEASE - stamp offsets, and recomputes the median batch interval from the stamp
column instead of RELEASE, to show how far the reported interval depends on which reading is used.
Descriptive only; enters no pass/fail. Reads the committed logs; writes nothing.

usage: python3 experiments/20261104-43-h200-memory-lever/clock_notes_r2.py
"""
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOK = 24 * 1024
ROW = re.compile(r'^\s+(\d+)\s+24\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*$')

for name in ('h200-session-TB1.log', 'h100-session-CA1.log'):
    text = (HERE / 'rental2' / name).read_text()
    notes = [l for l in text.splitlines() if l.startswith('NOTE: batch')]
    rows = [tuple(float(x) for x in m.groups()[1:]) for m in map(ROW.match, text.splitlines()) if m]
    release = [r[1] for r in rows]
    stamp = [r[2] for r in rows]
    seen = [r[3] for r in rows]
    iv_rel = [b - a for a, b in zip(release, release[1:])]
    iv_stamp = [b - a for a, b in zip(stamp, stamp[1:])]
    off = [r - s for r, s in zip(release, stamp)]
    seen_off = [s2 - s for s2, s in zip(seen, stamp)]
    print(name)
    print('  NOTE lines: %d' % len(notes))
    print('  RELEASE - stamp per batch, s: %s' % ' '.join('%.3f' % x for x in off))
    print('  seen - stamp per batch, s:    %s' % ' '.join('%.3f' % x for x in seen_off))
    print('  median interval from RELEASE: %.6f s -> %.4f tok/s' % (statistics.median(iv_rel), TOK / statistics.median(iv_rel)))
    print('  median interval from stamp:   %.6f s -> %.4f tok/s' % (statistics.median(iv_stamp), TOK / statistics.median(iv_stamp)))
