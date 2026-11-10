#!/usr/bin/env python3
"""CPU receipt for the Qwen DeltaNet M2 design prototypes (experiments/20261105-32-qwen-deltanet-m2-design).

Usage: [M2_RUN_TAG=<tag>] [M2_CORES=0-5] record.py [build] [honest] [hostile] [ubsan] [ubsan-honest] [model] [norm] [ranges]
  build         fixtures (M1 reference.py, seeds 1..10) + compile admit_proto.cpp
  honest        H5a: one honest proof per seed through verify_from_words (pinned to 6 cores)
  hostile       H5b/c: hostile public encodings + R9 on seed 1
  ubsan         post-review: the hostile suite again, built with -fsanitize=undefined (no recover)
  ubsan-honest  third review: the honest seeds again under the UBSan build
  model         H1-H3: count_model.py
  norm          third review: norm_alias_regression.py (design-level, no proof), checked against its expected output
  ranges        H4: head_reference.py range suite
Writes evidence.json here and raw lines to the experiment's runs/.

Reruns must not overwrite earlier raw runs. Set M2_RUN_TAG: every raw file then gets the suffix
-<tag> (runs/h5-honest-<tag>.jsonl, ...) and every evidence.json key the suffix @<tag>. Without a
tag the original file names are used (the registered runs and the first two post-review reruns).
Each step records the commit it ran at, whether the binary's inputs were clean at that commit, and
the SHA-256 of the C++ sources of the binary.
"""
import fcntl, hashlib, json, os, pathlib, platform, statistics, subprocess, sys, time
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
sys.path.insert(0, str(root / 'research/operators/qwen_deltanet'))
import reference as R
rel = str(here.relative_to(root))
exp = root / 'experiments/20261105-32-qwen-deltanet-m2-design/runs'
work = here / 'work'; work.mkdir(exist_ok=True); exp.mkdir(parents=True, exist_ok=True)
SEEDS = list(range(1, 11))
CORES = os.environ.get('M2_CORES', '0-5')
TAG = os.environ.get('M2_RUN_TAG', '')
SFX = f'-{TAG}' if TAG else ''
def K(name): return f'{name}@{TAG}' if TAG else name
only = sys.argv[1:]

def sh(argv, timeout=7200):
    t = time.monotonic(); p = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=timeout)
    return dict(argv=[str(a) for a in argv], exit=p.returncode, seconds=round(time.monotonic() - t, 3), stdout=p.stdout, stderr=p.stderr[-4000:])
def st(x):
    return dict(n=len(x), median=statistics.median(x), sd=statistics.stdev(x) if len(x) > 1 else 0, min=min(x), max=max(x))
def git(*a): return subprocess.check_output(['git', *a], cwd=root, text=True).strip()
CXX = [here / 'admit_proto.cpp', here / 'm1b_builder.h', root / 'research/operators/qwen_deltanet_lookup/lookup.h']
BINARY_INPUTS = ['blocks', 'research/operators/qwen_deltanet_lookup', f'{rel}/admit_proto.cpp', f'{rel}/m1b_builder.h', 'research/operators/qwen_deltanet/reference.py']
def where():
    """The commit a step ran at, and the sources of the binary it ran. binary_inputs_dirty: whether
    anything the binary or its fixtures are built from (blocks/, lookup.h, the two prototype sources,
    the M1 reference) differed from that commit. Documents and receipts may differ: the run itself
    rewrites evidence.json."""
    return dict(head=git('rev-parse', 'HEAD'), binary_inputs_dirty=bool(git('status', '--porcelain', '--', *BINARY_INPUTS)),
                cxx_sha256={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in CXX}, cores=CORES)

ev_path = here / 'evidence.json'
class Ev(dict):
    """evidence.json in memory; remembers which keys this process set, so that two record.py runs
    at once (the -O2 and the UBSan chains) do not drop each other's keys on save."""
    touched = set()
    def __setitem__(s, k, v): s.touched.add(k); super().__setitem__(k, v)
ev = Ev(json.loads(ev_path.read_text()) if ev_path.exists() and only else {})
env = dict(platform=platform.platform(), python=sys.version.split()[0], cores=CORES,
           compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
           base=subprocess.check_output(['git', 'merge-base', 'HEAD', 'origin/main'], cwd=root, text=True).strip(),
           sources={str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                    sorted(here.glob('*.py')) + sorted(here.glob('*.cpp')) + sorted(here.glob('*.h')) +
                    [root / 'research/operators/qwen_deltanet_lookup/lookup.h', root / 'research/operators/qwen_deltanet/reference.py']})
# A tagged rerun keeps the earlier receipts' top-level environment (their cores, their source hashes).
if TAG: ev[K('env')] = env
else:
    for k_, v_ in env.items(): ev[k_] = v_
def save():
    with open(work / 'evidence.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cur = json.loads(ev_path.read_text()) if ev_path.exists() and only else {}
        for k_ in ev.touched: cur[k_] = ev[k_]
        tmp = ev_path.with_suffix('.json.tmp'); tmp.write_text(json.dumps(cur, indent=1) + '\n'); os.replace(tmp, ev_path)
binary = work / 'admit_proto.bin'
ubsan_binary = work / 'admit_proto_ubsan.bin'
def run_bin(fx, mode, b=None):
    return sh(['taskset', '-c', CORES, str((b or binary).relative_to(root)), str(fx.relative_to(root)), mode])
def build_ubsan():
    c = sh(['g++', '-std=c++17', '-O2', '-fno-ipa-modref', '-fsanitize=undefined', '-fno-sanitize-recover=undefined', '-DBLK_FIELD=2', '-DBLK_HASH=1',
            '-I', 'blocks', f'{rel}/admit_proto.cpp', '-o', str(ubsan_binary.relative_to(root))])
    assert c['exit'] == 0, c['stderr']
def honest_runs(b, out):
    runs = []
    for s in SEEDS:
        c = run_bin(work / f'seed{s}.bin', 'honest', b)
        line = json.loads(c['stdout'].splitlines()[0]) if c['stdout'] else {}
        runs.append(dict(seed=s, exit=c['exit'], wall=c['seconds'], **line, stderr=c['stderr']))
        print(json.dumps({k: v for k, v in runs[-1].items() if k != 'stderr'}), flush=True)
        out.write_text(''.join(json.dumps(r) + '\n' for r in runs))
    ok = [r for r in runs if r.get('accept')]
    return dict(accepted=len(ok), of=len(runs), prove_s=st([r['prove_s'] for r in ok]), decode_s=st([r['decode_s'] for r in ok]),
                derive_s=st([r['derive_s'] for r in ok]), verify_s=st([r['verify_s'] for r in ok]),
                proof_bytes=st([r['proof_bytes'] for r in ok]), peak_rss_kb=st([r['peak_rss_kb'] for r in ok]),
                nonzero_exits=sum(r['exit'] != 0 for r in runs), runtime_error_lines=sum(r['stderr'].count('runtime error') for r in runs),
                stderr_bytes=sum(len(r['stderr']) for r in runs), **where())

if not only or 'build' in only:
    fx = {}
    for s in SEEDS:
        out = work / f'seed{s}.bin'
        meta = R.write_fixture(str(out), s)
        fx[s] = dict(meta=meta, sha256=hashlib.sha256(out.read_bytes()).hexdigest())
    ev[K('fixtures')] = fx
    c = sh(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks',
            f'{rel}/admit_proto.cpp', '-o', str(binary.relative_to(root))])
    ev[K('compile')] = dict(c, **where()); save(); assert c['exit'] == 0, c['stderr']

if not only or 'honest' in only:
    ev[K('honest')] = honest_runs(binary, exp / f'h5-honest{SFX}.jsonl')
    save()

if not only or 'hostile' in only:
    c = run_bin(work / 'seed1.bin', 'hostile')
    (exp / f'h5-hostile-seed1{SFX}.jsonl').write_text(c['stdout'])
    lines = [json.loads(l) for l in c['stdout'].splitlines() if l.startswith('{')]
    hs = [l for l in lines if l.get('mode') == 'hostile']
    by = {}
    for l in hs: by.setdefault(l['class'], [0, 0]); by[l['class']][0] += l['as_expected']; by[l['class']][1] += 1
    ev[K('hostile')] = dict(exit=c['exit'], seconds=c['seconds'], as_expected=sum(l['as_expected'] for l in hs), total=len(hs), by_class=by, stderr=c['stderr'], **where())
    print(json.dumps(ev[K('hostile')]), flush=True); save()

if 'ubsan' in only:
    build_ubsan()
    c = sh(['taskset', '-c', CORES, str(ubsan_binary.relative_to(root)), str((work / 'seed1.bin').relative_to(root)), 'hostile'])
    (exp / f'h5-hostile-seed1-ubsan{SFX}.jsonl').write_text(c['stdout'])
    lines = [json.loads(l) for l in c['stdout'].splitlines() if l.startswith('{')]
    hs = [l for l in lines if l.get('mode') == 'hostile']
    ev[K('hostile_ubsan')] = dict(exit=c['exit'], seconds=c['seconds'], as_expected=sum(l['as_expected'] for l in hs), total=len(hs),
                                  ubsan_reports=c['stderr'].count('runtime error'), stderr=c['stderr'], **where())
    print(json.dumps({k: v for k, v in ev[K('hostile_ubsan')].items() if k != 'stderr'}), flush=True); save()

if 'ubsan-honest' in only:
    if not ubsan_binary.exists() or 'ubsan' not in only: build_ubsan()
    ev[K('honest_ubsan')] = honest_runs(ubsan_binary, exp / f'h5-honest-ubsan{SFX}.jsonl')
    ev[K('honest_ubsan')]['ubsan_reports'] = ev[K('honest_ubsan')]['runtime_error_lines']
    save()

if not only or 'model' in only:
    c = sh([sys.executable, f'{rel}/count_model.py', '--json', str((exp / f'model{SFX}.json').relative_to(root))])
    ev[K('model')] = dict(exit=c['exit'], seconds=c['seconds'], stdout=c['stdout'][-6000:], **where()); print(c['stdout']); save()

if 'norm' in only:
    c = sh([sys.executable, f'{rel}/norm_alias_regression.py', '--json', str((exp / f'norm-alias-regression{SFX}.json').relative_to(root)),
            '--check', f'{rel}/norm_alias_expected.json'])
    ev[K('norm')] = dict(exit=c['exit'], seconds=c['seconds'], stdout=c['stdout'][-3000:], stderr=c['stderr'], **where()); print(c['stdout'][-3000:]); save()
    assert c['exit'] == 0, c['stderr']

if not only or 'ranges' in only:
    c = sh(['taskset', '-c', CORES, sys.executable, f'{rel}/head_reference.py', '--suite', '--json', str((exp / f'ranges-head{SFX}.json').relative_to(root))])
    ev[K('ranges')] = dict(exit=c['exit'], seconds=c['seconds'], stdout=c['stdout'][-6000:]); print(c['stdout']); save()
    # secondary, unregistered: q unscaled (o finer); and a delta conv kernel (pass-through stress)
    for tag, extra in (('q-unscaled', ['--q-unscaled']), ('delta-kernel', ['--kernel', 'delta'])):
        c = sh(['taskset', '-c', CORES, sys.executable, f'{rel}/head_reference.py', '--suite', *extra, '--json', str((exp / f'ranges-head-{tag}{SFX}.json').relative_to(root))])
        ev[K(f'ranges_{tag}')] = dict(exit=c['exit'], seconds=c['seconds'], stdout=c['stdout'][-3000:]); print(c['stdout'][-1500:]); save()
