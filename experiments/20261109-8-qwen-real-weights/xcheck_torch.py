#!/usr/bin/env python3
"""Cross-check of the float64 reference in real_head.py against the Transformers source itself.

The functions l2norm, causal_conv1d_fn and torch_recurrent_gated_delta_rule, and the bodies of the
zero-centred RMSNorm and RMSNormGated forwards, are taken VERBATIM from modeling_qwen3_5.py (pinned
e540ae45, sha256 checked) with ast (decorators dropped) and executed with torch on the layer-0 path,
(a) in float64, compared with real_head.run_float, and (b) in the checkpoint dtype (BF16 weights and
activations, the reference's own FP32 upcasts), which is the publisher's eager CPU numerics, compared
with the float64 path. Prompts: all 10. Writes runs/xcheck-torch.json.
Usage: xcheck_torch.py <modeling_qwen3_5.py> <cache_dir> <ckpt>"""
import ast, hashlib, json, sys
import numpy as np
import torch
import torch.nn.functional as Fn
import real_head as RH

SRC_SHA = "41a55adcfaebf92a762de7ca1c5c456310d3e03c64d4413a90ccf098c00dc6d8"

def load_src(path):
    src = open(path).read(); assert hashlib.sha256(src.encode()).hexdigest() == SRC_SHA
    tree = ast.parse(src); ns = dict(torch=torch, F=Fn, ACT2FN={"silu": Fn.silu}, nn=torch.nn)
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("l2norm", "causal_conv1d_fn", "torch_recurrent_gated_delta_rule"):
            node.decorator_list = []; keep.append(node)
        if isinstance(node, ast.ClassDef) and node.name in ("Qwen3_5RMSNormGated", "Qwen3_5RMSNorm"):
            node.decorator_list = []; node.bases = [ast.Attribute(value=ast.Name("nn", ast.Load()), attr="Module", ctx=ast.Load())]; keep.append(node)
    mod = ast.Module(body=keep, type_ignores=[]); ast.fix_missing_locations(mod)
    exec(compile(mod, path, "exec"), ns)
    return ns

def layer0(ns, L, x, dtype):
    """Qwen3_5DecoderLayer input_layernorm + Qwen3_5GatedDeltaNet.forward up to self.norm (no out_proj), batch 1,
    following L536-646 line by line with the no-cache branch (causal_conv1d_fn) and the recurrent rule."""
    t = lambda a: torch.tensor(a, dtype=dtype)
    ln = ns["Qwen3_5RMSNorm"](5120, eps=1e-6); ln.weight = torch.nn.Parameter(t(L["input_layernorm.weight"]))
    hs = ln(t(x)[None])                                                  # (1, T, 5120)
    lin = lambda name, h: h @ t(L[f"linear_attn.{name}.weight"]).T
    mixed = lin("in_proj_qkv", hs).transpose(1, 2)
    z = lin("in_proj_z", hs).reshape(1, hs.shape[1], -1, 128)
    b = lin("in_proj_b", hs); a = lin("in_proj_a", hs)
    mixed = ns["causal_conv1d_fn"](mixed, t(L["linear_attn.conv1d.weight"]).squeeze(1), None, activation="silu").transpose(1, 2)
    q, k, v = torch.split(mixed, [2048, 2048, 6144], dim=-1)
    q = q.reshape(1, -1, 16, 128); k = k.reshape(1, -1, 16, 128); v = v.reshape(1, -1, 48, 128)
    beta = b.sigmoid()
    g = -t(L["linear_attn.A_log"]).float().exp() * Fn.softplus(a.float() + t(L["linear_attn.dt_bias"]))
    q = q.repeat_interleave(3, dim=2); k = k.repeat_interleave(3, dim=2)
    if dtype == torch.float64: g = g.double()
    core, _ = ns["torch_recurrent_gated_delta_rule"](q, k, v, g=g, beta=beta, initial_state=None, output_final_state=False, use_qk_l2norm_in_kernel=True)
    nm = ns["Qwen3_5RMSNormGated"](128, eps=1e-6); nm.weight = torch.nn.Parameter(t(L["linear_attn.norm.weight"]))
    o = core.reshape(-1, 128); y = nm(o, z.reshape(-1, 128))
    T = hs.shape[1]
    return o.double().numpy().reshape(T, 48, 128), y.double().numpy().reshape(T, 48, 128)

def rel(a, b): return float(np.linalg.norm(a - b) / np.linalg.norm(b))

def main():
    ns = load_src(sys.argv[1]); L, emb = RH.load_layer(sys.argv[2], sys.argv[3])
    prompts = json.load(open(RH.HERE / "prompts.json"))["prompts"]; out = []
    with torch.no_grad():
        for p in prompts:
            ids = p["token_ids"]
            x, h, qkv, z, a, b = RH.inproj(L, emb, ids)
            xq, xk, xv, ar, br, zz, Wc, A, dtb, gain = RH.heads(L, qkv, z, a, b)
            ours = list(RH.run_float(xq, xk, xv, ar, br, zz, Wc, A, dtb, gain))
            of = np.stack([o for _, o, _ in ours]); yf = np.stack([y for _, _, y in ours])
            X = np.stack([emb[t_] for t_ in ids])
            o64, y64 = layer0(ns, L, X, torch.float64)
            o16, y16 = layer0(ns, L, X, torch.bfloat16)
            per_head = [rel(y16[:, hh], y64[:, hh]) for hh in range(48)]
            row = dict(prompt=p["id"], T=len(ids), f64_vs_ours_max_abs_y=float(np.abs(y64 - yf).max()), f64_vs_ours_max_abs_o=float(np.abs(o64 - of).max()),
                       f64_vs_ours_rel_y=rel(yf, y64), bf16_eager_rel_y_vs_f64=rel(y16, y64), bf16_eager_rel_o_vs_f64=rel(o16, o64),
                       bf16_eager_rel_y_per_head=dict(median=float(np.median(per_head)), max=float(np.max(per_head))))
            out.append(row); print(json.dumps(row), flush=True)
    json.dump(dict(source_sha256=SRC_SHA, torch=torch.__version__, ckpt=sys.argv[3], rows=out), open(RH.HERE / "runs" / "xcheck-torch.json", "w"), indent=1)

if __name__ == "__main__": main()
