#!/usr/bin/env python3
"""Q1: float64 streaming forward of Qwen3.8-27B (stock and abliterated) on PR #68's frozen prompts, to produce the
head inputs of deeper DeltaNet layers for scaled_head.py (PR #74, unchanged), plus a closed-loop end-to-end run of
the integer lowering on a short-prompt subset. PREREG.md (this directory).

Weights are read by HTTP range request into memory, one layer at a time (nothing written to disk). Every fetched
tensor's sha256 goes into runs/manifest-<ckpt>.json. Float semantics: modeling_qwen3_5.py as pinned by PR #68
(DeltaNet via PR #68's real_head.inproj-equivalent / heads / run_float; gated full attention; SwiGLU MLP;
zero-centred RMSNorm), float64 throughout.

Paths on the end-to-end subset E: REF (float64), INT (every DeltaNet layer's heads replaced by scaled_head.Head with
arm XS18), BF16H (heads replaced by run_float(emulate_bf16=True)). Everything else in INT and BF16H is float64.

Usage (scratch = a directory outside the repo; runs = this directory's runs/):
  q1_forward.py fixture <scratch> <runs>      debug on "The capital of Italy is" (not in the suite), layers 0-3
  q1_forward.py stageA  <scratch> <runs>      stock layers 0..20, all prompts (REF) + E paths; prep for L16, L20
  q1_forward.py stageB  <scratch> <runs>      abl layers 17..20 from stock's layer-17 input; prep for abl L20
  q1_forward.py stageD  <scratch> <runs>      stock layers 21..63 on E paths, final norm, lm_head, metrics
  q1_forward.py stageE  <scratch> <runs>      abl layers 17..63 on E paths (from stock's layer-17 E states), metrics
"""
import hashlib, json, math, os, struct, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP / "20261110-8-qwen-norm-scaling"))
sys.path.insert(0, str(EXP / "20261109-8-qwen-real-weights"))
import scaled_head as SH   # PR #74, unchanged
import real_head as RH     # PR #68, unchanged

REPOS = {"stock": ("Qwen/Qwen3.8-27B", "37561816e66b5b9153b1b64c10968c18c1e6f4a0"),
         "abl": ("huihui-ai/Huihui-Qwen3.8-27B-abliterated", "739e3c5b89849f6c238ce1e5b70008612ae42cdd")}
P = "model.language_model."
HID, NL, EPS = 5120, 64, 1e-6
NH, NKV, HD, ROT, THETA = 24, 4, 256, 64, 1e7
E_IDS = ("p01-ordinary-short", "p07-chat-ordinary", "p08-chat-refusal", "p09-multilingual")
FIXTURE = [760, 6511, 314, 14898, 369]   # "The capital of Italy is" (debug only, not in the suite)
TOKYO = 25358
UA = {"User-Agent": "flashprove-q1-fidelity/1"}
CHUNK = 48 << 20

def layer_type(i): return "full_attention" if i % 4 == 3 else "linear_attention"

def arm_xs18():
    return json.load(open(HERE / "arms-q1.json"))["XS18"]["cfg"]

# ------------------------------------------------------------------ fetch
def get(url, rng=None, tries=5):
    h = dict(UA)
    if rng: h["Range"] = rng
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=300) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403): raise SystemExit(f"gated or forbidden: {url} ({e.code}); stop")
            if i == tries - 1: raise
        except Exception:
            if i == tries - 1: raise
        time.sleep(2 * (i + 1))

class Ckpt:
    def __init__(self, which, runs):
        self.which = which; repo, rev = REPOS[which]
        self.base = f"https://huggingface.co/{repo}/resolve/{rev}/"
        self.wm = json.loads(get(self.base + "model.safetensors.index.json"))["weight_map"]
        self.hdr = {}
        self.manf = Path(runs) / f"manifest-{which}.json"
        self.man = json.load(open(self.manf)) if self.manf.exists() else dict(repo=repo, rev=rev, tensors={}, embedding_rows={})
        self.pool = ThreadPoolExecutor(8)

    def header(self, shard):
        if shard not in self.hdr:
            n = struct.unpack("<Q", get(self.base + shard, "bytes=0-7"))[0]
            self.hdr[shard] = (n, json.loads(get(self.base + shard, f"bytes=8-{7 + n}")))
        return self.hdr[shard]

    def raw(self, name):
        shard = self.wm[name]; hl, h = self.header(shard); b, e = h[name]["data_offsets"]
        lo, hi = 8 + hl + b, 8 + hl + e - 1
        parts = [(s, min(s + CHUNK - 1, hi)) for s in range(lo, hi + 1, CHUNK)]
        data = b"".join(self.pool.map(lambda r: get(self.base + shard, f"bytes={r[0]}-{r[1]}"), parts))
        assert len(data) == e - b, (name, len(data), e - b)
        assert h[name]["dtype"] == "BF16", (name, h[name]["dtype"])
        self.man["tensors"][name] = dict(shard=shard, range=f"bytes={lo}-{hi}", nbytes=len(data), dtype=h[name]["dtype"],
                                         shape=h[name]["shape"], sha256=hashlib.sha256(data).hexdigest())
        return data, h[name]["shape"]

    def t(self, name):
        data, shape = self.raw(name)
        a = (np.frombuffer(data, dtype="<u2").astype(np.uint32) << 16).view(np.float32).reshape(shape)
        del data
        return a.astype(np.float64)

    def layer(self, i):
        pre = P + f"layers.{i}."
        names = [n for n in self.wm if n.startswith(pre)]
        L = {}
        for n in names:
            L[n[len(pre):]] = self.t(n)
        return L

    def emb_rows(self, ids):
        name = P + "embed_tokens.weight"; shard = self.wm[name]; hl, h = self.header(shard); b, e = h[name]["data_offsets"]
        V, d = h[name]["shape"]; row = (e - b) // V; assert row == 2 * d
        def one(t):
            lo = 8 + hl + b + t * row; data = get(self.base + shard, f"bytes={lo}-{lo + row - 1}"); assert len(data) == row
            return t, lo, data
        out = {}
        for t, lo, data in self.pool.map(one, sorted(set(ids))):
            self.man["embedding_rows"][str(t)] = dict(range=f"bytes={lo}-{lo + row - 1}", sha256=hashlib.sha256(data).hexdigest())
            out[t] = (np.frombuffer(data, dtype="<u2").astype(np.uint32) << 16).view(np.float32).astype(np.float64)
        return out

    def lm_head_logits(self, H):
        """H (N, 5120) float64 -> logits (N, V), lm_head streamed in row chunks; sha256 over the whole tensor."""
        name = "lm_head.weight"; shard = self.wm[name]; hl, h = self.header(shard); b, e = h[name]["data_offsets"]
        V, d = h[name]["shape"]; row = 2 * d; rows_per = CHUNK // row
        out = np.empty((H.shape[0], V)); sha = hashlib.sha256(); lo0 = 8 + hl + b
        ranges = [(r0, min(r0 + rows_per, V)) for r0 in range(0, V, rows_per)]
        fetch = lambda r: get(self.base + shard, f"bytes={lo0 + r[0] * row}-{lo0 + r[1] * row - 1}")
        for (r0, r1), data in zip(ranges, self.pool.map(fetch, ranges)):
            assert len(data) == (r1 - r0) * row
            sha.update(data)
            W = (np.frombuffer(data, dtype="<u2").astype(np.uint32) << 16).view(np.float32).reshape(r1 - r0, d).astype(np.float64)
            out[:, r0:r1] = H @ W.T
        self.man["tensors"][name] = dict(shard=shard, range=f"bytes={lo0}-{lo0 + V * row - 1}", nbytes=V * row, dtype="BF16",
                                         shape=[V, d], sha256=sha.hexdigest())
        return out

    def save(self):
        self.manf.write_text(json.dumps(self.man, indent=1, sort_keys=True) + "\n")

# ------------------------------------------------------------------ float64 blocks
def rms0(x, w):
    return x / np.sqrt((x * x).mean(-1, keepdims=True) + EPS) * (1.0 + w)

def deltanet_inputs(L, x):
    """x (T, 5120) residual -> head inputs (PR #68 inproj, with the residual in place of the embedding)."""
    h = rms0(x, L["input_layernorm.weight"])
    qkv = h @ L["linear_attn.in_proj_qkv.weight"].T
    z = h @ L["linear_attn.in_proj_z.weight"].T
    a = h @ L["linear_attn.in_proj_a.weight"].T; b = h @ L["linear_attn.in_proj_b.weight"].T
    return RH.heads(L, qkv, z, a, b)

def head_out(hd, mode, cfg=None):
    """Per-token head outputs y (T, 48, 128) as float64, by REF float64, INT (scaled_head) or BF16H."""
    xq, xk, xv, ar, br, zz, Wc, A, dtb, gain = hd
    if mode == "REF":
        return np.stack([y for _, _, y in RH.run_float(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain)])
    if mode == "BF16H":
        return np.stack([y for _, _, y in RH.run_float(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, emulate_bf16=True)])
    h = SH.Head(cfg)
    ys = [y for _, _, y, _ in h.run(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain, {})]
    return np.stack(ys) * math.ldexp(1.0, -h.c["Fy"])

def attention(L, x):
    T = x.shape[0]
    h = rms0(x, L["input_layernorm.weight"])
    qg = (h @ L["self_attn.q_proj.weight"].T).reshape(T, NH, 2 * HD)
    q, gate = qg[:, :, :HD], qg[:, :, HD:].reshape(T, NH * HD)
    q = rms0(q, L["self_attn.q_norm.weight"])
    k = rms0((h @ L["self_attn.k_proj.weight"].T).reshape(T, NKV, HD), L["self_attn.k_norm.weight"])
    v = (h @ L["self_attn.v_proj.weight"].T).reshape(T, NKV, HD)
    inv = 1.0 / (THETA ** (np.arange(0, ROT, 2, dtype=np.float64) / ROT))
    fr = np.arange(T, dtype=np.float64)[:, None] * inv[None, :]
    emb = np.concatenate([fr, fr], -1); cos, sin = np.cos(emb)[:, None, :], np.sin(emb)[:, None, :]
    def rope(u):
        r, p = u[..., :ROT], u[..., ROT:]
        rh = np.concatenate([-r[..., ROT // 2:], r[..., :ROT // 2]], -1)
        return np.concatenate([r * cos + rh * sin, p], -1)
    q, k = rope(q), rope(k)
    kv = np.arange(NH) // (NH // NKV)
    s = np.einsum("thd,uhd->htu", q, k[:, kv]) / math.sqrt(HD)
    s = np.where(np.tril(np.ones((T, T), bool))[None], s, -np.inf)
    s = s - s.max(-1, keepdims=True); p = np.exp(s); p /= p.sum(-1, keepdims=True)
    o = np.einsum("htu,uhd->thd", p, v[:, kv]).reshape(T, NH * HD)
    o = o * (1.0 / (1.0 + np.exp(-gate)))
    return o @ L["self_attn.o_proj.weight"].T

def mlp(L, x):
    h = rms0(x, L["post_attention_layernorm.weight"])
    g = h @ L["mlp.gate_proj.weight"].T; u = h @ L["mlp.up_proj.weight"].T
    return (g / (1.0 + np.exp(-g)) * u) @ L["mlp.down_proj.weight"].T

def layer_step(i, L, x, mode="REF", cfg=None, keep=None):
    """One decoder layer on x (T, 5120). For DeltaNet layers the heads run in `mode`. keep: dict to receive
    head inputs / y / mixer output (for prep and the U1 reading)."""
    if layer_type(i) == "linear_attention":
        hd = deltanet_inputs(L, x)
        y = head_out(hd, mode, cfg)
        mix = y.reshape(y.shape[0], -1) @ L["linear_attn.out_proj.weight"].T
        if keep is not None: keep.update(hd=hd, y=y, mix=mix)
    else:
        mix = attention(L, x)
    x = x + mix
    return x + mlp(L, x)

# ------------------------------------------------------------------ helpers
def prompts():
    return json.load(open(EXP / "20261109-8-qwen-real-weights" / "prompts.json"))["prompts"]

def write_prep(outdir, ck, pid, x, hd):
    Path(outdir).mkdir(parents=True, exist_ok=True)
    np.savez(Path(outdir) / f"prep-{ck}-{pid}.npz", x=x, **dict(zip(("xq", "xk", "xv", "ar", "br", "zz", "Wc", "A", "dtb", "gain"), hd)))

def rel(a, b):
    nb = float(np.linalg.norm(b)); return float(np.linalg.norm(a - b)) / nb if nb else float("nan")

def log(runs, name, obj):
    with open(Path(runs) / name, "a") as f: f.write(json.dumps(obj) + "\n")

def lse(z):
    m = z.max(-1, keepdims=True); return (m + np.log(np.exp(z - m).sum(-1, keepdims=True)))[..., 0]

def logit_metrics(Lr, Lp):
    lr = Lr - lse(Lr)[:, None]; lp = Lp - lse(Lp)[:, None]
    kl = (np.exp(lr) * (lr - lp)).sum(-1)
    return dict(top1_agree=[bool(a) for a in (Lr.argmax(-1) == Lp.argmax(-1))], kl=[float(v) for v in kl],
                maxdiff_over_std=[float(v) for v in np.abs(Lr - Lp).max(-1) / Lr.std(-1)],
                top1_ref=[int(v) for v in Lr.argmax(-1)], top1_path=[int(v) for v in Lp.argmax(-1)])

def e_paths_step(i, L, E, cfg, runs, ck):
    """E: {path: {pid: x or None}}; INT failures set to None with the error logged."""
    for path in ("REF", "INT", "BF16H"):
        for pid, x in E[path].items():
            if x is None: continue
            try:
                E[path][pid] = layer_step(i, L, x, path, cfg)
            except OverflowError as e:
                log(runs, f"e2e-{ck}-errors.jsonl", dict(layer=i, path=path, prompt=pid, error=str(e))); E[path][pid] = None
    if True:
        row = dict(ckpt=ck, layer=i, type=layer_type(i))
        for path in ("INT", "BF16H"):
            row[path] = {pid: (rel(E[path][pid], E["REF"][pid]) if E[path][pid] is not None else None) for pid in E["REF"]}
        log(runs, f"e2e-{ck}-divergence.jsonl", row)

def finish_e2e(C, E, runs, ck, Lnorm):
    pids = list(E["REF"])
    T = {pid: E["REF"][pid].shape[0] for pid in pids}
    stack = []
    for path in ("REF", "INT", "BF16H"):
        for pid in pids:
            x = E[path][pid] if E[path][pid] is not None else np.zeros_like(E["REF"][pid])
            stack.append(rms0(x, Lnorm))
    Z = C.lm_head_logits(np.concatenate(stack))
    off = 0; LG = {}
    for path in ("REF", "INT", "BF16H"):
        for pid in pids:
            LG[(path, pid)] = Z[off:off + T[pid]]; off += T[pid]
    res = dict(ckpt=ck, prompts={})
    for pid in pids:
        d = dict(T=T[pid])
        for path in ("INT", "BF16H"):
            d[path] = None if E[path][pid] is None else logit_metrics(LG[("REF", pid)], LG[(path, pid)])
        d["ref_top1"] = [int(v) for v in LG[("REF", pid)].argmax(-1)]
        res["prompts"][pid] = d
    p01 = res["prompts"].get("p01-ordinary-short")
    if p01: res["sanity_p01_last_top1"] = p01["ref_top1"][-1]; res["sanity_pass"] = p01["ref_top1"][-1] == TOKYO
    (Path(runs) / f"e2e-{ck}.json").write_text(json.dumps(res, indent=1) + "\n")
    return res

def save_E(path, E):
    np.savez(path, **{f"{p}|{pid}": (x if x is not None else np.zeros(0)) for p, d in E.items() for pid, x in d.items()})

def load_E(path):
    d = np.load(path); E = {"REF": {}, "INT": {}, "BF16H": {}}
    for k in d.files:
        p, pid = k.split("|"); E[p][pid] = d[k] if d[k].size else None
    return E

# ------------------------------------------------------------------ stages
def stage_fixture(scratch, runs):
    C = Ckpt("stock", scratch)  # manifest for the fixture goes to scratch, not runs
    t0 = time.time(); emb = C.emb_rows(FIXTURE); x0 = np.stack([emb[t] for t in FIXTURE])
    L0 = C.layer(0)
    ref = json.load(open(EXP / "20261109-8-qwen-real-weights" / "runs" / "fetch-stock.json"))["tensors"]
    sha_ok = {n: C.man["tensors"][n]["sha256"] == m["sha256"] for n, m in ref.items()}
    # PR #68's inproj on the same tensors vs ours
    Lr = {k: v for k, v in L0.items()}
    _, _, qkv, z, a, b = RH.inproj(Lr, emb, FIXTURE)
    ours = deltanet_inputs(L0, x0); theirs = RH.heads(Lr, qkv, z, a, b)
    eq = all(np.array_equal(u, w) for u, w in zip(ours, theirs))
    cfgs = json.load(open(HERE / "arms-q1.json")); arm_ok = {}
    for n, arm in cfgs.items():
        try:
            yi = head_out(ours, "INT", arm["cfg"]); yf = head_out(ours, "REF"); arm_ok[n] = rel(yi, yf)
        except OverflowError as e:
            arm_ok[n] = "overflow " + str(e)
    x = x0
    for i in range(4):
        L = L0 if i == 0 else C.layer(i)
        x = layer_step(i, L, x)
        print("fixture layer", i, layer_type(i), float(np.linalg.norm(x)), round(time.time() - t0, 1), flush=True)
    out = dict(layer0_sha_equal_pr68=sha_ok, inproj_equal_pr68=eq, arm_rel_y_fixture=arm_ok, x4_norm=float(np.linalg.norm(x)),
               seconds=round(time.time() - t0, 1))
    (Path(scratch) / "fixture.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out, indent=1))

def stage_fixture2(scratch, runs):
    """Debug of the E-path code (e_paths_step, save/load, metrics on synthetic logits) on the fixture, layers 0-3.
    No lm_head, no registered prompt."""
    sc = Path(scratch); C = Ckpt("stock", scratch); cfg = arm_xs18(); t0 = time.time()
    emb = C.emb_rows(FIXTURE); x0 = np.stack([emb[t] for t in FIXTURE])
    E = {path: {"fx": x0.copy()} for path in ("REF", "INT", "BF16H")}
    for i in range(4):
        L = C.layer(i); e_paths_step(i, L, E, cfg, scratch, "fixture"); del L
    save_E(sc / "Efx.npz", E); E2 = load_E(sc / "Efx.npz")
    same = all(np.array_equal(E[p][k], E2[p][k]) for p in E for k in E[p])
    rng = np.random.default_rng(0); Lr = rng.normal(size=(5, 1000)); Lp = Lr + 0.01 * rng.normal(size=(5, 1000))
    m = logit_metrics(Lr, Lp); m0 = logit_metrics(Lr, Lr)
    out = dict(save_load_equal=same, kl_self=max(m0["kl"]), agree_self=all(m0["top1_agree"]), kl_small=max(m["kl"]),
               seconds=round(time.time() - t0, 1))
    (sc / "fixture2.json").write_text(json.dumps(out, indent=1) + "\n"); print(json.dumps(out))

def stage_A(scratch, runs):
    sc = Path(scratch); C = Ckpt("stock", runs); cfg = arm_xs18(); t0 = time.time()
    ps = prompts(); ids = sorted({t for p in ps for t in p["token_ids"]}); emb = C.emb_rows(ids)
    X = {p["id"]: np.stack([emb[t] for t in p["token_ids"]]) for p in ps}
    E = {path: {pid: X[pid].copy() for pid in E_IDS} for path in ("REF", "INT", "BF16H")}
    for i in range(0, 21):
        L = C.layer(i)
        if i == 17:
            np.savez(sc / "x17-stock.npz", **X); save_E(sc / "E17.npz", E)
        for pid in X:
            keep = {}
            Xn = layer_step(i, L, X[pid], keep=keep)
            if i in (16, 20) and layer_type(i) == "linear_attention":
                write_prep(sc / f"prep-L{i}", f"stock-L{i}", pid, X[pid], keep["hd"])
            if i == 20:
                np.savez(sc / f"mix20-stock-{pid}.npz", x=X[pid], mix=keep["mix"])
            X[pid] = Xn
        if i in (16, 20):
            np.save(sc / f"Wo-stock-L{i}.npy", L["linear_attn.out_proj.weight"].astype(np.float32))
        e_paths_step(i, L, E, cfg, runs, "stock")
        del L
        C.save()
        print("A layer", i, layer_type(i), round(time.time() - t0, 1), flush=True)
    save_E(sc / "E21-stock.npz", E)
    print("stageA done", round(time.time() - t0, 1), flush=True)

def stage_B(scratch, runs):
    sc = Path(scratch); C = Ckpt("abl", runs); t0 = time.time()
    X = dict(np.load(sc / "x17-stock.npz"))
    for i in range(17, 21):
        L = C.layer(i)
        for pid in list(X):
            keep = {}
            Xn = layer_step(i, L, X[pid], keep=keep)
            if i == 20:
                write_prep(sc / "prep-abl-L20", "abl-L20", pid, X[pid], keep["hd"])
                st = np.load(sc / f"mix20-stock-{pid}.npz")
                nx = np.linalg.norm(st["x"], axis=1)
                dm = np.linalg.norm(keep["mix"] - st["mix"], axis=1) / nx
                dx = np.linalg.norm(X[pid] - st["x"], axis=1) / nx
                log(runs, "u1-layer20.jsonl", dict(prompt=pid, T=int(len(nx)),
                    mix_diff_frob=float(np.linalg.norm(keep["mix"] - st["mix"]) / np.linalg.norm(st["x"])),
                    mix_diff_tok_median=float(np.median(dm)), mix_diff_tok_max=float(dm.max()),
                    resid_in_diff_frob=float(np.linalg.norm(X[pid] - st["x"]) / np.linalg.norm(st["x"])),
                    resid_in_diff_tok_median=float(np.median(dx))))
            X[pid] = Xn
        if i == 20: np.save(sc / "Wo-abl-L20.npy", L["linear_attn.out_proj.weight"].astype(np.float32))
        del L; C.save()
        print("B layer", i, round(time.time() - t0, 1), flush=True)
    print("stageB done", round(time.time() - t0, 1), flush=True)

def stage_DE(scratch, runs, ck):
    sc = Path(scratch); C = Ckpt(ck, runs); cfg = arm_xs18(); t0 = time.time()
    if ck == "stock": E, start = load_E(sc / "E21-stock.npz"), 21
    else: E, start = load_E(sc / "E17.npz"), 17
    for i in range(start, NL):
        L = C.layer(i); e_paths_step(i, L, E, cfg, runs, ck); del L; C.save()
        print(ck, "E2E layer", i, layer_type(i), round(time.time() - t0, 1), flush=True)
    Ln = C.t(P + "norm.weight")
    res = finish_e2e(C, E, runs, ck, Ln); C.save()
    print(ck, "e2e done", round(time.time() - t0, 1), "sanity", res.get("sanity_pass"), flush=True)

def main():
    cmd, scratch, runs = sys.argv[1], sys.argv[2], sys.argv[3]
    Path(scratch).mkdir(parents=True, exist_ok=True); Path(runs).mkdir(parents=True, exist_ok=True)
    {"fixture": stage_fixture, "fixture2": stage_fixture2, "stageA": stage_A, "stageB": stage_B,
     "stageD": lambda s, r: stage_DE(s, r, "stock"), "stageE": lambda s, r: stage_DE(s, r, "abl")}[cmd](scratch, runs)

if __name__ == "__main__": main()
