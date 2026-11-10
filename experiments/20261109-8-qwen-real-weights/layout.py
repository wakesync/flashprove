#!/usr/bin/env python3
"""Q1: layout facts from the safetensors headers (as recorded by stream_hash.py: name, dtype, shape, offsets,
header length per shard), and the comparison with the shapes M1 / M1b / M2 assumed. Writes runs/layout.json.
Usage: layout.py"""
import collections, json, re
from pathlib import Path
R = Path(__file__).resolve().parent / "runs"
S = json.load(open(R / "stream-stock.json")); A = json.load(open(R / "stream-abl.json"))
P = "model.language_model."

def flat(d): return {t: dict(v, shard=s) for s, sh in d["shards"].items() for t, v in sh["tensors"].items()}
fs, fa = flat(S), flat(A)
same_names = set(fs) == set(fa)
same_meta = all(fs[t]["shape"] == fa[t]["shape"] and fs[t]["dtype"] == fa[t]["dtype"] and fs[t]["begin"] == fa[t]["begin"]
                and fs[t]["end"] == fa[t]["end"] and fs[t]["shard"] == fa[t]["shard"] for t in fs)
hdr = {s: dict(stock=S["shards"][s]["header_len"], abl=A["shards"][s]["header_len"]) for s in S["shards"]}
types = {}
for t in fs:
    m = re.match(r"model\.language_model\.layers\.(\d+)\.(linear_attn|self_attn)\.", t)
    if m: types.setdefault(int(m.group(1)), set()).add(m.group(2))
deltanet = sorted(i for i, v in types.items() if v == {"linear_attn"}); attn = sorted(i for i, v in types.items() if v == {"self_attn"})
def t(name):
    v = fs[name]; return dict(dtype=v["dtype"], shape=v["shape"], shard=v["shard"], data_offsets=[v["begin"], v["end"]], nbytes=v["nbytes"])
layer0 = {n: t(n) for n in sorted(fs) if n.startswith(P + "layers.0.")}
fam_shapes = collections.defaultdict(set)
for n, v in fs.items():
    m = re.match(r"model\.language_model\.layers\.\d+\.(.*)", n)
    if m: fam_shapes[m.group(1)].add(tuple(v["shape"]))
# what M1 / M1b / M2 (DESIGN.md D1, section 2; reference.py D; head_reference.py) assumed
assumed = {
    "linear_attn.in_proj_qkv.weight": [10240, 5120], "linear_attn.in_proj_z.weight": [6144, 5120],
    "linear_attn.in_proj_a.weight": [48, 5120], "linear_attn.in_proj_b.weight": [48, 5120],
    "linear_attn.out_proj.weight": [5120, 6144], "linear_attn.conv1d.weight": [10240, 1, 4],
    "linear_attn.A_log": [48], "linear_attn.dt_bias": [48], "linear_attn.norm.weight": [128],
    "mlp.gate_proj.weight": [17408, 5120], "mlp.up_proj.weight": [17408, 5120], "mlp.down_proj.weight": [5120, 17408],
}
shape_check = {k: dict(assumed=v, found=[list(s) for s in fam_shapes[k]], match=fam_shapes[k] == {tuple(v)}) for k, v in assumed.items()}
out = dict(
    stock=dict(repo=S["repo"], rev=S["rev"]), abl=dict(repo=A["repo"], rev=A["rev"]),
    n_tensors=len(fs), dtypes=dict(collections.Counter(v["dtype"] for v in fs.values())),
    same_names=same_names, same_dtype_shape_offsets_shard=same_meta,
    header_len_per_shard=hdr, header_len_note="abliterated headers are 24 to 32 bytes shorter: no __metadata__ {format: pt}; tensor offsets are identical",
    n_layers=len(types), deltanet_layers=deltanet, full_attention_layers=attn, first_deltanet_layer=deltanet[0],
    embedding=t(P + "embed_tokens.weight"), lm_head=t("lm_head.weight"), final_norm=t(P + "norm.weight"),
    layer0=layer0, per_layer_family_shapes={k: [list(s) for s in v] for k, v in sorted(fam_shapes.items())},
    shape_check_vs_M1_M1b_M2=shape_check, all_assumed_shapes_match=all(v["match"] for v in shape_check.values()),
)
(R / "layout.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({k: v for k, v in out.items() if k not in ("layer0", "header_len_per_shard", "per_layer_family_shapes", "shape_check_vs_M1_M1b_M2")}, indent=1))
print("all_assumed_shapes_match", out["all_assumed_shapes_match"])
