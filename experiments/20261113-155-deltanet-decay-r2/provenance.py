#!/usr/bin/env python3
"""Input rule of PREREG.md "Kill criterion": the recorded ar arrays are used only if (1) every file's sha256 is the
one listed in PREREG.md "Runs" and (2) PR #146's unchanged `decay_tables.py eval` on them reproduces PR #146's
committed `runs/eval/cells.csv.gz` and `runs/eval/domain.json.gz` (equal decompressed bytes).

usage: provenance.py <ar_dir> <scratch_out_dir>     -> runs/provenance.json (written whether the check passes or not)

This evaluates PR #146's arms T0..T3 only. No round-2 arm is touched here. Exit 0 iff both checks pass.
"""
import gzip, hashlib, json, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decay_r2 as R
SU = R.SU

COMMITTED = R.P146 / "runs" / "eval"


def gz_sha(p):
    return hashlib.sha256(gzip.decompress(Path(p).read_bytes())).hexdigest()


def main(ar_dir, out_dir):
    t0 = time.time(); out = dict(ok=False, sha256_all_equal=False, cells_equal=False, domain_equal=False, files=len(R.prereg_sha()))
    try:
        out["input_list_sha256"] = R.check_inputs(ar_dir); out["sha256_all_equal"] = True
    except SU.Incomplete as e:
        out["sha256_error"] = str(e)
    if out["sha256_all_equal"]:
        p = subprocess.run([sys.executable, str(R.P146 / "decay_tables.py"), "eval", str(ar_dir), str(out_dir)], capture_output=True, text=True)
        out["pr146_eval_exit"] = p.returncode
        if p.returncode == 0:
            for name, key in (("cells.csv.gz", "cells"), ("domain.json.gz", "domain")):
                a, b = gz_sha(Path(out_dir) / name), gz_sha(COMMITTED / name)
                out[key + "_sha256_decompressed"] = dict(recomputed=a, committed=b); out[key + "_equal"] = a == b
        else:
            out["pr146_eval_stderr_tail"] = p.stderr[-400:]
    out["ok"] = bool(out["sha256_all_equal"] and out["cells_equal"] and out["domain_equal"])
    out["seconds"] = round(time.time() - t0, 1)
    out["what"] = "PR #146's unchanged decay_tables.py eval (arms T0..T3) on the input files, compared with PR #146's committed runs/eval output"
    (HERE / "runs").mkdir(exist_ok=True)
    (HERE / "runs" / "provenance.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
