#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run bounded CPU checks and record sanitized raw logs and artifact hashes."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'research/extensions/evidence'
out.mkdir(exist_ok=False)
commands=[['bash','verifier/build.sh'],[sys.executable,'research/extensions/test_harness.py'],[sys.executable,'research/extensions/harness.py','research/extensions/baseline-v1.json','--baseline']]
results=[]
for i,command in enumerate(commands):
    start=time.monotonic()
    p=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    elapsed=time.monotonic()-start
    text=p.stdout.replace(str(ROOT),'<REPO>').replace(str(Path.home()),'<HOME>')
    (out/f'{i}.log').write_text(text)
    results.append({'argv':command,'cwd':'<REPO>','exit':p.returncode,'seconds':elapsed,'last_line':text.splitlines()[-1] if text else ''})
    if p.returncode: break
files=['bin/cp_verify','research/extensions/harness.py','research/extensions/test_harness.py','research/extensions/baseline-v1.json','research/extensions/record.py','integrations/check_proof.py','docs/model.md','lean/IntegerModel/Model.lean','lean/THEOREM.md','examples/accepted-proof/example.proof','examples/accepted-proof/example.req','examples/accepted-proof/example.y']
files += [str(p.relative_to(ROOT)) for p in (ROOT/'examples/accepted-proof/config').iterdir() if p.is_file()]
files += [str(p.relative_to(ROOT)) for p in out.glob('*.log')]
hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
record={'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'upstream_commit':'9e2bdd8ff5bf9c62f18263d7dac189b0400b260c','environment':{'os':platform.system(),'release':platform.release(),'arch':platform.machine(),'python':platform.python_version(),'compiler':subprocess.check_output(['g++','--version'],text=True).splitlines()[0]},'dependencies':'Python stdlib; upstream verifier build prerequisites; no installs','seed':'none: deterministic metadata/mutations and stored upstream proof; verifier randomness unchanged','commands':results,'sha256':hashes}
(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(results,indent=2))
sys.exit(0 if all(r['exit']==0 for r in results) and len(results)==len(commands) else 1)
