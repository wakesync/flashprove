#!/usr/bin/env python3
"""Descriptive only (added after the run, not a registered metric): for each served-vs-REF disagreement, decode the
served token and REF's pick, and check whether REF's pick is still a prefix of the remaining served text. If it is, the
served text is consistent with REF's pick followed by a different segmentation of the rest: the re-tokenised id differs
but the text could be the same (a tokenisation ambiguity of rebuilding ids from text, which counts cannot detect).
Usage: disagreement_text.py <dir with pinned tokenizer.json + chat_template.jinja>  -> runs/disagreement-text.json"""
import json, sys
from pathlib import Path
import rebuild_ids as RB
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
tk, _ = RB.load(sys.argv[1])
S = json.load(open(R / "summary.json")); ids = {q["id"]: q for q in json.load(open(R / "served-ids.json"))["prompts"]}
out = []
for d in S["disagreement_positions"]:
    q = ids[d["id"]]; rids = q["reply_ids"]; k = d["reply_pos"]
    before = tk.decode(rids[:k], skip_special_tokens=False); full = q["served_content"]
    rest = full[len(before):] if full.startswith(before) else None
    ref_s = tk.decode([d["REF"]], skip_special_tokens=False); srv_s = tk.decode([d["served"]], skip_special_tokens=False)
    out.append(dict(id=d["id"], reply_pos=k, served_id=d["served"], served_text=srv_s, ref_id=d["REF"], ref_text=ref_s,
                    ref_margin=d["ref_top2_margin"], context_tail=before[-40:], rest_head=(rest or "")[:40],
                    ref_pick_is_prefix_of_served_rest=bool(rest is not None and rest.startswith(ref_s)),
                    canonical_reencode_of_rest_starts_with_served=(tk.encode(rest, add_special_tokens=False).ids[:1] == [d["served"]]) if rest else None))
(R / "disagreement-text.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
for o in out: print(json.dumps(o, ensure_ascii=False))
