#!/usr/bin/env python3
"""Determinism check (A vs B) and the verdict against the PREREG bars. Writes runs/summary.json.
Usage: summarise.py <runs dir>"""
import json, os, sys
import numpy as np


def main():
    d = sys.argv[1]
    A = json.load(open(os.path.join(d, "result-A.json")))
    B = json.load(open(os.path.join(d, "result-B.json")))
    strip = lambda r: {k: v for k, v in r.items() if k not in ("tag", "seconds")}
    det_hashes = A["hashes"] == B["hashes"]
    det_all = strip(A) == strip(B)
    P = A["pooled"]
    b1 = P["rel_y_median_over_prompts"] <= 1e-2 and P["rel_y_max_over_prompts"] <= 5e-2
    b2 = P["set_diff_frac"] <= 0.01
    rng = A["ranges"]
    out_of_bound = {k: v for k, v in rng.items()
                    if k in ("m_clamp", "ly_clamp", "ly_cond5", "sig_out", "gh_clamp", "gh_cond6", "keyA_dom",
                             "uh_clamp", "uh_cond6", "keyB_dom", "uw_cond7") and v}
    fl = A["flips"]
    gf = np.array([f["gap_float"] for f in fl])
    gi = np.array([f["gap_int"] for f in fl])
    nd = np.array([f["n_differ"] for f in fl])
    s = dict(determinism=dict(hashes_equal=det_hashes, all_fields_equal_except_time=det_all),
             B1=dict(median=P["rel_y_median_over_prompts"], max=P["rel_y_max_over_prompts"],
                     min=P["rel_y_min_over_prompts"], bar="median<=1e-2 and max<=5e-2", verdict="PASS" if b1 else "FAIL"),
             B2=dict(set_diff_tokens=P["set_diff_tokens"], n_tokens=A["n_tokens"], frac=P["set_diff_frac"],
                     bar="<=0.01", verdict="PASS" if b2 else "FAIL"),
             B3=dict(verdict="IN-BOUND" if not out_of_bound else "OUT-OF-BOUND", nonzero=out_of_bound),
             overall=("PASS" if (b1 and b2 and det_hashes) else "FAIL"),
             flips=dict(n=len(fl), n_differ_counts={int(k): int((nd == k).sum()) for k in np.unique(nd)} if len(fl) else {},
                        gap_float_median=float(np.median(gf)) if len(fl) else None,
                        gap_float_max=float(gf.max()) if len(fl) else None,
                        gap_float_p90=float(np.quantile(gf, 0.9)) if len(fl) else None),
             descriptive=dict(rel_y_pooled=P["rel_y"], rel_y_attr_pooled=P["rel_y_attr"],
                              rel_y_sets_agree_per_prompt={p["id"]: p["rel_y_sets_agree"] for p in A["prompts"]},
                              rel_y_attr_per_prompt={p["id"]: p["rel_y_attr"] for p in A["prompts"]}),
             seconds=dict(A=A["seconds"], B=B["seconds"]))
    json.dump(s, open(os.path.join(d, "summary.json"), "w"), indent=1)
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
