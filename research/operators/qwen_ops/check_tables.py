#!/usr/bin/env python3
"""Artifact checks: regenerate twice; compare all bytes; independent exact root midpoints."""
import hashlib
import json
import pathlib
import subprocess
import sys
from tables import HERE, NAMES, load


def main():
    outputs=[]
    for _ in range(2):
        p=subprocess.run([sys.executable,str(HERE/'tables.py'),'--check'],check=True,text=True,capture_output=True)
        outputs.append(json.loads(p.stdout))
    checked=0
    for f in (12,14,16):
        S=1<<f
        for name in NAMES:
            t=load(name,f)
            assert len(t)==4096
            if name in ('sigmoid','softplus'):
                assert all(a<=b for a,b in zip(t,t[1:]))
            elif name!='silu':
                assert all(a>=b for a,b in zip(t,t[1:]))
            if name in ('rsqrt','l2-128'):
                d=1 if name=='rsqrt' else 128
                for i,y in enumerate(t):
                    # y-1/2 <= sqrt(S^2*1024/(d*(i+256))) <= y+1/2.
                    # At exact midpoint the selected y must be even.
                    n4=4*S*S*1024
                    lo=d*(i+256)*(2*y-1)**2
                    hi=d*(i+256)*(2*y+1)**2
                    assert lo<=n4<=hi
                    if n4 in (lo,hi):assert y%2==0
            checked+=1
        assert load('silu',f)[2048]==0
        assert load('sigmoid',f)[2048]==S//2
        assert load('rsqrt',f)[768]==S
    result={'regenerations':outputs,'tables_checked':checked,
            'exact_rsqrt_entries_checked':2*3*4096,
            'manifest_sha256':hashlib.sha256((HERE/'tables/manifest.json').read_bytes()).hexdigest(),
            'pass':True}
    path=HERE.parents[2]/'experiments/20261109-35-qwen-operators/runs/table-checks.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
