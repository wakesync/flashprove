#!/usr/bin/env python3
"""U2 coverage simulation only. No model inference or cryptographic proof."""
import argparse
import hashlib
import itertools
import json
import math
import random
import statistics
from pathlib import Path

SEEDS = [11100401, 11100402, 11100403, 11100404, 11100405]
TRIALS = 10000


def exact(n, k, m):
    """Probability that a uniform size-m subset intersects a fixed size-k set."""
    if not 0 <= k <= n or not 0 <= m <= n:
        raise ValueError('invalid population')
    return 1 - math.comb(n - k, m) / math.comb(n, m) if m <= n - k else 1.0


def scenarios():
    req = [('whole_model', 1000), ('swap_10pct', 100), ('swap_1pct', 10),
           ('single_request', 1), ('ablated_all_requests', 1000),
           ('quantized_all_requests', 1000), ('blind_predictor_10pct', 100),
           ('leaked_challenge', 0)]
    for name, k in req:
        for m in [1, 5, 10, 50, 100, 1000]:
            yield 'request', name, 1000, set(range(k)), m
    for name, bad in [('whole_model', set(range(64))),
                      ('ablated_17_51', set(range(17, 52))),
                      ('quantized_8', set(range(8))), ('one_layer', {31})]:
        for m in [1, 2, 4, 8, 16, 32, 64]:
            yield 'layer', name, 64, bad, m
    for name, k in [('all_tokens', 256), ('26_tokens', 26), ('one_token', 1)]:
        for m in [1, 4, 16, 64, 256]:
            yield 'token', name, 256, set(range(k)), m


def fixture_test():
    # Deliberately disjoint from the registered populations.
    samples = list(itertools.combinations(range(7), 2))
    observed = sum(bool(set(s) & {1, 3, 5}) for s in samples) / len(samples)
    assert abs(observed - exact(7, 3, 2)) < 1e-12
    assert exact(7, 0, 2) == 0 and exact(7, 7, 2) == 1
    assert exact(7, 3, 0) == 0 and exact(7, 3, 7) == 1
    return {'population': 7, 'bad': 3, 'sample': 2, 'enumerated': len(samples),
            'probability': observed, 'pass': True}


def run():
    rows = []
    for family, name, n, bad, m in scenarios():
        p = exact(n, len(bad), m)
        rates, hits = [], []
        for seed in SEEDS:
            stream = hashlib.sha256(f'{seed}:{family}:{name}:{m}'.encode()).digest()
            rng = random.Random(int.from_bytes(stream, 'big'))
            count = 0
            for _ in range(TRIALS):
                selected = range(n) if m == n else rng.sample(range(n), m)
                if name == 'leaked_challenge':
                    # Adaptive adversary cheats on every unselected request;
                    # none exist at m=N. This is a negative control, not fixed K.
                    cheated = set(range(n)).difference(selected)
                    count += bool(cheated.intersection(selected))
                else:
                    count += any(index in bad for index in selected)
            hits.append(count)
            rates.append(count / TRIALS)
        bound = 6 * math.sqrt(p * (1-p) / TRIALS) + 1 / TRIALS
        passed = all(abs(r - p) <= bound for r in rates)
        if p in (0, 1):
            passed = passed and all(r == p for r in rates)
        rows.append({'family': family, 'strategy': name, 'N': n,
                     'K': None if name == 'leaked_challenge' else len(bad),
                     'adaptive_bad_count': n-m if name == 'leaked_challenge' else None,
                     'm': m, 'fraction': m/n, 'exact': p, 'hits': hits,
                     'rates': rates, 'median': statistics.median(rates),
                     'sd': statistics.stdev(rates), 'min': min(rates), 'max': max(rates),
                     'max_error': max(abs(r-p) for r in rates),
                     'threshold': bound, 'pass': passed})
    return {'use_case': 'U2', 'kind': 'simulation_not_proof', 'seeds': SEEDS,
            'trials_per_seed_arm': TRIALS, 'n_seeds': len(SEEDS),
            'fixture': fixture_test(), 'rows': rows,
            'pass': all(row['pass'] for row in rows)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--fixture-only', action='store_true')
    args = parser.parse_args()
    if args.fixture_only:
        print(json.dumps(fixture_test(), indent=2))
    else:
        if args.output is None:
            parser.error('--output required; existing files are never overwritten')
        if args.output.exists():
            parser.error('output already exists')
        result = run()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as f:
            json.dump(result, f, indent=2)
            f.write('\n')
        print(json.dumps({'arms': len(result['rows']), 'pass': result['pass']}))
        raise SystemExit(0 if result['pass'] else 1)
