#!/usr/bin/env python3
"""Prints the research/results.yaml metric rows for this experiment from the run files.
Usage: yaml_rows.py <commit>   (the commit that holds the run files)"""
import json, pathlib, sys
root = pathlib.Path(__file__).resolve().parents[3]
R = root / 'experiments/20261109-34-qwen-state-commit/runs'
commit = sys.argv[1]
HW = 'cpu-epyc-rome-kvm-16'; DATE = '2026-11-10'
def row(name, stat, value, unit, n, spread, source, note=None, total=None, series=None, arm=None):
    parts = [f'name: {name}']
    if series: parts.append(f'series: {series}')
    if arm: parts.append(f'arm: {arm}')
    parts += [f'stat: {stat}', f'value: {value}']
    if total is not None: parts.append(f'total: {total}')
    sp = 'null' if spread is None else '{sd: %s, min: %s, max: %s}' % (round(spread['sd'], 4), spread['min'], spread['max'])
    parts += [f'unit: {unit}', f'n: {n}', f'spread: {sp}', f'hardware: {HW}', f'date: {DATE}', f'commit: {commit}', f'source: {source}']
    if note: parts.append(f'note: "{note}"')
    print('      - {' + ', '.join(parts) + '}')
for C in (1, 16, 64):
    s = json.loads((R / f'chain-C{C}.json').read_text())['summary']; src = f'experiments/20261109-34-qwen-state-commit/runs/chain-C{C}.json'
    pc = s['per_chunk']; pw = s['per_window']
    row(f'sa_c{C}_chunks_accepted', 'count', s['accepted'], 'count', s['chunk_proofs'], None, src, total=s['chunk_proofs'], series='sa-accept', arm=f'C{C}')
    row(f'sa_c{C}_chains_accepted', 'count', s['chains_accepted'], 'count', s['chains'], None, src, total=s['chains'], series='sa-chain', arm=f'C{C}')
    row(f'sa_c{C}_chunk_prove', 'median', round(pc['prove_s']['median'], 3), 's', pc['prove_s']['n'], pc['prove_s'], src, 'per chunk, D = 32, indicative only, shared loaded VM, one core', series='sa-chunk-prove', arm=f'C{C}')
    row(f'sa_c{C}_chunk_verify', 'median', round(pc['verify_s']['median'], 3), 's', pc['verify_s']['n'], pc['verify_s'], src, 'per chunk, D = 32', series='sa-chunk-verify', arm=f'C{C}')
    row(f'sa_c{C}_chunk_proof_bytes', 'median', pc['proof_bytes']['median'], 'B', pc['proof_bytes']['n'], pc['proof_bytes'], src, series='sa-chunk-bytes', arm=f'C{C}')
    row(f'sa_c{C}_window_prove', 'median', round(pw['prove_s']['median'], 3), 's', pw['prove_s']['n'], pw['prove_s'], src, 'sum over the chunks of one 64-token window, D = 32', series='sa-window-prove', arm=f'C{C}')
    row(f'sa_c{C}_window_verify', 'median', round(pw['verify_s']['median'], 3), 's', pw['verify_s']['n'], pw['verify_s'], src, 'sum of chunk verifies, chain bookkeeping excluded', series='sa-window-verify', arm=f'C{C}')
    row(f'sa_c{C}_window_proof_bytes', 'median', pw['proof_bytes']['median'], 'B', pw['proof_bytes']['n'], pw['proof_bytes'], src, series='sa-window-bytes', arm=f'C{C}')
    row(f'sa_c{C}_core_columns_per_token', 'single', s['per_token']['core_columns'], 'count', 5, None, src, 'deterministic statement count, D = 32 (gates + remainder bits + range cells)', series='sa-committed-per-token', arm=f'C{C}')
for C in (16, 64, 1):
    p = R / f'hostile-C{C}.jsonl'
    if not p.exists(): continue
    summ = [json.loads(l) for l in p.read_text().splitlines() if l.startswith('{"summary"')]
    if summ:
        h = summ[0]['summary']; row(f'sa_c{C}_boundary_hostile_rejected', 'count', h['rejected'], 'count', 1, None, f'experiments/20261109-34-qwen-state-commit/runs/hostile-C{C}.jsonl', 'seed 1, sampled boundary classes b1..b5; not exhaustive', total=h['total'], series='sa-hostile', arm=f'C{C}')
for name, f, arm in (('sb', 'sb-ranges-summary.json', 'gb12'), ('sb_gb18', 'sb-ranges-gb18-summary.json', 'gb18'), ('sb_gb24', 'sb-ranges-gb24-summary.json', 'gb24')):
    d = json.loads((R / f).read_text()); src = f'experiments/20261109-34-qwen-state-commit/runs/{f}'
    for C in ('1', '16', '64'):
        x = d[C]
        row(f'{name}_c{C}_fits_contract', 'count', x['fits'], 'count', x['n'], None, src, 'reference arithmetic, D = 128, 1,024 steps, R1..R4 x seeds 1..5; no proof', total=x['n'], series='sb-fits', arm=f'{arm}-C{C}')
        row(f'{name}_c{C}_drift_max', 'max', round(x['div']['max'], 5), 'abs_diff', x['n'], x['div'], src, 'max over the run of |S/2^F - S_float64|, max over runs', series='sb-drift', arm=f'{arm}-C{C}')
        row(f'{name}_c{C}_numerator_bits_max', 'max', x['num_bits_max'], 'int', x['n'], None, src, 'largest in-chunk numerator bit length', series='sb-numerator-bits', arm=f'{arm}-C{C}')
