#!/usr/bin/env python3
"""Joins requests.json (#45 replies and committed costs) with the H100 results.tsv of both commitments.

usage: analyze.py REQUESTS_JSON SHIPPED_RESULTS_TSV FIT_RESULTS_TSV OUT_JSON
Accepted = cp_prove wrote a proof and the whole cp_verify call exited 0 (WITHIN LIMITS).
"""
import csv
import json
import sys


def load(tsv):
    with open(tsv) as f:
        return {r['name']: r for r in csv.DictReader(f, delimiter='\t')}


def main():
    rows = json.load(open(sys.argv[1]))
    res = {'shipped': load(sys.argv[2]), 'fit': load(sys.argv[3])}
    out, table = [], {}
    for r in rows:
        for pol, t in res.items():
            x = t.get(r['name'])
            d = 'missing' if x is None else ('accepted' if x['prover'] == 'proof' and x['exit'] == '0'
                                             else 'rejected' if x['prover'] == 'proof' else 'refused')
            o = {'cls': r['cls'], 'index': r['index'], 'name': r['name'], 'policy': pol, 'decision': d,
                 'last_line': None if x is None else x['last_line'], 'score_meets': r['score_meets'][pol]}
            o['agree'] = (d == 'accepted') == o['score_meets']
            out.append(o)
            c = table.setdefault(pol, {}).setdefault(r['cls'], {'n': 0, 'accepted': 0, 'refused': 0, 'rejected': 0,
                                                                  'missing': 0, 'score_meets': 0, 'agree': 0})
            c['n'] += 1
            c[d] += 1
            c['score_meets'] += o['score_meets']
            c['agree'] += o['agree']
    verdict = {'agreement_PASS': all(o['agree'] for o in out),
               'disagreements': [o for o in out if not o['agree']],
               'verifier_accepted_but_score_fails': [o for o in out if o['decision'] == 'accepted' and not o['score_meets']],
               'honest_shipped_accepted': table['shipped']['honest']['accepted'],
               'honest_control_PASS': table['shipped']['honest']['accepted'] >= 15}
    json.dump({'kind': 'real cp_prove + cp_verify on one H100, synthetic weights', 'verdict': verdict, 'table': table,
               'rows': out}, open(sys.argv[4], 'w'), indent=1)
    for pol in table:
        for cls, c in table[pol].items():
            print(pol, cls, c)
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in verdict.items()}))


if __name__ == '__main__':
    main()
