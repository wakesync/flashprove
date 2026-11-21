#!/usr/bin/env python3
"""Registered runs of experiments/20261121-229-qwen-m3a1-weight-side (PREREG.md): 5 honest proofs (prover seeds 1..5)
and every hostile (H1-H6) and completeness (C1-C3) case, on head 0's REAL table M.i32 built by prepare.py real.

Each case's output goes to its own file under runs/, written once (refuses to overwrite).
Usage: run_registered.py <qm3a1.bin> <M.i32> <runs_dir>
"""
import json, subprocess, sys, time
from pathlib import Path

CASES = ["H1-other-root-one-tap", "H1b-other-root-same-weights", "H2a-tap-changed-v-from-trace", "H2b-tap-changed-v-from-table",
         "H3-gain-2^50-trace-and-table", "H4-gain-in-class-not-the-tables", "H5-dt-2^17", "H6-table-row0-pad-nonzero",
         "C1-dt-78848", "C2-dt-minus-23424", "C3-dt-2^17-minus-1"]


def one(binary, M, args, out):
    if out.exists():
        raise SystemExit(f"refusing to overwrite {out.name}")
    t0 = time.time()
    r = subprocess.run(["taskset", "-c", "2-7", "/usr/bin/time", "-v", binary, M] + args, capture_output=True, text=True, timeout=1800)
    rss = [l for l in r.stderr.splitlines() if "Maximum resident set size" in l]
    rec = dict(args=args, exit=r.returncode, wall_s=round(time.time() - t0, 3), stdout=r.stdout.strip().splitlines(),
               max_rss_kb_time=int(rss[0].split()[-1]) if rss else None,
               stderr_tail=[l for l in r.stderr.splitlines() if "FAIL" in l])
    out.write_text(json.dumps(rec, indent=1) + "\n")
    last = json.loads(rec["stdout"][-1]) if rec["stdout"] else {}
    print(out.name, "exit", r.returncode, "accepted", last.get("accepted"), last.get("trace_why"), "|", last.get("lin_why"), flush=True)


def main():
    binary, M, runs = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    runs.mkdir(parents=True, exist_ok=True)
    for s in range(1, 6):
        one(binary, M, ["honest", str(s)], runs / f"honest-seed{s}.json")
    for c in CASES:
        one(binary, M, ["case", c], runs / f"case-{c.replace('^', '')}.json")


if __name__ == "__main__":
    main()
