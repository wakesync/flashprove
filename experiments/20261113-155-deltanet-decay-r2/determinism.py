#!/usr/bin/env python3
"""Determinism check of PREREG.md "Runs": the registered evaluation run twice must give equal per-cell outputs
(decompressed bytes). usage: determinism.py <second_run_dir>   -> runs/determinism.json
The first run is the committed runs/eval; the second run's output stays in scratch."""
import gzip, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
A = HERE / "runs" / "eval"; B = Path(sys.argv[1]); out = {}
for n in ("cells.csv.gz", "heads.json.gz"):
    a = hashlib.sha256(gzip.decompress((A / n).read_bytes())).hexdigest(); b = hashlib.sha256(gzip.decompress((B / n).read_bytes())).hexdigest()
    out[n] = dict(run1_sha256_decompressed=a, run2_sha256_decompressed=b, equal=a == b)
out["equal"] = all(v["equal"] for v in out.values())
out["runs"] = [json.loads(l) for l in (HERE / "runs" / "progress.log.jsonl").read_text().splitlines()]
(HERE / "runs" / "determinism.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1))
sys.exit(0 if out["equal"] else 1)
