#!/usr/bin/env python3
"""End-to-end, teacher-forced token agreement with PR #159's table decays (U4, U3) inside PR #124's XS18 heads,
abliterated leg only (PREREG.md).

Paths: REF (float64), XS18 (PR #124's arm, unchanged, the control), XS18+U4 and XS18+U3 (XS18 with the decay a
replaced by PR #159's arm emulation, converted from 2^-20 to XS18's 2^-18 by a18 = floor((a20 + 2) / 4)),
REF#2 and XS18+U4#2 on p01 and p09 (determinism).

Only the DeltaNet head computation is lowered; in_proj, out_proj, full attention, MLP, every RMSNorm, the final norm
and lm_head are float64 in every path. In the U paths only the decay value a differs from XS18. No proof.

Imported unchanged: PR #88 `q1_forward.py` (forward, weight fetch, head inputs), PR #74 `scaled_head.py` (Head),
PR #124 `e2e.py` (Stream, logits_metrics, lm_head_chunks, save_state, load_state, rel), PR #159 `decay_r2.py`
(arm_decay, load_tables). The decay substitution is a subclass of scaled_head.Head whose `run` is Head.run's own
source with exactly one line changed (the `a = ...` line), asserted to match once.

Usage:
  decay_e2e.py fine20  <scratch>                 2^20-row fine exp table for U3 (PR #159's generator) -> <scratch>/fine20.npy
  decay_e2e.py fixture <scratch> <out.json>      debug: "The capital of Italy is", stock layers 0..3, all paths
  decay_e2e.py run     <scratch> <runs>          registered run (resumes from <scratch>/ckpt.npz)
"""
import inspect, json, math, os, sys, textwrap, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "20261111-8-qwen-e2e-agreement"))
sys.path.insert(0, str(EXP / "20261113-155-deltanet-decay-r2"))
import e2e as E            # PR #124, unchanged (imports q1_forward PR #88, scaled_head PR #74, real_head PR #68)
import decay_r2 as DR      # PR #159, unchanged
F = E.F
SH = F.SH

XS18 = E.ARMS["XS18"]["cfg"]
FG = XS18["Fg"]; FAB = XS18["Fab"]
assert FG == 18 and DR.G == 20
PATHS = ["REF", "XS18", "XS18+U4", "XS18+U3", "REF#2", "XS18+U4#2"]
DECAY = {"REF": None, "REF#2": None, "XS18": "float", "XS18+U4": "U4", "XS18+U4#2": "U4", "XS18+U3": "U3"}
DET_SUBSET = ["p01-ordinary-short", "p09-multilingual"]
DET_PAIRS = (("REF#2", "REF"), ("XS18+U4#2", "XS18+U4"))
TOKYO = 25358
NOTE = ("abliterated leg only; only the DeltaNet head computation is lowered (XS18), and in the U paths only the decay "
        "a differs (PR #159 U4 / U3 at 2^-20, shifted to 2^-18 with round half up); in_proj, out_proj, attention, MLP, "
        "norms and lm_head are float64; no proof")

# ------------------------------------------------------------------ the one-line decay substitution
_OLD = 'a = math.ldexp(1.0, c["Fg"]) * np.exp(-A * np.logaddexp(0.0, xa))'
_NEW = 'a = self.decay_at(t, math.ldexp(1.0, c["Fg"]) * np.exp(-A * np.logaddexp(0.0, xa)))'
_src = textwrap.dedent(inspect.getsource(SH.Head.run))
assert _src.count(_OLD) == 1, "the decay line of scaled_head.Head.run is not the registered one"
SUBST_SOURCE = _src.replace(_OLD, _NEW)
_ns = dict(vars(SH))
exec(compile(SUBST_SOURCE, "scaled_head.Head.run[decay line substituted]", "exec"), _ns)

class DecayHead(SH.Head):
    """XS18 head; a18 None = XS18's own float decay (control), else a (T, 48) array of integers at 2^18."""
    def __init__(self, cfg, a18=None):
        super().__init__(cfg); self.a18 = a18
    def decay_at(self, t, a_float):
        return a_float if self.a18 is None else self.a18[t]
    run = _ns["run"]

def to18(a20):
    """Registered conversion: floor((a20 + 2) / 4), a20 >= 0 integer at 2^20 (int64 arithmetic, exact)."""
    a20 = np.asarray(a20, dtype=np.int64); assert (a20 >= 0).all()
    return ((a20 + 2) >> 2).astype(np.float64)

def table_decay(ar, A, dtb, arm, T):
    """-> (a18 (T, H) float64 integers, a20 int64) or raises OverflowError on a rejected lookup."""
    a, rej = DR.arm_decay(ar, A, dtb, arm, T)
    if rej.any():
        raise OverflowError(f"guard decay {arm}: {int(rej.sum())} rejected lookups")
    a20 = np.rint(np.ldexp(a, DR.G)).astype(np.int64)
    assert np.array_equal(np.ldexp(a20.astype(np.float64), -DR.G), a), "arm_decay output is not an integer at 2^-20"
    return to18(a20), a20

def xs18_float_decay18(ar, A, dtb):
    """The a XS18 uses (scaled_head.Head.run, gates rounded): rint(2^18 exp(-A softplus(rint(2^14 ar) 2^-14 + dtb)))."""
    ari = np.rint(ar * math.ldexp(1.0, FAB))
    xa = ari * math.ldexp(1.0, -FAB) + dtb[None, :]
    return np.rint(math.ldexp(1.0, FG) * np.exp(-A[None, :] * np.logaddexp(0.0, xa)))

# ------------------------------------------------------------------ worker (spawned, 1 BLAS thread)
def head_task(path, pid, hd, a18):
    try:
        if DECAY[path] is None:
            return path, pid, F.head_out(hd, "REF"), None, None
        xq, xk, xv, ar, br, zz, Wc, A, dtb, gain = hd
        h = DecayHead(XS18, a18)
        y = np.stack([y for _, _, y, _ in h.run(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, {})]) * math.ldexp(1.0, -h.c["Fy"])
        yf = F.head_out(hd, "REF")
        num = np.sqrt(((y - yf) ** 2).sum(axis=(0, 2))); den = np.sqrt((yf ** 2).sum(axis=(0, 2)))
        return path, pid, y, [float(a / b) if b else float("nan") for a, b in zip(num, den)], None
    except OverflowError as e:
        return path, pid, None, None, "OverflowError: " + str(e)

def make_pool():
    import multiprocessing as mp
    old = {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}
    for k in old: os.environ[k] = "1"
    pool = mp.get_context("spawn").Pool(6)
    for k, v in old.items():
        if v is None: os.environ.pop(k, None)
        else: os.environ[k] = v
    return pool

def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# ------------------------------------------------------------------ one layer, all paths
def layer_all(i, L, X, pool, runs, leg, T, errname):
    t0 = time.time(); drow = {}
    if F.layer_type(i) == "linear_attention":
        pend = []; dec = {}
        for p in PATHS:
            for pid, x in X.get(p, {}).items():
                if x is None: continue
                hd = F.deltanet_inputs(L, x); ar, A, dtb = hd[3], hd[7], hd[8]
                a18 = None
                if DECAY[p] is not None:
                    af = np.exp(-A[None, :] * np.logaddexp(0.0, ar + dtb[None, :]))
                    if DECAY[p] == "float":
                        used = xs18_float_decay18(ar, A, dtb)
                    else:
                        try:
                            a18, _ = table_decay(ar, A, dtb, DECAY[p], T); used = a18
                        except OverflowError as e:
                            E.log(runs, errname, dict(leg=leg, layer=i, path=p, prompt=pid, error=str(e))); X[p][pid] = None; continue
                    dec.setdefault(p, {})[pid] = float(np.abs(np.ldexp(used, -FG) - af).max())
                pend.append(pool.apply_async(head_task, (p, pid, hd, a18)))
        tin = time.time() - t0
        Wo = L["linear_attn.out_proj.weight"]; heads_rows = []
        for r in pend:
            p, pid, y, relh, err = r.get()
            if err is not None:
                E.log(runs, errname, dict(leg=leg, layer=i, path=p, prompt=pid, error=err)); X[p][pid] = None; continue
            x = X[p][pid]
            x = x + y.reshape(y.shape[0], -1) @ Wo.T
            X[p][pid] = x + F.mlp(L, x)
            if relh is not None: heads_rows.append(dict(leg=leg, layer=i, path=p, prompt=pid, rel_y=relh))
        for row in heads_rows: E.log(runs, f"heads-{leg}.jsonl", row)
        if dec: E.log(runs, f"decay-err-{leg}.jsonl", dict(leg=leg, layer=i, max_abs_a_minus_float=dec))
        tt = dict(inputs_s=round(tin, 1))
    else:
        for p in PATHS:
            for pid, x in X.get(p, {}).items():
                if x is None: continue
                x = x + F.attention(L, x)
                X[p][pid] = x + F.mlp(L, x)
        tt = {}
    row = dict(leg=leg, layer=i, type=F.layer_type(i), seconds=round(time.time() - t0, 1), **tt)
    for p in PATHS:
        if p == "REF" or p not in X: continue
        row[p] = {pid: (E.rel(x, X["REF"][pid]) if x is not None else None) for pid, x in X[p].items()}
    det = {}
    for p2, p1 in DET_PAIRS:
        for pid, x in X.get(p2, {}).items():
            a = X[p1][pid]
            det[f"{p2}|{pid}"] = bool(x is not None and a is not None and x.shape == a.shape and np.array_equal(x, a))
    row["det_bit_equal"] = det
    E.log(runs, f"divergence-{leg}.jsonl", row)
    return row

# ------------------------------------------------------------------ registered run
def init_paths(prompts, emb):
    pr = {p["id"]: np.stack([emb[t] for t in p["token_ids"]]) for p in prompts["prompts"]}
    X = {}
    for p in PATHS:
        ids = DET_SUBSET if p.endswith("#2") else list(pr)
        X[p] = {pid: pr[pid].copy() for pid in ids}
    return X

def cmd_run(scratch, runs):
    sc = Path(scratch); runs = Path(runs); sc.mkdir(parents=True, exist_ok=True); runs.mkdir(parents=True, exist_ok=True)
    E.PATH_ORDER = PATHS          # used by E.logits_metrics (main process only)
    prompts = json.load(open(E.HERE / "prompts-e2e.json"))
    for pid in DET_SUBSET: assert pid in {p["id"] for p in prompts["prompts"]}
    T = DR.load_tables(sc / "fine20.npy")
    ckpts = {"stock": F.Ckpt("stock", runs), "abl": F.Ckpt("abl", runs)}
    pool = make_pool()
    if (sc / "ckpt.npz").exists():
        X, meta = E.load_state(sc / "ckpt.npz")
        E.log(runs, "progress.log.jsonl", dict(t=now(), resume=True, meta=meta))
    else:
        ids = sorted({t for p in prompts["prompts"] for t in p["token_ids"]})
        emb = ckpts["stock"].emb_rows(ids); ckpts["stock"].save()
        X = init_paths(prompts, emb); meta = dict(leg="abl", next_layer=0, done=False)
        E.log(runs, "progress.log.jsonl", dict(t=now(), start=True, tables_sha256=T["sha"], paths={p: list(d) for p, d in X.items()}))
    layers = [(i, "stock" if i <= 16 else "abl") for i in range(F.NL)]
    todo = [(i, ck) for i, ck in layers if meta.get("next_layer") is not None and i >= meta["next_layer"]]
    ex = ThreadPoolExecutor(1)
    fut = ex.submit(ckpts[todo[0][1]].layer, todo[0][0]) if todo else None
    for n, (i, ck) in enumerate(todo):
        tw = time.time(); L = fut.result(); wait = time.time() - tw
        ckpts[ck].save()
        fut = ex.submit(ckpts[todo[n + 1][1]].layer, todo[n + 1][0]) if n + 1 < len(todo) else None
        row = layer_all(i, L, X, pool, runs, "abl", T, "errors-abl.jsonl"); del L
        meta.update(next_layer=i + 1 if i + 1 < F.NL else None); E.save_state(sc / "ckpt.npz", X, meta)
        E.log(runs, "progress.log.jsonl", dict(t=now(), layer=i, ckpt=ck, fetch_wait_s=round(wait, 1), layer_s=row["seconds"]))
        print("abl layer", i, ck, F.layer_type(i), "wait", round(wait, 1), "s", row["seconds"], flush=True)
    if not meta.get("done"):
        t0 = time.time(); C = ckpts["abl"]; Ln = C.t(F.P + "norm.weight")
        Hn = {p: {pid: (F.rms0(x, Ln) if x is not None else None) for pid, x in d.items()} for p, d in X.items()}
        res = E.logits_metrics(Hn, E.lm_head_chunks(C)); C.save()
        p01 = res["p01-ordinary-short"]
        out = dict(leg="abl", checkpoint="abl", note=NOTE, prompts=res, seconds=round(time.time() - t0, 1),
                   sanity_p01_last_top1=p01["ref_top1"][-1], sanity_pass=p01["ref_top1"][-1] == TOKYO)
        (runs / "e2e-abl.json").write_text(json.dumps(out) + "\n")
        meta.update(done=True); E.save_state(sc / "ckpt.npz", X, meta)
        E.log(runs, "progress.log.jsonl", dict(t=now(), logits_done=True, seconds=out["seconds"], sanity_pass=out["sanity_pass"]))
        print("abl logits done", out["seconds"], "sanity", out["sanity_pass"], flush=True)
    pool.close(); pool.join()
    E.log(runs, "progress.log.jsonl", dict(t=now(), all_done=True))

# ------------------------------------------------------------------ debug fixture (not a suite prompt)
def cmd_fixture(scratch, out):
    sc = Path(scratch); sc.mkdir(parents=True, exist_ok=True); t0 = time.time()
    E.PATH_ORDER = PATHS
    T = DR.load_tables(sc / "fine20.npy")
    C = F.Ckpt("stock", sc); pool = make_pool()
    emb = C.emb_rows(F.FIXTURE); x0 = np.stack([emb[t] for t in F.FIXTURE])
    X = {p: {"fx": x0.copy()} for p in PATHS}; Y = {p: {"fx": x0.copy()} for p in PATHS}
    checks = dict(control_bit_identical=[], u_decay_equal=[])
    for i in range(4):
        L = C.layer(i)
        if F.layer_type(i) == "linear_attention":
            # (a) control: substituted run with a18=None is bit-identical to scaled_head.Head.run
            hd = F.deltanet_inputs(L, X["XS18"]["fx"])
            y0 = F.head_out(hd, "INT", XS18)
            xq, xk, xv, ar, br, zz, Wc, A, dtb, gain = hd
            y1 = np.stack([y for _, _, y, _ in DecayHead(XS18).run(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, {})]) * math.ldexp(1.0, -XS18["Fy"])
            checks["control_bit_identical"].append(dict(layer=i, equal=bool(np.array_equal(y0, y1))))
            # (b) the a used inside the head equals the converted table value
            for arm in ("U4", "U3"):
                a18, a20 = table_decay(ar, A, dtb, arm, T)
                seen = []
                class Rec(DecayHead):
                    def decay_at(self, t, a_float):
                        v = DecayHead.decay_at(self, t, a_float); seen.append(np.array(v)); return v
                list(Rec(XS18, a18).run(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, {}))
                checks["u_decay_equal"].append(dict(layer=i, arm=arm, equal=bool(np.array_equal(np.stack(seen), np.floor((a20 + 2) / 4))),
                                                    max_abs_err_vs_float=float(np.abs(a18 / 2 ** FG - np.exp(-A * np.logaddexp(0.0, ar + dtb))).max())))
        layer_all(i, L, X, pool, sc, "fx", T, "errors-fx.jsonl")
        layer_all(i, L, Y, pool, sc, "fx2", T, "errors-fx.jsonl"); del L
        if i == 1:
            E.save_state(sc / "fx2.npz", Y, {}); Y, _ = E.load_state(sc / "fx2.npz")
    E.save_state(sc / "fx.npz", X, dict(a=1)); X2, m2 = E.load_state(sc / "fx.npz")
    rt = all(np.array_equal(X[p][k], X2[p][k]) for p in X for k in X[p]) and m2 == dict(a=1)
    resume_eq = all(np.array_equal(X[p]["fx"], Y[p]["fx"]) for p in X)
    # synthetic logits: streaming vs dense
    rng = np.random.default_rng(0); d = 64; V = 10007; Tn = 7
    W = rng.normal(size=(V, d)); W[123] = W[45]
    Hn = {p: {"s": rng.normal(size=(Tn, d)) * 0.5} for p in PATHS}
    Hn["XS18"]["s"] = Hn["REF"]["s"] + 1e-3 * rng.normal(size=(Tn, d)); Hn["REF#2"]["s"] = Hn["REF"]["s"].copy()
    res = E.logits_metrics(Hn, ((r0, W[r0:r0 + 1000]) for r0 in range(0, V, 1000)))["s"]
    Zr = Hn["REF"]["s"] @ W.T; lr = Zr - F.lse(Zr)[:, None]; worst = {}
    for p in PATHS[1:]:
        Zp = Hn[p]["s"] @ W.T; lp = Zp - F.lse(Zp)[:, None]; kl = (np.exp(lr) * (lr - lp)).sum(1)
        worst[p] = dict(kl_absdiff=float(np.abs(kl - np.array(res["paths"][p]["kl"])).max()),
                        top1_equal=[int(v) for v in Zp.argmax(1)] == res["paths"][p]["top1_path"])
    pool.close(); pool.join()
    o = dict(fixture_layers=4, paths=PATHS, checks=checks, save_load_equal=rt, resume_equal=resume_eq,
             resid_rel_vs_ref={p: E.rel(X[p]["fx"], X["REF"]["fx"]) for p in X},
             det_equal={p2: bool(np.array_equal(X[p2]["fx"], X[p1]["fx"])) for p2, p1 in DET_PAIRS},
             synthetic=worst, kl_self=max(res["paths"]["REF#2"]["kl"]), seconds=round(time.time() - t0, 1))
    o["all_ok"] = bool(all(c["equal"] for c in checks["control_bit_identical"]) and all(c["equal"] for c in checks["u_decay_equal"])
                       and rt and resume_eq and all(o["det_equal"].values()) and all(w["kl_absdiff"] < 1e-12 and w["top1_equal"] for w in worst.values()))
    Path(out).write_text(json.dumps(o, indent=1) + "\n"); print(json.dumps(o, indent=1))
    sys.exit(0 if o["all_ok"] else 3)

def cmd_fine20(scratch):
    Path(scratch).mkdir(parents=True, exist_ok=True)
    DR.cmd_fine20(str(Path(scratch) / "fine20.npy"))

if __name__ == "__main__":
    c = sys.argv[1]
    if c == "fine20": cmd_fine20(sys.argv[2])
    elif c == "fixture": cmd_fixture(sys.argv[2], sys.argv[3])
    elif c == "run": cmd_run(sys.argv[2], sys.argv[3])
    else: raise SystemExit("usage: see the module docstring")
