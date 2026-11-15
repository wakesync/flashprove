#!/usr/bin/env python3
"""Held-out integer attention with FROZEN calibration scales (PREREG.md, this directory). CPU only, no proof.

The arithmetic is PR #178's `experiments/20261113-176-qwen-int-attn/int_attn.py`, imported unchanged: this file calls its
`arm_prompt` (quant with RNE + clamp, `int_core`), `attn_parts`, `float_o`, `finish`, `rel_heads`, `rel`. What is new here is
only the input path: the per-layer exponents E_q, E_k, E_v and sh are read from PR #178's `runs/layers.jsonl` (hash-pinned)
and never fitted, refitted or adjusted on the evaluation prompts. Entries whose RNE exceeds the clamp are clamped and counted
(with head location), exactly as `int_attn.quant` does.

Usage:
  heldout.py fixture <scratch> <outdir>   debug: "The capital of Italy is" (not in either prompt set), stock layers 0..3
  heldout.py run <scratch> <runs>         registered run on prompts-heldout.json (resumes from <scratch>/ckpt.npz)
"""
import hashlib, json, math, os, shutil, sys, time, types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
SRC176 = EXP / "20261113-176-qwen-int-attn"
sys.path.insert(0, str(SRC176))
import int_attn as IA        # PR #178, unchanged (imports PR #88 q1_forward and PR #124 e2e, unchanged)
F, E = IA.F, IA.E

INT_ATTN_SHA = "357feafac4f3d6a3786d5ab4f484cd1b69eb29a879a72bbfa48cb6bfa248d0a7"
TABLE = SRC176 / "runs" / "layers.jsonl"
TABLE_SHA = "73404d471b069f1944d4a518e7ea8544d4a2c53a17bd3d554ca0f2a677713aee"
ARMS = {"C2047": 2047, "C1665": 1665}
ATT_LAYERS = IA.ATT_LAYERS
NH, NKV, HD = IA.NH, IA.NKV, IA.HD
WIDE = 32767
DISK_FLOOR = 21e9
PROMPTS = HERE / "prompts-heldout.json"

def sha256(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

# ------------------------------------------------------------------ frozen scale table
class TableError(Exception): pass

def load_table(path=TABLE, expect_sha=TABLE_SHA, arms=ARMS, layers=ATT_LAYERS):
    """Return {(arm, layer): read-only {Eq, Ek, Ev, sh}}. Refuses a wrong hash, missing / duplicate / extra keys, wrong clamp."""
    raw = Path(path).read_bytes()
    if expect_sha is not None and hashlib.sha256(raw).hexdigest() != expect_sha: raise TableError("table sha256 mismatch")
    out = {}
    for n, line in enumerate(raw.decode().splitlines()):
        if not line.strip(): continue
        r = json.loads(line); key = (r.get("arm"), r.get("layer"))
        if key[0] not in arms or key[1] not in layers: raise TableError(f"unexpected row {key} (line {n})")
        if key in out: raise TableError(f"duplicate row {key}")
        if r.get("clamp") != arms[key[0]]: raise TableError(f"clamp {r.get('clamp')} != {arms[key[0]]} for {key}")
        vals = {}
        for f in ("Eq", "Ek", "Ev", "sh"):
            v = r.get(f)
            if not isinstance(v, int) or isinstance(v, bool): raise TableError(f"bad {f} in {key}")
            vals[f] = v
        if not (IA.SH_MIN <= vals["sh"] <= IA.SH_MAX): raise TableError(f"sh outside 4..12 in {key}")
        out[key] = types.MappingProxyType(vals)
    want = {(a, l) for a in arms for l in layers}
    if set(out) != want: raise TableError(f"missing rows {sorted(want - set(out))}")
    return types.MappingProxyType(out)

# ------------------------------------------------------------------ evaluator: one arm, one prompt, frozen scales
def head_counts(w, cl):
    """Per head over-clamp counts of a (T, heads, dh) RNE array."""
    return [int(x) for x in (np.abs(w) > cl).sum(axis=(0, 2))]

def eval_frozen(q, k, v, scales, cl):
    """q rotated (T,NH,HD) unscaled, k, v (T,NKV,HD); scales: frozen {Eq,Ek,Ev,sh}. Calls PR #178's arm_prompt unchanged.
    Returns (o_arm or None, o_int or None, stats). A failed arithmetic guard is recorded, never hidden."""
    ex_ = {f: int(scales[f]) for f in ("Eq", "Ek", "Ev", "sh")}       # a copy: nothing downstream can write the table
    _, qw = IA.quant(q / math.sqrt(HD), ex_["Eq"], cl)
    _, kw = IA.quant(k, ex_["Ek"], cl)
    _, vw = IA.quant(v, ex_["Ev"], cl)
    loc = dict(q_over_by_head=head_counts(qw, cl), k_over_by_kvhead=head_counts(kw, cl), v_over_by_kvhead=head_counts(vw, cl))
    obs = dict(obs_mx_q=float(np.abs(q).max()) / math.sqrt(HD), obs_mx_k=float(np.abs(k).max()), obs_mx_v=float(np.abs(v).max()))
    try:
        oa, oi, st = IA.arm_prompt(q, k, v, ex_, cl)
        st["guard_fail"] = []
    except AssertionError as e:
        oa, oi = None, None
        st = dict(q_over=int((np.abs(qw) > cl).sum()), q_n=int(qw.size), k_over=int((np.abs(kw) > cl).sum()), k_n=int(kw.size),
                  v_over=int((np.abs(vw) > cl).sum()), v_n=int(vw.size), q_maxw=int(np.abs(qw).max()), k_maxw=int(np.abs(kw).max()),
                  v_maxw=int(np.abs(vw).max()), wide_over_32767=int((np.abs(qw) > WIDE).sum() + (np.abs(kw) > WIDE).sum() + (np.abs(vw) > WIDE).sum()),
                  max_abs_s=None, e_zero=None, causal=None, guard_fail=[str(e)])
    if st["wide_over_32767"]: st["guard_fail"] = st["guard_fail"] + ["wide value over 32767"]
    st.update(loc); st.update(obs); st["scales_used"] = ex_
    return oa, oi, st

# ------------------------------------------------------------------ logging
def log(path, obj):
    with open(path, "a") as f: f.write(json.dumps(obj) + "\n")

def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def rss_gb():
    """Peak RSS of this process in decimal GB (ru_maxrss is KiB on Linux). PR #178 divided by 1e6; fixed here."""
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 / 1e9

# ------------------------------------------------------------------ one attention layer, both arms, frozen scales
def attention_layer(i, L, X, runs, table, det_prompts):
    t0 = time.time(); parts = {}; ofl = {}; mixf = {}; bit_eq = {}; ref_mix = {}
    for pid, x in X.items():
        q, k, v, gate = IA.attn_parts(L, x); parts[pid] = (q, k, v, gate); ofl[pid] = IA.float_o(q, k, v)
    t_float = time.time() - t0
    for pid, x in X.items():
        ref_mix[pid] = F.attention(L, x)
        mixf[pid] = IA.finish(L, ofl[pid], parts[pid][3])
        bit_eq[pid] = bool(np.array_equal(mixf[pid], ref_mix[pid]))
    t_ref = time.time() - t0 - t_float
    obs = dict(obs_mx_q=max(float(np.abs(p[0]).max()) for p in parts.values()) / math.sqrt(HD),
               obs_mx_k=max(float(np.abs(p[1]).max()) for p in parts.values()),
               obs_mx_v=max(float(np.abs(p[2]).max()) for p in parts.values()))
    for arm, cl in ARMS.items():
        ta = time.time(); sc = table[(arm, i)]; frozen = dict(sc); allrel = []; oint = {}; guards = []; used = []
        tot = dict(q_over=0, q_n=0, k_over=0, k_n=0, v_over=0, v_n=0, e_zero=0, causal=0, wide_over_32767=0)
        mx = dict(q_maxw=0, k_maxw=0, v_maxw=0, max_abs_s=0.0)
        for pid in X:
            q, k, v, gate = parts[pid]
            oa, oi, st = eval_frozen(q, k, v, sc, cl)
            if pid in det_prompts: oint[pid] = oi
            if oa is not None:
                rh = IA.rel_heads(oa, ofl[pid]); mix_rel = IA.rel(IA.finish(L, oa, gate), mixf[pid])
            else:
                rh = [None] * NH; mix_rel = None
            allrel += rh
            for h, r in enumerate(rh): log(runs / "cells.jsonl", dict(arm=arm, layer=i, prompt=pid, head=h, rel_y=r))
            log(runs / "prompt-rows.jsonl", dict(arm=arm, layer=i, prompt=pid, T=int(q.shape[0]), mix_rel=mix_rel, **st))
            guards += [dict(prompt=pid, guard=g) for g in st["guard_fail"]]; used.append(st["scales_used"])
            for kk in tot: tot[kk] += st[kk] or 0
            for kk in mx: mx[kk] = max(mx[kk], st[kk] or 0)
        dets = {}
        for pid in det_prompts:
            if pid in X:
                q, k, v, gate = parts[pid]
                _, oi2, _ = eval_frozen(q, k, v, sc, cl)
                dets[pid] = bool(oi2 is not None and oint[pid] is not None and np.array_equal(oi2, oint[pid]))
        scales_ok = all(u == frozen for u in used) and dict(table[(arm, i)]) == frozen   # PREREG V3
        good = [r for r in allrel if r is not None]
        a = np.array(good) if good else np.array([np.nan])
        clamps = tot["q_over"] + tot["k_over"] + tot["v_over"]
        row = dict(t=now(), arm=arm, layer=i, clamp=cl, Smax=HD * cl * cl, **frozen, **obs, **tot, **mx,
                   n_clamped=clamps, guard_failures=guards, n_pairs=len(allrel), n_cells_valid=len(good),
                   rel_median=float(np.median(a)), rel_max=float(a.max()), rel_min=float(a.min()),
                   n_over_001=int((a > 0.01).sum()), n_over_005=int((a > 0.05).sum()),
                   range_pass=bool(clamps == 0 and not guards),
                   fid_pass=bool(not guards and len(good) == len(allrel) and np.median(a) <= 0.01 and a.max() <= 0.05),
                   det_bit_equal=dets, scales_frozen_ok=scales_ok, arm_seconds=round(time.time() - ta, 1))
        log(runs / "layers.jsonl", row)
        print(arm, "layer", i, "E", frozen, "clamped", clamps, "guards", len(guards), "median", round(row["rel_median"], 5),
              "max", round(row["rel_max"], 5), "R", row["range_pass"], "F", row["fid_pass"], flush=True)
    log(runs / "attn-timing.jsonl", dict(t=now(), layer=i, float_s=round(t_float, 1), ref_attention_s=round(t_ref, 1),
                                          total_s=round(time.time() - t0, 1), mix_bit_equal_q1=bit_eq, peak_rss_gb_self=round(rss_gb(), 3)))
    return ref_mix

# ------------------------------------------------------------------ REF driver (PR #178's forward, without recording x_l)
def forward(X, layers, ckpts, sc, runs, pool, meta, last, table, det_prompts):
    fetch_ex = ThreadPoolExecutor(1)
    todo = [(i, ck) for i, ck in layers if meta["next_layer"] <= i <= last]
    sub = lambda n: fetch_ex.submit(ckpts[todo[n][1]].layer, todo[n][0])
    fut = sub(0) if todo else None
    for n, (i, ck) in enumerate(todo):
        tw = time.time(); L = fut.result(); wait = time.time() - tw
        ckpts[ck].save()
        fut = sub(n + 1) if n + 1 < len(todo) else None
        t0 = time.time()
        if F.layer_type(i) == "linear_attention":
            IA.deltanet_layer(L, X, pool)
        else:
            mix = attention_layer(i, L, X, runs, table, det_prompts)
            if i == last: X = None
            else:
                for pid in X:
                    x = X[pid] + mix[pid]; X[pid] = x + F.mlp(L, x)
        del L
        if X is not None:
            meta.update(next_layer=i + 1); IA.save_state(Path(sc) / "ckpt.npz", X, meta)
        free = shutil.disk_usage(sc).free
        log(runs / "progress.log", dict(t=now(), layer=i, ckpt=ck, type=F.layer_type(i), fetch_wait_s=round(wait, 1),
                                         layer_s=round(time.time() - t0, 1), disk_free_gb=round(free / 1e9, 1), peak_rss_gb_self=round(rss_gb(), 3)))
        print("layer", i, ck, F.layer_type(i), "wait", round(wait, 1), "s", round(time.time() - t0, 1), flush=True)
        if free < DISK_FLOOR:
            log(runs / "progress.log", dict(t=now(), stop="disk floor", disk_free_gb=round(free / 1e9, 1))); raise SystemExit(3)
        if X is None: break
    fetch_ex.shutdown()

def preflight():
    if sha256(SRC176 / "int_attn.py") != INT_ATTN_SHA: raise SystemExit("int_attn.py sha256 mismatch")
    return load_table()

def cmd_run(scratch, runs):
    table = preflight()
    sc = Path(scratch); runs = Path(runs); sc.mkdir(parents=True, exist_ok=True); runs.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(sc).free < DISK_FLOOR: log(runs / "progress.log", dict(t=now(), stop="disk floor at start")); raise SystemExit(3)
    man = json.load(open(PROMPTS)); det = tuple(man["determinism_subset"])
    ckpts = {"stock": F.Ckpt("stock", runs), "abl": F.Ckpt("abl", runs)}
    pool = E.make_pool()
    if (sc / "ckpt.npz").exists():
        X, meta = IA.load_state(sc / "ckpt.npz"); log(runs / "progress.log", dict(t=now(), resume=True, meta=meta))
    else:
        ids = sorted({t for p in man["prompts"] for t in p["token_ids"]})
        emb = ckpts["stock"].emb_rows(ids); ckpts["stock"].save()
        X = {p["id"]: np.stack([emb[t] for t in p["token_ids"]]) for p in man["prompts"]}
        meta = dict(next_layer=0)
        log(runs / "progress.log", dict(t=now(), start=True, prompts={k: int(v.shape[0]) for k, v in X.items()},
                                         split_sha256=man["split_sha256"], table_sha256=TABLE_SHA, int_attn_sha256=INT_ATTN_SHA,
                                         u0=IA.U0, arms=ARMS, det=list(det)))
    layers = [(i, "stock" if i <= 16 else "abl") for i in range(F.NL)]
    forward(X, layers, ckpts, sc, runs, pool, meta, ATT_LAYERS[-1], table, det)
    pool.close(); pool.join()
    log(runs / "progress.log", dict(t=now(), all_done=True, peak_rss_gb_self=round(rss_gb(), 3)))

def cmd_fixture(scratch, out):
    """Debug only (PREREG (e)): fixture tokens, stock layers 0..3 with the frozen layer-3 scales; split bit-equal to q1."""
    table = preflight()
    sc = Path(scratch); out = Path(out); sc.mkdir(parents=True, exist_ok=True); out.mkdir(parents=True, exist_ok=True)
    C = F.Ckpt("stock", out); pool = E.make_pool()
    emb = C.emb_rows(F.FIXTURE); X = {"fx": np.stack([emb[t] for t in F.FIXTURE])}
    forward(X, [(i, "stock") for i in range(4)], {"stock": C}, sc, out, pool, dict(next_layer=0), 3, table, ("fx",))
    pool.close(); pool.join()
    tim = [json.loads(l) for l in open(out / "attn-timing.jsonl")]
    lay = [json.loads(l) for l in open(out / "layers.jsonl")]
    ok = all(all(r["mix_bit_equal_q1"].values()) for r in tim) and all(r["scales_frozen_ok"] and all(r["det_bit_equal"].values()) for r in lay)
    res = dict(ok=bool(ok), note="debug only, fixture not in either prompt set",
               layers=[{k: r[k] for k in ("arm", "layer", "Eq", "Ek", "Ev", "sh", "n_clamped", "rel_median", "rel_max", "det_bit_equal", "scales_frozen_ok")} for r in lay],
               mix_bit_equal=[r["mix_bit_equal_q1"] for r in tim], peak_rss_gb_self=round(rss_gb(), 3))
    (out / "fixture.json").write_text(json.dumps(res, indent=1) + "\n"); print(json.dumps(res), flush=True)
    if not ok: raise SystemExit(4)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run": cmd_run(sys.argv[2], sys.argv[3])
    elif cmd == "fixture": cmd_fixture(sys.argv[2], sys.argv[3])
    else: raise SystemExit(__doc__)
