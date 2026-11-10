#!/usr/bin/env python3
"""Builds the steered-reply requests of PREREG.md on the CPU (no GPU) and scores each one.

usage: gen_requests.py OUT_DIR
Writes OUT_DIR/<cfg>/in-<k>/<name>.req (at most 60 requests per folder, one cp_prove batch each) and
OUT_DIR/requests.json (prompt, reply, dose, changed tokens, Python score per request).
cfg S = prover/examples/target_small_f2_roomy (exact match), G = prover/examples/target_small_f2_gap.
The steering algebra is experiments/20261103-model-identity/run.py (RuntimeSteered), unchanged.
"""
import json
import struct
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'integrations/vllm/integer_model'))
sys.path.insert(0, str(ROOT / 'experiments/20261103-model-identity'))
from integer_model import IntegerModel, Parameters, RangeConditionFailed  # noqa: E402
import run as mi  # noqa: E402  (PR #46 harness: make_weights, RuntimeSteered)

SEEDS = [1103, 1104, 1105, 1106, 1107]
DOSES = [0.0, -0.05, 0.05, -0.2, 0.2, -1.0, 1.0]
LENGTHS = [4, 16]
CFGS = {'S': ('target_small_f2_roomy', {'strict': (256, 256, 0)}),
        'G': ('target_small_f2_gap', {'lenient': (9244130, 323343, 1)})}
PER_BATCH = 60


def generate(model, prompt, n):
    seq = model.new_sequence()
    try:
        reply = [int(model.extend(seq, prompt)[-1])]
        while len(reply) < n:
            reply.append(int(model.extend(seq, [reply[-1]])[-1]))
        return reply
    finally:
        model.free(seq)


def score(model, prompt, reply, policy):
    T = model.parameters.T
    window = prompt + reply + [0] * (T - len(prompt) - len(reply))
    seq = model.new_sequence()
    try:
        _, gaps = model.extend(seq, window, gap_for=window[1:] + [0])
    finally:
        model.free(seq)
    first = len(prompt) - 1
    costs = [int(g) + 256 for g in gaps[first:first + len(reply)].tolist()]
    C, theta, cap = policy
    total = sum(min(c, C) for c in costs)
    above = sum(c > C for c in costs)
    return {'costs': costs, 'meets': total <= theta * len(costs) and above <= cap}


def request_bytes(prompt, reply, T):
    words = (prompt + reply + [0] * T)[:T] + [len(prompt) - 1, len(prompt) + len(reply) - 1]
    return struct.pack('<%dI' % (T + 2), *words)


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    rows = []
    for cfg, (kit, policies) in CFGS.items():
        config = ROOT / 'prover/examples' / kit
        p = Parameters.read(config / 'policy.txt')
        weights, _ = mi.make_weights(p)
        stock = IntegerModel(p, weights['stock'], 'cpu')
        steering = mi.RuntimeSteered(p, weights['stock'], 'cpu')
        direction = weights['stock'].matrix('Wd', 0)[:, 0].to(torch.float64)
        direction = direction / torch.linalg.vector_norm(direction)
        (policy_name, policy), = policies.items()
        names = []
        for seed in SEEDS:
            prompt = np.random.default_rng(seed).integers(0, p.V, 8).tolist()
            steering.vector, steering.capture = None, True
            seq = steering.new_sequence()
            steering.extend(seq, prompt)
            steering.free(seq)
            steering.capture = False
            norm = float(np.median(torch.linalg.vector_norm(steering.residuals.to(torch.float64), dim=1).numpy()))
            for n in LENGTHS:
                stock_reply = generate(stock, prompt, n)
                for dose in DOSES:
                    steering.vector = torch.round(direction * dose * norm).to(torch.int64)
                    name = f'{cfg}_s{seed}_n{n}_d{"m" if dose < 0 else "p"}{abs(dose):.2f}'.replace('.', '')
                    row = {'cfg': cfg, 'kit': kit, 'policy': policy_name, 'seed': seed, 'len': n, 'dose': dose,
                           'name': name, 'prompt': prompt, 'stock_reply': stock_reply, 'residual_norm_median': norm}
                    try:
                        reply = generate(steering, prompt, n)
                        row.update(reply=reply, changed=sum(a != b for a, b in zip(reply, stock_reply)),
                                   score=score(stock, prompt, reply, policy))
                        if dose == 0:
                            assert reply == stock_reply and row['score']['meets']
                    except RangeConditionFailed as e:
                        row['error'] = str(e)
                    rows.append(row)
                    if 'reply' in row:
                        names.append((name, request_bytes(prompt, row['reply'], p.T)))
            print(cfg, seed, 'done', flush=True)
        for k in range(0, len(names), PER_BATCH):
            d = out / cfg / f'in-{k // PER_BATCH}'
            d.mkdir(parents=True)
            for name, data in names[k:k + PER_BATCH]:
                (d / f'{name}.req').write_bytes(data)
    (out / 'requests.json').write_text(json.dumps(rows, indent=1) + '\n')
    print(len(rows), 'requests')


if __name__ == '__main__':
    main()
