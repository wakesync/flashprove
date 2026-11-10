#!/usr/bin/env python3
"""Cross-check actual C++ proof fixtures with independent Python integer lowering."""
import hashlib
import json
import subprocess
from tables import HERE, load
from rotary_tables import load as rotary_load
ROOT=HERE.parents[2]
REL=str(HERE.relative_to(ROOT))
exe=f'{REL}/work/crosscheck.bin'
subprocess.run(['g++','-std=c++17','-O2','-fno-ipa-modref','-DBLK_FIELD=2','-DBLK_HASH=1','-I','blocks',
                f'{REL}/reference_crosscheck.cpp','-o',exe],cwd=ROOT,check=True)
p=subprocess.run([exe],cwd=ROOT,check=True,text=True,capture_output=True)
records=[]
for line in p.stdout.splitlines():
    z=json.loads(line);f=z['F'];S=1<<f;x=z['x'];op=z['op']
    if op=='nonlinear':
        key=x[0]//(S//256)+2048
        y=[load(n,f)[key] for n in ('silu','sigmoid','softplus','decay-half','decay-one','decay-two')]
    elif op=='conv':
        y=[sum(x[t+j]*x[7+j] for j in range(4))//S for t in range(4)]
    elif op in ('l2','rms'):
        D=len(x);key=(1024*sum(v*v for v in x))//(D*S*S)-256
        coefficient=load('l2-128' if op=='l2' else 'rsqrt',f)[key]
        y=[v*coefficient//S for v in x]
    else:
        tab=rotary_load(f);y=x.copy();pos=z['position']
        for j in range(32):
            C,U=tab[64*pos+2*j:64*pos+2*j+2]
            y[j]=(x[j]*C-x[j+32]*U)//S
            y[j+32]=(x[j+32]*C+x[j]*U)//S
    assert y==z['y'],(op,f,z['seed'])
    records.append(dict(op=op,F=f,seed=z['seed'],output_words=len(y),equal=True,
                        fixture_sha256=hashlib.sha256(line.encode()).hexdigest()))
result=dict(cases=len(records),matched=sum(x['equal'] for x in records),
            output_words=sum(x['output_words'] for x in records),records=records,
            cpp_fixture_source_sha256=hashlib.sha256((HERE/'proof.cpp').read_bytes()).hexdigest())
(ROOT/'experiments/20261109-35-qwen-operators/runs/crosscheck.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'}))
