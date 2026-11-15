#!/usr/bin/env python3
"""Capture a host-identifier-free environment manifest before fixture execution."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import numpy

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def main():
    cpu = next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
               if line.startswith("model name"))
    mem = next(line.split(":", 1)[1].strip() for line in Path("/proc/meminfo").read_text().splitlines()
               if line.startswith("MemTotal:"))
    files = ["research/weight-binding/wb_leafv2.py", "experiments/20261112-149-leaf-v2/summarise.py",
             "experiments/20261113-189-missing-metadata/reproduce.py"]
    env = dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               commits=dict(base="4991f69acbc9db0c9cd0bc80b79ad658078e3737", prereg=git("rev-parse", "HEAD")),
               toolchain=dict(python=platform.python_version(), numpy=numpy.__version__, kernel=platform.release(),
                              system=platform.system(), flags="taskset -c 10,11; OPENBLAS_NUM_THREADS=1; OMP_NUM_THREADS=1",
                              cuda="not used", compiler="not used"),
               hardware=dict(cpu=cpu, affinity=sorted(os.sched_getaffinity(0)), ram=mem,
                             gpu="not used", provider="shared CPU host", shared_and_loaded=True),
               seeds=[], note="Deterministic local file replay, no weights, network experiment calls or conversion.",
               source_sha256={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files})
    out = HERE / "ENV.json"
    with out.open("x") as stream:
        stream.write(json.dumps(env, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
