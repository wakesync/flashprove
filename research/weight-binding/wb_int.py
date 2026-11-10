#!/usr/bin/env python3
"""H2/H3: integer-level stock vs abliterated on a few real tensors. NOT A PROOF.

For each named tensor, fetch its BF16 bytes from both pinned checkpoints by HTTP range request
(held in memory, never written), check the bytes' SHA-256 against PR #68's streamed hash, convert to
the repository's integers by the rule of weight_sums/weight_sums.py for a matrix that reads no norm
(e = the largest exponent with RNE(2^e max|v|) <= 4095; w = RNE(2^e v), int16 little endian), and
report: exponent, differing entries, SHA-256 of the integers, max |delta|, and a toy multilinear
fingerprint MLE_w(z) mod 2^31-1 at a point z derived from (label, tensor name) only.

The fingerprint stands in for the field evaluation a proof would open against a per-tensor root
(DESIGN.md section 3). The toy prime is not the protocol's field; no security figure follows.

Usage: wb_int.py <stream-stock.json> <stream-abl.json> <out.json> <tensor> [<tensor> ...]
       wb_int.py selftest
"""
import hashlib, json, math, struct, sys, time, urllib.request

import numpy as np

REPOS = {"stock": ("Qwen/Qwen3.8-27B", "37561816e66b5b9153b1b64c10968c18c1e6f4a0"),
         "abl": ("huihui-ai/Huihui-Qwen3.8-27B-abliterated", "739e3c5b89849f6c238ce1e5b70008612ae42cdd")}
UA = {"User-Agent": "flashprove-weight-binding/1"}
P = (1 << 31) - 1
LARGEST = 4095


def get(url, rng, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=dict(UA, Range=rng))
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise SystemExit(f"gated or forbidden ({e.code}); stop, do not look for credentials")
            if i == tries - 1:
                raise
        except Exception:
            if i == tries - 1:
                raise
        time.sleep(3 * (i + 1))


def locate(stream_path, name):
    s = json.load(open(stream_path))
    for shard, v in s["shards"].items():
        if name in v["tensors"]:
            t = v["tensors"][name]
            return shard, v["header_len"], t
    raise KeyError(name)


def fetch(which, stream_path, name):
    repo, rev = REPOS[which]
    shard, hl, t = locate(stream_path, name)
    lo, hi = 8 + hl + t["begin"], 8 + hl + t["end"] - 1
    t0 = time.time()
    data = get(f"https://huggingface.co/{repo}/resolve/{rev}/{shard}", f"bytes={lo}-{hi}")
    sec = time.time() - t0
    assert len(data) == t["end"] - t["begin"], (name, len(data))
    return data, t, sec


def bf16_to_f32(data, shape):
    u = np.frombuffer(data, dtype="<u2").astype(np.uint32) << 16
    return u.view(np.float32).reshape(shape)


def exponent_of(largest):
    """weight_sums.py exponent_of, verbatim logic."""
    e = 12 - math.frexp(largest)[1]
    if math.ldexp(largest, e) >= LARGEST + 0.5:
        e -= 1
    return e


def to_int(v):
    largest = float(np.abs(v).max())
    assert np.isfinite(largest) and largest > 0
    e = exponent_of(largest)
    w = np.rint(v.astype(np.float64) * math.ldexp(1.0, e))
    assert np.abs(w).max() <= LARGEST
    return e, w.astype(np.int16)


def point(label, name, nvars):
    """nvars coordinates in [0, P) from SHA-256(label || name || i). Pin-independent by construction."""
    z = []
    for i in range(nvars):
        d = hashlib.sha256(b"fp-wb-point-v1" + label.encode() + b"\x00" + name.encode() + struct.pack("<I", i)).digest()
        z.append(int.from_bytes(d[:8], "little") % P)
    return z


def mle_eval(w_flat, z):
    """Multilinear extension of w (padded with zeros to 2^len(z)) at z, mod P. First coordinate = highest bit.
    Folds in place with int64 arithmetic (values < 2^31, products < 2^62)."""
    n = len(z)
    a = np.zeros(1 << n, dtype=np.int64)
    a[: w_flat.size] = w_flat.astype(np.int64) % P
    size = 1 << n
    for zi in z:
        half = size // 2
        lo, hi = a[:half], a[half:size]
        # lo + zi * (hi - lo) mod P
        diff = (hi - lo) % P
        a[:half] = (lo + (diff * zi) % P) % P
        size = half
    return int(a[0])


def analyse(name, d_s, d_a, shape):
    vs, va = bf16_to_f32(d_s, shape), bf16_to_f32(d_a, shape)
    es, ws = to_int(vs)
    ea, wa = to_int(va)
    diff_bf16 = int(np.count_nonzero(np.frombuffer(d_s, "<u2") != np.frombuffer(d_a, "<u2")))
    diff_int = int(np.count_nonzero(ws != wa)) if es == ea else None
    wsf, waf = ws.reshape(-1), wa.reshape(-1)
    nvars = max(1, (wsf.size - 1).bit_length())
    z = point("qwen3.8-27b-text", name, nvars)
    t0 = time.time()
    fs = mle_eval(wsf, z)
    tf = time.time() - t0
    fa = mle_eval(waf, z)
    max_delta = int(np.abs(wsf.astype(np.int32) - waf.astype(np.int32)).max())
    return dict(name=name, shape=list(shape), elements=int(wsf.size),
                exponent=dict(stock=es, abl=ea),
                bf16_entries_differing=diff_bf16,
                int_entries_differing=diff_int,
                int_fraction_differing=(diff_int / wsf.size) if diff_int is not None else None,
                int_sha256=dict(stock=hashlib.sha256(ws.astype("<i2").tobytes()).hexdigest(),
                                abl=hashlib.sha256(wa.astype("<i2").tobytes()).hexdigest()),
                max_abs_int_delta_same_index=max_delta,
                fingerprint_nvars=nvars,
                fingerprint=dict(stock=fs, abl=fa), fingerprint_equal=(fs == fa),
                fingerprint_seconds_one=round(tf, 2))


def run(stock_stream, abl_stream, out, names):
    res = dict(note="NOT A PROOF. Integer conversion per weight_sums.py (matrix, no norm); toy MLE fingerprint mod 2^31-1.",
               revs={k: v[1] for k, v in REPOS.items()}, tensors=[], gating=[])
    began = time.time()
    for name in names:
        d_s, t_s, sec_s = fetch("stock", stock_stream, name)
        h_s = hashlib.sha256(d_s).hexdigest()
        d_a, t_a, sec_a = fetch("abl", abl_stream, name)
        h_a = hashlib.sha256(d_a).hexdigest()
        g = dict(name=name, stock_matches_68=(h_s == t_s["sha256"]), abl_matches_68=(h_a == t_a["sha256"]),
                 fetch_seconds=dict(stock=round(sec_s, 1), abl=round(sec_a, 1)), bytes=len(d_s))
        res["gating"].append(g)
        print("fetched", json.dumps(g), flush=True)
        if not (g["stock_matches_68"] and g["abl_matches_68"]):
            continue
        r = analyse(name, d_s, d_a, tuple(t_s["shape"]))
        r["bytes_identical"] = (d_s == d_a)
        res["tensors"].append(r)
        print("analysed", json.dumps({k: r[k] for k in ("name", "exponent", "int_entries_differing", "int_fraction_differing", "fingerprint_equal", "max_abs_int_delta_same_index")}), flush=True)
        del d_s, d_a
        json.dump(res, open(out, "w"), indent=1)
    res["seconds_total"] = round(time.time() - began, 1)
    json.dump(res, open(out, "w"), indent=1)


def selftest():
    """Synthetic fixtures only (none of the registered tensors)."""
    rng = np.random.default_rng(1110)
    # MLE check against a direct sum on a tiny vector.
    w = rng.integers(-4095, 4096, size=13).astype(np.int16)
    z = point("selftest", "tiny", 4)
    direct = 0
    for i in range(16):
        val = int(w[i]) % P if i < 13 else 0
        wt = 1
        for s in range(4):
            bit = (i >> (3 - s)) & 1
            wt = wt * (z[s] if bit else (1 - z[s]) % P) % P
        direct = (direct + val * wt) % P
    assert mle_eval(w, z) == direct, "mle"
    # Conversion check: exponent rule and a one-entry change.
    v = rng.standard_normal((64, 48)).astype(np.float32) * 0.02
    bf = (v.view(np.uint32) >> 16).astype(np.uint16)
    d1 = bf.tobytes()
    bf2 = bf.copy(); bf2[3, 5] ^= 0x0040
    d2 = bf2.tobytes()
    r = analyse("synthetic", d1, d2, (64, 48))
    assert r["bf16_entries_differing"] == 1
    assert r["int_entries_differing"] in (0, 1)
    r0 = analyse("synthetic", d1, d1, (64, 48))
    assert r0["fingerprint_equal"] and r0["int_entries_differing"] == 0
    e, wi = to_int(bf16_to_f32(d1, (64, 48)))
    assert np.abs(wi).max() <= 4095 and np.abs(wi).max() >= 2048
    print("selftest ok", r["int_entries_differing"], r["fingerprint_equal"])


if __name__ == "__main__":
    if sys.argv[1] == "selftest":
        selftest()
    else:
        run(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
