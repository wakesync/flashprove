#!/usr/bin/env python3
"""Write ENV.json from fixed facts plus the run logs (PR #178's env.py, adapted).
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
P = json.load(open(HERE / "prompts-heldout.json"))
env = {
    "experiment": "20261114-204-int-attn-heldout",
    "kind": "open-loop held-out measurement of upstream's integer attention on the 16 full-attention layers of Qwen3.8-27B abliterated, arms C2047 and C1665, with per-layer exponents FROZEN from PR #178's runs/layers.jsonl, on 8 new prompts; CPU only, no proof built",
    "status": sys.argv[2],
    "commits": {"base": "cdde96296e658fe803711dbb1b4699a225cc544a (main; contains PR #178 merge 6b2761af95cf4dc76a275f5f9d40f183c4f2e152)",
                "prereg": "9526a68 (first commit, alone)", "manifest": "0f98cb2", "evaluator_and_tests": "cc8f850", "code": sys.argv[1],
                "progress_log": [l for l in prog if any(s in l for s in ("slot_granted", "exit", "all_done", "stop", "kill", "resume"))],
                "frozen_sources": {"int_attn.py": "experiments/20261113-176-qwen-int-attn/int_attn.py sha256 357feafac4f3d6a3786d5ab4f484cd1b69eb29a879a72bbfa48cb6bfa248d0a7 (imported unchanged)",
                                   "scale_table": "experiments/20261113-176-qwen-int-attn/runs/layers.jsonl sha256 73404d471b069f1944d4a518e7ea8544d4a2c53a17bd3d554ca0f2a677713aee (32 rows, E_q E_k E_v sh copied)"},
                "reused_unchanged": "experiments/20261110-8-qwen-q1-deep-fidelity/q1_forward.py (PR #88); experiments/20261111-8-qwen-e2e-agreement/e2e.py (PR #124); experiments/20261110-8-qwen-norm-scaling/scaled_head.py (PR #74); experiments/20261109-8-qwen-real-weights/real_head.py (PR #68)"},
    "prompts": {"file": "prompts-heldout.json", "n": P["n_prompts"], "total_tokens": P["total_tokens"], "split_sha256": P["split_sha256"],
                "tokenizer_sha256": P["tokenizer_sha256"], "tokenizers": P["tokenizers_version"] + " (scratch venv, only to tokenise; make_prompts.py)"},
    "checkpoints": {"stock": {"repo": "Qwen/Qwen3.8-27B", "revision": "37561816e66b5b9153b1b64c10968c18c1e6f4a0"},
                    "abliterated": {"repo": "huihui-ai/Huihui-Qwen3.8-27B-abliterated", "revision": "739e3c5b89849f6c238ce1e5b70008612ae42cdd"},
                    "fetched_in_registered_run": man, "manifest_check": mc, "token": "none",
                    "note": "weights read into memory by HTTP range request, one layer at a time, never written to disk"},
    "toolchain": {"python": platform.python_version(), "numpy": np.__version__,
                  "blas": "numpy wheel BLAS; 6 threads in the main process; REF DeltaNet head workers: 6 spawned processes with 1 BLAS thread each",
                  "flags": "OMP_NUM_THREADS=6 OPENBLAS_NUM_THREADS=6 MKL_NUM_THREADS=6, taskset -c 8-13"},
    "hardware": {"cpu": "AMD EPYC-Rome, 16 vCPU KVM VM (results.yaml key cpu-epyc-rome-kvm-16), shared with other lanes and other services, loaded",
                 "ram_gb": 30, "os": "Linux 6.8 x86_64", "gpu": "none", "provider": "self-hosted VM",
                 "pinning": "big-memory lock, then the shared two-slot heavy gate, taskset -c 8-13",
                 "time_v": {k: grab(k) for k in ("Elapsed (wall clock) time (h:mm:ss or m:ss)", "Maximum resident set size (kbytes)", "User time (seconds)", "Percent of CPU this job got", "Exit status")}},
    "seeds": ["none for the registered run (deterministic float64 and integer arithmetic)", "unit tests: numpy default_rng(0)"],
    "repeats": "one deterministic run registered, no reruns for variance; spread over (prompt, head) cells per layer; determinism checked by computing both arms twice on h01 and h05 at every attention layer",
    "memory_units": "memavailable_gb, rss_limit_gb, peak_tree_rss_gb, peak_rss_gb_self are decimal GB = kB (KiB) * 1024 / 1e9 (fixed vs PR #178); time -v 'kbytes' are KiB; disk_free_gb is decimal GB",
    "data_on_disk": "scratch outside the repo: ckpt.npz (REF stream of 8 prompts, overwritten per layer), deleted after the numbers were committed; no attention inputs recorded; no weight data on disk or in the repo",
}
(HERE / "ENV.json").write_text(json.dumps(env, indent=1) + "\n"); print("ENV.json written")
