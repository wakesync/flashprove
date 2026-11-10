#!/usr/bin/env python3
"""Regenerate rotary artifacts twice and check exact integer invariants."""
import hashlib
import json
import subprocess
import sys
from tables import HERE
from rotary_tables import load

outputs=[]
for _ in range(2):
    p=subprocess.run([sys.executable,str(HERE/'rotary_tables.py'),'--check'],check=True,capture_output=True,text=True)
    outputs.append(json.loads(p.stdout))
checked=0
for f in (12,14,16):
    S=1<<f;tab=load(f)
    assert len(tab)==65536
    for j in range(32):assert tab[2*j:2*j+2]==(S,0)
    assert all(abs(x)<=S for x in tab)
    for i in range(0,len(tab),2):
        C,U=tab[i:i+2]
        assert abs(C*C+U*U-S*S)<=2*S+1
        checked+=1
result=dict(regenerations=outputs,integer_pair_invariants_checked=checked,pass_all=True,
            manifest_sha256=hashlib.sha256((HERE/'tables/rotary-manifest.json').read_bytes()).hexdigest())
path=HERE.parents[2]/'experiments/20261109-35-qwen-operators/runs/rotary-table-checks.json'
path.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
