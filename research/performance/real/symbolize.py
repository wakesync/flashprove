#!/usr/bin/env python3
"""Turns sampler.c's samples into flat (self) and inclusive profiles by function.
usage: symbolize.py <cp_verify built with -fno-omit-frame-pointer -g> <samples.PID.txt>... [--top N]
Uses nm -C for function ranges (no external profiler). Samples at 1 kHz of process CPU time.
"""
import bisect
import collections
import re
import subprocess
import sys


def load_syms(binary):
    out = subprocess.check_output(['nm', '-C', '-S', '--defined-only', binary], text=True)
    syms = []
    for line in out.splitlines():
        parts = line.split(' ', 3)
        if len(parts) == 4 and parts[2] in 'tTwW':
            syms.append((int(parts[0], 16), int(parts[1], 16), parts[3]))
    syms.sort()
    return syms


def main():
    args = sys.argv[1:]
    top = 40
    if '--top' in args:
        i = args.index('--top')
        top = int(args[i + 1])
        del args[i:i + 2]
    groups = []
    while '--match' in args:
        i = args.index('--match')
        groups.append(args[i + 1])
        del args[i:i + 2]
    binary, files = args[0], args[1:]
    syms = load_syms(binary)
    starts = [s[0] for s in syms]

    def name(addr):
        i = bisect.bisect_right(starts, addr) - 1
        if i >= 0 and addr < syms[i][0] + max(syms[i][1], 1):
            return syms[i][2]
        return '?'
    for f in files:
        rows = [list(map(lambda x: int(x, 16), l.split())) for l in open(f) if l.strip()]
        self_c, incl_c = collections.Counter(), collections.Counter()
        group_c = collections.Counter()
        folded_c = collections.Counter()  # self time with library frames (malloc, memset ..) charged to their caller
        for r in rows:
            names = [name(a) if a else '<lib>' for a in r]
            # a return address points after the call: step back one byte for frames past the leaf
            names = [names[0]] + [name(a - 1) if a else '<lib>' for a in r[1:]]
            self_c[names[0]] += 1
            folded_c[next((n for n in names if n != '<lib>'), '<lib>')] += 1
            for n in set(names):
                incl_c[n] += 1
            for g in groups:
                if any(re.search(g, n) for n in names):
                    group_c[g] += 1
        total = len(rows)
        print(f'== {f}: {total} samples (~{total / 1000:.2f} s CPU)')
        for g in groups:
            print(f'-- stacks matching {g!r}: {group_c[g]} ({100 * group_c[g] / max(total, 1):.1f}%)')
        print('-- self')
        for n, c in self_c.most_common(top):
            print(f'{100 * c / total:6.2f}% {c:6d}  {n[:180]}')
        print('-- self, library time charged to the calling function')
        for n, c in folded_c.most_common(top):
            print(f'{100 * c / total:6.2f}% {c:6d}  {n[:180]}')
        print('-- inclusive')
        for n, c in incl_c.most_common(top):
            print(f'{100 * c / total:6.2f}% {c:6d}  {n[:180]}')


if __name__ == '__main__':
    main()
