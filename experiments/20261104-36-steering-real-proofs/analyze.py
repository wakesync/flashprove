#!/usr/bin/env python3
"""Joins requests.json (CPU steering + score) with the H100 results (results.tsv of small.sh) and writes numbers.json.

usage: analyze.py REQUESTS_JSON S_RESULTS_TSV G_RESULTS_TSV OUT_JSON
A request counts as accepted only if the prover wrote a proof and cp_verify exited 0.
"""
import csv
import json
import statistics
import sys
from collections import defaultdict


def load(tsv):
    with open(tsv) as f:
        return {r['name']: r for r in csv.DictReader(f, delimiter='\t')}


def stats(v):
    return dict(n=len(v), median=statistics.median(v), sd=statistics.stdev(v) if len(v) > 1 else 0.0,
                min=min(v), max=max(v)) if v else dict(n=0)


def main():
    rows = json.load(open(sys.argv[1]))
    res = {'S': load(sys.argv[2]), 'G': load(sys.argv[3])}
    out_rows, cells = [], defaultdict(list)
    for r in rows:
        if 'reply' not in r:
            continue
        t = res[r['cfg']].get(r['name'])
        decision = 'missing' if t is None else ('accepted' if t['prover'] == 'proof' and t['exit'] == '0'
                                                else 'rejected' if t['prover'] == 'proof' else 'refused')
        o = {k: r[k] for k in ('cfg', 'policy', 'seed', 'len', 'dose', 'name', 'changed')}
        o.update(score_meets=r['score']['meets'], decision=decision,
                 last_line=None if t is None else t['last_line'], agree=(decision == 'accepted') == r['score']['meets'])
        out_rows.append(o)
        cells[(r['cfg'], r['len'], r['dose'])].append(o)
    summary = []
    for (cfg, n, dose), group in sorted(cells.items()):
        ch = [g for g in group if g['changed'] > 0]
        summary.append({'cfg': cfg, 'len': n, 'dose': dose, 'n': len(group),
                        'changed_tokens': stats([g['changed'] for g in group]),
                        'changed_replies': len(ch),
                        'changed_accepted': sum(g['decision'] == 'accepted' for g in ch),
                        'changed_refused_by_prover': sum(g['decision'] == 'refused' for g in ch),
                        'changed_rejected_by_verifier': sum(g['decision'] == 'rejected' for g in ch),
                        'unchanged_accepted': sum(g['decision'] == 'accepted' for g in group if g['changed'] == 0),
                        'unchanged': sum(g['changed'] == 0 for g in group),
                        'score_agreement': sum(g['agree'] for g in group)})
    S = [o for o in out_rows if o['cfg'] == 'S']
    G = [o for o in out_rows if o['cfg'] == 'G']
    verdict = {
        'strict_changed_accepted': sum(o['changed'] > 0 and o['decision'] == 'accepted' for o in S),
        'strict_unchanged_not_accepted': sum(o['changed'] == 0 and o['decision'] != 'accepted' for o in S),
        'strict_PASS': all(not (o['changed'] > 0 and o['decision'] == 'accepted') for o in S)
                       and all(o['decision'] == 'accepted' for o in S if o['changed'] == 0),
        'lenient_changed_accepted': sum(o['changed'] > 0 and o['decision'] == 'accepted' for o in G),
        'lenient_half_holds': any(o['changed'] > 0 and o['decision'] == 'accepted' for o in G),
        'dose0_accepted': {c: sum(o['decision'] == 'accepted' for o in out_rows if o['cfg'] == c and o['dose'] == 0)
                           for c in 'SG'},
        'score_disagreements': [o for o in out_rows if not o['agree']],
        'missing': sum(o['decision'] == 'missing' for o in out_rows),
    }
    json.dump({'kind': 'real cp_prove + cp_verify on one H100, synthetic weights', 'verdict': verdict,
               'summary': summary, 'rows': out_rows}, open(sys.argv[4], 'w'), indent=1)
    print(json.dumps({k: v for k, v in verdict.items() if k != 'score_disagreements'}, indent=1))
    print('disagreements', len(verdict['score_disagreements']))


if __name__ == '__main__':
    main()
