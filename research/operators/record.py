"""Reproduce scoped operator evidence; no private machine identifiers in receipt."""
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

from topk import build

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE/'evidence'
OUT.mkdir(exist_ok=True)
start = time.monotonic()
p = subprocess.run([sys.executable, 'research/operators/test_topk.py'], cwd=ROOT, capture_output=True, text=True)
log = p.stdout+p.stderr
(OUT/'tests.log').write_text(log)
c = build([10, 20, 30, 40], [127, 0, -128, 0], 3)
c.export(OUT/'honest.constraints')
paths = [HERE/n for n in ['topk.py', 'check.cpp', 'test_topk.py', 'record.py', 'README.md']]
paths += [ROOT/'blocks/field/field.h', ROOT/'blocks/field/gl64.h', OUT/'tests.log', OUT/'honest.constraints']
result = {
    'base_commit': '604b259df77f85bb07f13739336e536e717e7157',
    'source_head_at_execution': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'command': 'python3 research/operators/test_topk.py',
    'python': platform.python_version(), 'platform': platform.system()+' '+platform.machine(),
    'compiler': subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
    'seed': 530042, 'exit_code': p.returncode, 'last_line': log.rstrip().splitlines()[-1],
    'elapsed_seconds': time.monotonic()-start,
    'example': {'wires': len(c.values), 'constraints': len(c.rows), 'public_wires': len(c.public)},
    'cryptographic_proof_coverage': 'NONE; disclosed witness constraint satisfaction only',
    'hashes': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in paths},
}
(OUT/'results.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
raise SystemExit(p.returncode)
