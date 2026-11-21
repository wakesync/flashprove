#!/usr/bin/env python3
"""Weights of one Gated DeltaNet head (layer 0, V head h) as the integer matrix M of the M3a-1 weight table.

Research only. Fetches whole layer-0 linear_attn tensors of the pinned STOCK revision by HTTP range
(the merged experiments/20261109-8-qwen-real-weights/fetch.py get()), checks each tensor's SHA-256
against the merged runs/stream-stock.json, converts by DESIGN.md 5.0 with the exponent rule of
research/weight-binding/wb_int.py, and writes M (595 x 8192, int32 little endian) to a data
directory OUTSIDE the repository. Only shapes, exponents and SHA-256 values go to the summary.

Layout of M (rows of 8192 entries, zero padded):
  row 0          the 1,666 trace-read weights at addresses 0..1665:
                 conv taps of channels q[h_k*128 + i], k[2048 + h_k*128 + i], v[4096 + h*128 + i]
                 (i < 128, 4 taps each, channel-major; h_k = h // 3: the QK head that V head h reads,
                 as real_head.py of the real-weights experiment), then 128 gains
                 (RNE(2^e sqrt(128) gain)), then cA = RNE(2^e exp(A_log[h])), then dt = RNE(2^12 dt_bias[h])
  rows 1..514    in_proj rows: q (128), k (128), v (128), z (128), a (1), b (1); 5,120 entries each
  rows 515..594  out_proj[:, h*128 .. h*128+127] as 655,360 values in column-major order
                 (value (o, c) at flat index c*5120 + o), 8,192 per row
  Total weights: 1,666 + 514 x 5,120 + 655,360 = 3,288,706 (DESIGN 3.2).

Usage:
  prepare.py real <data_dir> <summary.json>      head 0, real stock weights (registered input)
  prepare.py synthetic <data_dir> <summary.json> debug fixture: numpy seed 9101, "head 1", no real weights
"""
import hashlib, json, math, sys, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments" / "20261109-8-qwen-real-weights"))
sys.path.insert(0, str(ROOT / "research" / "weight-binding"))
import fetch as rw_fetch  # noqa: E402  (merged get())
import wb_int  # noqa: E402  (merged exponent_of)

REPO, REV = rw_fetch.REPOS["stock"]
PFX = "model.language_model.layers.0.linear_attn."
NAMES = ["A_log", "conv1d.weight", "dt_bias", "in_proj_a.weight", "in_proj_b.weight", "in_proj_qkv.weight",
         "in_proj_z.weight", "norm.weight", "out_proj.weight"]
COLS, ROWS, N_CELLS, D, DM = 8192, 595, 1666, 128, 5120
F_SCALE = 12


def stream_entry(name):
    s = json.load(open(ROOT / "experiments/20261109-8-qwen-real-weights/runs/stream-stock.json"))
    for shard, v in s["shards"].items():
        if name in v["tensors"]:
            return shard, v["header_len"], v["tensors"][name]
    raise KeyError(name)


def fetch_tensor(name, data_dir):
    path = data_dir / (name + ".bin")
    shard, hl, t = stream_entry(name)
    if not path.exists():
        lo, hi = 8 + hl + t["begin"], 8 + hl + t["end"] - 1
        data = rw_fetch.get(f"https://huggingface.co/{REPO}/resolve/{REV}/{shard}", f"bytes={lo}-{hi}")
        path.write_bytes(data)
    data = path.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    if h != t["sha256"] or len(data) != t["nbytes"]:
        raise SystemExit(f"STOP: {name} sha256 {h} differs from the merged stream hash {t['sha256']}")
    u = np.frombuffer(data, dtype="<u2").astype(np.uint32) << 16
    return u.view(np.float32).reshape(t["shape"]), dict(shape=t["shape"], dtype=t["dtype"], sha256=h, stream_sha256_match=True)


def rne(x, e):
    return np.rint(np.asarray(x, dtype=np.float64) * math.ldexp(1.0, e)).astype(np.int64)


def conv(v, scale=1.0):
    v = np.asarray(v, dtype=np.float64) * scale
    e = wb_int.exponent_of(float(np.abs(v).max()))
    w = rne(v, e)
    assert np.abs(w).max() <= 4095
    return e, w


def build(tensors, h):
    hk = h // 3
    e_conv, conv_i = conv(tensors["conv1d.weight"].reshape(10240, 4))
    e_gain, gain_i = conv(tensors["norm.weight"], math.sqrt(128))
    e_A, cA_i = conv(np.exp(tensors["A_log"].astype(np.float64)))
    dt_i = rne(tensors["dt_bias"], F_SCALE)
    qch = hk * D + np.arange(D); kch = 2048 + hk * D + np.arange(D); vch = 4096 + h * D + np.arange(D)
    ch = np.concatenate([qch, kch, vch])
    M = np.zeros((ROWS, COLS), dtype=np.int64)
    row0 = np.concatenate([conv_i[ch].reshape(-1), gain_i, [cA_i[h]], [dt_i[h]]])
    assert row0.size == N_CELLS
    M[0, :N_CELLS] = row0
    e_qkv, qkv_i = conv(tensors["in_proj_qkv.weight"])
    e_z, z_i = conv(tensors["in_proj_z.weight"])
    e_a, a_i = conv(tensors["in_proj_a.weight"])
    e_b, b_i = conv(tensors["in_proj_b.weight"])
    rows = np.concatenate([qkv_i[qch], qkv_i[kch], qkv_i[vch], z_i[h * D + np.arange(D)], a_i[h:h + 1], b_i[h:h + 1]])
    assert rows.shape == (514, DM)
    M[1:515, :DM] = rows
    e_o, o_i = conv(tensors["out_proj.weight"])
    oc = o_i[:, h * D:(h + 1) * D].T.reshape(-1)  # column-major: (o, c) at c*5120 + o
    assert oc.size == 655360 == 80 * COLS
    M[515:, :] = oc.reshape(80, COLS)
    exps = dict(conv_taps=e_conv, gain_sqrt128=e_gain, cA=e_A, dt_bias=F_SCALE, in_proj_qkv=e_qkv, in_proj_z=e_z,
                in_proj_a=e_a, in_proj_b=e_b, out_proj=e_o)
    return M, exps


def write(M, h, exps, data_dir, out, extra):
    assert M.shape == (ROWS, COLS)
    lim = 4095
    assert np.abs(M[0, :N_CELLS - 1]).max() <= lim and -(1 << 17) <= M[0, N_CELLS - 1] < (1 << 17)
    m32 = M.astype("<i4")
    (data_dir / "M.i32").write_bytes(m32.tobytes())
    cells = M[0, :N_CELLS]
    nonzero = int(np.count_nonzero(M)); total = 1666 + 514 * DM + 655360
    summary = dict(head=h, qk_head=h // 3, matrix=dict(rows=ROWS, columns=COLS), weights_in_table=total,
                   trace_cells=N_CELLS, exponents=exps,
                   M_i32_sha256=hashlib.sha256(m32.tobytes()).hexdigest(),
                   row0_cells_sha256=hashlib.sha256(cells.astype("<i8").tobytes()).hexdigest(),
                   ranges=dict(conv_taps=[int(cells[:1536].min()), int(cells[:1536].max())],
                               gains=[int(cells[1536:1664].min()), int(cells[1536:1664].max())],
                               cA=int(cells[1664]), dt=int(cells[1665]),
                               matrix_abs_max=int(np.abs(M[1:]).max())),
                   nonzero_entries=nonzero, **extra)
    json.dump(summary, open(out, "w"), indent=1)
    print(json.dumps({k: summary[k] for k in ("head", "weights_in_table", "exponents", "ranges", "M_i32_sha256")}))


def main():
    mode, data_dir, out = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    data_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if mode == "real":
        tensors, meta = {}, {}
        for n in NAMES:
            tensors[n], meta[PFX + n] = fetch_tensor(PFX + n, data_dir)
            print("checked", n, meta[PFX + n]["sha256"][:16], flush=True)
        M, exps = build(tensors, 0)
        write(M, 0, exps, data_dir, out, dict(source=dict(repo=REPO, rev=REV, tensors=meta), seconds=round(time.time() - t0, 1)))
    elif mode == "synthetic":
        rng = np.random.default_rng(9101)
        M = rng.integers(-4095, 4096, size=(ROWS, COLS)).astype(np.int64)
        M[0, N_CELLS:] = 0
        M[0, N_CELLS - 1] = int(rng.integers(-(1 << 17), 1 << 17))
        write(M, 1, dict(note="synthetic, no exponents"), data_dir, out, dict(source="synthetic numpy seed 9101, debug only"))
    else:
        raise SystemExit("mode: real | synthetic")


if __name__ == "__main__":
    main()
