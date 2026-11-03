#!/usr/bin/env python3
"""Record integrated research checks without replacing earlier lane evidence."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/integration/evidence'
OUT.mkdir(exist_ok=False)
def scrub(s):
    for p, replacement in [(str(ROOT), '<REPO>'), (str(Path.home()), '<HOME>')]:
        s = s.replace(p, replacement)
    return s
commands = [
    ['git','diff','--exit-code','9e2bdd8ff5bf9c62f18263d7dac189b0400b260c','--','.',':(exclude)research'],
    ['python3','research/extensions/test_harness.py'],
    ['python3','research/extensions/harness.py','research/extensions/baseline-v1.json','--baseline'],
    ['python3','research/reproduction/audit_cases.py','research/integration/audit'],
    ['sha256sum','-c','research/reproduction/REVIEW-SHA256SUMS'],
]
results=[]
for i, command in enumerate(commands):
    start=time.monotonic()
    p=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    text=scrub(p.stdout)
    (OUT/f'{i}.log').write_text(text)
    results.append(dict(argv=command,exit=p.returncode,seconds=time.monotonic()-start,last_line=text.rstrip().split('\n')[-1]))
files=['bin/cp_verify','research/extensions/harness.py','research/extensions/test_harness.py','research/extensions/baseline-v1.json','research/reproduction/audit_cases.py','research/integration/record.py']
files += [str(p.relative_to(ROOT)) for folder in [OUT,ROOT/'research/integration/audit'] for p in folder.glob('*') if p.is_file()]
record=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),environment=dict(kernel=platform.release(),python=platform.python_version(),arch=platform.machine(),compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0]),seed='deterministic stored fixtures and mutations; no new model proof',commands=results,sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files})
(OUT/'results.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(results,indent=2))
sys.exit(int(any(r['exit'] for r in results)))
