#!/usr/bin/env python3
"""End-to-end, teacher-forced token agreement of the XS18 / XS20 DeltaNet head lowerings vs float64 (PREREG.md).

Only the DeltaNet head computation (conv, SiLU, L2 norms, gates, recurrence, gated norm) is lowered. in_proj, out_proj,
full attention, MLP, every RMSNorm, the final norm and lm_head stay float64. No proof, no soundness claim.

Float64 forward, weight fetch and head code: PR #88 `q1_forward.py`, PR #74 `scaled_head.py`, PR #68 `real_head.py`,
imported unchanged.

Paths (PREREG "Setup"): REF, XS18, XS20 on all 10 prompts; BF16H on 5 (context only); REF#2, XS18#2 on 3 (determinism).
Every dense step is one call per (path, prompt) so that duplicate paths see identical shapes.

Legs, in this order: "abl" = stock layers 0..16 (byte-identical in both checkpoints, PR #68), then abl layers 17..63,
abl final norm and lm_head; "stock" = from the saved state after layer 16, stock layers 17..63, final norm, lm_head.
After every layer the full state is saved (atomic rename) so a lost process resumes at the next layer.

Usage:
  e2e.py run <scratch> <runs>        registered run (resumes from <scratch>/ckpt.npz if present)
  e2e.py fixture <scratch> <out>     debug: "The capital of Italy is", stock layers 0..3, plus synthetic logit check
"""
import json, math, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "20261110-8-qwen-q1-deep-fidelity"))
import q1_forward as F   # PR #88, unchanged (imports scaled_head PR #74 and real_head PR #68, unchanged)

NL = F.NL
ARMS = json.load(open(EXP / "20261110-8-qwen-q1-deep-fidelity" / "arms-q1.json"))
MODE = {"REF": ("REF", None), "REF#2": ("REF", None), "BF16H": ("BF16H", None),
        "XS18": ("INT", "XS18"), "XS18#2": ("INT", "XS18"), "XS20": ("INT", "XS20")}
PATH_ORDER = ["REF", "XS18", "XS20", "BF16H", "REF#2", "XS18#2"]
TOKYO = 25358
NOTE = ("only the DeltaNet head computation is lowered; in_proj, out_proj, full attention, MLP, norms, final norm and "
        "lm_head are float64; no proof; arms are numerical lowerings, not sound relations")

# ------------------------------------------------------------------ worker (spawned, 1 BLAS thread)
def head_task(path, pid, hd):
    mode, arm = MODE[path]
    try:
        cfg = ARMS[arm]["cfg"] if arm else None
        y = F.head_out(hd, mode, cfg)
        relh = None
        if mode == "INT":   # closed-loop local per-head error: float64 heads on this path's own head inputs
            yf = F.head_out(hd, "REF")
            num = np.sqrt(((y - yf) ** 2).sum(axis=(0, 2))); den = np.sqrt((yf ** 2).sum(axis=(0, 2)))
            relh = [float(a / b) if b else float("nan") for a, b in zip(num, den)]
        return path, pid, y, relh, None
    except OverflowError as e:
        return path, pid, None, None, "OverflowError: " + str(e)

# ------------------------------------------------------------------ state
def save_state(path, X, meta):
    tmp = Path(str(path) + ".tmp.npz")
    np.savez(tmp, __meta__=np.frombuffer(json.dumps(meta).encode(), dtype=np.uint8),
             **{f"{p}|{pid}": (x if x is not None else np.zeros(0)) for p, d in X.items() for pid, x in d.items()})
    os.replace(tmp, path)

def load_state(path):
    d = np.load(path); meta = json.loads(bytes(d["__meta__"]).decode()); X = {}
    for k in d.files:
        if k == "__meta__": continue
        p, pid = k.split("|"); X.setdefault(p, {})[pid] = d[k] if d[k].size else None
    return X, meta

def log(runs, name, obj):
    with open(Path(runs) / name, "a") as f: f.write(json.dumps(obj) + "\n")

def rel(a, b):
    nb = float(np.linalg.norm(b)); return float(np.linalg.norm(a - b)) / nb if nb else float("nan")

# ------------------------------------------------------------------ one layer, all paths
def layer_all(i, L, X, pool, runs, leg, errname):
    t0 = time.time()
    if F.layer_type(i) == "linear_attention":
        pend = []
        for p in PATH_ORDER:
            for pid, x in X.get(p, {}).items():
                if x is None: continue
                hd = F.deltanet_inputs(L, x)
                pend.append(pool.apply_async(head_task, (p, pid, hd)))
        tin = time.time() - t0
        Wo = L["linear_attn.out_proj.weight"]; heads_rows = []
        for r in pend:
            p, pid, y, relh, err = r.get()
            if err is not None:
                log(runs, errname, dict(leg=leg, layer=i, path=p, prompt=pid, error=err)); X[p][pid] = None; continue
            x = X[p][pid]
            x = x + y.reshape(y.shape[0], -1) @ Wo.T
            X[p][pid] = x + F.mlp(L, x)
            if relh is not None: heads_rows.append(dict(leg=leg, layer=i, path=p, prompt=pid, rel_y=relh))
        for row in heads_rows: log(runs, f"heads-{leg}.jsonl", row)
        tt = dict(inputs_s=round(tin, 1))
    else:
        for p in PATH_ORDER:
            for pid, x in X.get(p, {}).items():
                if x is None: continue
                x = x + F.attention(L, x)
                X[p][pid] = x + F.mlp(L, x)
        tt = {}
    row = dict(leg=leg, layer=i, type=F.layer_type(i), seconds=round(time.time() - t0, 1), **tt)
    for p in PATH_ORDER:
        if p == "REF" or p not in X: continue
        ref = "REF"
        row[p] = {pid: (rel(x, X[ref][pid]) if x is not None else None) for pid, x in X[p].items()}
    det = {}
    for p2, p1 in (("REF#2", "REF"), ("XS18#2", "XS18")):
        for pid, x in X.get(p2, {}).items():
            a = X[p1][pid]
            det[f"{p2}|{pid}"] = bool(x is not None and a is not None and x.shape == a.shape and np.array_equal(x, a))
    row["det_bit_equal"] = det
    log(runs, f"divergence-{leg}.jsonl", row)
    return row

# ------------------------------------------------------------------ streaming logit metrics
class Stream:
    """Online per-position statistics over vocabulary chunks for one prompt: REF and every other path on it."""
    def __init__(self, T, paths):
        self.T = T; self.paths = paths
        z = lambda v: np.full(T, v, dtype=np.float64)
        self.r = dict(m=z(-np.inf), s=z(0.0), t1=z(-np.inf), t1i=np.zeros(T, np.int64), t2=z(-np.inf), n=0, mean=z(0.0), M2=z(0.0))
        self.p = {p: dict(m=z(-np.inf), s=z(0.0), t1=z(-np.inf), t1i=np.zeros(T, np.int64), A=z(0.0), mad=z(0.0)) for p in paths}

    @staticmethod
    def _lse_upd(st, Z):
        cm = Z.max(1); nm = np.maximum(st["m"], cm)
        sc = np.exp(st["m"] - nm); sc[~np.isfinite(st["m"])] = 0.0
        st["s"] = st["s"] * sc + np.exp(Z - nm[:, None]).sum(1)
        old = st["m"]; st["m"] = nm
        return old, nm, sc

    @staticmethod
    def _top_upd(st, Z, off, second=False):
        ci = Z.argmax(1); cv = Z[np.arange(Z.shape[0]), ci]
        if second:
            Z2 = Z.copy(); Z2[np.arange(Z.shape[0]), ci] = -np.inf; c2 = Z2.max(1)
            # new top2 = second largest of {t1, t2, cv, c2}
            better = cv > st["t1"]
            st["t2"] = np.where(better, np.maximum(st["t1"], c2), np.maximum(st["t2"], cv))
        better = cv > st["t1"]       # strict: ties keep the lower vocabulary id (chunks arrive in id order)
        st["t1"] = np.where(better, cv, st["t1"]); st["t1i"] = np.where(better, ci + off, st["t1i"])

    def update(self, off, Zr, Zp):
        r = self.r
        old, nm, sc = self._lse_upd(r, Zr)
        self._top_upd(r, Zr, off, second=True)
        # Chan combine for the population mean / M2 of REF logits
        nb = Zr.shape[1]; mb = Zr.mean(1); M2b = ((Zr - mb[:, None]) ** 2).sum(1); na = r["n"]; n = na + nb
        d = mb - r["mean"]; r["mean"] = r["mean"] + d * nb / n; r["M2"] = r["M2"] + M2b + d * d * na * nb / n; r["n"] = n
        er = np.exp(Zr - nm[:, None])
        for p, Zq in Zp.items():
            q = self.p[p]
            self._lse_upd(q, Zq); self._top_upd(q, Zq, off)
            q["A"] = q["A"] * sc + (er * (Zr - Zq)).sum(1)
            q["mad"] = np.maximum(q["mad"], np.abs(Zr - Zq).max(1))

    def result(self):
        r = self.r; lr = r["m"] + np.log(r["s"]); sd = np.sqrt(r["M2"] / r["n"])
        out = dict(T=self.T, ref_top1=[int(v) for v in r["t1i"]], ref_margin=[float(v) for v in r["t1"] - r["t2"]], paths={})
        for p, q in self.p.items():
            lp = q["m"] + np.log(q["s"])
            kl = q["A"] / r["s"] - lr + lp
            out["paths"][p] = dict(top1_agree=[bool(v) for v in q["t1i"] == r["t1i"]], kl=[float(v) for v in kl],
                                   maxdiff_over_std=[float(v) for v in q["mad"] / sd], top1_path=[int(v) for v in q["t1i"]])
        return out

def logits_metrics(Hn, chunks):
    """Hn: {path: {pid: (T, d) normed final hidden or None}}; chunks: iterator of (row_offset, W (r, d) float64).
    One matmul per (path, prompt) block and chunk. Dead paths (None) are skipped and reported as dead."""
    S = {pid: Stream(Hn["REF"][pid].shape[0], [p for p in PATH_ORDER if p != "REF" and pid in Hn.get(p, {})
                                                 and Hn[p][pid] is not None]) for pid in Hn["REF"]}
    for off, W in chunks:
        WT = W.T
        for pid, st in S.items():
            Zr = Hn["REF"][pid] @ WT
            st.update(off, Zr, {p: Hn[p][pid] @ WT for p in st.paths})
    res = {pid: st.result() for pid, st in S.items()}
    for pid in res:
        for p in PATH_ORDER:
            if p != "REF" and pid in Hn.get(p, {}) and Hn[p][pid] is None: res[pid]["paths"][p] = None
    return res

def lm_head_chunks(C, rows_per=4096):
    """Stream lm_head.weight (BF16) in row chunks, sha256 over the whole tensor into C's manifest."""
    import hashlib
    name = "lm_head.weight"; shard = C.wm[name]; hl, h = C.header(shard); b, e = h[name]["data_offsets"]
    V, d = h[name]["shape"]; row = 2 * d; lo0 = 8 + hl + b; sha = hashlib.sha256()
    ranges = [(r0, min(r0 + rows_per, V)) for r0 in range(0, V, rows_per)]
    fetch = lambda r: F.get(C.base + shard, f"bytes={lo0 + r[0] * row}-{lo0 + r[1] * row - 1}")
    ex = ThreadPoolExecutor(4); futs = [ex.submit(fetch, rg) for rg in ranges[:4]]; k = 4
    for j, (r0, r1) in enumerate(ranges):
        data = futs[j].result(); futs[j] = None
        if k < len(ranges): futs.append(ex.submit(fetch, ranges[k])); k += 1
        assert len(data) == (r1 - r0) * row
        sha.update(data)
        W = (np.frombuffer(data, dtype="<u2").astype(np.uint32) << 16).view(np.float32).reshape(r1 - r0, d).astype(np.float64)
        yield r0, W
    C.man["tensors"][name] = dict(shard=shard, range=f"bytes={lo0}-{lo0 + V * row - 1}", nbytes=V * row, dtype="BF16",
                                  shape=[V, d], sha256=sha.hexdigest())

# ------------------------------------------------------------------ driver
def init_paths(prompts, emb):
    pr = {p["id"]: np.stack([emb[t] for t in p["token_ids"]]) for p in prompts["prompts"]}
    X = {}
    for p in PATH_ORDER:
        ids = list(pr) if p in ("REF", "XS18", "XS20") else (prompts["bf16h_subset"] if p == "BF16H" else prompts["determinism_subset"])
        X[p] = {pid: pr[pid].copy() for pid in ids}
    return X

def run_leg(leg, X, i0, layers, ckpts, sc, runs, pool, meta, finish):
    """layers: list of (i, ckpt_name). Saves state after every layer; finish(X) computes logits at the end."""
    fetch_ex = ThreadPoolExecutor(1)
    sub = lambda k: fetch_ex.submit(ckpts[layers[k][1]].layer, layers[k][0])
    todo = [k for k, (i, _) in enumerate(layers) if i >= i0]
    fut = sub(todo[0]) if todo else None
    for n, k in enumerate(todo):
        i, ck = layers[k]
        tw = time.time(); L = fut.result(); wait = time.time() - tw
        ckpts[ck].save()                                       # manifest written while no fetch is in flight
        fut = sub(todo[n + 1]) if n + 1 < len(todo) else None
        row = layer_all(i, L, X, pool, runs, leg, f"errors-{leg}.jsonl"); del L
        meta.update(leg=leg, next_layer=i + 1); save_state(sc / "ckpt.npz", X, meta)
        if i == 16 and leg == "abl": save_state(sc / "x16.npz", X, dict(after_layer=16))
        log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), leg=leg, layer=i, ckpt=ck,
                                              fetch_wait_s=round(wait, 1), layer_s=row["seconds"]))
        print(leg, "layer", i, ck, F.layer_type(i), "wait", round(wait, 1), "s", row["seconds"], flush=True)
    finish(X)

def finish_leg(leg, ck, X, C, runs, sc, meta):
    t0 = time.time(); Ln = C.t(F.P + "norm.weight")
    Hn = {p: {pid: (F.rms0(x, Ln) if x is not None else None) for pid, x in d.items()} for p, d in X.items()}
    res = logits_metrics(Hn, lm_head_chunks(C)); C.save()
    p01 = res.get("p01-ordinary-short")
    out = dict(leg=leg, checkpoint=ck, note=NOTE, prompts=res, seconds=round(time.time() - t0, 1),
               sanity_p01_last_top1=p01["ref_top1"][-1], sanity_pass=p01["ref_top1"][-1] == TOKYO)
    (Path(runs) / f"e2e-{leg}.json").write_text(json.dumps(out) + "\n")
    meta.setdefault("legs_done", []).append(leg); meta.update(next_layer=None); save_state(sc / "ckpt.npz", X, meta)
    log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), leg=leg, logits_done=True,
                                          seconds=out["seconds"], sanity_pass=out["sanity_pass"]))
    print(leg, "logits done", out["seconds"], "sanity", out["sanity_pass"], flush=True)

def make_pool():
    import multiprocessing as mp
    old = {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}
    for k in old: os.environ[k] = "1"
    pool = mp.get_context("spawn").Pool(6)
    for k, v in old.items():
        if v is None: os.environ.pop(k, None)
        else: os.environ[k] = v
    return pool

def cmd_run(scratch, runs):
    sc = Path(scratch); runs = Path(runs); sc.mkdir(parents=True, exist_ok=True); runs.mkdir(parents=True, exist_ok=True)
    prompts = json.load(open(HERE / "prompts-e2e.json"))
    ckpts = {"stock": F.Ckpt("stock", runs), "abl": F.Ckpt("abl", runs)}
    pool = make_pool()
    if (sc / "ckpt.npz").exists():
        X, meta = load_state(sc / "ckpt.npz")
        log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), resume=True, meta=meta))
    else:
        ids = sorted({t for p in prompts["prompts"] for t in p["token_ids"]})
        emb = ckpts["stock"].emb_rows(ids); ckpts["stock"].save()
        X = init_paths(prompts, emb); meta = dict(leg="abl", next_layer=0, legs_done=[])
        log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), start=True,
                                              paths={p: list(d) for p, d in X.items()}))
    if "abl" not in meta.get("legs_done", []):
        layers = [(i, "stock" if i <= 16 else "abl") for i in range(NL)]
        i0 = meta["next_layer"] if meta.get("leg") == "abl" and meta.get("next_layer") is not None else NL
        run_leg("abl", X, i0, layers, ckpts, sc, runs, pool, meta,
                lambda X: finish_leg("abl", "abl", X, ckpts["abl"], runs, sc, meta))
    if "stock" not in meta.get("legs_done", []):
        if meta.get("leg") != "stock" or meta.get("next_layer") is None:
            X, _ = load_state(sc / "x16.npz"); meta.update(leg="stock", next_layer=17)
        layers = [(i, "stock") for i in range(17, NL)]
        run_leg("stock", X, meta["next_layer"], layers, ckpts, sc, runs, pool, meta,
                lambda X: finish_leg("stock", "stock", X, ckpts["stock"], runs, sc, meta))
    pool.close(); pool.join()
    log(runs, "progress.log.jsonl", dict(t=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), all_done=True))

def cmd_fixture(scratch, out):
    """Debug only (PREREG): the fixture prompt, stock layers 0..3, every path; save/load round trip; resume equality;
    streaming logit metrics on synthetic logits against a dense computation."""
    sc = Path(scratch); sc.mkdir(parents=True, exist_ok=True); t0 = time.time()
    C = F.Ckpt("stock", sc); pool = make_pool()
    emb = C.emb_rows(F.FIXTURE); x0 = np.stack([emb[t] for t in F.FIXTURE])
    X = {p: {"fx": x0.copy()} for p in PATH_ORDER}
    # straight run X and a run Y that is saved and reloaded after layer 1 (resume equality)
    Y = {p: {"fx": x0.copy()} for p in PATH_ORDER}
    for i in range(4):
        L = C.layer(i)
        layer_all(i, L, X, pool, sc, "fx", "errors-fx.jsonl")
        layer_all(i, L, Y, pool, sc, "fx2", "errors-fx.jsonl"); del L
        if i == 1:
            save_state(sc / "fx2.npz", Y, {}); Y, _ = load_state(sc / "fx2.npz")
    save_state(sc / "fx.npz", X, dict(a=1)); X2, m2 = load_state(sc / "fx.npz")
    rt = all(np.array_equal(X[p][k], X2[p][k]) for p in X for k in X[p]) and m2 == dict(a=1)
    resume_eq = all(np.array_equal(X[p]["fx"], Y[p]["fx"]) for p in X)
    # synthetic logits: streaming vs dense
    rng = np.random.default_rng(0); d = 64; V = 10007; T = 7
    W = rng.normal(size=(V, d)); W[123] = W[45]          # exact tie between ids 45 and 123
    Hn = {p: {"s": rng.normal(size=(T, d)) * 0.5} for p in PATH_ORDER}
    Hn["XS18"]["s"] = Hn["REF"]["s"] + 1e-3 * rng.normal(size=(T, d)); Hn["REF#2"]["s"] = Hn["REF"]["s"].copy()
    res = logits_metrics(Hn, ((r0, W[r0:r0 + 1000]) for r0 in range(0, V, 1000)))["s"]
    Zr = Hn["REF"]["s"] @ W.T; lr = Zr - F.lse(Zr)[:, None]
    worst = {}
    for p in ("XS18", "XS20", "REF#2"):
        Zp = Hn[p]["s"] @ W.T; lp = Zp - F.lse(Zp)[:, None]
        kl = (np.exp(lr) * (lr - lp)).sum(1)
        worst[p] = dict(kl_absdiff=float(np.abs(kl - np.array(res["paths"][p]["kl"])).max()),
                        top1_equal=[int(v) for v in Zp.argmax(1)] == res["paths"][p]["top1_path"],
                        mad_equal=bool(np.allclose(np.abs(Zr - Zp).max(1) / Zr.std(1), res["paths"][p]["maxdiff_over_std"], rtol=1e-12)))
    s2 = np.sort(Zr, 1)
    margin_ok = bool(np.allclose(s2[:, -1] - s2[:, -2], res["ref_margin"], rtol=0, atol=1e-12))
    o = dict(fixture_layers=4, paths=list(X), resid_rel_vs_ref={p: rel(X[p]["fx"], X["REF"]["fx"]) for p in X},
             det_equal={p2: bool(np.array_equal(X[p2]["fx"], X[p1]["fx"])) for p2, p1 in (("REF#2", "REF"), ("XS18#2", "XS18"))},
             save_load_equal=rt, resume_equal=resume_eq, synthetic=worst, ref_top1_equal=[int(v) for v in Zr.argmax(1)] == res["ref_top1"],
             margin_ok=margin_ok, kl_self=max(res["paths"]["REF#2"]["kl"]), seconds=round(time.time() - t0, 1))
    pool.close(); pool.join()
    Path(out).write_text(json.dumps(o, indent=1) + "\n"); print(json.dumps(o, indent=1))

if __name__ == "__main__":
    {"run": cmd_run, "fixture": cmd_fixture}[sys.argv[1]](sys.argv[2], sys.argv[3])
