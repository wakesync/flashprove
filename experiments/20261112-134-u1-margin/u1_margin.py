#!/usr/bin/env python3
"""U1 margin (PREREG.md): D = KL(REF_stock || REF_abl) per teacher-forced position, float64, on PR #124's 10 frozen prompts.

Only the float64 REF path. Reused unchanged:
  - PR #88 `q1_forward.py` (weights by HTTP range request, sha256 manifest; float64 layer blocks),
  - PR #124 `e2e.py`: `layer_all` (one layer for every path present; here only "REF"), `save_state` / `load_state`,
    `Stream` (online log-sum-exp KL, top-1, margin; used twice, once per direction), `lm_head_chunks`, `make_pool`.
New here: the driver below (leg order, one shared lm_head pass for both checkpoints) and the two-direction use of Stream.

Leg order: stock layers 0..16 (REF) -> x16 state; abl layers 17..63 + abl final norm -> Habl; stock layers 17..63 from
x16 + stock final norm -> Hstock; one streamed lm_head pass (stock repo; tensor identical in both checkpoints per PR #87's
manifests, sha256 checked by validate.py against both) computing KL both ways.

Usage:
  u1_margin.py run <scratch> <runs> [x16.npz]   registered run; with a third arg, layers 0..16 are not recomputed
                                                (PREREG fallback); resumes from <scratch>/ckpt.npz
  u1_margin.py fixture <scratch> <out.json>     debug: "The capital of Italy is", stock L0, abl/stock L17, full lm_head
"""
import hashlib, json, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "20261111-8-qwen-e2e-agreement"))
import e2e as E          # PR #124, unchanged (imports PR #88 q1_forward, unchanged)
F = E.F

def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def plog(runs, **kw):
    kw = dict(t=now(), **kw); E.log(runs, "progress.log.jsonl", kw); print(json.dumps(kw), flush=True)

def run_layers(leg, X, layers, ck, sc, runs, pool, meta, statefile):
    """layers: list of layer ids, all from Ckpt ck; prefetch next layer in a thread; save state after each layer."""
    from concurrent.futures import ThreadPoolExecutor
    ex = ThreadPoolExecutor(1)
    fut = ex.submit(ck.layer, layers[0]) if layers else None
    for n, i in enumerate(layers):
        tw = time.time(); L = fut.result(); wait = time.time() - tw
        ck.save()
        fut = ex.submit(ck.layer, layers[n + 1]) if n + 1 < len(layers) else None
        row = E.layer_all(i, L, X, pool, runs, leg, f"errors-{leg}.jsonl"); del L
        meta.update(leg=leg, next_layer=i + 1); E.save_state(sc / statefile, X, meta)
        plog(runs, leg=leg, layer=i, ckpt=ck.which, fetch_wait_s=round(wait, 1), layer_s=row["seconds"])
    ex.shutdown()

def final_hidden(ck, X):
    Ln = ck.t(F.P + "norm.weight"); ck.save()
    return {pid: F.rms0(x, Ln) for pid, x in X["REF"].items()}

def two_way(Hs, Ha, chunks):
    """Per prompt: S_sa = Stream(ref=stock, path 'abl') -> KL(stock||abl), stock top1/margin, abl top1;
    S_as = Stream(ref=abl, path 'stock') -> KL(abl||stock), abl margin. e2e.Stream unchanged."""
    S = {pid: (E.Stream(Hs[pid].shape[0], ["abl"]), E.Stream(Hs[pid].shape[0], ["stock"])) for pid in Hs}
    for off, W in chunks:
        WT = W.T
        for pid, (sa, as_) in S.items():
            Zs = Hs[pid] @ WT; Za = Ha[pid] @ WT
            sa.update(off, Zs, {"abl": Za}); as_.update(off, Za, {"stock": Zs})
    out = {}
    for pid, (sa, as_) in S.items():
        r1, r2 = sa.result(), as_.result()
        out[pid] = dict(T=r1["T"], stock_top1=r1["ref_top1"], stock_margin=r1["ref_margin"],
                        abl_top1=r2["ref_top1"], abl_margin=r2["ref_margin"],
                        D_kl_stock_abl=r1["paths"]["abl"]["kl"], kl_abl_stock=r2["paths"]["stock"]["kl"],
                        top1_equal=r1["paths"]["abl"]["top1_agree"],
                        abl_top1_from_s1=r1["paths"]["abl"]["top1_path"], stock_top1_from_s2=r2["paths"]["stock"]["top1_path"],
                        maxdiff_over_stock_sd=r1["paths"]["abl"]["maxdiff_over_std"])
    return out

def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def cmd_run(scratch, runs, x16=None):
    sc = Path(scratch); runs = Path(runs); sc.mkdir(parents=True, exist_ok=True); runs.mkdir(parents=True, exist_ok=True)
    prompts = json.load(open(EXP / "20261111-8-qwen-e2e-agreement" / "prompts-e2e.json"))
    stock, abl = F.Ckpt("stock", runs), F.Ckpt("abl", runs)
    pool = E.make_pool()
    if (sc / "ckpt.npz").exists():
        X, meta = E.load_state(sc / "ckpt.npz"); plog(runs, resume=True, meta=meta)
    elif x16:
        X, m16 = E.load_state(x16); X = {"REF": X["REF"]}
        meta = dict(leg="abl", next_layer=17, phase="abl", x16_external=True, x16_sha256=sha_file(x16))
        E.save_state(sc / "x16.npz", X, dict(after_layer=16, external=True))
        plog(runs, start=True, x16_external=True, x16_sha256=meta["x16_sha256"], x16_meta=m16, prompts=list(X["REF"]))
    else:
        ids = sorted({t for p in prompts["prompts"] for t in p["token_ids"]})
        emb = stock.emb_rows(ids); stock.save()
        X = {"REF": {p["id"]: np.stack([emb[t] for t in p["token_ids"]]) for p in prompts["prompts"]}}
        meta = dict(leg="shared", next_layer=0, phase="shared")
        plog(runs, start=True, prompts=list(X["REF"]))
    if meta["phase"] == "shared":
        run_layers("shared", X, list(range(meta["next_layer"], 17)), stock, sc, runs, pool, meta, "ckpt.npz")
        E.save_state(sc / "x16.npz", X, dict(after_layer=16)); meta.update(phase="abl", leg="abl", next_layer=17)
        E.save_state(sc / "ckpt.npz", X, meta)
    if meta["phase"] == "abl":
        run_layers("abl", X, list(range(meta["next_layer"], F.NL)), abl, sc, runs, pool, meta, "ckpt.npz")
        Ha = final_hidden(abl, X); E.save_state(sc / "habl.npz", {"REF": Ha}, {})
        X, _ = E.load_state(sc / "x16.npz"); X = {"REF": X["REF"]}
        meta.update(phase="stock", leg="stock", next_layer=17); E.save_state(sc / "ckpt.npz", X, meta)
        plog(runs, leg="abl", final_hidden_done=True)
    if meta["phase"] == "stock":
        run_layers("stock", X, list(range(meta["next_layer"], F.NL)), stock, sc, runs, pool, meta, "ckpt.npz")
        Hs = final_hidden(stock, X); E.save_state(sc / "hstock.npz", {"REF": Hs}, {})
        meta.update(phase="logits"); E.save_state(sc / "ckpt.npz", X, meta)
        plog(runs, leg="stock", final_hidden_done=True)
    if meta["phase"] == "logits":
        Hs = E.load_state(sc / "hstock.npz")[0]["REF"]; Ha = E.load_state(sc / "habl.npz")[0]["REF"]
        t0 = time.time(); res = two_way(Hs, Ha, E.lm_head_chunks(stock)); stock.save()
        out = dict(note="float64 REF stock vs float64 REF abl; D = KL(stock || abl) in nats; no integer arm in this file",
                   prompts=res, seconds=round(time.time() - t0, 1),
                   sanity_p01_last_top1=dict(stock=res["p01-ordinary-short"]["stock_top1"][-1],
                                             abl=res["p01-ordinary-short"]["abl_top1"][-1]))
        (runs / "d-per-position.json").write_text(json.dumps(out) + "\n")
        meta.update(phase="done"); E.save_state(sc / "ckpt.npz", X, meta)
        plog(runs, logits_done=True, seconds=out["seconds"], sanity=out["sanity_p01_last_top1"])
    pool.close(); pool.join(); plog(runs, all_done=True)

def cmd_fixture(scratch, out):
    sc = Path(scratch); sc.mkdir(parents=True, exist_ok=True); t0 = time.time()
    stock, abl = F.Ckpt("stock", sc), F.Ckpt("abl", sc); pool = E.make_pool()
    emb = stock.emb_rows(F.FIXTURE); x0 = np.stack([emb[t] for t in F.FIXTURE])
    X = {"REF": {"fx": x0.copy()}}
    E.layer_all(0, stock.layer(0), X, pool, sc, "fx", "errors-fx.jsonl")
    E.save_state(sc / "fx16.npz", X, dict(a=1)); X2, m = E.load_state(sc / "fx16.npz")
    rt = np.array_equal(X2["REF"]["fx"], X["REF"]["fx"]) and m == dict(a=1)
    Xa = {"REF": {"fx": X["REF"]["fx"].copy()}}; Xs = {"REF": {"fx": X["REF"]["fx"].copy()}}
    La = abl.layer(17); E.layer_all(17, La, Xa, pool, sc, "fxa", "errors-fx.jsonl"); del La
    Ls = stock.layer(17); E.layer_all(17, Ls, Xs, pool, sc, "fxs", "errors-fx.jsonl"); del Ls
    Ha = final_hidden(abl, Xa); Hs = final_hidden(stock, Xs)
    # full lm_head, streamed two-way vs dense reference on the same 5 tokens
    Zsl, Zal = [], []
    def chunks():
        for off, W in E.lm_head_chunks(stock):
            Zsl.append(Hs["fx"] @ W.T); Zal.append(Ha["fx"] @ W.T); yield off, W
    res = two_way(Hs, Ha, chunks())["fx"]
    Zs = np.concatenate(Zsl, 1); Za = np.concatenate(Zal, 1); del Zsl, Zal   # dense logits, same W chunks
    ls = Zs - F.lse(Zs)[:, None]; la = Za - F.lse(Za)[:, None]
    kd = (np.exp(ls) * (ls - la)).sum(1); kr = (np.exp(la) * (la - ls)).sum(1)
    s2 = np.sort(Zs, 1); a2 = np.sort(Za, 1)
    # synthetic two-way check with ties
    rng = np.random.default_rng(0); d = 64; V = 10007; T = 7
    W = rng.normal(size=(V, d)); W[123] = W[45]
    A = rng.normal(size=(T, d)) * 0.5; B = A + 0.05 * rng.normal(size=(T, d))
    sy = two_way({"s": A}, {"s": B}, ((r0, W[r0:r0 + 1000]) for r0 in range(0, V, 1000)))["s"]
    ZA = A @ W.T; ZB = B @ W.T; lA = ZA - F.lse(ZA)[:, None]; lB = ZB - F.lse(ZB)[:, None]
    o = dict(save_load_equal=bool(rt), resid_rel_abl_vs_stock_after_L17=E.rel(Xa["REF"]["fx"], Xs["REF"]["fx"]),
             lm_head_sha256=stock.man["tensors"]["lm_head.weight"]["sha256"],
             real=dict(D_stream=res["D_kl_stock_abl"], D_dense=[float(v) for v in kd],
                       D_absdiff=float(np.abs(kd - np.array(res["D_kl_stock_abl"])).max()),
                       rev_absdiff=float(np.abs(kr - np.array(res["kl_abl_stock"])).max()),
                       top1_ok=[int(v) for v in Zs.argmax(1)] == res["stock_top1"] and [int(v) for v in Za.argmax(1)] == res["abl_top1"],
                       margins_ok=bool(np.allclose(s2[:, -1] - s2[:, -2], res["stock_margin"], rtol=0, atol=1e-9)
                                       and np.allclose(a2[:, -1] - a2[:, -2], res["abl_margin"], rtol=0, atol=1e-9)),
                       last_top1=dict(stock=res["stock_top1"][-1], abl=res["abl_top1"][-1])),
             synthetic=dict(D_absdiff=float(np.abs((np.exp(lA) * (lA - lB)).sum(1) - np.array(sy["D_kl_stock_abl"])).max()),
                            rev_absdiff=float(np.abs((np.exp(lB) * (lB - lA)).sum(1) - np.array(sy["kl_abl_stock"])).max()),
                            top1_ok=[int(v) for v in ZA.argmax(1)] == sy["stock_top1"] and [int(v) for v in ZB.argmax(1)] == sy["abl_top1"],
                            consistent_top1=sy["abl_top1"] == sy["abl_top1_from_s1"] and sy["stock_top1"] == sy["stock_top1_from_s2"]),
             seconds=round(time.time() - t0, 1))
    ok = (o["save_load_equal"] and o["real"]["D_absdiff"] < 1e-9 and o["real"]["rev_absdiff"] < 1e-9 and o["real"]["top1_ok"]
          and o["real"]["margins_ok"] and o["synthetic"]["D_absdiff"] < 1e-10 and o["synthetic"]["rev_absdiff"] < 1e-10
          and o["synthetic"]["top1_ok"] and o["synthetic"]["consistent_top1"])
    o["fixture_ok"] = bool(ok)
    pool.close(); pool.join()
    Path(out).write_text(json.dumps(o, indent=1) + "\n"); print(json.dumps(o, indent=1))
    sys.exit(0 if ok else 3)

if __name__ == "__main__":
    a = sys.argv
    if a[1] == "run": cmd_run(a[2], a[3], a[4] if len(a) > 4 else None)
    else: cmd_fixture(a[2], a[3])
