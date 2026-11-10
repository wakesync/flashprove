#!/usr/bin/env python3
"""CPU-only runs. Invoke through the planning heavy-job gate, with <=6-core affinity."""
import hashlib
import json
import pathlib
import statistics
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXP = ROOT/'experiments/20261109-35-qwen-operators'
RUNS = EXP/'runs'
WORK = HERE/'work'
REL = str(HERE.relative_to(ROOT))
RUNS.mkdir(exist_ok=True)
WORK.mkdir(exist_ok=True)


def stats(v):
    return dict(n=len(v), median=statistics.median(v), sd=statistics.stdev(v) if len(v)>1 else 0, min=min(v), max=max(v))


def run(args):
    p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if p.stderr:
        print(p.stderr[-4000:], file=sys.stderr)
    if p.returncode:
        raise RuntimeError((args, p.returncode, p.stdout[-2000:], p.stderr[-2000:]))
    return p.stdout


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv)>1 else 'all'
    op = sys.argv[2] if len(sys.argv)>2 else 'nonlinear'
    exe = f'{REL}/work/proof.bin'
    if mode in ('final','ubsan-all'):
        build_mode='build' if mode=='final' else 'ubsan-build'
        print(run([sys.executable,f'{REL}/record.py',build_mode]),end='',flush=True)
        for operator in ('nonlinear','conv','l2','rms','rotary'):
            phases=('honest','hostile','smoke') if mode=='final' else ('ubsan-hostile',)
            for phase in phases:
                print(run([sys.executable,f'{REL}/record.py',phase,operator]),end='',flush=True)
        out=run([exe,'conv','12','1','history-control'])
        suffix='-ubsan' if mode=='ubsan-all' else ''
        (RUNS/f'conv-history-control{suffix}.jsonl').write_text(out)
        print(out,end='',flush=True)
        sys.exit(0)
    if mode in ('all','build','ubsan','ubsan-build'):
        cmd = ['g++','-std=c++17','-O2','-Wall','-Wextra','-fno-ipa-modref','-DBLK_FIELD=2','-DBLK_HASH=1','-I','blocks',f'{REL}/proof.cpp','-o',exe]
        if mode in ('ubsan','ubsan-build'):
            cmd += ['-fsanitize=undefined','-fno-sanitize-recover=undefined']
        run(cmd)
        metadata=dict(source_commit=run(['git','rev-parse','HEAD']).strip(),
                      dirty_tracked=bool(run(['git','diff','--name-only']).strip()),
                      compiler=run(['g++','--version']).splitlines()[0], command=cmd,
                      proof_cpp_sha256=hashlib.sha256((HERE/'proof.cpp').read_bytes()).hexdigest(),
                      binary_sha256=hashlib.sha256((ROOT/exe).read_bytes()).hexdigest())
        suffix='-ubsan' if mode in ('ubsan','ubsan-build') else ''
        (RUNS/f'build{suffix}.json').write_text(json.dumps(metadata,indent=2)+'\n')
    if mode in ('all','honest'):
        lines=[]
        for seed in range(1,11):
            out=run([exe,op,'12',str(seed),'honest'])
            lines.extend(json.loads(l) for l in out.splitlines())
            print(out,end='',flush=True)
            (RUNS/f'{op}-honest.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in lines))
        summary={k:stats([x[k] for x in lines]) for k in ('prove_s','verify_s','proof_bytes','columns','relations')}
        summary['accepted']=sum(x['accept'] for x in lines)
        (RUNS/f'{op}-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if mode in ('all','hostile','ubsan','ubsan-hostile'):
        out=run([exe,op,'12','1','hostile'])
        suffix = '-ubsan' if mode in ('ubsan','ubsan-hostile') else ''
        (RUNS/f'{op}-hostile{suffix}.jsonl').write_text(out)
        print(out,end='',flush=True)
    if mode=='smoke':
        for f in (14,16):
            out=run([exe,op,str(f),'1','honest'])
            (RUNS/f'{op}-f{f}-smoke.jsonl').write_text(out)
            print(out,end='',flush=True)
