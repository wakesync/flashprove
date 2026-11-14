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

Usage: summarise_heldout.py [<in_dir> [<out_dir>]]   (defaults: runs/ and runs/)
"""
import json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ARMS = {"C2047": 2047, "C1665": 1665}
LAYERS = list(range(3, 64, 4))
NH = 24
BAR_MED, BAR_MAX = 0.01, 0.05

class Refuse(Exception): pass

def jl(p):
    if not p.exists(): raise Refuse(f"missing file {p.name}")
    out = []
    for n, line in enumerate(p.read_text().splitlines()):
        if not line.strip(): continue
        try: out.append(json.loads(line))
        except json.JSONDecodeError: raise Refuse(f"malformed line {n} in {p.name}")
    return out

def summarise(ind, prompts, det, table):
    lay, cells, prows, tim = jl(ind / "layers.jsonl"), jl(ind / "cells.jsonl"), jl(ind / "prompt-rows.jsonl"), jl(ind / "attn-timing.jsonl")
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
        if r is not None and not isinstance(r, (int, float)): raise Refuse(f"bad rel_y {k}")
        cset[k] = r
    for p in prows:
        k = (p.get("arm"), p.get("layer"), p.get("prompt"))
        if k[0] not in ARMS or k[1] not in LAYERS or k[2] not in prompts: raise Refuse(f"unexpected prompt row {k}")
        if k in pset: raise Refuse(f"duplicate prompt row {k}")
        pset[k] = p
    tset = {}
    for t in tim:
        if t.get("layer") not in LAYERS or t.get("layer") in tset: raise Refuse(f"bad or duplicate timing row {t.get('layer')}")
        tset[t["layer"]] = t
    rec_layers = {l for l, _ in keys}
    for k in list(cset) + [k + (None,) for k in pset]:
        if k[1] not in rec_layers: raise Refuse(f"cell or prompt row for an unrecorded layer {k[:3]} (interrupted layer)")
    per_arm = {a: [] for a in ARMS}
    for r in lay:
        a, l = r["arm"], r["layer"]; cl = ARMS[a]
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
        arr = np.array(good) if good else np.array([np.nan])
        med, mxv = float(np.median(arr)), float(arr.max())
        if good and (abs(med - r["rel_median"]) > 0 or abs(mxv - r["rel_max"]) > 0): raise Refuse(f"statistics of {a} {l} disagree with cells")
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
    try: s = summarise(ind, [p["id"] for p in man["prompts"]], tuple(man["determinism_subset"]), table)
    except Refuse as e:
        print("REFUSED:", e); raise SystemExit(2)
    (outd / "summary.json").write_text(json.dumps(s, indent=1) + "\n"); (outd / "summary.md").write_text(md(s))
    print(json.dumps({a: (v["H_R"], v["H_F"]) for a, v in s["arms"].items()}))

if __name__ == "__main__": main()
