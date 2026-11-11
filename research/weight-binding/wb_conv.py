#!/usr/bin/env python3
"""Conversion id of Qwen3.8-27B (DESIGN.md 2.0 object 2), with the config pin (attack A12) and the
851 = 498 + 224 + 129 inventory enforced in code. Issue #91, follow-up to PR #87.

HASH LEVEL ONLY. THIS IS NOT A PROOF. No weight is read. Inputs: the per-tensor stream file of PR #68
(name, dtype, shape, SHA-256 of the BF16 bytes) and the pin's config.json.

Order (DESIGN 2.0): checkpoint id (wb_manifest, all 1,199 tensors) -> conversion id. The conversion id
hashes, in order: the checkpoint id; the rule version string; the config pin; the number of blocks;
the Merkle root over one leaf per effective text block (722), sorted by block name.

Leaf of block b (v1):
  H(0x00 || "fp-wb-conv-leaf-v1" || len||canonical-json(leaf)), leaf = {
    block: name, cls: tensor class, sources: [[source name, checkpoint-leaf hash hex], ...] in the order
    the rule reads them, rule: {step: string, params: {...}} }
Node: H(0x01 || "fp-wb-conv-node-v1" || l || r), odd last node promoted (as wb_manifest).
Config pin: H("fp-wb-config-v1" || len||canonical-json(pinned text_config fields)), floats as binary64 hex.
Conversion id: H("fp-wb-conv-id-v1" || checkpoint id || len||rule version || config pin || n (8 LE) || root).

What a leaf does NOT carry (open, DESIGN 2.0 lists them): the exponent e_b and int_sha256_b. They are
functions of the source bytes (bound by the checkpoint-leaf hashes) and the rule (bound by the rule step
and params); computing them needs all 55.6 GB per pin. A leaf v2 can add them.

Usage:
  wb_conv.py build <stream.json> <config.json> <out.json>
"""
import hashlib, json, math, re, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wb_manifest as wbm  # noqa: E402

RULE_VERSION = "fp-qwen3.8-conv-rules-v1"
F = 12  # activation scale exponent, the open parameter of #70 (F = 12 candidate)
LM = "model.language_model."


class InventoryError(Exception):
    pass


class ConfigError(Exception):
    pass


def _h(*p):
    return wbm._h(*p)


def _lp(b):
    return wbm._lp(b)


def _f32hex(x):
    return struct.pack("<f", x)[::-1].hex()


def _canon(obj):
    """Canonical JSON: sorted keys, no spaces, floats replaced by {"f64": hex} so no repr ambiguity."""
    def fix(o):
        if isinstance(o, bool) or o is None or isinstance(o, (int, str)):
            return o
        if isinstance(o, float):
            return {"f64": struct.pack(">d", o).hex()}
        if isinstance(o, list):
            return [fix(x) for x in o]
        if isinstance(o, dict):
            return {k: fix(v) for k, v in o.items()}
        raise TypeError(type(o))
    return json.dumps(fix(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


# ---------------------------------------------------------------- config pin (A12)
PINNED_FIELDS = [
    "attn_output_gate", "full_attention_interval", "head_dim", "hidden_act", "hidden_size",
    "intermediate_size", "layer_types", "linear_conv_kernel_dim", "linear_key_head_dim",
    "linear_num_key_heads", "linear_num_value_heads", "linear_value_head_dim", "mamba_ssm_dtype",
    "num_attention_heads", "num_hidden_layers", "num_key_value_heads", "output_gate_type",
    "partial_rotary_factor", "rms_norm_eps", "rope_parameters", "tie_word_embeddings", "vocab_size",
]


def config_fields(cfg):
    tc = cfg.get("text_config", cfg)
    missing = [k for k in PINNED_FIELDS if k not in tc]
    if missing:
        raise ConfigError("config lacks pinned fields %s" % missing)
    return {k: tc[k] for k in PINNED_FIELDS}


def config_pin(fields):
    return _h(b"fp-wb-config-v1", _lp(_canon(fields)))


# ---------------------------------------------------------------- inventory + rules
COMMON = {"round": "RNE", "int": "two's complement"}
STEP_MATRIX = "e=max{e: RNE(2^e max|v|)<=4095}; w=RNE(2^e v); int16; v=BF16->binary32 exact"
STEP_FOLDED = ("g=RN32(1+w_norm) (zero-centred RMSNorm, binary32); gamma=RN32(g*c); p=RN32(gamma*v) "
               "per input column; e=max{e: RNE(2^e max|p|)<=4095}; w=RNE(2^e p); int16")
STEP_EMBED = "w=RNE(2^eres v); eres=F; int32 four-digit unit"
STEP_CONV = "e=max{e: RNE(2^e max|v|)<=4095}; w=RNE(2^e v); weight cell class [-4096,4095]"
STEP_GATED = "p=RN32(v*sqrt(128)) (gain as stored, no 1+w); e=max{e: RNE(2^e max|p|)<=4095}; w=RNE(2^e p); cell"
STEP_CA = "a=RN64(exp(RN64(A_log))) binary64 exp; e_A=max{e: RNE(2^e max|a|)<=4095}; cA=RNE(2^e_A a); s_A=e_A; cell"
STEP_DT = "dt=RNE(2^F v); class [-2^(F+5),2^(F+5)); four-digit unit"
STEP_QK = "g=RN32(1+v) (zero-centred RMSNorm, binary32); e=max{e: RNE(2^e max|g|)<=4095}; w=RNE(2^e g); cell"

CELL_CLASSES = ("cell_conv", "cell_gated_gain", "cell_cA", "cell_dt_bias", "cell_qk_norm")
MATRIX_CLASSES = ("matrix_plain", "matrix_norm_folded", "matrix_final_norm_folded", "matrix_embedding")
EXPECTED = {"text": 851, "matrix": 498, "cell": 224, "folded_norm": 129, "effective": 722}


def _rule(step, **params):
    return {"step": step, "params": dict(COMMON, **params)}


def classify(names, fields):
    """Return (blocks, folded_norms). Raises InventoryError unless the text tensors are exactly what the
    pinned config implies and split 851 = 498 + 224 + 129. blocks: name -> (cls, [source names], rule)."""
    lt = fields["layer_types"]
    L = fields["num_hidden_layers"]
    if not isinstance(lt, list) or len(lt) != L or any(t not in ("linear_attention", "full_attention") for t in lt):
        raise ConfigError("layer_types not a list of %d known types" % L)
    text = sorted(n for n in names if n.startswith(LM) or n == "lm_head.weight")
    present = set(text)
    blocks, folded, expected_names = {}, [], set()

    def need(n):
        expected_names.add(n)
        if n not in present:
            raise InventoryError("missing tensor %s" % n)
        return n

    c1 = _f32hex(1.0)
    for i, t in enumerate(lt):
        p = LM + "layers.%d." % i
        inn, post = need(p + "input_layernorm.weight"), need(p + "post_attention_layernorm.weight")
        folded += [inn, post]
        if t == "linear_attention":
            for m in ("in_proj_qkv", "in_proj_z", "in_proj_a", "in_proj_b"):
                n = need(p + "linear_attn.%s.weight" % m)
                blocks[n] = ("matrix_norm_folded", [n, inn], _rule(STEP_FOLDED, c_f32=c1, norm_role="input_layernorm"))
            n = need(p + "linear_attn.out_proj.weight")
            blocks[n] = ("matrix_plain", [n], _rule(STEP_MATRIX))
            n = need(p + "linear_attn.conv1d.weight")
            blocks[n] = ("cell_conv", [n], _rule(STEP_CONV, kernel=fields["linear_conv_kernel_dim"]))
            n = need(p + "linear_attn.norm.weight")
            blocks[n] = ("cell_gated_gain", [n], _rule(STEP_GATED, width=fields["linear_value_head_dim"],
                                                         sqrt_f32=_f32hex(math.sqrt(fields["linear_value_head_dim"]))))
            n = need(p + "linear_attn.A_log")
            blocks[n] = ("cell_cA", [n], _rule(STEP_CA, map="exp", fmt="binary64"))
            n = need(p + "linear_attn.dt_bias")
            blocks[n] = ("cell_dt_bias", [n], _rule(STEP_DT, F=F, cls_lo=-(1 << (F + 5)), cls_hi=1 << (F + 5)))
        else:
            for m in ("q_proj", "k_proj", "v_proj"):
                n = need(p + "self_attn.%s.weight" % m)
                blocks[n] = ("matrix_norm_folded", [n, inn], _rule(STEP_FOLDED, c_f32=c1, norm_role="input_layernorm"))
            n = need(p + "self_attn.o_proj.weight")
            blocks[n] = ("matrix_plain", [n], _rule(STEP_MATRIX))
            for m in ("q_norm", "k_norm"):
                n = need(p + "self_attn.%s.weight" % m)
                blocks[n] = ("cell_qk_norm", [n], _rule(STEP_QK))
        for m in ("gate_proj", "up_proj"):
            n = need(p + "mlp.%s.weight" % m)
            blocks[n] = ("matrix_norm_folded", [n, post], _rule(STEP_FOLDED, c_f32=c1, norm_role="post_attention_layernorm"))
        n = need(p + "mlp.down_proj.weight")
        blocks[n] = ("matrix_plain", [n], _rule(STEP_MATRIX))
    fn = need(LM + "norm.weight")
    folded.append(fn)
    n = need("lm_head.weight")
    blocks[n] = ("matrix_final_norm_folded", [n, fn], _rule(STEP_FOLDED, c_f32=c1, norm_role="final_norm"))
    n = need(LM + "embed_tokens.weight")
    blocks[n] = ("matrix_embedding", [n], _rule(STEP_EMBED, eres=F))

    extra = present - expected_names
    if extra:
        raise InventoryError("text tensors the config does not account for: %s" % sorted(extra)[:5])
    nm = sum(1 for c, _, _ in blocks.values() if c in MATRIX_CLASSES)
    nc = sum(1 for c, _, _ in blocks.values() if c in CELL_CLASSES)
    got = {"text": len(text), "matrix": nm, "cell": nc, "folded_norm": len(folded), "effective": len(blocks)}
    if got != EXPECTED:
        raise InventoryError("inventory %s != expected %s" % (got, EXPECTED))
    used = {s for _, srcs, _ in blocks.values() for s in srcs[1:]}
    unused = set(folded) - used
    if unused:
        raise InventoryError("folded norms read by no block: %s" % sorted(unused))
    if set(folded) & set(blocks):
        raise InventoryError("a folded norm has its own block")
    return blocks, folded


def check_shapes(tensors, fields):
    """The config must be consistent with the tensor shapes it governs (A12: a config that changes
    head counts / widths / conv width / vocab must disagree with the bytes)."""
    H, I, V = fields["hidden_size"], fields["intermediate_size"], fields["vocab_size"]
    hd, nq, nkv = fields["head_dim"], fields["num_attention_heads"], fields["num_key_value_heads"]
    dk, dv = fields["linear_key_head_dim"], fields["linear_value_head_dim"]
    nk, nv, K = fields["linear_num_key_heads"], fields["linear_num_value_heads"], fields["linear_conv_kernel_dim"]
    qmul = 2 if fields["attn_output_gate"] else 1
    exp = {"embed_tokens.weight": [V, H], "norm.weight": [H]}
    for i, t in enumerate(fields["layer_types"]):
        p = "layers.%d." % i
        exp[p + "input_layernorm.weight"] = [H]
        exp[p + "post_attention_layernorm.weight"] = [H]
        exp[p + "mlp.gate_proj.weight"] = [I, H]
        exp[p + "mlp.up_proj.weight"] = [I, H]
        exp[p + "mlp.down_proj.weight"] = [H, I]
        if t == "linear_attention":
            conv = 2 * nk * dk + nv * dv
            exp.update({p + "linear_attn.in_proj_qkv.weight": [conv, H], p + "linear_attn.in_proj_z.weight": [nv * dv, H],
                        p + "linear_attn.in_proj_a.weight": [nv, H], p + "linear_attn.in_proj_b.weight": [nv, H],
                        p + "linear_attn.out_proj.weight": [H, nv * dv], p + "linear_attn.conv1d.weight": [conv, 1, K],
                        p + "linear_attn.norm.weight": [dv], p + "linear_attn.A_log": [nv], p + "linear_attn.dt_bias": [nv]})
        else:
            exp.update({p + "self_attn.q_proj.weight": [qmul * nq * hd, H], p + "self_attn.k_proj.weight": [nkv * hd, H],
                        p + "self_attn.v_proj.weight": [nkv * hd, H], p + "self_attn.o_proj.weight": [H, nq * hd],
                        p + "self_attn.q_norm.weight": [hd], p + "self_attn.k_norm.weight": [hd]})
    full = {LM + k: v for k, v in exp.items()}
    full["lm_head.weight"] = [V, H]
    for n, s in full.items():
        if n not in tensors:
            raise InventoryError("missing tensor %s" % n)
        if list(tensors[n][1]) != s:
            raise ConfigError("config implies %s shape %s, tensor has %s" % (n, s, list(tensors[n][1])))


# ---------------------------------------------------------------- the id
def leaf_obj(name, cls, srcs, rule, ck_leaf):
    return {"block": name, "cls": cls, "sources": [[s, ck_leaf[s]] for s in srcs], "rule": rule}


def conv_leaf_hash(obj):
    return _h(b"\x00", b"fp-wb-conv-leaf-v1", _lp(_canon(obj)))


def conv_node_hash(a, b):
    return _h(b"\x01", b"fp-wb-conv-node-v1", a, b)


def conv_levels(leaves):
    lv = [leaves]
    while len(lv[-1]) > 1:
        cur = lv[-1]
        lv.append([conv_node_hash(cur[i], cur[i + 1]) if i + 1 < len(cur) else cur[i] for i in range(0, len(cur), 2)])
    return lv


def conversion_id(ck_id, pin, n, root, rule_version=RULE_VERSION):
    return _h(b"fp-wb-conv-id-v1", ck_id, _lp(rule_version.encode()), pin, struct.pack("<Q", n), root)


class Conversion:
    def __init__(self, tensors, cfg):
        self.ck = wbm.Manifest(tensors)
        ck_leaf = {n: self.ck.leaves[i].hex() for n, i in self.ck.index.items()}
        self.fields = config_fields(cfg)
        self.pin = config_pin(self.fields)
        blocks, self.folded = classify(list(tensors), self.fields)
        check_shapes(tensors, self.fields)
        self.names = sorted(blocks)
        self.leaf_objs = [leaf_obj(b, *blocks[b], ck_leaf) for b in self.names]
        self.leaves = [conv_leaf_hash(o) for o in self.leaf_objs]
        self.lv = conv_levels(self.leaves)
        self.root = self.lv[-1][0]
        self.id = conversion_id(self.ck.id, self.pin, len(self.names), self.root)
        self.index = {b: i for i, b in enumerate(self.names)}

    def open(self, block):
        i = self.index[block]
        path, j = [], i
        for cur in self.lv[:-1]:
            s = j ^ 1
            path.append(cur[s].hex() if s < len(cur) else None)
            j //= 2
        return dict(checkpoint_id=self.ck.id.hex(), config_pin=self.pin.hex(), rule_version=RULE_VERSION,
                    n=len(self.names), index=i, leaf=self.leaf_objs[i], path=path)

    def to_json(self):
        return dict(note="conversion id (DESIGN 2.0 object 2), hash level, NOT A PROOF", rule_version=RULE_VERSION,
                    checkpoint_id=self.ck.id.hex(), config_fields=self.fields, config_pin=self.pin.hex(),
                    n_blocks=len(self.names), root=self.root.hex(), conversion_id=self.id.hex(),
                    folded_norms=sorted(self.folded), blocks=self.leaf_objs)


EXPECTED_STEP = {"matrix_plain": STEP_MATRIX, "matrix_norm_folded": STEP_FOLDED, "matrix_final_norm_folded": STEP_FOLDED,
                 "matrix_embedding": STEP_EMBED, "cell_conv": STEP_CONV, "cell_gated_gain": STEP_GATED,
                 "cell_cA": STEP_CA, "cell_dt_bias": STEP_DT, "cell_qk_norm": STEP_QK}
EXPECTED_NSRC = {"matrix_norm_folded": 2, "matrix_final_norm_folded": 2}


def leaf_well_formed(obj):
    """Structural check of a block leaf (the verifier's own rule table): class known, step = the class's
    step, source count right, first source = the block itself, hashes canonical hex."""
    if not isinstance(obj, dict) or set(obj) != {"block", "cls", "sources", "rule"}:
        return "leaf fields"
    c = obj["cls"]
    if c not in EXPECTED_STEP:
        return "unknown class"
    r = obj["rule"]
    if not isinstance(r, dict) or set(r) != {"step", "params"} or r["step"] != EXPECTED_STEP[c]:
        return "rule step is not the class's step"
    s = obj["sources"]
    if not isinstance(s, list) or len(s) != EXPECTED_NSRC.get(c, 1):
        return "source count"
    if any(not (isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and wbm._is_hex32(x[1])) for x in s):
        return "source encoding"
    if s[0][0] != obj["block"]:
        return "first source is not the block's own tensor"
    return None


def verify_conv_opening(held_id_hex, op):
    """True iff the block-leaf opening is canonical and recomputes the verifier-held conversion id."""
    keys = {"checkpoint_id", "config_pin", "rule_version", "n", "index", "leaf", "path"}
    if not isinstance(op, dict) or set(op) != keys:
        return False
    if leaf_well_formed(op["leaf"]) is not None:
        return False
    if not (wbm._is_hex32(op["checkpoint_id"]) and wbm._is_hex32(op["config_pin"]) and isinstance(op["rule_version"], str)):
        return False
    shape = dict(index=op["index"], n=op["n"], name="x", dtype="x", shape=[], sha256="0" * 64, path=op["path"])
    if wbm.canonical_opening(shape) is not None:
        return False
    cur, j = conv_leaf_hash(op["leaf"]), op["index"]
    for sib in op["path"]:
        if sib is not None:
            s = bytes.fromhex(sib)
            cur = conv_node_hash(cur, s) if j % 2 == 0 else conv_node_hash(s, cur)
        j //= 2
    cid = conversion_id(bytes.fromhex(op["checkpoint_id"]), bytes.fromhex(op["config_pin"]), op["n"], cur, op["rule_version"])
    return cid.hex() == held_id_hex


def verify_conversion(held_id_hex, tensors, cfg):
    """Whole recompute: True iff (tensors, cfg) build without inventory/config errors and give the held id."""
    try:
        return Conversion(tensors, cfg).id.hex() == held_id_hex
    except (InventoryError, ConfigError):
        return False


def build(stream, cfg_path, out):
    repo, rev, t = wbm.tensors_from_stream(stream)
    cfg = json.load(open(cfg_path))
    c = Conversion(t, cfg)
    d = c.to_json()
    d.update(repo=repo, rev=rev, config_sha256=hashlib.sha256(open(cfg_path, "rb").read()).hexdigest())
    with open(out, "w") as f:
        json.dump(d, f, indent=1, sort_keys=True)
        f.write("\n")
    print(repo, rev, "checkpoint", c.ck.id.hex(), "conversion", c.id.hex(), "blocks", len(c.names))


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "build":
        build(*sys.argv[2:])
    else:
        print(__doc__)
        sys.exit(2)
