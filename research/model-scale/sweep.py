#!/usr/bin/env python3
"""Sweep runner: generate -> prove -> verify -> hostile cases, one CSV row per point.

  python3 research/model-scale/sweep.py [--jobs N] [--max-log-len L] [--target 10|128] [--only d,T,bits]

CPU only, single-threaded prover per point (EngineCpu), at most --jobs points at once, each pinned
to its own core (default cores 8..8+jobs-1). Points whose table would exceed --max-log-len are
recorded as plan-only rows (planner bytes, no proof). Writes results/sweep-t<target>.csv and
results/sweep-t<target>.jsonl."""
import argparse, csv, json, os, subprocess, sys, time, platform
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
here = Path(__file__).resolve().parent; root = here.parents[1]
sys.path.insert(0, str(here))
import kda_scale as K

ap = argparse.ArgumentParser()
ap.add_argument('--jobs', type=int, default=6)
ap.add_argument('--first-core', type=int, default=8)
ap.add_argument('--max-log-len', type=int, default=21)
ap.add_argument('--target', type=int, default=10)
ap.add_argument('--dims', default='2,4,8,16,32,64,128')
ap.add_argument('--tokens', default='1,2,4,8')
ap.add_argument('--bits', default='4,8,12')
ap.add_argument('--seed', type=int, default=7)
ap.add_argument('--work', default='/tmp/flashprove-model-scale')
ap.add_argument('--tag', default='')
a = ap.parse_args()
work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
res = here / 'results'; res.mkdir(exist_ok=True)
tag = f't{a.target}' + (f'-{a.tag}' if a.tag else '')

# PR19 cross-check: bits=4, d=1 is PR19's exact contract (scale 4, [-8,7], staged floor).
import numpy as np
s, o = K.integer_reference(np.array([[-3]]), [(np.array([3]), np.array([-3]), np.array([2]), 3, np.array([3]))], 4)
assert int(s[0, 0]) == -3 and int(o[0][0]) == -3, 'PR19 fixture semantics'

plans = {}
for line in (here / f'plan_t{a.target}.txt').read_text().split('\n'):
    x = line.split()
    if len(x) > 2 and x[1] != '0':
        plans[int(x[0])] = dict(bytes=int(x[1]), args=x[2:])

binary = work / 'run.bin'
compile_cmd = ['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks',
               'research/model-scale/run.cpp', '-o', str(binary)]
t0 = time.monotonic(); c = subprocess.run(['taskset', '-c', str(a.first_core)] + compile_cmd, cwd=root, capture_output=True, text=True)
compile_info = dict(argv=compile_cmd, exit=c.returncode, seconds=round(time.monotonic() - t0, 2), stderr=c.stderr[-2000:])
if c.returncode:
    print(c.stderr); sys.exit(1)

points = [(d, t, b) for b in map(int, a.bits.split(',')) for d in map(int, a.dims.split(',')) for t in map(int, a.tokens.split(','))]
import math
def est_L(d, t, b):
    return max(7, math.ceil(math.log2(K.columns_formula(d, d, t, 1, b))))
points.sort(key=lambda p: est_L(*p))

cores = list(range(a.first_core, a.first_core + a.jobs))
import threading
free = list(cores); lock = threading.Lock(); mem_lock = threading.Semaphore(1)

def one(p):
    d, t, b = p
    L = est_L(d, t, b)
    row = dict(d_k=d, d_v=d, tokens=t, heads=1, bits=b, frac_bits=b - 2, seed=a.seed, target=a.target, est_log_len=L,
               columns=K.columns_formula(d, d, t, 1, b), planned_bytes=plans.get(L, {}).get('bytes', 0))
    if L > a.max_log_len or L not in plans:
        row['status'] = 'plan-only' if L in plans else 'no-plan'
        return row
    big = L >= 20
    if big:
        mem_lock.acquire()  # at most one >=2^20 point in memory at a time
    try:
        with lock:
            core = free.pop()
        fx = work / f'kda_d{d}_t{t}_b{b}.bin'
        g = subprocess.run(['taskset', '-c', str(core), sys.executable, str(here / 'gen.py'), str(d), str(d), str(t), '1', str(b), str(a.seed), str(fx)],
                           capture_output=True, text=True)
        gl = json.loads(g.stdout.strip().split('\n')[-1]) if g.stdout.strip() else {}
        row.update({k: v for k, v in gl.items() if k not in row or k == 'columns'})
        if g.returncode == 3:
            row['status'] = 'reference-overflow-rejected'
        elif g.returncode:
            row['status'] = 'gen-failed'; row['stderr'] = g.stderr[-500:]
        else:
            assert gl['log_len'] == L, (gl['log_len'], L)
            cmd = ['taskset', '-c', str(core), str(binary), str(fx), str(a.target), '6' if a.target == 10 else '0', str(L)] + plans[L]['args']
            t1 = time.monotonic(); r = subprocess.run(cmd, capture_output=True, text=True); wall = time.monotonic() - t1
            out = json.loads(r.stdout.strip().split('\n')[-1]) if r.stdout.strip() else {}
            row.update(out); row['run_wall_s'] = round(wall, 3); row['core'] = core
            row['status'] = 'proved' if r.returncode == 0 and out.get('ok') else 'FAILED'
            if r.returncode:
                row['stderr'] = (r.stderr or r.stdout)[-500:]
        try:
            fx.unlink()
        except FileNotFoundError:
            pass
        with lock:
            free.append(core)
    finally:
        if big:
            mem_lock.release()
    print(json.dumps(row), flush=True)
    return row

started = time.time()
with ThreadPoolExecutor(max_workers=a.jobs) as ex:
    rows = list(ex.map(one, points))
fields = ['d_k', 'd_v', 'tokens', 'heads', 'bits', 'frac_bits', 'seed', 'target', 'work', 'status', 'est_log_len', 'columns', 'coordinates', 'wires',
          'affine_rows', 'affine_terms', 'linear_claims', 'rounded', 'bit_columns', 'planned_bytes', 'proof_bytes', 'prove_s', 'verify_s',
          'verify_min_s', 'plan_s', 'max_rss_kb', 'rejected_static', 'hostile_provers', 'hostile_s', 'clipped_inputs', 'max_abs_err',
          'max_abs_err_state', 'max_abs_err_output', 'max_abs_integer', 'gen_seconds', 'run_wall_s', 'core', 'overflow', 'fail', 'stderr']
with open(res / f'sweep-{tag}.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
(res / f'sweep-{tag}.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
(res / f'sweep-{tag}.meta.json').write_text(json.dumps(dict(platform=platform.platform(), cpu=open('/proc/cpuinfo').read().split('model name')[1].split('\n')[0].strip(': '),
    compiler=subprocess.check_output(['g++', '--version'], text=True).split('\n')[0], compile=compile_info, args=vars(a), started=started,
    seconds=round(time.time() - started, 1), loadavg_end=open('/proc/loadavg').read().strip(),
    note='parallel points pinned to distinct cores on a shared VM; other lanes were running; timings are indicative, not exclusive'), indent=2) + '\n')
bad = [r for r in rows if r['status'] in ('FAILED', 'gen-failed')]
print(f'sweep: {len(rows)} points, {sum(r["status"] == "proved" for r in rows)} proved, {len(bad)} failed')
sys.exit(1 if bad else 0)
