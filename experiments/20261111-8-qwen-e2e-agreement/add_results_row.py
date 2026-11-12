#!/usr/bin/env python3
"""Insert (or replace) the qwen-e2e-agreement row in research/results.yaml from runs/summary.json.
Usage: add_results_row.py <commit sha holding runs/summary.json> <pr number> <YYYY-MM-DD>"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; Y = ROOT / "research" / "results.yaml"
C, PR, D = sys.argv[1], int(sys.argv[2]), sys.argv[3]
X = "experiments/20261111-8-qwen-e2e-agreement"
SRC = f"{X}/runs/summary.json"; HW = "cpu-epyc-rome-kvm-16"
S = json.load(open(HERE / "runs" / "summary.json"))
NOTE = ("teacher-forced, every DeltaNet layer's heads by the arm, in_proj/out_proj/attention/MLP/norms/lm_head float64; "
        "integer reference arithmetic, no proof, not a sound lowering; one deterministic run, spread is over positions")

def g(v): return float(f"{v:.4g}")
def m(name, stat, value, unit, n, spread=None, arm=None, series=None, total=None, note=None, src=SRC):
    d = dict(name=name)
    if series: d["series"] = series
    if arm: d["arm"] = arm
    d.update(stat=stat, value=value)
    if total is not None: d["total"] = total
    d.update(unit=unit, n=n, spread=spread, hardware=HW, date=D, commit=C, source=src)
    if note: d["note"] = note
    return "      - " + json.dumps(d)

rows, verdict = [], {}
for leg in ("stock", "abl"):
    L = S["legs"][leg]
    if not L.get("finished"):
        verdict[leg] = None; continue
    for arm in ("XS18", "XS20"):
        c = L["cells"][arm]; a = arm.lower(); verdict[(leg, arm)] = c["PASS"]
        rows.append(m(f"top1_agree_{a}_{leg}", "count", c["agree"], "count", c["n"], total=c["n"], arm=f"{arm} {leg}",
                      series="e2e-top1", note=f"positions where the arm's argmax equals REF's; bar >= 99%; {NOTE}; "
                                               f"{'PASS' if c['PASS'] else 'FAIL'} vs prereg"))
        sp = c["spread_over_prompts"]["kl_median"]
        rows.append(m(f"kl_median_{a}_{leg}", "median", g(c["kl_median"]), "ratio", c["n"], arm=f"{arm} {leg}", series="e2e-kl",
                      spread=dict(sd=g(c["kl_sd"]), min=g(c["kl_min"]), max=g(c["kl_max"])),
                      note=f"KL(REF || arm) in nats (the ledger has no nats unit) over 1,461 positions; bar median <= 1e-4, max <= 0.1; "
                           f"SD = sample SD over positions of one run; per-prompt medians range {sp['min']:.3g} to {sp['max']:.3g}; {NOTE}"))
    b = L["context"]["BF16H"]
    rows.append(m(f"kl_median_bf16h_{leg}", "median", g(b["kl_median"]), "ratio", b["n"], arm=f"BF16H {leg}", series="e2e-kl",
                  spread=dict(sd=g(b["kl_sd"]), min=g(b["kl_min"]), max=g(b["kl_max"])),
                  note="context only, no bar: BF16-cast heads with FP32 recurrence, rest float64, 5 prompts (608 positions); nats"))
    rows.append(m(f"determinism_{leg}", "count", int(L["deterministic"]), "count", 1, total=1,
                  note="REF#2 and XS18#2 on p01, p04, p09 bit-identical to REF and XS18 at every layer and in the logit metrics (1 = yes)"))
H = S["hypotheses"]
status = "measured" if H["H1"] and H["H2"] else "negative"
def word(v): return "not finished" if v is None else ("PASS" if v else "FAIL")
cells = "; ".join(f"{arm} {leg} {S['legs'][leg]['cells'][arm]['agree']}/{S['legs'][leg]['cells'][arm]['n']} top-1, KL median "
                  f"{S['legs'][leg]['cells'][arm]['kl_median']:.2g} max {S['legs'][leg]['cells'][arm]['kl_max']:.2g} nats ({word(verdict[(leg, arm)])})"
                  for leg in ("stock", "abl") if S["legs"][leg].get("finished") for arm in ("XS18", "XS20"))
summary = (f"{'PASS' if status == 'measured' else 'FAIL or partial'} vs prereg: H1 (XS18 both checkpoints) {word(H['H1'])}, "
           f"H2 (XS20 both) {word(H['H2'])}. {cells}. Bar: top-1 >= 99%, KL median <= 1e-4, max <= 0.1 nats. "
           "In every cell the largest single-position KL is on the repeated-word prompt, where most closed-loop per-head errors over 0.05 "
           "also sit (descriptive co-occurrence, not attribution); the 3 top-1 flips are on the digits prompt at REF top-1 margins under "
           "0.01 logits. Proxy fidelity only: no proof, arms not sound")
entry = f'''  - id: qwen-e2e-agreement
    title: "Qwen3.8-27B end to end, stock and abliterated: next-token agreement with XS18 / XS20 integer DeltaNet heads in every layer vs float64"
    status: {status}
    replication: unreplicated
    pr: {PR}
    summary: {json.dumps(summary)}
    conditions: "teacher-forced on 10 frozen prompts (1,461 positions, 3 of them >= 256 tokens, incl. 512 repeated-word tokens), all 64 layers, float64 reference forward reimplemented in numpy; only the DeltaNet head computation is lowered (in_proj, out_proj, attention, MLP, norms, lm_head float64); CPU, one deterministic run (repeats would be identical; duplicate-path determinism check), shared loaded host, no proof, arms not sound; abl = stock layers 0 to 16 (byte-identical) then abl 17 to 63"
    evidence: [{X}/RESULTS.md]
    metrics:
''' + "\n".join(rows) + "\n\n"
t = Y.read_text()
start = t.find("  - id: qwen-e2e-agreement\n")
if start >= 0:
    end = t.find("\n  - id: ", start + 5); t = t[:start] + t[end + 1:]
anchor = "  - id: qwen-q1-deep-fidelity\n"
assert t.count(anchor) == 1
Y.write_text(t.replace(anchor, entry + anchor)); print("inserted", len(rows), "metrics, status", status)
