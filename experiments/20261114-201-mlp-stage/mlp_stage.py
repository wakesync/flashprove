#!/usr/bin/env python3
"""MLP stage attribution, abliterated layers 31..63 (PREREG.md, issue #201). No proof, no soundness claim.

Paths, all from the REF residual entering layer 31 (PR #167's hashed layer-30 state), float64 DeltaNet heads, in_proj,
out_proj, attention, every RMSNorm (incl. the MLP pre-norm), final norm and lm_head:
  REF     float64 MLP (PR #88 q1_forward.mlp, unchanged)
  M31     PR #138's mlp_int (experiments/20261112-132-int-mlp-e2e/mlp_e2e.py, imported unchanged), 13-bit weights
  M31-S   as M31, s = RNE(2^12 silu(gw / 2^12)) in float64 (no table step, no index clip); every other line identical
  M31-W   as M31, gate/up/down with the float64 weights: acc = m . (2^e W_float), same exponent e, same floors, same table
  M31#2   M31 again on p01 and p09 (determinism)
Reused unchanged: PR #124 e2e.py (logits_metrics, lm_head_chunks, load_state, log, rel, make_pool), PR #88 q1_forward.py
(Ckpt, rms0, deltanet_inputs, head_out, attention, mlp, layer_type), PR #138 mlp_e2e.py (mlp_int, exponent, to_int_inplace,
exact_matmul, GuardError, TS, constants).

Usage:
  mlp_stage.py run <start state npz> <runs dir> <grant unix> [hard stop iso]
  mlp_stage.py fixture <scratch> <out json>        debug only: PR #88's fixture prompt, stock layers 0 and 3, stock lm_head
"""
import calendar, hashlib, json, math, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "20261112-132-int-mlp-e2e"))
import mlp_e2e as M      # PR #138, unchanged (imports PR #124 e2e and PR #88 q1_forward)
E, F = M.E, M.F

FB = M.FB
TS = M.TS
PATHS = ["REF", "M31", "M31-S", "M31-W", "M31#2"]
INT_TABLE = ("M31", "M31#2")
DET = ["p01-ordinary-short", "p09-multilingual"]
SIX = ["p01-ordinary-short", "p07-chat-ordinary", "p08-chat-refusal", "p09-multilingual", "p04-repeat-punct", "p03-repeat-word"]
START_SHA = "22dff8b92107511838e50e4b26d6e91a2b55d09064711c638042c4c18fb80009"
CAP_S = 100 * 60
N_LIN, N_FULL, LOGITS_S = 24, 9, 150
W_NAMES = (("g", "gate"), ("u", "up"), ("d", "down"))
now = lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def head_task(path, pid, hd):
    return path, pid, F.head_out(hd, "REF")


def amax(x):
    return float(np.abs(x).max(initial=0.0))


def stats(m, gw, u, s, h, accd, out, lo, hi):
    """The same keys and counters as mlp_int's range row (PR #138)."""
    return dict(m=amax(m), gw=amax(gw), u=amax(u), s=amax(s), h=amax(h), acc_down=amax(accd), out=amax(out),
                n_m_over_2047=int((np.abs(m) > M.A_PUB).sum()),
                n_gw_ge_2e18=int((np.abs(gw) >= M.HONEST).sum()), n_gw_ge_2e23=int((np.abs(gw) >= M.RNG).sum()),
                n_u_ge_2e18=int((np.abs(u) >= M.HONEST).sum()), n_u_ge_2e23=int((np.abs(u) >= M.RNG).sum()),
                n_h_ge_2e18=int((np.abs(h) >= M.HONEST).sum()), n_h_ge_2e23=int((np.abs(h) >= M.RNG).sum()),
                n_silu_sat_lo=lo, n_silu_sat_hi=hi,
                n_acc_down_ge_ledger=int((np.abs(accd) >= M.DOWN_LEDGER).sum()), n_out_ge_2e31=int((np.abs(out) >= M.OUT_PUB).sum()),
                n_m=int(m.size), n_hidden=int(gw.size), n_out=int(out.size))


def silu_exact(gw):
    """s = RNE(2^12 silu(gw / 2^12)), float64, numpy rint (ties to even). No table, no clip."""
    g = gw / 2.0 ** FB
    return np.rint(2.0 ** FB * (g / (1.0 + np.exp(-g))))


def mlp_int_S(L, x, ex):
    """M31-S: mlp_int with the table lookup replaced by silu_exact. Domain exits are counted, not saturated."""
    hf = F.rms0(x, L["post_attention_layernorm.weight"])
    m = np.rint(hf * 2.0 ** FB)
    accg = M.exact_matmul(m, L["mlp.gate_proj.weight"], "gate"); gw = np.floor(accg / 2.0 ** ex["g"])
    accu = M.exact_matmul(m, L["mlp.up_proj.weight"], "up"); u = np.floor(accu / 2.0 ** ex["u"])
    raw = np.floor(gw / 2.0 ** (FB - 8)) + 2048
    lo = int((raw < 0).sum()); hi = int((raw > 4095).sum())
    s = silu_exact(gw)
    if amax(s) * amax(u) >= M.EXACT:
        raise M.GuardError(f"s*u: {amax(s) * amax(u):.3e} >= 2^53")
    h = np.floor(s * u / 2.0 ** FB)
    accd = M.exact_matmul(h, L["mlp.down_proj.weight"], "down"); out = np.floor(accd / 2.0 ** ex["d"])
    return out / 2.0 ** FB, stats(m, gw, u, s, h, accd, out, lo, hi)


def mlp_W(L, x, ex):
    """M31-W: L holds the float64 weights. acc = m . (2^e W_float) (scaling by 2^e is exact), same floors and table."""
    hf = F.rms0(x, L["post_attention_layernorm.weight"])
    m = np.rint(hf * 2.0 ** FB)
    accg = (m @ L["mlp.gate_proj.weight"].T) * 2.0 ** ex["g"]; gw = np.floor(accg / 2.0 ** ex["g"])
    accu = (m @ L["mlp.up_proj.weight"].T) * 2.0 ** ex["u"]; u = np.floor(accu / 2.0 ** ex["u"])
    raw = np.floor(gw / 2.0 ** (FB - 8)) + 2048
    lo = int((raw < 0).sum()); hi = int((raw > 4095).sum())
    s = TS[np.clip(raw, 0, 4095).astype(np.int64)]
    h = np.floor(s * u / 2.0 ** FB)                            # no 2^53 guard on this path (PREREG); magnitudes logged
    accd = (h @ L["mlp.down_proj.weight"].T) * 2.0 ** ex["d"]; out = np.floor(accd / 2.0 ** ex["d"])
    st = stats(m, gw, u, s, h, accd, out, lo, hi); st["acc_g"] = amax(accg); st["acc_u"] = amax(accu)
    return out / 2.0 ** FB, st


def layer_all(i, L, X, pool, runs, leg):
    t0 = time.time(); errname = f"errors-{leg}.jsonl"
    if F.layer_type(i) == "linear_attention":
        pend = []
        for p in PATHS:
            for pid, x in X.get(p, {}).items():
                if x is None: continue
                pend.append(pool.apply_async(head_task, (p, pid, F.deltanet_inputs(L, x))))
        Wo = L["linear_attn.out_proj.weight"]
        for r in pend:
            p, pid, y = r.get()
            X[p][pid] = X[p][pid] + y.reshape(y.shape[0], -1) @ Wo.T
    else:
        for p in PATHS:
            for pid, x in X.get(p, {}).items():
                if x is None: continue
                X[p][pid] = x + F.attention(L, x)
    tmix = time.time() - t0
    for pid, x in X["REF"].items():
        if x is not None: X["REF"][pid] = x + F.mlp(L, x)
    ex = {k: M.exponent(float(np.abs(L[f"mlp.{n}_proj.weight"]).max())) for k, n in W_NAMES}
    rng_row = dict(leg=leg, layer=i, paths={})

    def run_path(p, fn):
        if p not in X: return
        rng_row["paths"][p] = {}
        for pid, x in X[p].items():
            if x is None: continue
            try:
                d, st = fn(L, x, ex)
            except M.GuardError as e:
                log(runs, errname, dict(leg=leg, layer=i, path=p, prompt=pid, error="GuardError: " + str(e))); X[p][pid] = None; continue
            X[p][pid] = x + d; rng_row["paths"][p][pid] = st

    run_path("M31-W", mlp_W)                                   # float weights, before the in-place conversion
    conv = {k: M.to_int_inplace(L[f"mlp.{n}_proj.weight"]) for k, n in W_NAMES}
    assert all(conv[k]["e"] == ex[k] for k in ex), (conv, ex)
    rng_row["weights"] = conv
    for p in INT_TABLE: run_path(p, M.mlp_int)
    run_path("M31-S", mlp_int_S)
    log(runs, f"ranges-{leg}.jsonl", rng_row)
    row = dict(leg=leg, layer=i, type=F.layer_type(i), seconds=round(time.time() - t0, 1), mix_s=round(tmix, 1))
    for p in PATHS:
        if p == "REF" or p not in X: continue
        row[p] = {pid: (rel(x, X["REF"][pid]) if x is not None and X["REF"][pid] is not None else None) for pid, x in X[p].items()}
    row["det_bit_equal"] = {f"M31#2|{pid}": bool(x is not None and X["M31"].get(pid) is not None and np.array_equal(x, X["M31"][pid]))
                            for pid, x in X.get("M31#2", {}).items()}
    log(runs, f"divergence-{leg}.jsonl", row)
    return row


log, rel = E.log, E.rel


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def plog(runs, line):
    with open(Path(runs) / "progress.log", "a") as f: f.write(f"{now()} {line}\n")


def finish(X, C, runs, leg, sanity_tok):
    t0 = time.time(); Ln = C.t(F.P + "norm.weight")
    Hn = {p: {pid: (F.rms0(x, Ln) if x is not None else None) for pid, x in d.items()} for p, d in X.items()}
    res = E.logits_metrics(Hn, E.lm_head_chunks(C)); C.save()
    out = dict(leg=leg, checkpoint=C.which, paths=PATHS, prompts=res, seconds=round(time.time() - t0, 1))
    if sanity_tok is not None:
        p01 = res.get("p01-ordinary-short")
        out.update(sanity_p01_last_top1=p01["ref_top1"][-1], sanity_pass=p01["ref_top1"][-1] == sanity_tok)
    (Path(runs) / f"e2e-{leg}.json").write_text(json.dumps(out) + "\n")
    log(runs, "progress.log.jsonl", dict(t=now(), leg=leg, logits_done=True, seconds=out["seconds"], sanity_pass=out.get("sanity_pass")))
    return out


def cmd_run(state, runs, grant, hard_txt):
    E.PATH_ORDER = PATHS                       # logits_metrics reads it (main process only)
    runs = Path(runs); runs.mkdir(parents=True, exist_ok=True)
    hard = calendar.timegm(time.strptime(hard_txt, "%Y-%m-%dT%H:%M:%SZ"))
    h = sha256(state)
    plog(runs, f"start-state sha256 {h} expected {START_SHA} match {h == START_SHA}")
    if h != START_SHA:
        plog(runs, "BLOCKED: start-state hash differs"); sys.exit(4)
    X0, meta = E.load_state(state)
    plog(runs, f"start-state meta {json.dumps(meta)}")
    assert meta.get("next_layer") == 31, meta
    prompts = json.load(open(EXP / "20261111-8-qwen-e2e-agreement" / "prompts-e2e.json"))["prompts"]
    T = {p["id"]: len(p["token_ids"]) for p in prompts}
    (runs / "probe").mkdir(exist_ok=True)
    ckpts = {"stock": F.Ckpt("stock", runs / "probe"), "abl": F.Ckpt("abl", runs)}
    pool = E.make_pool()
    # ---- timing probe (PREREG Kill criterion): synthetic 512-token residual, stock layers 0 and 3, every full path
    xs = np.random.default_rng(0).normal(size=(512, F.HID))
    P = {p: {"probe": xs.copy()} for p in PATHS if p != "M31#2"}
    tl = {}
    for i in (0, 3):
        tf = time.time(); L = ckpts["stock"].layer(i); tfe = time.time() - tf
        t1 = time.time(); layer_all(i, L, P, pool, runs / "probe", "probe"); tl[i] = time.time() - t1; del L
        plog(runs, f"probe stock layer {i} ({F.layer_type(i)}): fetch {tfe:.1f} s, compute {tl[i]:.1f} s")
    ckpts["stock"].save()
    t_lin, t_full = tl[0], tl[3]
    proj = lambda n: (n / 512) * (N_LIN * t_lin + N_FULL * t_full) + LOGITS_S
    tn = time.time(); avail = min(CAP_S - (tn - grant), hard - tn)
    n10 = sum(T.values()); n6 = sum(T[p] for p in SIX)
    use = [p["id"] for p in prompts] if proj(n10) <= avail else [p for p in [q["id"] for q in prompts] if p in SIX]
    choice = dict(t_lin_s=round(t_lin, 2), t_full_s=round(t_full, 2), projected_10_s=round(proj(n10), 1), projected_6_s=round(proj(n6), 1),
                  available_s=round(avail, 1), since_grant_s=round(tn - grant, 1), set="all10" if len(use) == 10 else "six",
                  prompts=use, n_tokens=sum(T[p] for p in use))
    plog(runs, "decision " + json.dumps(choice)); log(runs, "progress.log.jsonl", dict(t=now(), decision=choice))
    # ---- registered run
    X = {p: {pid: X0["REF"][pid].copy() for pid in use if p != "M31#2" or pid in DET} for p in PATHS}
    del X0
    fetch_ex = ThreadPoolExecutor(1); C = ckpts["abl"]
    layers = list(range(31, F.NL))
    fut = fetch_ex.submit(C.layer, layers[0])
    for n, i in enumerate(layers):
        tw = time.time(); L = fut.result(); wait = time.time() - tw
        C.save()
        fut = fetch_ex.submit(C.layer, layers[n + 1]) if n + 1 < len(layers) else None
        row = layer_all(i, L, X, pool, runs, "abl"); del L
        log(runs, "progress.log.jsonl", dict(t=now(), leg="abl", layer=i, fetch_wait_s=round(wait, 1), layer_s=row["seconds"]))
        print("abl layer", i, F.layer_type(i), "wait", round(wait, 1), "s", row["seconds"], flush=True)
    out = finish(X, C, runs, "abl", E.TOKYO)
    print("logits done", out["seconds"], "sanity", out.get("sanity_pass"), flush=True)
    pool.close(); pool.join()
    log(runs, "progress.log.jsonl", dict(t=now(), all_done=True))


def cmd_fixture(scratch, outp):
    """Debug only: PR #88's fixture prompt (not in the suite), stock layers 0 and 3, every path, then the stock lm_head."""
    E.PATH_ORDER = PATHS
    sc = Path(scratch); sc.mkdir(parents=True, exist_ok=True); t0 = time.time()
    C = F.Ckpt("stock", sc); pool = E.make_pool()
    emb = C.emb_rows(F.FIXTURE); x0 = np.stack([emb[t] for t in F.FIXTURE])
    X = {p: {"fx": x0.copy()} for p in PATHS}
    times = []
    for i in (0, 3):
        tf = time.time(); L = C.layer(i); tfe = time.time() - tf
        row = layer_all(i, L, X, pool, sc, "fx"); del L
        times.append(dict(layer=i, fetch_s=round(tfe, 1), layer_s=row["seconds"]))
    out = finish(X, C, sc, "fx", None)
    pool.close(); pool.join()
    rows = [json.loads(l) for l in open(sc / "ranges-fx.jsonl")]
    r = out["prompts"]["fx"]
    o = dict(det_equal=bool(np.array_equal(X["M31#2"]["fx"], X["M31"]["fx"])),
             resid_rel_vs_ref={p: rel(X[p]["fx"], X["REF"]["fx"]) for p in PATHS if p != "REF"},
             ref_top1=r["ref_top1"], kl={p: r["paths"][p]["kl"] for p in r["paths"]},
             top1_agree={p: r["paths"][p]["top1_agree"] for p in r["paths"]},
             logits_det_equal=r["paths"]["M31#2"] == r["paths"]["M31"],
             weights=[x["weights"] for x in rows], ranges={p: [x["paths"][p]["fx"] for x in rows] for p in PATHS if p != "REF"},
             errors=(sc / "errors-fx.jsonl").exists(), timing=times, logits_s=out["seconds"], seconds=round(time.time() - t0, 1))
    Path(outp).write_text(json.dumps(o, indent=1) + "\n"); print(json.dumps(o, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "run":
        cmd_run(sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5] if len(sys.argv) > 5 else "2026-11-14T06:45:00Z")
    else:
        cmd_fixture(sys.argv[2], sys.argv[3])
