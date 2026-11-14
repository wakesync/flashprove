#!/usr/bin/env python3
"""Descriptive breakdown of runs/summary.json (public file, no token ids): every abl != served position with its
in-window flag and both margins; margins at separating positions; the first in-window abl != served position per prompt.
Written after the registered run and after its numbers were read (descriptive only, no bar; PREREG Amendment A-1).
Usage: describe177.py [runs/summary.json] [out.json]"""
import json, statistics, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
S = json.load(open(sys.argv[1] if len(sys.argv) > 1 else HERE / "runs" / "summary.json"))
out = dict(note="descriptive, after results; margins are top-1 minus top-2 logit of each float64 checkpoint; served-token logit gap not available (route gives no logprobs)",
           prompts={})
allmiss = []; allsep = []
for x in S["prompts"]:
    miss = [dict(j=p["j"], in_window=p["in_window"], abl_margin=p["abl_margin"], stock_margin=p["stock_margin"], stock_eq_served=p["stock_eq_served"],
                 D=p["D_kl_stock_abl"]) for p in x["positions"] if not p["abl_eq_served"]]
    sep = [p for p in x["positions"] if p["separating"]]
    first_sep = sep[0] if sep else None
    w = [p for p in x["positions"] if p["in_window"]]
    out["prompts"][x["id"]] = dict(
        abl_ne_served=miss, abl_ne_served_in_window=sum(m["in_window"] for m in miss),
        first_abl_ne_served_j=miss[0]["j"] if miss else None,
        separating_in_window=sum(p["separating"] for p in w),
        clean_prefix_len=next((p["j"] for p in x["positions"] if not p["abl_eq_served"]), x["n_reply"]),
        separating_in_clean_prefix=sum(p["separating"] for p in x["positions"][:next((p["j"] for p in x["positions"] if not p["abl_eq_served"]), x["n_reply"])]),
        first_separating=dict(j=first_sep["j"], D=first_sep["D_kl_stock_abl"], stock_margin=first_sep["stock_margin"], abl_margin=first_sep["abl_margin"]) if first_sep else None)
    allmiss += miss; allsep += sep
am = [m["abl_margin"] for m in allmiss]
out["abl_ne_served_total"] = len(allmiss)
out["abl_ne_served_in_window_total"] = sum(m["in_window"] for m in allmiss)
out["abl_ne_served_abl_margin"] = dict(median=statistics.median(am), min=min(am), max=max(am)) if am else None
out["abl_ne_served_abl_margin_lt_1"] = sum(a < 1.0 for a in am)
out["separating_D"] = dict(n=len(allsep), median=statistics.median([p["D_kl_stock_abl"] for p in allsep]),
                           min=min(p["D_kl_stock_abl"] for p in allsep), max=max(p["D_kl_stock_abl"] for p in allsep)) if allsep else None
out["separating_stock_margin"] = dict(median=statistics.median([p["stock_margin"] for p in allsep]),
                                      min=min(p["stock_margin"] for p in allsep), max=max(p["stock_margin"] for p in allsep)) if allsep else None
txt = json.dumps(out, indent=1) + "\n"
if len(sys.argv) > 2: Path(sys.argv[2]).write_text(txt)
print(txt)
