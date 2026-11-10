#!/usr/bin/env python3
"""Source-to-effective-weight inventory of Qwen3.8-27B (PR #87 review: astra item 2, opus R3 notes).

COUNTED from tensor names, not measured, not a proof. Input: PR #68's streamed name list on main
(experiments/20261109-8-qwen-real-weights/runs/stream-stock.json). No weight is read.

Every source tensor (1,199) is classified by how it reaches the integer statement:
  matrix            its own block of the weight table (a claim of R1 opens it)
  folded_norm       no block of its own: folded into the matrices that read it at conversion
                    (input_layernorm -> in_proj_* or q/k/v_proj; post_attention_layernorm ->
                    gate/up_proj; the final model.language_model.norm -> lm_head)
  cell_direct       a weight cell read by the trace, integer = RNE(2^e v) (conv1d taps)
  cell_scaled       a weight cell after a fixed constant (linear_attn.norm: sqrt(128) folded in)
  cell_derived      a weight cell after a non-linear map (A_log -> cA = RNE(2^e exp(A_log)))
  cell_fixed_F      a weight cell at the activation scale 2^F, four-digit unit (dt_bias)
  cell_qk_norm      q_norm / k_norm gains of an attention layer, kept as cells (#70 r2)
  visual / mtp      outside U1 text scope (covered by the manifest id, not by the key-file claim)
Usage: wb_inventory.py <out.json>
"""
import collections, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
stream = json.load(open(ROOT / "experiments/20261109-8-qwen-real-weights/runs/stream-stock.json"))
names = sorted(n for s in stream["shards"].values() for n in s["tensors"])

RULES = [
    (r"^model\.visual\.", "visual"),
    (r"^mtp\.", "mtp"),
    (r"\.(input_layernorm|post_attention_layernorm)\.weight$", "folded_norm"),
    (r"^model\.language_model\.norm\.weight$", "folded_norm"),
    (r"\.linear_attn\.conv1d\.weight$", "cell_direct"),
    (r"\.linear_attn\.norm\.weight$", "cell_scaled"),
    (r"\.linear_attn\.A_log$", "cell_derived"),
    (r"\.linear_attn\.dt_bias$", "cell_fixed_F"),
    (r"\.self_attn\.(q_norm|k_norm)\.weight$", "cell_qk_norm"),
    (r"\.(linear_attn\.(in_proj_qkv|in_proj_z|in_proj_a|in_proj_b|out_proj)|self_attn\.(q_proj|k_proj|v_proj|o_proj)|mlp\.(gate_proj|up_proj|down_proj))\.weight$", "matrix"),
    (r"^model\.language_model\.embed_tokens\.weight$", "matrix"),
    (r"^lm_head\.weight$", "matrix"),
]


def kind(n):
    for pat, k in RULES:
        if re.search(pat, n):
            return k
    return "UNCLASSIFIED"


by = collections.defaultdict(list)
for n in names:
    by[kind(n)].append(n)
fam = {k: dict(collections.Counter(re.sub(r"layers\.\d+\.", "L.", n) for n in v)) for k, v in by.items()}
text = [n for n in names if kind(n) not in ("visual", "mtp")]
cells = sum(len(by[k]) for k in ("cell_direct", "cell_scaled", "cell_derived", "cell_fixed_F", "cell_qk_norm"))
out = dict(
    label="COUNTED from PR #68's tensor name list; not measured, not a proof",
    tensors=len(names), text_tensors=len(text), visual=len(by["visual"]), mtp=len(by["mtp"]),
    unclassified=by.get("UNCLASSIFIED", []),
    text_by_kind={k: len(v) for k, v in sorted(by.items()) if k not in ("visual", "mtp")},
    matrix_blocks=len(by["matrix"]), weight_cell_tensors=cells, folded_norms=len(by["folded_norm"]),
    effective_text_blocks=len(by["matrix"]) + cells,
    folded_norm_names=[n for n in by["folded_norm"] if "layers." not in n],
    families=fam,
)
assert not out["unclassified"], out["unclassified"]
assert out["effective_text_blocks"] + out["folded_norms"] == out["text_tensors"]
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "families"}, indent=1))
