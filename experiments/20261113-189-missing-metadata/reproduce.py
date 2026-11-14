#!/usr/bin/env python3
"""Independent scratch-copy reproduction of #189. No evidence-suite fixture helpers.

Run from the repository root with --out NEW_DIRECTORY. Only the output directory
and private temporary copies are written; committed PR #151 runs are read-only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "experiments/20261112-149-leaf-v2"
SOURCE = EXP / "runs"
CLI = ROOT / "research/weight-binding/wb_leafv2.py"
SUMMARISE = EXP / "summarise.py"
ARMS = (
    "baseline", "complete-no-meta", "cut-no-meta-tree-cache",
    "cut-meta-kept", "cut-tree-kept", "reordered-no-meta-tree-cache",
)
EXPECTED = (
    ("identical-complete", "PASS"), ("identical-complete", "PASS"),
    ("identical-partial", "PASS-SUBSET"), ("refused", "refused"),
    ("refused", "refused"), ("refused", "refused"),
)


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def hashes(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob("*")) if p.is_file()}


def stats(xs):
    return dict(n=len(xs), median=statistics.median(xs), sd=statistics.stdev(xs),
                min=min(xs), max=max(xs)) if xs else None


def make_fixture(parent, arm):
    runs = parent / "runs"
    shutil.copytree(SOURCE, runs)
    # Do not let a copied summary masquerade as a fresh output on refusal.
    (runs / "summary.json").unlink()
    run3 = runs / "run3"
    if arm != "baseline" and arm != "cut-meta-kept":
        (run3 / "run-meta.json").unlink()
    if arm.startswith("cut-") or arm.startswith("reordered-"):
        (runs / "compare-run1-run3.json").unlink()
        if arm != "cut-tree-kept":
            (run3 / "leaves-v2.json").unlink()
        path = run3 / "blocks.jsonl"
        lines = path.read_bytes().splitlines(keepends=True)
        assert all(line.endswith(b"\n") for line in lines)
        if arm.startswith("cut-"):
            lines = lines[:-1]
        else:
            lines[3], lines[40] = lines[40], lines[3]
        path.write_bytes(b"".join(lines))
    return runs


def call(args, parent):
    result = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT,
                            capture_output=True, text=True, timeout=120)
    def clean(text):
        return text.replace(str(parent), "<fixture>").replace(str(ROOT), "<repo>")
    return dict(rc=result.returncode, stdout=clean(result.stdout), stderr=clean(result.stderr))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    before = hashes(SOURCE)
    dump(args.out / "source-before.json", before)
    rows = []
    blocked = False
    try:
        for repetition in range(1, 6):
            for arm, expected in zip(ARMS, EXPECTED):
                with tempfile.TemporaryDirectory(prefix="leafv2-meta189-") as tmp:
                    parent = Path(tmp)
                    runs = make_fixture(parent, arm)
                    row = dict(repetition=repetition, arm=arm,
                               expected_compare=expected[0], expected_summary=expected[1],
                               run3_input_sha256=hashes(runs / "run3"))
                    comparison = call([CLI, "compare", runs / "run1", runs / "run3", parent / "comparison.json"], parent)
                    row["compare_process"] = comparison
                    row["comparison"] = (json.loads((parent / "comparison.json").read_text())
                                         if (parent / "comparison.json").exists() else None)
                    row["compare_status"] = ("refused" if comparison["rc"] == 2 else
                                             row["comparison"]["status"] if row["comparison"] else "error")
                    mutated = arm.startswith("cut-") or arm.startswith("reordered-")
                    if mutated and row["compare_status"] == "identical-complete":
                        row["blocking_finding"] = "truncated/reordered comparator reported full coverage"
                        blocked = True
                    else:
                        summary = call([SUMMARISE, "--runs", runs], parent)
                        row["summary_process"] = summary
                        row["summary"] = (json.loads((runs / "summary.json").read_text())
                                          if (runs / "summary.json").exists() else None)
                        row["summary_status"] = ("refused" if summary["rc"] == 2 else
                                                 row["summary"]["h3"]["overall"]["status"] if row["summary"] else "error")
                        if mutated and row["summary_status"] == "PASS":
                            row["blocking_finding"] = "truncated/reordered summary reported full PASS"
                            blocked = True
                    row["ok"] = (row["compare_status"] == expected[0] and row.get("summary_status") == expected[1]
                                 and comparison["rc"] == (2 if expected[0] == "refused" else 0)
                                 and row.get("summary_process", {}).get("rc") == (2 if expected[1] == "refused" else 0))
                    rows.append(row)
                    dump(args.out / ("rep%d-%s.json" % (repetition, arm)), row)
                    print(repetition, arm, row["compare_status"], row.get("summary_status"), flush=True)
                    if blocked:
                        return 2
    finally:
        after = hashes(SOURCE)
        dump(args.out / "source-after.json", after)
        arms = {}
        for arm in ARMS:
            selected = [r for r in rows if r["arm"] == arm]
            if not selected:
                continue
            common = [r["comparison"]["n_common"] for r in selected if r["comparison"]]
            arms[arm] = dict(n=len(selected), n_expected=sum(r["ok"] for r in selected),
                             compare_statuses=[r["compare_status"] for r in selected],
                             summary_statuses=[r.get("summary_status") for r in selected],
                             common_blocks=stats(common),
                             full_pass_indicator=stats([int(r.get("summary_status") == "PASS") for r in selected]))
        dump(args.out / "summary.json", dict(arms=arms, n_rows=len(rows), n_expected=sum(r["ok"] for r in rows),
                                             source_unchanged=before == after, blocking_finding=blocked,
                                             note="Deterministic replays of existing evidence, measured, unreplicated. Not conversion repeats or performance measurements."))
        if before != after:
            raise RuntimeError("STOP: source evidence changed")
    return 0 if len(rows) == 30 and all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
