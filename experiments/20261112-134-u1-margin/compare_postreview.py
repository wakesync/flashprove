#!/usr/bin/env python3
"""Receipt: does the post-review analyse.py, run on the committed inputs, reproduce the committed analysis?

Compares postreview/analysis.json (written by `python3 analyse.py runs postreview` with the script as changed after
review, PREREG Amendment A-2) with runs/analysis.json (written by the script as committed for the registered run).
Reads both, writes postreview/reproduction.json. Light, no weights, no model forward.

Usage: python3 compare_postreview.py     exit 0 iff the two files are byte-identical and the headline numbers match."""
import hashlib, json, platform, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; OLD = HERE / "runs" / "analysis.json"; NEW = HERE / "postreview" / "analysis.json"

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def head(a):
    x = a["pooled"]["XS18"]; y = a["pooled"]["XS20"]; n = x["n"]
    return dict(verdict=a["verdict"], gates_all_ok=a["gates"]["all_ok"], positions=n,
                xs18_count_gt10=round(x["share_gt10"] * n), xs18_share_gt10=x["share_gt10"],
                xs18_count_gt100=round(x["share_gt100"] * n), xs18_share_gt100=x["share_gt100"],
                xs18_prompts_share10_ge_090=x["prompts_share10_ge_090"], xs18_log10r=x["log10r"],
                xs20_share_gt10=y["share_gt10"], xs20_share_gt100=y["share_gt100"], xs20_prompts_share10_ge_090=y["prompts_share10_ge_090"],
                D=a["pooled"]["D"], E_XS18=a["pooled"]["E_XS18"], top1_differ=a["pooled"]["top1_differ"],
                per_prompt_xs18={p: [v["XS18"]["share_gt10"], v["XS18"]["share_gt100"]] for p, v in a["prompts"].items()})

def main():
    old, new = json.loads(OLD.read_text()), json.loads(NEW.read_text())
    same_bytes = OLD.read_bytes() == NEW.read_bytes(); same_head = head(old) == head(new)
    val = json.loads((HERE / "postreview" / "input-validation.json").read_text())
    out = dict(what="post-review analyse.py on the committed inputs vs the committed analysis of the registered run; no rerun of the model",
               committed_runs_analysis_sha256=sha(OLD), postreview_analysis_sha256=sha(NEW), byte_identical=same_bytes,
               analyse_py_sha256=sha(HERE / "analyse.py"), toolchain=dict(python=platform.python_version(), numpy=np.__version__),
               headline_equal=same_head, headline=head(new),
               input_validation=dict(tier=val["tier"], positions=val["positions"], tensor_coverage=val["tensor_coverage"],
                                     E_nonpositive_positions=val["E_nonpositive_positions"], exit_code=val["exit_code"]),
               ok=bool(same_bytes and same_head and val["exit_code"] == 0))
    (HERE / "postreview" / "reproduction.json").write_text(json.dumps(out, indent=1) + "\n")
    print("byte-identical:", same_bytes, "| headline equal:", same_head, "| sha256", out["postreview_analysis_sha256"])
    h = out["headline"]
    print("verdict", h["verdict"]["verdict"], "| D > 10E", h["xs18_count_gt10"], "/", h["positions"], "| D > 100E", h["xs18_count_gt100"], "/", h["positions"],
          "| prompts", h["xs18_prompts_share10_ge_090"], "of", h["verdict"]["prompts_run"])
    sys.exit(0 if out["ok"] else 1)

if __name__ == "__main__": main()
