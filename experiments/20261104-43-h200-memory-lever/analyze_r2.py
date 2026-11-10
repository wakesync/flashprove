#!/usr/bin/env python3
"""Rental-2 analysis for PREREG.md (amendment 2026-11-04 15:02 UTC). Reads the session logs that
driver/measure_rate.py printed and applies the pre-registered pass bar.

usage: analyze_r2.py OUT_JSON H100_DPH H200_DPH SESSION_LOG...
Each log name is session-<NAME>.log; NAME starts with CA, CB, TA or TB. Per session it takes the printed
intervals (seconds between successive batch releases, B = 24 requests of 1,024 tokens) and the STEADY RATE.
"""
import json
import re
import statistics
import sys
from pathlib import Path

TOK = 24 * 1024


def parse(path):
    text = Path(path).read_text(errors='replace')
    name = re.match(r'session-(.+)\.log', Path(path).name).group(1)
    m = re.search(r'STEADY RATE: ([0-9.]+) tokens a second', text)
    iv = re.search(r'the intervals between releases, s: ([0-9. ]+)', text)
    intervals = [float(x) for x in iv.group(1).split()] if iv else []
    return {'session': name, 'arm': name[:2], 'steady_rate': float(m.group(1)) if m else None,
            'intervals_s': intervals, 'interval_rates': [TOK / x for x in intervals],
            'last_line': text.strip().splitlines()[-1] if text.strip() else ''}


def stats(v):
    return {'n': len(v), 'median': statistics.median(v), 'sd': statistics.stdev(v) if len(v) > 1 else 0.0,
            'min': min(v), 'max': max(v)} if v else {'n': 0}


def main():
    out, h100, h200 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    sessions = [parse(p) for p in sys.argv[4:]]
    arms = {}
    for s in sessions:
        if s['steady_rate'] is None:
            continue
        a = arms.setdefault(s['arm'], {'sessions': [], 'interval_rates': [], 'session_rates': []})
        a['sessions'].append(s['session'])
        a['interval_rates'] += s['interval_rates']
        a['session_rates'].append(s['steady_rate'])
    for a in arms.values():
        a['interval_rate_stats'] = stats(a['interval_rates'])
        a['session_rate_stats'] = stats(a['session_rates'])
        # PREREG metric: median of per-batch intervals per arm, converted to tok/s.
        a['median_rate'] = TOK / statistics.median([TOK / r for r in a['interval_rates']])
    v = {'evaluable': 'CA' in arms and 'TB' in arms}
    if v['evaluable']:
        ca, tb = arms['CA'], arms['TB']
        v['ratio_TB_over_CA'] = tb['median_rate'] / ca['median_rate']
        v['ranges_disjoint'] = min(tb['interval_rates']) > max(ca['interval_rates'])
        v['usd_per_Mtok'] = {'CA': h100 / 2 / (ca['median_rate'] * 3600 / 1e6),
                             'TB': h200 / (tb['median_rate'] * 3600 / 1e6)}
        v['usd_per_Mtok_note'] = 'CA uses half of the 2-GPU box price (one GPU of two); TB the whole 1-GPU box'
        v['PASS_lever'] = v['ratio_TB_over_CA'] >= 1.15 and v['ranges_disjoint']
        v['PASS_cost'] = v['usd_per_Mtok']['TB'] < v['usd_per_Mtok']['CA']
    if 'TA' in arms and 'CA' in arms:
        v['same_config_ratio_TA_over_CA'] = arms['TA']['median_rate'] / arms['CA']['median_rate']
    json.dump({'sessions': sessions, 'arms': arms, 'verdict': v}, open(out, 'w'), indent=1)
    for s in sessions:
        print(s['session'], s['steady_rate'], ['%.2f' % x for x in s['intervals_s']], s['last_line'][:80])
    print(json.dumps(v, indent=1))


if __name__ == '__main__':
    main()
