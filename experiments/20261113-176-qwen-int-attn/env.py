#!/usr/bin/env python3
"""Write ENV.json from fixed facts plus the run logs (PR #152's env.py, adapted).
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
mc = json.load(open(R / "manifest-check.json")) if (R / "manifest-check.json").exists() else None
env = {
    "experiment": "20261113-176-qwen-int-attn",
    "kind": "open-loop per-layer measurement of upstream's integer attention (docs/model.md 6, steps 2 clamp only, 3, 4) on the 16 full-attention layers of Qwen3.8-27B abliterated, arms C2047 and C1665, vs float64; CPU only, no proof built",
    "status": sys.argv[2],
    "commits": {"base": "59bff9a4608e0cc720d58d7c30823a8838fa43e4 (main)", "prereg": "cc31ae3 (first commit, alone)",
                "code": sys.argv[1], "progress_log": [l for l in prog if "slot_granted" in l or "exit" in l or "all_done" in l or "stop" in l or "kill" in l],
                "reused_unchanged": "experiments/20261110-8-qwen-q1-deep-fidelity/q1_forward.py (PR #88); experiments/20261111-8-qwen-e2e-agreement/{e2e.py, prompts-e2e.json} (PR #124); experiments/20261110-8-qwen-norm-scaling/scaled_head.py (PR #74); experiments/20261109-8-qwen-real-weights/real_head.py (PR #68)"},
    "checkpoints": {"stock": {"repo": "Qwen/Qwen3.8-27B", "revision": "37561816e66b5b9153b1b64c10968c18c1e6f4a0"},
                    "abliterated": {"repo": "huihui-ai/Huihui-Qwen3.8-27B-abliterated", "revision": "739e3c5b89849f6c238ce1e5b70008612ae42cdd"},
                    "fetched_in_registered_run": man, "manifest_check": mc, "token": "none",
                    "note": "weights read into memory by HTTP range request, one layer at a time, never written to disk"},
    "toolchain": {"python": platform.python_version(), "numpy": np.__version__, "long_double": "x87 80-bit (scaled_head.py, used by REF's head workers only through real_head)",
                  "blas": "numpy wheel BLAS; 6 threads in the main process; REF DeltaNet head workers: 6 spawned processes with 1 BLAS thread each",
                  "flags": "OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 MKL_NUM_THREADS=6, taskset -c 10-15"},
    "hardware": {"cpu": "AMD EPYC-Rome, 16 vCPU KVM VM (results.yaml key cpu-epyc-rome-kvm-16), shared with other lanes and other services, loaded",
                 "ram_gb": 30, "os": "Linux 6.8 x86_64", "gpu": "none", "provider": "self-hosted VM",
                 "pinning": "big-memory lock, then the shared two-slot heavy gate, taskset -c 10-15",
                 "time_v": {k: grab(k) for k in ("Elapsed (wall clock) time (h:mm:ss or m:ss)", "Maximum resident set size (kbytes)", "User time (seconds)", "Percent of CPU this job got", "Exit status")}},
    "seeds": ["none for the registered run (deterministic float64 and integer arithmetic)", "debug synthetic arrays: numpy default_rng(0)"],
    "repeats": "one deterministic run registered, no reruns for variance; spread is over (prompt, head) pairs per layer; determinism checked by computing arm C2047 twice on p01 and p09 at every attention layer",
    "data_on_disk": "scratch outside the repo: ckpt.npz (REF stream of 10 prompts, overwritten per layer) and the 16 recorded attention inputs xin-*.npz (about 0.96 GB), deleted after the numbers were committed; no weight data on disk or in the repo",
    "memory_units": "the memory fields of the run logs quoted above and in runs/ (memavailable_gb, rss_limit_gb, peak_tree_rss_gb, peak_rss_gb_self) are Linux kB (KiB) counters divided by 1e6, not GB: multiply by 1.024 for decimal GB; time -v 'kbytes' are KiB; disk_free_gb is decimal GB (RESULTS.md section 6; note added 2026-11-13 after review)",
}
(HERE / "ENV.json").write_text(json.dumps(env, indent=1) + "\n"); print("ENV.json written")
