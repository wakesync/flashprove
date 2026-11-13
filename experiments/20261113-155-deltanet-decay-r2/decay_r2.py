#!/usr/bin/env python3
"""Integer emulation of the registered round-2 decay arms U1..U4 (PREREG.md) and their error vs float64.

Builds on PR #146 (`../20261112-136-deltanet-decay/`), imported unchanged: `decay_tables.float_decay` (the float64
reference), `decay_tables.cell_metrics` (the metric), `decay_tables.load_layers` + `suite.py` (the registered suite
and its completeness checks), `decay_tables.softplus_v1`, `coarse_exp`, `softplus_grid`, `fine_exp_lookup`, and the
pinned integer table generator `research/operators/qwen_ops/tables.py`.

Usage:
  decay_r2.py fine20 <out.npy>                       the 2^20-row fine exp table, integer generator, all rows
  decay_r2.py eval <ar_dir> <out_dir> <fine20.npy> [--fixture]
                                                     registered evaluation of U1..U4 (or the debug fixture)
  decay_r2.py split <ar_dir> <out_dir> <fine20.npy> <arm> [--fixture]
                                                     descriptive error split by source for one arm

`eval` and `split` on the registered suite refuse (exit 2, nothing written) unless every input file's sha256 is the
one listed in PREREG.md "Runs" and `runs/provenance.json` records that PR #146's own evaluation of the same files
reproduced PR #146's committed output (provenance.py). Nothing here is proved; these are emulations of table
semantics.
"""
import csv, gzip, hashlib, io, json, re, struct, sys, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
P146 = HERE.parent / "20261112-136-deltanet-decay"
sys.path.insert(0, str(P146))
import decay_tables as DT   # PR #146, unchanged
import suite as SU          # PR #146, unchanged

TB = DT.TB
Q = TB.Q
ARMS = ("U1", "U2", "U3", "U4")
G = 20                      # PREREG "Internal scale rule"
ONE12, ONE20 = 1 << 12, 1 << G
SPW_LO, SPW_ROWS = -4096, 6144          # U3 softplus table: rows at x = (j - 4096)/256, [-16, 8)
U4_LO, U4_ROWS = -4096, 12288           # U4 per-head table: rows at x in [-16, 32)
E_TOK, E_CUM = DT.E_TOK, DT.E_CUM
SPLIT_SOURCES = dict(U1=("cA_rounding", "softplus_table", "g_floor_and_exp_tables", "output_rounding"),
                     U2=("cA_rounding", "softplus_table", "g_floor_and_exp_tables", "output_rounding"),
                     U3=("cA_rounding", "softplus_table", "g_floor_and_exp_tables", "output_rounding"),
                     U4=("row_step", "output_rounding"))


# ------------------------------------------------------------------ registered input list
def prereg_sha():
    """{file name: sha256} from the fenced list in PREREG.md "Runs"."""
    txt = (HERE / "PREREG.md").read_text()
    m = dict((n, h) for h, n in re.findall(r"^([0-9a-f]{64})  (ar-L\d\d\.npz)$", txt, flags=re.M))
    SU.need(len(m) == len(SU.DELTANET_LAYERS), f"PREREG.md lists {len(m)} input files, expected {len(SU.DELTANET_LAYERS)}")
    SU.need(sorted(m) == [f"ar-L{i:02d}.npz" for i in SU.DELTANET_LAYERS], "PREREG.md input list is not the 48 DeltaNet layer files")
    return m


def check_inputs(ar_dir):
    """Every registered file present with the registered sha256, and no other ar-L file. Returns the list digest."""
    want = prereg_sha()
    have = sorted(p.name for p in Path(ar_dir).glob("ar-L*.npz"))
    SU.need(have == sorted(want), f"input files {len(have)} are not the registered {len(want)}")
    for n in have:
        h = hashlib.sha256((Path(ar_dir) / n).read_bytes()).hexdigest()
        SU.need(h == want[n], f"{n}: sha256 {h} is not the registered {want[n]}")
    return hashlib.sha256("".join(f"{want[n]}  {n}\n" for n in sorted(want)).encode()).hexdigest()


def check_provenance():
    p = HERE / "runs" / "provenance.json"
    SU.need(p.exists(), "runs/provenance.json missing: run provenance.py first (PREREG 'Kill criterion', input rule)")
    j = json.loads(p.read_text())
    SU.need(j.get("ok") is True and j.get("sha256_all_equal") is True and j.get("cells_equal") is True and j.get("domain_equal") is True,
            "runs/provenance.json does not record a passed input check")
    return j


# ------------------------------------------------------------------ tables
def softplus_rows(lo_row, n, f):
    """RNE(2^f softplus((j + lo_row)/256)), j = 0..n-1, with the pinned integer generator (as tables.generate)."""
    return np.array([TB.nearest(TB.logq(Q + TB.expq((j + lo_row) * (Q // 256))) * (1 << f), Q) for j in range(n)], dtype=np.int64)


def fine_row(k, f=G):
    """RNE(2^f exp(-k / 2^f)) with the pinned integer generator (same expression as PR #146's exp_neg_q, no cache)."""
    return TB.nearest(TB.expq(-(k * Q // (1 << f))) * (1 << f), Q)


def _fine_chunk(a):
    return [fine_row(k) for k in range(a[0], a[1])]


def cmd_fine20(out, procs=6):
    import multiprocessing as mp
    t0 = time.time(); step = 4096
    chunks = [(a, min(a + step, ONE20)) for a in range(0, ONE20, step)]
    with mp.Pool(procs) as pool: parts = pool.map(_fine_chunk, chunks)
    tab = np.array([v for p in parts for v in p], dtype=np.int64)
    assert tab.shape == (ONE20,) and tab[0] == ONE20
    np.save(out, tab)
    fl = np.rint(np.ldexp(np.exp(-np.arange(ONE20) / ONE20), G)).astype(np.int64)
    print(json.dumps(dict(rows=int(tab.shape[0]), sha256=table_sha(tab), seconds=round(time.time() - t0, 1),
                          rows_differing_from_float64_rne=int((tab != fl).sum()), min=int(tab.min()), max=int(tab.max()))))


def table_sha(t):
    return hashlib.sha256(np.ascontiguousarray(t, dtype="<i8").tobytes()).hexdigest()


def load_tables(fine20_path):
    SP12, sp12_sha = DT.softplus_v1()
    T = dict(SP12=SP12, EXPC12=DT.coarse_exp(12), SP20=DT.softplus_grid(G), EXPC20=DT.coarse_exp(G),
             SP20W=softplus_rows(SPW_LO, SPW_ROWS, G), FINE20=np.load(fine20_path))
    assert T["FINE20"].shape == (ONE20,) and T["FINE20"].dtype == np.int64
    assert np.array_equal(T["SP20W"][-SPW_LO - 2048:], T["SP20"]), "widened softplus table must equal the v1-grid table on [-8, 8)"
    T["sha"] = dict(softplus_f12_v1=sp12_sha, coarse_exp_f12=table_sha(T["EXPC12"]), softplus_f20=table_sha(T["SP20"]),
                    coarse_exp_f20=table_sha(T["EXPC20"]), softplus_f20_wide=table_sha(T["SP20W"]), fine_exp_f20=table_sha(T["FINE20"]))
    return T


# ------------------------------------------------------------------ arms
def e_head(a):
    """PREREG per-head exponent rule: the largest e in 1..24 with RNE(2^e A_h) <= 4,095."""
    best = None
    for e in range(1, 25):
        if DT.rne(2 ** e * float(a)) <= 4095: best = e
    assert best is not None, "A too large for a 12-bit cA at e >= 1"
    return best


def head_consts(A, per_head=True):
    if per_head: e = np.array([e_head(a) for a in A], dtype=np.int64)
    else: e = np.full(len(A), DT.e_A_of(A), dtype=np.int64)       # T3's per-layer rule, for the equivalence test only
    cA = np.array([DT.rne(2 ** int(k) * float(a)) for k, a in zip(e, A)], dtype=np.int64)
    return e, cA


def front(ar, dtb):
    X = DT.floor_scale(ar, 12) + np.array([DT.rne(2 ** 12 * d) for d in dtb], dtype=np.int64)[None, :]
    return X, np.floor_divide(X, 16)


def u4_table(A):
    """D_h[j] = RNE(2^20 exp(-A_h softplus((j - 4096 + 1/2)/256))), float64, shape (12288, H)."""
    mid = (np.arange(U4_ROWS) + U4_LO + 0.5) / 256.0
    return np.rint(np.ldexp(np.exp(-A[None, :] * np.logaddexp(0.0, mid)[:, None]), G)).astype(np.int64)


def softplus_int(X, r, arm, T):
    if arm == "U1": return np.where(X >= 8 * ONE12, X, T["SP12"][np.clip(r + 2048, 0, 4095)])
    if arm == "U2": return np.where(X >= 8 * ONE12, X << (G - 12), T["SP20"][np.clip(r + 2048, 0, 4095)])
    if arm == "U3": return np.where(X >= 8 * ONE12, X << (G - 12), T["SP20W"][np.clip(r - SPW_LO, 0, SPW_ROWS - 1)])
    raise ValueError(arm)


def exp_int(g, arm, T):
    """g >= 0 integer at the arm's scale -> a_int at the same scale (fine table below 1, coarse v1-layout rows above)."""
    if arm == "U1":
        fine = g < ONE12
        out = T["EXPC12"][np.clip((g >> 4) + 2048, 0, 4095)]
        if fine.any(): out = np.where(fine, DT.fine_exp_lookup(np.where(fine, g, 0), 12), out)
        return out
    fine = g < ONE20
    return np.where(fine, T["FINE20"][np.where(fine, g, 0)], T["EXPC20"][np.clip((g >> 12) + 2048, 0, 4095)])


def arm_decay(ar, A, dtb, arm, T, per_head=True):
    """ar (T, H) float64, A, dtb (H,). Returns a (T, H) float64 (NaN where rejected) and the reject mask."""
    X, r = front(ar, dtb)
    if arm == "U4":
        j = r - U4_LO
        rej = j > U4_ROWS - 1
        a = np.take_along_axis(u4_table(A), np.clip(j, 0, U4_ROWS - 1), axis=0).astype(np.float64) / ONE20
        return np.where(rej, np.nan, a), rej
    e, cA = head_consts(A, per_head)
    sp = softplus_int(X, r, arm, T)
    g = (cA[None, :] * sp) >> e[None, :]          # floor (cA > 0, sp >= 0)
    one = ONE12 if arm == "U1" else ONE20
    return exp_int(g, arm, T).astype(np.float64) / one, np.zeros(X.shape, bool)


def split_sources(ar, A, dtb, arm, T):
    """Each source alone, everything else float64 (descriptive, as PR #146 section 4)."""
    x, g, a = DT.float_decay(ar, A, dtb); X, r = front(ar, dtb); out = {}
    if arm == "U4":
        mid = (np.clip(r, U4_LO, U4_LO + U4_ROWS - 1) + 0.5) / 256.0
        out["row_step"] = np.exp(-A[None, :] * np.logaddexp(0.0, mid))
        out["output_rounding"] = np.rint(np.ldexp(a, G)) / ONE20
        return out
    f = 12 if arm == "U1" else G; one = 1 << f
    e, cA = head_consts(A)
    out["cA_rounding"] = np.exp(-(cA / 2.0 ** e)[None, :] * np.logaddexp(0.0, x))
    out["softplus_table"] = np.exp(-A[None, :] * (softplus_int(X, r, arm, T).astype(np.float64) / one))
    gi = np.floor(np.ldexp(g, f)).astype(np.int64)
    out["g_floor_and_exp_tables"] = exp_int(gi, arm, T).astype(np.float64) / one
    out["output_rounding"] = np.rint(np.ldexp(a, f)) / one
    return out


# ------------------------------------------------------------------ driver
def wcsv(path, rows):
    buf = io.StringIO(newline=""); w = csv.DictWriter(buf, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz: gz.write(buf.getvalue().encode())


def wjsongz(path, obj):
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz: gz.write(json.dumps(obj).encode())


def _open(ar_dir, fixture):
    mode = dict(fixture=fixture, set="S10", partial_layers=None)
    layers = DT.load_layers(ar_dir, mode)          # PR #146: refuses anything but the full registered suite
    prov = None; digest = None
    if not fixture:
        digest = check_inputs(ar_dir); prov = check_provenance()
        SU.need(prov.get("input_list_sha256") == digest, "runs/provenance.json was made for a different input list")
    return layers, digest


def cmd_eval(ar_dir, out_dir, fine20, fixture=False):
    layers, digest = _open(ar_dir, fixture)
    t0 = time.time(); T = load_tables(fine20); od = Path(out_dir); od.mkdir(parents=True, exist_ok=True)
    cells = []; heads = []
    for i, A, dtb, ars in layers:
        e, cA = head_consts(A)
        for h in range(len(A)): heads.append(dict(layer=i, head=h, A=float(A[h]), dt_bias=float(dtb[h]), e_h=int(e[h]), cA_h=int(cA[h])))
        for pid in sorted(ars):
            ar = ars[pid]; x, g, a = DT.float_decay(ar, A, dtb)
            for arm in ARMS:
                aa, rej = arm_decay(ar, A, dtb, arm, T)
                m = DT.cell_metrics(aa, a, rej)
                for h in range(len(A)):
                    cells.append(dict(arm=arm, layer=i, head=h, prompt=pid, T=ar.shape[0], rejects=int(m["rejects"][h]),
                                      e_tok_max=float(m["e_tok_max"][h]), e_tok_med=float(m["e_tok_med"][h]),
                                      e_cum_max=float(m["e_cum_max"][h]), e_logcum_max=float(m["e_logcum_max"][h])))
        print("layer", i, "done", round(time.time() - t0, 1), flush=True)
    wcsv(od / "cells.csv.gz", cells); wjsongz(od / "heads.json.gz", heads)
    meta = dict(arms=list(ARMS), G=G, layers=[i for i, *_ in layers], prompts=sorted(layers[0][3]), fixture=bool(fixture),
                set=None if fixture else "S10", input_list_sha256=digest, tables_sha256=T["sha"],
                softplus_wide=dict(rows=SPW_ROWS, lo_row=SPW_LO), u4=dict(rows_per_head=U4_ROWS, lo_row=U4_LO),
                bar=dict(e_tok=E_TOK, e_cum=E_CUM, rejects=0), seconds=round(time.time() - t0, 1))
    (od / "eval-meta.json").write_text(json.dumps(meta, indent=1) + "\n"); print(json.dumps(meta))


def cmd_split(ar_dir, out_dir, fine20, arm, fixture=False):
    SU.need(arm in ARMS, f"unknown arm {arm!r}")
    layers, digest = _open(ar_dir, fixture)
    T = load_tables(fine20); od = Path(out_dir); od.mkdir(parents=True, exist_ok=True); rows = []
    for i, A, dtb, ars in layers:
        for pid in sorted(ars):
            ar = ars[pid]; x, g, a = DT.float_decay(ar, A, dtb)
            for src, aa in split_sources(ar, A, dtb, arm, T).items():
                m = DT.cell_metrics(aa, a, np.zeros(aa.shape, bool))
                for h in range(len(A)):
                    rows.append(dict(source=src, layer=i, head=h, prompt=pid, e_tok_max=float(m["e_tok_max"][h]), e_cum_max=float(m["e_cum_max"][h])))
    wcsv(od / f"split-{arm}.csv.gz", rows); print("split", arm, len(rows), "rows")


if __name__ == "__main__":
    try:
        c = sys.argv[1]; fx = "--fixture" in sys.argv; a = [v for v in sys.argv[2:] if v != "--fixture"]
        if c == "fine20": cmd_fine20(a[0])
        elif c == "eval": cmd_eval(a[0], a[1], a[2], fx)
        elif c == "split": cmd_split(a[0], a[1], a[2], a[3], fx)
        else: raise SystemExit("usage: see the module docstring")
    except SU.Incomplete as e:
        print("decay_r2.py: REFUSED: " + str(e), file=sys.stderr); sys.exit(2)
