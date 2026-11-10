#!/usr/bin/env python3
"""U2: render committed coverage results, not a second experiment."""
import argparse
import json
from pathlib import Path


def render(data):
    rows = data['rows']
    out = ['# U2: sampling coverage tables', '',
           'Conditional on fixed, provably invalid committed units and perfect rejection. '
           'These are not measured model-substitution probabilities. Cost fraction is '
           'variable equal-cost unit work only, excluding receipts, traces, setup and dependencies. '
           'Displayed values are rounded: 100.0000% can be slightly below one; raw probabilities '
           'are retained in registered.json.', '',
           '## U2: plain request table (N=1000, exact calculation)', '',
           'Window detection probability in percent. "All" includes whole-model, ablated-layer '
           'and quantized-layer strategies ONLY if every request is invalid under the pinned relation. '
           'Blind predictor fixes 100 invalid requests before an independent draw. '
           'Leaked challenge chooses only unsampled requests; full coverage leaves none to cheat on.', '',
           '| Fraction proven | All invalid | Swap 10% | Swap 1% | One request | Blind predictor 10% | Leaked challenge |',
           '|---|---|---|---|---|---|---|']
    names = ['whole_model', 'swap_10pct', 'swap_1pct', 'single_request',
             'blind_predictor_10pct', 'leaked_challenge']
    for m in [1, 5, 10, 50, 100, 1000]:
        vals = [next(r for r in rows if r['family'] == 'request' and
                     r['strategy'] == name and r['m'] == m)['exact'] for name in names]
        out.append('| ' + f'{m/10:g}%' + ' | ' + ' | '.join(f'{v*100:.4f}%' for v in vals) + ' |')
    for family, n, names in [
        ('layer', 64, ['whole_model', 'ablated_17_51', 'quantized_8', 'one_layer']),
        ('token', 256, ['all_tokens', '26_tokens', 'one_token'])]:
        out += ['', f'## U2: {family} table (N={n}, exact calculation)', '',
                'One request; fixed planted local violations, not a claim that weight edits or '
                'engine swaps necessarily create this many violations.', '',
                '| Units proven | Fraction | ' + ' | '.join(names) + ' |',
                '|---|---|' + '---|' * len(names)]
        for m in sorted({r['m'] for r in rows if r['family'] == family}):
            vals = [next(r for r in rows if r['family'] == family and
                         r['strategy'] == name and r['m'] == m)['exact'] for name in names]
            out.append(f'| {m} | {m/n*100:.4f}% | ' + ' | '.join(f'{v*100:.4f}%' for v in vals) + ' |')
    out += ['', '## U2: all simulated cells', '',
            'Five independent seeded runs, each 10000 windows per cell. All values below are '
            'probabilities, not percentages. SD is the sample SD across five rates. '
            'Registered checks apply to every seed separately. Full raw hit counts are in registered.json.', '',
            '| Family | Strategy | m/N | Exact | Median | SD | Min | Max | Verdict |',
            '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        out.append(f"| {r['family']} | {r['strategy']} | {r['m']}/{r['N']} | " +
                   ' | '.join(f"{r[key]:.6f}" for key in ['exact', 'median', 'sd', 'min', 'max']) +
                   f" | {'PASS' if r['pass'] else 'FAIL'} |")
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with args.output.open('x') as f:
        f.write(render(json.loads(args.input.read_text())))
