#!/usr/bin/env python3
"""Descriptive local safetensors availability check. Never reads the network."""
import argparse
import datetime
import json
import os
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,action='append',required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args()
roots=[]
for i,root in enumerate(a.root):
    found=[]
    errors=[]
    def error(e):
        errors.append(type(e).__name__)
    if root.exists():
        for base,dirs,files in os.walk(root,onerror=error,followlinks=False):
            dirs[:]=[d for d in dirs if d not in {'.git','node_modules','.lake','target','.venv'}]
            for f in files:
                if f.endswith('.safetensors'):
                    q=Path(base)/f
                    found.append(dict(basename=f,bytes=q.stat().st_size,
                                      stock_pin_in_path='37561816' in str(q),huihui_pin_in_path='739e3c5b' in str(q)))
    roots.append(dict(search_root_index=i,exists=root.exists(),safetensors=found,errors=errors))
candidates=any(r['safetensors'] for r in roots)
result=dict(kind='descriptive-cache-probe',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            searched_labels=['lane-projects','standard-user-cache','legacy-hf-cache','user-models'][:len(roots)],roots=roots,
            roots_computed=False,verdict='NOT DONE',
            reason=('Local safetensors candidates require manual pin/completeness inspection.' if candidates else 'No safetensors files were found in the searched local weight/cache directories. No weight download and no recomputation from old hash receipts.'),
            pins={'stock':'37561816','huihui':'739e3c5b'},network_used=False)
with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps(result,indent=2))
