#!/usr/bin/env python3
"""Teacher-force served replies through float64 (REF) and the XS18 / XS20 DeltaNet-head paths (PREREG.md).

Reuses PR #124's `e2e.py` by import (unchanged): `layer_all`, `run_leg`, `logits_metrics`, `lm_head_chunks`,
`save_state` / `load_state`, `make_pool`. Changes, all made here and not in e2e.py:
- paths: REF, XS18, XS20 on every included prompt; REF#2, XS18#2 on the first two included prompts (determinism);
  no BF16H, no stock leg (only the served, abliterated checkpoint: stock layers 0..16, byte-identical per PR #68,
  then abl layers 17..63, abl final norm, abl lm_head; the same layer map as PR #124's abl leg);
- input: served-ids.json (rebuilt prompt ids + reply ids) instead of prompts-e2e.json; no p01 " Tokyo" sanity check,
  the registered sanity check is REF-vs-served >= 80% (summarise_served.py);
- output: runs/forward.json with the full per-position top-1 of every path and REF's top-2 margin (from e2e.Stream).
Only the DeltaNet head computation is lowered. No proof, no soundness claim.

Usage:
  served_e2e.py run <scratch> <runs> <served-ids.json>
  served_e2e.py fixture <scratch> <out.json>   debug/timing only: template-probe sequence (not in the suite), stock layers 0..3
"""
import json, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "20261111-8-qwen-e2e-agreement"))
import e2e as E          # PR #124, unchanged
F = E.F                  # PR #88 q1_forward, unchanged

E.PATH_ORDER = ["REF", "XS18", "XS20", "REF#2", "XS18#2"]
NOTE = E.NOTE
# Template-probe sequence (PREREG "Template probe"): rebuilt prompt ids (20) + "Tokyo" + <|im_end|>. Not in the suite.
PROBE_TEXT_NOTE = "capital of Japan probe, enable_thinking=False template"

def build_X(C, sel, det_ids):
    """sel: list of (pid, ids). Embedding rows from the stock checkpoint (identical in abl, PR #68)."""
    emb = C.emb_rows(sorted({t for _, ids in sel for t in ids}))
    pr = {pid: np.stack([emb[t] for t in ids]) for pid, ids in sel}
    X = {p: {pid: pr[pid].copy() for pid in pr} for p in ("REF", "XS18", "XS20")}
    for p in ("REF#2", "XS18#2"): X[p] = {pid: pr[pid].copy() for pid in det_ids}
    return X

def finish(X, C, runs, sc, meta, seqs):
    t0 = time.time(); Ln = C.t(F.P + "norm.weight")
    Hn = {p: {pid: (F.rms0(x, Ln) if x is not None else None) for pid, x in d.items()} for p, d in X.items()}
    res = E.logits_metrics(Hn, E.lm_head_chunks(C)); C.save()
    out = dict(checkpoint="abl (stock layers 0..16 identical)", note=NOTE, sequences=seqs, prompts=res,
               seconds=round(time.time() - t0, 1))
    (Path(runs) / "forward.json").write_text(json.dumps(out) + "\n")
    meta["done"] = True; E.save_state(sc / "ckpt.npz", X, meta)
    E.log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), logits_done=True, seconds=out["seconds"]))
    print("logits done", out["seconds"], flush=True)

def cmd_run(scratch, runs, ids_file):
    sc = Path(scratch); runs = Path(runs); sc.mkdir(parents=True, exist_ok=True); runs.mkdir(parents=True, exist_ok=True)
    S = json.load(open(ids_file))
    inc = [q for q in S["prompts"] if q["included"]]
    # teacher-forced input: prompt ids + reply ids except the last (the last reply id is predicted, never fed)
    sel = [(q["id"], q["prompt_ids"] + q["reply_ids"][:-1]) for q in inc]
    seqs = {q["id"]: dict(n_prompt=len(q["prompt_ids"]), n_reply=len(q["reply_ids"]), input_ids=q["prompt_ids"] + q["reply_ids"][:-1],
                          reply_ids=q["reply_ids"]) for q in inc}
    det_ids = [q["id"] for q in inc[:2]]
    ckpts = {"stock": F.Ckpt("stock", runs), "abl": F.Ckpt("abl", runs)}
    pool = E.make_pool()
    if (sc / "ckpt.npz").exists():
        X, meta = E.load_state(sc / "ckpt.npz")
        E.log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), resume=True, meta=meta))
    else:
        X = build_X(ckpts["stock"], sel, det_ids); ckpts["stock"].save(); meta = dict(leg="abl", next_layer=0)
        E.log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), start=True,
                                                paths={p: list(d) for p, d in X.items()}, tokens=sum(len(s) for _, s in sel)))
    if not meta.get("done"):
        layers = [(i, "stock" if i <= 16 else "abl") for i in range(F.NL)]
        i0 = meta["next_layer"] if meta.get("next_layer") is not None else F.NL
        E.run_leg("abl", X, i0, layers, ckpts, sc, runs, pool, meta, lambda X: finish(X, ckpts["abl"], runs, sc, meta, seqs))
    pool.close(); pool.join()
    E.log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), all_done=True))

def cmd_fixture(scratch, out):
    """Debug and timing only: the template-probe sequence (not a suite prompt) through stock layers 0..3, all 5 paths.
    Reports per-layer seconds; no lm_head."""
    sc = Path(scratch); sc.mkdir(parents=True, exist_ok=True); t0 = time.time()
    ids = json.load(open(sc / "probe-ids.json"))["ids"]
    C = F.Ckpt("stock", sc); pool = E.make_pool()
    X = build_X(C, [("probe", ids)], ["probe"]); per = []
    for i in range(4):
        tf = time.time(); L = C.layer(i); tfetch = time.time() - tf
        row = E.layer_all(i, L, X, pool, sc, "fx", "errors-fx.jsonl"); del L
        per.append(dict(layer=i, fetch_s=round(tfetch, 1), compute_s=row["seconds"], det=row["det_bit_equal"]))
    pool.close(); pool.join()
    o = dict(note=PROBE_TEXT_NOTE, tokens=len(ids), per_layer=per,
             resid_rel_vs_ref={p: E.rel(X[p]["probe"], X["REF"]["probe"]) for p in X}, seconds=round(time.time() - t0, 1))
    Path(out).write_text(json.dumps(o, indent=1) + "\n"); print(json.dumps(o, indent=1))

if __name__ == "__main__":
    if sys.argv[1] == "run": cmd_run(sys.argv[2], sys.argv[3], sys.argv[4])
    else: cmd_fixture(sys.argv[2], sys.argv[3])
