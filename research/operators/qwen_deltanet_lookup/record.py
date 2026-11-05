#!/usr/bin/env python3
"""CPU-only receipt for Qwen DeltaNet M1b with the RNG/LKP smallness test (lookup.h).

Fixtures come from research/operators/qwen_deltanet/reference.py (M1, unchanged). Compiles
test.cpp, runs one honest proof per seed 1..10 (one process each, sequential, pinned to 6 cores),
the hostile suite on seed 1, and H3b: honest proofs of the R3 window where M1 overflowed.
Writes evidence.json here and raw lines to experiments/20261105-32-qwen-deltanet-m1b-lookup/runs/.
Usage: record.py [build] [honest] [hostile] [h3b]
"""
import hashlib, json, os, pathlib, platform, statistics, subprocess, sys, time
import numpy as np
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(root / 'research/operators/qwen_deltanet'))
import reference as R
rel = str(here.relative_to(root))
exp = root / 'experiments/20261105-32-qwen-deltanet-m1b-lookup/runs'
work = here / 'work'; work.mkdir(exist_ok=True); exp.mkdir(parents=True, exist_ok=True)
SEEDS = list(range(1, 11))
CORES = os.environ.get('M1B_CORES', '0-5')
only = sys.argv[1:]

def sh(argv, timeout=7200):
    t = time.monotonic(); p = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=timeout)
    return dict(argv=[str(a) for a in argv], exit=p.returncode, seconds=round(time.monotonic() - t, 3), stdout=p.stdout, stderr=p.stderr[-4000:])

ev_path = here / 'evidence.json'
ev = json.loads(ev_path.read_text()) if ev_path.exists() and only else {}
ev.update(platform=platform.platform(), python=sys.version.split()[0], cores=CORES,
          compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
          base=subprocess.check_output(['git', 'merge-base', 'HEAD', 'origin/main'], cwd=root, text=True).strip(),
          sources={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                   [here / 'test.cpp', here / 'lookup.h', here / 'record.py', root / 'research/operators/qwen_deltanet/reference.py',
                    root / 'research/operators/qwen_deltanet/product.h', root / 'blocks/iop/rng.h', root / 'blocks/iop/lkp.h']})
def save(): ev_path.write_text(json.dumps(ev, indent=1) + '\n')
binary = work / 'test.bin'
def run_bin(fx, mode):
    return sh(['taskset', '-c', CORES, str(binary.relative_to(root)), str(fx.relative_to(root)), mode])
def st(x):
    return dict(n=len(x), median=statistics.median(x), sd=statistics.stdev(x) if len(x) > 1 else 0, min=min(x), max=max(x))

if not only or 'build' in only:
    fx = {}
    for s in SEEDS:
        out = work / f'seed{s}.bin'
        meta = R.write_fixture(str(out), s)
        fx[s] = dict(meta=meta, sha256=hashlib.sha256(out.read_bytes()).hexdigest())
    ev['fixtures'] = fx
    c = sh(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks',
            f'{rel}/test.cpp', '-o', str(binary.relative_to(root))])
    ev['compile'] = c; save(); assert c['exit'] == 0, c['stderr']

if not only or 'honest' in only:
    runs = []
    for s in SEEDS:
        c = run_bin(work / f'seed{s}.bin', 'honest')
        line = json.loads(c['stdout'].splitlines()[0]) if c['stdout'] else {}
        runs.append(dict(seed=s, exit=c['exit'], wall=c['seconds'], **line, stderr=c['stderr']))
        print(json.dumps({k: v for k, v in runs[-1].items() if k != 'stderr'}), flush=True)
        (exp / 'honest.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in runs))
    ok = [r for r in runs if r.get('accept')]
    ev['honest'] = dict(accepted=len(ok), of=len(runs), prove_s=st([r['prove_s'] for r in ok]), verify_s=st([r['verify_s'] for r in ok]),
                        proof_bytes=st([r['proof_bytes'] for r in ok]), peak_rss_kb=st([r['peak_rss_kb'] for r in ok]),
                        prove_s_without_first=st([r['prove_s'] for r in ok[1:]]) if len(ok) > 2 else None)
    save()

if not only or 'hostile' in only:
    c = run_bin(work / 'seed1.bin', 'hostile')
    (exp / 'hostile-seed1.jsonl').write_text(c['stdout'])
    lines = [json.loads(l) for l in c['stdout'].splitlines() if l.startswith('{')]
    hs = [l for l in lines if l.get('mode') == 'hostile']
    by = {}
    for l in hs: by.setdefault(l['class'], [0, 0]); by[l['class']][0] += l['rejected']; by[l['class']][1] += 1
    ev['hostile'] = dict(exit=c['exit'], seconds=c['seconds'], rejected=sum(l['rejected'] for l in hs), total=len(hs), by_class=by, stderr=c['stderr'])
    print(json.dumps(ev['hostile']), flush=True); save()

if not only or 'h3b' in only:
    # The R3 window: T = 4 tokens ending at the first step where |delta| >= 2^18 (M1's overflow).
    res = []
    for s in range(1, 6):
        toks = R.gen_tokens(s, 'R3', 1024, 12)
        S = np.zeros((R.D, R.D), dtype=np.int64); first = None; states = [S]
        for t, tok in enumerate(toks):
            M, delta, S, o = R.step(S, tok, 12, check=False); states.append(S)
            if first is None and np.abs(delta).max() >= R.BOUND: first = t; break
        t0 = first - 3; S0 = states[t0]; rec = []; Sx = S0
        for tok in toks[t0:first + 1]:
            M, delta, Sx, o = R.step(Sx, tok, 12, check=False); rec.append((M, delta, Sx.copy(), o))
        out = work / f'r3_seed{s}.bin'
        arr = [np.array([4, R.D, 12], dtype=np.int64), S0.reshape(-1)]
        for tok in toks[t0:first + 1]: arr += [np.array([tok['a'], tok['beta']], dtype=np.int64), tok['k'], tok['v'], tok['q']]
        for M, delta, Sx2, o in rec: arr += [M, delta, Sx2.reshape(-1), o]
        np.concatenate(arr).astype('<i8').tofile(out)
        meta = dict(seed=s, window=[t0, first], max_abs_delta=int(max(np.abs(r[1]).max() for r in rec)), max_abs_v=int(max(np.abs(t['v']).max() for t in toks[t0:first + 1])),
                    max_abs_S=int(max(np.abs(r[2]).max() for r in rec)), max_abs_M=int(max(np.abs(r[0]).max() for r in rec)))
        c = run_bin(out, 'honest')
        line = json.loads(c['stdout'].splitlines()[0]) if c['stdout'] else {}
        res.append(dict(meta, exit=c['exit'], **line, stderr=c['stderr']))
        print(json.dumps({k: v for k, v in res[-1].items() if k != 'stderr'}), flush=True)
        (exp / 'h3b-r3.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in res))
    ev['h3b'] = dict(accepted=sum(1 for r in res if r.get('accept')), of=len(res)); save()
