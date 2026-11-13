#!/usr/bin/env python3
"""Verdicts for the registered arms U1..U4 from decay_r2.py output (PREREG "Acceptance threshold": PR #146's bar).
usage: summarise_r2.py <eval_dir> [--fixture]   -> <eval_dir>/summary.json, summary.md

Before any verdict the per-cell file is checked against the registered suite (PR #146's suite.py): eval-meta.json
must name exactly the 48 registered DeltaNet layers, the 10 registered prompts and the registered bar, and
cells.csv.gz must hold exactly one row per (arm, layer, head, prompt), with the registered token count, an integer
reject count (only U4 can reject) and, unless the cell has a rejected lookup, finite nonnegative e_tok_max, e_tok_med
and e_cum_max (these are absolute differences) with e_tok_med <= e_tok_max. A missing, truncated or unparsable
eval-meta.json or cells.csv.gz is refused the same way. Anything else exits 2 with nothing written. The debug fixture (--fixture) is checked for internal consistency only and is never a
registered verdict."""
import csv, gzip, json, sys, zlib
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "20261112-136-deltanet-decay"))
import suite as SU   # PR #146, unchanged

ARMS = ("U1", "U2", "U3", "U4")
REJECTING = ("U4",)
E_TOK, E_CUM = SU.BAR["e_tok"], SU.BAR["e_cum"]
need = SU.need


def rd(p):
    try:
        with gzip.open(p, "rt") as fh: return list(csv.DictReader(fh))
    except (OSError, EOFError, UnicodeDecodeError, csv.Error, zlib.error) as e:
        raise SU.Incomplete(f"{Path(p).name}: unreadable ({type(e).__name__}: {e})")


def rd_meta(p):
    try:
        m = json.loads(Path(p).read_text())
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise SU.Incomplete(f"{Path(p).name}: unreadable ({type(e).__name__}: {e})")
    need(isinstance(m, dict), f"{Path(p).name}: not a JSON object")
    return m


def st(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    if len(v) == 0: return None
    return dict(n=int(len(v)), min=float(v.min()), median=float(np.median(v)), max=float(v.max()), sd=float(v.std()))


def validate(meta, cells, fixture=False):
    need(bool(meta.get("fixture")) == bool(fixture), f"eval-meta.json fixture={meta.get('fixture')!r} but mode fixture={fixture}")
    need(meta.get("bar") == SU.BAR, f"eval-meta.json bar {meta.get('bar')!r} is not the registered bar {SU.BAR!r}")
    need(meta.get("arms") == list(ARMS), f"eval-meta.json arms {meta.get('arms')!r} are not {list(ARMS)}")
    need(isinstance(meta.get("layers"), list) and isinstance(meta.get("prompts"), list), "eval-meta.json: layers / prompts missing")
    if fixture:
        layers = [SU.as_int(l, "eval-meta layer") for l in meta["layers"]]; prompts = list(meta["prompts"]); toks = None
        need(layers and prompts and all(l in SU.DELTANET_LAYERS for l in layers), "fixture eval-meta.json: bad layers / prompts")
    else:
        toks = SU.registered_tokens("S10"); layers = list(SU.DELTANET_LAYERS); prompts = sorted(toks)
        need(meta["layers"] == layers, "eval-meta.json layers are not the 48 registered DeltaNet layers")
        need(meta["prompts"] == prompts, "eval-meta.json prompts are not the 10 registered prompts")
        need(meta.get("set") == "S10", "eval-meta.json set is not S10")
    need(len(cells) > 0 and set(cells[0]) >= {"arm", "layer", "head", "prompt", "T", "rejects", "e_tok_max", "e_tok_med", "e_cum_max"}, "cells.csv.gz: columns missing")
    ids = Counter((c["arm"], SU.as_int(c["layer"], "layer"), SU.as_int(c["head"], "head"), c["prompt"]) for c in cells)
    dup = [k for k, v in ids.items() if v > 1]
    need(not dup, f"cells.csv.gz: {len(dup)} duplicated cells, e.g. {dup[:3]}")
    want = {(a, l, h, p) for a in ARMS for l in layers for h in range(SU.N_HEADS) for p in prompts}
    have = set(ids)
    need(have == want, f"cells.csv.gz: cell set differs from the registered grid: {len(want - have)} missing (e.g. {sorted(want - have)[:3]}), {len(have - want)} unexpected (e.g. {sorted(have - want)[:3]})")
    for c in cells:
        T = SU.as_int(c["T"], "cells T"); r = SU.as_int(c["rejects"], "cells rejects")
        where = f"{c['arm']} L{c['layer']} h{c['head']} {c['prompt']}"
        need(T >= 1 and 0 <= r <= T, f"cells.csv.gz: T={T}, rejects={r} out of range at {where}")
        if toks is not None: need(T == toks[c["prompt"]], f"cells.csv.gz: T={T} at {where}, registered {toks[c['prompt']]}")
        need(c["arm"] in REJECTING or r == 0, f"cells.csv.gz: rejects on a clamping arm at {where} (only U4 rejects)")
        if r == 0:
            for k in ("e_tok_max", "e_tok_med", "e_cum_max"):
                need(SU.finite(c[k]), f"cells.csv.gz: non-finite {k}={c[k]!r} in a cell without a rejected lookup ({where})")
                need(float(c[k]) >= 0, f"cells.csv.gz: negative {k}={c[k]!r} (an absolute error) in a cell without a rejected lookup ({where})")
            need(float(c["e_tok_med"]) <= float(c["e_tok_max"]), f"cells.csv.gz: e_tok_med={c['e_tok_med']!r} > e_tok_max={c['e_tok_max']!r} ({where})")
    return "FIXTURE (debug, not a registered verdict)" if fixture else "COMPLETE"


def verdicts(cells):
    out = {}
    for arm in ARMS:
        cs = [c for c in cells if c["arm"] == arm]; fail = []
        for c in cs:
            r = int(c["rejects"]); et = float(c["e_tok_max"]); ec = float(c["e_cum_max"]); why = []
            if r: why.append("reject")
            if not (et <= E_TOK) and not r: why.append("e_tok")
            if not (ec <= E_CUM): why.append("e_cum")
            if why: fail.append(dict(layer=int(c["layer"]), head=int(c["head"]), prompt=c["prompt"], T=int(c["T"]), why=why, rejects=r, e_tok_max=et, e_cum_max=ec))
        by = {k: sum(k in f["why"] for f in fail) for k in ("reject", "e_tok", "e_cum")}
        lh = sorted({(f["layer"], f["head"]) for f in fail}); per_layer = defaultdict(set); per_prompt = Counter(f["prompt"] for f in fail)
        for l, h in lh: per_layer[l].add(h)
        norej = [c for c in cs if int(c["rejects"]) == 0]
        out[arm] = dict(verdict="PASS" if not fail else "FAIL", n_cells=len(cs), n_fail_cells=len(fail), fail_by_reason=by,
                        n_fail_layer_heads=len(lh), of_layer_heads=len({(c["layer"], c["head"]) for c in cs}),
                        fail_heads_per_layer={str(l): sorted(h) for l, h in sorted(per_layer.items())},
                        fail_cells_per_prompt=dict(sorted(per_prompt.items())),
                        rejects_total=sum(int(c["rejects"]) for c in cs), cells_with_reject=sum(int(c["rejects"]) > 0 for c in cs),
                        e_tok_max_over_cells=st([float(c["e_tok_max"]) for c in norej]),
                        e_tok_med_over_cells=st([float(c["e_tok_med"]) for c in norej]),
                        e_cum_max_over_cells=st([float(c["e_cum_max"]) for c in cs]),
                        worst_e_tok=sorted(fail, key=lambda f: -f["e_tok_max"])[:20], worst_e_cum=sorted(fail, key=lambda f: -f["e_cum_max"])[:20])
    return out


def main(d, fixture=False):
    d = Path(d); meta = rd_meta(d / "eval-meta.json"); cells = rd(d / "cells.csv.gz")
    cov = validate(meta, cells, fixture)
    arms = verdicts(cells)
    H = None if fixture else bool(arms["U3"]["verdict"] == "PASS" and arms["U1"]["verdict"] == "FAIL" and arms["U2"]["verdict"] == "FAIL")
    S = dict(meta=meta, coverage=dict(label=cov, layers=len(meta["layers"]), heads=SU.N_HEADS, prompts=len(meta["prompts"]),
                                      cells_per_arm=len(meta["layers"]) * SU.N_HEADS * len(meta["prompts"]), checked_by="suite.py (PR #146) + summarise_r2.validate"),
             bar=SU.BAR, arms=arms, hypothesis=dict(statement="U3 PASS and U1, U2 FAIL", holds=H))
    (d / "summary.json").write_text(json.dumps(S, indent=1) + "\n")
    L = ["| arm | verdict | cells failing / n | by reason (reject, e_tok, e_cum) | (layer, head) failing / n | e_tok max per cell: median (max) | e_cum max per cell: median (max) |", "|---|---|---|---|---|---|---|"]
    for arm, a in arms.items():
        et = a["e_tok_max_over_cells"]; ec = a["e_cum_max_over_cells"]; b = a["fail_by_reason"]
        L.append(f"| {arm} | {a['verdict']} | {a['n_fail_cells']} / {a['n_cells']} | {b['reject']}, {b['e_tok']}, {b['e_cum']} | {a['n_fail_layer_heads']} / {a['of_layer_heads']} | "
                 + (f"{et['median']:.3g} ({et['max']:.3g})" if et else "n/a") + " | " + (f"{ec['median']:.3g} ({ec['max']:.3g})" if ec else "n/a") + " |")
    if fixture: L.append(f"\nCoverage: {cov}.")
    else: L.append(f"\nH (U3 PASS and U1, U2 FAIL): {'holds' if H else 'false'}.")
    (d / "summary.md").write_text("\n".join(L) + "\n"); print("\n".join(L))
    return S


if __name__ == "__main__":
    try:
        main(sys.argv[1], "--fixture" in sys.argv[2:])
    except SU.Incomplete as e:
        print("summarise_r2.py: REFUSED, input is not the expected cell set: " + str(e), file=sys.stderr); sys.exit(2)
