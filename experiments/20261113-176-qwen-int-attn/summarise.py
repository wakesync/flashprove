#!/usr/bin/env python3
"""Apply the PREREG bar to runs/layers.jsonl and runs/cells.jsonl -> runs/summary.json, runs/summary.md.

Per arm: every one of the 16 attention layers must have median rel_y <= 0.01 and max <= 0.05 over its 240
(prompt, head) pairs (recomputed here from cells.jsonl, cross-checked against layers.jsonl), and the determinism
check (C2047 twice on p01 and p09, bit-identical integer o) must hold on every layer. A run with fewer than 16
attention layers gets no all-layer verdict.

Input validation (PREREG Amendments, 2026-11-13, added after the registered run, in review): before anything is
computed or written, the records are checked against the registered Cartesian product. The summariser REFUSES
(exit code 2, a "REFUSED" message, no file written) on any of:
  - a record that is not valid JSON, lacks a field, or names an arm, layer, prompt or head outside the registration;
  - a duplicate (arm, layer) layer record, (arm, layer, prompt, head) cell, (arm, layer, prompt) prompt row or timing row;
  - a timing row for a layer without both arm records, or a recorded layer (other than the last) without one;
  - a recorded layer whose cells are not exactly the 10 registered prompts x 24 heads, or whose prompt rows are not
    exactly the 10 registered prompts;
  - layer records that are not a prefix of the order the run writes them in (layer 3 C2047, layer 3 C1665, layer 7
    C2047, ...): a hole in the middle, or an arm that is missing;
  - a C2047 layer record whose determinism evidence is not exactly the two registered prompts, or determinism
    evidence on C1665 (the run writes none there);
  - a layer record whose median, max, min, counts, pass flag, clamp, Smax or counter totals disagree with the cells
    and prompt rows.
A run cut by a stop rule is still summarised as PARTIAL: its layer records are a prefix of the run order. Cells and
prompt rows of the one layer the cut interrupted (no layer record yet) are accepted, excluded from every statistic and
listed under "interrupted". `determinism_ok` is true only when all 16 C2047 layers carry both checks and all are true,
false when any check is false, and null when no check failed but fewer than 16 C2047 layers are recorded.
Known limit: a run that was cut inside an attention layer and then resumed would write that layer's cells twice, and
is refused as a duplicate. The registered run was not resumed.

Units of the copied memory fields: `peak_tree_rss_gb` and `peak_rss_gb_self` are copied unchanged from the run logs.
They are Linux KiB counters divided by 1e6 (multiply by 1.024 for decimal GB); see RESULTS.md section 6.
"""
import json, math, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
PROMPTS_FILE = HERE.parent / "20261111-8-qwen-e2e-agreement" / "prompts-e2e.json"
ATT = [i for i in range(64) if i % 4 == 3]
ARMS = ("C2047", "C1665")
CLAMP = {"C2047": 2047, "C1665": 1665}
NH, NKV, HD = 24, 4, 256
DET_ARM, DET_PROMPTS = "C2047", ("p01-ordinary-short", "p09-multilingual")
ORDER = [(l, a) for l in ATT for a in ARMS]          # the order int_attn.py writes layer records in
N_PAIRS = 10 * NH
LAYER_KEYS = ("arm", "layer", "clamp", "Smax", "Eq", "Ek", "Ev", "sh", "sh_fit", "adjust", "q_over", "q_n", "k_over", "k_n",
              "v_over", "v_n", "q_maxw", "k_maxw", "v_maxw", "max_abs_s", "e_zero", "causal", "wide_over_32767", "n_pairs",
              "rel_median", "rel_max", "rel_min", "n_over_001", "n_over_005", "layer_pass", "det_bit_equal", "arm_seconds")
SUM_KEYS = ("q_over", "q_n", "k_over", "k_n", "v_over", "v_n", "e_zero", "causal", "wide_over_32767")
MAX_KEYS = ("q_maxw", "k_maxw", "v_maxw", "max_abs_s")
PROW_KEYS = ("arm", "layer", "prompt", "T", "mix_rel") + SUM_KEYS + MAX_KEYS
CELL_KEYS = {"arm", "layer", "prompt", "head", "rel_y"}


class Refused(Exception):
    pass


def is_int(x): return isinstance(x, int) and not isinstance(x, bool)
def is_num(x): return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def rd(p, errs, required=False):
    if not p.exists():
        if required: errs.append(f"{p.name}: file missing")
        return []
    out = []
    for n, l in enumerate(open(p), 1):
        try:
            o = json.loads(l)
        except ValueError:
            errs.append(f"{p.name} line {n}: not valid JSON"); continue
        if not isinstance(o, dict):
            errs.append(f"{p.name} line {n}: not a JSON object"); continue
        out.append(o)
    return out


def validate(lay, cells, prow, timrows, prompt_T, errs):
    """Appends every problem found to errs. Returns (recorded, interrupted): the set of (layer, arm) with a layer record
    and the one (layer, arm) the run was cut inside, if its cells or prompt rows are present (else None)."""
    E = errs.append
    # ---- layer records: fields, identities, uniqueness, prefix of the run order
    recorded = {}
    for n, r in enumerate(lay, 1):
        miss = [k for k in LAYER_KEYS if k not in r]
        if miss: E(f"layers.jsonl record {n}: missing fields {miss}"); continue
        if r["arm"] not in ARMS or not is_int(r["layer"]) or r["layer"] not in ATT:
            E(f"layers.jsonl record {n}: unexpected arm or layer ({r['arm']!r}, {r['layer']!r})"); continue
        key = (r["layer"], r["arm"])
        if key in recorded: E(f"layers.jsonl: duplicate layer record {r['arm']} layer {r['layer']}"); continue
        recorded[key] = r
    if not recorded: E("layers.jsonl: no layer record")
    if set(recorded) != set(ORDER[:len(recorded)]):
        gone = [f"{a} layer {l}" for l, a in ORDER[:len(recorded)] if (l, a) not in recorded]
        E(f"layers.jsonl: the layer records are not a prefix of the run order (hole or missing arm): absent {gone[:6]}"
          + (f" and {len(gone) - 6} more" if len(gone) > 6 else ""))
    nxt = ORDER[len(recorded)] if len(recorded) < len(ORDER) else None
    interrupted = None
    # ---- cells
    seen = set(); per = {}
    for n, c in enumerate(cells, 1):
        if set(c) != CELL_KEYS: E(f"cells.jsonl row {n}: fields are not exactly {sorted(CELL_KEYS)}"); continue
        if c["arm"] not in ARMS or not is_int(c["layer"]) or c["layer"] not in ATT or c["prompt"] not in prompt_T \
                or not is_int(c["head"]) or not 0 <= c["head"] < NH:
            E(f"cells.jsonl row {n}: unexpected arm, layer, prompt or head ({c['arm']!r}, {c['layer']!r}, {c['prompt']!r}, {c['head']!r})"); continue
        if not is_num(c["rel_y"]) or c["rel_y"] < 0: E(f"cells.jsonl row {n}: rel_y is not a finite non-negative number"); continue
        key = (c["arm"], c["layer"], c["prompt"], c["head"])
        if key in seen: E(f"cells.jsonl row {n}: duplicate cell {key}"); continue
        seen.add(key)
        la = (c["layer"], c["arm"])
        if la in recorded: per.setdefault(la, []).append(c["rel_y"])
        elif la == nxt: interrupted = nxt
        else: E(f"cells.jsonl row {n}: cell of {c['arm']} layer {c['layer']}, which has no layer record and is not the interrupted layer")
    for la in recorded:
        n = len(per.get(la, []))
        if n != N_PAIRS: E(f"cells.jsonl: {la[1]} layer {la[0]} has {n} of the {N_PAIRS} registered (prompt, head) cells")
    # ---- prompt rows
    seenp = set(); prs = {}
    for n, p in enumerate(prow, 1):
        miss = [k for k in PROW_KEYS if k not in p]
        if miss: E(f"prompt-rows.jsonl row {n}: missing fields {miss}"); continue
        if p["arm"] not in ARMS or not is_int(p["layer"]) or p["layer"] not in ATT or p["prompt"] not in prompt_T:
            E(f"prompt-rows.jsonl row {n}: unexpected arm, layer or prompt ({p['arm']!r}, {p['layer']!r}, {p['prompt']!r})"); continue
        key = (p["arm"], p["layer"], p["prompt"])
        if key in seenp: E(f"prompt-rows.jsonl row {n}: duplicate prompt row {key}"); continue
        seenp.add(key)
        T = prompt_T[p["prompt"]]
        if not all(is_num(p[k]) for k in ("T", "mix_rel") + SUM_KEYS + MAX_KEYS) or p["mix_rel"] < 0:
            E(f"prompt-rows.jsonl row {n}: a counter is not a finite number"); continue
        if p["T"] != T or p["q_n"] != T * NH * HD or p["k_n"] != T * NKV * HD or p["v_n"] != T * NKV * HD or p["causal"] != NH * T * (T + 1) // 2:
            E(f"prompt-rows.jsonl row {n}: T or a denominator does not match the registered prompt {p['prompt']} ({T} tokens)"); continue
        la = (p["layer"], p["arm"])
        if la in recorded: prs.setdefault(la, []).append(p)
        elif la == nxt: interrupted = nxt
        else: E(f"prompt-rows.jsonl row {n}: row of {p['arm']} layer {p['layer']}, which has no layer record and is not the interrupted layer")
    # ---- each layer record against its cells and prompt rows
    for la, r in recorded.items():
        tag = f"{la[1]} layer {la[0]}"
        rows = prs.get(la, [])
        if len(rows) != len(prompt_T): E(f"prompt-rows.jsonl: {tag} has {len(rows)} of the {len(prompt_T)} registered prompts"); continue
        if not all(is_num(r[k]) for k in SUM_KEYS + MAX_KEYS + ("rel_median", "rel_max", "rel_min", "n_pairs", "n_over_001", "n_over_005", "clamp", "Smax")):
            E(f"layers.jsonl: {tag} has a field that is not a finite number"); continue
        if r["clamp"] != CLAMP[la[1]] or r["Smax"] != HD * CLAMP[la[1]] ** 2: E(f"layers.jsonl: {tag} clamp or Smax is not the registered one")
        bad = [k for k in SUM_KEYS if r[k] != sum(p[k] for p in rows)] + [k for k in MAX_KEYS if r[k] != max(p[k] for p in rows)]
        if bad: E(f"layers.jsonl: {tag} totals disagree with its prompt rows: {bad}")
        v = per.get(la, [])
        if len(v) == N_PAIRS:
            a = np.array(v); med, mx, mn = float(np.median(a)), float(a.max()), float(a.min())
            if r["n_pairs"] != N_PAIRS or abs(med - r["rel_median"]) >= 1e-15 or abs(mx - r["rel_max"]) >= 1e-15 or abs(mn - r["rel_min"]) >= 1e-15 \
                    or r["n_over_001"] != int((a > 0.01).sum()) or r["n_over_005"] != int((a > 0.05).sum()) \
                    or r["layer_pass"] is not bool(med <= 0.01 and mx <= 0.05):
                E(f"layers.jsonl: {tag} median, max, min, counts or pass flag disagree with its cells")
        d = r["det_bit_equal"]
        if not isinstance(d, dict) or not all(isinstance(x, bool) for x in d.values()):
            E(f"layers.jsonl: {tag} determinism evidence is not a map of booleans")
        elif la[1] == DET_ARM and set(d) != set(DET_PROMPTS):
            E(f"layers.jsonl: {tag} determinism evidence is {sorted(d)}, not exactly the registered {sorted(DET_PROMPTS)}")
        elif la[1] != DET_ARM and d:
            E(f"layers.jsonl: {tag} carries determinism evidence, which the run writes only on {DET_ARM}")
    # ---- timing rows
    seent = set()
    for n, t in enumerate(timrows, 1):
        if not is_int(t.get("layer")) or t["layer"] not in ATT: E(f"attn-timing.jsonl row {n}: unexpected layer {t.get('layer')!r}"); continue
        if t["layer"] in seent: E(f"attn-timing.jsonl row {n}: duplicate timing row for layer {t['layer']}"); continue
        seent.add(t["layer"])
    # the run writes a layer's timing row after both of its arm records; only the last recorded layer may lack one (cut)
    both = [l for l in ATT if all((l, a) in recorded for a in ARMS)]
    extra = sorted(seent - set(both)); lack = [l for l in both[:-1] if l not in seent]
    if extra: E(f"attn-timing.jsonl: timing rows for layers without both arm records: {extra}")
    if lack: E(f"attn-timing.jsonl: no timing row for recorded layers {lack}")
    return set(recorded), interrupted


def build(runs):
    errs = []
    lay = rd(runs / "layers.jsonl", errs, required=True); cells = rd(runs / "cells.jsonl", errs, required=True)
    prow = rd(runs / "prompt-rows.jsonl", errs, required=True)
    timrows = rd(runs / "attn-timing.jsonl", errs); prog = rd(runs / "progress.log", errs)
    prompt_T = {p["id"]: len(p["token_ids"]) for p in json.load(open(PROMPTS_FILE))["prompts"]}
    if len(prompt_T) != 10: errs.append("the registered prompt file does not hold 10 prompts")
    recorded, interrupted = validate(lay, cells, prow, timrows, prompt_T, errs)
    if errs: raise Refused(errs)
    tim = {r["layer"]: r for r in timrows}
    cells = [c for c in cells if (c["layer"], c["arm"]) in recorded]
    prow = [p for p in prow if (p["layer"], p["arm"]) in recorded]
    out = dict(arms={}, layers_done=sorted({r["layer"] for r in lay}), note="measured, unreplicated; open loop; in-sample scale fit")
    md = ["| arm | layer | E_q E_k E_v | sh (fit) | max \\|qw\\| \\|kw\\| \\|vw\\| | over-clamp q/k/v | max \\|s\\| / Smax | e=0 share | rel_y median | rel_y max | >0.01 | >0.05 | mix rel median | pass | arm s |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    det_rows = [r for r in lay if r["arm"] == DET_ARM]
    det_fail = any(not all(r["det_bit_equal"].values()) for r in det_rows)
    det_complete = sorted(r["layer"] for r in det_rows) == ATT
    det_ok = False if det_fail else (True if det_complete else None)
    for arm in ARMS:
        rows = sorted([r for r in lay if r["arm"] == arm], key=lambda r: r["layer"]); per = []
        for r in rows:
            a = np.array([c["rel_y"] for c in cells if c["arm"] == arm and c["layer"] == r["layer"]])
            med, mx = float(np.median(a)), float(a.max())
            mixr = [p["mix_rel"] for p in prow if p["arm"] == arm and p["layer"] == r["layer"]]
            ok = med <= 0.01 and mx <= 0.05
            per.append(dict(layer=r["layer"], n_pairs=int(a.size), rel_median=med, rel_max=mx, rel_min=float(a.min()),
                            n_over_001=int((a > 0.01).sum()), n_over_005=int((a > 0.05).sum()), pass_=ok,
                            Eq=r["Eq"], Ek=r["Ek"], Ev=r["Ev"], sh=r["sh"], sh_fit=r["sh_fit"], adjust=r["adjust"],
                            q_over=r["q_over"], q_n=r["q_n"], k_over=r["k_over"], k_n=r["k_n"], v_over=r["v_over"], v_n=r["v_n"],
                            q_maxw=r["q_maxw"], k_maxw=r["k_maxw"], v_maxw=r["v_maxw"], max_abs_s=r["max_abs_s"], Smax=r["Smax"],
                            e_zero=r["e_zero"], causal=r["causal"], wide_over_32767=r["wide_over_32767"],
                            mix_rel_median=float(np.median(mixr)), mix_rel_max=float(np.max(mixr)),
                            det=r["det_bit_equal"], arm_seconds=r["arm_seconds"],
                            layer_seconds=tim.get(r["layer"], {}).get("total_s")))
            md.append(f"| {arm} | {r['layer']} | {r['Eq']} {r['Ek']} {r['Ev']} | {r['sh']} ({r['sh_fit']}) | {r['q_maxw']} {r['k_maxw']} {r['v_maxw']} | "
                      f"{r['q_over']}/{r['k_over']}/{r['v_over']} | {r['max_abs_s']:.0f} / {r['Smax']} | {r['e_zero'] / r['causal']:.3f} | "
                      f"{med:.5f} | {mx:.5f} | {int((a > 0.01).sum())} | {int((a > 0.05).sum())} | {float(np.median(mixr)):.5f} | {'yes' if ok else 'NO'} | {r['arm_seconds']} |")
        done = [p["layer"] for p in per]; complete = done == ATT
        npass = sum(p["pass_"] for p in per)
        if det_fail: verdict = "FAIL (determinism)"
        elif complete and det_ok is True: verdict = "PASS" if npass == 16 else "FAIL"
        else: verdict = "PARTIAL: " + ("fails already on a layer done" if npass < len(per) else "no failing layer among those done")
        allc = np.array([c["rel_y"] for c in cells if c["arm"] == arm])
        out["arms"][arm] = dict(verdict=verdict, layers_done=done, layers_pass=npass, determinism_ok=det_ok, per_layer=per,
                                pooled=dict(n=int(allc.size), median=float(np.median(allc)) if allc.size else None,
                                            max=float(allc.max()) if allc.size else None, min=float(allc.min()) if allc.size else None,
                                            n_over_001=int((allc > 0.01).sum()), n_over_005=int((allc > 0.05).sum())))
    stop = [p for p in prog if "kill" in p or "stop" in p or "exit" in p]
    out["stops"] = stop
    out["peak_tree_rss_gb"] = next((p.get("peak_tree_rss_gb") for p in prog if "peak_tree_rss_gb" in p), None)
    out["timing"] = [dict(layer=k, **{x: v for x, v in t.items() if x in ("float_s", "ref_attention_s", "total_s", "mix_bit_equal_q1", "peak_rss_gb_self")}) for k, t in sorted(tim.items())]
    if interrupted is not None:
        out["interrupted"] = dict(layer=interrupted[0], arm=interrupted[1], note="cut inside this layer: its cells and prompt rows are excluded from every statistic")
    lines = ["# summary (generated by summarise.py)", ""]
    for arm in ARMS:
        a = out["arms"][arm]; p = a["pooled"]
        lines.append(f"- {arm}: {a['verdict']}; layers passing {a['layers_pass']} of {len(a['layers_done'])} done; determinism ok {a['determinism_ok']}; "
                     f"pooled n={p['n']} median {p['median']} max {p['max']}, over 0.01: {p['n_over_001']}, over 0.05: {p['n_over_005']}")
    lines += ["", *md, ""]
    return out, lines


def main():
    """summarise.py [RUNS_DIR [OUT_DIR]]: read the records in RUNS_DIR (default runs/), write summary.json and summary.md
    to OUT_DIR (default RUNS_DIR). The optional arguments exist for the tests and for checking a rewrite against the
    committed summary without touching it."""
    runs = Path(sys.argv[1]) if len(sys.argv) > 1 else RUNS
    outd = Path(sys.argv[2]) if len(sys.argv) > 2 else runs
    try:
        out, lines = build(runs)
    except Refused as e:
        errs = e.args[0]
        print(f"REFUSED: {len(errs)} problem(s) in the run records; nothing written.", file=sys.stderr)
        for x in errs[:25]: print("  - " + x, file=sys.stderr)
        if len(errs) > 25: print(f"  ... and {len(errs) - 25} more", file=sys.stderr)
        sys.exit(2)
    (outd / "summary.json").write_text(json.dumps(out, indent=1) + "\n")
    (outd / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:4]))


if __name__ == "__main__":
    main()
