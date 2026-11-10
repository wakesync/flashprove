#!/usr/bin/env python3
"""Insert the Q1 row into research/results.yaml, before the glm-kda-model-scale entry. One-off, idempotent.
Usage: add_results_row.py <commit sha holding runs/summary.json>"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
Y = ROOT / "research" / "results.yaml"
C = sys.argv[1]
S = "experiments/20261110-8-qwen-q1-deep-fidelity/runs/summary.json"
E = "experiments/20261110-8-qwen-q1-deep-fidelity/runs/e2e-stock.json"
U = "experiments/20261110-8-qwen-q1-deep-fidelity/runs/u1-layer20.jsonl"
H = "cpu-epyc-rome-kvm-16"
D = "2026-11-10"

def m(name, stat, value, unit, n, src=S, spread=None, arm=None, series=None, total=None, note=None):
    parts = [f"name: {name}"]
    if series: parts.append(f"series: {series}")
    if arm: parts.append(f'arm: "{arm}"')
    parts += [f"stat: {stat}", f"value: {value}"]
    if total is not None: parts.append(f"total: {total}")
    parts += [f"unit: {unit}", f"n: {n}"]
    parts.append("spread: null" if spread is None else "spread: {sd: null, min: %s, max: %s}" % spread)
    parts += [f"hardware: {H}", f"date: {D}", f"commit: {C}", f"source: {src}"]
    if note: parts.append(f'note: "{note}"')
    return "      - {" + ", ".join(parts) + "}"

NB = "per (prompt, head) relative L2 error of the gated-norm output vs float64; bar median <= 0.01 and max <= 0.05; integer reference arithmetic, no proof, not a sound lowering"
rows = [
    m("q1_arms_passing", "count", 0, "count", 480, total=42, note="14 arms x 3 targets (stock L16, stock L20, abl L20), 480 pairs each; every arm 480/480 in stated honest classes and 0 guard errors; all fail on max rel_y"),
    m("rel_y_xs18_t16", "median", 0.00289, "ratio", 480, spread=(0.000888, 0.378), arm="XS18 T16", series="q1-rel-y", note=NB + "; XS18 = PR 74 X3-r2"),
    m("rel_y_xs18_t20s", "median", 0.00192, "ratio", 480, spread=(0.000256, 0.249), arm="XS18 T20s", series="q1-rel-y", note=NB),
    m("rel_y_xs18_t20a", "median", 0.00199, "ratio", 480, spread=(0.000267, 0.247), arm="XS18 T20a", series="q1-rel-y", note=NB),
    m("rel_y_xs20_t16", "median", 0.00158, "ratio", 480, spread=(0.000658, 0.107), arm="XS20 T16", series="q1-rel-y", note="best arm on T16, still fails max; " + NB),
    m("rel_y_xs20_t20s", "median", 0.00122, "ratio", 480, spread=(0.000237, 0.0737), arm="XS20 T20s", series="q1-rel-y", note="best arm on T20s, fails max"),
    m("rel_y_xs20_t20a", "median", 0.00123, "ratio", 480, spread=(0.000256, 0.0734), arm="XS20 T20a", series="q1-rel-y", note="best arm on T20a, fails max"),
    m("rel_y_c4p_t20s", "median", 0.0653, "ratio", 480, spread=(0.00538, 3.6), arm="C4P T20s", series="q1-rel-y", note="PR 74 best registered arm at layer 0, measured at stock layer 20"),
    m("e2e_stock_xs18_top1_agree", "count", 96, "count", 96, src=E, total=96, note="descriptive, no threshold: every DeltaNet layer's heads replaced by XS18, rest float64, 4 short prompts (p01, p07, p08, p09), stock only; KL(REF || INT) median 1.59e-7, max 0.00251 nats (runs/summary.json; the ledger has no nats unit); abliterated end-to-end not finished"),
    m("u1_l20_mix_diff_over_resid", "median", 0.002676, "ratio", 10, src=S, spread=(0.001231, 0.004598), note="stock vs abl float64 mixer-output difference at layer 20 over the residual norm, per prompt; descriptive size comparison, not a detection result"),
]
entry = f'''  - id: qwen-q1-deep-fidelity
    title: "Qwen3.8-27B real weights, layers 16 and 20 (stock and abliterated): integer DeltaNet head lowerings vs float64, plus a stock end-to-end subset"
    status: negative
    replication: unreplicated
    pr: 88
    summary: "FAIL vs prereg: none of 14 arms meets the A2 bar on any of 3 targets (stock layer 16, stock layer 20, abl layer 20); H1 (XS18 = PR 74 X3-r2 passes all three) is false. XS18 median rel_y 0.00289 / 0.00192 / 0.00199 is under 0.01, but max is 0.378 / 0.249 / 0.247 against 0.05, from a few pairs mostly on the repeated-word prompt; best arm XS20 still has max 0.107 / 0.0737 / 0.0734. No state scale up to 2^20 makes the slow-decay heads pass on every target (T16 slow max 0.0791 at XS20). Descriptive: with every DeltaNet layer's heads replaced by XS18, the stock model keeps top-1 on 96 of 96 positions of 4 short prompts (KL median 1.6e-7 nats, max 0.0025). The abliterated end-to-end stage stopped at layer 45 and is not finished"
    conditions: "per-layer open-loop at layers 16 and 20, 48 V heads, 10 frozen prompts (2,396 tokens), float64 reference forward reimplemented in numpy, CPU, one deterministic run, no proof; arms are numerical lowerings, not sound (PR 74 RESULTS 8.2); in_proj, out_proj, attention, MLP and lm_head stay float64; end-to-end on 4 short prompts (96 positions), stock only; abl end-to-end (stage E) not finished after the owning session was lost; scratch prefix in six time -v headers replaced by a placeholder before commit"
    evidence: [experiments/20261110-8-qwen-q1-deep-fidelity/RESULTS.md]
    metrics:
''' + "\n".join(rows) + "\n\n"
t = Y.read_text()
if "id: qwen-q1-deep-fidelity" in t:
    print("already present"); sys.exit(0)
anchor = "  - id: glm-kda-model-scale\n"
assert t.count(anchor) == 1
Y.write_text(t.replace(anchor, entry + anchor))
print("inserted", len(rows), "metrics")
