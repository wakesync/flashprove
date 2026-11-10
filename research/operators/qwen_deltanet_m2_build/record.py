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
host's heavy-job gate; cores come from M2_CORES (default 0-5). M2_NOT_AFTER (UTC, e.g.
2026-11-10T04:08:00Z): a step that would START after it is skipped and recorded as skipped.

Provenance is recorded per step under evidence.json "provenance": the commit, the files of this
directory that differ from it, every source hash, UTC start and end, and the load average. (The
first version of this script kept one top-level "head" and "sources" that every invocation
overwrote; the stage 1 steps ran under that version, and their record is kept as it was written.)
"""
import datetime, hashlib, json, os, pathlib, platform, statistics, subprocess, sys, time
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(root / 'research/operators/qwen_deltanet'))
sys.path.insert(0, str(here))
rel = str(here.relative_to(root))
exp = root / 'experiments/20261109-32-qwen-deltanet-lookup-build/runs'
work = here / 'work'; work.mkdir(exist_ok=True); exp.mkdir(parents=True, exist_ok=True)
SEEDS = list(range(1, 11))
CORES = os.environ.get('M2_CORES', '0-5')
NOT_AFTER = os.environ.get('M2_NOT_AFTER', '')
only = sys.argv[1:]
FLAGS = ['-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks']
UB = ['-fsanitize=undefined', '-fno-sanitize-recover=undefined']

def now(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
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
def git(*a): return subprocess.check_output(['git', *a], cwd=root, text=True).strip()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def sources():
    files = sorted(here.glob('*.py')) + sorted(here.glob('*.cpp')) + sorted(here.glob('*.h')) + sorted((here / 'tables').glob('*')) + \
        [root / 'research/operators/qwen_deltanet_lookup/lookup.h', root / 'research/operators/qwen_deltanet/reference.py', root / 'blocks/iop/lkp.h', root / 'blocks/iop/rng.h']
    return {str(p.relative_to(root)): sha(p) for p in files}

ev_path = here / 'evidence.json'
ev = json.loads(ev_path.read_text()) if ev_path.exists() else {}
ev.setdefault('provenance', {})
if 'sources' in ev:  # written by the first version of this script, during the stage 1 steps
    ev['provenance']['stage1_steps_as_first_recorded'] = dict(
        head=ev.pop('head', None), sources=ev.pop('sources'), cores=ev.get('cores'),
        note='one record for honest1, hostile1 and ubsan1: they ran in one process, which hashed the sources when it started')
ev.update(platform=platform.platform(), python=sys.version.split()[0], compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0])
def save(): ev_path.write_text(json.dumps(ev, indent=1, sort_keys=True) + '\n')

def compile_(src, out, extra=()):
    c = sh(['g++', *FLAGS, *extra, f'{rel}/{src}', '-o', str(out.relative_to(root))])
    assert c['exit'] == 0, c['stderr']
    return dict(exit=c['exit'], seconds=c['seconds'], warnings=c['stderr'].count('warning:'), binary_sha256=sha(out), flags=FLAGS + list(extra))
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
            fx[s] = dict(meta=meta, sha256=sha(fixture(1, s)))
    else:
        import reference_m2 as R2
        for s in SEEDS:
            meta = R2.write_fixture(str(fixture(2, s)), s)
            fx[s] = dict(meta=meta, sha256=sha(fixture(2, s)))
    ev[f'stage{stage}_fixtures'] = fx
    ev[f'stage{stage}_compile'] = compile_('stage1.cpp' if stage == 1 else 'm2.cpp', binary(stage)); save()

def do_honest(stage):
    runs = []
    for s in SEEDS:
        c = run_bin(stage, s, 'honest')
        ls = lines_of(c['stdout'])
        line = next((l for l in ls if l.get('mode') == 'honest'), {})
        counts = next((l for l in ls if l.get('mode') == 'counts'), {})
        runs.append(dict(seed=s, exit=c['exit'], wall=c['seconds'], finished_utc=now(), **line, counts=counts, stderr=c['stderr']))
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
    d = dict(exit=c['exit'], seconds=c['seconds'], as_expected=sum(l['as_expected'] for l in hs), total=len(hs), finished_summary=any(l.get('mode') == 'hostile-summary' for l in ls),
             accepted_cases=[l['attack'] for l in hs if not l['rejected']], not_as_expected=[l['attack'] for l in hs if not l['as_expected']], by_class=by, stderr=c['stderr'])
    if ub: d['ubsan_reports'] = c['stderr'].count('runtime error')
    ev[f'stage{stage}_hostile{"_ubsan" if ub else ""}'] = d; save()
    print(json.dumps({k: v for k, v in d.items() if k != 'stderr'}), flush=True)

def do_counts():
    c = sh([sys.executable, 'research/operators/qwen_deltanet_m2/count_model.py'])
    model = json.loads(c['stdout'])
    want = {1: model['H2']['armB_m1b_shape'], 2: model['H3']['armB_T16']}
    keys = ['gate_columns', 'range_cells', 'lkp_keys', 'relations', 'columns_used', 'log_length', 'rng_multiplicity_places', 'remainder_multiplicity_places']
    out = {}
    for stage in (1, 2):
        got = ev.get(f'stage{stage}_honest', {}).get('counts') or {}
        if not got: out[f'stage{stage}'] = dict(measured=False); continue
        rows = {k: dict(built=got.get(k), model=want[stage][k], equal=got.get(k) == want[stage][k]) for k in keys}
        out[f'stage{stage}'] = dict(measured=True, all_equal=all(r['equal'] for r in rows.values()), rows=rows,
                                    relation_terms_built=got.get('relation_terms'), relation_terms_model_not_compared=want[stage]['terms'])
    ev['counts_vs_model'] = out; save()
    (exp / 'counts-vs-model.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1), flush=True)

STEPS = dict(build1=lambda: do_build(1), build2=lambda: do_build(2), honest1=lambda: do_honest(1), honest2=lambda: do_honest(2),
             hostile1=lambda: do_hostile(1), hostile2=lambda: do_hostile(2), ubsan1=lambda: do_hostile(1, True), ubsan2=lambda: do_hostile(2, True), counts=do_counts)
for step in only:
    if step not in STEPS: raise SystemExit(f'unknown step {step}')
    if NOT_AFTER and now() > NOT_AFTER:
        ev['provenance'][step] = dict(skipped=True, reason=f'would start at {now()}, after M2_NOT_AFTER {NOT_AFTER}'); save()
        print(json.dumps({step: ev['provenance'][step]}), flush=True); continue
    dirty = [l for l in git('status', '--porcelain', '--', rel).splitlines() if not l.endswith('evidence.json')]
    p = dict(head=git('rev-parse', 'HEAD'), files_differing_from_head=dirty, sources=sources(), cores=CORES, started_utc=now(), loadavg_start=list(os.getloadavg()))
    STEPS[step]()
    p.update(finished_utc=now(), loadavg_end=list(os.getloadavg()))
    ev['provenance'][step] = p; save()
save()
