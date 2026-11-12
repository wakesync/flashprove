#!/usr/bin/env python3
"""Post hoc cross-check (not registered): this run's stock XS18 and BF16H logit metrics on PR #88's 4 end-to-end prompts
vs PR #88's committed runs/e2e-stock.json (same arm, same code, different batching and BLAS scheduling). Writes
runs/xcheck-pr88.json."""
import json
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
old = json.load(open(HERE.parent / "20261110-8-qwen-q1-deep-fidelity" / "runs" / "e2e-stock.json"))["prompts"]
new = json.load(open(HERE / "runs" / "e2e-stock.json"))["prompts"]
out = {}
for pid, o in old.items():
    n = new[pid]; d = dict(ref_top1_equal=o["ref_top1"] == n["ref_top1"])
    for po, pn in (("INT", "XS18"), ("BF16H", "BF16H")):
        a, b = o[po], n["paths"][pn]
        ka, kb = np.array(a["kl"]), np.array(b["kl"])
        d[pn] = dict(top1_equal=a["top1_path"] == b["top1_path"], kl_max_absdiff=float(np.abs(ka - kb).max()),
                     kl_max_reldiff=float((np.abs(ka - kb) / np.maximum(ka, 1e-300)).max()))
    out[pid] = d
(HERE / "runs" / "xcheck-pr88.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1))
