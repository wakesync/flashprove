#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Write ENV.json for 20261111-9-client-envelope from the host and the registered run summary."""

import json
import os
import pathlib
import platform
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent


def out(*words):
    return subprocess.run(words, capture_output=True, text=True).stdout.strip()


def main():
    summ = json.loads((HERE / "runs" / "registered" / "summary.json").read_text())
    mem = next(int(line.split()[1]) for line in open("/proc/meminfo")
               if line.startswith("MemTotal"))
    cpu = next(line.split(":", 1)[1].strip() for line in open("/proc/cpuinfo")
               if line.startswith("model name"))
    env = {
        "commits": {
            "base": "cf4b213f1fe4d1c0073e0e1266281eee7e92b79b",
            "prereg": "66951011f0c780bc68f440c8d7affd9145ca28ff",
            "prereg_count_fix": "2fc685b67018ac8866f65c29edf058347eec5d6a",
            "code_vectors_amendment_1": "d4856a4ce61481ec66e495d198cb50a9f47b96b4",
            "note": "the registered run executed the client, runner and vectors at d4856a4, pushed "
                    "before the run started",
        },
        "toolchain": {
            "python": platform.python_version(),
            "compiler": out("g++", "--version").splitlines()[0],
            "platform": platform.system(),
            "kernel": platform.release(),
            "cp_verify_build_digest": "ea191b014747c2c6c5c3c4622a06fa51bbda1c2591b314678c717f351663bd66",
            "cp_verify_binary_sha256": summ["cp_verify_sha256"],
            "cp_verify_built_by": "verifier/build.sh (default flags), before the run",
            "ed25519": "tools/manifest/ed25519.py (pure Python, RFC 8032)",
        },
        "hardware": {
            "key": "cpu-epyc-rome-kvm-16", "cpu": cpu, "logical_cpus": os.cpu_count(),
            "memory_kib": mem, "affinity": "taskset -c 13-15 (3 cores)",
            "shared_loaded_host": True, "exclusive_core": False, "heavy_gate": True,
            "heavy_gate_note": "run through the host's two-slot heavy-job gate; times are "
                               "diagnostic only", "gpu": False,
        },
        "seeds": {"note": "no random seeds: keys and nonces are SHA-256 of fixed public labels "
                          "(make_vectors.py, label 'registered'); client clock injected per step",
                  "label": "registered", "debug_label_not_evidence": "debug"},
        "run": {"started_utc": summ["granted_utc"], "finished_utc": summ["finished_utc"],
                "elapsed_seconds": summ["elapsed_s"], "budget_seconds": summ["budget_s"],
                "killed": summ["killed"], "repetitions": summ["runs_planned"],
                "cp_verify_threads": 1, "vectors": summ["vectors"],
                "vector_sums_sha256": summ["vector_sums_sha256"]},
        "inputs": {
            "examples/accepted-proof/example.proof": out("sha256sum", str(REPO / "examples/accepted-proof/example.proof")).split()[0],
            "examples/accepted-proof-clipped-gap/example.proof": out("sha256sum", str(REPO / "examples/accepted-proof-clipped-gap/example.proof")).split()[0],
        },
    }
    (HERE / "ENV.json").write_text(json.dumps(env, indent=2, sort_keys=False) + "\n")
    print("wrote ENV.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
