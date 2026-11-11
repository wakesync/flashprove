#!/usr/bin/env python3
"""Build, debug (disjoint seed/shape), or the once-only registered suite for #93 hidden-root windows.

Run build and suite through the CPU heavy-job gate. Every proof process is pinned with taskset.
Existing receipts are never overwritten (files are opened with mode 'x').
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import platform
import statistics
import subprocess
import time
import numpy as np
import fixtures as X
from count import counts

HERE = X.HERE
ROOT = X.ROOT
EXP = ROOT / 'experiments/20261111-93-hidden-root-handoff'
REGISTERED = EXP
WORK = HERE / 'work'
BINARY = WORK / 'window.bin'
CORES = os.environ.get('FP_CORES', '6-9')
FLAGS = ['-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1']
SEEDS = [201, 202, 203, 204, 205]
HARD_STOP = datetime.datetime(2026, 11, 12, 0, 50, tzinfo=datetime.timezone.utc)
BUDGET = 40 * 60

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def digest(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

def write_new(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

def command(args, timeout=600):
    p = subprocess.run(['taskset', '-c', CORES, *[str(x) for x in args]], cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    rows = [json.loads(x) for x in p.stdout.splitlines() if x.startswith('{')]
    if not rows:
        return dict(accept=False, exit=p.returncode, error=p.stderr.strip()[-500:])
    row = rows[-1]
    row['exit'] = p.returncode
    return row

def build(out_dir):
    WORK.mkdir(exist_ok=True)
    args = ['taskset', '-c', CORES, 'g++', *FLAGS, '-I', 'blocks', 'research/operators/qwen_hidden_root/window.cpp', '-o', str(BINARY.relative_to(ROOT))]
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=600)
    if p.returncode:
        raise RuntimeError(p.stderr[-4000:])
    sources = [HERE / n for n in ['window.cpp', 'fixtures.py', 'run.py', 'count.py']] + [
        ROOT / 'research/operators/qwen_handoff/lowering.h', ROOT / 'research/operators/qwen_handoff/sha256.h',
        ROOT / 'research/operators/qwen_deltanet/reference.py', ROOT / 'research/operators/qwen_deltanet_lookup/lookup.h']
    receipt = dict(compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0], flags=FLAGS,
                   binary_sha256=digest(BINARY), sources={str(s.relative_to(ROOT)): digest(s) for s in sources},
                   warnings=p.stderr.replace(str(ROOT), '<REPO>'), built_utc=utc())
    if out_dir is not None:
        write_new(out_dir / 'runs/build.json', receipt)
    print(json.dumps({'build': 'ok', 'binary_sha256': receipt['binary_sha256']}), flush=True)

def files_for(d, stmt, cin, cout):
    d.mkdir(parents=True, exist_ok=True)
    (d / 'verifier.stmt').write_bytes(stmt)
    (d / 'c_in').write_bytes(X.cbytes(cin))
    (d / 'c_out').write_bytes(X.cbytes(cout))
    return d / 'verifier.stmt', d / 'c_in', d / 'c_out'

def prove_case(d, stmt, cin, cout, w, mode):
    s, ci, co = files_for(d, stmt, cin, cout)
    wd = d / 'witness'
    X.write_witness(wd, w)
    proof = d / 'window.proof'
    r = command([BINARY, mode, s, ci, co, wd, proof])
    v = command([BINARY, 'verify', s, ci, co, '-', proof]) if proof.exists() else dict(accept=False, why='no proof emitted')
    return r, v, proof

def verify_slot(d, stmt, cin, cout, proof):
    s, ci, co = files_for(d, stmt, cin, cout)
    return command([BINARY, 'verify', s, ci, co, '-', proof])

def chain_verify(d, ch, r0, slots):
    """Verifier-held: descriptor (statement per position, N) and R0. Prover: [(claimed C_out, proof)]."""
    cin, per = r0, []
    for k, (cout, proof) in enumerate(slots):
        stmt = X.window_statement(ch, k) if k < ch['N'] else None
        if stmt is None:
            per.append(dict(slot=k, accept=False, why='slot beyond statement window count'))
            continue
        v = verify_slot(d / f'slot{k}', stmt, cin, cout, proof)
        per.append(dict(slot=k, accept=v['accept'], why=v.get('why', '')))
        cin = cout
    count_ok = len(slots) == ch['N']
    ok = count_ok and all(p['accept'] for p in per)
    return dict(accept=ok, count_ok=count_ok, slots=per)

def contains_state_row(path, ch):
    raw = pathlib.Path(path).read_bytes()
    for S in ch['S']:
        for row in np.asarray(S):
            if X.le(row) in raw:
                return True
    return False

def run_seed(seed, D, C, N, sink, end):
    d0 = WORK / f'seed-{seed}'
    ch = X.chain(seed, D, C, N, 3, 1)
    other = X.chain(seed, D, C, N, 4, 2)
    rows, honest_proofs = [], []
    expected = counts(D, C)

    def emit(row):
        row['seed'] = seed
        rows.append(row)
        print(json.dumps({k: row.get(k) for k in ['seed', 'case', 'window', 'accept', 'violations']}), flush=True)
        if sink is not None:
            with sink.open('a') as f:
                f.write(json.dumps(row) + '\n')

    def guard():
        if end is not None and time.monotonic() >= end:
            raise TimeoutError('registered suite budget or lane hard stop')

    for k in range(N):
        guard()
        w = X.honest_witness(ch, k)
        assert X.claimed_in(w) == ch['commit'][k] and X.claimed_out(w) == ch['commit'][k + 1]
        stmt = X.window_statement(ch, k)
        r, v, proof = prove_case(d0 / f'honest-w{k}', stmt, ch['commit'][k], ch['commit'][k + 1], w, 'prove')
        cpp_in, cpp_out = r.get('in_hash'), r.get('out_hash')
        py_in, py_out = X.cbytes(ch['commit'][k]), X.cbytes(ch['commit'][k + 1])
        hexpy = lambda c: ''.join('%016x' % x for x in c)
        agree = cpp_in == hexpy(ch['commit'][k]) and cpp_out == hexpy(ch['commit'][k + 1])
        cnt = {kk: r.get(kk) for kk in ['core_columns', 'aligned_columns', 'relations', 'range_cells', 'hash_columns', 'hash_relations', 'permutations']}
        count_match = all(cnt[kk] == expected[kk] for kk in cnt)
        dd = d0 / f'honest-w{k}'
        leak = {n: contains_state_row(dd / n, ch) for n in ['verifier.stmt', 'c_in', 'c_out']}
        leak_proof = contains_state_row(proof, ch)
        honest_proofs.append((ch['commit'][k + 1], proof))
        emit(dict(case='honest_window', window=k, accept=v['accept'], why=v.get('why'), violations=r.get('violated_relations'),
                  proof=r, verify=v, py_cpp_commit_agree=agree, count_match=count_match, counted=cnt,
                  verifier_inputs_contain_state_row=leak, proof_contains_state_row=leak_proof,
                  statement_sha256=digest(dd / 'verifier.stmt'), proof_sha256=digest(proof)))
        del py_in, py_out
    for k in range(N):
        guard()
        w = X.honest_witness(ch, k)
        r, v, proof = prove_case(d0 / f'honest-hostilepath-w{k}', X.window_statement(ch, k), ch['commit'][k], ch['commit'][k + 1], w, 'hostile')
        emit(dict(case='honest_window_hostile_path', window=k, accept=v['accept'], why=v.get('why'), violations=r.get('violated_relations'),
                  proof=r, verify=v, proof_sha256=digest(proof) if proof.exists() else None))
    guard()
    w4 = X.honest_witness(other, 1)
    r, v, l4proof = prove_case(d0 / 'layer4-honest-w1', X.window_statement(other, 1), other['commit'][1], other['commit'][2], w4, 'prove')
    emit(dict(case='honest_layer4_window', window=1, accept=v['accept'], why=v.get('why'), violations=r.get('violated_relations'), proof=r, verify=v))
    for name in X.WINDOW_CASES:
        guard()
        w, cin, cout = X.hostile(name, ch, other)
        r, v, proof = prove_case(d0 / f'neg-{name}', X.window_statement(ch, 1), cin, cout, w, 'hostile')
        emit(dict(case=name, window=1, accept=v['accept'], why=v.get('why'), violations=r.get('violated_relations'), proof=r, verify=v,
                  proof_sha256=digest(proof) if proof.exists() else None, label='complete hostile proof, proof verifier'))
    r0 = ch['commit'][0]
    p = honest_proofs
    chains = {
        'honest_chain': [p[0], p[1], p[2]],
        'replayed_earlier_window': [p[0], p[1], p[1]],
        'dropped_middle_window': [p[0], p[2]],
        'spliced_other_layer_proof': [p[0], (other['commit'][2], l4proof), p[2]],
        'truncated_chain': [p[0], p[1]],
    }
    labels = {'truncated_chain': 'chain-statement check: verifier-held N', 'dropped_middle_window': 'proof verifier at slot 1 plus verifier-held N',
              'honest_chain': 'paired honest control'}
    for name, slots in chains.items():
        guard()
        res = chain_verify(d0 / f'chain-{name}', ch, r0, slots)
        emit(dict(case=name, window=None, accept=res['accept'], chain=res, label=labels.get(name, 'proof verifier on the spliced slot')))
    return rows

def stats(xs):
    xs = [float(x) for x in xs]
    return dict(n=len(xs), median=statistics.median(xs), sd=statistics.stdev(xs) if len(xs) > 1 else 0.0, min=min(xs), max=max(xs))

EXPECT_ACCEPT = {'honest_window', 'honest_window_hostile_path', 'honest_layer4_window', 'honest_chain'}

def suite():
    start = time.monotonic()
    started = utc()
    print(json.dumps({'slot_granted_utc': started}), flush=True)
    # The lane hard stop applies to the registered run only; a later rerun (--out) keeps the 40 min budget.
    remaining = (HARD_STOP - datetime.datetime.now(datetime.timezone.utc)).total_seconds() if EXP == REGISTERED else BUDGET
    end = start + min(BUDGET, remaining)
    out = EXP / 'runs/suite.jsonl'
    out.parent.mkdir(exist_ok=True)
    with out.open('x'):
        pass
    rows = []
    for seed in SEEDS:
        rows += run_seed(seed, 8, 2, 3, out, end)
    cases = {}
    for r in rows:
        cases.setdefault(r['case'], []).append(r)
    per_case = {}
    for name, rs in cases.items():
        by_seed = {}
        for r in rs:
            by_seed.setdefault(r['seed'], []).append(int(bool(r['accept'])))
        frac = [sum(v) / len(v) for v in by_seed.values()]
        entry = dict(acceptance=stats(frac), instances=len(rs), accepted=sum(int(bool(r['accept'])) for r in rs))
        viol = [r['violations'] for r in rs if r.get('violations') is not None]
        if viol:
            entry['violations'] = stats(viol)
        per_case[name] = entry
    honest = [r for r in rows if r['case'] == 'honest_window']
    structure = {k: stats([r['proof'][k] for r in honest]) for k in
                 ['core_columns', 'aligned_columns', 'relations', 'relation_terms', 'range_cells', 'hash_columns', 'hash_relations',
                  'recurrence_columns', 'recurrence_relations', 'proof_bytes', 'prove_s']}
    structure['verify_s'] = stats([r['verify']['verify_s'] for r in honest])
    ok_rows = all(bool(r['accept']) == (r['case'] in EXPECT_ACCEPT) for r in rows)
    h3 = all(r['count_match'] for r in honest)
    agree = all(r['py_cpp_commit_agree'] for r in honest)
    h4 = not any(any(r['verifier_inputs_contain_state_row'].values()) for r in honest)
    seeds_done = sorted({r['seed'] for r in rows})
    complete = seeds_done == SEEDS
    verdict = 'PASS' if (ok_rows and h3 and agree and h4 and complete) else 'FAIL'
    result = dict(started_utc=started, finished_utc=utc(), seeds=seeds_done, per_case=per_case, structure=structure,
                  H1_H2_H3_outcomes_as_expected=ok_rows, H4_counts_match=h3, py_cpp_commit_agree=agree,
                  verifier_inputs_free_of_state_rows=h4,
                  proof_files_containing_a_state_row=sum(bool(r['proof_contains_state_row']) for r in honest),
                  verdict=verdict,
                  note='Measured, unreplicated. Research target 10 / work 6, deterministic toy coins. Unvetted Poseidon-shaped sponge. Synthetic weights labels. Not zero-knowledge.')
    write_new(EXP / 'runs/summary.json', result)
    write_new(EXP / 'runs/counts.json', {'kind': 'counted; only D8/C2 built and checked', 'rows': [counts(D, C) for D, C in [(8, 2), (32, 2), (128, 2), (128, 64)]]})
    cpu = next((l.split(':', 1)[1].strip() for l in pathlib.Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name')), 'unknown')
    env = dict(commits={'repo': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                        'base': 'cf4b213f1fe4d1c0073e0e1266281eee7e92b79b', 'prereg': 'f7f8cb9b013ab42562ba2e86588fe012ac7f9f83'},
               toolchain={'python': platform.python_version(), 'numpy': np.__version__,
                          'compiler': subprocess.check_output(['g++', '--version'], text=True).splitlines()[0], 'flags': FLAGS},
               hardware={'cpu': cpu, 'taskset_cores': CORES, 'provider': 'shared loaded CPU host, heavy-job gate fp-heavy.sh',
                         'ram_bytes': os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES'), 'logical_cpus': os.cpu_count(), 'gpu': 'none',
                         'parallel_proof_processes': 1},
               seeds=SEEDS, salt_streams={'layer3': 1, 'layer4': 2},
               security={'target_bits': 10, 'work_bits': 6, 'coins': 'ToyCoins(100), deterministic, not production',
                         'sponge': 'width 12 rate 8 capacity 4, x^7, 8 full + 22 partial rounds, Cauchy MDS, SHA-256 counter constants; unvetted'},
               started_utc=started, finished_utc=utc(), binary_sha256=digest(BINARY))
    write_new(EXP / 'ENV.json', env)
    print(json.dumps(dict(verdict=verdict, seeds=seeds_done)), flush=True)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['build', 'debug', 'suite'])
    ap.add_argument('--out', type=pathlib.Path, help='fresh receipt directory for a rerun')
    a = ap.parse_args()
    if a.out is not None:
        EXP = a.out.resolve()
    if a.mode == 'build':
        build(EXP)
    elif a.mode == 'debug':
        build(None)
        rows = run_seed(909, 4, 1, 3, None, None)
        bad = [r['case'] for r in rows if bool(r['accept']) != (r['case'] in EXPECT_ACCEPT)]
        print(json.dumps({'debug_unexpected': bad}), flush=True)
    else:
        suite()
