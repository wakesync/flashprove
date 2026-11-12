#!/usr/bin/env python3
"""Insert (or replace) the qwen-served-reply-agreement row in research/results.yaml from runs/summary.json.
Usage: add_results_row.py <commit sha holding runs/summary.json> <pr number> <YYYY-MM-DD>"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; Y = ROOT / "research" / "results.yaml"
C, PR, D = sys.argv[1], int(sys.argv[2]), sys.argv[3]
X = "experiments/20261112-131-served-reply-agreement"
SRC = f"{X}/runs/summary.json"; HW = "cpu-epyc-rome-kvm-16"
S = json.load(open(HERE / "runs" / "summary.json"))
NOTE = ("replies generated greedily by an attested H200 serving deployment (vLLM, BF16) of the abliterated checkpoint, "
        "teacher-forced on CPU; only the DeltaNet heads are integer, the rest float64; token ids rebuilt from text and checked "
        "against served counts only; no proof; one deterministic CPU run, spread is over prompts")

def m(name, value, n, arm, series, note):
    d = dict(name=name, series=series, arm=arm, stat="count", value=value, total=n, unit="count", n=n, spread=None,
             hardware=HW, date=D, commit=C, source=SRC, note=note)
    return "      - " + json.dumps(d)

N = S["measured_positions"]; c = S["pooled"]["counts"]; V = S["verdict"]
sp = S["spread_over_prompts"]
def spr(k): return f"per-prompt fraction median {sp[k]['median']:.3g}, min {sp[k]['min']:.3g}, max {sp[k]['max']:.3g}"
rows = [
    m("served_eq_ref", c["REF_s"], N, "float64 REF", "served-top1", f"reply positions where float64 argmax = served token; bar >= 98% (H0 {V['H0']}); {spr('REF_served')}; {NOTE}"),
    m("served_eq_xs18", c["XS18_s"], N, "XS18", "served-top1", f"reply positions where XS18 argmax = served token; bar >= 98% (H1 {V['H1_XS18']}); {spr('XS18_served')}; {NOTE}"),
    m("served_eq_xs20", c["XS20_s"], N, "XS20", "served-top1", f"reply positions where XS20 argmax = served token; bar >= 98% (H2 {V['H2_XS20']}); {spr('XS20_served')}; {NOTE}"),
    m("ref_eq_xs18", c["XS18_r"], N, "XS18", "ref-top1", f"reply positions where XS18 argmax = float64 argmax; bar >= 99%; {NOTE}"),
    m("ref_eq_xs20", c["XS20_r"], N, "XS20", "ref-top1", f"reply positions where XS20 argmax = float64 argmax; bar >= 99%; {NOTE}"),
    m("prompts_included", S["n_included"], S["n_included"] + S["n_excluded"], "rebuild", "served-ids",
      "prompts whose rebuilt prompt and reply token counts both equal the served usage counts (registered inclusion rule)"),
]
allpass = all(v == "PASS" for v in V.values())
status = "measured" if allpass else "negative"
summary = (f"H0 (float64 picks served token >= 98%) {V['H0']}, H1 XS18 {V['H1_XS18']}, H2 XS20 {V['H2_XS20']}. "
           f"Of {N} reply positions in {S['n_included']} greedy served replies: float64 picks the served token at {c['REF_s']}, "
           f"XS18 at {c['XS18_s']}, XS20 at {c['XS20_s']}; XS18 / XS20 equal float64 at {c['XS18_r']} / {c['XS20_r']}. "
           f"Whole replies reproduced (every position): float64 {sum(r['whole_reply']['REF'] for r in S['per_prompt'])}, "
           f"XS18 {sum(r['whole_reply']['XS18'] for r in S['per_prompt'])}, XS20 {sum(r['whole_reply']['XS20'] for r in S['per_prompt'])} "
           f"of {S['n_included']}. Serving text identical over 3 repetitions for "
           f"{sum(r['reps_text_identical'] for r in S['per_prompt'])} of {S['n_included']} prompts. Proxy fidelity only: no proof")
entry = f'''  - id: qwen-served-reply-agreement
    title: "Qwen3.8-27B abliterated: do float64 and XS18 / XS20 integer DeltaNet heads pick the tokens a BF16 serving deployment generated?"
    status: {status}
    replication: unreplicated
    pr: {PR}
    summary: {json.dumps(summary)}
    conditions: "10 ordinary prompts, greedy replies (temperature 0, at most 64 tokens) from an attested H200 serving deployment (vLLM, BF16; model identity as reported by its configuration, not hashed); token ids rebuilt from text with the pinned tokenizer and template, checked against served usage counts only; teacher-forced on CPU through all 64 layers, only the DeltaNet head computation integer; one deterministic CPU run, no proof"
    evidence: [{X}/RESULTS.md]
    metrics:
''' + "\n".join(rows) + "\n\n"
t = Y.read_text()
start = t.find("  - id: qwen-served-reply-agreement\n")
if start >= 0:
    end = t.find("\n  - id: ", start + 5); t = t[:start] + t[end + 1:]
anchor = "  - id: qwen-e2e-agreement\n"
assert t.count(anchor) == 1
Y.write_text(t.replace(anchor, entry + anchor)); print("inserted", len(rows), "metrics, status", status)
