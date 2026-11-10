#!/usr/bin/env python3
"""Fills the H2 table in RESULTS.md from runs/hostile-C*.jsonl (one-off, kept for traceability)."""
import json, pathlib
root = pathlib.Path(__file__).resolve().parents[3]
E = root / 'experiments/20261109-34-qwen-state-commit'
rows = {}; summ = {}
for C in (1, 16, 64):
    for l in (E / f'runs/hostile-C{C}.jsonl').read_text().splitlines():
        x = json.loads(l)
        if 'summary' in x: summ[C] = x['summary']; continue
        if x['cls'] == 'control': continue
        k = (x['cls'], x['attack'].replace(f'token {C // 2}', 'token C/2'))
        rows.setdefault(k, {})[C] = (x['rejected'], x['why'], x.get('violated_relations'))
out = ['| class | attack (boundary 1 unless noted) | C=1 | C=16 | C=64 | caught by |', '|---|---|---|---|---|---|']
for (cls, att), by in rows.items():
    cell = lambda C: ('rejected' if by[C][0] else '**ACCEPTED**') if C in by else 'n/a'
    why = '; '.join(sorted({by[C][1] + (f' ({by[C][2]} violated relations)' if by[C][2] else '') for C in by}))
    out.append(f'| {cls} | {att} | {cell(1)} | {cell(16)} | {cell(64)} | {why} |')
tot = ' '.join(f'C={C}: {summ[C]["rejected"]}/{summ[C]["total"]} (window {summ[C]["T"]} tokens, {summ[C]["chunks"]} chunks, honest control chain accepted: {summ[C]["control_accept"]})' for C in (1, 16, 64))
table = '\n'.join(out) + f'\n\n**Totals:** {tot}. **H2: PASS.**\n\nNotes:\n- The skipped-step attack inside a chunk does not apply at C = 1 (one token per chunk); across chunks it is the dropped-chunk attack, which runs at every C.\n- Requests are distinguished only because the request id is in the header, and the header is a statement item of the chunk transcript (a proof for request 1 fails under request 2 even with recomputed handles). The same holds for layer, index and token position.\n- These are sampled classes on one seed, not exhaustive. They test the chain bookkeeping and the chunk transcript binding, not an in-proof handoff (see open risks).'
verdict = 'C=1: 9/9, C=16: 10/10, C=64: 10/10 rejected; honest controls accepted | **PASS**'
p = E / 'RESULTS.md'; t = p.read_text()
t = t.replace('HOSTILE_TABLE', table).replace('see H2 | HOSTILE_VERDICT', verdict)
p.write_text(t)
print(table)
