#!/usr/bin/env python3
"""Write ENV.json from fixed facts plus runs/progress.log.jsonl, runs/run.time and runs/manifest-check.json.
Usage: env.py <code commit at run>"""
import json, platform, re, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
prog = [json.loads(l) for l in (R / "progress.log.jsonl").read_text().splitlines()]
tv = (R / "run.time").read_text() if (R / "run.time").exists() else ""
def grab(k):
    m = re.search(re.escape(k) + r":\s*(.*)", tv); return m.group(1).strip() if m else None
xc = json.load(open(R / "manifest-check.json")) if (R / "manifest-check.json").exists() else None
env = {
    "experiment": "20261112-136-deltanet-decay",
    "kind": "record DeltaNet decay inputs (ar, A, dt_bias) per layer, V head and token from PR #88's float64 forward (unchanged) on the abliterated Qwen3.8-27B; integer emulation of table designs T0..T3 vs float64 decay; CPU only, no proof",
    "commits": {"base": "c810b3e998c45c14fc0c422cf3cb69ec72ab47df (main)", "prereg": "38927cf (first commit, alone)", "code_at_run": sys.argv[1],
                "reused_unchanged": "experiments/20261110-8-qwen-q1-deep-fidelity/q1_forward.py (PR #88), experiments/20261109-8-qwen-real-weights/real_head.py (PR #68), experiments/20261110-8-qwen-norm-scaling/scaled_head.py (imported by q1_forward, not used on the REF path), experiments/20261111-8-qwen-e2e-agreement/prompts-e2e.json (PR #124), research/operators/qwen_ops/tables.py and tables/softplus-f12.i64le (PR #67)",
                "progress": prog},
    "checkpoints": {"stock": {"repo": "Qwen/Qwen3.8-27B", "revision": "37561816e66b5b9153b1b64c10968c18c1e6f4a0", "used_for": "embedding rows and layers 0..16 (byte-identical in both checkpoints, PR #68)"},
                    "abliterated": {"repo": "huihui-ai/Huihui-Qwen3.8-27B-abliterated", "revision": "739e3c5b89849f6c238ce1e5b70008612ae42cdd", "used_for": "layers 17..63, final norm, lm_head (sanity check only)"},
                    "manifest_check_vs_pr124": xc, "token": "none", "note": "weights read into memory by HTTP range request, never written to disk"},
    "toolchain": {"python": platform.python_version(), "numpy": np.__version__, "blas": "OpenBLAS (numpy wheel), 6 threads, single process"},
    "hardware": {"cpu": "AMD EPYC-Rome, 16 vCPU KVM VM (results.yaml key cpu-epyc-rome-kvm-16), shared with other lanes and loaded", "ram_gb": 30, "os": "Linux 6.8 x86_64", "gpu": "none",
                 "pinning": "registered run through the host's bigmem lock then fp-heavy.sh, taskset -c 6-11; table evaluation light, outside the gate",
                 "time_v": {k: grab(k) for k in ("Elapsed (wall clock) time (h:mm:ss or m:ss)", "Maximum resident set size (kbytes)", "User time (seconds)", "Percent of CPU this job got", "Exit status")}},
    "seeds": {"registered_run": "none (deterministic float64 forward and integer table emulation)", "selftest": "numpy default_rng(1), synthetic heads only"},
    "repeats": "one deterministic forward; repeats would be identical (fixture: driver run twice bit-identical, and bit-identical to plain layer_step); spread reported over tokens, prompts and (layer, head) cells",
    "data_on_disk": "scratch outside the repo: per-layer ar arrays (about 0.3 MB per layer) and the residual state; the committed runs/ holds the per-(layer, head, prompt) tables, compressed",
}
(HERE / "ENV.json").write_text(json.dumps(env, indent=1) + "\n"); print("ENV.json written")
