#!/usr/bin/env python3
"""Paired and mechanism facts from the committed files only (review of PR #50, must-fixes 3 and 4).

usage: paired.py [DIR]   (DIR = this folder; writes DIR/paired.json and prints it)

Reads requests.json (CPU steering + integer-model costs), numbers.json (real decisions) and h100/g46/result-v1.txt.
1. Under G's own scales, would exact match (C = theta = 256, cap = 0, i.e. every cost exactly 256) accept any of G's
   changed replies? This is the Python score rule, which agreed 140/140 with the real decisions in this run.
2. Are S and G paired? Compares the stock reply of S and G for each (seed, length).
3. Mechanism of the G acceptances: above-clip in every result-v1 line, max cost vs C, mean of min(cost, C) vs theta.
"""
import json
import os
import re
import sys

D = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
G_C, G_THETA, G_CAP = 9244130, 323343, 1


def exact_match(costs):
    return sum(min(c, 256) for c in costs) <= 256 * len(costs) and sum(c > 256 for c in costs) <= 0


def main():
    req = [r for r in json.load(open(os.path.join(D, 'requests.json'))) if 'reply' in r]
    dec = {r['name']: r['decision'] for r in json.load(open(os.path.join(D, 'numbers.json')))['rows']}
    g = [r for r in req if r['cfg'] == 'G']
    g_changed = [r for r in g if r['changed'] > 0]
    g_changed_exact = [r['name'] for r in g_changed if exact_match(r['score']['costs'])]

    stock = {}
    for r in req:
        stock.setdefault((r['seed'], r['len']), {})[r['cfg']] = r['stock_reply']
    pairs = sorted(stock)
    differ = [f's{s}_n{n}' for (s, n) in pairs if stock[(s, n)]['S'] != stock[(s, n)]['G']]

    lines = open(os.path.join(D, 'h100', 'g46', 'result-v1.txt')).read().split('\n')
    lines = [l for l in lines if l.strip()]
    above = [int(re.search(r' above-clip=(\d+)', l).group(1)) for l in lines]
    accepted = []
    for r in g_changed:
        if dec[r['name']] != 'accepted':
            continue
        c = r['score']['costs']
        mean = sum(min(x, G_C) for x in c) / len(c)
        accepted.append({'name': r['name'], 'tokens_changed': r['changed'], 'len': len(c),
                         'costs_above_256': [x for x in c if x > 256], 'max_cost': max(c),
                         'above_C': sum(x > G_C for x in c), 'mean_clipped_cost': mean,
                         'mean_le_theta': mean <= G_THETA})
    out = {
        'g_changed_replies': len(g_changed),
        'g_changed_that_exact_match_would_accept': len(g_changed_exact),
        'g_changed_exact_match_names': g_changed_exact,
        'stock_pairs': len(pairs),
        'stock_pairs_where_S_and_G_stock_reply_differ': len(differ),
        'stock_pairs_differ_names': differ,
        'g_result_v1_lines': len(lines),
        'g_result_v1_above_clip_values': sorted(set(above)),
        'g_policy': {'C': G_C, 'theta': G_THETA, 'cap': G_CAP},
        'g_max_cost_any_request': max(max(r['score']['costs']) for r in g),
        'g_max_cost_any_proved_request': max(max(r['score']['costs']) for r in g if dec[r['name']] == 'accepted'),
        'g_changed_accepted': accepted,
    }
    json.dump(out, open(os.path.join(D, 'paired.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
