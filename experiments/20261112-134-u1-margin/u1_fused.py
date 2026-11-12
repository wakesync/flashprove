#!/usr/bin/env python3
"""U1 margin, fused single pass (PREREG.md Amendment A-1). Registered run driver.

Starts from the REF residual states after layer 16 (PR #124 scratch x16.npz; layers 0..16 byte-identical in both
checkpoints per PR #87's committed manifests). For each layer 17..63: fetch the stock layer once (PR #88 Ckpt.layer,
sha256 manifest), fetch from the abl repo only the tensors whose committed PR #87 sha256 differs (70 in total, layers
17..51), run PR #124's e2e.layer_all (unchanged, REF path only) on the stock state with the stock layer and on the
abl state with the patched layer. Then each final norm (identical tensor, fetched from each repo) and one streamed
lm_head pass (stock repo) through u1_margin.two_way (e2e.Stream unchanged, both directions).

Usage: u1_fused.py run <scratch> <runs> <x16.npz> <prompt ids comma-separated>
       u1_fused.py synth <out.json>    synthetic two-way KL check vs dense (no weights)
"""
import hashlib, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import u1_margin as U
E, F = U.E, U.F

def changed_tensors():
    B = EXP / "20261110-36-weight-binding" / "runs"
    a = {t["name"]: t["sha256"] for t in json.load(open(B / "manifest-abl.json"))["tensors"]}
    s = {t["name"]: t["sha256"] for t in json.load(open(B / "manifest-stock.json"))["tensors"]}
    assert set(a) == set(s)
    return sorted(k for k in a if a[k] != s[k])

def cmd_run(scratch, runs, x16, ids):
    sc = Path(scratch); runs = Path(runs); sc.mkdir(parents=True, exist_ok=True); runs.mkdir(parents=True, exist_ok=True)
    ids = ids.split(",")
    diff = changed_tensors(); bylayer = {}
    for n in diff:
        i = int(n.split("layers.")[1].split(".")[0]); bylayer.setdefault(i, []).append(n)
    stock, abl = F.Ckpt("stock", runs), F.Ckpt("abl", runs); pool = E.make_pool()
    if (sc / "ckpt.npz").exists():
        St, meta = E.load_state(sc / "ckpt.npz"); U.plog(runs, resume=True, meta=meta)
    else:
        X, m16 = E.load_state(x16)
        St = {"S": {p: X["REF"][p] for p in ids}, "A": {p: X["REF"][p].copy() for p in ids}}
        meta = dict(next_layer=17, x16_sha256=U.sha_file(x16), prompts=ids, n_changed=len(diff))
        U.plog(runs, start=True, x16_sha256=meta["x16_sha256"], x16_meta=m16, prompts=ids,
               tokens=int(sum(St["S"][p].shape[0] for p in ids)), n_changed=len(diff), changed_layers=sorted(bylayer))
    def fetch(i):
        L = stock.layer(i); pre = F.P + f"layers.{i}."
        La = dict(L); La.update({n[len(pre):]: abl.t(n) for n in bylayer.get(i, [])})
        return L, La
    ex = ThreadPoolExecutor(1); layers = list(range(meta["next_layer"], F.NL))
    fut = ex.submit(fetch, layers[0]) if layers else None
    for n, i in enumerate(layers):
        tw = time.time(); L, La = fut.result(); wait = time.time() - tw
        stock.save(); abl.save()
        fut = ex.submit(fetch, layers[n + 1]) if n + 1 < len(layers) else None
        Xs = {"REF": St["S"]}; Xa = {"REF": St["A"]}
        r1 = E.layer_all(i, L, Xs, pool, runs, "stock", "errors-stock.jsonl")
        r2 = E.layer_all(i, La, Xa, pool, runs, "abl", "errors-abl.jsonl"); del L, La
        rel = {p: E.rel(St["A"][p], St["S"][p]) for p in ids}
        E.log(runs, "resid-abl-vs-stock.jsonl", dict(layer=i, patched=len(bylayer.get(i, [])), rel=rel))
        meta["next_layer"] = i + 1; E.save_state(sc / "ckpt.npz", St, meta)
        U.plog(runs, layer=i, patched=len(bylayer.get(i, [])), fetch_wait_s=round(wait, 1), s_stock=r1["seconds"], s_abl=r2["seconds"])
    ex.shutdown()
    Hs = U.final_hidden(stock, {"REF": St["S"]}); Ha = U.final_hidden(abl, {"REF": St["A"]})
    t0 = time.time(); res = U.two_way(Hs, Ha, E.lm_head_chunks(stock)); stock.save(); abl.save()
    out = dict(note="float64 REF stock vs float64 REF abl; D = KL(stock || abl) in nats; no integer arm in this file",
               prompts=res, seconds=round(time.time() - t0, 1), x16_sha256=meta["x16_sha256"],
               sanity_p01_last_top1=(dict(stock=res["p01-ordinary-short"]["stock_top1"][-1], abl=res["p01-ordinary-short"]["abl_top1"][-1])
                                     if "p01-ordinary-short" in res else None))
    (runs / "d-per-position.json").write_text(json.dumps(out) + "\n")
    pool.close(); pool.join(); U.plog(runs, logits_done=True, seconds=out["seconds"], sanity=out["sanity_p01_last_top1"])

def cmd_synth(out):
    rng = np.random.default_rng(0); d = 64; V = 10007; T = 7
    W = rng.normal(size=(V, d)); W[123] = W[45]
    A = rng.normal(size=(T, d)) * 0.5; B = A + 0.05 * rng.normal(size=(T, d))
    sy = U.two_way({"s": A}, {"s": B}, ((r0, W[r0:r0 + 1000]) for r0 in range(0, V, 1000)))["s"]
    ZA = A @ W.T; ZB = B @ W.T; lA = ZA - F.lse(ZA)[:, None]; lB = ZB - F.lse(ZB)[:, None]
    sA = np.sort(ZA, 1); sB = np.sort(ZB, 1)
    o = dict(D_absdiff=float(np.abs((np.exp(lA) * (lA - lB)).sum(1) - np.array(sy["D_kl_stock_abl"])).max()),
             rev_absdiff=float(np.abs((np.exp(lB) * (lB - lA)).sum(1) - np.array(sy["kl_abl_stock"])).max()),
             top1_ok=[int(v) for v in ZA.argmax(1)] == sy["stock_top1"] and [int(v) for v in ZB.argmax(1)] == sy["abl_top1"],
             margins_ok=bool(np.allclose(sA[:, -1] - sA[:, -2], sy["stock_margin"], atol=1e-12, rtol=0)
                             and np.allclose(sB[:, -1] - sB[:, -2], sy["abl_margin"], atol=1e-12, rtol=0)),
             consistent_top1=sy["abl_top1"] == sy["abl_top1_from_s1"] and sy["stock_top1"] == sy["stock_top1_from_s2"],
             n_changed_tensors=len(changed_tensors()))
    o["ok"] = bool(o["D_absdiff"] < 1e-10 and o["rev_absdiff"] < 1e-10 and o["top1_ok"] and o["margins_ok"] and o["consistent_top1"])
    Path(out).write_text(json.dumps(o, indent=1) + "\n"); print(json.dumps(o, indent=1))

if __name__ == "__main__":
    a = sys.argv
    if a[1] == "run": cmd_run(a[2], a[3], a[4], a[5])
    else: cmd_synth(a[2])
