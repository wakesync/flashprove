#!/usr/bin/env python3
"""Record retained wrapper harness results, without executing tests or altering evidence."""
import hashlib
import json
import pathlib
import sys

repo = pathlib.Path(__file__).resolve().parents[2]
planning = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(__file__).resolve().parent
cases = ["floods", "floods-and-goes-on", "floods-standard-output",
         "accept-at-the-bound-then-more", "bound-then-abort", "both-bounds-then-abort",
         "much-under-the-bound", "aborted", "aborted-after-accept", "time-limit",
         "signal-TERM", "signal-HUP", "signal-INT"]

def digest(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

results = {}
for version in ("baseline", "fixed"):
    root = planning / f"wrapper-{version}-work"
    calls = root / "calls"
    entries = {}
    for name in cases:
        err = calls / (name + ".err")
        stdout = calls / (name + ".out")
        text = err.read_text(errors="replace")
        entry = {"stdout": stdout.read_text(), "stdout_file": digest(stdout), "stderr_file": digest(err)}
        work = next((line.removeprefix("work directory: ") for line in text.splitlines()
                     if line.startswith("work directory: ")), None)
        if work:
            entry["lean_files"] = {file: digest(pathlib.Path(work) / file)
                                   for file in ("lean.err", "lean.out") if (pathlib.Path(work) / file).exists()}
        entry["diagnostics"] = [line[-200:] for line in text.splitlines()
                                if "timeout: the monitored command" in line or line.startswith("lean_verify.sh: no verdict:")]
        entries[name] = entry
    # Hash every raw per-call artifact, including signal process records, not merely selected cases.
    inventory = {str(path.relative_to(root)): digest(path) for path in sorted(calls.iterdir()) if path.is_file()}
    (out / (version + "-call-hashes.json")).write_text(json.dumps(inventory, indent=2) + "\n")
    results[version] = {"exit": int((out / (version + ".exit")).read_text()), "cases": entries}
# Sanitize host-specific absolute workspace paths in the portable report and console logs.
serialized = json.dumps(results, indent=2).replace(str(planning), "<PLANNING>")
(out / "results.json").write_text(serialized + "\n")
for version in ("baseline", "fixed"):
    log = out / (version + ".log")
    log.write_text(log.read_text().replace(str(planning), "<PLANNING>"))
