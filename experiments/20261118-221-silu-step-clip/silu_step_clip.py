#!/usr/bin/env python3
"""SiLU table step vs domain clip, abliterated layers 31..63 (PREREG.md, issue #221). Diagnostic only: no proof, no
soundness claim, no repair chosen. The arms are not candidate operators.

Every path starts from the REF residual entering layer 31 (PR #167's hashed layer-30 state). DeltaNet heads, in_proj,
out_proj, attention, every RMSNorm, final norm and lm_head are float64, as in PR #202.
  REF      float64 MLP (PR #88 q1_forward.mlp, unchanged)
  M31-C    clip only removed: gw in D -> TS[floor(gw/16)+2048] (as M31); gw outside D -> silu_exact(gw)
  M31-T    step only removed: s = silu_exact(clip(gw, -2^15, 2^15-1))
  M31-C#2  M31-C again on p01 and p09 (determinism)
  (fixture only, debug: M31 = PR #138 mlp_int, M31-S = PR #202 mlp_int_S, for the U3 relations)
D = [-2^15, 2^15), silu_exact = PR #202's (rint(2^12 silu(gw/2^12)), float64, ties to even). Every other line of the MLP is
PR #138's mlp_int, copied below line for line except the line that computes s.
Reused unchanged: PR #202 mlp_stage.py (silu_exact, stats, sha256, plog, head_task, constants), PR #138 mlp_e2e.py,
PR #124 e2e.py, PR #88 q1_forward.py.

Usage:
  silu_step_clip.py run <start state npz> <runs dir> <grant unix> <hard stop iso>
  silu_step_clip.py fixture <scratch> <out json>     debug only: PR #88 fixture prompt, stock layers 0 and 3, stock lm_head
"""
import calendar, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "20261114-201-mlp-stage"))
import mlp_stage as S    # PR #202, unchanged (imports PR #138 mlp_e2e, PR #124 e2e, PR #88 q1_forward)
M, E, F = S.M, S.E, S.F
FB, TS = S.FB, S.TS
LO, HI = -2 ** 15, 2 ** 15            # domain D = [LO, HI)
START_SHA = S.START_SHA
CAP_S = 100 * 60
N_LIN, N_FULL, LOGITS_S = 24, 9, 150
DET = S.DET
SIX = S.SIX
RUN_PATHS = ["REF", "M31-C", "M31-T", "M31-C#2"]
FIX_PATHS = ["REF", "M31", "M31-S", "M31-C", "M31-T", "M31-C#2"]
W_NAMES = S.W_NAMES
now = S.now
log, rel = E.log, E.rel
amax = S.amax


def s_table(gw):
    """M31's lookup (PR #138 mlp_int line 116)."""
    raw = np.floor(gw / 2.0 ** (FB - 8)) + 2048
    return TS[np.clip(raw, 0, 4095).astype(np.int64)]


def s_clip_removed(gw):
    """M31-C: table inside D, silu_exact outside D."""
    inside = (gw >= LO) & (gw < HI)
    return np.where(inside, s_table(gw), S.silu_exact(gw))


def s_step_removed(gw):
    """M31-T: silu_exact on gw clipped to [-2^15, 2^15 - 1]."""
    return S.silu_exact(np.clip(gw, LO, HI - 1))


SFUN = {"M31": s_table, "M31-C": s_clip_removed, "M31-C#2": s_clip_removed, "M31-T": s_step_removed, "M31-S": S.silu_exact}
HOOK = None   # fixture only: called with (path, gw, s) to check U3 relations on real gw arrays


def mlp_arm(path):
    sfun = SFUN[path]

    def f(L, x, ex):
        """PR #138 mlp_int, line for line, except s = sfun(gw)."""
        hf = F.rms0(x, L["post_attention_layernorm.weight"])
        m = np.rint(hf * 2.0 ** FB)
        accg = M.exact_matmul(m, L["mlp.gate_proj.weight"], "gate"); gw = np.floor(accg / 2.0 ** ex["g"])
        accu = M.exact_matmul(m, L["mlp.up_proj.weight"], "up"); u = np.floor(accu / 2.0 ** ex["u"])
        raw = np.floor(gw / 2.0 ** (FB - 8)) + 2048
        lo = int((raw < 0).sum()); hi = int((raw > 4095).sum())
        s = sfun(gw)
        if HOOK is not None: HOOK(path, gw, s)
        if amax(s) * amax(u) >= M.EXACT:
            raise M.GuardError(f"s*u: {amax(s) * amax(u):.3e} >= 2^53")
        h = np.floor(s * u / 2.0 ** FB)
        accd = M.exact_matmul(h, L["mlp.down_proj.weight"], "down"); out = np.floor(accd / 2.0 ** ex["d"])
        return out / 2.0 ** FB, S.stats(m, gw, u, s, h, accd, out, lo, hi)
    return f


def layer_all(i, L, X, pool, runs, leg, paths):
    t0 = time.time(); errname = f"errors-{leg}.jsonl"
    if F.layer_type(i) == "linear_attention":
        pend = []
        for p in paths:
            for pid, x in X.get(p, {}).items():
                if x is None: continue
                pend.append(pool.apply_async(S.head_task, (p, pid, F.deltanet_inputs(L, x))))
        Wo = L["linear_attn.out_proj.weight"]
        for r in pend:
            p, pid, y = r.get()
            X[p][pid] = X[p][pid] + y.reshape(y.shape[0], -1) @ Wo.T
    else:
        for p in paths:
            for pid, x in X.get(p, {}).items():
                if x is None: continue
                X[p][pid] = x + F.attention(L, x)
    tmix = time.time() - t0
    for pid, x in X["REF"].items():
        if x is not None: X["REF"][pid] = x + F.mlp(L, x)
    ex = {k: M.exponent(float(np.abs(L[f"mlp.{n}_proj.weight"]).max())) for k, n in W_NAMES}
    conv = {k: M.to_int_inplace(L[f"mlp.{n}_proj.weight"]) for k, n in W_NAMES}
    assert all(conv[k]["e"] == ex[k] for k in ex), (conv, ex)
    rng_row = dict(leg=leg, layer=i, paths={}, weights=conv)
    for p in paths:
        if p == "REF" or p not in X: continue
        fn = mlp_arm(p); rng_row["paths"][p] = {}
        for pid, x in X[p].items():
            if x is None: continue
            try:
                d, st = fn(L, x, ex)
            except M.GuardError as e:
                log(runs, errname, dict(leg=leg, layer=i, path=p, prompt=pid, error="GuardError: " + str(e))); X[p][pid] = None; continue
            X[p][pid] = x + d; rng_row["paths"][p][pid] = st
    log(runs, f"ranges-{leg}.jsonl", rng_row)
    row = dict(leg=leg, layer=i, type=F.layer_type(i), seconds=round(time.time() - t0, 1), mix_s=round(tmix, 1))
    for p in paths:
        if p == "REF" or p not in X: continue
        row[p] = {pid: (rel(x, X["REF"][pid]) if x is not None and X["REF"][pid] is not None else None) for pid, x in X[p].items()}
    row["det_bit_equal"] = {f"M31-C#2|{pid}": bool(x is not None and X["M31-C"].get(pid) is not None and np.array_equal(x, X["M31-C"][pid]))
                            for pid, x in X.get("M31-C#2", {}).items()}
    log(runs, f"divergence-{leg}.jsonl", row)
    return row


def finish(X, C, runs, leg, sanity_tok, paths):
    t0 = time.time(); Ln = C.t(F.P + "norm.weight")
    Hn = {p: {pid: (F.rms0(x, Ln) if x is not None else None) for pid, x in d.items()} for p, d in X.items()}
    res = E.logits_metrics(Hn, E.lm_head_chunks(C)); C.save()
    out = dict(leg=leg, checkpoint=C.which, paths=paths, prompts=res, seconds=round(time.time() - t0, 1))
    if sanity_tok is not None:
        p01 = res.get("p01-ordinary-short")
        out.update(sanity_p01_last_top1=p01["ref_top1"][-1], sanity_pass=p01["ref_top1"][-1] == sanity_tok)
    (Path(runs) / f"e2e-{leg}.json").write_text(json.dumps(out) + "\n")
    log(runs, "progress.log.jsonl", dict(t=now(), leg=leg, logits_done=True, seconds=out["seconds"], sanity_pass=out.get("sanity_pass")))
    return out


def cmd_run(state, runs, grant, hard_txt):
    paths = RUN_PATHS
    E.PATH_ORDER = paths
    runs = Path(runs); runs.mkdir(parents=True, exist_ok=True)
    hard = calendar.timegm(time.strptime(hard_txt, "%Y-%m-%dT%H:%M:%SZ"))
    h = S.sha256(state)
    S.plog(runs, f"start-state sha256 {h} expected {START_SHA} match {h == START_SHA}")
    if h != START_SHA:
        S.plog(runs, "BLOCKED: start-state hash differs"); sys.exit(4)
    X0, meta = E.load_state(state)
    S.plog(runs, f"start-state meta {json.dumps(meta)}")
    if meta.get("next_layer") != 31:
        S.plog(runs, "BLOCKED: next_layer is not 31"); sys.exit(4)
    prompts = json.load(open(EXP / "20261111-8-qwen-e2e-agreement" / "prompts-e2e.json"))["prompts"]
    T = {p["id"]: len(p["token_ids"]) for p in prompts}
    (runs / "probe").mkdir(exist_ok=True)
    ckpts = {"stock": F.Ckpt("stock", runs / "probe"), "abl": F.Ckpt("abl", runs)}
    pool = E.make_pool()
    # ---- timing probe (PREREG Kill criterion): synthetic 512-token residual, stock layers 0 and 3, every path but the duplicate
    xs = np.random.default_rng(0).normal(size=(512, F.HID))
    P = {p: {"probe": xs.copy()} for p in paths if p != "M31-C#2"}
    tl = {}
    for i in (0, 3):
        tf = time.time(); L = ckpts["stock"].layer(i); tfe = time.time() - tf
        t1 = time.time(); layer_all(i, L, P, pool, runs / "probe", "probe", paths); tl[i] = time.time() - t1; del L
        S.plog(runs, f"probe stock layer {i} ({F.layer_type(i)}): fetch {tfe:.1f} s, compute {tl[i]:.1f} s")
    ckpts["stock"].save()
    t_lin, t_full = tl[0], tl[3]
    proj = lambda n: (n / 512) * (N_LIN * t_lin + N_FULL * t_full) + LOGITS_S
    tn = time.time(); avail = min(CAP_S - (tn - grant), hard - tn)
    n10 = sum(T.values()); n6 = sum(T[p] for p in SIX)
    use = [p["id"] for p in prompts] if proj(n10) <= avail else [q["id"] for q in prompts if q["id"] in SIX]
    choice = dict(t_lin_s=round(t_lin, 2), t_full_s=round(t_full, 2), projected_10_s=round(proj(n10), 1), projected_6_s=round(proj(n6), 1),
                  available_s=round(avail, 1), since_grant_s=round(tn - grant, 1), set="all10" if len(use) == 10 else "six",
                  prompts=use, n_tokens=sum(T[p] for p in use))
    S.plog(runs, "decision " + json.dumps(choice)); log(runs, "progress.log.jsonl", dict(t=now(), decision=choice))
    # ---- registered run
    X = {p: {pid: X0["REF"][pid].copy() for pid in use if p != "M31-C#2" or pid in DET} for p in paths}
    del X0
    fetch_ex = ThreadPoolExecutor(1); C = ckpts["abl"]
    layers = list(range(31, F.NL))
    fut = fetch_ex.submit(C.layer, layers[0])
    for n, i in enumerate(layers):
        tw = time.time(); L = fut.result(); wait = time.time() - tw
        C.save()
        fut = fetch_ex.submit(C.layer, layers[n + 1]) if n + 1 < len(layers) else None
        row = layer_all(i, L, X, pool, runs, "abl", paths); del L
        log(runs, "progress.log.jsonl", dict(t=now(), leg="abl", layer=i, fetch_wait_s=round(wait, 1), layer_s=row["seconds"]))
        print("abl layer", i, F.layer_type(i), "wait", round(wait, 1), "s", row["seconds"], flush=True)
    out = finish(X, C, runs, "abl", E.TOKYO, paths)
    print("logits done", out["seconds"], "sanity", out.get("sanity_pass"), flush=True)
    pool.close(); pool.join()
    log(runs, "progress.log.jsonl", dict(t=now(), all_done=True))


def u_relations(gw, s_c, s_t):
    """U1/U2 element-wise on one gw array. Returns counts (all must be zero mismatches)."""
    inside = (gw >= LO) & (gw < HI)
    s_m31 = s_table(gw); s_s = S.silu_exact(gw)
    return dict(n=int(gw.size), n_inside=int(inside.sum()), n_outside=int((~inside).sum()),
                U1_in_mismatch=int((s_c[inside] != s_m31[inside]).sum()),
                U1_out_mismatch=int((s_c[~inside] != s_s[~inside]).sum()),
                U2_in_mismatch=int((s_t[inside] != s_s[inside]).sum()),
                U2_out_mismatch_vs_clipped=int((s_t[~inside] != S.silu_exact(np.clip(gw[~inside], LO, HI - 1))).sum()),
                U2_out_differs_from_S=int((s_t[~inside] != s_s[~inside]).sum()))


def cmd_fixture(scratch, outp):
    """Debug only: PR #88's fixture prompt (not in the suite), stock layers 0 and 3, every fixture path, stock lm_head."""
    global HOOK
    paths = FIX_PATHS
    E.PATH_ORDER = paths
    sc = Path(scratch); sc.mkdir(parents=True, exist_ok=True); t0 = time.time()
    C = F.Ckpt("stock", sc); pool = E.make_pool()
    emb = C.emb_rows(F.FIXTURE); x0 = np.stack([emb[t] for t in F.FIXTURE])
    X = {p: {"fx": x0.copy()} for p in paths}
    rel_rows = []

    def hook(path, gw, s):
        if path == "M31-C":
            r = u_relations(gw, s, s_step_removed(gw)); r["path"] = path; rel_rows.append(r)
    HOOK = hook
    times = []
    for i in (0, 3):
        tf = time.time(); L = C.layer(i); tfe = time.time() - tf
        row = layer_all(i, L, X, pool, sc, "fx", paths); del L
        times.append(dict(layer=i, fetch_s=round(tfe, 1), layer_s=row["seconds"]))
    HOOK = None
    out = finish(X, C, sc, "fx", None, paths)
    pool.close(); pool.join()
    rows = [json.loads(l) for l in open(sc / "ranges-fx.jsonl")]
    r = out["prompts"]["fx"]
    o = dict(note="debug only, fixture prompt, stock layers 0 and 3; not a registered measurement",
             det_equal=bool(np.array_equal(X["M31-C#2"]["fx"], X["M31-C"]["fx"])),
             logits_det_equal=r["paths"]["M31-C#2"] == r["paths"]["M31-C"],
             u3_relations_per_layer=rel_rows,
             u3_all_zero=all(v[k] == 0 for v in rel_rows for k in ("U1_in_mismatch", "U1_out_mismatch", "U2_in_mismatch", "U2_out_mismatch_vs_clipped")),
             resid_rel_vs_ref={p: rel(X[p]["fx"], X["REF"]["fx"]) for p in paths if p != "REF"},
             ref_top1=r["ref_top1"], kl={p: r["paths"][p]["kl"] for p in r["paths"]},
             top1_agree={p: r["paths"][p]["top1_agree"] for p in r["paths"]},
             domain_exits={p: [x["paths"][p]["fx"]["n_silu_sat_lo"] + x["paths"][p]["fx"]["n_silu_sat_hi"] for x in rows] for p in paths if p != "REF"},
             errors=(sc / "errors-fx.jsonl").exists(), timing=times, logits_s=out["seconds"], seconds=round(time.time() - t0, 1))
    Path(outp).write_text(json.dumps(o, indent=1) + "\n"); print(json.dumps(o, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "run":
        cmd_run(sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5])
    else:
        cmd_fixture(sys.argv[2], sys.argv[3])
