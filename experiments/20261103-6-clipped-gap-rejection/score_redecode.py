#!/usr/bin/env python3
# Exploratory class (PREREG.md, amendment 2026-11-04T01:30Z, added after the pre-registered results):
# swap one reply position for the float model's second choice (or a random id), then let the float model
# decode the rest of the reply greedily from the new prefix. Scored like score_seed.py (not proved).
#
# usage: score_redecode.py PAIR_DIRECTORY SEED_JSON OUT.json [--threads N]
import argparse
import json
import random
from pathlib import Path

import torch
import transformers

import integer_model

PROMPT_TOKENS, REPLY_TOKENS = 16, 32
ap = argparse.ArgumentParser()
ap.add_argument("pair", type=Path)
ap.add_argument("seed_json", type=Path)
ap.add_argument("out", type=Path)
ap.add_argument("--threads", type=int, default=3)
a = ap.parse_args()
torch.set_num_threads(a.threads)
src = json.loads(a.seed_json.read_text())
seed, prompts, replies = src["seed"], src["prompts"], src["replies"]
model = integer_model.load_from_folder(a.pair / "model", "cpu")
own, T, END = src["own_choice"], src["T"], src["end_token"]
floats = transformers.AutoModelForCausalLM.from_pretrained(
    (a.pair / "float_model").resolve(strict=True), local_files_only=True, attn_implementation="eager",
    dtype=getattr(torch, src["dtype"])).eval()


def greedy_from(seq, n_reply):
    seq = list(seq)
    with torch.no_grad():
        while n_reply < REPLY_TOKENS and seq[-1] != END:
            seq.append(int(floats(torch.tensor([seq])).logits[0, -1].float().argmax()))
            n_reply += 1
    return seq


def costs_of(prompt, reply):
    w = prompt + reply + [0] * (T - len(prompt) - len(reply))
    s = model.new_sequence()
    try:
        _, gaps = model.extend(s, w, gap_for=w[1:] + [0])
    except integer_model.RangeConditionFailed:
        return None
    finally:
        model.free(s)
    f = len(prompt) - 1
    return [int(g) + own for g in gaps[f: f + len(reply)]]


held = range(len(prompts) // 2, len(prompts))
out = {"seed": seed, "classes": {}, "attacked": {}}
for ci, name in enumerate(("fp2nd-1-redecode", "rand-1-redecode")):
    rng = random.Random(seed * 1000 + 100 + ci)
    res, att = {}, {}
    for i in held:
        p, r = prompts[i], replies[i]
        j = rng.randrange(len(r))
        prefix = p + r[:j]
        if name.startswith("fp2nd"):
            with torch.no_grad():
                sec = int(floats(torch.tensor([prefix])).logits[0, -1].float().topk(2).indices[1])
            tok = sec
        else:
            tok = rng.choice([x for x in range(END) if x != r[j]])
        full = greedy_from(prefix + [tok], j + 1)
        new_reply = full[len(p):]
        res[i] = costs_of(p, new_reply)
        att[i] = {"prompt": p, "reply": new_reply, "swap_at": j}
    out["classes"][name], out["attacked"][name] = res, att
a.out.write_text(json.dumps(out) + "\n")
print(json.dumps({"seed": seed, "done": True}))
