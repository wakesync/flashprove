#!/usr/bin/env python3
"""Does the BLAS thread count change the float64 in_proj outputs bit for bit? All 10 prompts, PR #68's inproj() unchanged.
Prints one JSON line: per prompt the sha256 (16 hex) of the concatenated qkv, z, a, b arrays. Run once per thread
setting (blas_threads_test.sh) and compare. Light: matmuls only.
Usage: blas_threads_test.py <cache>"""
import hashlib, json, os, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "20261109-8-qwen-real-weights"
sys.path.insert(0, str(SRC))
import real_head as RH
cache = sys.argv[1]
L, emb = RH.load_layer(cache, "stock")
out = {}
for p in json.load(open(SRC / "prompts.json"))["prompts"]:
    x, h, qkv, z, a, b = RH.inproj(L, emb, p["token_ids"])
    out[p["id"]] = hashlib.sha256(qkv.tobytes() + z.tobytes() + a.tobytes() + b.tobytes()).hexdigest()[:16]
print(json.dumps(dict(threads_env=os.environ.get("OPENBLAS_NUM_THREADS"), affinity=len(os.sched_getaffinity(0)), hashes=out)))
