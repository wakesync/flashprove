#!/usr/bin/env python3
"""Post-review recheck (PREREG Amendments, 2026-11-11): signed range of o for the X-family rows that sit on the class edge.

The registered class for the X family is o in [-2^17, 2^17) (PREREG "Stated honest classes"). The committed rows record
only max |o| (scaled_head `max["o"]`), and summarise_q1.py used PR #74's `summarise.bounds("X1")`, o < 2^17 + 1 on max |o|,
which admits o = +2^17. A row is decided by max |o| alone unless max |o| == 2^17 exactly; for those rows this script
reruns `scaled_head.Head` (PR #74, unchanged) on the run's prep files (head inputs) and records the signed max and min of
o for the row's head. It also records, as a consistency check, whether the rerun's max |o| equals the committed value.

Writes runs/o-sign-recheck.jsonl (a new file; no committed run file is changed).
Usage: recheck_o_sign.py <scratch>   (scratch = the run's scratch dir with prep-L16/, prep-L20/, prep-abl-L20/)"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "20261110-8-qwen-norm-scaling"))
import scaled_head as SH  # PR #74 engine, unchanged
TG = {"T16": ("prep-L16", "stock-L16"), "T20s": ("prep-L20", "stock-L20"), "T20a": ("prep-abl-L20", "abl-L20")}
EDGE = 2 ** 17

def main():
    scratch = Path(sys.argv[1]); arms = json.load(open(HERE / "arms-q1.json"))
    rows = []
    over = 0
    for tg in TG:
        for l in open(HERE / "runs" / f"arms-{tg}.jsonl"):
            r = json.loads(l)
            if not r["arm"].startswith("XS") or "error" in r: continue
            o = r["max"].get("o", 0)
            if o > EDGE: over += 1
            if o == EDGE: rows.append((tg, r["arm"], r["prompt"], r["head"]))
    print("X-family rows with max |o| == 2^17:", len(rows), "| with max |o| > 2^17:", over, flush=True)
    cache = {}
    out = []
    for tg, arm, pid, head in rows:
        key = (tg, arm, pid)
        if key not in cache:
            pd, lb = TG[tg]
            d = np.load(scratch / pd / f"prep-{lb}-{pid}.npz")
            hd = tuple(d[k] for k in ("xq", "xk", "xv", "ar", "br", "zz", "Wc", "A", "dtb", "gain"))
            omax = omin = None
            for S, o, y, Fo in SH.Head(arms[arm]["cfg"]).run(*hd, {}):
                a, b = o.max(axis=1), o.min(axis=1)
                omax = a if omax is None else np.maximum(omax, a)
                omin = b if omin is None else np.minimum(omin, b)
            cache[key] = (omax, omin)
        omax, omin = cache[key]
        hi, lo = float(omax[head]), float(omin[head])
        out.append(dict(target=tg, arm=arm, prompt=pid, head=head, o_max=hi, o_min=lo,
                        abs_max_matches_committed=bool(max(abs(hi), abs(lo)) == EDGE),
                        in_prereg_class=bool(lo >= -EDGE and hi < EDGE)))
        print(json.dumps(out[-1]), flush=True)
    with open(HERE / "runs" / "o-sign-recheck.jsonl", "w") as f:
        for r in out: f.write(json.dumps(r) + "\n")
    print("out of class:", sum(not r["in_prereg_class"] for r in out), "of", len(out))

if __name__ == "__main__": main()
