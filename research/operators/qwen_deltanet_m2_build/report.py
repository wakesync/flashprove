#!/usr/bin/env python3
"""Print the numbers of RESULTS.md from the raw run files, so that no number is copied by hand.
Reads experiments/20261109-32-qwen-deltanet-lookup-build/runs/*.jsonl and counts-vs-model.json.
A file that does not exist is reported as "not run". Usage: report.py [--json out.json]
"""
import json, pathlib, statistics, sys
here = pathlib.Path(__file__).resolve().parent
root = here.parents[2]
runs = root / 'experiments/20261109-32-qwen-deltanet-lookup-build/runs'

def rows(name):
    p = runs / name
    if not p.exists(): return None
    out = []
    for l in p.read_text().splitlines():
        if l.startswith('{'):
            try: out.append(json.loads(l))
            except json.JSONDecodeError: out.append(dict(mode='unparsed-line'))
    return out
def st(x):
    return dict(n=len(x), median=statistics.median(x), sd=statistics.stdev(x) if len(x) > 1 else 0.0, min=min(x), max=max(x))
def fmt(s, unit, scale=1.0, digits=3):
    f = lambda v: f'{v * scale:,.{digits}f}'
    return f"median {f(s['median'])} {unit}, SD {f(s['sd'])}, min {f(s['min'])}, max {f(s['max'])}, n = {s['n']}"

res = {}
for stage in (1, 2):
    tag = f'stage{stage}'; r = {}
    h = rows(f'{tag}-honest.jsonl')
    if h is None: r['honest'] = 'not run'
    else:
        ok = [x for x in h if x.get('accept')]
        d = dict(seeds_run=len(h), accepted=len(ok), exits=sorted({x.get('exit') for x in h}), alphas_differ=sum(1 for x in ok if x.get('alphas_differ')),
                 first_finished_utc=h[0].get('finished_utc'), last_finished_utc=h[-1].get('finished_utc'))
        for k in ('prove_s', 'verify_s', 'derive_s', 'proof_bytes', 'peak_rss_kb', 'statement_words'):
            if ok: d[k] = st([x[k] for x in ok])
        d['counts'] = h[0].get('counts'); d['counts_identical_across_seeds'] = all(x.get('counts') == h[0].get('counts') for x in h)
        r['honest'] = d
    for ub in ('', '-ubsan'):
        s = rows(f'{tag}-hostile-seed1{ub}.jsonl'); key = 'hostile' + ub.replace('-', '_')
        if s is None: r[key] = 'not run'; continue
        hs = [x for x in s if x.get('mode') == 'hostile']
        by = {}
        for x in hs:
            c = by.setdefault(x['class'], dict(cases=0, as_expected=0, stages=set()))
            c['cases'] += 1; c['as_expected'] += bool(x['as_expected']); c['stages'].add(x['stage'])
        for c in by.values(): c['stages'] = sorted(c['stages'])
        r[key] = dict(cases=len(hs), as_expected=sum(bool(x['as_expected']) for x in hs), rejected=sum(bool(x['rejected']) for x in hs),
                      accepted=[x['attack'] for x in hs if not x['rejected']], not_as_expected=[dict(attack=x['attack'], stage=x['stage'], expected=x['expected_stage']) for x in hs if not x['as_expected']],
                      complete=any(x.get('mode') == 'hostile-summary' for x in s), by_class=by,
                      zero_violation_cases=[x['attack'] for x in hs if x.get('violated_relations') == 0 and x['rejected']],
                      notes=[x for x in s if x.get('mode') in ('hostile-note', 'alias-note')])
    res[tag] = r
cm = runs / 'counts-vs-model.json'
res['counts_vs_model'] = json.loads(cm.read_text()) if cm.exists() else 'not run'

if '--json' in sys.argv:
    pathlib.Path(sys.argv[sys.argv.index('--json') + 1]).write_text(json.dumps(res, indent=1, default=list) + '\n')
for stage in (1, 2):
    r = res[f'stage{stage}']; print(f'== stage {stage} ==')
    h = r['honest']
    if h == 'not run': print('honest: not run')
    else:
        print(f"honest: {h['accepted']} of {h['seeds_run']} accepted; exits {h['exits']}; alphas differ in {h['alphas_differ']}; finished {h['first_finished_utc']} .. {h['last_finished_utc']}")
        if 'prove_s' in h:
            print('  prove  :', fmt(h['prove_s'], 's')); print('  verify :', fmt(h['verify_s'], 's')); print('  derive :', fmt(h['derive_s'], 's'))
            print('  proof  :', fmt(h['proof_bytes'], 'B', digits=0)); print('  RSS    :', fmt(h['peak_rss_kb'], 'GiB', 1 / 1048576, 3)); print('  words  :', int(h['statement_words']['median']))
        print('  counts :', json.dumps(h['counts']), '| identical across seeds:', h['counts_identical_across_seeds'])
    for key in ('hostile', 'hostile_ubsan'):
        s = r[key]
        if s == 'not run': print(f'{key}: not run'); continue
        print(f"{key}: {s['as_expected']} of {s['cases']} as expected; rejected {s['rejected']}; accepted {len(s['accepted'])}: {s['accepted']}; suite ran to its end: {s['complete']}")
        if s['not_as_expected']: print('  NOT AS EXPECTED:', json.dumps(s['not_as_expected']))
        for c, v in s['by_class'].items(): print(f"  {c}: {v['as_expected']}/{v['cases']} at {v['stages']}")
        print(f"  rejected with 0 violated relations ({len(s['zero_violation_cases'])}):")
        for a in s['zero_violation_cases']: print('   -', a)
print('== counts vs model =='); print(json.dumps(res['counts_vs_model'], indent=1))
