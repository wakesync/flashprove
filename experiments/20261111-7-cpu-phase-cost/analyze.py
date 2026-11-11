#!/usr/bin/env python3
"""Summarize runs/runs.jsonl of experiments/20261111-7-cpu-phase-cost into runs/summary.json and
print the RESULTS tables (markdown). Definitions are PREREG.md's "Metric" section. Run from the repo root:
  python3 experiments/20261111-7-cpu-phase-cost/analyze.py
Nothing is excluded: every process record is counted; failed processes are listed and kept out of
timing statistics only (their count is reported).
"""
import json, pathlib, statistics as stt, sys
exp = pathlib.Path(__file__).resolve().parent
# optional: analyze.py <runs.jsonl> <summary.json> (default: runs/runs.jsonl -> runs/summary.json)
src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else exp / 'runs/runs.jsonl'
dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else exp / 'runs/summary.json'
recs = [json.loads(l) for l in open(src)]
T_POSITIONS = 4  # profile B: T = 4 head positions per statement, each with a proved output

def st(xs):
    xs = [float(x) for x in xs]
    if not xs: return None
    return dict(n=len(xs), median=stt.median(xs), sd=stt.stdev(xs) if len(xs) > 1 else 0.0, min=min(xs), max=max(xs))
def ph(rec, name, batch=None):
    v = [l['s'] for l in rec['lines'] if l.get('phase') == name and (batch is None or l.get('batch') == batch)]
    return v
def one(rec, name, batch=None):
    v = ph(rec, name, batch); assert len(v) == 1, (rec['cell'], rec['rep'], name, batch, v); return v[0]
def inproc(rec): return sum(l['s'] for l in rec['lines'] if 'phase' in l and not l['phase'].startswith('v_inner'))
def by(cell, role): return {r['rep']: r for r in recs if r.get('cell') == cell and r.get('role') == role}

out = {'events': [r for r in recs if 'event' in r], 'failures': [], 'cells': {}}
for r in recs:
    if r.get('role') in ('prover', 'verifier') and r['exit'] != 0:
        out['failures'].append(dict(cell=r['cell'], rep=r['rep'], role=r['role'], exit=r['exit'], stderr_tail=r['stderr_tail'][-500:],
                                    other=[l for l in r['lines'] if 'phase' not in l]))
    for l in r.get('lines', []):
        if 'reject' in l or 'refused' in l: out['failures'].append(dict(cell=r['cell'], rep=r['rep'], role=r['role'], line=l))

def ok_pairs(cell):
    P, V = by(cell, 'prover'), by(cell, 'verifier')
    return [(P[k], V[k]) for k in sorted(P) if k in V and P[k]['exit'] == 0 and V[k]['exit'] == 0], len(P)
def files(cell):
    return {r['rep']: r['bytes'] for r in recs if r.get('cell') == cell and r.get('role') == 'files'}

# ---------- profile A, cold ----------
pairs, attempted = ok_pairs('A-cold')
c = {'attempted': attempted, 'ok': len(pairs)}
rows = {k: [] for k in ('prover_startup', 'configure', 'setup', 'witness', 'commit_tables', 'commit_key', 'commit_entry', 'commit',
                        'write_files', 'prove', 'verifier_startup', 'v_configure', 'v_read', 'v_check_key', 'v_check_entry', 'v_check_proofs',
                        'verification', 'e2e', 'prover_wall', 'prover_rss_kb', 'verifier_rss_kb', 'prover_cpu_s', 'verifier_cpu_s')}
for P, V in pairs:
    rows['prover_startup'].append(P['process_wall_s'] - inproc(P))
    rows['configure'].append(one(P, 'configure'))
    rows['setup'].append(rows['prover_startup'][-1] + rows['configure'][-1])
    rows['witness'].append(one(P, 'witness'))
    for k in ('commit_tables', 'commit_key', 'commit_entry'): rows[k].append(one(P, k))
    rows['commit'].append(one(P, 'commit_tables') + one(P, 'commit_key') + one(P, 'commit_entry'))
    rows['write_files'].append(one(P, 'write_commitment') + one(P, 'write_proofs', 0))
    rows['prove'].append(one(P, 'prove_batch', 0))
    rows['verifier_startup'].append(V['process_wall_s'] - inproc(V))
    rows['v_configure'].append(one(V, 'v_configure'))
    rows['v_read'].append(one(V, 'v_read_commitment') + one(V, 'v_read_proofs', 0))
    rows['v_check_key'].append(one(V, 'v_check_key')); rows['v_check_entry'].append(one(V, 'v_check_entry'))
    rows['v_check_proofs'].append(one(V, 'v_check_proofs', 0))
    rows['verification'].append(V['process_wall_s'])
    rows['prover_wall'].append(P['process_wall_s'])
    rows['e2e'].append(P['process_wall_s'] + V['process_wall_s'])
    rows['prover_rss_kb'].append(P['ru_maxrss_kb']); rows['verifier_rss_kb'].append(V['ru_maxrss_kb'])
    rows['prover_cpu_s'].append(P['ru_utime_s'] + P['ru_stime_s']); rows['verifier_cpu_s'].append(V['ru_utime_s'] + V['ru_stime_s'])
c['stats'] = {k: st(v) for k, v in rows.items()}
fa = files('A-cold')
c['bytes'] = {k: st([fa[r][k] for r in fa]) for k in sorted(next(iter(fa.values())))} if fa else {}
c['raw'] = rows
out['cells']['A-cold'] = c

# ---------- profile A, amortized ----------
pairs, attempted = ok_pairs('A-amort')
c = {'attempted': attempted, 'ok': len(pairs)}
r2 = {k: [] for k in ('batches', 'columns_left', 'commit_once', 'first_batch_prove', 'per_batch_prove', 'per_batch_check', 'per_batch_verified',
                      'per_batch_verified_io', 'process_pair_wall', 'per_batch_total_wall_incl_fixed', 'prover_rss_kb', 'verifier_rss_kb')}
for P, V in pairs:
    summ = next(l for l in P['lines'] if l.get('summary') == 'prove')
    K = summ['batches']; r2['batches'].append(K); r2['columns_left'].append(summ['columns_left'])
    r2['commit_once'].append(one(P, 'commit_tables') + one(P, 'commit_key') + one(P, 'commit_entry'))
    r2['first_batch_prove'].append(one(P, 'prove_batch', 0))
    pb = [one(P, 'prove_batch', b) for b in range(1, K)]
    vb = [one(V, 'v_check_proofs', b) for b in range(1, K)]
    io = [one(P, 'write_proofs', b) + one(V, 'v_read_proofs', b) for b in range(1, K)]
    r2['per_batch_prove'].append(stt.median(pb)); r2['per_batch_check'].append(stt.median(vb))
    r2['per_batch_verified'].append(stt.median([a + b for a, b in zip(pb, vb)]))
    r2['per_batch_verified_io'].append(stt.median([a + b + d for a, b, d in zip(pb, vb, io)]))
    r2['process_pair_wall'].append(P['process_wall_s'] + V['process_wall_s'])
    r2['per_batch_total_wall_incl_fixed'].append((P['process_wall_s'] + V['process_wall_s']) / K)
    r2['prover_rss_kb'].append(P['ru_maxrss_kb']); r2['verifier_rss_kb'].append(V['ru_maxrss_kb'])
c['stats'] = {k: st(v) for k, v in r2.items()}
c['raw'] = r2
out['cells']['A-amort'] = c

# ---------- profile B, cold ----------
pairs, attempted = ok_pairs('B-cold')
c = {'attempted': attempted, 'ok': len(pairs)}
r3 = {k: [] for k in ('prover_startup', 'read_input', 'witness', 'prove', 'write_files', 'verifier_startup', 'v_read', 'v_derive', 'v_proof_verifier',
                      'v_verify_stage1', 'verification', 'prover_wall', 'e2e', 'prove_positions_per_s', 'e2e_positions_per_s',
                      'prover_rss_kb', 'verifier_rss_kb', 'prover_cpu_s', 'verifier_cpu_s')}
for P, V in pairs:
    r3['prover_startup'].append(P['process_wall_s'] - inproc(P))
    r3['read_input'].append(one(P, 'read_input', 0)); r3['witness'].append(one(P, 'witness', 0)); r3['prove'].append(one(P, 'prove', 0))
    r3['write_files'].append(one(P, 'write_proof', 0))
    r3['verifier_startup'].append(V['process_wall_s'] - inproc(V))
    r3['v_read'].append(one(V, 'v_read', 0)); r3['v_derive'].append(one(V, 'v_inner_derive', 0)); r3['v_proof_verifier'].append(one(V, 'v_inner_proof_verifier', 0))
    r3['v_verify_stage1'].append(one(V, 'v_verify_stage1', 0))
    r3['verification'].append(V['process_wall_s']); r3['prover_wall'].append(P['process_wall_s'])
    r3['e2e'].append(P['process_wall_s'] + V['process_wall_s'])
    r3['prove_positions_per_s'].append(T_POSITIONS / r3['prove'][-1]); r3['e2e_positions_per_s'].append(T_POSITIONS / r3['e2e'][-1])
    r3['prover_rss_kb'].append(P['ru_maxrss_kb']); r3['verifier_rss_kb'].append(V['ru_maxrss_kb'])
    r3['prover_cpu_s'].append(P['ru_utime_s'] + P['ru_stime_s']); r3['verifier_cpu_s'].append(V['ru_utime_s'] + V['ru_stime_s'])
c['stats'] = {k: st(v) for k, v in r3.items()}
fb = files('B-cold')
c['bytes'] = {'proof-0.bin': st([fb[r]['proof-0.bin'] for r in fb]), 'words-0.bin': st([fb[r]['words-0.bin'] for r in fb])} if fb else {}
c['raw'] = r3
out['cells']['B-cold'] = c

# ---------- profile B, amortized ----------
pairs, attempted = ok_pairs('B-amort')
c = {'attempted': attempted, 'ok': len(pairs), 'statements_per_process': None}
r4 = {k: [] for k in ('first_prove', 'per_stmt_prove', 'per_stmt_verify', 'per_stmt_verified', 'per_stmt_verified_positions_per_s',
                      'process_pair_wall', 'per_stmt_total_wall_incl_fixed', 'prover_rss_kb', 'verifier_rss_kb')}
for P, V in pairs:
    n = next(l for l in P['lines'] if l.get('summary') == 'prove')['batches']; c['statements_per_process'] = n
    r4['first_prove'].append(one(P, 'prove', 0))
    pv = [one(P, 'witness', i) + one(P, 'prove', i) for i in range(1, n)]
    vv = [one(V, 'v_verify_stage1', i) for i in range(1, n)]
    r4['per_stmt_prove'].append(stt.median(pv)); r4['per_stmt_verify'].append(stt.median(vv))
    both = stt.median([a + b for a, b in zip(pv, vv)])
    r4['per_stmt_verified'].append(both); r4['per_stmt_verified_positions_per_s'].append(T_POSITIONS / both)
    r4['process_pair_wall'].append(P['process_wall_s'] + V['process_wall_s'])
    r4['per_stmt_total_wall_incl_fixed'].append((P['process_wall_s'] + V['process_wall_s']) / n)
    r4['prover_rss_kb'].append(P['ru_maxrss_kb']); r4['verifier_rss_kb'].append(V['ru_maxrss_kb'])
c['stats'] = {k: st(v) for k, v in r4.items()}
c['raw'] = r4
out['cells']['B-amort'] = c

# ---------- registered verdicts ----------
def rng(s): return (s['min'], s['max'])
def overlap(a, b): return not (a[1] < b[0] or b[1] < a[0])
v = {}
A, Aa, B = out['cells']['A-cold']['stats'], out['cells']['A-amort']['stats'], out['cells']['B-cold']['stats']
if B.get('prove') and out['cells']['B-cold']['ok'] == 10:
    phasesB = {k: B[k] for k in ('prover_startup', 'read_input', 'witness', 'prove', 'write_files', 'verification')}
    order = sorted(phasesB, key=lambda k: -phasesB[k]['median'])
    share = B['prove']['median'] / B['e2e']['median']
    v['B'] = dict(prove_share_of_e2e=share, order=order, second_is_verification=order[1] == 'verification',
                  prove_range_overlaps_next=overlap(rng(B['prove']), rng(phasesB[order[1]])))
    v['B']['verdict'] = 'PASS' if share >= 0.60 and order[0] == 'prove' and v['B']['second_is_verification'] and not v['B']['prove_range_overlaps_next'] else 'FAIL'
else:
    v['B'] = dict(verdict='KILLED', reason='fewer than 10 successful cold pairs')
if A.get('prove') and out['cells']['A-cold']['ok'] == 10 and out['cells']['A-amort']['ok'] == 10:
    phasesA = {k: A[k] for k in ('setup', 'witness', 'commit', 'write_files', 'prove', 'verification')}
    order = sorted(phasesA, key=lambda k: -phasesA[k]['median'])
    top2 = set(order[:2]) == {'commit', 'prove'}
    sep = all(not overlap(rng(phasesA[t]), rng(phasesA[o])) for t in ('commit', 'prove') for o in order[2:])
    ratio = Aa['per_batch_verified']['median'] / A['e2e']['median']
    nonover = Aa['per_batch_verified']['max'] < A['e2e']['min']
    v['A'] = dict(order=order, top2_commit_and_prove=top2, top2_ranges_separate_from_smaller=sep, amortized_over_cold=ratio,
                  amortized_max_below_cold_min=nonover, amortization_K=sorted(set(out['cells']['A-amort']['raw']['batches'])))
    v['A']['verdict'] = 'PASS' if top2 and sep and ratio < 0.5 and nonover else 'FAIL'
else:
    v['A'] = dict(verdict='KILLED', reason='fewer than 10 successful pairs in a cell')
out['verdicts'] = v
dst.write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')

def f(s, d=3, scale=1.0):
    if s is None: return 'n/a'
    return f"{s['median']*scale:.{d}f} | {s['sd']*scale:.{d}f} | {s['min']*scale:.{d}f}..{s['max']*scale:.{d}f}"
print('failures:', len(out['failures']))
print(json.dumps(v, indent=1))
for cell, cs in out['cells'].items():
    print(f"\n### {cell} (ok {cs['ok']} of {cs['attempted']})\n\n| quantity | median | SD | min..max |\n|---|---:|---:|---:|")
    for k, s in cs['stats'].items():
        if s is None: continue
        if k.endswith('rss_kb'): print(f"| {k[:-3]} (MiB) | {f(s, 1, 1/1024)} |")
        else: print(f"| {k} | {f(s, 4)} |")
    for k, s in cs.get('bytes', {}).items(): print(f"| bytes {k} | {f(s, 0)} |")
