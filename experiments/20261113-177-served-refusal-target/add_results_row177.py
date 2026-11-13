#!/usr/bin/env python3
"""Insert (or replace) the qwen-served-refusal-target row in research/results.yaml from runs/summary.json.
Usage: add_results_row177.py <commit holding runs/summary.json> <pr number> <YYYY-MM-DD>"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; Y = ROOT / "research" / "results.yaml"
C, PR, D = sys.argv[1], int(sys.argv[2]), sys.argv[3]
X = "experiments/20261113-177-served-refusal-target"; SRC = f"{X}/runs/summary.json"; HW = "cpu-epyc-rome-kvm-16"
S = json.load(open(HERE / "runs" / "summary.json"))
ref = [p for p in S["prompts"] if p["kind"] == "refusal-type"]
NOTE = ("greedy replies (temperature 0, max 48 tokens) from an attested H200 serving deployment (vLLM, BF16) of the abliterated "
        "checkpoint, token ids rebuilt from text and checked against served counts only; teacher-forced on CPU, float64 stock and "
        "float64 abliterated; one deterministic CPU run, spread over prompts; no proof; one fixture, not a detector")
def g(v): return float(f"{v:.4g}")
def m(name, stat, value, unit, n, spread=None, note=None, total=None):
    d = dict(name=name, stat=stat, value=value)
    if total is not None: d["total"] = total
    d.update(unit=unit, n=n, spread=spread, hardware=HW, date=D, commit=C, source=SRC)
    if note: d["note"] = note
    return "      - " + json.dumps(d)
H0 = S["H0"]; sp = S["refusal_type_spread"]
nref = sum(p["all"]["n"] for p in ref); nwin = sum(p["window"]["n"] for p in ref)
rows = [
 m("served177_abl_eq_served", "count", H0["abl_eq_served"], "count", H0["positions"], total=H0["positions"],
   note=f"reply positions (8 prompts) where float64 abliterated argmax = served token; bar >= 98% (H0); {NOTE}"),
 m("served177_stock_ne_served_refusal", "count", sum(p["all"]["stock_ne_served"] for p in ref), "count", nref, total=nref,
   note=f"reply positions of the 6 refusal-type prompts where float64 stock argmax != served token; {NOTE}"),
 m("served177_separating_refusal_window", "count", sum(p["window"]["separating"] for p in ref), "count", nwin, total=nwin,
   note=f"refusal-type reply positions inside a 64-token window where stock != served and abliterated = served (H1 needs >= 1); {NOTE}"),
 m("served177_stock_ne_served_share_refusal", "median", g(sp["stock_ne_served_share_all"]["median"]), "fraction", 6,
   spread=dict(sd=None, min=g(sp["stock_ne_served_share_all"]["min"]), max=g(sp["stock_ne_served_share_all"]["max"])),
   note=f"per refusal-type prompt share of reply positions where stock != served, median over 6 prompts; {NOTE}"),
 m("served177_refusal_rule_true", "count", len(S["refusal_rule_true"]), "count", 8, total=8,
   note="served replies matching the registered refusal string rule (PREREG), 6 refusal-type + 2 controls"),
]
t = S["target"]
tgt = (f"Target by the registered rule: {t['id']} (reply ids sha256 {t['reply_ids_sha256'][:16]}..., stock != served at "
       f"{t['window_stock_ne_served']} of {t['window_positions']} in-window reply positions, prompt + reply fits 64 tokens: {t['fits_64']})"
       if t else "No target named (no in-window stock != served position on any refusal-type prompt)")
summ = (f"{S['verdict']} vs prereg. Float64 abliterated picks the served token at {H0['abl_eq_served']} of {H0['positions']} reply positions "
        f"(bar 0.98). On the 6 refusal-type replies float64 stock differs from the served token at "
        f"{sum(p['all']['stock_ne_served'] for p in ref)} of {nref} positions; separating positions inside a 64-token window: "
        f"{sum(p['window']['separating'] for p in ref)} of {nwin}. Registered refusal string rule true for {len(S['refusal_rule_true'])} of 8 replies. "
        f"{tgt}. Reply text not published (issue #177). Measured, unreplicated")
block = "\n".join([
    "  - id: qwen-served-refusal-target",
    '    title: "Qwen3.8-27B: on served greedy replies to refusal-type prompts, does float64 stock pick different tokens than float64 abliterated (DESIGN section 10 target)?"',
    "    status: measured", "    replication: unreplicated", f"    pr: {PR}",
    "    summary: " + json.dumps(summ),
    '    conditions: "6 refusal-type prompts (break-in, lock, paywall, ticket) + 2 harmless controls, greedy replies (temperature 0, seed 123, max 48 tokens) from an attested H200 serving deployment (vLLM, BF16; model identity as reported by its configuration, not hashed); ids rebuilt from text, checked against served counts only; teacher-forced float64 forwards of stock and abliterated on CPU (PR #88/#124/#139/#162 code unchanged); one deterministic run; no proof; reply text of refusal-type prompts not published"',
    f"    evidence: [{X}/RESULTS.md]", "    metrics:"] + rows) + "\n"
txt = Y.read_text()
if "  - id: qwen-served-refusal-target\n" in txt:
    a = txt.index("  - id: qwen-served-refusal-target\n"); b = txt.find("\n  - id: ", a + 5); b = len(txt) if b < 0 else b + 1
    txt = txt[:a] + block + ("\n" if b < len(txt) else "") + txt[b:]
else:
    txt = txt.rstrip("\n") + "\n\n" + block
Y.write_text(txt); print(block)
