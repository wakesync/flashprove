#!/usr/bin/env python3
"""Integer emulation of the registered decay table designs T0..T3 (PREREG.md) and their error vs float64.

Inputs: per DeltaNet layer `ar-LXX.npz` written by record.py (ar per prompt (T, 48), A = exp(A_log), dt_bias).
Tables: the pinned v1 softplus table (research/operators/qwen_ops/tables/softplus-f12.i64le, sha256 checked against
its manifest); the coarse exp(-x) table in v1 layout and the fine exp table keyed on g at 2^-12 are generated here
with the pinned integer generator's own functions (`tables.expq`, `tables.nearest`, `tables.logq`, imported unchanged).

Usage:
  decay_tables.py selftest <out.json>                     synthetic checks (no model data)
  decay_tables.py eval <ar_dir> <out_dir> [--fixture]     registered evaluation (or the debug fixture)
"""
import csv, gzip, hashlib, json, math, struct, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "research" / "operators" / "qwen_ops"))
import tables as TB   # PR #67, unchanged

Q = TB.Q
F = 12
ONE = 1 << F
ARMS = ("T0", "T1", "T2", "T3")
E_TOK, E_CUM = 2.0 ** -9, 0.01

# ------------------------------------------------------------------ tables
def softplus_v1():
    data = (TB.HERE / "tables" / "softplus-f12.i64le").read_bytes()
    man = json.load(open(TB.HERE / "tables" / "manifest.json"))
    sha = [t["sha256"] for t in man["tables"] if t["file"] == "softplus-f12.i64le"][0]
    assert hashlib.sha256(data).hexdigest() == sha
    return np.array(struct.unpack("<4096q", data), dtype=np.int64), sha

_exp_cache = {}
def exp_neg_q(num, den):
    """Q256 exp(-num/den) via the pinned generator (TB.expq, floor arithmetic)."""
    k = (num, den)
    if k not in _exp_cache: _exp_cache[k] = TB.expq(-(num * Q // den))
    return _exp_cache[k]

def coarse_exp(f=F):
    """v1 layout: row i at x = (i - 2048)/256, value RNE(2^f exp(-x))."""
    return np.array([TB.nearest(exp_neg_q(i - 2048, 256) * (1 << f), Q) for i in range(4096)], dtype=np.int64)

def fine_exp_lookup(keys, f=F):
    """Fine table keyed on g at 2^-f over [0, 1): row k = RNE(2^f exp(-k / 2^f)). Only the rows used are generated."""
    out = np.empty(keys.shape, dtype=np.int64); u = np.unique(keys)
    m = {int(k): TB.nearest(exp_neg_q(int(k), 1 << f) * (1 << f), Q) for k in u}
    for k, v in m.items(): out[keys == k] = v
    return out

_sp_cache = {}
def softplus_grid(f):
    """softplus at the v1 row grid x = (i - 2048)/256, output at 2^f, generated as tables.generate does."""
    if f not in _sp_cache:
        vals = []
        for i in range(4096):
            x = (i - 2048) * (Q // 256)
            vals.append(TB.nearest(TB.logq(Q + TB.expq(x)) * (1 << f), Q))
        _sp_cache[f] = np.array(vals, dtype=np.int64)
    return _sp_cache[f]

def rne(v): return int(round(v))

def e_A_of(A):
    m = float(np.max(np.abs(A))); e = 0
    while rne(2 ** (e + 1) * m) <= 4095 and e < 24: e += 1
    assert 1 <= e <= 24
    return e

# ------------------------------------------------------------------ arms
def floor_scale(v, f):
    """floor(2^f v) exactly for float64 v (ldexp is exact, floor of a float is exact)."""
    return np.floor(np.ldexp(v, f)).astype(np.int64)

def arm_decay(ar, A, dtb, arm, SP, EXPC, f=F, sp_f=None):
    """ar (T, H) float64, A, dtb (H,). Returns a (T, H) float64 (NaN where rejected), reject mask, and debug ints.
    f: internal scale of x, sp, g, fine key and outputs (12 for the registered arms)."""
    one = 1 << f
    X = floor_scale(ar, f) + np.array([rne(2 ** f * d) for d in dtb], dtype=np.int64)[None, :]
    sh = f - 8                                   # v1 softplus row step 1/256
    key = np.floor_divide(X, 1 << sh) + 2048
    rej = (key < 0) | (key > 4095)
    sp = (SP if sp_f is None else sp_f)[np.clip(key, 0, 4095)]
    if arm == "T3": sp = np.where(X >= 8 * one, X, sp)
    eA = e_A_of(A); cA = np.array([rne(2 ** eA * a) for a in A], dtype=np.int64)
    g = (cA[None, :] * sp) >> eA                # floor (sp >= 0, cA >= 0)
    gk = np.floor_divide(g, 1 << sh) + 2048
    rej |= (gk < 0) | (gk > 4095)
    out = EXPC[np.clip(gk, 0, 4095)]
    if arm in ("T2", "T3"):
        fine = g < one
        if fine.any(): out = np.where(fine, fine_exp_lookup(np.where(fine, g, 0), f), out)
    a = out.astype(np.float64) / one
    if arm == "T0": a = np.where(rej, np.nan, a)
    return a, (rej if arm == "T0" else np.zeros_like(rej)), dict(X=X, key=key, g=g, gk=gk, cA=cA, eA=eA)

def float_decay(ar, A, dtb):
    x = ar + dtb[None, :]; g = A[None, :] * np.logaddexp(0.0, x); return x, g, np.exp(-g)

def cell_metrics(a_arm, a, rej):
    """per head over tokens: e_tok max/median, e_cum max, log-cum max, rejects. a_arm NaN -> rejected."""
    d = np.abs(a_arm - a)
    P = np.cumprod(a, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        Pa = np.cumprod(np.where(np.isnan(a_arm), 0.0, a_arm), axis=0)
        ec = np.abs(Pa - P); el = np.abs(np.log(Pa) - np.log(P))
    nrej = rej.sum(0)
    return dict(e_tok_max=np.nanmax(np.where(np.isnan(d), -np.inf, d), axis=0), e_tok_med=np.nanmedian(d, axis=0) if not np.isnan(d).all() else np.full(d.shape[1], np.nan),
                e_cum_max=ec.max(0), e_logcum_max=np.where(np.isfinite(el), el, np.inf).max(0), rejects=nrej)

# ------------------------------------------------------------------ descriptive split (T3 semantics)
def split_sources(ar, A, dtb, SP, EXPC):
    x, g, a = float_decay(ar, A, dtb)
    one = ONE; out = {}
    eA = e_A_of(A); cA = np.array([rne(2 ** eA * v) for v in A], dtype=np.float64) / 2 ** eA
    out["cA_rounding"] = np.exp(-cA[None, :] * np.logaddexp(0.0, x))
    X = floor_scale(ar, F) + np.array([rne(2 ** F * d) for d in dtb], dtype=np.int64)[None, :]
    key = np.clip(np.floor_divide(X, 16) + 2048, 0, 4095)
    sp = np.where(X >= 8 * one, X, SP[key]).astype(np.float64) / one
    out["softplus_table"] = np.exp(-A[None, :] * sp)
    gi = np.floor(np.ldexp(g, F)).astype(np.int64)
    gk = np.clip(np.floor_divide(gi, 16) + 2048, 0, 4095)
    v = EXPC[gk].copy(); fine = gi < one
    if fine.any(): v = np.where(fine, fine_exp_lookup(np.where(fine, gi, 0)), v)
    out["g_key_and_exp_table"] = v.astype(np.float64) / one
    out["output_rounding"] = np.rint(np.ldexp(a, F)) / one
    return out

# ------------------------------------------------------------------ driver
def load_layers(ar_dir):
    out = []
    for p in sorted(Path(ar_dir).glob("ar-L*.npz")):
        d = np.load(p); i = int(p.stem.split("L")[1])
        out.append((i, d["A"], d["dt_bias"], {k.split("|", 1)[1]: d[k] for k in d.files if k.startswith("ar|")}))
    return out

def q(v): return [float(np.min(v)), float(np.median(v)), float(np.max(v))]

def cmd_eval(ar_dir, out_dir, fixture=False):
    t0 = time.time(); od = Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    SP, sp_sha = softplus_v1(); EXPC = coarse_exp()
    layers = load_layers(ar_dir)
    cells = []; dom = []; split = []; sweep = []
    sweep_tabs = {f: (softplus_grid(f), coarse_exp(f)) for f in (14, 16, 18)}
    for i, A, dtb, ars in layers:
        eA = e_A_of(A)
        allx = np.concatenate([ars[p] + dtb[None, :] for p in ars]); allg = A[None, :] * np.logaddexp(0.0, allx)
        n = allx.shape[0]
        for h in range(len(A)):
            xs, gs = allx[:, h], allg[:, h]
            dom.append(dict(layer=i, head=h, n=n, A=float(A[h]), dt_bias=float(dtb[h]), e_A=eA, cA=rne(2 ** eA * A[h]),
                            share_x_lt_m8=float((xs < -8).mean()), share_x_ge_8=float((xs >= 8).mean()),
                            count_x_out=int(((xs < -8) | (xs >= 8)).sum()), share_g_lt_step=float((gs < 1 / 256).mean()),
                            count_g_lt_step=int((gs < 1 / 256).sum()), share_g_ge_8=float((gs >= 8).mean()),
                            x_min_med_max=q(xs), g_min_med_max=q(gs), a_min_med_max=q(np.exp(-gs))))
        for pid, ar in ars.items():
            x, g, a = float_decay(ar, A, dtb)
            for arm in ARMS:
                aa, rej, _ = arm_decay(ar, A, dtb, arm, SP, EXPC)
                m = cell_metrics(aa, a, rej)
                for h in range(len(A)):
                    cells.append(dict(arm=arm, layer=i, head=h, prompt=pid, T=ar.shape[0], rejects=int(m["rejects"][h]),
                                      e_tok_max=float(m["e_tok_max"][h]), e_tok_med=float(m["e_tok_med"][h]),
                                      e_cum_max=float(m["e_cum_max"][h]), e_logcum_max=float(m["e_logcum_max"][h])))
            for src, aa in split_sources(ar, A, dtb, SP, EXPC).items():
                m = cell_metrics(aa, a, np.zeros(aa.shape, bool))
                for h in range(len(A)):
                    split.append(dict(source=src, layer=i, head=h, prompt=pid, e_tok_max=float(m["e_tok_max"][h]), e_cum_max=float(m["e_cum_max"][h])))
            for f, (spf, expf) in sweep_tabs.items():
                aa, rej, _ = arm_decay(ar, A, dtb, "T3", None, expf, f=f, sp_f=spf)
                m = cell_metrics(aa, a, rej)
                for h in range(len(A)):
                    sweep.append(dict(F=f, layer=i, head=h, prompt=pid, e_tok_max=float(m["e_tok_max"][h]), e_cum_max=float(m["e_cum_max"][h])))
        print("layer", i, "done", round(time.time() - t0, 1), flush=True)
    def wcsv(name, rows):
        with gzip.open(od / name, "wt", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    wcsv("cells.csv.gz", cells); wcsv("split-T3.csv.gz", split); wcsv("sweep-T3-F.csv.gz", sweep)
    with gzip.open(od / "domain.json.gz", "wt") as fh: json.dump(dom, fh)
    meta = dict(softplus_table_sha256=sp_sha, coarse_exp_sha256=hashlib.sha256(struct.pack("<4096q", *[int(v) for v in EXPC])).hexdigest(),
                layers=[i for i, *_ in layers], prompts=sorted(layers[0][3]) if layers else [], fixture=fixture,
                seconds=round(time.time() - t0, 1), bar=dict(e_tok=E_TOK, e_cum=E_CUM, rejects=0))
    (od / "eval-meta.json").write_text(json.dumps(meta, indent=1) + "\n"); print(json.dumps(meta))

def cmd_selftest(out):
    SP, sha = softplus_v1(); EXPC = coarse_exp(); r = {}
    # v1 coarse exp rows match float exp to 1 unit at 2^12
    xs = (np.arange(4096) - 2048) / 256.0; ref = np.rint(np.exp(-xs[2048:]) * ONE)
    r["coarse_exp_rows_ge0_maxdiff_units"] = float(np.abs(EXPC[2048:] - ref).max())
    r["softplus_rows_vs_float_maxdiff_units"] = float(np.abs(SP - np.rint(np.logaddexp(0, xs) * ONE)).max())
    # fine table rows
    k = np.array([0, 1, 7, 100, 4095]); r["fine_rows"] = dict(zip(map(int, k), map(int, fine_exp_lookup(k))))
    r["fine_rows_vs_float"] = [int(v) for v in np.rint(np.exp(-k / ONE) * ONE)]
    # synthetic heads: x in-domain, out-of-domain (both sides), slow and fast decays
    rng = np.random.default_rng(1)
    A = np.array([0.004, 0.03, 0.34, 0.1]); dtb = np.array([19.25, -1.8, -5.7, 3.0])
    ar = rng.normal(0, 3, size=(50, 4)); ar[0, 2] = -20.0
    x, g, a = float_decay(ar, A, dtb)
    for arm in ARMS:
        aa, rej, dbg = arm_decay(ar, A, dtb, arm, SP, EXPC)
        m = cell_metrics(aa, a, rej)
        r[arm] = dict(rejects=m["rejects"].tolist(), e_tok_max=[float(v) for v in m["e_tok_max"]], e_cum_max=[float(v) for v in m["e_cum_max"]], eA=dbg["eA"], cA=dbg["cA"].tolist())
    # T0 must reject head 0 (x around 19) and head 2 token 0 (x = -25.7); T1 must not reject
    r["T0_rejects_head0_all"] = bool(r["T0"]["rejects"][0] > 40); r["T0_rejects_head2"] = bool(r["T0"]["rejects"][2] >= 1)
    r["T1_no_reject"] = sum(r["T1"]["rejects"]) == 0
    # floor_scale exactness and the integer key convention on negatives
    r["floor_neg"] = int(floor_scale(np.array([-1e-9]), 12)[0]) == -1 and int(np.floor_divide(-1, 16)) == -1
    # sweep tables: F = 14 softplus grid equals the pinned F = 14 table
    d14 = (TB.HERE / "tables" / "softplus-f14.i64le").read_bytes()
    r["softplus_f14_regen_equal_pinned"] = bool(np.array_equal(softplus_grid(14), np.array(struct.unpack("<4096q", d14))))
    Path(out).write_text(json.dumps(r, indent=1) + "\n"); print(json.dumps(r, indent=1))

if __name__ == "__main__":
    if sys.argv[1] == "selftest": cmd_selftest(sys.argv[2])
    else: cmd_eval(sys.argv[2], sys.argv[3], "--fixture" in sys.argv)
