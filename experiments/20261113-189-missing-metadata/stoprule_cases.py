#!/usr/bin/env python3
"""Review-driven reproduction for issue #189 (PREREG amendment A-1): inputs for which a truncated,
reordered or substituted run 3 gets a full H3 PASS. HASH LEVEL, NOT A PROOF. Reader behaviour unchanged.

Written for amendment A-1. It imports neither reproduce.py nor the evidence suite, and it does not import
the reader: the reader and the summariser are called as unchanged subprocesses, and the coverage
cross-check below parses the fixture's own files with the json module only.

Every case copies the committed experiments/20261112-149-leaf-v2/runs into a private temporary directory
and alters only the copy. The committed runs are read-only; their hashes are taken before and after.

Usage (from the top of the tree):
  stoprule_cases.py --out NEW_DIRECTORY        the registered cases, five fresh copies each
  stoprule_cases.py --debug-forward-50         one unregistered fixture, prints, writes nothing

Exit status: 0 every case gave its registered expectation and the cross-check agreed with the reader;
1 at least one case differed from its registered expectation (recorded, the run continues);
3 the reader reported coverage or agreement that the files do not contain (the more serious finding,
the run stops at that replay); 4 a committed source file changed.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EXP = ROOT / "experiments/20261112-149-leaf-v2"
SOURCE = EXP / "runs"
CLI = ROOT / "research/weight-binding/wb_leafv2.py"
SUMMARISE = EXP / "summarise.py"
REPS = 5
TIMEOUT_S = 120
PINS = ("stock", "abl")


# ---------------------------------------------------------------- committed inputs
def read_lines(path):
    lines = path.read_bytes().splitlines(keepends=True)
    assert lines and all(line.endswith(b"\n") for line in lines), path
    return lines


def name_of(line):
    return json.loads(line)["name"]


def committed():
    """Lines of the three committed runs, plus run 1 and run 3 keyed by block name. Registered forward
    order is the sorted block names; run 1 is stored forward and run 3 is stored in exact reverse."""
    r1, r2, r3 = (read_lines(SOURCE / run / "blocks.jsonl") for run in ("run1", "run2", "run3"))
    names = sorted(name_of(line) for line in r1)
    assert len(names) == 78 and len(set(names)) == 78
    assert [name_of(line) for line in r1] == names
    assert [name_of(line) for line in r3] == names[::-1]
    assert [name_of(line) for line in r2] == names[::-1][:len(r2)]
    return dict(names=names, r1=r1, r2=r2, r3=r3, r3_forward=r3[::-1],
                r1_by={name_of(line): line for line in r1}, r3_by={name_of(line): line for line in r3})


def hashes(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------- fixtures
def strip_run3(runs, meta=True, tree=True, cache=True):
    if meta:
        (runs / "run3/run-meta.json").unlink()
    if tree:
        (runs / "run3/leaves-v2.json").unlink()
    if cache:
        (runs / "compare-run1-run3.json").unlink()


def put(runs, lines, run="run3"):
    (runs / run / "blocks.jsonl").write_bytes(b"".join(lines))


def edited_meta(runs, done):
    path = runs / "run3/run-meta.json"
    meta = json.loads(path.read_text())
    meta.update(done=done, reverse=False, stopped="fixture: stopped after %d blocks" % done)
    path.write_text(json.dumps(meta, indent=1, sort_keys=True))


def b_forward(k):
    def build(runs, c):
        strip_run3(runs)
        put(runs, c["r3_forward"][:k])
    return build


def b_forward_meta(k):
    def build(runs, c):
        strip_run3(runs, meta=False)
        put(runs, c["r3_forward"][:k])
        edited_meta(runs, k)
    return build


def b_run1_records(k=None):
    def build(runs, c):
        strip_run3(runs)
        put(runs, c["r1"] if k is None else c["r1"][:k])
    return build


def b_run1_dir(keep_meta):
    def build(runs, c):
        shutil.rmtree(runs / "run3")
        shutil.copytree(runs / "run1", runs / "run3")
        (runs / "compare-run1-run3.json").unlink()
        if not keep_meta:
            (runs / "run3/run-meta.json").unlink()
    return build


def b_alternate_by_name(runs, c):
    strip_run3(runs)
    put(runs, [(c["r1_by"] if i % 2 == 0 else c["r3_by"])[n] for i, n in enumerate(c["names"])])


def b_splice(runs, c):
    strip_run3(runs)
    put(runs, c["r1"][:39] + c["r3_forward"][39:70])


def b_original_cut_last(runs, c):
    strip_run3(runs)
    put(runs, c["r3"][:-1])


def b_original_cut_then_reversed(runs, c):
    strip_run3(runs)
    put(runs, c["r3"][:-1][::-1])


def b_run2_records(runs, c):
    strip_run3(runs)
    put(runs, c["r2"])


def b_alternate_by_index(runs, c):
    strip_run3(runs)
    put(runs, [(c["r1"] if i % 2 == 0 else c["r3"])[i] for i in range(78)])


def b_run2_forward(runs, c):
    put(runs, c["r2"][::-1], run="run2")


def case(name, kind, build, compare, n_common, summary, union, source):
    return dict(name=name, kind=kind, build=build, expected=dict(compare=compare, n_common=n_common,
                                                                 summary=summary, union=union), source=source)


BOTH, FIRST, SECOND, LANE = "both reviews", "first review", "second review", "this lane"
PART, FULL = "identical-partial", "identical-complete"
CASES = (
    # item 1: forward prefixes that run 2 completes
    case("forward-77", "truncated+reordered", b_forward(77), PART, 77, "PASS", 78, BOTH),
    case("forward-76", "truncated+reordered", b_forward(76), PART, 76, "PASS", 78, FIRST),
    case("forward-71", "truncated+reordered", b_forward(71), PART, 71, "PASS", 78, FIRST),
    case("forward-70", "truncated+reordered", b_forward(70), PART, 70, "PASS", 78, BOTH),
    # item 2: boundary controls
    case("forward-69", "truncated+reordered", b_forward(69), PART, 69, "PASS-SUBSET", 77, LANE),
    case("forward-60", "truncated+reordered", b_forward(60), PART, 60, "PASS-SUBSET", 68, SECOND),
    case("forward-39", "truncated+reordered", b_forward(39), PART, 39, "PASS-SUBSET", 47, FIRST),
    case("forward-10", "truncated+reordered", b_forward(10), PART, 10, "PASS-SUBSET", 18, SECOND),
    case("forward-1", "truncated+reordered", b_forward(1), PART, 1, "BELOW-COVERAGE", 9, FIRST),
    # item 3
    case("forward-78-whole", "reordered", b_forward(78), FULL, 78, "PASS", 78, BOTH),
    # items 4 to 6: substitution
    case("run1-records-as-run3", "substituted", b_run1_records(), FULL, 78, "PASS", 78, FIRST),
    case("run1-dir-as-run3-meta-kept", "substituted", b_run1_dir(True), FULL, 78, "PASS", 78, BOTH),
    case("run1-dir-as-run3-no-meta", "substituted", b_run1_dir(False), FULL, 78, "PASS", 78, SECOND),
    case("run1-first-70-as-run3", "substituted+truncated", b_run1_records(70), PART, 70, "PASS", 78, SECOND),
    # items 7 and 8: mixed sources
    case("alternate-run1-run3-by-name", "mixed sources", b_alternate_by_name, FULL, 78, "PASS", 78, FIRST),
    case("splice-run1-39-forward-run3-39-69", "mixed sources+truncated", b_splice, PART, 70, "PASS", 78, SECOND),
    # item 9: metadata edited to agree
    case("forward-77-meta-consistent", "truncated+reordered, metadata edited", b_forward_meta(77), PART, 77, "PASS", 78, FIRST),
    case("forward-70-meta-consistent", "truncated+reordered, metadata edited", b_forward_meta(70), PART, 70, "PASS", 78, SECOND),
    # item 10: controls the reviews report as not a full PASS
    case("control-original-order-cut-last", "truncated", b_original_cut_last, PART, 77, "PASS-SUBSET", 77, BOTH),
    case("control-original-cut-then-reversed", "truncated+reordered", b_original_cut_then_reversed, "refused", None, "refused", None, FIRST),
    case("control-run2-records-as-run3", "substituted", b_run2_records, PART, 8, "BELOW-COVERAGE", 8, BOTH),
    case("control-alternate-run1-run3-by-index", "mixed sources", b_alternate_by_index, "refused", None, "refused", None, FIRST),
    case("control-run2-forward-meta-kept", "run 2 reordered", b_run2_forward, FULL, 78, "refused", None, SECOND),
)
DEBUG = case("debug-forward-50", "truncated+reordered", b_forward(50), PART, 50, "PASS-SUBSET", 58, LANE)


def make_fixture(parent, c, committed_lines):
    runs = parent / "runs"
    shutil.copytree(SOURCE, runs)
    (runs / "summary.json").unlink()      # a copied summary must not pass for a fresh output on refusal
    c["build"](runs, committed_lines)
    return runs


# ---------------------------------------------------------------- the unchanged readers, as subprocesses
def call(args, parent):
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    r = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, capture_output=True, text=True,
                       timeout=TIMEOUT_S, env=env)

    def clean(text):
        return text.replace(str(parent), "<fixture>").replace(str(ROOT), "<repo>")
    return dict(rc=r.returncode, stdout=clean(r.stdout), stderr=clean(r.stderr))


def run_compare(runs, run, parent):
    out = parent / ("comparison-%s.json" % run)
    proc = call([CLI, "compare", runs / "run1", runs / run, out], parent)
    doc = json.loads(out.read_text()) if out.exists() else None
    status = "refused" if proc["rc"] == 2 else doc["status"] if doc else "error"
    return proc, doc, status


def run_summary(runs, parent):
    proc = call([SUMMARISE, "--runs", runs], parent)
    path = runs / "summary.json"
    doc = json.loads(path.read_text()) if path.exists() else None
    status = "refused" if proc["rc"] == 2 else doc["h3"]["overall"]["status"] if doc else "error"
    return proc, doc, status, (hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None)


# ---------------------------------------------------------------- own view of the fixture files (no reader)
def own_records(runs, run):
    """name -> the fields H3 compares, parsed with json only. None if the file does not parse line by line."""
    out = {}
    try:
        for line in (runs / run / "blocks.jsonl").read_bytes().splitlines():
            r = json.loads(line)
            out.setdefault(r["name"], []).append(
                dict(kind=r["kind"], **{p: (r[p]["e"], r[p]["int_sha256"], r[p]["sha256"]) for p in PINS}))
    except (ValueError, KeyError, TypeError):
        return None
    return out


def crosscheck(runs, comparisons, summary):
    """Compare what the reader reported with what the files contain. Returns (problems, facts)."""
    problems, facts = [], {}
    own = {run: own_records(runs, run) for run in ("run1", "run2", "run3")}
    union_own, union_reader = set(), set()
    for run in ("run2", "run3"):
        doc = comparisons[run]
        if doc is None:
            continue
        a, b = own["run1"], own[run]
        if a is None or b is None or any(len(v) != 1 for v in list(a.values()) + list(b.values())):
            problems.append("%s: the reader accepted files this script cannot read as one record per block" % run)
            continue
        common = sorted(set(a) & set(b))
        agree = {n: a[n][0] == b[n][0] for n in common}
        rows = {r["name"]: r["identical"] for r in doc["rows"]}
        invented = sorted(set(rows) - set(common))
        if invented:
            problems.append("%s: reader reports %d common blocks that are not in both files" % (run, len(invented)))
        if sorted(rows) != common or doc["n_common"] != len(common):
            problems.append("%s: reader common-block set differs from the files (%d vs %d)" % (run, doc["n_common"], len(common)))
        false_match = sorted(n for n in rows if rows[n] and not agree.get(n, False))
        if false_match:
            problems.append("%s: reader reports %d blocks identical whose e / int_sha256 / sha256 differ" % (run, len(false_match)))
        if doc["n_identical"] != sum(agree.values()):
            problems.append("%s: reader identical count %d, files give %d" % (run, doc["n_identical"], sum(agree.values())))
        facts[run] = dict(own_n_common=len(common), own_n_identical=sum(agree.values()),
                          reader_n_common=doc["n_common"], reader_n_identical=doc["n_identical"])
        union_own |= set(common)
        union_reader |= set(rows)
    if summary is not None:
        u = summary["h3"]["union"]
        kinds = {n: v[0]["kind"] for n, v in (own["run1"] or {}).items()}
        want = dict(n_blocks=len(union_own), n_controls=sum(kinds[n] == "control" for n in union_own),
                    n_changed=sum(kinds[n] == "changed" for n in union_own))
        got = {k: u[k] for k in want}
        if got != want or union_reader != union_own:
            problems.append("summary union %r differs from the files %r" % (got, want))
        run3_common = set(own["run1"] or {}) & set(own["run3"] or {})
        facts["union"] = dict(own=want, reader=got, blocks_in_run3_file=len(run3_common),
                              blocks_only_run2_supplies=len(union_own - run3_common))
    return problems, facts


def provenance(runs, c):
    """Which committed run each line of the fixture's run 3 file is a byte-identical copy of."""
    known = {}
    for tag in ("r1", "r2", "r3"):
        for line in c[tag]:
            known[line] = "run%s" % tag[1]
    counts = {}
    for line in (runs / "run3/blocks.jsonl").read_bytes().splitlines(keepends=True):
        src = known.get(line, "other")
        counts[src] = counts.get(src, 0) + 1
    return counts


# ---------------------------------------------------------------- one replay
def replay(c, repetition, committed_lines):
    with tempfile.TemporaryDirectory(prefix="leafv2-stoprule-") as tmp:
        parent = Path(tmp)
        runs = make_fixture(parent, c, committed_lines)
        row = dict(case=c["name"], kind=c["kind"], repetition=repetition, expected=c["expected"],
                   reported_by=c["source"],
                   run3_files=sorted(p.name for p in (runs / "run3").iterdir()),
                   run3_blocks_sha256=hashlib.sha256((runs / "run3/blocks.jsonl").read_bytes()).hexdigest(),
                   run3_lines=len((runs / "run3/blocks.jsonl").read_bytes().splitlines()),
                   run3_lines_copied_from=provenance(runs, committed_lines),
                   run2_blocks_sha256=hashlib.sha256((runs / "run2/blocks.jsonl").read_bytes()).hexdigest(),
                   run1_blocks_sha256=hashlib.sha256((runs / "run1/blocks.jsonl").read_bytes()).hexdigest())
        comparisons = {}
        for run in ("run3", "run2"):
            proc, doc, status = run_compare(runs, run, parent)
            comparisons[run] = doc
            row["compare_" + run] = dict(process=proc, status=status,
                                         result=({k: v for k, v in doc.items() if k != "rows"} if doc else None))
        proc, doc, status, sha = run_summary(runs, parent)
        row["summary"] = dict(process=proc, status=status, summary_sha256=sha, h3=(doc["h3"] if doc else None))
        problems, facts = crosscheck(runs, comparisons, doc)
        row["crosscheck"] = dict(problems=problems, facts=facts)
        e = c["expected"]
        c3 = row["compare_run3"]
        union = doc["h3"]["union"]["n_blocks"] if doc else None
        row["observed"] = dict(compare=c3["status"], n_common=(c3["result"]["n_common"] if c3["result"] else None),
                               summary=status, union=union)
        row["as_registered"] = row["observed"] == e
        row["full_pass"] = status == "PASS"
        row["full_coverage_comparator"] = c3["status"] == "identical-complete"
        return row


def stats(xs):
    xs = [x for x in xs if x is not None]
    return dict(n=len(xs), median=statistics.median(xs), sd=statistics.stdev(xs) if len(xs) > 1 else None,
                min=min(xs), max=max(xs)) if xs else None


def environment():
    def git(*args):
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()
    import numpy
    cpu = next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
               if line.startswith("model name"))
    mem = next(line.split(":", 1)[1].strip() for line in Path("/proc/meminfo").read_text().splitlines()
               if line.startswith("MemTotal:"))
    files = ["research/weight-binding/wb_leafv2.py", "experiments/20261112-149-leaf-v2/summarise.py",
             "experiments/20261113-189-missing-metadata/stoprule_cases.py"]
    return dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                commits=dict(base="4991f69acbc9db0c9cd0bc80b79ad658078e3737",
                             reviewed_head="bdc059a4c7302b8787c18c5c038468e89c5415d9",
                             amendment_a1=git("rev-parse", "HEAD")),
                toolchain=dict(python=platform.python_version(), numpy=numpy.__version__, kernel=platform.release(),
                               system=platform.system(),
                               flags="taskset -c 12,13; OPENBLAS_NUM_THREADS=1; OMP_NUM_THREADS=1",
                               cuda="not used", compiler="not used"),
                hardware=dict(cpu=cpu, affinity=sorted(os.sched_getaffinity(0)), ram=mem, gpu="not used",
                              provider="shared CPU host", shared_and_loaded=True),
                seeds=[], note="Deterministic local file replay of committed evidence. No weights, model, "
                               "conversion, network call or proof.",
                source_sha256={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files})


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path)
    group.add_argument("--debug-forward-50", action="store_true")
    args = parser.parse_args()
    lines = committed()
    if args.debug_forward_50:
        row = replay(DEBUG, 0, lines)
        print(json.dumps({k: row[k] for k in ("observed", "as_registered", "crosscheck", "run3_lines_copied_from")},
                         indent=1, sort_keys=True))
        return 0
    args.out.mkdir(parents=True, exist_ok=False)
    before = hashes(SOURCE)
    dump(args.out / "source-before.json", before)
    dump(args.out / "env.json", environment())
    rows, serious = [], False
    try:
        for repetition in range(1, REPS + 1):
            for c in CASES:
                row = replay(c, repetition, lines)
                rows.append(row)
                dump(args.out / ("rep%d-%s.json" % (repetition, c["name"])), row)
                print(repetition, c["name"], row["observed"], "as registered" if row["as_registered"] else "DIFFERS",
                      "crosscheck", "ok" if not row["crosscheck"]["problems"] else row["crosscheck"]["problems"], flush=True)
                if row["crosscheck"]["problems"]:
                    serious = True
                    return 3
    finally:
        after = hashes(SOURCE)
        dump(args.out / "source-after.json", after)
        cases = {}
        for c in CASES:
            sel = [r for r in rows if r["case"] == c["name"]]
            if not sel:
                continue
            first = sel[0]
            only2 = [r["crosscheck"]["facts"].get("union", {}).get("blocks_only_run2_supplies") for r in sel]
            cases[c["name"]] = dict(
                kind=c["kind"], reported_by=c["source"], expected=c["expected"], n=len(sel),
                n_as_registered=sum(r["as_registered"] for r in sel),
                compare_statuses=[r["observed"]["compare"] for r in sel],
                summary_statuses=[r["observed"]["summary"] for r in sel],
                common_blocks=stats([r["observed"]["n_common"] for r in sel]),
                union_blocks=stats([r["observed"]["union"] for r in sel]),
                union_blocks_only_run2_supplies=stats(only2),
                full_pass_indicator=stats([int(r["full_pass"]) for r in sel]),
                full_coverage_comparator_indicator=stats([int(r["full_coverage_comparator"]) for r in sel]),
                run3_lines=first["run3_lines"], run3_lines_copied_from=first["run3_lines_copied_from"],
                run3_files=first["run3_files"],
                crosscheck_problems=sum(len(r["crosscheck"]["problems"]) for r in sel))
        altered_full = sorted(n for n, v in cases.items()
                              if not n.startswith("control-") and v["full_pass_indicator"]["max"] == 1)
        dump(args.out / "summary.json", dict(
            cases=cases, n_cases=len(cases), n_rows=len(rows), repetitions=REPS,
            n_rows_as_registered=sum(r["as_registered"] for r in rows),
            n_rows_full_pass=sum(r["full_pass"] for r in rows),
            cases_with_full_pass_on_altered_run3=altered_full,
            stop_rule_fired=bool(altered_full),
            crosscheck_problems=sum(len(r["crosscheck"]["problems"]) for r in rows),
            reader_reported_coverage_or_agreement_absent_from_files=serious,
            source_unchanged=before == after,
            note="Issue #189 stop-rule finding, measured, unreplicated. Deterministic replays of committed evidence "
                 "through the unchanged reader and summariser; not conversion repeats, not a proof, no performance "
                 "claim. A full PASS here is real union coverage (run 2 supplies the blocks the altered run 3 "
                 "lacks, or the substituted records are real records) with provenance the reader cannot check; "
                 "it is not a desired contract."))
        if before != after:
            sys.exit(4)
    return 0 if len(rows) == REPS * len(CASES) and all(r["as_registered"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
