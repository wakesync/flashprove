#!/usr/bin/env python3
"""CPU-only receipt for the MoE top-k routing slice. No downloads, no GPU.

Generates the pre-registered fixtures (two arms x seeds 1..10, plus the E=16 enumeration
fixtures), compiles test.cpp, runs one honest proof per seed (one process each, sequential,
pinned to <= 6 cores with taskset), the hostile suite on seed 1 per arm and the relation-level
enumeration (H2b). Writes evidence.json here and the raw lines to
experiments/20261105-11-moe-topk-routing/runs/. Fixtures go to work/ (git-ignored).
"""
import hashlib, json, os, pathlib, platform, shutil, statistics, subprocess, sys, time
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
rel = str(here.relative_to(root))
exp = root / 'experiments/20261105-11-moe-topk-routing/runs'
work = here / 'work'; work.mkdir(exist_ok=True); exp.mkdir(parents=True, exist_ok=True)
ARMS = ['glm', 'deepseek']
SEEDS = list(range(1, 11))
CORES = '0-5'
only = sys.argv[1:]  # optional subset of {build,honest,hostile,enum}

def sh(argv, timeout=3600):
    t = time.monotonic(); p = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=timeout)
    return dict(argv=[str(a) for a in argv], exit=p.returncode, seconds=round(time.monotonic() - t, 3), stdout=p.stdout, stderr=p.stderr[-4000:])
def pin(argv):
    return (['taskset', '-c', CORES] if shutil.which('taskset') else []) + argv

ev_path = here / 'evidence.json'
ev = json.loads(ev_path.read_text()) if ev_path.exists() and only else {}
ev.update(platform=platform.platform(), python=sys.version.split()[0], cpu_count=os.cpu_count(), pinned_cores=CORES,
          compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
          base=subprocess.check_output(['git', 'merge-base', 'HEAD', 'origin/main'], cwd=root, text=True).strip())
def save(): ev_path.write_text(json.dumps(ev, indent=1) + '\n')
def fx(name): return work.relative_to(root) / name

binary = work / 'test.bin'
if not only or 'build' in only:
    fixtures = {}
    for arm in ARMS:
        for s in SEEDS:
            c = sh(['python3', f'{rel}/reference.py', '--arm', arm, '--seed', str(s), '--out', str(fx(f'{arm}{s}.bin'))])
            assert c['exit'] == 0, c
            fixtures[f'{arm}{s}'] = dict(meta=json.loads(c['stdout']), sha256=hashlib.sha256((work / f'{arm}{s}.bin').read_bytes()).hexdigest())
    for k in (2, 3):
        c = sh(['python3', f'{rel}/reference.py', '--arm', 'enum', '--E', '16', '--k', str(k), '--h', '2', '--T', '1', '--seed', '1', '--out', str(fx(f'enum{k}.bin'))])
        assert c['exit'] == 0, c
        fixtures[f'enum{k}'] = dict(meta=json.loads(c['stdout']), sha256=hashlib.sha256((work / f'enum{k}.bin').read_bytes()).hexdigest())
    ev['fixtures'] = fixtures
    c = sh(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks',
            f'{rel}/test.cpp', '-o', str(binary.relative_to(root))])
    ev['compile'] = c; save(); assert c['exit'] == 0, c['stderr']

def st(k, rs):
    x = [r[k] for r in rs]
    return dict(n=len(x), median=statistics.median(x), sd=statistics.stdev(x) if len(x) > 1 else 0, min=min(x), max=max(x))

if not only or 'honest' in only:
    ev['honest'] = {}
    for arm in ARMS:
        runs = []
        for s in SEEDS:
            c = sh(pin([str(binary.relative_to(root)), str(fx(f'{arm}{s}.bin')), 'honest']))
            line = json.loads(c['stdout'].splitlines()[0]) if c['stdout'] else {}
            runs.append(dict(arm=arm, seed=s, exit=c['exit'], wall=c['seconds'], **line, stderr=c['stderr']))
            print(json.dumps(runs[-1]), flush=True)
        (exp / f'honest-{arm}.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in runs))
        ok = [r for r in runs if r.get('accept')]
        ev['honest'][arm] = dict(accepted=len(ok), of=len(runs),
                                 prove_s=st('prove_s', ok), verify_s=st('verify_s', ok), proof_bytes=st('proof_bytes', ok),
                                 peak_rss_kb=st('peak_rss_kb', ok), prove_s_without_first=st('prove_s', ok[1:]) if len(ok) > 2 else None,
                                 columns=dict((k, ok[0][k]) for k in ('columns_used', 'selection_columns_per_token', 'aggregation_columns_per_token', 'log_length', 'relations', 'relation_terms')) if ok else None)
        save()

if not only or 'hostile' in only:
    ev['hostile'] = {}
    for arm in ARMS:
        c = sh(pin([str(binary.relative_to(root)), str(fx(f'{arm}1.bin')), 'hostile']), timeout=7200)
        lines = [json.loads(l) for l in c['stdout'].splitlines() if l.startswith('{')]
        (exp / f'hostile-{arm}.jsonl').write_text(''.join(json.dumps(l) + '\n' for l in lines))
        hs = [l for l in lines if l['mode'] == 'hostile']
        by = {}
        for l in hs:
            d = by.setdefault(l['class'], dict(rejected=0, total=0, min_violated=None))
            d['total'] += 1; d['rejected'] += l['rejected']
            if l['class'][:2] in ('a1', 'a2', 'a3', 'a4', 'a5', 'a6'):
                d['min_violated'] = l['violated_relations'] if d['min_violated'] is None else min(d['min_violated'], l['violated_relations'])
        ev['hostile'][arm] = dict(exit=c['exit'], seconds=c['seconds'], rejected=sum(l['rejected'] for l in hs), total=len(hs), by_class=by, stderr=c['stderr'])
        print(json.dumps(ev['hostile'][arm]), flush=True); save()

if not only or 'enum' in only:
    ev['enum'] = {}
    for k in (2, 3):
        c = sh([str(binary.relative_to(root)), str(fx(f'enum{k}.bin')), 'enum'])
        ev['enum'][f'k{k}'] = dict(exit=c['exit'], seconds=c['seconds'], **json.loads(c['stdout'].splitlines()[0]))
        print(json.dumps(ev['enum'][f'k{k}']), flush=True)
    (exp / 'enum.json').write_text(json.dumps(ev['enum'], indent=1) + '\n'); save()
