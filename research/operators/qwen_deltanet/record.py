#!/usr/bin/env python3
"""CPU-only receipt for the Qwen3.8 Gated DeltaNet M1 slice. No downloads, no GPU.

Generates the 10 pre-registered fixtures (seeds 1..10), compiles test.cpp, runs one honest
proof per seed (one process each, sequential), the hostile suite on seed 1, and the range
study (ranges.py). Writes evidence.json here and the raw lines to
experiments/20261104-11-qwen-deltanet-m1/runs/. Fixtures go to work/ (git-ignored).
"""
import hashlib, json, pathlib, platform, statistics, subprocess, sys, time
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
rel = str(here.relative_to(root))
exp = root / 'experiments/20261104-11-qwen-deltanet-m1/runs'
work = here / 'work'; work.mkdir(exist_ok=True); exp.mkdir(parents=True, exist_ok=True)
SEEDS = list(range(1, 11))
only = sys.argv[1:]  # optional: subset of {build,honest,hostile,ranges}

def sh(argv, timeout=3600):
    t = time.monotonic(); p = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=timeout)
    return dict(argv=[str(a) for a in argv], exit=p.returncode, seconds=round(time.monotonic() - t, 3), stdout=p.stdout, stderr=p.stderr[-4000:])

ev_path = here / 'evidence.json'
ev = json.loads(ev_path.read_text()) if ev_path.exists() and only else {}
ev.update(platform=platform.platform(), python=sys.version.split()[0],
          compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
          base=subprocess.check_output(['git', 'merge-base', 'HEAD', 'origin/main'], cwd=root, text=True).strip())
def save(): ev_path.write_text(json.dumps(ev, indent=1) + '\n')

binary = work / 'test.bin'
if not only or 'build' in only:
    fx = {}
    for s in SEEDS:
        c = sh(['python3', f'{rel}/reference.py', '--seed', str(s), '--out', str(work.relative_to(root) / f'seed{s}.bin')])
        assert c['exit'] == 0, c
        fx[s] = dict(meta=c['stdout'].strip(), sha256=hashlib.sha256((work / f'seed{s}.bin').read_bytes()).hexdigest())
    ev['fixtures'] = fx
    c = sh(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks',
            f'{rel}/test.cpp', '-o', str(binary.relative_to(root))])
    ev['compile'] = c; save(); assert c['exit'] == 0, c['stderr']

if not only or 'honest' in only:
    runs = []
    for s in SEEDS:
        c = sh([str(binary.relative_to(root)), str(work.relative_to(root) / f'seed{s}.bin'), 'honest'])
        line = json.loads(c['stdout'].splitlines()[0]) if c['stdout'] else {}
        runs.append(dict(seed=s, exit=c['exit'], wall=c['seconds'], **line, stderr=c['stderr']))
        print(json.dumps(runs[-1]), flush=True)
        (exp / 'honest.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in runs))
    def st(k, rs):
        x = [r[k] for r in rs]
        return dict(n=len(x), median=statistics.median(x), sd=statistics.stdev(x) if len(x) > 1 else 0, min=min(x), max=max(x))
    ok = [r for r in runs if r.get('accept')]
    ev['honest'] = dict(accepted=len(ok), of=len(runs),
                        prove_s=st('prove_s', ok), verify_s=st('verify_s', ok), proof_bytes=st('proof_bytes', ok),
                        peak_rss_kb=st('peak_rss_kb', ok),
                        prove_s_without_first=st('prove_s', ok[1:]) if len(ok) > 2 else None)
    save()

if not only or 'hostile' in only:
    c = sh([str(binary.relative_to(root)), str(work.relative_to(root) / 'seed1.bin'), 'hostile'], timeout=7200)
    (exp / 'hostile-seed1.jsonl').write_text(c['stdout'])
    lines = [json.loads(l) for l in c['stdout'].splitlines() if l.startswith('{')]
    hos = [l for l in lines if l['mode'] == 'hostile']
    by = {}
    for l in hos: by.setdefault(l['class'], [0, 0]); by[l['class']][0] += l['rejected']; by[l['class']][1] += 1
    ev['hostile'] = dict(exit=c['exit'], seconds=c['seconds'], per_class={k: dict(rejected=v[0], total=v[1]) for k, v in by.items()},
                         rejected=sum(l['rejected'] for l in hos), total=len(hos), stderr=c['stderr'])
    print(json.dumps(ev['hostile']), flush=True); save()

if not only or 'ranges' in only:
    c = sh(['python3', f'{rel}/ranges.py'])
    ev['ranges'] = dict(exit=c['exit'], seconds=c['seconds'], stdout=c['stdout'])
    (exp / 'ranges.json').write_text((here / 'ranges.json').read_text())
    print(c['stdout'], flush=True); save()

paths = sorted(list(here.glob('*.py')) + list(here.glob('*.cpp')) + list(here.glob('*.h'))) + \
    [here.parent / 'affine_rows/product.h', here.parent / 'shared_wires/product.h', here.parent / 'public_binding/product.h']
ev['sha256'] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
save(); print('record: done')
