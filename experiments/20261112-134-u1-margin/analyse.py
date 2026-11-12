#!/usr/bin/env python3
"""Validity gates and D vs E analysis (PREREG.md + A-1; fail-closed input validation per A-2). Light, no weights.

Usage: analyse.py [<inputs dir> [<output dir>]]

Reads from <inputs dir> (default runs/): d-per-position.json, manifest-{stock,abl}.json and progress.log of this lane's
run. Reads from the repo: PR #124's committed prompts-e2e.json, runs/e2e-{stock,abl}.json and
runs/manifest-{stock,abl}.json, and PR #87's committed runs/manifest-{stock,abl}.json.
Writes <output dir>/analysis.json and <output dir>/input-validation.json (default output dir: the inputs dir). It never
overwrites either file. The committed output of the registered run, runs/analysis.json, is therefore reproduced with
`analyse.py runs <new dir>` and is not rewritten.

Exit codes (PREREG Amendment A-2, added after review; no metric, threshold or number changes):
  0  the evidence is complete and the validity gates (a), (b), (c) pass: verdict PASS or FAIL as registered
  2  INVALID, nothing written: evidence missing, malformed, non-finite, or not the registered prompt tier
  3  KILLED (validity gate): the evidence is complete but gate (a), (b) or (c) fails; analysis.json says so
  4  nothing written: an output file already exists in the output dir
"""
import json, math, re, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
P124D = HERE.parent / "20261111-8-qwen-e2e-agreement"; P124 = P124D / "runs"
P87 = HERE.parent / "20261110-36-weight-binding" / "runs"
TOKYO = 25358; VOCAB = 248320
# Registered in PREREG A-1 (and run_fused.sh): the prompt tier follows from the slot grant time; compute hard stop.
FULL = ["p01-ordinary-short", "p07-chat-ordinary", "p08-chat-refusal", "p09-multilingual", "p02-ordinary-paragraph",
        "p04-repeat-punct", "p05-code", "p03-repeat-word", "p06a-digits-256", "p11-chat-long"]
T3 = ["p01-ordinary-short", "p07-chat-ordinary", "p08-chat-refusal", "p09-multilingual", "p06a-digits-256", "p11-chat-long"]
TIERS = {1: ("2026-11-12T18:15:00Z", FULL, 1461),                                        # grant <= limit: ids, positions
         2: ("2026-11-12T18:28:00Z", [p for p in FULL if p != "p03-repeat-word"], 949),
         3: ("2026-11-12T18:35:00Z", T3, 634)}
HARD_STOP = "2026-11-12T18:50:00Z"
# Tensors the fused run (A-1 item 2) must have fetched: stock = every tensor of layers 17..63 + final norm + lm_head;
# abl = the tensors whose committed PR #87 sha256 differs between the checkpoints + final norm.
NORM = "model.language_model.norm.weight"; LM_HEAD = "lm_head.weight"
LAYER = re.compile(r"^model\.language_model\.layers\.(\d+)\.")
N_CHANGED, N_STOCK, N_ABL = 70, 624, 71
OUTPUTS = ("analysis.json", "input-validation.json")

class Invalid(Exception): pass

def q(a, p): return float(np.percentile(a, p)) if len(a) else None
def ts(s): return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
def is_int(v): return isinstance(v, int) and not isinstance(v, bool)
def is_num(v): return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
def is_bool(v): return isinstance(v, bool)

def no_dup(pairs):
    d = dict(pairs)
    if len(d) != len(pairs): raise ValueError("duplicate key in a JSON object")
    return d

def jload(p, bad, what):
    if not p.is_file(): bad.append(f"{what}: file missing ({p.name})"); return None
    try: return json.loads(p.read_text(), object_pairs_hook=no_dup)
    except (ValueError, OSError) as e: bad.append(f"{what}: not readable as JSON without duplicate keys ({p.name}, {type(e).__name__})"); return None

def arr(bad, where, v, T, test, lo=None, hi=None):
    """v must be a list of exactly T values that pass `test` and lie in [lo, hi]."""
    if not isinstance(v, list) or len(v) != T: bad.append(f"{where}: not a list of {T} values"); return
    n = sum(1 for x in v if not test(x) or (lo is not None and x < lo) or (hi is not None and x > hi))
    if n: bad.append(f"{where}: {n} value(s) missing, non-finite, of the wrong type or out of range")

def read_tier(R, bad):
    """The registered tier is a function of the logged slot grant time (A-1 item 4). The log is not authenticated."""
    p = R / "progress.log"
    if not p.is_file(): bad.append("progress.log: file missing (its slot grant time decides the registered prompt tier, A-1)"); return None
    lines = p.read_text().splitlines(); pick = lambda pre: [l for l in lines if l.startswith(pre)]
    g, tl, en = pick("slot granted "), pick("tier "), pick("end rc=")
    try:
        if len(g) != 1: raise ValueError(f"{len(g)} 'slot granted' lines, need exactly 1")
        grant = ts(g[0].split()[2])
    except (ValueError, IndexError) as e: bad.append(f"progress.log: slot grant time not readable ({e})"); return None
    tier = next((k for k in sorted(TIERS) if grant <= ts(TIERS[k][0])), None)
    if tier is None: bad.append(f"progress.log: the grant is after {TIERS[3][0]}; A-1 registers no run for it"); return None
    if tl != [f"tier {tier} prompts {','.join(TIERS[tier][1])}"]:
        bad.append(f"progress.log: the logged tier line is not the A-1 tier {tier} line that this grant time requires")
    end = None
    try:
        if len(en) != 1 or en[0].split()[0] != "end" or en[0].split()[1] != "rc=0": raise ValueError("need exactly one 'end rc=0' line")
        end = en[0].split()[2]
        if not grant <= ts(end) <= ts(HARD_STOP): raise ValueError(f"end time outside [grant, hard stop {HARD_STOP}]")
    except (ValueError, IndexError) as e: bad.append(f"progress.log: no clean end of the registered run ({e})")
    return dict(tier=tier, grant=g[0].split()[2], end=end)

def validate(R):
    """Returns the loaded evidence, or raises Invalid with every reason found. Nothing here computes a result."""
    bad = []
    tr = read_tier(R, bad)
    pj = jload(P124D / "prompts-e2e.json", bad, "PR #124 frozen prompts")
    es = jload(P124 / "e2e-stock.json", bad, "PR #124 E (stock)"); ea = jload(P124 / "e2e-abl.json", bad, "PR #124 E (abl)")
    b87 = {}
    for ck in ("stock", "abl"):
        j = jload(P87 / f"manifest-{ck}.json", bad, f"PR #87 manifest ({ck})")
        b87[ck] = {t["name"]: t["sha256"] for t in j["tensors"]} if j else {}
    d = jload(R / "d-per-position.json", bad, "D file")
    if None in (pj, es, ea) or not b87["stock"] or not b87["abl"]: raise Invalid(bad)
    frozen = {p["id"]: p["n_tokens"] for p in pj["prompts"]}
    if list(frozen) != FULL or any(sum(frozen[p] for p in ids) != n for _, ids, n in TIERS.values()):
        bad.append("PR #124 frozen prompts do not give the registered prompt ids and tier position counts")
        raise Invalid(bad)
    # 1. prompts: exactly the registered tier, every per-position array complete, typed and finite
    dp = d.get("prompts") if isinstance(d, dict) else None
    if d is not None and not isinstance(dp, dict): bad.append("D file: no 'prompts' object")
    if tr and isinstance(dp, dict):
        ids = TIERS[tr["tier"]][1]
        missing = [p for p in ids if p not in dp]; extra = sorted(set(dp) - set(ids))
        if missing or extra:
            bad.append(f"D file: the prompts are not the registered tier {tr['tier']} set ({len(ids)} prompts, {TIERS[tr['tier']][2]} positions): "
                       f"missing {missing}, not in the tier {extra}")
        for pid in (p for p in ids if p in dp):
            r, T = dp[pid], frozen[pid]
            if not isinstance(r, dict) or not is_int(r.get("T")) or r["T"] != T:
                bad.append(f"D file {pid}: T is not the frozen prompt's {T} positions"); continue
            for k in ("stock_top1", "abl_top1"): arr(bad, f"D file {pid}.{k}", r.get(k), T, is_int, 0, VOCAB - 1)
            for k in ("stock_margin", "abl_margin"): arr(bad, f"D file {pid}.{k}", r.get(k), T, is_num, 0.0)
            arr(bad, f"D file {pid}.D_kl_stock_abl", r.get("D_kl_stock_abl"), T, is_num, -1e-9)   # a KL is >= 0 up to rounding
            for leg, src in (("stock", es), ("abl", ea)):
                c = src["prompts"].get(pid); w = f"PR #124 E ({leg}) {pid}"
                if not isinstance(c, dict) or c.get("T") != T: bad.append(f"{w}: missing or T is not {T}"); continue
                arr(bad, f"{w}.ref_top1", c.get("ref_top1"), T, is_int, 0, VOCAB - 1); arr(bad, f"{w}.ref_margin", c.get("ref_margin"), T, is_num, 0.0)
                for arm in ("XS18", "XS20"):
                    a = c.get("paths", {}).get(arm, {})
                    arr(bad, f"{w}.{arm}.kl", a.get("kl"), T, is_num); arr(bad, f"{w}.{arm}.top1_agree", a.get("top1_agree"), T, is_bool)
    # 2. fetched tensors: exactly the expected coverage, each entry with a sha256
    changed = sorted(k for k in b87["stock"] if b87["abl"].get(k) != b87["stock"][k])
    exp = dict(stock={n for n in b87["stock"] if LAYER.match(n) and 17 <= int(LAYER.match(n).group(1)) <= 63} | {NORM, LM_HEAD},
               abl=set(changed) | {NORM})
    if set(b87["stock"]) != set(b87["abl"]) or len(changed) != N_CHANGED or len(exp["stock"]) != N_STOCK or len(exp["abl"]) != N_ABL:
        bad.append(f"PR #87 manifests do not give the registered coverage ({N_CHANGED} changed tensors; {N_STOCK} stock and {N_ABL} abl tensors to fetch)")
        raise Invalid(bad)
    man = {}
    for ck in ("stock", "abl"):
        m = jload(R / f"manifest-{ck}.json", bad, f"manifest ({ck})"); o = jload(P124 / f"manifest-{ck}.json", bad, f"PR #124 manifest ({ck})")
        if m is None or o is None: continue
        mt = m.get("tensors") if isinstance(m, dict) else None
        if not isinstance(mt, dict): bad.append(f"manifest ({ck}): no 'tensors' object"); continue
        if (m.get("repo"), m.get("rev")) != (o["repo"], o["rev"]): bad.append(f"manifest ({ck}): repository or revision is not PR #124's")
        miss = exp[ck] - set(mt); unk = set(mt) - exp[ck]
        if miss or unk:
            bad.append(f"manifest ({ck}): the fetched tensors are not the expected {len(exp[ck])} "
                       f"({len(mt)} present, {len(miss)} expected ones missing, {len(unk)} not expected)")
        nosha = [n for n, e in mt.items() if not (isinstance(e, dict) and isinstance(e.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", e["sha256"]))]
        if nosha: bad.append(f"manifest ({ck}): {len(nosha)} entr(ies) without a sha256")
        if exp[ck] - set(o["tensors"]): bad.append(f"PR #124 manifest ({ck}): expected tensors are not in it")
        man[ck] = (mt, o["tensors"])
    if bad or tr is None or not isinstance(dp, dict) or len(man) != 2: raise Invalid(bad or ["evidence incomplete"])
    return dict(tr=tr, d=dp, es=es["prompts"], ea=ea["prompts"], man=man, b87=b87, exp=exp)

def analyse(v):
    d, es, ea = v["d"], v["es"], v["ea"]
    out = dict(gates={}, prompts={}, pooled={})
    # gate (a): must be true. p01 is in every registered tier, and validate() has required the tier's prompts.
    p01 = d["p01-ordinary-short"]
    out["gates"]["a_tokyo"] = bool(p01["stock_top1"][-1] == TOKYO and p01["abl_top1"][-1] == TOKYO)
    # gate (b): reproduce PR #124's REF
    bad = []; mmax = 0.0
    for pid, r in d.items():
        for leg, src, top, mar in (("stock", es, "stock_top1", "stock_margin"), ("abl", ea, "abl_top1", "abl_margin")):
            c = src[pid]
            for t in range(r["T"]):
                dm = abs(r[mar][t] - c["ref_margin"][t]); mmax = max(mmax, dm)
                if (c["ref_margin"][t] > 1e-6 and r[top][t] != c["ref_top1"][t]) or dm > 1e-6:
                    bad.append(dict(prompt=pid, leg=leg, t=t, mine=r[top][t], pr124=c["ref_top1"][t], dmargin=dm))
    out["gates"]["b_reproduce"] = dict(ok=not bad, max_abs_margin_diff=mmax, failures=bad[:50], n_fail=len(bad))
    # gate (c): sha256 vs PR #124's manifests, as registered, and also vs PR #87's (A-2: the fused pass of A-1 item 2
    # rests on PR #87's hashes). validate() has required the full expected coverage, so an empty or partial manifest
    # cannot reach this point.
    cm = {}
    for ck in ("stock", "abl"):
        m, o = v["man"][ck]; p87 = v["b87"][ck]
        both = sorted(set(m) & set(o)); cm[ck] = dict(compared=len(both), mismatch=[n for n in both if m[n]["sha256"] != o[n]["sha256"] or m[n]["sha256"] != p87[n]],
                                                      not_in_pr124=sorted(set(m) - set(o)))
    out["gates"]["c_manifest"] = dict(ok=all(not x["mismatch"] for x in cm.values()), **cm)
    valid = bool(out["gates"]["a_tokyo"] is True and out["gates"]["b_reproduce"]["ok"] and out["gates"]["c_manifest"]["ok"])
    out["gates"]["all_ok"] = valid
    # D vs E
    allr = {"XS18": [], "XS20": []}; allD = []; allE = []; flips = []; nonpos = {"XS18": [], "XS20": []}
    for pid, r in d.items():
        D = np.array(r["D_kl_stock_abl"])
        pr = dict(T=r["T"], D_median=float(np.median(D)), D_max=float(D.max()), D_min=float(D.min()),
                  top1_differ=int(sum(a != b for a, b in zip(r["stock_top1"], r["abl_top1"]))),
                  top1_differ_pr124=int(sum(a != b for a, b in zip(es[pid]["ref_top1"], ea[pid]["ref_top1"]))),
                  differ_positions=[dict(t=t, stock=r["stock_top1"][t], abl=r["abl_top1"][t], stock_margin=r["stock_margin"][t], D=r["D_kl_stock_abl"][t])
                                    for t in range(r["T"]) if r["stock_top1"][t] != r["abl_top1"][t]])
        for arm in ("XS18", "XS20"):
            Es = es[pid]["paths"][arm]; Ea = ea[pid]["paths"][arm]
            Ev = np.maximum(np.array(Es["kl"]), np.array(Ea["kl"]))
            rr = np.where(Ev > 0, D / np.where(Ev > 0, Ev, 1), np.inf)
            allr[arm] += list(rr)
            lr = np.log10(rr[np.isfinite(rr)])
            pr[arm] = dict(E_median=float(np.median(Ev)), E_max=float(Ev.max()), share_gt10=float((rr > 10).mean()), share_gt100=float((rr > 100).mean()),
                           log10r_median=q(lr, 50), log10r_sd=float(lr.std()) if len(lr) else None, log10r_min=float(lr.min()) if len(lr) else None,
                           log10r_max=float(lr.max()) if len(lr) else None, sumD_over_sumE=float(D.sum() / Ev.sum()), n_E_nonpos=int((Ev <= 0).sum()))
            nonpos[arm] += [dict(prompt=pid, t=int(t), E_stock=float(Es["kl"][t]), E_abl=float(Ea["kl"][t]), D=float(D[t])) for t in np.where(Ev <= 0)[0]]
            if arm == "XS18": allE += list(Ev)
            for leg, src in (("stock", es), ("abl", ea)):
                for t, ok in enumerate(src[pid]["paths"][arm]["top1_agree"]):
                    if not ok: flips.append(dict(prompt=pid, leg=leg, arm=arm, t=t, D=float(D[t]), E=float(Ev[t]), r=float(rr[t])))
        allD += list(D); out["prompts"][pid] = pr
    for arm in ("XS18", "XS20"):
        rr = np.array(allr[arm]); lr = np.log10(rr[np.isfinite(rr)])
        out["pooled"][arm] = dict(n=len(rr), share_gt10=float((rr > 10).mean()), share_gt100=float((rr > 100).mean()),
                                  log10r=dict(median=q(lr, 50), sd=float(lr.std()), min=float(lr.min()), max=float(lr.max()),
                                              p1=q(lr, 1), p10=q(lr, 10), p90=q(lr, 90)),
                                  prompts_share10_ge_090=sum(1 for p in out["prompts"].values() if p[arm]["share_gt10"] >= 0.90))
    out["pooled"]["D"] = dict(n=len(allD), median=float(np.median(allD)), max=float(max(allD)), min=float(min(allD)), p10=q(allD, 10), p90=q(allD, 90))
    out["pooled"]["E_XS18"] = dict(median=float(np.median(allE)), max=float(max(allE)))
    out["pooled"]["top1_differ"] = sum(p["top1_differ"] for p in out["prompts"].values())
    out["pooled"]["top1_differ_pr124_same_prompts"] = sum(p["top1_differ_pr124"] for p in out["prompts"].values())
    out["integer_flip_positions"] = flips
    # verdict (XS18 primary)
    P = out["pooled"]["XS18"]; n = len(out["prompts"]); need = math.ceil(0.8 * n)
    c1, c2, c3 = P["share_gt10"] >= 0.95, P["share_gt100"] >= 0.50, P["prompts_share10_ge_090"] >= need
    if not valid: vd = "KILLED (validity gate)"
    elif c1 and c2 and c3: vd = "PASS"
    elif P["share_gt10"] < 0.50: vd = "FAIL (negative in the issue's sense)"
    else: vd = "FAIL (mixed)"
    out["verdict"] = dict(verdict=vd, c1=bool(c1), c2=bool(c2), c3=bool(c3), prompts_needed=need, prompts_run=n,
                          subset=n < 10)
    return out, nonpos

def main(argv):
    R = Path(argv[1]) if len(argv) > 1 else HERE / "runs"; OUT = Path(argv[2]) if len(argv) > 2 else R
    exist = [f for f in OUTPUTS if (OUT / f).exists()]
    if exist:
        print(f"NOT RUN: {', '.join(exist)} already in the output dir; this script never overwrites. Give a new output dir as the second argument.", file=sys.stderr)
        return 4
    try:
        v = validate(R)
        out, nonpos = analyse(v)
        text = json.dumps(out, indent=1, allow_nan=False) + "\n"      # a non-finite statistic is not a result either
    except Invalid as e:
        print("INVALID, no analysis written:", file=sys.stderr)
        for b in e.args[0]: print(" -", b, file=sys.stderr)
        return 2
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, ZeroDivisionError) as e:
        print(f"INVALID, no analysis written:\n - malformed evidence or non-finite statistic ({type(e).__name__}: {e})", file=sys.stderr)
        return 2
    tr = v["tr"]; ids = TIERS[tr["tier"]][1]; g = out["gates"]; rc = 0 if g["all_ok"] else 3
    val = dict(what="input validation of analyse.py (PREREG Amendment A-2); written only when the evidence is complete",
               tier=tr["tier"], slot_granted=tr["grant"], run_end=tr["end"], prompts=ids, positions=sum(r["T"] for r in v["d"].values()),
               positions_registered_for_tier=TIERS[tr["tier"]][2], tokyo_checked=True,
               tensor_coverage={ck: dict(expected=len(v["exp"][ck]), present=len(v["man"][ck][0]), sha256_compared=g["c_manifest"][ck]["compared"],
                                         sha256_mismatch=len(g["c_manifest"][ck]["mismatch"])) for ck in ("stock", "abl")},
               E_nonpositive_positions=nonpos,
               E_nonpositive_note="E = max(E_stock, E_abl) <= 0: the ratio counts as +inf in the shares and is left out of the finite log10 ratio statistics (PREREG Metric)",
               gates=dict(a_tokyo=g["a_tokyo"], b_reproduce=g["b_reproduce"]["ok"], c_manifest=g["c_manifest"]["ok"], all_ok=g["all_ok"]),
               verdict=out["verdict"]["verdict"], exit_code=rc)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "analysis.json").write_text(text)
    (OUT / "input-validation.json").write_text(json.dumps(val, indent=1, allow_nan=False) + "\n")
    print(json.dumps(dict(verdict=out["verdict"], gates={k: (x if not isinstance(x, dict) else x.get("ok")) for k, x in out["gates"].items()},
                          tier=tr["tier"], pooled=out["pooled"]), indent=1))
    for pid, p in out["prompts"].items():
        print(pid, p["T"], "D med %.3g max %.3g" % (p["D_median"], p["D_max"]), "XS18 >10 %.3f >100 %.3f" % (p["XS18"]["share_gt10"], p["XS18"]["share_gt100"]),
              "top1diff", p["top1_differ"], "(pr124", p["top1_differ_pr124"], ")")
    for arm, lst in nonpos.items():
        for x in lst: print("E <= 0:", arm, x["prompt"], "t", x["t"])
    if rc: print("KILLED (validity gate): the numbers above are not a result", file=sys.stderr)
    return rc

if __name__ == "__main__":
    sys.exit(main(sys.argv))
