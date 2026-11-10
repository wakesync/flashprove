#!/usr/bin/env python3
"""Repeat-timing runner (fix for PR #42 review must-fix 2): n repeats of the same point, same seed, same binary.

  python3 research/model-scale/repeat.py --binary RUN.bin [--n 10] [--jobs 3] [--points d,T,b;...]

Each fixture is generated ONCE per point (deterministic, seed 7, sha256 recorded) and reused for all repeats.
Runs are interleaved round-robin (rep 0 of every point, then rep 1, ...) so slow drift in host load is spread
across points instead of landing on one. Each run is pinned to its own core (taskset). At most --big-slots
points with log_len >= 21 run at once (memory). Hostile provers are skipped (--skip-hostile-provers): they
were already exercised once per point in the original sweep and the review rerun; these runs are for timing.
The 24 static mutations still run and must all be rejected.

Writes results/repeat-t10.jsonl (one raw row per run, incl. loadavg sampled just before and after the run)
and results/repeat-t10-summary.json (median / SD / min / max per point)."""
import argparse, hashlib, json, os, statistics, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
here = Path(__file__).resolve().parent; root = here.parents[1]

ap = argparse.ArgumentParser()
ap.add_argument('--binary', required=True)
ap.add_argument('--n', type=int, default=10)
ap.add_argument('--jobs', type=int, default=3)
ap.add_argument('--first-core', type=int, default=8)
ap.add_argument('--big-slots', type=int, default=2)
ap.add_argument('--seed', type=int, default=7)
ap.add_argument('--work', default='/tmp/flashprove-model-scale-repeat')
ap.add_argument('--points', default='64,1,4;64,2,4;128,1,4;128,2,4;128,1,8;128,4,4;128,2,8;128,1,12')
a = ap.parse_args()
work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
plans = {int(x[0]): x[2:] for x in (l.split() for l in (here / 'plan_t10.txt').read_text().split('\n')) if len(x) > 2 and x[1] != '0'}
points = [tuple(map(int, p.split(','))) for p in a.points.split(';')]

fixtures = {}
for d, t, b in points:
    fx = work / f'kda_d{d}_t{t}_b{b}.bin'
    g = subprocess.run([sys.executable, str(here / 'gen.py'), str(d), str(d), str(t), '1', str(b), str(a.seed), str(fx)], capture_output=True, text=True, check=True)
    gl = json.loads(g.stdout.strip().split('\n')[-1])
    fixtures[(d, t, b)] = dict(path=fx, log_len=gl['log_len'], columns=gl['columns'], sha256=hashlib.sha256(fx.read_bytes()).hexdigest())
    print(json.dumps(dict(fixture=f'd{d}_t{t}_b{b}', log_len=gl['log_len'], columns=gl['columns'], sha256=fixtures[(d, t, b)]['sha256'])), flush=True)

jobs = [(rep, p) for rep in range(a.n) for p in points]
free = list(range(a.first_core, a.first_core + a.jobs)); lock = threading.Lock(); big = threading.Semaphore(a.big_slots)
out = here / 'results' / 'repeat-t10.jsonl'; outl = threading.Lock()
out.write_text('')

def one(job):
    rep, (d, t, b) = job; fx = fixtures[(d, t, b)]; L = fx['log_len']; isbig = L >= 21
    if isbig: big.acquire()
    try:
        with lock: core = free.pop()
        la0 = open('/proc/loadavg').read().split()[0]
        cmd = ['taskset', '-c', str(core), a.binary, str(fx['path']), '10', '6', str(L)] + plans[L] + ['--skip-hostile-provers']
        t0 = time.monotonic(); r = subprocess.run(cmd, capture_output=True, text=True); wall = time.monotonic() - t0
        la1 = open('/proc/loadavg').read().split()[0]
        with lock: free.append(core)
    finally:
        if isbig: big.release()
    o = json.loads(r.stdout.strip().split('\n')[-1]) if r.stdout.strip() else {}
    row = dict(d_k=d, tokens=t, bits=b, rep=rep, seed=a.seed, log_len=L, columns=fx['columns'], fixture_sha256=fx['sha256'], core=core,
               exit=r.returncode, ok=bool(o.get('ok')) and r.returncode == 0, loadavg1_before=float(la0), loadavg1_after=float(la1),
               run_wall_s=round(wall, 3), started_unix=round(time.time() - wall, 1), **{k: v for k, v in o.items() if k not in ('ok', 'log_len')})
    if o.get('log_len') not in (None, L): row['ok'] = False; row['fail'] = 'log_len mismatch'
    with outl:
        with open(out, 'a') as f: f.write(json.dumps(row) + '\n')
    print(json.dumps(row), flush=True)
    return row

started = time.time()
with ThreadPoolExecutor(max_workers=a.jobs) as ex:
    rows = list(ex.map(one, jobs))
for fx in fixtures.values():
    fx['path'].unlink(missing_ok=True)

def stats(xs):
    return dict(n=len(xs), median=statistics.median(xs), sd=statistics.stdev(xs) if len(xs) > 1 else None, min=min(xs), max=max(xs))
summ = []
for p in points:
    rs = [r for r in rows if (r['d_k'], r['tokens'], r['bits']) == p and r['ok']]
    summ.append(dict(d_k=p[0], tokens=p[1], bits=p[2], log_len=fixtures[p]['log_len'], columns=fixtures[p]['columns'], runs=sum((r['d_k'], r['tokens'], r['bits']) == p for r in rows),
                     ok_runs=len(rs), prove_s=stats([r['prove_s'] for r in rs]), verify_s=stats([r['verify_s'] for r in rs]),
                     proof_bytes=sorted(set(r['proof_bytes'] for r in rs)), max_rss_kb=stats([r['max_rss_kb'] for r in rs]),
                     rejected_static=sorted(set(r['rejected_static'] for r in rs)), loadavg1=stats([r['loadavg1_before'] for r in rs] + [r['loadavg1_after'] for r in rs])))
(here / 'results' / 'repeat-t10-summary.json').write_text(json.dumps(dict(args={k: v for k, v in vars(a).items() if k not in ('binary', 'work')}, started_unix=round(started, 1),
    seconds=round(time.time() - started, 1), hardware_note='shared 16-vCPU VM, other lanes may run; loadavg sampled per run', points=summ), indent=2) + '\n')
bad = [r for r in rows if not r['ok']]
print(f'repeat: {len(rows)} runs, {len(rows) - len(bad)} ok, {len(bad)} failed')
sys.exit(1 if bad else 0)
