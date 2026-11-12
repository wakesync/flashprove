#!/usr/bin/env python3
"""Write ENV.json from fixed facts plus whatever run logs exist (PR #138's env.py, adapted).
Usage: env.py <code commit> <status text>"""
import json, platform, re, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
prog = (R / "progress.log").read_text().splitlines() if (R / "progress.log").exists() else []
tv = (R / "run.time").read_text() if (R / "run.time").exists() else ""


def grab(k):
    m = re.findall(re.escape(k) + r":\s*(.*)", tv); return m if m else None


man = {}
for ck in ("stock", "abl"):
    f = R / f"manifest-{ck}.json"
    if f.exists():
        m = json.load(open(f)); man[ck] = dict(tensors=len(m["tensors"]), embedding_rows=len(m["embedding_rows"]))
env = {
    "experiment": "20261112-148-norm-class",
    "kind": "open-loop per-layer measurement of Qwen3.8-27B abliterated pre-norm outputs against the public class 2,047 and of three arms (clamp, smaller scale, wider class) vs a float64 forward; CPU only, no proof built",
    "status": sys.argv[2],
    "commits": {"base": "d247f4c01edc20f7317e587cc1b27ba4ae61ceae (main)", "prereg": "11b9889f04dfc1d2b35c217201444818135e1536 (first commit, alone)",
                "code": sys.argv[1], "progress_log": prog,
                "reused_unchanged": "experiments/20261112-132-int-mlp-e2e/mlp_e2e.py (PR #138); experiments/20261111-8-qwen-e2e-agreement/{e2e.py, prompts-e2e.json} (PR #124); experiments/20261110-8-qwen-q1-deep-fidelity/{q1_forward.py, arms-q1.json} (PR #88); experiments/20261110-8-qwen-norm-scaling/scaled_head.py; experiments/20261109-8-qwen-real-weights/real_head.py; research/operators/qwen_m3/bounds.py (PR #70); research/operators/qwen_ops/tables/silu-f12.i64le (PR #67)"},
    "checkpoints": {"stock": {"repo": "Qwen/Qwen3.8-27B", "revision": "37561816e66b5b9153b1b64c10968c18c1e6f4a0"},
                    "abliterated": {"repo": "huihui-ai/Huihui-Qwen3.8-27B-abliterated", "revision": "739e3c5b89849f6c238ce1e5b70008612ae42cdd"},
                    "fetched_in_registered_run": man, "token": "none",
                    "note": "weights are read into memory by HTTP range request, one layer at a time, never written to disk"},
    "toolchain": {"python": platform.python_version(), "numpy": np.__version__, "long_double": "x87 80-bit (scaled_head.py relies on it, x86-64 only)",
                  "blas": "numpy wheel BLAS; 6 threads in the main process, head workers: 6 spawned processes with 1 BLAS thread each",
                  "flags": "OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 MKL_NUM_THREADS=6, taskset -c 6-11"},
    "hardware": {"cpu": "AMD EPYC-Rome, 16 vCPU KVM VM (results.yaml key cpu-epyc-rome-kvm-16), shared with other lanes and other services, loaded",
                 "ram_gb": 30, "os": "Linux 6.8 x86_64", "gpu": "none", "provider": "self-hosted VM",
                 "pinning": "heavy work through the shared two-slot heavy gate and the big-memory lock, taskset -c 6-11",
                 "time_v": {k: grab(k) for k in ("Elapsed (wall clock) time (h:mm:ss or m:ss)", "Maximum resident set size (kbytes)", "User time (seconds)", "Percent of CPU this job got", "Exit status")}},
    "seeds": ["none for the registered run (deterministic float64 and integer arithmetic)", "debug synthetic arrays: numpy default_rng(0)"],
    "repeats": "one deterministic run registered; spread is over prompts and tokens; determinism checked by computing arm C twice on p01 and p09",
    "data_on_disk": "scratch outside the repo: ckpt.npz (the float64 reference stream of 6 prompts, about 28 MB, overwritten after every layer); no weight data in the repo or on disk",
}
(HERE / "ENV.json").write_text(json.dumps(env, indent=1) + "\n"); print("ENV.json written")
