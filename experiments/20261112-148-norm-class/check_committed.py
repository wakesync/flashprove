#!/usr/bin/env python3
"""Review round 1 receipt: run the fixed summarise.py on a copy of the committed run files (runs/baseline.jsonl,
runs/arms.jsonl, runs/progress.log.jsonl, unchanged since the run commit d68c3e1e) and check that summary.json and
summary.md come out byte-identical to the committed ones. Writes nothing in runs/. Exit 0 iff both are identical.
Usage: check_committed.py [out.json]"""
import hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent; R = HERE / "runs"
sha = lambda b: hashlib.sha256(b).hexdigest()
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    for f in ("baseline.jsonl", "arms.jsonl", "progress.log.jsonl"): shutil.copyfile(R / f, d / f)
    p = subprocess.run([sys.executable, str(HERE / "summarise.py"), str(d)], capture_output=True, text=True)
    o = dict(summarise_rc=p.returncode, inputs={f: sha((R / f).read_bytes()) for f in ("baseline.jsonl", "arms.jsonl", "progress.log.jsonl")})
    for f in ("summary.json", "summary.md"):
        new = (d / f).read_bytes() if (d / f).exists() else b""
        o[f] = dict(committed_sha256=sha((R / f).read_bytes()), regenerated_sha256=sha(new), byte_identical=new == (R / f).read_bytes())
o["ok"] = bool(o["summarise_rc"] == 0 and o["summary.json"]["byte_identical"] and o["summary.md"]["byte_identical"])
s = json.dumps(o, indent=1) + "\n"
if len(sys.argv) > 1: Path(sys.argv[1]).write_text(s)
print(s, end="")
sys.exit(0 if o["ok"] else 1)
