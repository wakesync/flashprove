#!/usr/bin/env python3
"""Summarise the held-out run (PREREG.md). Validates every record against the registered product first and REFUSES
(exit 2, nothing written) on malformed, duplicate, missing or unexpected records, a layer record that disagrees with its
cells / prompt rows, a non-prefix layer order, or validity evidence of the wrong shape.

Verdicts per arm, two independent axes (PREREG "Acceptance threshold"):
  H_R: PASS iff 16 layers done, zero clamps, zero guard failures; FAIL if any on a done layer; else NOT TESTED (partial).
  H_F: PASS iff 16 layers pass median <= 0.01 and max <= 0.05 over 192 cells and no guard failure; FAIL if a done layer
       fails (or has a guard failure); else NOT TESTED (partial).
  Validity (V1 split bit-equal to q1, V2 determinism on the two preselected prompts for both arms, V3 frozen scales used):
  if any false, the arm's verdicts are "comparison invalid".

Strict field checks (PREREG Amendment A1, added after review of PR #206; they refuse, they never change a verdict on
well-formed records): every count is a non-negative integer (JSON true/false and 3.0 are not integers), bounded by its
denominator; every rel_y / statistic is a finite non-negative number (NaN, Infinity, negative refused); every evidence
flag is a real JSON boolean; each prompt row's T equals the frozen manifest's n_tokens and its q_n / k_n / v_n equal
T x 24 x 256 / T x 4 x 256 / T x 4 x 256; per-head clamp arrays (24 query heads, 4 kv heads) sum to the row's counts;
a count of entries over the clamp is non-zero exactly when the recorded max |RNE| exceeds the clamp.

PREREG Amendment A2 (second review of PR #206): (1) the evaluator's guarded-null representation is admitted exactly where
heldout.py writes it and nowhere else: when int_attn's arithmetic assertion fires, heldout.eval_frozen writes the prompt
row with mix_rel, max_abs_s, e_zero and causal all null and a non-empty guard_fail list of strings, and attention_layer
writes rel_y null for all 24 heads of that prompt; a layer whose cells are all null carries NaN rel_median / rel_max /
rel_min. Any other null, a partial null set, or a null without a guard is refused. (2) Every retained descriptive field
is checked: obs_mx_q/k/v, max_abs_s, arm_seconds and the timing seconds finite and non-negative; max_abs_s within
[0, Smax] (scores of clamped operands); e_zero <= causal = 24 x T(T+1)/2; the layer's maxima and sums equal those of its
prompt rows; n_pairs, n_cells_valid, rel_min and the over-bar counts equal those of its cells; a wide value is a guard.
(3) Every per-head clamp count is bounded by that head's T x 256 entries.

Usage: summarise_heldout.py [<in_dir> [<out_dir>]]   (defaults: runs/ and runs/)
"""
import json, math, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ARMS = {"C2047": 2047, "C1665": 1665}
LAYERS = list(range(3, 64, 4))
NH, NKV, HD = 24, 4, 256
BAR_MED, BAR_MAX = 0.01, 0.05

class Refuse(Exception): pass

# ---- strict field checks (Amendment A1) ------------------------------------------------------------------------
def is_int(x): return type(x) is int                       # rejects bool, float, str, None
def is_num(x): return type(x) in (int, float) and math.isfinite(x)

def nonneg_int(x, what, upper=None):
    if not is_int(x) or x < 0: raise Refuse(f"{what} is not a non-negative integer: {x!r}")
    if upper is not None and x > upper: raise Refuse(f"{what} = {x} exceeds its denominator {upper}")
    return x

def nonneg_num(x, what):
    if not is_num(x) or x < 0: raise Refuse(f"{what} is not a finite non-negative number: {x!r}")
    return x

def boolean(x, what):
    if type(x) is not bool: raise Refuse(f"{what} is not a JSON boolean: {x!r}")
    return x

def bool_map(d, what):
    if not isinstance(d, dict): raise Refuse(f"{what} is not an object")
    for k, v in d.items(): boolean(v, f"{what}[{k}]")
    return d

def by_head(arr, n, total, what, per_head=None):
    if not isinstance(arr, list) or len(arr) != n: raise Refuse(f"{what} is not a list of {n} counts")
    for i, x in enumerate(arr): nonneg_int(x, f"{what}[{i}]", per_head)    # A2: each head has only T x 256 entries
    if sum(arr) != total: raise Refuse(f"{what} sums to {sum(arr)}, not the row total {total}")

def over_vs_max(over, maxw, cl, what):
    nonneg_int(maxw, f"{what} max |RNE|")
    if (over > 0) != (maxw > cl): raise Refuse(f"{what}: {over} entries over the clamp but max |RNE| {maxw} vs clamp {cl}")

GUARD_NULL = ("mix_rel", "max_abs_s", "e_zero", "causal")   # A2: fields heldout.eval_frozen nulls on an assertion
WIDE_GUARD = "wide value over 32767"

def guarded_null(p):
    """A2: True iff the prompt row is in the evaluator's assertion-path representation (all GUARD_NULL fields null and a
    non-empty guard list); False iff none of them is null. Anything in between is refused."""
    k = (p["arm"], p["layer"], p["prompt"])
    nulls = [f for f in GUARD_NULL if p.get(f, 0) is None]
    if not nulls: return False
    if len(nulls) != len(GUARD_NULL): raise Refuse(f"{k}: only {nulls} null; the evaluator nulls exactly {list(GUARD_NULL)} together")
    if not p.get("guard_fail") or p["guard_fail"] == [WIDE_GUARD]: raise Refuse(f"{k}: null metrics without an arithmetic guard failure")
    return True

def check_prompt_row(p, cl, ntok):
    k = (p["arm"], p["layer"], p["prompt"])
    T = p.get("T")
    if not is_int(T) or T <= 0: raise Refuse(f"T of {k} is not a positive integer: {T!r}")
    if ntok is not None and T != ntok[p["prompt"]]: raise Refuse(f"T of {k} = {T}, manifest n_tokens {ntok[p['prompt']]}")
    for t, nh in (("q", NH), ("k", NKV), ("v", NKV)):
        n = p.get(f"{t}_n")
        if not is_int(n) or n != T * nh * HD: raise Refuse(f"{t}_n of {k} = {n!r}, expected T x {nh} x {HD} = {T * nh * HD}")
        nonneg_int(p.get(f"{t}_over"), f"{t}_over of {k}", n)
        over_vs_max(p[f"{t}_over"], p.get(f"{t}_maxw"), cl, f"{t} of {k}")
    by_head(p.get("q_over_by_head"), NH, p["q_over"], f"q_over_by_head of {k}", T * HD)
    by_head(p.get("k_over_by_kvhead"), NKV, p["k_over"], f"k_over_by_kvhead of {k}", T * HD)
    by_head(p.get("v_over_by_kvhead"), NKV, p["v_over"], f"v_over_by_kvhead of {k}", T * HD)
    g = p.get("guard_fail")
    if not isinstance(g, list) or not all(type(x) is str and x for x in g): raise Refuse(f"guard_fail of {k} is not a list of strings")
    if not isinstance(p.get("scales_used"), dict): raise Refuse(f"scales_used of {k} is not an object")
    w = nonneg_int(p.get("wide_over_32767"), f"wide_over_32767 of {k}", p["q_over"] + p["k_over"] + p["v_over"])
    if (w > 0) != (WIDE_GUARD in g): raise Refuse(f"{k}: wide_over_32767 = {w} but guard list {g}")
    for f in ("obs_mx_q", "obs_mx_k", "obs_mx_v"): nonneg_num(p.get(f), f"{f} of {k}")
    if guarded_null(p): return True
    nonneg_num(p.get("mix_rel"), f"mix_rel of {k}")
    s = nonneg_num(p.get("max_abs_s"), f"max_abs_s of {k}")
    if s > HD * cl * cl or s != math.floor(s): raise Refuse(f"max_abs_s of {k} = {s!r} is not an integer score within Smax")
    causal = nonneg_int(p.get("causal"), f"causal of {k}")
    if causal != NH * T * (T + 1) // 2: raise Refuse(f"causal of {k} = {causal}, expected 24 x T(T+1)/2")
    nonneg_int(p.get("e_zero"), f"e_zero of {k}", causal)
    return False

def check_layer_row(r, cl, n_tok_total):
    k = (r["arm"], r["layer"])
    for f in ("clamp", "Smax", "Eq", "Ek", "Ev", "sh"):
        if not is_int(r.get(f)): raise Refuse(f"{f} of {k} is not an integer: {r.get(f)!r}")
    for t, nh in (("q", NH), ("k", NKV), ("v", NKV)):
        n = r.get(f"{t}_n")
        if not is_int(n) or (n_tok_total is not None and n != n_tok_total * nh * HD): raise Refuse(f"{t}_n of {k} = {n!r}")
        nonneg_int(r.get(f"{t}_over"), f"{t}_over of {k}", n)
        over_vs_max(r[f"{t}_over"], r.get(f"{t}_maxw"), cl, f"{t} of {k}")
    nonneg_int(r.get("n_clamped"), f"n_clamped of {k}")
    if not isinstance(r.get("guard_failures"), list): raise Refuse(f"guard_failures of {k} is not a list")
    nv = nonneg_int(r.get("n_cells_valid"), f"n_cells_valid of {k}")
    for f in ("rel_median", "rel_max", "rel_min"):
        x = r.get(f)
        if nv == 0 and type(x) is float and math.isnan(x): continue      # A2: all cells guarded -> producer writes NaN
        nonneg_num(x, f"{f} of {k}")
    for f in ("obs_mx_q", "obs_mx_k", "obs_mx_v", "arm_seconds"): nonneg_num(r.get(f), f"{f} of {k}")
    s = nonneg_num(r.get("max_abs_s"), f"max_abs_s of {k}")
    if s > HD * cl * cl: raise Refuse(f"max_abs_s of {k} = {s!r} exceeds Smax")
    for f in ("e_zero", "causal", "wide_over_32767", "n_pairs", "n_over_001", "n_over_005"): nonneg_int(r.get(f), f"{f} of {k}")
    for f in ("range_pass", "fid_pass", "scales_frozen_ok"): boolean(r.get(f), f"{f} of {k}")
    bool_map(r.get("det_bit_equal"), f"det_bit_equal of {k}")

def jl(p):
    if not p.exists(): raise Refuse(f"missing file {p.name}")
    out = []
    for n, line in enumerate(p.read_text().splitlines()):
        if not line.strip(): continue
        try: out.append(json.loads(line))
        except json.JSONDecodeError: raise Refuse(f"malformed line {n} in {p.name}")
    return out

def summarise(ind, prompts, det, table, ntok=None):
    """ntok: {prompt id: n_tokens} from the frozen manifest; main() always passes it (T and denominators are then
    checked against it). Without it T is still checked to be a positive integer and denominators against T."""
    if ntok is not None and set(ntok) != set(prompts): raise Refuse("manifest n_tokens do not cover exactly the prompts")
    n_tok_total = sum(ntok.values()) if ntok is not None else None
    lay, cells, prows, tim = jl(ind / "layers.jsonl"), jl(ind / "cells.jsonl"), jl(ind / "prompt-rows.jsonl"), jl(ind / "attn-timing.jsonl")
    for name, recs in (("layers", lay), ("cells", cells), ("prompt-rows", prows), ("attn-timing", tim)):
        for x in recs:
            if not isinstance(x, dict): raise Refuse(f"non-object record in {name}")
            if not is_int(x.get("layer")): raise Refuse(f"layer of a {name} record is not an integer: {x.get('layer')!r}")
            if name == "cells" and not is_int(x.get("head")): raise Refuse(f"head of a cell is not an integer: {x.get('head')!r}")
    order = [(l, a) for l in LAYERS for a in ARMS]
    keys = [(r.get("layer"), r.get("arm")) for r in lay]
    if len(set(keys)) != len(keys): raise Refuse("duplicate layer record")
    if keys != order[:len(keys)]: raise Refuse("layer records are not a prefix of the run order")
    done = sorted({l for l, a in keys if all((l, b) in keys for b in ARMS)})
    if len(keys) % 2: raise Refuse("missing arm on the last layer record")
    cset, pset = {}, {}
    for c in cells:
        k = (c.get("arm"), c.get("layer"), c.get("prompt"), c.get("head"))
        if k[0] not in ARMS or k[1] not in LAYERS or k[2] not in prompts or k[3] not in range(NH): raise Refuse(f"unexpected cell {k}")
        if k in cset: raise Refuse(f"duplicate cell {k}")
        r = c.get("rel_y")
        if r is not None and (not is_num(r) or r < 0): raise Refuse(f"bad rel_y {k}: {r!r}")
        cset[k] = r
    for p in prows:
        k = (p.get("arm"), p.get("layer"), p.get("prompt"))
        if k[0] not in ARMS or k[1] not in LAYERS or k[2] not in prompts: raise Refuse(f"unexpected prompt row {k}")
        if k in pset: raise Refuse(f"duplicate prompt row {k}")
        check_prompt_row(p, ARMS[k[0]], ntok)
        pset[k] = p
    tset = {}
    for t in tim:
        if t.get("layer") not in LAYERS or t.get("layer") in tset: raise Refuse(f"bad or duplicate timing row {t.get('layer')}")
        bool_map(t.get("mix_bit_equal_q1"), f"mix_bit_equal_q1 of layer {t['layer']}")
        for f in ("total_s", "float_s", "ref_attention_s"): nonneg_num(t.get(f), f"{f} of layer {t['layer']}")
        tset[t["layer"]] = t
    rec_layers = {l for l, _ in keys}
    for k in list(cset) + [k + (None,) for k in pset]:
        if k[1] not in rec_layers: raise Refuse(f"cell or prompt row for an unrecorded layer {k[:3]} (interrupted layer)")
    per_arm = {a: [] for a in ARMS}
    for r in lay:
        a, l = r["arm"], r["layer"]; cl = ARMS[a]
        check_layer_row(r, cl, n_tok_total)
        want_c = {(a, l, p, h) for p in prompts for h in range(NH)}
        got_c = {k for k in cset if k[0] == a and k[1] == l}
        if got_c != want_c: raise Refuse(f"cells of {a} {l} are not exactly {len(prompts)} prompts x {NH} heads")
        if {k for k in pset if k[0] == a and k[1] == l} != {(a, l, p) for p in prompts}: raise Refuse(f"prompt rows of {a} {l} incomplete")
        if l not in tset: raise Refuse(f"timing row for layer {l} missing")
        if r.get("clamp") != cl or r.get("Smax") != 256 * cl * cl: raise Refuse(f"clamp/Smax of {a} {l}")
        if {f: r.get(f) for f in ("Eq", "Ek", "Ev", "sh")} != table[(a, l)]: raise Refuse(f"scales of {a} {l} differ from the frozen table")
        vals = [cset[(a, l, p, h)] for p in prompts for h in range(NH)]
        good = [v for v in vals if v is not None]
        pr = [pset[(a, l, p)] for p in prompts]
        clamps = sum(p["q_over"] + p["k_over"] + p["v_over"] for p in pr)
        guards = [dict(prompt=p["prompt"], guard=g) for p in pr for g in p["guard_fail"]]
        if any(p.get("scales_used") != table[(a, l)] for p in pr): raise Refuse(f"scales_used of {a} {l} differ from the frozen table")
        if r.get("n_clamped") != clamps or r.get("guard_failures") != guards: raise Refuse(f"clamp or guard totals of {a} {l} disagree with prompt rows")
        for f in ("q_over", "q_n", "k_over", "k_n", "v_over", "v_n"):
            if r.get(f) != sum(p[f] for p in pr): raise Refuse(f"{f} total of {a} {l}")
        if len(good) != len(vals) and not guards: raise Refuse(f"missing rel_y without a guard failure {a} {l}")
        for p in prompts:                                       # A2: nulls only on the evaluator's guarded path
            gn = guarded_null(pset[(a, l, p)]); nulls = sum(cset[(a, l, p, h)] is None for h in range(NH))
            if nulls != (NH if gn else 0): raise Refuse(f"{a} {l} {p}: {nulls} null rel_y, prompt row guarded-null {gn}")
        for f in ("q_maxw", "k_maxw", "v_maxw", "obs_mx_q", "obs_mx_k", "obs_mx_v"):
            if r[f] != max(p[f] for p in pr): raise Refuse(f"{f} of {a} {l} is not the maximum of its prompt rows")
        if r["max_abs_s"] != max([0.0] + [p["max_abs_s"] for p in pr if p["max_abs_s"] is not None]): raise Refuse(f"max_abs_s of {a} {l} disagrees with prompt rows")
        for f in ("e_zero", "causal", "wide_over_32767"):
            if r[f] != sum(p[f] or 0 for p in pr): raise Refuse(f"{f} total of {a} {l} disagrees with prompt rows")
        arr = np.array(good) if good else np.array([np.nan])
        med, mxv = float(np.median(arr)), float(arr.max())
        if good and (abs(med - r["rel_median"]) > 0 or abs(mxv - r["rel_max"]) > 0): raise Refuse(f"statistics of {a} {l} disagree with cells")
        if (r["n_pairs"], r["n_cells_valid"], r["n_over_001"], r["n_over_005"]) != (len(vals), len(good), int((arr > BAR_MED).sum()), int((arr > BAR_MAX).sum())) \
           or (good and r["rel_min"] != float(arr.min())) or (not good and not math.isnan(r["rel_median"])):
            raise Refuse(f"cell counts or rel_min of {a} {l} disagree with cells")
        fid = bool(not guards and len(good) == len(vals) and med <= BAR_MED and mxv <= BAR_MAX)
        rng = bool(clamps == 0 and not guards)
        if r.get("fid_pass") != fid or r.get("range_pass") != rng: raise Refuse(f"pass flags of {a} {l} disagree")
        dk = set(r.get("det_bit_equal", {}))
        if dk != set(det): raise Refuse(f"determinism evidence of {a} {l} is not exactly {det}")
        v1 = all(tset[l]["mix_bit_equal_q1"].get(p) is True for p in prompts) and set(tset[l]["mix_bit_equal_q1"]) == set(prompts)
        per_arm[a].append(dict(layer=l, clamped=clamps, q_over=r["q_over"], k_over=r["k_over"], v_over=r["v_over"],
                               q_n=r["q_n"], k_n=r["k_n"], v_n=r["v_n"], guards=guards, n_cells=len(vals), n_valid=len(good),
                               rel_median=med, rel_max=mxv, rel_min=float(arr.min()), n_over_001=int((arr > BAR_MED).sum()),
                               n_over_005=int((arr > BAR_MAX).sum()), range_pass=rng, fid_pass=fid,
                               det_ok=all(r["det_bit_equal"].values()), split_ok=v1, scales_ok=bool(r.get("scales_frozen_ok")),
                               scales=table[(a, l)], max_abs_s=r.get("max_abs_s"),
                               q_maxw=r.get("q_maxw"), k_maxw=r.get("k_maxw"), v_maxw=r.get("v_maxw"),
                               obs_mx=[r.get("obs_mx_q"), r.get("obs_mx_k"), r.get("obs_mx_v")],
                               mix_rel=[pset[(a, l, p)]["mix_rel"] for p in prompts], arm_seconds=r.get("arm_seconds"),
                               layer_seconds=tset[l]["total_s"]))
    out = dict(prompts=prompts, layers_done=done, complete=len(done) == len(LAYERS), arms={})
    for a, rows in per_arm.items():
        valid = all(x["det_ok"] and x["split_ok"] and x["scales_ok"] for x in rows)
        complete = len(rows) == len(LAYERS)
        if not valid: hr = hf = "comparison invalid"
        else:
            hr = "FAIL" if any(not x["range_pass"] for x in rows) else ("PASS" if complete else "NOT TESTED (partial)")
            hf = "FAIL" if any(not x["fid_pass"] for x in rows) else ("PASS" if complete else "NOT TESTED (partial)")
        allc = [cset[(a, x["layer"], p, h)] for x in rows for p in prompts for h in range(NH)]
        allc = np.array([c for c in allc if c is not None]) if rows else np.array([np.nan])
        out["arms"][a] = dict(H_R=hr, H_F=hf, valid=valid, layers_done=len(rows),
                              layers_range_fail=[x["layer"] for x in rows if not x["range_pass"]],
                              layers_fid_fail=[x["layer"] for x in rows if not x["fid_pass"]],
                              total_clamped=sum(x["clamped"] for x in rows), total_guard_failures=sum(len(x["guards"]) for x in rows),
                              pooled=dict(n=int(allc.size), median=float(np.median(allc)), max=float(allc.max()),
                                          n_over_001=int((allc > BAR_MED).sum()), n_over_005=int((allc > BAR_MAX).sum())),
                              not_tested_layers=[l for l in LAYERS if l not in [x["layer"] for x in rows]], layers=rows)
    return out

def md(s):
    L = ["# summary (generated by summarise_heldout.py; measured, unreplicated, open loop, frozen #178 scales)", ""]
    L.append(f"layers done: {len(s['layers_done'])} of 16; prompts: {len(s['prompts'])}")
    for a, v in s["arms"].items():
        L += ["", f"## {a}: H_R {v['H_R']}, H_F {v['H_F']} (valid {v['valid']})",
              f"range-fail layers {v['layers_range_fail']}, fidelity-fail layers {v['layers_fid_fail']}, clamped {v['total_clamped']}, guard failures {v['total_guard_failures']}",
              f"pooled n={v['pooled']['n']} median {v['pooled']['median']:.5f} max {v['pooled']['max']:.5f} >0.01 {v['pooled']['n_over_001']} >0.05 {v['pooled']['n_over_005']}", "",
              "| layer | Eq Ek Ev sh | clamped q/k/v (of q_n, k_n) | max qw kw vw | median | max | >0.01 | >0.05 | R | F |", "|---|---|---|---|---|---|---|---|---|---|"]
        for x in v["layers"]:
            sc = x["scales"]
            L.append(f"| {x['layer']} | {sc['Eq']} {sc['Ek']} {sc['Ev']} {sc['sh']} | {x['q_over']}/{x['k_over']}/{x['v_over']} (of {x['q_n']}, {x['k_n']}) | "
                     f"{x['q_maxw']} {x['k_maxw']} {x['v_maxw']} | {x['rel_median']:.5f} | {x['rel_max']:.5f} | {x['n_over_001']} | {x['n_over_005']} | "
                     f"{'yes' if x['range_pass'] else 'no'} | {'yes' if x['fid_pass'] else 'no'} |")
    return "\n".join(L) + "\n"

def main():
    ind = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "runs"
    outd = Path(sys.argv[2]) if len(sys.argv) > 2 else ind
    man = json.load(open(HERE / "prompts-heldout.json"))
    sys.path.insert(0, str(HERE)); import heldout as H
    table = {k: dict(v) for k, v in H.load_table().items()}
    try:
        ntok = {}
        for p in man["prompts"]:
            if not is_int(p.get("n_tokens")) or p["n_tokens"] <= 0 or p["n_tokens"] != len(p.get("token_ids", [])):
                raise Refuse(f"manifest n_tokens of {p.get('id')} is not the length of its token ids")
            ntok[p["id"]] = p["n_tokens"]
        if sum(ntok.values()) != man.get("total_tokens"): raise Refuse("manifest total_tokens disagrees with its prompts")
        s = summarise(ind, [p["id"] for p in man["prompts"]], tuple(man["determinism_subset"]), table, ntok)
    except Refuse as e:
        print("REFUSED:", e); raise SystemExit(2)
    (outd / "summary.json").write_text(json.dumps(s, indent=1) + "\n"); (outd / "summary.md").write_text(md(s))
    print(json.dumps({a: (v["H_R"], v["H_F"]) for a, v in s["arms"].items()}))

if __name__ == "__main__": main()
