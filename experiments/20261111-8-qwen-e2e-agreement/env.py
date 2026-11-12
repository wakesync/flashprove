#!/usr/bin/env python3
"""Write ENV.json from fixed facts plus runs/progress.log, runs/run.time and the manifests. Usage: env.py <code commit>"""
import json, platform, re, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
prog = (R / "progress.log").read_text().splitlines() if (R / "progress.log").exists() else []
tv = (R / "run.time").read_text() if (R / "run.time").exists() else ""
grab = lambda k: (re.search(re.escape(k) + r":\s*(.*)", tv).group(1).strip() if re.search(re.escape(k) + r":\s*(.*)", tv) else None)
man = {}
for ck in ("stock", "abl"):
    f = R / f"manifest-{ck}.json"
    if f.exists():
        m = json.load(open(f)); man[ck] = dict(tensors=len(m["tensors"]), embedding_rows=len(m["embedding_rows"]))
xc = json.load(open(R / "manifest-check.json")) if (R / "manifest-check.json").exists() else None
env = {
    "experiment": "20261111-8-qwen-e2e-agreement",
    "kind": "end-to-end teacher-forced token agreement of integer DeltaNet head lowerings (XS18, XS20; PR #74 engine unchanged) vs a float64 forward of Qwen3.8-27B, stock and abliterated; only the DeltaNet head computation is lowered, in_proj, out_proj, attention, MLP, norms and lm_head stay float64; CPU only, no proof built",
    "commits": {"base": "cf4b213f1fe4d1c0073e0e1266281eee7e92b79b (main)", "prereg": "436280e (first commit, alone) + wording fix before any code",
                "code_at_run": sys.argv[1], "progress_log": prog,
                "reused_unchanged": "experiments/20261110-8-qwen-q1-deep-fidelity/{q1_forward.py, arms-q1.json}, experiments/20261110-8-qwen-norm-scaling/scaled_head.py, experiments/20261109-8-qwen-real-weights/{real_head.py, prompts.json} at main cf4b213"},
    "checkpoints": {"stock": {"repo": "Qwen/Qwen3.8-27B", "revision": "37561816e66b5b9153b1b64c10968c18c1e6f4a0"},
                    "abliterated": {"repo": "huihui-ai/Huihui-Qwen3.8-27B-abliterated", "revision": "739e3c5b89849f6c238ce1e5b70008612ae42cdd"},
                    "fetched": man, "manifest_check": xc, "token": "none",
                    "note": "abl leg = stock layers 0..16 (byte-identical, PR #68 runs/diff.json) then abl layers 17..63, abl final norm and abl lm_head; weights read into memory by HTTP range request, never written to disk"},
    "toolchain": {"python": platform.python_version(), "numpy": np.__version__, "long_double": "x87 80-bit (scaled_head.py relies on it, x86-64 only)",
                  "blas": "OpenBLAS (numpy wheel), 6 threads for the dense float64 forward in the main process; head workers: 6 spawned processes, 1 BLAS thread each",
                  "tokenizers": "0.23.3, only to tokenise p11 (make_prompts_e2e.py), in a separate venv"},
    "hardware": {"cpu": "AMD EPYC-Rome, 16 vCPU KVM VM (results.yaml key cpu-epyc-rome-kvm-16), shared with other lanes and loaded (load average about 10 to 12 during the run)",
                 "ram_gb": 30, "os": "Linux 6.8 x86_64", "gpu": "none",
                 "pinning": "registered run through fp-heavy.sh, taskset -c 0-5; fixture debug through fp-heavy.sh too; summaries light, outside the gate",
                 "time_v": {k: grab(k) for k in ("Elapsed (wall clock) time (h:mm:ss or m:ss)", "Maximum resident set size (kbytes)", "User time (seconds)", "Percent of CPU this job got", "Exit status")}},
    "seeds": {"registered_run": "none (deterministic float64 and integer arithmetic)", "timing_probe": "numpy default_rng(12345) fixture ids (before PREREG, no metric)", "debug_fixture_synthetic_logits": "numpy default_rng(0)"},
    "repeats": "one deterministic run; >= 5 repeats would be identical and are not meaningful; spread over prompts and positions reported instead; determinism checked by duplicate paths REF#2 / XS18#2 on p01, p04, p09",
    "data_on_disk": "scratch outside the repo: ckpt.npz (all paths' residual states, overwritten after every layer) and x16.npz, about 0.2 GB each; no weight data in the repo",
}
(HERE / "ENV.json").write_text(json.dumps(env, indent=1) + "\n"); print("ENV.json written")
