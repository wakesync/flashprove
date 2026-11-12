#!/usr/bin/env python3
"""Record the DeltaNet decay inputs on real activations (PREREG.md, this directory).

Float64 forward: PR #88 `q1_forward.layer_step` (mode REF), imported unchanged. The only addition is this driver:
it passes a `keep` dict to `layer_step` (an existing argument of that function) and saves, per DeltaNet layer and
prompt, keep["hd"]'s `ar` (in_proj_a output, (T, 48)), and per layer `A = exp(A_log)` and `dt_bias` (48,). Nothing
in the forward is changed or re-implemented. Checkpoint legs as PR #124's "abl" leg: stock layers 0..16 (byte-
identical in both checkpoints, PR #68), abliterated layers 17..63, abliterated final norm and lm_head.

Usage:
  record.py fixture <scratch> <out.json>          debug only: "The capital of Italy is", stock layers 0..3, twice
  record.py run <scratch> <runs> <S10|S7>         registered run; per-layer files in <scratch>/ar/, resumes
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "20261110-8-qwen-q1-deep-fidelity"))
import q1_forward as F   # PR #88, unchanged

PROMPTS = EXP / "20261111-8-qwen-e2e-agreement" / "prompts-e2e.json"   # PR #124, unchanged
S7 = ["p01-ordinary-short", "p07-chat-ordinary", "p08-chat-refusal", "p09-multilingual",
      "p02-ordinary-paragraph", "p04-repeat-punct", "p05-code"]
TOKYO = 25358

def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def log(runs, obj):
    with open(Path(runs) / "progress.log.jsonl", "a") as f: f.write(json.dumps(obj) + "\n")

def step_all(i, L, X):
    """One layer for every prompt through q1_forward.layer_step (REF). Returns {pid: ar} for DeltaNet layers."""
    ars = {}
    for pid in X:
        keep = {}
        X[pid] = F.layer_step(i, L, X[pid], "REF", None, keep)
        if F.layer_type(i) == "linear_attention":
            xq, xk, xv, ar, br, zz, Wc, A, dtb, gain = keep["hd"]
            ars[pid] = (np.asarray(ar, dtype=np.float64), np.asarray(A, dtype=np.float64), np.asarray(dtb, dtype=np.float64))
    return ars

def save_layer(d, i, ars):
    pids = list(ars)
    A = ars[pids[0]][1]; dtb = ars[pids[0]][2]
    tmp = Path(d) / f"ar-L{i:02d}.tmp.npz"
    np.savez(tmp, A=A, dt_bias=dtb, **{f"ar|{pid}": ars[pid][0] for pid in pids})
    os.replace(tmp, Path(d) / f"ar-L{i:02d}.npz")

def save_state(path, X, meta):
    tmp = Path(str(path) + ".tmp.npz")
    np.savez(tmp, __meta__=np.frombuffer(json.dumps(meta).encode(), dtype=np.uint8), **X)
    os.replace(tmp, path)

def load_state(path):
    d = np.load(path); meta = json.loads(bytes(d["__meta__"]).decode())
    return {k: d[k] for k in d.files if k != "__meta__"}, meta

def cmd_fixture(scratch, out):
    sc = Path(scratch); sc.mkdir(parents=True, exist_ok=True); t0 = time.time()
    C = F.Ckpt("stock", sc)
    emb = C.emb_rows(F.FIXTURE); x0 = np.stack([emb[t] for t in F.FIXTURE])
    X1 = {"fx": x0.copy()}; X2 = {"fx": x0.copy()}; X3 = {"fx": x0.copy()}
    res = dict(layers=[])
    (sc / "fx-ar").mkdir(exist_ok=True)
    for i in range(4):
        L = C.layer(i)
        a1 = step_all(i, L, X1); a2 = step_all(i, L, X2)
        X3["fx"] = F.layer_step(i, L, X3["fx"])        # plain layer_step, no keep
        row = dict(layer=i, type=F.layer_type(i), x_bit_equal_rerun=bool(np.array_equal(X1["fx"], X2["fx"])),
                   x_bit_equal_plain_layer_step=bool(np.array_equal(X1["fx"], X3["fx"])))
        if a1:
            ar, A, dtb = a1["fx"]
            row.update(ar_bit_equal_rerun=bool(np.array_equal(ar, a2["fx"][0])), ar_shape=list(ar.shape),
                       A_eq_exp_Alog=bool(np.array_equal(A, np.exp(L["linear_attn.A_log"]))),
                       dtb_eq=bool(np.array_equal(dtb, L["linear_attn.dt_bias"])))
            save_layer(sc / "fx-ar", i, a1)
        res["layers"].append(row); del L
        print(json.dumps(row), flush=True)
    res["seconds"] = round(time.time() - t0, 1)
    Path(out).write_text(json.dumps(res, indent=1) + "\n"); print(json.dumps(res))

def cmd_run(scratch, runs, which):
    sc = Path(scratch); runs = Path(runs); sc.mkdir(parents=True, exist_ok=True); runs.mkdir(parents=True, exist_ok=True)
    (sc / "ar").mkdir(exist_ok=True)
    pr = json.load(open(PROMPTS))["prompts"]
    if which == "S7": pr = [p for p in pr if p["id"] in S7]
    assert which in ("S10", "S7") and len(pr) == (10 if which == "S10" else 7)
    ckpts = {"stock": F.Ckpt("stock", runs), "abl": F.Ckpt("abl", runs)}
    if (sc / "state.npz").exists():
        X, meta = load_state(sc / "state.npz"); log(runs, dict(t=now(), resume=True, next_layer=meta["next_layer"]))
    else:
        ids = sorted({t for p in pr for t in p["token_ids"]})
        emb = ckpts["stock"].emb_rows(ids); ckpts["stock"].save()
        X = {p["id"]: np.stack([emb[t] for t in p["token_ids"]]) for p in pr}
        meta = dict(next_layer=0, set=which); log(runs, dict(t=now(), start=True, set=which, prompts={p["id"]: len(p["token_ids"]) for p in pr}))
    layers = [(i, "stock" if i <= 16 else "abl") for i in range(F.NL)]
    todo = [li for li in layers if li[0] >= meta["next_layer"]]
    ex = ThreadPoolExecutor(1); fut = ex.submit(ckpts[todo[0][1]].layer, todo[0][0]) if todo else None
    for n, (i, ck) in enumerate(todo):
        tw = time.time(); L = fut.result(); wait = time.time() - tw
        ckpts[ck].save()
        fut = ex.submit(ckpts[todo[n + 1][1]].layer, todo[n + 1][0]) if n + 1 < len(todo) else None
        tl = time.time(); ars = step_all(i, L, X); del L
        if ars: save_layer(sc / "ar", i, ars)
        meta["next_layer"] = i + 1; save_state(sc / "state.npz", X, meta)
        log(runs, dict(t=now(), layer=i, ckpt=ck, type=F.layer_type(i), fetch_wait_s=round(wait, 1), layer_s=round(time.time() - tl, 1)))
        print("layer", i, ck, F.layer_type(i), "wait", round(wait, 1), "s", round(time.time() - tl, 1), flush=True)
    # sanity: REF top-1 at p01's last position, abl final norm and lm_head
    C = ckpts["abl"]; Ln = C.t(F.P + "norm.weight")
    h = F.rms0(X["p01-ordinary-short"][-1:], Ln)
    z = C.lm_head_logits(h); C.save()
    top = int(z[0].argmax())
    out = dict(t=now(), sanity_p01_last_top1=top, sanity_pass=top == TOKYO, set=which)
    (runs / "sanity.json").write_text(json.dumps(out, indent=1) + "\n"); log(runs, out); print(json.dumps(out), flush=True)

if __name__ == "__main__":
    if sys.argv[1] == "fixture": cmd_fixture(sys.argv[2], sys.argv[3])
    else: cmd_run(sys.argv[2], sys.argv[3], sys.argv[4])
