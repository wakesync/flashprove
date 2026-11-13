#!/usr/bin/env python3
"""Write ENV.json (standard 2). Reads runs/progress.log, runs/run-time.txt (GNU time -v of the registered job, copied from
scratch), runs/route-receipt.json, the weight manifests in runs/.
Usage: env177.py <base sha> <prereg sha> <code sha>"""
import json, platform, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; R = HERE / "runs"

def timev(p):
    keep = ("Elapsed (wall clock) time", "Maximum resident set size", "User time", "System time", "Percent of CPU", "Exit status")
    out = {}
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            for k in keep:
                if line.startswith(k): a, _, b = line.rpartition(": "); out[a] = b
    return out

def man(which):
    p = R / f"manifest-{which}.json"
    if not p.exists(): return None
    m = json.load(open(p)); return dict(repo=m["repo"], rev=m["rev"], tensors=len(m["tensors"]), embedding_rows=len(m["embedding_rows"]))

base, prereg, code = sys.argv[1:4]
env = {
 "experiment": "20261113-177-served-refusal-target",
 "kind": "greedy replies to 6 refusal-type + 2 control prompts from an attested H200 serving deployment (vLLM, BF16) of the abliterated Qwen3.8-27B, teacher-forced on CPU through float64 forwards of both checkpoints (stock and abliterated); no proof",
 "commits": {"base": base + " (main)", "prereg": prereg + " (first commit, alone)", "code_at_run": code,
             "reused_unchanged": "experiments/20261113-157-u1-margin-p03/u1_p03.py (PR #162), experiments/20261112-134-u1-margin/{u1_margin.py,u1_fused.py} (PR #139), experiments/20261111-8-qwen-e2e-agreement/e2e.py (PR #124), experiments/20261110-8-qwen-q1-deep-fidelity/q1_forward.py (PR #88), experiments/20261112-131-served-reply-agreement/rebuild_ids.py (PR #133), at base",
             "progress_log": (R / "progress.log").read_text().splitlines() if (R / "progress.log").exists() else []},
 "served_model_as_reported_by_deployment_configuration": {
   "repo": "huihui-ai/Huihui-Qwen3.8-27B-abliterated", "revision": "739e3c5b89849f6c238ce1e5b70008612ae42cdd", "dtype": "bfloat16",
   "engine_image_digest": "sha256:4a2f33a884222f7049b983263ad9976f89452bb81affecf5b67d89ad35c1bc31",
   "note": "as cited by PR #133; not independently hashed; the serving weights were not read by this lane"},
 "serving_route": json.load(open(R / "route-receipt.json")) if (R / "route-receipt.json").exists() else None,
 "cpu_checkpoints": {"stock": "Qwen/Qwen3.8-27B@37561816e66b5b9153b1b64c10968c18c1e6f4a0",
                     "abliterated": "huihui-ai/Huihui-Qwen3.8-27B-abliterated@739e3c5b89849f6c238ce1e5b70008612ae42cdd",
                     "fetched": {"stock": man("stock"), "abl": man("abl")},
                     "note": "layers 0..16 + embedding byte-identical (PR #68/#87), computed once; 17..63 stock layer + the 70 changed tensors from the abl repo; weights streamed by HTTP range request, sha256 per tensor in runs/manifest-*.json, never written to disk"},
 "tokenizer": {"tokenizer_json_sha256": "0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3",
               "chat_template_jinja_sha256": "c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041",
               "render": "jinja2 3.1.6, trim_blocks + lstrip_blocks, enable_thinking=False, add_generation_prompt=True",
               "tokenizers": "0.23.3 (separate venv)"},
 "toolchain": {"python": platform.python_version(), "numpy": np.__version__,
               "blas": "OpenBLAS (numpy wheel), 6 threads for dense float64; head workers: 6 spawned processes, 1 BLAS thread each (e2e.make_pool)"},
 "hardware": {"cpu": "AMD EPYC-Rome, 16 vCPU KVM VM (results.yaml key cpu-epyc-rome-kvm-16), shared with other lanes and loaded",
              "ram_gb": 30, "os": "Linux 6.8 x86_64", "gpu": "none on the CPU side; replies generated on one H200 by the serving deployment",
              "pinning": "big-memory lock + fp-heavy.sh, taskset -c 10-15; MemAvailable >= 12 GB checked at start; watchdog 5 s (RSS 14 GB, disk 21 GB, hard stop)",
              "time_v": timev(R / "run-time.txt")},
 "seeds": [123],
 "seeds_note": "123 = serving seed (temperature 0, greedy); the CPU forward is deterministic float64, no randomness, one run (PREREG Runs)",
 "data_on_disk": "scratch outside the repo: residual state ckpt.npz, served reply text, private rebuild and per-position top-1 ids (publication rule)"}
(HERE / "ENV.json").write_text(json.dumps(env, indent=1) + "\n"); print("ENV.json written")
