#!/usr/bin/env python3
"""U1 margin on p03-repeat-word (PREREG.md). Registered run driver. CPU, float64, REF path only.

PR #139's fused pass (u1_fused.py) started from a layer-16 scratch state that is no longer available, so this driver
computes stock layers 0..16 itself and then runs the same fused pass for layers 17..63:
  - stock embedding rows (PR #88 Ckpt.emb_rows, sha256 per row);
  - layers 0..16: stock layer (byte-identical in both checkpoints per PR #87), PR #124 e2e.layer_all unchanged, one
    shared REF state;
  - layers 17..63: stock layer fetched once; the abl layer is that dict with the tensors whose committed PR #87 sha256
    differs replaced by tensors fetched from the abl repo (PR #139 u1_fused.changed_tensors, unchanged); both REF
    states through e2e.layer_all;
  - each checkpoint's final norm, one streamed lm_head pass (stock repo) through PR #139 u1_margin.two_way.
Reused unchanged: PR #88 q1_forward.py, PR #124 e2e.py, PR #139 u1_margin.py / u1_fused.py. New: this driver only.
Weights are streamed by HTTP range requests and never written to disk; only residual states are saved (resume).

Usage:
  u1_p03.py run <scratch> <runs>          registered run on p03-repeat-word (512 positions); resumes from <scratch>/ckpt.npz
  u1_p03.py fixture <scratch> <out.json>  debug only: "The capital of Italy is" (not in the suite), stock layers 0 and 3,
                                          fused layer 17, both final norms, full lm_head two-way vs dense logits
"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "20261112-134-u1-margin"))
import u1_margin as U      # PR #139, unchanged (imports PR #124 e2e and PR #88 q1_forward, unchanged)
import u1_fused as UF      # PR #139, unchanged (changed_tensors only)
E, F = U.E, U.F
PID = "p03-repeat-word"

def by_layer():
    diff = UF.changed_tensors(); bl = {}
    for n in diff:
        i = int(n.split("layers.")[1].split(".")[0]); bl.setdefault(i, []).append(n)
    return diff, bl

def forward(stock, abl, St, meta, sc, runs, pool, shared_layers, fused_layers, bylayer):
    """Advance St from meta['next_layer'] through shared_layers (stock only, St['S'] is the shared state, St['A'] None)
    and then fused_layers (St['S'] stock, St['A'] abl). State saved after every layer."""
    todo = [("shared", i) for i in shared_layers] + [("fused", i) for i in fused_layers]
    todo = [(k, i) for k, i in todo if i >= meta["next_layer"]]
    def fetch(kind_i):
        kind, i = kind_i; L = stock.layer(i)
        if kind == "shared": return L, None
        pre = F.P + f"layers.{i}."
        La = dict(L); La.update({n[len(pre):]: abl.t(n) for n in bylayer.get(i, [])})
        return L, La
    ex = ThreadPoolExecutor(1); fut = ex.submit(fetch, todo[0]) if todo else None
    for n, (kind, i) in enumerate(todo):
        tw = time.time(); L, La = fut.result(); wait = time.time() - tw
        stock.save(); abl.save()
        fut = ex.submit(fetch, todo[n + 1]) if n + 1 < len(todo) else None
        if kind == "shared":
            r1 = E.layer_all(i, L, {"REF": St["S"]}, pool, runs, "shared", "errors-shared.jsonl"); s_abl = None
        else:
            if St["A"] is None: St["A"] = {p: x.copy() for p, x in St["S"].items()}   # layers 0..16 shared, then split
            r1 = E.layer_all(i, L, {"REF": St["S"]}, pool, runs, "stock", "errors-stock.jsonl")
            r2 = E.layer_all(i, La, {"REF": St["A"]}, pool, runs, "abl", "errors-abl.jsonl"); s_abl = r2["seconds"]
            E.log(runs, "resid-abl-vs-stock.jsonl", dict(layer=i, patched=len(bylayer.get(i, [])),
                                                          rel={p: E.rel(St["A"][p], St["S"][p]) for p in St["S"]}))
        del L, La
        meta["next_layer"] = i + 1
        E.save_state(sc / "ckpt.npz", {"S": St["S"], "A": St["A"] or {}}, meta)
        U.plog(runs, kind=kind, layer=i, patched=len(bylayer.get(i, [])) if kind == "fused" else 0,
               fetch_wait_s=round(wait, 1), s_stock=r1["seconds"], s_abl=s_abl)
    ex.shutdown()

def cmd_run(scratch, runs):
    sc = Path(scratch); runs = Path(runs); sc.mkdir(parents=True, exist_ok=True); runs.mkdir(parents=True, exist_ok=True)
    prompts = json.load(open(EXP / "20261111-8-qwen-e2e-agreement" / "prompts-e2e.json"))
    toks = next(p for p in prompts["prompts"] if p["id"] == PID)["token_ids"]; assert len(toks) == 512
    diff, bylayer = by_layer()
    stock, abl = F.Ckpt("stock", runs), F.Ckpt("abl", runs); pool = E.make_pool()
    if (sc / "ckpt.npz").exists():
        X, meta = E.load_state(sc / "ckpt.npz"); St = {"S": X["S"], "A": X.get("A") or None}
        U.plog(runs, resume=True, meta=meta)
    else:
        emb = stock.emb_rows(toks); stock.save()
        St = {"S": {PID: np.stack([emb[t] for t in toks])}, "A": None}
        meta = dict(next_layer=0, prompts=[PID], n_changed=len(diff))
        U.plog(runs, start=True, prompts=[PID], tokens=len(toks), n_changed=len(diff), changed_layers=sorted(bylayer),
               x16="recomputed (stock layers 0..16 in this run)")
    forward(stock, abl, St, meta, sc, runs, pool, range(0, 17), range(17, F.NL), bylayer)
    Hs = U.final_hidden(stock, {"REF": St["S"]}); Ha = U.final_hidden(abl, {"REF": St["A"]})
    t0 = time.time(); res = U.two_way(Hs, Ha, E.lm_head_chunks(stock)); stock.save(); abl.save()
    out = dict(note="float64 REF stock vs float64 REF abl on p03-repeat-word; D = KL(stock || abl) in nats; layers 0..16 "
                    "recomputed (stock, shared); no integer arm in this file", prompts=res, seconds=round(time.time() - t0, 1))
    (runs / "d-p03.json").write_text(json.dumps(out) + "\n")
    pool.close(); pool.join(); U.plog(runs, logits_done=True, seconds=out["seconds"])

def cmd_fixture(scratch, out):
    sc = Path(scratch); sc.mkdir(parents=True, exist_ok=True); t0 = time.time()
    diff, bylayer = by_layer()
    stock, abl = F.Ckpt("stock", sc), F.Ckpt("abl", sc); pool = E.make_pool()
    emb = stock.emb_rows(F.FIXTURE)
    St = {"S": {"fx": np.stack([emb[t] for t in F.FIXTURE])}, "A": None}
    meta = dict(next_layer=0)
    forward(stock, abl, St, meta, sc, sc, pool, [0, 3], [17], bylayer)
    X2, m2 = E.load_state(sc / "ckpt.npz")
    save_ok = bool(np.array_equal(X2["S"]["fx"], St["S"]["fx"]) and np.array_equal(X2["A"]["fx"], St["A"]["fx"]) and m2 == meta)
    Hs = U.final_hidden(stock, {"REF": St["S"]}); Ha = U.final_hidden(abl, {"REF": St["A"]})
    Zsl, Zal = [], []
    def chunks():
        for off, W in E.lm_head_chunks(stock):
            Zsl.append(Hs["fx"] @ W.T); Zal.append(Ha["fx"] @ W.T); yield off, W
    res = U.two_way(Hs, Ha, chunks())["fx"]
    Zs = np.concatenate(Zsl, 1); Za = np.concatenate(Zal, 1); del Zsl, Zal
    ls = Zs - F.lse(Zs)[:, None]; la = Za - F.lse(Za)[:, None]
    kd = (np.exp(ls) * (ls - la)).sum(1); kr = (np.exp(la) * (la - ls)).sum(1)
    s2 = np.sort(Zs, 1); a2 = np.sort(Za, 1)
    o = dict(prompt="The capital of Italy is (debug fixture, not in the suite)", layers=dict(shared=[0, 3], fused=[17]),
             patched_at_17=len(bylayer.get(17, [])), save_load_equal=save_ok,
             resid_rel_abl_vs_stock_after_L17=E.rel(St["A"]["fx"], St["S"]["fx"]),
             D_stream=res["D_kl_stock_abl"], D_dense=[float(v) for v in kd],
             D_absdiff=float(np.abs(kd - np.array(res["D_kl_stock_abl"])).max()),
             rev_absdiff=float(np.abs(kr - np.array(res["kl_abl_stock"])).max()),
             top1_ok=[int(v) for v in Zs.argmax(1)] == res["stock_top1"] and [int(v) for v in Za.argmax(1)] == res["abl_top1"],
             margins_ok=bool(np.allclose(s2[:, -1] - s2[:, -2], res["stock_margin"], rtol=0, atol=1e-9)
                             and np.allclose(a2[:, -1] - a2[:, -2], res["abl_margin"], rtol=0, atol=1e-9)),
             manifest_counts=dict(stock=len(stock.man["tensors"]), abl=len(abl.man["tensors"])),
             seconds=round(time.time() - t0, 1))
    o["fixture_ok"] = bool(o["save_load_equal"] and o["D_absdiff"] < 1e-9 and o["rev_absdiff"] < 1e-9 and o["top1_ok"]
                           and o["margins_ok"] and o["patched_at_17"] == 2 and o["manifest_counts"]["abl"] == 3)
    pool.close(); pool.join()
    Path(out).write_text(json.dumps(o, indent=1) + "\n"); print(json.dumps(o, indent=1))
    sys.exit(0 if o["fixture_ok"] else 3)

if __name__ == "__main__":
    a = sys.argv
    if a[1] == "run": cmd_run(a[2], a[3])
    elif a[1] == "fixture": cmd_fixture(a[2], a[3])
    else: raise SystemExit(__doc__)
