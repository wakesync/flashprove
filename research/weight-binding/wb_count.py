#!/usr/bin/env python3
"""Counted (not measured) costs of the weight-binding design, from numbers on main.

Every output is a count from published shapes, or arithmetic on a measured number that is cited.
Nothing here is a measurement. Writes experiments/20261110-36-weight-binding/runs/counted.json, or the
path given as the first argument (used by the PR #87 rerun so the committed file is not rewritten).

Sources:
  shapes: research/operators/qwen_m3/count_m3.py (Q, weights()) at main; #68 runs/stream-stock.json
  M3a-head weight cells (1,666 per V head) and tie layout: #70 DESIGN.md 6.2, count_m3.py wcells
  packed trace volume per token (95,057,841 entries): #70 RESULTS.md H5.2
  H3 fingerprint rate: this PR, runs/h2h3-int.json (toy prime, numpy, one process)
"""
import json, math, sys
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research/operators/qwen_m3"))
import count_m3 as cm  # noqa: E402

Q = cm.Q
W = cm.weights()
E = ROOT / "experiments/20261110-36-weight-binding/runs"

stream = json.load(open(ROOT / "experiments/20261109-8-qwen-real-weights/runs/stream-stock.json"))
names = [n for s in stream["shards"].values() for n in s["tensors"]]
text = [n for n in names if n.startswith("model.language_model.") or n == "lm_head.weight"]

# Weight cells read by the trace per DeltaNet layer (DESIGN 6.2: conv taps, gated-norm gain, cA, dt_bias).
conv_cells = Q["in_proj_qkv"] * Q["conv_taps"]          # 10,240 x 4
gain_cells = Q["D"]                                        # 128, shared by the V heads
ca_cells = Q["v_heads"]                                    # 48
dt_cells = Q["v_heads"]                                    # 48
per_dn_layer = conv_cells + gain_cells + ca_cells + dt_cells
attn_gain_cells = 2 * Q["attn_dh"]                         # q and k RMSNorm gains, 256 each (if retained as cells)
cells_model = Q["deltanet_layers"] * per_dn_layer + Q["attention_layers"] * attn_gain_cells
keys_model = 3 * cells_model                               # arm B: 3 keys per cell
rels_model = 2 * cells_model + math.ceil((cells_model + 1) / 256)  # class relations + 256-term tie sums (per window)

packed_per_token = 95_057_841                              # #70 RESULTS H5.2, counted
windows = {T: packed_per_token * T for T in (16, 64, 1024)}

# H3 toy rate (this PR) -> CPU time to fingerprint every committed integer once. EXTRAPOLATED.
h = json.load(open(E / "h2h3-int.json"))
el = sum(t["elements"] for t in h["tensors"])
sec = sum(t["fingerprint_seconds_one"] for t in h["tensors"])
rate = el / sec

# U2 link: probability that a sampled statement touches a layer the abliteration changed (17..51).
L, lo, hi = 64, 17, 51
changed = hi - lo + 1
unchanged = L - changed
p_layers = {k: 1 - comb(unchanged, k) / comb(L, k) for k in (1, 2, 4, 8)}
def block_hit(b):
    starts = range(0, L - b + 1)
    return sum(1 for s in starts if s <= hi and s + b - 1 >= lo) / len(starts)
p_blocks = {b: block_hit(b) for b in (1, 4, 16)}

out = dict(
    label="COUNTED from published shapes and main's counts; the fingerprint time is EXTRAPOLATED from a toy numpy run. Nothing here is a measurement of a proof.",
    tensors_in_checkpoint=len(names), text_tensors=len(text),
    committed_integers=W["total"], committed_bytes=W["bytes_int16_plus_emb32"],
    manifest=dict(leaves=len(names), path_siblings=math.ceil(math.log2(len(names))),
                  opening_bytes_approx=32 * math.ceil(math.log2(len(names))) + 32 + 200,
                  note="hash-level manifest of this PR; opening = sibling path + leaf fields"),
    weight_cells=dict(per_deltanet_layer=per_dn_layer, conv=conv_cells, gain=gain_cells, cA=ca_cells, dt_bias=dt_cells,
                      attention_qk_gain_cells_per_layer=attn_gain_cells, whole_model=cells_model,
                      keys_whole_model=keys_model, relations_whole_model=rels_model,
                      m3a_one_v_head=W["m3a_weight_cells_read_by_trace"],
                      note="read once per window (#70 count_m3 'once'); arm B 3 keys + 2 relations per cell + one batched tie split into 256-term sums; table-side opening rides in the matmul batch"),
    tie_share_of_window=dict((f"T{T}", keys_model / v) for T, v in windows.items()),
    packed_entries_per_token=packed_per_token,
    fingerprint_toy=dict(elements=el, seconds=round(sec, 2), elements_per_second=round(rate),
                         whole_model_minutes_extrapolated=round(W["total"] / rate / 60, 1),
                         note="numpy, one process, toy prime 2^31-1, shared loaded host; a C or GPU field kernel would differ"),
    commit_minutes_extrapolated_70=2.6176491262409223,
    u2_layer_sampling=dict(changed_layers=changed, of=L,
                           p_touch_changed_k_distinct_layers=p_layers,
                           p_touch_changed_contiguous_block=p_blocks,
                           note="touching a changed layer is necessary, not sufficient: the statement must also open that layer's down_proj / out_proj / o_proj claims against the bound table and bind its input"),
)
out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else E / "counted.json"
json.dump(out, open(out_path, "w"), indent=1)
print(json.dumps(out, indent=1))
