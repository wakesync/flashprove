#!/usr/bin/env python3
"""Descriptive (PREREG: "which one it picks is reported"): at every stop position, the end id each path picked.
-> runs/stop-ids.json"""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
FW = json.load(open(R / "forward.json")); S = json.load(open(R / "served-ids.json"))
out = []
for q in S["prompts"]:
    if not q["included"] or q["finish_reason"] != "stop": continue
    f = FW["prompts"][q["id"]]; t = len(q["prompt_ids"]) - 1 + len(q["reply_ids"]) - 1
    out.append(dict(id=q["id"], input_pos=t, REF=f["ref_top1"][t], XS18=f["paths"]["XS18"]["top1_path"][t],
                    XS20=f["paths"]["XS20"]["top1_path"][t], ref_top2_margin=f["ref_margin"][t]))
(R / "stop-ids.json").write_text(json.dumps(out, indent=1) + "\n")
for o in out: print(o)
