#!/usr/bin/env python3
"""CPU receipt for the Qwen DeltaNet M2 design prototypes (experiments/20261105-32-qwen-deltanet-m2-design).

Usage: record.py [build] [honest] [hostile] [ubsan] [model] [ranges]
  build    fixtures (M1 reference.py, seeds 1..10) + compile admit_proto.cpp
  honest   H5a: one honest proof per seed through verify_from_words (pinned to 6 cores)
  hostile  H5b/c: hostile public encodings + R9 on seed 1
  ubsan    post-review: the hostile suite again, built with -fsanitize=undefined (no recover)
  model    H1-H3: count_model.py
  ranges   H4: head_reference.py range suite
Writes evidence.json here and raw lines to the experiment's runs/.
"""
import hashlib, json, os, pathlib, platform, statistics, subprocess, sys, time
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(root / 'research/operators/qwen_deltanet'))
import reference as R
rel = str(here.relative_to(root))
exp = root / 'experiments/20261105-32-qwen-deltanet-m2-design/runs'
work = here / 'work'; work.mkdir(exist_ok=True); exp.mkdir(parents=True, exist_ok=True)
SEEDS = list(range(1, 11))
CORES = os.environ.get('M2_CORES', '0-5')
only = sys.argv[1:]

def sh(argv, timeout=7200):
    t = time.monotonic(); p = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=timeout)
    return dict(argv=[str(a) for a in argv], exit=p.returncode, seconds=round(time.monotonic() - t, 3), stdout=p.stdout, stderr=p.stderr[-4000:])
def st(x):
    return dict(n=len(x), median=statistics.median(x), sd=statistics.stdev(x) if len(x) > 1 else 0, min=min(x), max=max(x))

ev_path = here / 'evidence.json'
ev = json.loads(ev_path.read_text()) if ev_path.exists() and only else {}
ev.update(platform=platform.platform(), python=sys.version.split()[0], cores=CORES,
          compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
          base=subprocess.check_output(['git', 'merge-base', 'HEAD', 'origin/main'], cwd=root, text=True).strip(),
          sources={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                   sorted(here.glob('*.py')) + sorted(here.glob('*.cpp')) + sorted(here.glob('*.h')) +
                   [root / 'research/operators/qwen_deltanet_lookup/lookup.h', root / 'research/operators/qwen_deltanet/reference.py']})
def save(): ev_path.write_text(json.dumps(ev, indent=1) + '\n')
binary = work / 'admit_proto.bin'
def run_bin(fx, mode):
    return sh(['taskset', '-c', CORES, str(binary.relative_to(root)), str(fx.relative_to(root)), mode])

if not only or 'build' in only:
    fx = {}
    for s in SEEDS:
        out = work / f'seed{s}.bin'
        meta = R.write_fixture(str(out), s)
        fx[s] = dict(meta=meta, sha256=hashlib.sha256(out.read_bytes()).hexdigest())
    ev['fixtures'] = fx
    c = sh(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks',
            f'{rel}/admit_proto.cpp', '-o', str(binary.relative_to(root))])
    ev['compile'] = c; save(); assert c['exit'] == 0, c['stderr']

if not only or 'honest' in only:
    runs = []
    for s in SEEDS:
        c = run_bin(work / f'seed{s}.bin', 'honest')
        line = json.loads(c['stdout'].splitlines()[0]) if c['stdout'] else {}
        runs.append(dict(seed=s, exit=c['exit'], wall=c['seconds'], **line, stderr=c['stderr']))
        print(json.dumps({k: v for k, v in runs[-1].items() if k != 'stderr'}), flush=True)
        (exp / 'h5-honest.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in runs))
    ok = [r for r in runs if r.get('accept')]
    ev['honest'] = dict(accepted=len(ok), of=len(runs), prove_s=st([r['prove_s'] for r in ok]), decode_s=st([r['decode_s'] for r in ok]),
                        derive_s=st([r['derive_s'] for r in ok]), verify_s=st([r['verify_s'] for r in ok]),
                        proof_bytes=st([r['proof_bytes'] for r in ok]), peak_rss_kb=st([r['peak_rss_kb'] for r in ok]))
    save()

if not only or 'hostile' in only:
    c = run_bin(work / 'seed1.bin', 'hostile')
    (exp / 'h5-hostile-seed1.jsonl').write_text(c['stdout'])
    lines = [json.loads(l) for l in c['stdout'].splitlines() if l.startswith('{')]
    hs = [l for l in lines if l.get('mode') == 'hostile']
    by = {}
    for l in hs: by.setdefault(l['class'], [0, 0]); by[l['class']][0] += l['as_expected']; by[l['class']][1] += 1
    ev['hostile'] = dict(exit=c['exit'], seconds=c['seconds'], as_expected=sum(l['as_expected'] for l in hs), total=len(hs), by_class=by, stderr=c['stderr'])
    print(json.dumps(ev['hostile']), flush=True); save()

if 'ubsan' in only:
    ub = work / 'admit_proto_ubsan.bin'
    c = sh(['g++', '-std=c++17', '-O2', '-fno-ipa-modref', '-fsanitize=undefined', '-fno-sanitize-recover=undefined', '-DBLK_FIELD=2', '-DBLK_HASH=1',
            '-I', 'blocks', f'{rel}/admit_proto.cpp', '-o', str(ub.relative_to(root))])
    assert c['exit'] == 0, c['stderr']
    c = sh(['taskset', '-c', CORES, str(ub.relative_to(root)), str((work / 'seed1.bin').relative_to(root)), 'hostile'])
    (exp / 'h5-hostile-seed1-ubsan.jsonl').write_text(c['stdout'])
    lines = [json.loads(l) for l in c['stdout'].splitlines() if l.startswith('{')]
    hs = [l for l in lines if l.get('mode') == 'hostile']
    ev['hostile_ubsan'] = dict(exit=c['exit'], seconds=c['seconds'], as_expected=sum(l['as_expected'] for l in hs), total=len(hs),
                               ubsan_reports=c['stderr'].count('runtime error'), stderr=c['stderr'])
    print(json.dumps({k: v for k, v in ev['hostile_ubsan'].items() if k != 'stderr'}), flush=True); save()

if not only or 'model' in only:
    c = sh([sys.executable, f'{rel}/count_model.py', '--json', str((exp / 'model.json').relative_to(root))])
    ev['model'] = dict(exit=c['exit'], seconds=c['seconds'], stdout=c['stdout'][-6000:]); print(c['stdout']); save()

if not only or 'ranges' in only:
    c = sh(['taskset', '-c', CORES, sys.executable, f'{rel}/head_reference.py', '--suite', '--json', str((exp / 'ranges-head.json').relative_to(root))])
    ev['ranges'] = dict(exit=c['exit'], seconds=c['seconds'], stdout=c['stdout'][-6000:]); print(c['stdout']); save()
    # secondary, unregistered: q unscaled (o finer); and a delta conv kernel (pass-through stress)
    for tag, extra in (('q-unscaled', ['--q-unscaled']), ('delta-kernel', ['--kernel', 'delta'])):
        c = sh(['taskset', '-c', CORES, sys.executable, f'{rel}/head_reference.py', '--suite', *extra, '--json', str((exp / f'ranges-head-{tag}.json').relative_to(root))])
        ev[f'ranges_{tag}'] = dict(exit=c['exit'], seconds=c['seconds'], stdout=c['stdout'][-3000:]); print(c['stdout'][-1500:]); save()
