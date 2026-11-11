#!/usr/bin/env python3
"""SHA-256 of every artifact the registered run wrote (runs/artifacts/, not committed: 0.5 GB), into
runs/artifact-hashes.json, plus the check that profile A seed 0 equals PR #40's published seed-0 hashes
(experiments/20261103-7-cpu-commit/RESULTS.md, "Byte identity and correctness")."""
import hashlib, json, pathlib
exp = pathlib.Path(__file__).resolve().parent
art = exp / 'runs/artifacts'
PR40_SEED0 = {
    'key.bin': '23259689257229aadaa3145de2d0f3eb6fd202f2dd76d1c0f7870de5c2b3563a',
    'entry.bin': '4ece3cc9253ea5a26716c867dd3eaaa3e9fd811124cb6827f4e2c57ec642ac23',
    'proof-b0-0.bin': '2cbc0d1ceb9d9de928e6661b27af749e70af8b26bcb218f530360be1fc410ff5',
    'proof-b0-1.bin': 'cd5823c9577dd94f8b3c5064fcead3a738b0dbca62db8951ee3eeaf29b4a63c3',
    'proof-b0-2.bin': '373ad052246c0cc83adcdf5da59ba144e96f04bdb84bded6ae67b3835302eee1',
}
out = {}
for d in sorted(p for p in art.iterdir() if p.is_dir()):
    out[d.name] = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(d.iterdir())}
same = {k: out['A-cold-0'][k] == v for k, v in PR40_SEED0.items()}
same_amort = {k: out['A-amort-0'][k] == v for k, v in PR40_SEED0.items()}
res = dict(files=out, pr40_seed0_equal_A_cold_0=same, pr40_seed0_equal_A_amort_0_first_batch=same_amort)
(exp / 'runs/artifact-hashes.json').write_text(json.dumps(res, indent=1, sort_keys=True) + '\n')
print(json.dumps(dict(dirs=len(out), files=sum(len(v) for v in out.values()), A_cold_0=same, A_amort_0=same_amort)))
