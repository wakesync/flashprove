#!/usr/bin/env python3
"""Build and run the bounded native toy key-file suite. No network or downloads."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
FLAGS = ['-std=c++17', '-O2', '-Wall', '-Wextra', '-fno-ipa-modref', '-DBLK_FIELD=2', '-DBLK_HASH=1', '-I', 'blocks']
DEADLINE = dt.datetime(2026, 11, 12, 1, tzinfo=dt.timezone.utc)

def now():
    return dt.datetime.now(dt.timezone.utc)

def command(args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()

def dump(p, obj):
    with p.open('x') as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write('\n')

def stats(v):
    return dict(n=len(v), median=statistics.median(v), sd=statistics.stdev(v) if len(v)>1 else 0,
                min=min(v), max=max(v))

def summarize(out):
    rows=[]
    for p in sorted(out.glob('seed-*/results.json')):
        rows.extend(json.loads(p.read_text())['records'])
    arms={}
    for arm in sorted({r['arm'] for r in rows}):
        rr=[r for r in rows if r['arm']==arm]
        arms[arm]=dict(accepted=sum(r['accepted'] for r in rr), expected_accept=rr[0]['expected'],
                      passed=sum(r['pass'] for r in rr), native_attempted=sum(r['native_attempted'] for r in rr),
                      native_accepted=sum(r['native_accepted'] for r in rr),
                      verify_ms=stats([r['verify_ms'] for r in rr]),
                      key_bytes=stats([r['key_bytes'] for r in rr]),
                      native_key_bytes=stats([r['native_key_bytes'] for r in rr]),
                      stages=sorted({r['stage'] for r in rr}),
                      reasons=sorted({r['reason'] for r in rr}))
    return dict(verdict='PASS' if rows and all(r['pass'] for r in rows) else 'FAIL',
                rows=len(rows), arms=arms, timing_scope='key verification including held-manifest hashing and expected MLE recomputation; not prover or plan construction')

def environment(binary, ubsan=False):
    cpu=next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),'unknown')
    ram=next(line for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))
    return dict(commits={'repo':command(['git','rev-parse','HEAD']), 'base':'cf4b213f1fe4d1c0073e0e1266281eee7e92b79b'},
                toolchain={'compiler':command(['g++','--version']).splitlines()[0], 'python':platform.python_version(), 'flags':FLAGS+(['-fsanitize=undefined','-fno-sanitize-recover=all','-g'] if ubsan else [])},
                hardware={'cpu':cpu, 'affinity':sorted(os.sched_getaffinity(0)), 'memory':ram, 'gpu':'not used', 'provider':'shared CPU host', 'shared_loaded':True},
                binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('mode',choices=['build','debug','suite','summary']);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--binary',type=Path,default=HERE/'work'/'test.bin');ap.add_argument('--ubsan',action='store_true');ap.add_argument('--enforce-deadline',action='store_true')
    a=ap.parse_args(); out=a.out.resolve();binary=a.binary.resolve()
    if a.mode=='summary':
        print(json.dumps(summarize(out),indent=2));return
    out.mkdir(parents=True,exist_ok=False)
    if shutil.disk_usage(ROOT).free<3*1024**3:
        raise SystemExit('free disk below 3 GiB')
    if a.mode=='build':
        binary.parent.mkdir(parents=True,exist_ok=True)
        flags=FLAGS+(['-fsanitize=undefined','-fno-sanitize-recover=all','-g'] if a.ubsan else [])
        args=['g++',*flags,'research/weight-binding/keyfile/test.cpp','-o',str(binary)]
        start=time.monotonic();p=subprocess.run(args,cwd=ROOT,text=True,capture_output=True,timeout=120)
        dump(out/'build.json',dict(exit=p.returncode,elapsed_s=time.monotonic()-start,flags=flags,stdout=p.stdout,stderr=p.stderr.replace(str(ROOT),'<REPO>')))
        raise SystemExit(p.returncode)
    # Invoke the whole command through the host heavy-job gate. This timestamp is
    # taken only once the gate grants its slot, so it also records budget start.
    start=time.monotonic();grant=now();env=environment(binary,a.ubsan)
    seeds=[9001] if a.mode=='debug' else list(range(1001,1011))
    env.update(seeds=seeds,gate_granted_utc=grant.isoformat(),elapsed_budget_s=2100,hard_stop_utc=DEADLINE.isoformat(),deadline_enforced=a.enforce_deadline)
    dump(out/'ENV.json',env)
    done=[]
    for seed in seeds:
        remain=2100-(time.monotonic()-start)
        if a.enforce_deadline:remain=min(remain,(DEADLINE-now()).total_seconds())
        if remain<=0:
            dump(out/'KILLED.json',{'reason':'registered wall clock budget','completed':done});raise SystemExit(124)
        p=subprocess.run([str(binary),str(out/f'seed-{seed:04d}'),str(seed)],cwd=ROOT,text=True,capture_output=True,timeout=remain)
        dump(out/f'run-{seed:03d}.json',dict(seed=seed,exit=p.returncode,stdout=p.stdout,stderr=p.stderr.replace(str(ROOT),'<REPO>')))
        done.append(seed)
        print(p.stdout.strip(),flush=True)
        if p.returncode:
            print(p.stderr,file=sys.stderr);raise SystemExit(p.returncode)
    summary=summarize(out);summary['elapsed_s']=time.monotonic()-start
    dump(out/'summary.json',summary)
    # Separate Python SHA-256 implementation: exact leaf/root encoding cross-check.
    sys.path.insert(0,str(HERE.parent));import wb_manifest
    debug=a.mode=='debug'
    v=[[(r+(2*i+1 if debug else i))%4-2 for i in range(4)] for r in range(4)]
    names=[('debug.' if debug else '')+f'tensor.{r}' for r in range(4)]
    tensors={name:('I64',[4],hashlib.sha256(b''.join(x.to_bytes(8,'little',signed=True) for x in row)).hexdigest()) for name,row in zip(names,v)}
    expected=wb_manifest.Manifest(tensors).id.hex()
    native=[json.loads(p.read_text())['checkpoint_id'] for p in sorted(out.glob('seed-*/results.json'))]
    dump(out/'manifest-cross-check.json',dict(expected=expected,native=native,pass_all=all(x==expected for x in native),tensors=tensors))
    assert all(x==expected for x in native)
    raise SystemExit(0 if summary['verdict']=='PASS' else 1)

if __name__=='__main__':main()
