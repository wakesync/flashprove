#!/usr/bin/env python3
"""Bookkeeping receipts written after the registered run (no arm is evaluated on a registered array here).

usage: receipts.py fine20 <fine20.npy>    -> runs/fine20.json   (the 2^20-row fine exp table: sha256, every row vs
                                             float64 RNE, a 10,001-row sample regenerated with the integer generator)
       receipts.py tests <fine20.npy>     -> runs/test_r2.json  (test_r2.py run in a child process: counts, exit code)
"""
import json, os, re, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decay_r2 as R


def fine20(path):
    t = np.load(path); n = 1 << 20
    fl = np.rint(np.ldexp(np.exp(-np.arange(n) / n), 20)).astype(np.int64)
    ks = sorted(set(np.linspace(0, n - 1, 10001).astype(int).tolist()))
    bad = sum(int(t[k]) != R.fine_row(k) for k in ks)
    meta = json.loads((HERE / "runs" / "eval" / "eval-meta.json").read_text())
    out = dict(rows=int(t.shape[0]), sha256_int64_le=R.table_sha(t), equals_table_used_by_registered_run=R.table_sha(t) == meta["tables_sha256"]["fine_exp_f20"],
               rows_differing_from_float64_rne=int((t != fl).sum()), sample_rows_regenerated_with_integer_generator=len(ks), sample_mismatches=bad,
               generator="decay_r2.py fine20: research/operators/qwen_ops/tables.py expq / nearest, all 2^20 rows")
    (HERE / "runs" / "fine20.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1))
    return 0 if (bad == 0 and out["equals_table_used_by_registered_run"]) else 1


def tests(path):
    p = subprocess.run([sys.executable, str(HERE / "test_r2.py")], capture_output=True, text=True, env=dict(os.environ, R2_FINE20=str(path)), cwd=str(HERE))
    m = re.search(r"Ran (\d+) tests? in", p.stderr); last = [l for l in p.stderr.strip().splitlines() if l.strip()][-1]
    head = subprocess.run(["git", "-C", str(HERE), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(HERE), "status", "--porcelain", "--", "test_r2.py", "decay_r2.py", "summarise_r2.py"], capture_output=True, text=True).stdout.strip()
    out = dict(command="R2_FINE20=<fine20.npy> python3 test_r2.py", exit=p.returncode, tests_run=int(m.group(1)) if m else None, last_line=last,
               repo_head_at_run=head, test_or_arm_code_uncommitted_at_run=bool(dirty),
               data="synthetic heads only (numpy seed 155) and fabricated per-cell rows; no registered activation array is read")
    (HERE / "runs" / "test_r2.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1))
    return p.returncode


if __name__ == "__main__":
    sys.exit(fine20(sys.argv[2]) if sys.argv[1] == "fine20" else tests(sys.argv[2]))
