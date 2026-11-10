#!/usr/bin/env python3
"""CPU receipt for the Qwen DeltaNet two-lookup build (experiments/20261109-32-qwen-deltanet-lookup-build).

Usage: record.py <step> [<step> ...]
  build1     stage 1 fixtures (M1 reference.py, seeds 1..10) + compile stage1.cpp
  honest1    stage 1: one honest proof per seed through verify_stage1 (pinned cores)
  hostile1   stage 1: the hostile suite on seed 1
  ubsan1     stage 1: the hostile suite again under -fsanitize=undefined (no recover)
  build2     stage 2 fixtures (reference_m2.py, seeds 1..10) + compile m2.cpp
  honest2 / hostile2 / ubsan2   the same for the M2 head
  counts     builder counts against count_model.py arm B (H3)
Writes evidence.json here and raw lines to the experiment's runs/. Run the heavy steps through the
host's heavy-job gate; cores come from M2_CORES (default 0-5).
"""
import hashlib, json, os, pathlib, platform, statistics, subprocess, sys, time
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(root / 'research/operators/qwen_deltanet'))
rel = str(here.relative_to(root))
exp = root / 'experiments/20261109-32-qwen-deltanet-lookup-build/runs'
work = here / 'work'; work.mkdir(exist_ok=True); exp.mkdir(parents=True, exist_ok=True)
SEEDS = list(range(1, 11))
CORES = os.environ.get('M2_CORES', '0-5')
only = sys.argv[1:]
FLAGS = ['-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks']
UB = ['-fsanitize=undefined', '-fno-sanitize-recover=undefined']

def sh(argv, timeout=14400):
    t = time.monotonic(); p = subprocess.run([str(a) for a in argv], cwd=root, capture_output=True, text=True, timeout=timeout)
    return dict(argv=[str(a) for a in argv], exit=p.returncode, seconds=round(time.monotonic() - t, 3), stdout=p.stdout, stderr=p.stderr[-4000:])
def st(x):
    return dict(n=len(x), median=statistics.median(x), sd=statistics.stdev(x) if len(x) > 1 else 0, min=min(x), max=max(x))
def lines_of(text):
    out = []
    for l in text.splitlines():
        if l.startswith('{'):
            try: out.append(json.loads(l))
            except json.JSONDecodeError: pass
    return out

ev_path = here / 'evidence.json'
ev = json.loads(ev_path.read_text()) if ev_path.exists() else {}
ev.update(platform=platform.platform(), python=sys.version.split()[0], cores=CORES,
          compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
          head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
          sources={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                   sorted(here.glob('*.py')) + sorted(here.glob('*.cpp')) + sorted(here.glob('*.h')) + sorted((here / 'tables').glob('*')) +
                   [root / 'research/operators/qwen_deltanet_lookup/lookup.h', root / 'research/operators/qwen_deltanet/reference.py',
                    root / 'blocks/iop/lkp.h', root / 'blocks/iop/rng.h']})
def save(): ev_path.write_text(json.dumps(ev, indent=1, sort_keys=True) + '\n')

def compile_(src, out, extra=()):
    c = sh(['g++', *FLAGS, *extra, f'{rel}/{src}', '-o', str(out.relative_to(root))])
    assert c['exit'] == 0, c['stderr']
    return dict(exit=c['exit'], seconds=c['seconds'], warnings=c['stderr'].count('warning:'))
def fixture(stage, s): return work / f'stage{stage}-seed{s}.bin'
def binary(stage, ub=False): return work / (('stage1' if stage == 1 else 'm2') + ('-ubsan' if ub else '') + '.bin')
def run_bin(stage, s, mode, ub=False):
    return sh(['taskset', '-c', CORES, str(binary(stage, ub).relative_to(root)), str(fixture(stage, s).relative_to(root)), mode])

def do_build(stage):
    fx = {}
    if stage == 1:
        import reference as R
        for s in SEEDS:
            meta = R.write_fixture(str(fixture(1, s)), s)
            fx[s] = dict(meta=meta, sha256=hashlib.sha256(fixture(1, s).read_bytes()).hexdigest())
    else:
        import reference_m2 as R2
        for s in SEEDS:
            meta = R2.write_fixture(str(fixture(2, s)), s)
            fx[s] = dict(meta=meta, sha256=hashlib.sha256(fixture(2, s).read_bytes()).hexdigest())
    ev[f'stage{stage}_fixtures'] = fx
    ev[f'stage{stage}_compile'] = compile_('stage1.cpp' if stage == 1 else 'm2.cpp', binary(stage)); save()

def do_honest(stage):
    runs = []
    for s in SEEDS:
        c = run_bin(stage, s, 'honest')
        ls = lines_of(c['stdout'])
        line = next((l for l in ls if l.get('mode') == 'honest'), {})
        counts = next((l for l in ls if l.get('mode') == 'counts'), {})
        runs.append(dict(seed=s, exit=c['exit'], wall=c['seconds'], **line, counts=counts, stderr=c['stderr']))
        print(json.dumps({k: v for k, v in runs[-1].items() if k not in ('stderr', 'counts')}), flush=True)
        (exp / f'stage{stage}-honest.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in runs))
    ok = [r for r in runs if r.get('accept')]
    d = dict(accepted=len(ok), of=len(runs), alphas_differ=sum(1 for r in ok if r.get('alphas_differ')), lookup_alphas=sorted({r.get('lookup_alphas') for r in ok}))
    for k in ('prove_s', 'verify_s', 'derive_s', 'build_s', 'proof_bytes', 'peak_rss_kb'):
        if ok: d[k] = st([r[k] for r in ok])
    d['counts'] = runs[0].get('counts') if runs else {}
    d['counts_identical_across_seeds'] = all(r.get('counts') == runs[0].get('counts') for r in runs)
    ev[f'stage{stage}_honest'] = d; save()
    print(json.dumps(d), flush=True)

def do_hostile(stage, ub=False):
    if ub: ev[f'stage{stage}_compile_ubsan'] = compile_('stage1.cpp' if stage == 1 else 'm2.cpp', binary(stage, True), UB)
    c = run_bin(stage, 1, 'hostile', ub)
    (exp / f'stage{stage}-hostile-seed1{"-ubsan" if ub else ""}.jsonl').write_text(c['stdout'])
    ls = lines_of(c['stdout']); hs = [l for l in ls if l.get('mode') == 'hostile']
    by = {}
    for l in hs: by.setdefault(l['class'], [0, 0]); by[l['class']][0] += l['as_expected']; by[l['class']][1] += 1
    d = dict(exit=c['exit'], seconds=c['seconds'], as_expected=sum(l['as_expected'] for l in hs), total=len(hs),
             accepted_cases=[l['attack'] for l in hs if not l['rejected']], by_class=by, stderr=c['stderr'])
    if ub: d['ubsan_reports'] = c['stderr'].count('runtime error')
    ev[f'stage{stage}_hostile{"_ubsan" if ub else ""}'] = d; save()
    print(json.dumps({k: v for k, v in d.items() if k != 'stderr'}), flush=True)

def do_counts():
    c = sh([sys.executable, 'research/operators/qwen_deltanet_m2/count_model.py'])
    model = json.loads(c['stdout'])
    want = {1: model['H2']['armB_m1b_shape'], 2: model['H3']['armB_T16']}
    keys = [('gate_columns', 'gate_columns'), ('range_cells', 'range_cells'), ('lkp_keys', 'lkp_keys'), ('relations', 'relations'), ('columns_used', 'columns_used'),
            ('log_length', 'log_length'), ('rng_multiplicity_places', 'rng_multiplicity_places'), ('remainder_multiplicity_places', 'remainder_multiplicity_places')]
    out = {}
    for stage in (1, 2):
        got = ev.get(f'stage{stage}_honest', {}).get('counts') or {}
        if not got: out[f'stage{stage}'] = dict(measured=False); continue
        rows = {k: dict(built=got.get(k), model=want[stage][m], equal=got.get(k) == want[stage][m]) for k, m in keys}
        out[f'stage{stage}'] = dict(measured=True, all_equal=all(r['equal'] for r in rows.values()), rows=rows,
                                    relation_terms_built=got.get('relation_terms'), relation_terms_model_not_compared=want[stage]['terms'])
    ev['counts_vs_model'] = out; save()
    (exp / 'counts-vs-model.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1), flush=True)

for step in only:
    if step in ('build1', 'build2'): do_build(int(step[-1]))
    elif step in ('honest1', 'honest2'): do_honest(int(step[-1]))
    elif step in ('hostile1', 'hostile2'): do_hostile(int(step[-1]))
    elif step in ('ubsan1', 'ubsan2'): do_hostile(int(step[-1]), True)
    elif step == 'counts': do_counts()
    else: raise SystemExit(f'unknown step {step}')
save()
