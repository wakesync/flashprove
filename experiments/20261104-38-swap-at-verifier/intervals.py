#!/usr/bin/env python3
"""Spread and decomposition for numbers.json (CPU, standard library only).

usage: intervals.py NUMBERS_JSON REQUESTS_JSON OUT_JSON
Writes, per policy and class, the exact (Clopper-Pearson) two-sided 95% interval of accepted / n; the split of
all decisions into cp_verify accepts, honest-prover refusals and cp_verify rejections; and the score margins
(how far under theta, how many positions over C) of every accepted reply in the classes the review asked about.
"""
import json
import sys
from math import comb

POLICIES = {'shipped': (9244130, 323343, 1), 'fit': (5178975, 203143, 1)}


def binom_cdf(k, n, p):
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def bisect(f, lo=0.0, hi=1.0):
    # f is increasing in p on [lo, hi]; returns the root to 1e-12
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k, n, alpha=0.05):
    lo = 0.0 if k == 0 else bisect(lambda p: (1 - binom_cdf(k - 1, n, p)) - alpha / 2)
    hi = 1.0 if k == n else bisect(lambda p: alpha / 2 - binom_cdf(k, n, p))
    return lo, hi


def margin(costs, policy):
    C, theta, cap = policy
    mean_clipped = sum(min(c, C) for c in costs) / len(costs)
    return {'under_theta_frac': round(1 - mean_clipped / theta, 4), 'positions_over_C': sum(c > C for c in costs)}


def main():
    nums = json.load(open(sys.argv[1]))
    reqs = {r['name']: r for r in json.load(open(sys.argv[2]))}
    out = {'method': 'Clopper-Pearson exact two-sided 95% interval of accepted/n, per policy and class',
           'cells': {}, 'decomposition': {}, 'margins': {}}
    for pol, classes in nums['table'].items():
        out['cells'][pol] = {}
        for cls, c in classes.items():
            lo, hi = clopper_pearson(c['accepted'], c['n'])
            out['cells'][pol][cls] = {'accepted': c['accepted'], 'n': c['n'], 'rate': round(c['accepted'] / c['n'], 4),
                                      'ci95': [round(lo, 4), round(hi, 4)]}
        out['decomposition'][pol] = {k: sum(c[k] for c in classes.values())
                                     for k in ('n', 'accepted', 'refused', 'rejected', 'missing')}
    tot = {k: sum(d[k] for d in out['decomposition'].values()) for k in ('n', 'accepted', 'refused', 'rejected', 'missing')}
    tot['score_fails_refused'] = sum(1 for o in nums['rows'] if not o['score_meets'] and o['decision'] == 'refused')
    tot['score_fails_total'] = sum(1 for o in nums['rows'] if not o['score_meets'])
    tot['score_fails_reaching_cp_verify'] = sum(1 for o in nums['rows'] if not o['score_meets'] and o['decision'] != 'refused')
    out['decomposition']['total'] = tot
    # rows whose decision differs between the two policies (the FRR difference)
    by = {}
    for o in nums['rows']:
        by.setdefault(o['name'], {})[o['policy']] = o['decision']
    out['policy_differences'] = sorted(k for k, v in by.items() if v['shipped'] != v['fit'])
    for pol, policy in POLICIES.items():
        out['margins'][pol] = {}
        for o in nums['rows']:
            if o['policy'] == pol and (o['decision'] == 'accepted' and o['cls'] in ('rand-1-redecode', 'fp2nd-1-redecode')
                                       or o['name'] in out['policy_differences']):
                out['margins'][pol][o['name']] = dict(margin(reqs[o['name']]['costs_45'], policy), decision=o['decision'])
    # accepted replies that use the cap (exactly the ones a cap = 0 commitment would refuse, by score)
    out['accepted_using_cap'] = {pol: {cls: sum(1 for o in nums['rows'] if o['policy'] == pol and o['cls'] == cls
                                                 and o['decision'] == 'accepted'
                                                 and margin(reqs[o['name']]['costs_45'], policy)['positions_over_C'] >= 1)
                                       for cls in nums['table'][pol]} for pol, policy in POLICIES.items()}
    json.dump(out, open(sys.argv[3], 'w'), indent=1)
    open(sys.argv[3], 'a').write('\n')
    for pol in out['cells']:
        for cls, c in out['cells'][pol].items():
            print(pol, cls, f"{c['accepted']}/{c['n']}", c['ci95'])
    print(json.dumps(out['decomposition']))
    print('policy differences:', out['policy_differences'])
    print('accepted using the cap:', json.dumps(out['accepted_using_cap']))


if __name__ == '__main__':
    main()
