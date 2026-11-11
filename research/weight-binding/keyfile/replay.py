#!/usr/bin/env python3
"""Read saved keys in fresh verifier processes, never trusting their header IDs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
p=argparse.ArgumentParser();p.add_argument('--runs',type=Path,required=True);p.add_argument('--binary',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
rows=[]
for path in sorted(a.runs.glob('seed-*/results.json')):
    receipt=json.loads(path.read_text());seed=receipt['seed']
    for record in receipt['records']:
        arm=record['arm'];key=path.parent/(arm+'.key')
        profile='other' if arm in {'other-checkpoint-honest-control','manifest-root-other-checkpoint'} else 'conversion' if arm in {'conversion-id-honest-control','conversion-id-mismatch'} else 'original'
        kind='legacy' if 'legacy' in arm else 'bound'
        run=subprocess.run([str(a.binary.resolve()),'verify',str(key.resolve()),str(seed),profile,kind],capture_output=True,text=True,timeout=30)
        decision=json.loads(run.stdout)
        passed=run.returncode==(0 if record['expected'] else 1) and decision['accepted']==record['expected'] and decision['native_attempted'] and decision['native_accepted']==record['expected']
        rows.append(dict(seed=seed,arm=arm,sha256=hashlib.sha256(key.read_bytes()).hexdigest(),exit=run.returncode,decision=decision,passed=bool(passed)))
result=dict(verdict='PASS' if rows and all(r['passed'] for r in rows) else 'FAIL',rows=rows)
with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
print(result['verdict'],len(rows),'saved-key decisions')
raise SystemExit(0 if result['verdict']=='PASS' else 1)
