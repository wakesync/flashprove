#!/usr/bin/env python3
# Scores honest and attacked replies on the small synthetic clipped-gap example, for one prompt seed.
# Pre-registration: PREREG.md in this directory (committed before this file).
#
# usage: score_seed.py PAIR_DIRECTORY SEED OUT.json [--threads N]
#   PAIR_DIRECTORY: what `python3 -m integer_model_vllm.example small_float_pair --directory D` made.
#   Run with integrations/vllm/integer_model on PYTHONPATH.
#
# Writes, per reply, the list of costs (logit gap + 2^sh) at the reply's positions, in the window of a
# proof (prompt + reply + zeros up to T), as try_limits.py's meets() computes them. A window that fails
# a range condition is stored as null (the honest prover makes no proof for it). Nothing here is proved.
import argparse
import json
import random
import time
from pathlib import Path

import torch
import transformers

import integer_model

PROMPT_TOKENS, REPLY_TOKENS, REPLIES = 16, 32, 128
KS = (1, 2, 4, 8, 16)

ap = argparse.ArgumentParser()
ap.add_argument("pair", type=Path)
ap.add_argument("seed", type=int)
ap.add_argument("out", type=Path)
ap.add_argument("--threads", type=int, default=4)
ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float32"])
a = ap.parse_args()
torch.set_num_threads(a.threads)
t_start = time.time()

model = integer_model.load_from_folder(a.pair / "model", "cpu")
policy = dict(l.split(maxsplit=1) for l in (a.pair / "model" / "policy.txt").read_text().splitlines())
own = 1 << int(policy["sh"])
T, end_token = model.parameters.T, model.parameters.V - 1
floats = transformers.AutoModelForCausalLM.from_pretrained(
    (a.pair / "float_model").resolve(strict=True), local_files_only=True,
    attn_implementation="eager", dtype=getattr(torch, a.dtype)).eval()

draw = random.Random(a.seed)  # seed 2026 = try_limits.py's own draw of prompts
prompts = [[draw.randrange(end_token) for _ in range(PROMPT_TOKENS)] for _ in range(REPLIES)]


def decode(some):
    seqs = [list(p) for p in some]
    with torch.no_grad():
        for _ in range(REPLY_TOKENS):
            ch = floats(torch.tensor(seqs)).logits[:, -1].float().argmax(dim=1).tolist()
            for s, c in zip(seqs, ch):
                s.append(c)
    return seqs


t0 = time.time()
seqs = decode(prompts)
with torch.no_grad():
    fp_second = floats(torch.tensor(seqs)).logits.float().topk(2, dim=2).indices[:, :, 1].tolist()
whole = [s[PROMPT_TOKENS:] for s in seqs]
replies = [r[: r.index(end_token) + 1] if end_token in r else r for r in whole]
t_decode = time.time() - t0


def window_pass(prompt, reply, want_logits=False):
    """Costs at the reply's positions, or None if a range condition fails; with want_logits also the
    integer model's logits at those positions (int64, n x V)."""
    w = prompt + reply + [0] * (T - len(prompt) - len(reply))
    kept = {}

    def rec(name, layer, t):
        if name == "lam":
            kept["lam"] = t

    seq = model.new_sequence()
    try:
        _, gaps = model.extend(seq, w, gap_for=w[1:] + [0], record=rec if want_logits else None)
    except integer_model.RangeConditionFailed:
        return (None, None) if want_logits else None
    finally:
        model.free(seq)
    first = len(prompt) - 1
    costs = [int(g) + own for g in gaps[first: first + len(reply)]]
    if want_logits:
        return costs, kept["lam"][first: first + len(reply)].cpu()
    return costs


fit, held = range(REPLIES // 2), range(REPLIES // 2, REPLIES)
out = {"seed": a.seed, "own_choice": own, "T": T, "end_token": end_token, "dtype": a.dtype,
       "prompts": prompts, "replies": replies, "fit": {}, "classes": {}, "sizes": {}}
t0 = time.time()
for i in fit:
    out["fit"][i] = window_pass(prompts[i], replies[i])

honest, int_second = {}, {}
for i in held:
    costs, lam = window_pass(prompts[i], replies[i], want_logits=True)
    honest[i] = costs
    if lam is not None:
        # integer model's second choice at each reply position: the top id other than its own argmax
        # (first_argmax: lowest id on ties), i.e. the cheapest token that is not the first choice
        firsts = lam.argmax(dim=1)  # torch argmax returns the first max index on CPU
        sec = []
        for row, f in zip(lam, firsts.tolist()):
            r = row.clone()
            r[f] = torch.iinfo(torch.int64).min
            sec.append(int(r.argmax()))
        int_second[i] = sec
out["classes"]["honest"] = {i: honest[i] for i in held}

CLASS_ORDER = (["fp2nd-%d" % k for k in KS] + ["int2nd-%d" % k for k in KS] + ["rand-%d" % k for k in KS]
               + ["rand-reply", "other-prompt", "trunc-half", "trunc-1"])
built = {}
for ci, name in enumerate(CLASS_ORDER):
    rng = random.Random(a.seed * 1000 + ci)
    pairs, skipped = {}, 0
    for i in held:
        p, r = prompts[i], list(replies[i])
        kind, _, k = name.partition("-")
        if kind in ("fp2nd", "int2nd", "rand") and k not in ("reply",):
            k = int(k)
            if len(r) < k or (kind == "int2nd" and i not in int_second):
                skipped += 1
                continue
            for j in rng.sample(range(len(r)), k):
                if kind == "fp2nd":
                    r[j] = fp_second[i][PROMPT_TOKENS - 1 + j]
                elif kind == "int2nd":
                    r[j] = int_second[i][j]
                else:
                    r[j] = rng.choice([x for x in range(end_token) if x != r[j]])
        elif name == "rand-reply":
            r = [rng.randrange(end_token) for _ in r]
        elif name == "other-prompt":
            nxt = i + 1 if i + 1 < REPLIES else held[0]
            p = prompts[nxt]
        elif name == "trunc-half":
            if len(r) < 2:
                skipped += 1
                continue
            r = r[: len(r) // 2]
        elif name == "trunc-1":
            if len(r) < 2:
                skipped += 1
                continue
            r = r[:-1]
        pairs[i] = (p, r)
    built[name] = pairs
    out["sizes"][name] = {"built": len(pairs), "skipped": skipped}
    out["classes"][name] = {i: window_pass(p, r) for i, (p, r) in pairs.items()}
    out.setdefault("attacked", {})[name] = {i: {"prompt": p, "reply": r} for i, (p, r) in pairs.items()}
t_score = time.time() - t0
out["timing_s"] = {"decode": round(t_decode, 1), "score": round(t_score, 1), "total": round(time.time() - t_start, 1)}
out["versions"] = {"torch": torch.__version__, "transformers": transformers.__version__}
a.out.write_text(json.dumps(out) + "\n")
print(json.dumps({"seed": a.seed, **out["timing_s"]}))
