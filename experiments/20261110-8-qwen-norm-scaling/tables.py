#!/usr/bin/env python3
"""Markdown tables for RESULTS.md from runs/*.summary.json, runs/cost.json, runs/cmp-ckpt.json. Prints to stdout and
writes runs/tables.md. Arms that did not run are listed as not run."""
import json
from pathlib import Path
R = Path(__file__).resolve().parent / "runs"
H = Path(__file__).resolve().parent
out = []
def P(s=""): out.append(s)
def load(n):
    p = R / n
    return json.load(open(p)) if p.exists() else {}
def g(x): return f"{x:.3g}"
cand, loc, cost = load("cand-stock.summary.json"), load("local-stock.summary.json"), load("cost.json")
arms_c = list(json.load(open(H / "arms-cand.json")))
arms_l = list(json.load(open(H / "arms-local.json")))

P("### Candidates: fidelity (stock, n = 480 (prompt, head) pairs per arm)\n")
P("| arm | n | rel_y median (min / max) | rel_S median (min / max) | layer-level rel_y median (n = 10) | pairs inside every stated bound | fidelity | verdict |")
P("|---|---|---|---|---|---|---|---|")
for a in arms_c:
    d = cand.get(a)
    if not d or not d.get("n"):
        P(f"| {a} | 0 | not run | | | | | not measured |"); continue
    y, s = d["rel_y"], d["rel_S"]
    P(f"| {a} | {d['n']} | {g(y['median'])} ({g(y['min'])} / {g(y['max'])}) | {g(s['median'])} ({g(s['min'])} / {g(s['max'])}) | "
      f"{g(d['layer_rel_y']['median'])} | {d['pairs_in_bounds']} / {d['n']} | {'meets' if d['fidelity_pass'] else 'misses'} | {'PASS' if d['pass'] else 'fail'} |")

P("\n### Candidates: range-checked classes, maximum over the 480 pairs (signed bits needed)\n")
cls = ("S", "M", "delta", "o", "Sigma", "w", "shift", "xin", "v", "ar", "br", "z", "cg", "y", "sigma", "Rc", "Vx", "aP", "oRc", "cgw")
P("| arm | " + " | ".join(cls) + " | classes over their stated bound (pairs) |")
P("|---|" + "---|" * (len(cls) + 1))
for a in arms_c:
    d = cand.get(a)
    if not d or not d.get("n"): P(f"| {a} | not run |" + " |" * len(cls)); continue
    cells = [f"{d['max'][k]:.4g} ({d['bits_signed'][k]})" if k in d["max"] else "" for k in cls]
    ov = ", ".join(f"{k} {v}" for k, v in d["pairs_over_by_class"].items()) or "none"
    P(f"| {a} | " + " | ".join(cells) + f" | {ov} |")

P("\n### Candidates: counted cost per head per token (COUNTED, NOT BUILT; delta against M2 arm B)\n")
P("| arm | LKP keys | gate columns | RNG cells | relations | delta keys | delta columns | delta cells | head total at T = 16 (columns + cells + keys) |")
P("|---|---|---|---|---|---|---|---|---|")
for a in arms_c:
    v = cost.get(a)
    if not v: P(f"| {a} | not counted (descriptive arm) | | | | | | | |"); continue
    p, d = v["per_head_token"], v["delta_vs_M2"]
    P(f"| {a} | {p['keys']:,} | {p['cols']:,} | {p['rcells']:,} | {p['rels']:,} | {d['keys']:+,} | {d['cols']:+,} | {d['rcells']:+,} | {v['T16_entries']:,} |")

P("\n### Error of the layer-0 mixer output against the residual stream it is added to (descriptive)\n")
P("e = ||W_o (y_int - y_f)|| / ||x||, Frobenius over the tokens of a prompt, n = 10 prompts; token-level maximum over 2,396 tokens.\n")
P("| arm | e median over prompts (min / max) | e per token: median of prompt medians | e per token: max | rel_y layer-level median |")
P("|---|---|---|---|---|")
bf = None
for a in arms_c:
    d = cand.get(a)
    if not d or not d.get("n"): P(f"| {a} | not run | | | |"); continue
    f = d["resid_frob"]; bf = d
    P(f"| {a} | {g(f['median'])} ({g(f['min'])} / {g(f['max'])}) | {g(d['resid_tok_median'])} | {g(d['resid_tok_max'])} | {g(d['layer_rel_y']['median'])} |")
if bf:
    f = bf["resid_bf16_frob"]; m = bf["mixer_over_resid_frob"]
    P(f"| BF16 emulation | {g(f['median'])} ({g(f['min'])} / {g(f['max'])}) | | {g(bf['resid_bf16_tok_max'])} | {g(bf['layer_bf16_rel_y']['median'])} |")
    P(f"\nSize of the float mixer output itself against the residual stream, ||W_o y_f|| / ||x||: median {g(m['median'])} (min {g(m['min'])}, max {g(m['max'])}), n = 10 prompts.")

P("\n### Localisation at the M2 configuration (stock, n = 480 pairs per arm)\n")
P("| arm | what is exact | n | rel_y median (min / max) | rel_S median (min / max) | layer-level rel_y median |")
P("|---|---|---|---|---|---|")
la = json.load(open(H / "arms-local.json"))
for a in arms_l:
    d = loc.get(a); ex = la[a]["cfg"].get("exact", [])
    what = "nothing (M2)" if not ex else ("everything" if len(ex) == 16 else (", ".join(ex) if len(ex) <= 8 else "all but " + ", ".join(x for x in
           ("in_qkv", "in_ab", "in_z", "conv", "silu", "l2n", "gates", "mem", "delta", "state", "o", "sigma", "rc", "w", "cg", "y") if x not in ex)))
    if not d or not d.get("n"): P(f"| {a} | {what} | 0 | not run | | |"); continue
    y, s = d["rel_y"], d["rel_S"]
    P(f"| {a} | {what} | {d['n']} | {g(y['median'])} ({g(y['min'])} / {g(y['max'])}) | {g(s['median'])} ({g(s['min'])} / {g(s['max'])}) | {g(d['layer_rel_y']['median'])} |")
(R / "tables.md").write_text("\n".join(out) + "\n"); print("\n".join(out))
