#!/usr/bin/env python3
"""The registered evaluation (PREREG "Runs"): decay_r2.py eval on the registered arrays, timed, with a log.
usage: run_eval.py <ar_dir> <out_dir> <fine20.npy> <log.jsonl> <label>
Appends start / end lines (UTC, exit code, wall seconds, max RSS of the child) to <log.jsonl>. Paths are not logged."""
import json, resource, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(ar_dir, out_dir, fine20, log, label):
    head = subprocess.run(["git", "-C", str(HERE), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(HERE), "status", "--porcelain", "--", "decay_r2.py", "summarise_r2.py", "PREREG.md"], capture_output=True, text=True).stdout.strip()
    with open(log, "a") as fh: fh.write(json.dumps(dict(event="start", label=label, utc=now(), code_commit=head, arm_code_modified=bool(dirty))) + "\n")
    t0 = time.time()
    p = subprocess.run([sys.executable, str(HERE / "decay_r2.py"), "eval", ar_dir, out_dir, fine20], capture_output=True, text=True)
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    with open(log, "a") as fh:
        fh.write(json.dumps(dict(event="end", label=label, utc=now(), exit=p.returncode, wall_seconds=round(time.time() - t0, 1),
                                 child_max_rss_kb=ru.ru_maxrss, stderr_tail=p.stderr[-300:] if p.returncode else "")) + "\n")
    print(p.stdout[-600:]); print(p.stderr[-600:], file=sys.stderr)
    return p.returncode


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:6]))
