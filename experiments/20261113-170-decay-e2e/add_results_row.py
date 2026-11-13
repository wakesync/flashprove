#!/usr/bin/env python3
"""Insert (or replace) the qwen-decay-e2e row in research/results.yaml from runs/summary.json.
Usage: add_results_row.py <commit sha holding runs/summary.json> <pr number> <YYYY-MM-DD>"""
import json, math, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; Y = ROOT / "research" / "results.yaml"
C, PR, D = sys.argv[1], int(sys.argv[2]), sys.argv[3]
X = "experiments/20261113-170-decay-e2e"; SRC = f"{X}/runs/summary.json"; HW = "cpu-epyc-rome-kvm-16"
S = json.load(open(HERE / "runs" / "summary.json"))
ARMS = ["XS18", "XS18+U4", "XS18+U3"]
NOTE = ("abliterated leg, teacher forced, 10 frozen prompts; XS18 DeltaNet heads with the decay a replaced by PR #159's table "
        "emulation shifted 2^-20 -> 2^-18 (round half up); in_proj/out_proj/attention/MLP/norms/lm_head float64; no proof; "
        "one deterministic run, spread is over positions")

def g(v): return float(f"{v:.4g}")
def m(name, stat, value, unit, n, spread=None, arm=None, series=None, total=None, note=None):
    d = dict(name=name)
    if series: d["series"] = series
    if arm: d["arm"] = arm
    d.update(stat=stat, value=value)
    if total is not None: d["total"] = total
    d.update(unit=unit, n=n, spread=spread, hardware=HW, date=D, commit=C, source=SRC)
    if note: d["note"] = note
    return "      - " + json.dumps(d)

V = S["verdicts"]; rows = []
if "cells" in S:
    for a in ARMS:
        c = S["cells"][a]; k = a.lower().replace("+", "_")
        rows.append(m(f"top1_agree_{k}_abl", "count", c["top1"], "count", 1461, total=1461, arm=f"{a} abl", series="decay-e2e-top1",
                      note=f"positions where the arm's argmax equals REF's; bar >= 99%; {V[a]} vs prereg; {NOTE}"))
        if math.isfinite(c["kl_max"]):
            rows.append(m(f"kl_median_{k}_abl", "median", g(c["kl_median"]), "ratio", 1461, arm=f"{a} abl", series="decay-e2e-kl",
                          spread=dict(sd=g(c["kl_sd_finite"]), min=None, max=g(c["kl_max"])),
                          note=f"KL(REF || arm) in nats over 1,461 positions; bar median <= 1e-4, max <= 0.1; SD over positions; {NOTE}"))
    status = "measured" if V["XS18+U4"] == "PASS" and V["XS18+U3"] == "PASS" else "negative"
    if any(v.startswith("KILLED") for v in V.values()): status = "negative"
    cells = "; ".join(f"{a} {S['cells'][a]['top1']}/1461 top-1, KL median {S['cells'][a]['kl_median']:.2g} max {S['cells'][a]['kl_max']:.2g} nats ({V[a]})" for a in ARMS)
    summary = (f"H (XS18+U4 keeps PR #124's bar with no extra flip at REF margin > 0.01) {'holds' if S['H_holds'] else 'does not hold'}. {cells}. "
               f"Control XS18 reproduces PR #124's committed abl numbers: {S['control']['reproduced']}. Proxy fidelity only: no proof, tables emulated")
    rep = "unreplicated"
else:
    rows.append(m("decay_e2e_layers_done_abl", "count", S["layers_done"], "count", 1, total=64,
                  note=f"layers of the abl leg finished before the registered hard stop; every arm KILLED (logits not produced); {NOTE}"))
    status = "in progress"; rep = "n/a"
    summary = (f"KILLED vs prereg: the registered run reached {S['layers_done']} of 64 layers before the hard stop (the heavy-CPU slot was "
               "held by another lane until shortly before it); no logits, no verdict for XS18, XS18+U4 or XS18+U3")
entry = f'''  - id: qwen-decay-e2e
    title: "Qwen3.8-27B abliterated end to end: PR #159's U4 / U3 table decays inside XS18's DeltaNet heads vs float64, token agreement"
    status: {status}
    replication: {rep}
    pr: {PR}
    summary: {json.dumps(summary)}
    conditions: "teacher-forced on PR #124's 10 frozen prompts (1,461 positions), abl leg only (stock layers 0 to 16, byte-identical, then abl 17 to 63); only the DeltaNet head computation is lowered (XS18), and in the U arms only its decay a; decay tables emulated as PR #159, U4 rows float64; CPU, one deterministic run, shared loaded host, no proof"
    evidence: [{X}/RESULTS.md]
    metrics:
''' + "\n".join(rows) + "\n\n"
t = Y.read_text()
start = t.find("  - id: qwen-decay-e2e\n")
if start >= 0:
    end = t.find("\n  - id: ", start + 5); t = t[:start] + t[end + 1:]
anchor = "  - id: qwen-e2e-agreement\n"
assert t.count(anchor) == 1
Y.write_text(t.replace(anchor, entry + anchor)); print("inserted", len(rows), "metrics, status", status)
