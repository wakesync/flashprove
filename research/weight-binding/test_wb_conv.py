#!/usr/bin/env python3
"""Hostile and honest tests of wb_conv (conversion id, config pin, inventory). Issue #91. NOT A PROOF.

CPU only, seconds. Run from the top of the tree:
  python3 research/weight-binding/test_wb_conv.py [<out.json>]
Exit 0 iff every test passes. Inputs: PR #68's streamed per-tensor hashes of both pins and the two
pinned config.json files committed under experiments/20261111-91-conversion-id/runs/. No weight is read.
"""
import copy, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import wb_conv as wc  # noqa: E402
import wb_manifest as wbm  # noqa: E402

R68 = ROOT / "experiments/20261109-8-qwen-real-weights/runs"
R91 = ROOT / "experiments/20261111-91-conversion-id/runs"
results = []


def check(group, name, cond):
    results.append(dict(group=group, name=name, ok=bool(cond)))
    print(("PASS " if cond else "FAIL ") + group + ": " + name)


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


_, _, TS = wbm.tensors_from_stream(R68 / "stream-stock.json")
_, _, TA = wbm.tensors_from_stream(R68 / "stream-abl.json")
CS = json.load(open(R91 / "config-stock.json"))
CA = json.load(open(R91 / "config-abl.json"))
S = wc.Conversion(TS, CS)
A = wc.Conversion(TA, CA)
SID = S.id.hex()

# ---- honest
check("honest", "stock rebuild gives the same id", wc.Conversion(TS, CS).id == S.id)
check("honest", "abliterated rebuild gives the same id", wc.Conversion(TA, CA).id == A.id)
check("honest", "stock id != abliterated id", S.id != A.id)
check("honest", "configs of the two pins pin the same fields (same config pin)", S.pin == A.pin)
check("honest", "verify_conversion accepts stock under stock id", wc.verify_conversion(SID, TS, CS))
check("honest", "verify_conversion refuses abliterated under stock id", not wc.verify_conversion(SID, TA, CA))
check("honest", "all 722 stock openings verify", all(wc.verify_conv_opening(SID, S.open(b)) for b in S.names))
by_cls = {}
for b in S.names:
    by_cls.setdefault(S.leaf_objs[S.index[b]]["cls"], b)
check("honest", "9 block classes present", len(by_cls) == 9)

# blocks whose source leaves differ between pins (70 changed source tensors from #68)
changed_src = {n for n in TS if TS[n] != TA[n]}
blocks_changed = [b for b in S.names if any(s in changed_src for s, _ in S.leaf_objs[S.index[b]]["sources"])]
ref = sum(1 for b in blocks_changed if wc.verify_conv_opening(SID, A.open(b)))
check("honest", "abliterated opening refused under stock id for every block reading a changed tensor (%d)" % len(blocks_changed),
      ref == 0 and len(blocks_changed) > 0)


# ---- per class hostile leaf mutations (opening under the honest id must be refused)
def mutated_opening(block, fn):
    op = copy.deepcopy(S.open(block))
    fn(op["leaf"])
    return wc.verify_conv_opening(SID, op)


def m_step_swap(leaf):
    leaf["rule"]["step"] = wc.STEP_MATRIX if leaf["rule"]["step"] != wc.STEP_MATRIX else wc.STEP_CONV


def m_param(leaf):
    k = sorted(leaf["rule"]["params"])[0]
    leaf["rule"]["params"][k] = "tampered"


def m_src_hash(leaf):
    h = leaf["sources"][0][1]
    leaf["sources"][0][1] = ("1" if h[0] != "1" else "2") + h[1:]


def m_cls(leaf):
    leaf["cls"] = "matrix_plain" if leaf["cls"] != "matrix_plain" else "cell_conv"


MUT = {"rule step swapped": m_step_swap, "rule param changed": m_param, "own source hash changed": m_src_hash,
       "class relabelled": m_cls}
for cls, b in sorted(by_cls.items()):
    for mname, fn in MUT.items():
        check("class:" + cls, mname + " refused", not mutated_opening(b, fn))

# class-specific rule mutations
gain_g = wc.STEP_FOLDED.replace("g=RN32(1+w_norm)", "g=w_norm")
for cls in ("matrix_norm_folded", "matrix_final_norm_folded"):
    b = by_cls[cls]
    check("class:" + cls, "gain form g as stored instead of 1+w refused",
          not mutated_opening(b, lambda l: l["rule"].__setitem__("step", gain_g)))
    check("class:" + cls, "norm source dropped refused", not mutated_opening(b, lambda l: l["sources"].pop()))
    check("class:" + cls, "sources reordered refused", not mutated_opening(b, lambda l: l["sources"].reverse()))
    check("class:" + cls, "norm source hash swapped for another norm's refused",
          not mutated_opening(b, lambda l: l["sources"][1].__setitem__(1, "%064x" % 7)))
b = by_cls["matrix_final_norm_folded"]
other_norm = wc.LM + "layers.63.input_layernorm.weight"
check("class:matrix_final_norm_folded", "final norm replaced by layer-63 input norm (honest hash) refused",
      not mutated_opening(b, lambda l: l["sources"].__setitem__(1, [other_norm, S.ck.leaves[S.ck.index[other_norm]].hex()])))
check("class:cell_cA", "map exp -> identity (cA = RNE(2^e A_log)) refused",
      not mutated_opening(by_cls["cell_cA"], lambda l: l["rule"]["params"].__setitem__("map", "identity")))
check("class:cell_cA", "exp evaluated in binary32 instead of binary64 refused",
      not mutated_opening(by_cls["cell_cA"], lambda l: l["rule"]["params"].__setitem__("fmt", "binary32")))
check("class:cell_dt_bias", "F = 12 -> 14 refused",
      not mutated_opening(by_cls["cell_dt_bias"], lambda l: l["rule"]["params"].__setitem__("F", 14)))
check("class:cell_dt_bias", "class bound 2^17 -> 2^12 refused",
      not mutated_opening(by_cls["cell_dt_bias"], lambda l: l["rule"]["params"].__setitem__("cls_hi", 4096)))
check("class:cell_gated_gain", "sqrt(128) constant dropped (1.0) refused",
      not mutated_opening(by_cls["cell_gated_gain"], lambda l: l["rule"]["params"].__setitem__("sqrt_f32", wc._f32hex(1.0))))
check("class:cell_qk_norm", "gain form 1+v -> v refused",
      not mutated_opening(by_cls["cell_qk_norm"], lambda l: l["rule"].__setitem__("step", wc.STEP_QK.replace("RN32(1+v)", "v"))))
check("class:cell_conv", "kernel 4 -> 3 refused",
      not mutated_opening(by_cls["cell_conv"], lambda l: l["rule"]["params"].__setitem__("kernel", 3)))
check("class:matrix_embedding", "eres 12 -> 13 refused",
      not mutated_opening(by_cls["matrix_embedding"], lambda l: l["rule"]["params"].__setitem__("eres", 13)))

# opening-level hostile: wrong config pin / rule version / checkpoint id / index / path
b0 = S.names[0]
for fld, val in (("config_pin", "%064x" % 1), ("rule_version", "fp-qwen3.8-conv-rules-v0"),
                 ("checkpoint_id", A.ck.id.hex()), ("index", 1), ("n", 721)):
    op = S.open(b0)
    op[fld] = val
    check("opening", "%s changed refused" % fld, not wc.verify_conv_opening(SID, op))
op = S.open(b0)
op["path"] = op["path"] + [None]
check("opening", "extra path element refused", not wc.verify_conv_opening(SID, op))
op = S.open(b0)
op["extra"] = 1
check("opening", "extra field refused", not wc.verify_conv_opening(SID, op))

# ---- A12 config substitution: same tensors, one config field changed
def cfg_with(k, v):
    c = copy.deepcopy(CS)
    c["text_config"][k] = v
    return c


lt = list(CS["text_config"]["layer_types"])
lt_swapped = list(lt)
lt_swapped[0], lt_swapped[3] = lt[3], lt[0]
A12 = {
    "layer_types (layers 0 and 3 swapped)": ("layer_types", lt_swapped),
    "rms_norm_eps 1e-6 -> 1e-5": ("rms_norm_eps", 1e-05),
    "rope_theta 1e7 -> 1e6": ("rope_parameters", dict(CS["text_config"]["rope_parameters"], rope_theta=1000000)),
    "partial_rotary_factor 0.25 -> 0.5": ("partial_rotary_factor", 0.5),
    "num_attention_heads 24 -> 48 (head_dim 128)": ("num_attention_heads", 48),
    "num_key_value_heads 4 -> 8": ("num_key_value_heads", 8),
    "linear_conv_kernel_dim 4 -> 3": ("linear_conv_kernel_dim", 3),
    "hidden_act silu -> gelu": ("hidden_act", "gelu"),
    "full_attention_interval 4 -> 2": ("full_attention_interval", 2),
    "attn_output_gate true -> false": ("attn_output_gate", False),
    "mamba_ssm_dtype float32 -> bfloat16": ("mamba_ssm_dtype", "bfloat16"),
    "output_gate_type swish -> sigmoid": ("output_gate_type", "sigmoid"),
}
for label, (k, v) in A12.items():
    c = cfg_with(k, v)
    check("A12", label + " refused (same tensors)", not wc.verify_conversion(SID, TS, c))
c = copy.deepcopy(CS)
del c["text_config"]["rms_norm_eps"]
check("A12", "pinned field missing refused", not wc.verify_conversion(SID, TS, c))
c = copy.deepcopy(CS)
c["text_config"]["use_cache"] = False
check("A12", "unpinned field (use_cache) change does not change the id (pin is the function-changing set)",
      wc.verify_conversion(SID, TS, c))
check("A12", "fields pinned >= 7", len(wc.PINNED_FIELDS) >= 7)

# ---- inventory enforced in code (H3)
inv = {"text": 851, "matrix": sum(1 for o in S.leaf_objs if o["cls"] in wc.MATRIX_CLASSES),
       "cell": sum(1 for o in S.leaf_objs if o["cls"] in wc.CELL_CLASSES), "folded_norm": len(S.folded),
       "effective": len(S.names)}
check("inventory", "honest 851 = 498 + 224 + 129, 722 effective: %s" % inv, inv == wc.EXPECTED)
pick = {
    "matrix": wc.LM + "layers.5.mlp.down_proj.weight",
    "cell": wc.LM + "layers.0.linear_attn.A_log",
    "folded_norm": wc.LM + "norm.weight",
    "qk_cell": wc.LM + "layers.3.self_attn.q_norm.weight",
    "lm_head": "lm_head.weight",
    "embedding": wc.LM + "embed_tokens.weight",
}
for k, n in pick.items():
    t = dict(TS)
    del t[n]
    check("inventory", "drop one %s (%s) raises" % (k, n.split(".")[-2]),
          raises(lambda: wc.Conversion(t, CS), wc.InventoryError))
t = dict(TS)
t[wc.LM + "layers.7.mlp.extra_proj.weight"] = ("BF16", (5120, 5120), "%064x" % 3)
check("inventory", "extra unknown text tensor raises", raises(lambda: wc.Conversion(t, CS), wc.InventoryError))
t = dict(TS)
t[wc.LM + "layers.0.self_attn.q_proj.weight"] = ("BF16", (12288, 5120), "%064x" % 3)
check("inventory", "attention tensor in a DeltaNet layer raises", raises(lambda: wc.Conversion(t, CS), wc.InventoryError))
t = dict(TS)
t[wc.LM + "layers.64.mlp.down_proj.weight"] = ("BF16", (5120, 17408), "%064x" % 3)
check("inventory", "layer 64 tensor (config has 64 layers) raises", raises(lambda: wc.Conversion(t, CS), wc.InventoryError))
t = dict(TS)
n = wc.LM + "layers.0.linear_attn.in_proj_a.weight"
t[n] = (t[n][0], (49, 5120), t[n][2])
check("inventory", "shape change on in_proj_a raises", raises(lambda: wc.Conversion(t, CS), wc.ConfigError))
saved = wc.EXPECTED
wc.EXPECTED = dict(saved, matrix=497)
check("inventory", "expected table off by one raises", raises(lambda: wc.Conversion(TS, CS), wc.InventoryError))
wc.EXPECTED = saved
# visual / mtp are covered by the checkpoint id but not by the conversion blocks
t = dict(TS)
vn = sorted(n for n in TS if n.startswith("model.visual."))[0]
t[vn] = (t[vn][0], t[vn][1], "%064x" % 9)
check("scope", "visual tensor change changes the conversion id via the checkpoint id",
      not wc.verify_conversion(SID, t, CS))
check("scope", "no block for visual / mtp", not any(b.startswith(("model.visual.", "mtp.")) for b in S.names))

ok = all(r["ok"] for r in results)
print("%d / %d PASS" % (sum(r["ok"] for r in results), len(results)))
if len(sys.argv) > 1:
    out = dict(label="hash-level tests of wb_conv, NOT A PROOF", n=len(results), passed=sum(r["ok"] for r in results),
               stock_conversion_id=SID, abl_conversion_id=A.id.hex(), stock_checkpoint_id=S.ck.id.hex(),
               abl_checkpoint_id=A.ck.id.hex(), config_pin=S.pin.hex(), blocks_reading_changed_tensor=len(blocks_changed),
               changed_source_tensors=len(changed_src), inventory=inv, results=results)
    with open(sys.argv[1], "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
sys.exit(0 if ok else 1)
