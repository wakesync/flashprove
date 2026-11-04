#!/usr/bin/env python3
"""Builds the attacked-reply requests of PREREG.md from #45's committed raw files (no decoding, no GPU).

usage: gen_requests.py OUT_DIR
Writes OUT_DIR/in-<k>/<name>.req (64 or fewer per folder), OUT_DIR/requests.json (prompt, reply,
class, #45's committed cost vector for that reply) and OUT_DIR/fit/policy.txt (the fit-point copy of
target_small_f2_gap/policy.txt). Request layout as experiments/20261103-6-clipped-gap-rejection/
cp_verify_spot.py request(): prompt, reply, zeros to T, r = len(prompt) - 1, e = len(prompt) + len(reply) - 1.
"""
import gzip
import json
import random
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'research/acceptance/clipped-gap/raw'
KIT = ROOT / 'prover/examples/target_small_f2_gap'
SEED = 2026
CLASSES = ['honest', 'fp2nd-1-redecode', 'rand-1-redecode', 'fp2nd-4', 'rand-4', 'int2nd-4', 'rand-1', 'rand-reply']
PER_CLASS = 16
T = 64
POLICIES = {'shipped': (9244130, 323343, 1), 'fit': (5178975, 203143, 1)}


def request_bytes(prompt, reply):
    assert prompt and reply and len(prompt) + len(reply) <= T + 1
    return struct.pack('<%dI' % (T + 2), *(prompt + reply + [0] * T)[:T], len(prompt) - 1, len(prompt) + len(reply) - 1)


def meets(costs, policy):
    C, theta, cap = policy
    return sum(min(c, C) for c in costs) <= theta * len(costs) and sum(c > C for c in costs) <= cap


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    seed = json.loads(gzip.open(RAW / f'seed{SEED}.json.gz').read())
    red = json.loads(gzip.open(RAW / f'redecode{SEED}.json.gz').read())
    rng = random.Random(2026001)
    rows = []
    for cls in CLASSES:
        if cls == 'honest':
            items = {str(i): {'prompt': seed['prompts'][i], 'reply': seed['replies'][i]} for i in range(64, 128)}
            costs = seed['classes']['honest']
        elif cls.endswith('-redecode'):
            items, costs = red['attacked'][cls], red['classes'][cls]
        else:
            items, costs = seed['attacked'][cls], seed['classes'][cls]
        keys = sorted(k for k in items if costs.get(k) is not None)
        for k in sorted(rng.sample(keys, PER_CLASS), key=int):
            it = items[k]
            c = costs[k]
            name = f'{cls.replace("-", "_")}_{k}'
            rows.append({'cls': cls, 'index': int(k), 'name': name, 'prompt': it['prompt'], 'reply': it['reply'],
                         'costs_45': c, 'score_meets': {p: meets(c, v) for p, v in POLICIES.items()}})
    for k in range(0, len(rows), 64):
        d = out / f'in-{k // 64}'
        d.mkdir()
        for r in rows[k:k + 64]:
            (d / f'{r["name"]}.req').write_bytes(request_bytes(r['prompt'], r['reply']))
    fit = out / 'fit'
    fit.mkdir()
    C, theta, cap = POLICIES['fit']
    lines = []
    for line in (KIT / 'policy.txt').read_text().splitlines():
        w = line.split()
        lines.append({'C': f'C {C}', 'theta': f'theta {theta}', 'cap': f'cap {cap}'}.get(w[0] if w else '', line))
    (fit / 'policy.txt').write_text('\n'.join(lines) + '\n')
    (out / 'requests.json').write_text(json.dumps(rows, indent=1) + '\n')
    for p in POLICIES:
        print(p, 'score meets:', {c: sum(r['score_meets'][p] for r in rows if r['cls'] == c) for c in CLASSES})


if __name__ == '__main__':
    main()
