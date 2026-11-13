#!/usr/bin/env python3
"""Bars, per-prompt table and the registered target (PREREG "Metric", "Target-selection rule", "Acceptance threshold").

Inputs (private, lane scratch): forward output of forward177.py and served-ids-private.json from rebuild177.py.
Outputs:
  <public_summary.json>, <public_summary.md>  committed: per reply position flags (abl==served, stock==served), KL both
      ways, both margins; per prompt counts, shares, first stock!=served position, window counts, refusal-rule outcome,
      sha256 of reply ids; bars and the target. For refusal-type prompts NO token ids at reply positions (top-1 ids would
      reveal the reply). Control prompts also get their top-1 ids.
  <private_detail.json>  scratch only: everything incl. top-1 ids.
Optional: --pr133 <forward.json> <served-ids.json> compares c01/c02 abl top-1 with PR #133's REF top-1 for q01/q02 when
the input ids are identical (descriptive).

Position convention: sequence = prompt ids + reply ids[:-1] (T = n_prompt + n_reply - 1). Logits at sequence index
n_prompt - 1 + j predict reply token j, which sits at sequence index n_prompt + j; it is inside the 64-token window iff
n_prompt + j < 64. At a stop position (finish "stop", last reply token) a checkpoint picks the served token iff its top-1
is 248046 or 248044 (PR #133 rule).

Usage: summarise177.py <forward-private.json> <served-ids-private.json> <out_dir_public> <private_detail.json>
           [--pr133 <forward.json> <served-ids.json>]"""
import json, statistics, sys
from pathlib import Path

STOP_SET = {248046, 248044}
WINDOW = 64

def per_prompt(q, fw):
    pid = q["id"]; s = fw["sequences"][pid]; r = fw["prompts"][pid]
    npr, nre = q["n_prompt"], q["n_reply"]
    assert s["n_prompt"] == npr and s["n_reply"] == nre and r["T"] == npr + nre - 1, pid
    assert s["reply_ids"] == q["reply_ids"] and s["input_ids"] == q["prompt_ids"] + q["reply_ids"][:-1], pid
    for k in ("stock_top1", "abl_top1", "stock_margin", "abl_margin", "D_kl_stock_abl", "kl_abl_stock"):
        assert len(r[k]) == r["T"], (pid, k)
    pos = []
    for j in range(nre):
        t = npr - 1 + j; served = q["reply_ids"][j]
        stop = q["finish_reason"] == "stop" and j == nre - 1
        st, ab = r["stock_top1"][t], r["abl_top1"][t]
        st_ok = (st in STOP_SET) if stop else st == served
        ab_ok = (ab in STOP_SET) if stop else ab == served
        pos.append(dict(j=j, seq_index_of_token=npr + j, in_window=npr + j < WINDOW, stop_position=stop,
                        abl_eq_served=ab_ok, stock_eq_served=st_ok, separating=(not st_ok) and ab_ok,
                        D_kl_stock_abl=r["D_kl_stock_abl"][t], kl_abl_stock=r["kl_abl_stock"][t],
                        stock_margin=r["stock_margin"][t], abl_margin=r["abl_margin"][t],
                        _stock_top1=st, _abl_top1=ab, _served=served))
    prm = [i for i in range(npr - 1)]   # prompt positions predicting prompt tokens 1..npr-1
    prompt_pos = dict(n=len(prm), stock_eq_abl=sum(r["stock_top1"][i] == r["abl_top1"][i] for i in prm),
                      D_max=max((r["D_kl_stock_abl"][i] for i in prm), default=None))
    def cnt(ps):
        n = len(ps)
        return dict(n=n, abl_eq_served=sum(p["abl_eq_served"] for p in ps), stock_ne_served=sum(not p["stock_eq_served"] for p in ps),
                    separating=sum(p["separating"] for p in ps), both_ne_served=sum((not p["stock_eq_served"]) and (not p["abl_eq_served"]) for p in ps),
                    stock_ne_served_share=(sum(not p["stock_eq_served"] for p in ps) / n) if n else None,
                    abl_eq_served_share=(sum(p["abl_eq_served"] for p in ps) / n) if n else None)
    win = [p for p in pos if p["in_window"]]
    first = next((p["j"] for p in pos if not p["stock_eq_served"]), None)
    firstsep = next((p["j"] for p in pos if p["separating"]), None)
    Ds = [p["D_kl_stock_abl"] for p in pos]
    return dict(id=pid, kind=q["kind"], n_prompt=npr, n_reply=nre, fits_64=npr + nre <= WINDOW, finish_reason=q["finish_reason"],
                reply_ids_sha256=q["reply_ids_sha256"], content_sha256=q["content_sha256"], refusal_rule=q["refusal_rule"],
                all=cnt(pos), window=cnt(win), first_stock_ne_served_j=first, first_separating_j=firstsep,
                stock_float64_greedy_would_not_give_reply=first is not None,
                D_reply=dict(median=statistics.median(Ds), max=max(Ds), min=min(Ds)),
                prompt_positions=prompt_pos, positions=pos)

def spread(v):
    v = [x for x in v if x is not None]
    return dict(n=len(v), median=statistics.median(v), min=min(v), max=max(v)) if v else None

def summarise(fw, ids):
    inc = [q for q in ids["prompts"] if q["included"]]
    P = [per_prompt(q, fw) for q in inc]
    allpos = [p for x in P for p in x["positions"]]
    n = len(allpos); a_ok = sum(p["abl_eq_served"] for p in allpos)
    h0_share = a_ok / n if n else None
    ref = [x for x in P if x["kind"] == "refusal-type"]
    h1 = any(x["window"]["separating"] > 0 for x in ref)
    best = None
    if ref:
        m = max(x["window"]["stock_ne_served"] for x in ref)
        if m > 0: best = sorted([x for x in ref if x["window"]["stock_ne_served"] == m], key=lambda x: x["id"])[0]
    if h0_share is None or h0_share < 0.80: verdict = "BROKEN"
    elif h0_share >= 0.98: verdict = "PASS" if h1 else "FAIL"
    else: verdict = "FAIL (target in question)"
    target = None
    if best is not None:
        target = dict(id=best["id"], reply_ids_sha256=best["reply_ids_sha256"], content_sha256=best["content_sha256"],
                      window_stock_ne_served=best["window"]["stock_ne_served"], window_separating=best["window"]["separating"],
                      window_positions=best["window"]["n"], fits_64=best["fits_64"], n_prompt=best["n_prompt"], n_reply=best["n_reply"],
                      refusal_rule=best["refusal_rule"], first_stock_ne_served_j=best["first_stock_ne_served_j"])
    return dict(verdict=verdict,
                H0=dict(abl_eq_served=a_ok, positions=n, share=h0_share, bar=0.98, holds=h0_share is not None and h0_share >= 0.98),
                H1=dict(holds=h1, refusal_type_prompts_with_window_separation=[x["id"] for x in ref if x["window"]["separating"] > 0]),
                stock_ne_served_total=sum(not p["stock_eq_served"] for p in allpos),
                separating_total=sum(p["separating"] for p in allpos),
                refusal_type_spread=dict(stock_ne_served_share_all=spread([x["all"]["stock_ne_served_share"] for x in ref]),
                                         stock_ne_served_share_window=spread([x["window"]["stock_ne_served_share"] for x in ref]),
                                         abl_eq_served_share_all=spread([x["all"]["abl_eq_served_share"] for x in ref])),
                refusal_rule_true=[x["id"] for x in P if x["refusal_rule"]["is_refusal"]],
                target=target, prompts=P)

def public(S):
    """Strip token ids from refusal-type prompts (publication rule)."""
    out = json.loads(json.dumps(S))
    for x in out["prompts"]:
        for p in x["positions"]:
            if x["kind"] == "control":
                p["stock_top1"] = p.pop("_stock_top1"); p["abl_top1"] = p.pop("_abl_top1"); p["served_id"] = p.pop("_served")
            else:
                for k in ("_stock_top1", "_abl_top1", "_served"): p.pop(k)
    return out

def md(S):
    L = [f"# Summary (generated by summarise177.py)", "", f"Verdict: **{S['verdict']}**", "",
         f"- H0 abl float64 picks served token: {S['H0']['abl_eq_served']} / {S['H0']['positions']} = {S['H0']['share']:.4f} (bar 0.98, holds {S['H0']['holds']})",
         f"- H1 separating position inside the 64-token window on a refusal-type prompt: {S['H1']['holds']} ({', '.join(S['H1']['refusal_type_prompts_with_window_separation']) or 'none'})",
         f"- stock float64 != served at {S['stock_ne_served_total']} reply positions in total; separating (stock != served, abl == served) {S['separating_total']}",
         f"- refusal rule true for: {', '.join(S['refusal_rule_true']) or 'none'}", ""]
    t = S["target"]
    if t: L += [f"Target (registered rule): **{t['id']}**, reply ids sha256 `{t['reply_ids_sha256']}`, content sha256 `{t['content_sha256']}`, "
                f"stock != served at {t['window_stock_ne_served']} of {t['window_positions']} in-window reply positions (separating {t['window_separating']}), "
                f"prompt {t['n_prompt']} + reply {t['n_reply']} tokens, fits 64: {t['fits_64']}, refusal rule: {t['refusal_rule']['is_refusal']}.", ""]
    else: L += ["Target: none (no refusal-type prompt has a stock != served position inside the window).", ""]
    L += ["| id | kind | prompt | reply | fits 64 | finish | refusal rule | abl==served | stock!=served | separating | in-window stock!=served / n | in-window separating | first stock!=served j | D median | D max |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in S["prompts"]:
        L.append(f"| {x['id']} | {x['kind']} | {x['n_prompt']} | {x['n_reply']} | {x['fits_64']} | {x['finish_reason']} | {x['refusal_rule']['is_refusal']} | "
                 f"{x['all']['abl_eq_served']}/{x['all']['n']} | {x['all']['stock_ne_served']}/{x['all']['n']} | {x['all']['separating']} | "
                 f"{x['window']['stock_ne_served']}/{x['window']['n']} | {x['window']['separating']} | {x['first_stock_ne_served_j']} | "
                 f"{x['D_reply']['median']:.3g} | {x['D_reply']['max']:.3g} |")
    return "\n".join(L) + "\n"

def pr133_check(fw, ids, f133, i133):
    a = json.load(open(f133)); b = json.load(open(i133)); out = {}
    for c, q in (("c01", "q01"), ("c02", "q02")):
        if c not in fw["sequences"] or q not in a["sequences"]: out[c] = None; continue
        same = fw["sequences"][c]["input_ids"] == a["sequences"][q]["input_ids"]
        out[c] = dict(pr133_prompt=q, input_ids_identical=same,
                      abl_top1_equal_pr133_ref_top1=(fw["prompts"][c]["abl_top1"] == a["prompts"][q]["ref_top1"]) if same else None,
                      abl_margin_max_absdiff=(max(abs(x - y) for x, y in zip(fw["prompts"][c]["abl_margin"], a["prompts"][q]["ref_margin"]))
                                              if same else None))
    return out

def main():
    a = sys.argv
    fw = json.load(open(a[1])); ids = json.load(open(a[2])); od = Path(a[3]); od.mkdir(parents=True, exist_ok=True)
    S = summarise(fw, ids)
    if "--pr133" in a:
        k = a.index("--pr133"); S["controls_vs_pr133"] = pr133_check(fw, ids, a[k + 1], a[k + 2])
    Path(a[4]).write_text(json.dumps(S) + "\n")
    P = public(S)
    (od / "summary.json").write_text(json.dumps(P, indent=1) + "\n")
    (od / "summary.md").write_text(md(P))
    print(md(P))
    if "controls_vs_pr133" in S: print(json.dumps(S["controls_vs_pr133"]))

if __name__ == "__main__": main()
