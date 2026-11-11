#!/usr/bin/env python3
"""Build, debug (separate seed), or once-only registered complete-proof suite.
Run build/suite through the CPU heavy-job gate. Existing receipts are never overwritten.
"""
import argparse
import copy
import datetime
import hashlib
import json
import os
import pathlib
import platform
import statistics
import subprocess
import sys
import time
import numpy as np
import fixtures as X
from count import counts

HERE=X.HERE
ROOT=X.ROOT
EXP=ROOT/'experiments/20261110-93-handoff'
WORK=HERE/'work'
BINARY=WORK/'handoff.bin'

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_new(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
def command(args,timeout=180):
    p=subprocess.run([str(x) for x in args],cwd=ROOT,text=True,capture_output=True,timeout=timeout)
    rows=[json.loads(x) for x in p.stdout.splitlines() if x.startswith('{')]
    if not rows:raise RuntimeError(f'command failed: {p.returncode}: {p.stderr[-2000:]}')
    row=rows[-1];row['exit']=p.returncode
    return row

def build():
    WORK.mkdir(exist_ok=True)
    flags=['-std=c++17','-O2','-Wall','-Wextra','-fno-ipa-modref','-DBLK_FIELD=2','-DBLK_HASH=1','-I','blocks']
    args=['g++',*flags,'research/operators/qwen_handoff/handoff.cpp','-o',str(BINARY.relative_to(ROOT))]
    p=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=180)
    if p.returncode:raise RuntimeError(p.stderr)
    sources=[HERE/'handoff.cpp',HERE/'lowering.h',HERE/'sha256.h',HERE/'fixtures.py',HERE/'run.py',HERE/'count.py',
             ROOT/'research/operators/qwen_deltanet/reference.py',ROOT/'research/operators/qwen_deltanet_lookup/lookup.h']
    receipt=dict(compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],flags=flags,
                 binary_sha256=digest(BINARY),sources={str(p.relative_to(ROOT)):digest(p) for p in sources},
                 warnings=p.stderr.replace(str(ROOT),'<REPO>'),started_utc=utc())
    write_new(EXP/'runs/build.json',receipt)
    print(json.dumps({'build':'ok','binary_sha256':receipt['binary_sha256']}),flush=True)

def one(seed,D,C,out,debug=False,end=None):
    s,parts=X.generate(seed,D,C)
    d=WORK/f'seed-{seed}'
    d.mkdir(parents=True,exist_ok=True)
    stmt=d/'verifier.stmt';stmt.write_bytes(X.statement_bytes(s))
    expected=counts(D,C)
    counted=command([BINARY,'count',stmt,'-','-'])
    for k in ['core_columns','aligned_columns','relations','range_cells']:
        assert expected[k]==counted[k],(k,expected[k],counted[k])
    rows=[]
    for name in ['honest',*X.CASES]:
        if end is not None and time.monotonic() >= end:
            raise TimeoutError('registered suite budget or lane hard stop')
        variant=parts if name=='honest' else X.hostile(name,s,parts)
        witness=d/name;X.write_parts(witness,variant)
        proof=witness/'joint.proof'
        r=command([BINARY,'prove' if name=='honest' else 'hostile',stmt,witness,proof])
        assert r['exit']==0 and r['products_hold'] and proof.stat().st_size==r['proof_bytes']
        # Separate process has no witness argument, no chain predicate or manifest.
        v=command([BINARY,'verify',stmt,'-',proof])
        row=dict(seed=seed,case=name,proof=r,verify=v,statement_sha256=digest(stmt),
                 proof_sha256=digest(proof),witness_sha256={f.name:digest(f) for f in sorted(witness.iterdir()) if f.suffix in ('.fx','.packet')})
        rows.append(row)
        print(json.dumps({'seed':seed,'case':name,'accept':v['accept'],'violations':r['violated_relations']}),flush=True)
        if out is not None:
            with out.open('a') as f:f.write(json.dumps(row)+'\n')
        if name=='honest':
            changed=copy.deepcopy(s);changed['layer']+=1
            replay=d/'changed-verifier.stmt';replay.write_bytes(X.statement_bytes(changed))
            rr=command([BINARY,'verify',replay,'-',proof])
            replay_row=dict(seed=seed,case='statement_replay_other_layer',verify=rr,
                            proof_sha256=digest(proof),statement_sha256=digest(replay))
            rows.append(replay_row)
            if out is not None:
                with out.open('a') as f:f.write(json.dumps(replay_row)+'\n')
    return rows,expected

def stats(xs):
    return dict(n=len(xs),median=statistics.median(xs),sd=statistics.stdev(xs) if len(xs)>1 else 0,min=min(xs),max=max(xs))

def suite():
    start=time.monotonic();started=utc()
    hard=datetime.datetime(2026,11,11,0,37,tzinfo=datetime.timezone.utc)
    remaining=(hard-datetime.datetime.now(datetime.timezone.utc)).total_seconds()
    # A later independent rerun uses the same 45-minute elapsed budget, not this lane's date.
    end=start+min(45*60,remaining) if EXP==ROOT/'experiments/20261110-93-handoff' else start+45*60
    out=EXP/'runs/suite.jsonl';out.parent.mkdir(exist_ok=True)
    with out.open('x'):pass
    rows=[];cnt=[]
    for seed in [101,102,103,104,105]:
        if time.monotonic()-start>45*60:raise TimeoutError('registered suite budget')
        rr,cc=one(seed,8,2,out,end=end);rows+=rr;cnt.append(cc)
    cases={name:stats([int(r['verify']['accept']) for r in rows if r['case']==name])
           for name in ['honest',*X.CASES,'statement_replay_other_layer']}
    honest=[r['proof'] for r in rows if r['case']=='honest']
    structures={k:stats([r[k] for r in honest]) for k in
                ['core_columns','aligned_columns','relations','relation_terms','range_cells','proof_bytes']}
    result=dict(started_utc=started,finished_utc=utc(),counts=cnt[0],case_acceptance=cases,structure=structures,
                honest_accepted=sum(r['verify']['accept'] for r in rows if r['case']=='honest'),
                hostile_rejected=sum(not r['verify']['accept'] for r in rows if r['case']!='honest'),
                hostile_cases=sum(r['case']!='honest' for r in rows),
                verdict='PASS' if all(r['verify']['accept']==(r['case']=='honest') for r in rows) else 'FAIL',
                note='Measured, unreplicated. Low research security. No timing claim. Split/drop/length attacks are fixed-slot witness encodings, not independently resumable variable-size proofs.')
    write_new(EXP/'runs/summary.json',result)
    write_new(EXP/'runs/counts.json',{'kind':'counted-not-built except D8 C2 cross-check',
                                   'rows':[counts(D,C) for D,C in [(8,2),(32,2),(128,2),(128,64)]]})
    cpu=next((l.split(':',1)[1].strip() for l in pathlib.Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name')),'unknown')
    env=dict(commits={'repo':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                      'base':'38523f9c6474465edda37613ebe7135b3d4acc4b','prereg':'9ff3e94'},
             toolchain={'python':platform.python_version(),'numpy':np.__version__,
                        'compiler':subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
                        'flags':['-std=c++17','-O2','-Wall','-Wextra','-fno-ipa-modref','-DBLK_FIELD=2','-DBLK_HASH=1']},
             hardware={'cpu':cpu,'affinity':sorted(os.sched_getaffinity(0)),'provider':'shared loaded CPU host',
                       'ram_bytes':os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES'),'gpu':'none','parallel_proof_processes':1},
             seeds=[101,102,103,104,105],security={'target_bits':10,'work_bits':6,'coins':'ToyCoins(100), deterministic, not production'},
             started_utc=started,finished_utc=utc(),binary_sha256=digest(BINARY))
    write_new(EXP/'ENV.json',env)
    print(json.dumps(result),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['build','debug','suite'])
    ap.add_argument('--out',type=pathlib.Path,help='Fresh receipt directory, e.g. research/operators/qwen_handoff/work/reproduction')
    a=ap.parse_args()
    if a.out is not None:EXP=a.out.resolve()
    if a.mode=='build':build()
    elif a.mode=='debug':
        one(909,4,1,None,True)
    else:suite()
