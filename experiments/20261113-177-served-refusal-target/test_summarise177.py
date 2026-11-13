#!/usr/bin/env python3
"""Synthetic test of summarise177.py (no weights, no suite data; written and run before the registered forward finished).
Builds two fake refusal-type prompts and one control with known flags and checks counts, window, stop rule, target
selection with tie to lowest id, verdict logic and that the public output carries no token ids for refusal-type prompts.
Usage: test_summarise177.py [out.json]"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import summarise177 as S

def mk(pid, kind, npr, reply, finish, stock_reply, abl_reply):
    T = npr + len(reply) - 1
    st = [7] * T; ab = [7] * T
    for j in range(len(reply)):
        st[npr - 1 + j] = stock_reply[j]; ab[npr - 1 + j] = abl_reply[j]
    q = dict(id=pid, kind=kind, included=True, n_prompt=npr, n_reply=len(reply), finish_reason=finish, prompt_ids=list(range(npr)),
             reply_ids=reply, reply_ids_sha256="x" + pid, content_sha256="c" + pid, refusal_rule=dict(is_refusal=False, markers_matched=[]))
    seq = dict(n_prompt=npr, n_reply=len(reply), input_ids=list(range(npr)) + reply[:-1], reply_ids=reply)
    r = dict(T=T, stock_top1=st, abl_top1=ab, stock_margin=[1.0] * T, abl_margin=[2.0] * T, D_kl_stock_abl=[0.1] * T, kl_abl_stock=[0.2] * T)
    return q, seq, r

def build(cases):
    ids = dict(prompts=[]); fw = dict(sequences={}, prompts={})
    for c in cases:
        q, s, r = mk(*c); ids["prompts"].append(q); fw["sequences"][q["id"]] = s; fw["prompts"][q["id"]] = r
    return fw, ids

def main():
    res = {}
    # rA: 62 prompt, 4 reply -> reply tokens at seq 62,63 in window, 64,65 out. stock wrong at j=0 and j=3, abl right.
    # rB: 60 prompt, 4 reply -> all 4 in window, stock wrong at j=1 only... then tie test below.
    # c: stop position, stock picks 248044 (counts as served), abl picks 248046.
    fw, ids = build([("rB", "refusal-type", 60, [11, 12, 13, 14], "length", [11, 99, 13, 14], [11, 12, 13, 14]),
                     ("rA", "refusal-type", 62, [21, 22, 23, 24], "length", [98, 22, 23, 97], [21, 22, 23, 24]),
                     ("c1", "control", 5, [31, 248046], "stop", [31, 248044], [31, 248046])])
    s = S.summarise(fw, ids); P = {x["id"]: x for x in s["prompts"]}
    res["rA_window"] = P["rA"]["window"]["n"] == 2 and P["rA"]["window"]["stock_ne_served"] == 1 and P["rA"]["all"]["stock_ne_served"] == 2
    res["rB_window"] = P["rB"]["window"]["n"] == 4 and P["rB"]["window"]["stock_ne_served"] == 1 and P["rB"]["first_stock_ne_served_j"] == 1
    res["stop_rule"] = P["c1"]["all"]["stock_ne_served"] == 0 and P["c1"]["all"]["abl_eq_served"] == 2
    res["tie_lowest_id"] = s["target"]["id"] == "rA"          # both have 1 in-window stock!=served; "rA" < "rB"
    res["verdict_pass"] = s["verdict"] == "PASS" and s["H0"]["share"] == 1.0
    pub = S.public(s)
    res["public_no_ids_refusal"] = all(not any(k in p for k in ("_stock_top1", "_abl_top1", "_served", "stock_top1", "abl_top1", "served_id"))
                                       for x in pub["prompts"] if x["kind"] == "refusal-type" for p in x["positions"])
    res["public_ids_control"] = all("stock_top1" in p for x in pub["prompts"] if x["kind"] == "control" for p in x["positions"])
    # negative: stock right everywhere
    fw2, ids2 = build([("rA", "refusal-type", 30, [1, 2, 3], "length", [1, 2, 3], [1, 2, 3])])
    s2 = S.summarise(fw2, ids2); res["verdict_fail_no_target"] = s2["verdict"] == "FAIL" and s2["target"] is None
    # abl wrong a lot -> broken
    fw3, ids3 = build([("rA", "refusal-type", 30, [1, 2, 3, 4, 5], "length", [9, 9, 9, 9, 9], [1, 9, 9, 9, 9])])
    s3 = S.summarise(fw3, ids3); res["verdict_broken"] = s3["verdict"] == "BROKEN"
    # 80..98 -> target in question
    fw4, ids4 = build([("rA", "refusal-type", 30, list(range(1, 11)), "length", [99] + list(range(2, 11)), [1, 2, 3, 4, 5, 6, 7, 8, 9, 99])])
    s4 = S.summarise(fw4, ids4); res["verdict_in_question"] = s4["verdict"] == "FAIL (target in question)"
    # shape mismatch is refused
    fw5, ids5 = build([("rA", "refusal-type", 30, [1, 2, 3], "length", [1, 2, 3], [1, 2, 3])]); fw5["prompts"]["rA"]["abl_top1"].pop()
    try: S.summarise(fw5, ids5); res["refuses_short_array"] = False
    except AssertionError: res["refuses_short_array"] = True
    res["all_ok"] = all(res.values())
    print(json.dumps(res, indent=1))
    if len(sys.argv) > 1: Path(sys.argv[1]).write_text(json.dumps(res, indent=1) + "\n")
    sys.exit(0 if res["all_ok"] else 1)

if __name__ == "__main__": main()
