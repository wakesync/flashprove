#!/usr/bin/env python3
"""Write ENV.json from fixed facts plus runs/progress.log, runs/run.time and the manifests (PR #124's env.py, adapted).
Usage: env.py <code commit>"""
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
xc = json.load(open(R / "manifest-check.json")) if (R / "manifest-check.json").exists() else None
env = {
    "experiment": "20261112-132-int-mlp-e2e",
    "kind": "end-to-end teacher-forced token agreement with the M3 design's integer SwiGLU MLP (PR #70 DESIGN 5.5, r2) in all 64 layers and XS18 DeltaNet heads, vs a float64 forward of Qwen3.8-27B, abliterated first; in_proj, out_proj, attention, every norm and lm_head stay float64; CPU only, no proof built",
    "commits": {"base": "d96cdda066f443a9b0c0f481b30eaaf45108ae65 (main)", "prereg": "c6311ec (first commit, alone); amendment A-1 6732850 (format only)",
                "code_at_run": sys.argv[1], "progress_log": prog,
                "reused_unchanged": "experiments/20261111-8-qwen-e2e-agreement/{e2e.py, prompts-e2e.json} (PR #124), and through it experiments/20261110-8-qwen-q1-deep-fidelity/{q1_forward.py, arms-q1.json}, experiments/20261110-8-qwen-norm-scaling/scaled_head.py, experiments/20261109-8-qwen-real-weights/real_head.py; research/operators/qwen_ops/tables/silu-f12.i64le (PR #67)"},
    "checkpoints": {"stock": {"repo": "Qwen/Qwen3.8-27B", "revision": "37561816e66b5b9153b1b64c10968c18c1e6f4a0"},
                    "abliterated": {"repo": "huihui-ai/Huihui-Qwen3.8-27B-abliterated", "revision": "739e3c5b89849f6c238ce1e5b70008612ae42cdd"},
                    "fetched": man, "manifest_check": xc, "token": "none",
                    "note": "abl leg = stock layers 0..16 (byte-identical, PR #68 runs/diff.json) then abl layers 17..63; weights read into memory by HTTP range request, never written to disk"},
    "toolchain": {"python": platform.python_version(), "numpy": np.__version__, "long_double": "x87 80-bit (scaled_head.py relies on it, x86-64 only)",
                  "blas": "OpenBLAS (numpy wheel), 6 threads in the main process (float64 forward and the exact integer-valued MLP matmuls); head workers: 6 spawned processes, 1 BLAS thread each"},
    "hardware": {"cpu": "AMD EPYC-Rome, 16 vCPU KVM VM (results.yaml key cpu-epyc-rome-kvm-16), shared with other lanes and loaded (load average about 8 to 10)",
                 "ram_gb": 30, "os": "Linux 6.8 x86_64", "gpu": "none",
                 "pinning": "registered run: flock bigmem.lock + fp-heavy.sh + taskset -c 6-11; fixture debug the same",
                 "time_v": {k: grab(k) for k in ("Elapsed (wall clock) time (h:mm:ss or m:ss)", "Maximum resident set size (kbytes)", "User time (seconds)", "Percent of CPU this job got", "Exit status")},
                 "time_v_note": "one entry per process start; the first process was killed at 17:00:32Z by a restart of the agent host's session service (not by the run) and left no time -v block"},
    "seeds": {"registered_run": "none (deterministic float64 and integer arithmetic)", "debug_fixture_synthetic": "numpy default_rng(0)"},
    "repeats": "one deterministic run; >= 5 repeats would be identical and are not meaningful; spread over prompts and positions reported instead; determinism checked by the duplicate path XM18#2 on p01, p04, p09",
    "data_on_disk": "scratch outside the repo: ckpt.npz (all paths' residual states, overwritten after every layer), about 0.2 GB; no weight data in the repo",
}
(HERE / "ENV.json").write_text(json.dumps(env, indent=1) + "\n"); print("ENV.json written")
