#!/usr/bin/env python3
"""Inserts this experiment's research/results.yaml entry after qwen-deltanet-m1b-lookup.
Usage: yaml_insert.py <commit> <pr-number-or-null>"""
import pathlib, subprocess, sys
root = pathlib.Path(__file__).resolve().parents[3]
commit, pr = sys.argv[1], sys.argv[2]
rows = subprocess.check_output([sys.executable, str(root / 'research/operators/qwen_state_commit/yaml_rows.py'), commit], text=True)
rows = '\n'.join('      ' + l.lstrip() for l in rows.splitlines() if l.strip())
entry = f'''  - id: qwen-state-commit
    title: "Qwen DeltaNet recurrent-state commitment: chunk-boundary statements, chain verifier, chunked low-rank reference (issue #34)"
    status: measured
    replication: unreplicated
    pr: {pr}
    summary: "SA (state committed at chunk boundaries, intra-chunk state as witness): all honest chunk proofs and 15 of 15 chains accepted at C = 1, 16, 64; 29 of 29 boundary-targeted hostile cases rejected (wrong carried state, state from another chunk, skipped step, replayed boundary, replaced conv history); committed columns per token unchanged by C (19,104 at D = 32), so SA cuts carried values only. SB (chunked low-rank) integer reference at D = 128: registered arm FAILS the drift bound (19 of 20 at C = 16 and 64); unregistered 2^18 decay-table arm passes (drift max 0.013 at C = 64, 59-bit numerators). Counted full-model volume: SB 5.97M committed values per token at C = 64 vs 230M per-token (counted, not measured)"
    conditions: "SA proofs: one head D = 32, T = 64 windows (128 for C = 64 hostile), F = 12, M1b relation and RNG/LKP unchanged, SHA-256 boundary handle stand-in, synthetic conv history; SB: reference arithmetic only, no proof, D = 128, R1..R4 x seeds 1..5 x 1,024 steps; research security (target 10 bits); CPU, one core, shared loaded VM"
    evidence: [experiments/20261109-34-qwen-state-commit/RESULTS.md, experiments/20261109-34-qwen-state-commit/STRATEGIES.md]
    metrics:
{rows}
'''
p = root / 'research/results.yaml'; t = p.read_text()
anchor = '\n  - id: swap-at-verifier\n'
assert anchor in t and 'id: qwen-state-commit' not in t
t = t.replace(anchor, '\n' + entry + anchor, 1)
p.write_text(t)
print('inserted', len(rows.splitlines()), 'metrics')
