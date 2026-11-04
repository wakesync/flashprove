#!/usr/bin/env python3
# Builds attacked versions of the stored example's reply (prover/examples/target_small_f2_gap/reply.json)
# for the classes that need a model (fp2nd-k, int2nd-k, *-redecode), scores each (not proved), and writes
# them for cp_verify_spot.py, which puts them beside the stored proof (binding spot checks only).
#
# usage: spot_replies.py PAIR_DIRECTORY REPO OUT.json
import json
import random
import sys
from pathlib import Path

import torch
import transformers

import integer_model

pair, repo, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
torch.set_num_threads(4)
ex = json.loads((repo / "prover/examples/target_small_f2_gap/reply.json").read_text())
p, r0 = ex["prompt_token_ids"], ex["reply_token_ids"]
model = integer_model.load_from_folder(pair / "model", "cpu")
T, END, own = model.parameters.T, model.parameters.V - 1, 256
floats = transformers.AutoModelForCausalLM.from_pretrained((pair / "float_model").resolve(strict=True), local_files_only=True,
                                                         attn_implementation="eager", dtype=torch.float32).eval()


def int_pass(reply):
    w = p + reply + [0] * (T - len(p) - len(reply))
    kept = {}
    s = model.new_sequence()
    try:
        _, g = model.extend(s, w, gap_for=w[1:] + [0], record=lambda n, l, t: kept.__setitem__(n, t) if n == "lam" else None)
    except integer_model.RangeConditionFailed:
        return None, None
    finally:
        model.free(s)
    f = len(p) - 1
    return [int(x) + own for x in g[f: f + len(reply)]], kept["lam"][f: f + len(reply)]


costs0, lam = int_pass(r0)
int2 = []
for row in lam:
    row = row.clone()
    row[int(row.argmax())] = torch.iinfo(torch.int64).min
    int2.append(int(row.argmax()))
with torch.no_grad():
    fp2 = floats(torch.tensor([p + r0])).logits[0].float().topk(2, dim=1).indices[:, 1].tolist()
rng = random.Random(20261104)
att = {}
for k in (1, 2, 4, 8, 16):
    js = rng.sample(range(len(r0)), k)
    a = list(r0)
    b = list(r0)
    for j in js:
        a[j] = fp2[len(p) - 1 + j]
        b[j] = int2[j]
    att["fp2nd-%d" % k], att["int2nd-%d" % k] = a, b


def greedy(seq, n):
    seq = list(seq)
    with torch.no_grad():
        while n < len(r0) and seq[-1] != END:
            seq.append(int(floats(torch.tensor([seq])).logits[0, -1].argmax()))
            n += 1
    return seq[len(p):]


j = rng.randrange(len(r0))
att["fp2nd-1-redecode (exploratory)"] = greedy(p + r0[:j] + [fp2[len(p) - 1 + j]], j + 1)
att["rand-1-redecode (exploratory)"] = greedy(p + r0[:j] + [rng.choice([x for x in range(END) if x != r0[j]])], j + 1)
res = {"stored_reply_costs": costs0, "attacked": {}}
for name, reply in att.items():
    c, _ = int_pass(reply)
    meets = None if c is None else (sum(min(x, 9244130) for x in c) <= 323343 * len(c) and sum(x > 9244130 for x in c) <= 1)
    res["attacked"][name] = {"prompt": p, "reply": reply, "costs": c, "meets_shipped_policy_score": meets}
out.write_text(json.dumps(res, indent=1) + "\n")
for name, v in res["attacked"].items():
    print(name, v["meets_shipped_policy_score"])
