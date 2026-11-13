#!/usr/bin/env python3
"""Write ENV.json from fixed facts plus runs/progress.log, runs/run.time and the manifests. Usage: env.py <code commit at run>"""
import json, platform, re, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; R = HERE / "runs"
prog = (R / "progress.log").read_text().splitlines() if (R / "progress.log").exists() else []
tv = (R / "run.time").read_text() if (R / "run.time").exists() else ""
def grab(k):
    m = re.search(re.escape(k) + r":\s*(.*)", tv); return m.group(1).strip() if m else None
man = {}
for ck in ("stock", "abl"):
    f = R / f"manifest-{ck}.json"
    if f.exists():
        m = json.load(open(f)); man[ck] = dict(tensors=len(m["tensors"]), embedding_rows=len(m["embedding_rows"]))
fx = json.load(open(R / "debug-fixture" / "fixture.json")) if (R / "debug-fixture" / "fixture.json").exists() else None
start = [json.loads(l) for l in open(R / "progress.log.jsonl") if '"start"' in l] if (R / "progress.log.jsonl").exists() else []
env = {
    "experiment": "20261113-170-decay-e2e",
    "kind": "end-to-end teacher-forced token agreement, abliterated leg, of PR #124's XS18 DeltaNet heads with the decay replaced by PR #159's U4 / U3 table emulation (shifted 2^-20 -> 2^-18, round half up), vs float64; CPU only, no proof",
    "commits": {"base": "59bff9a4608e0cc720d58d7c30823a8838fa43e4 (main)", "prereg": "ec71c8d523679036c36d7599b7e239c92231f1d3 (first commit, alone)",
                "code_at_run": sys.argv[1], "progress_log": prog,
                "reused_unchanged": "experiments/20261111-8-qwen-e2e-agreement/{e2e.py, prompts-e2e.json}, experiments/20261110-8-qwen-q1-deep-fidelity/{q1_forward.py, arms-q1.json}, experiments/20261110-8-qwen-norm-scaling/scaled_head.py (Head.run source with the one decay line substituted at import), experiments/20261113-155-deltanet-decay-r2/decay_r2.py, experiments/20261112-136-deltanet-decay/decay_tables.py, research/operators/qwen_ops/tables.py at main 59bff9a4"},
    "tables_sha256": start[0].get("tables_sha256") if start else None,
    "checkpoints": {"stock": {"repo": "Qwen/Qwen3.8-27B", "revision": "37561816e66b5b9153b1b64c10968c18c1e6f4a0"},
                    "abliterated": {"repo": "huihui-ai/Huihui-Qwen3.8-27B-abliterated", "revision": "739e3c5b89849f6c238ce1e5b70008612ae42cdd"},
                    "fetched": man, "token": "none",
                    "note": "abl leg = stock layers 0..16 (byte-identical, PR #68) then abl layers 17..63, abl final norm and lm_head; weights read into memory by HTTP range request, never written to disk"},
    "toolchain": {"python": platform.python_version(), "numpy": np.__version__, "long_double": "x87 80-bit (scaled_head.py relies on it, x86-64 only)",
                  "blas": "OpenBLAS (numpy wheel), 6 threads for the dense float64 forward in the main process; head workers: 6 spawned processes, 1 BLAS thread each"},
    "hardware": {"cpu": "AMD EPYC-Rome, 16 vCPU KVM VM (results.yaml key cpu-epyc-rome-kvm-16), shared with other lanes and loaded",
                 "ram_gb": 30, "os": "Linux 6.8 x86_64", "gpu": "none",
                 "pinning": "flock bigmem.lock + fp-heavy.sh, taskset -c 10-15 (PR #124 used 0-5); fixture and run under the same job",
                 "time_v": {k: grab(k) for k in ("Elapsed (wall clock) time (h:mm:ss or m:ss)", "Maximum resident set size (kbytes)", "User time (seconds)", "Percent of CPU this job got", "Exit status")}},
    "seeds": {"registered_run": "none (deterministic float64 and integer arithmetic)", "debug_fixture_synthetic_logits": "numpy default_rng(0)"},
    "repeats": "one deterministic run; repeats would be identical; spread over prompts and positions reported instead; determinism by duplicate paths REF#2 / XS18+U4#2 on p01, p09",
    "debug_fixture": None if fx is None else {k: fx[k] for k in ("all_ok", "save_load_equal", "resume_equal", "det_equal", "seconds")},
    "data_on_disk": "scratch outside the repo: ckpt.npz (all paths' residual states, overwritten after every layer), fine20.npy (8 MB); no weight data in the repo",
}
(HERE / "ENV.json").write_text(json.dumps(env, indent=1) + "\n"); print("ENV.json written")
