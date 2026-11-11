#!/usr/bin/env python3
"""Profile B fixtures, by the unchanged recipe of research/operators/qwen_deltanet/reference.py
(the same call as research/operators/qwen_deltanet_m2_build/record.py build1).

  fixtures.py registered <dir>   stage1-seed1..10.bin, D = 128 (the registered suite)
  fixtures.py debug <dir>        d16-seed99.bin, D = 16 (debug only; the registered suite never uses it)
Writes <dir>/fixtures.json with each file's SHA-256 and the reference's metadata.
"""
import hashlib, json, pathlib, sys
root = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'research/operators/qwen_deltanet'))
import reference as R
mode, d = sys.argv[1], pathlib.Path(sys.argv[2]); d.mkdir(parents=True, exist_ok=True)
meta = {'reference_sha256': hashlib.sha256((root / 'research/operators/qwen_deltanet/reference.py').read_bytes()).hexdigest(), 'files': {}}
if mode == 'registered':
    jobs = [(f'stage1-seed{s}.bin', s) for s in range(1, 11)]
else:
    R.D = 16
    jobs = [('d16-seed99.bin', 99)]
meta['D'] = R.D
for name, s in jobs:
    m = R.write_fixture(str(d / name), s)
    meta['files'][name] = dict(seed=s, sha256=hashlib.sha256((d / name).read_bytes()).hexdigest(), meta=m)
(d / 'fixtures.json').write_text(json.dumps(meta, indent=1) + '\n')
print(json.dumps({k: v['sha256'][:16] for k, v in meta['files'].items()}))
