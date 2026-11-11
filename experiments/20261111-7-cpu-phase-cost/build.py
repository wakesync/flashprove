#!/usr/bin/env python3
"""Build the two phase harnesses of experiments/20261111-7-cpu-phase-cost (CPU only, no CUDA).

Usage (from the repository root):  python3 experiments/20261111-7-cpu-phase-cost/build.py <work_dir> [--debug]
Writes <work_dir>/phase_a and <work_dir>/phase_b (or phase_b_d16 with --debug: STAGE1_D=16, debug only,
never a reported number) and <work_dir>/build.json with flags, compiler and binary SHA-256s.
"""
import hashlib, json, pathlib, subprocess, sys, time
root = pathlib.Path(__file__).resolve().parents[2]
exp = pathlib.Path(__file__).resolve().parent
work = pathlib.Path(sys.argv[1]).resolve(); work.mkdir(parents=True, exist_ok=True)
debug = '--debug' in sys.argv[2:]
# Profile A: the flags of experiments/20261103-7-cpu-commit/build.sh. Profile B: research/operators/qwen_deltanet_m2_build/record.py.
FLAGS_A = ['-O2', '-fno-ipa-modref', '-std=c++17', '-pthread', '-DBLK_FIELD=2', '-D_GLIBCXX_ASSERTIONS']
FLAGS_B = ['-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1']
CXX = 'g++-13'
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
out = {'compiler': subprocess.check_output([CXX, '--version'], text=True).splitlines()[0], 'binaries': {}}
jobs = []
if not debug:
    jobs.append(('phase_a', [CXX, *FLAGS_A, '-I', str(root / 'blocks'), str(exp / 'phase_a.cpp'), '-o', str(work / 'phase_a')], FLAGS_A))
    jobs.append(('phase_b', [CXX, *FLAGS_B, '-I', str(root / 'blocks'), str(exp / 'phase_b.cpp'), '-o', str(work / 'phase_b')], FLAGS_B))
else:
    jobs.append(('phase_a', [CXX, *FLAGS_A, '-I', str(root / 'blocks'), str(exp / 'phase_a.cpp'), '-o', str(work / 'phase_a')], FLAGS_A))
    jobs.append(('phase_b_d16', [CXX, *FLAGS_B, '-DSTAGE1_D=16', '-I', str(root / 'blocks'), str(exp / 'phase_b.cpp'), '-o', str(work / 'phase_b_d16')], FLAGS_B + ['-DSTAGE1_D=16']))
for name, argv, flags in jobs:
    t = time.monotonic()
    p = subprocess.run(argv, cwd=root, capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stderr[-6000:]); sys.exit(p.returncode)
    out['binaries'][name] = dict(flags=flags + ['-I', 'blocks'], seconds=round(time.monotonic() - t, 1),
                                 warnings=p.stderr.count('warning:'), sha256=sha(work / name))
    print(name, out['binaries'][name]['seconds'], 's', 'warnings', out['binaries'][name]['warnings'], flush=True)
(work / 'build.json').write_text(json.dumps(out, indent=1) + '\n')
