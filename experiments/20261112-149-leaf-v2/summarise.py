#!/usr/bin/env python3
"""Summarise the committed runs of 20261112-149-leaf-v2 into runs/summary.json. Reads committed run files only.

Evidence handling (changed after review round 1 of PR #151, PREREG amendment A-3; no number changed):
- Records come through the one validated loader, wb_leafv2.load_records. Duplicate records (identical ones
  too), unknown names, wrong kinds, inconsistent derived flags, a record count or order that disagrees with
  run-meta.json, and a stored leaves-v2.json that is not the tree of its records are refused: this script
  then exits 2 and writes nothing.
- H3 is recomputed here from the run files (wb_leafv2.compare_runs: canonical leaf JSON per block, trees
  rebuilt from the records). The committed runs/compare-run1-*.json files are not trusted as a cache: each
  must agree with the recomputation on every field it has, or the script refuses.
- h3.overall is the explicit H3 result on the union of run 2 and run 3 (PREREG A-1): PASS (all 78 blocks
  covered, no mismatch), PASS-SUBSET (the registered reduced coverage: at least 10 blocks with at least 2
  controls and 5 changed, no mismatch), BELOW-COVERAGE (less than that, no mismatch) or FAIL (any mismatch
  in a block, a root, a subset id or a stored tree file).

Registered mode (issue #203, experiments/20261114-203-leafv2-registered-pin; opt-in, the default output and
exit codes are exactly as before):
- `--registered` first checks run1, run2, run3 and the two pinned compare files against the committed pin
  runs/registered-pins.json (wb_leafv2.check_registered): a missing, extra-consumed, symlinked or changed
  file is refused (exit 2). The pin is a committed list that binds "registered run" to what the repository
  holds; it is NOT authentication.
- It adds h3.overall.basis: "single-run" when run 2 or run 3 alone has every block of the union in common
  with run 1, else "union". PASS requires basis single-run and all registered blocks; a union that reaches
  all registered blocks with no single run doing so is PASS-UNION, not PASS.
- It writes runs/summary-registered.json (runs/summary.json is not touched); --check compares with that file.
- Read once (PREREG amendment A-1 of that experiment, after review round 1 of PR #205): in registered mode
  each pinned file (the runs' blocks.jsonl / run-meta.json / leaves-v2.json and the two compare files) is
  read exactly once by the pin check (wb_leafv2.read_registered, read_registered_compare_files). The records,
  the stored tree and the compare files are parsed from those checked bytes; no pinned path is opened,
  stat'ed or listed again. The pin file is read once and its reported hash is the hash of the parsed bytes.
- Command line (amendment A-2): any argument other than --registered, --check and --runs DIR is refused
  (exit 2, message starting USAGE:), and so is --runs without a directory or with one that starts with --.

Usage (from the top of the tree):
  python3 experiments/20261112-149-leaf-v2/summarise.py                 write runs/summary.json
  python3 experiments/20261112-149-leaf-v2/summarise.py --registered    pin check, basis, PASS-UNION;
                                                                         write runs/summary-registered.json
  python3 experiments/20261112-149-leaf-v2/summarise.py --check         recompute and compare with the committed
                                                                         runs/summary.json, write nothing
  python3 experiments/20261112-149-leaf-v2/summarise.py --runs DIR      summarise a copy of runs/ (tests)
Exit status: 0 ok, 1 --check found a difference, 2 evidence refused or command line not understood (message
on stderr)."""
import hashlib, json, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE / "runs"
sys.path.insert(0, str(HERE.parent.parent / "research/weight-binding"))
import wb_leafv2 as lv  # noqa: E402

RUNS = ("run1", "run2", "run3")
REGISTERED = False      # set by --registered (issue #203)
REG = None              # registered mode only: the one registered read (pin, pin hash, runs, compare files)


def load(run):
    """Validated records of a run, in file order. [] if the run directory does not exist.
    Registered mode: parsed from the bytes the pin check read, never from the directory again."""
    if REGISTERED:
        snap = REG["runs"][run]
        recs = lv.load_records(snap)
        if "leaves-v2.json" in snap.files:
            lv.load_leaves(snap, recs)
        return list(recs.values())
    d = D / run
    if not d.exists():
        return []
    recs = lv.load_records(d)
    if (d / "leaves-v2.json").exists():
        lv.load_leaves(d, recs)
    return list(recs.values())


def stats(xs):
    xs = list(xs)
    if not xs:
        return None
    return dict(n=len(xs), median=statistics.median(xs), sd=(statistics.stdev(xs) if len(xs) > 1 else None),
                min=min(xs), max=max(xs))


def summ(recs):
    ch = [r for r in recs if r["kind"] == "changed"]
    ct = [r for r in recs if r["kind"] == "control"]
    sha_ok = sum(r[p]["sha_matches_68"] for r in recs for p in ("stock", "abl"))
    fam = {}
    for r in ch:
        f = r["name"].split(".", 4)[-1]
        fam.setdefault(f, []).append(r)
    by_fam = {}
    for f, rs in sorted(fam.items()):
        fr = [r["int_fraction_differing"] for r in rs if r.get("int_entries_differing") is not None]
        by_fam[f] = dict(n=len(rs), int_sha_differ=sum(not r["int_sha256_equal"] for r in rs),
                         e_equal=sum(r["e_equal"] for r in rs), int_fraction_differing=stats(fr),
                         max_abs_int_delta=stats([r["max_abs_int_delta"] for r in rs if r.get("max_abs_int_delta") is not None]))
    fr_all = [r["int_fraction_differing"] for r in ch if r.get("int_entries_differing") is not None]
    return dict(
        n_blocks=len(recs), n_changed=len(ch), n_controls=len(ct),
        h1_sha_matches_68=sha_ok, h1_total=2 * len(recs),
        h2_controls_identical=sum(r["e_equal"] and r["int_sha256_equal"] for r in ct),
        h2_controls_zero_int_diff=sum(r.get("int_entries_differing") == 0 for r in ct),
        h2_changed_int_sha_differ=sum(not r["int_sha256_equal"] for r in ch),
        h2_changed_e_equal=sum(r["e_equal"] for r in ch),
        h2_changed_e_differ=[dict(name=r["name"], stock=r["stock"]["e"], abl=r["abl"]["e"]) for r in ch if not r["e_equal"]],
        h2_changed_zero_int_diff=[r["name"] for r in ch if r.get("int_entries_differing") == 0],
        int_fraction_differing_changed=stats(fr_all),
        int_entries_differing_changed=stats([r["int_entries_differing"] for r in ch if r.get("int_entries_differing") is not None]),
        by_family=by_fam,
        exponents_stock=sorted({r["stock"]["e"] for r in recs}),
        fetch_s=stats([r[p]["fetch_s"] for r in recs for p in ("stock", "abl")]),
        convert_s=stats([r[p]["convert_s"] for r in recs for p in ("stock", "abl")]),
        rss_max_kb=max((r["rss_max_kb"] for r in recs), default=None),
        free_disk_min=min((r["free_disk"] for r in recs), default=None),
    )


def h3_block(present):
    """H3 recomputed from the run files; the committed compare files must agree with the recomputation."""
    n_registered = len(lv.registered()[0])
    h3, union, union_ok, mismatch, cached_files = {}, set(), True, False, {}
    for other in ("run2", "run3"):
        cached = D / ("compare-run1-%s.json" % other)
        # registered mode: the compare file's bytes were read once by the pin check; presence = the checked set
        cached_raw = REG["compare_files"].get(cached.name) if REGISTERED else None
        cached_there = (cached_raw is not None) if REGISTERED else cached.exists()
        if other not in present:
            if cached_there:
                raise lv.EvidenceError("%s exists but %s has no run directory: a comparison without its run" % (cached, other))
            continue
        if REGISTERED:
            c = lv.compare_registered(REG["runs"]["run1"], REG["runs"][other])
        else:
            c = lv.compare_runs(D / "run1", D / other)
        c.pop("registered_pin_sha256", None)
        if cached_there:
            try:
                old = json.loads(cached_raw.decode("utf-8") if REGISTERED else cached.read_text())
            except ValueError as ex:
                raise lv.EvidenceError("%s: not valid JSON (%s)" % (cached, ex))
            bad = sorted(k for k in old if k not in c or old[k] != c[k]) if isinstance(old, dict) else ["(not an object)"]
            if bad:
                raise lv.EvidenceError("%s: stale or altered, it disagrees with the comparison recomputed from the "
                                       "run files on %s" % (cached, ", ".join(bad)))
            cached_files[cached.name] = dict(sha256=hashlib.sha256(cached_raw if REGISTERED else cached.read_bytes()).hexdigest(),
                                             agrees_with_recomputation=True)
        h3[other] = {k: v for k, v in c.items() if k != "rows"}
        for r in c["rows"]:
            union.add((r["name"], r["kind"]))
            union_ok &= r["identical"]
        mismatch |= c["status"] == "mismatch"
    if not h3:
        return None
    n = len(union)
    nc = sum(1 for _, k in union if k == "control")
    nch = sum(1 for _, k in union if k == "changed")
    all_identical = bool(union_ok and not mismatch)
    single = any(h3[o]["n_common"] == n for o in h3)        # one run alone covers the whole union
    if not all_identical:
        status = "FAIL"
    elif n == n_registered and REGISTERED and not single:
        status = "PASS-UNION"
    elif n == n_registered:
        status = "PASS"
    elif n >= 10 and nc >= 2 and nch >= 5:
        status = "PASS-SUBSET"
    else:
        status = "BELOW-COVERAGE"
    h3["union"] = dict(n_blocks=n, n_controls=nc, n_changed=nch, all_identical=all_identical,
                       note="PREREG amendment A-1: H3 on the union of run2 and run3, each vs run1")
    h3["overall"] = dict(
        status=status, n_registered=n_registered,
        rule="FAIL on any mismatch (block leaf, fetched-bytes hash, root, subset id, stored tree file); PASS when the "
             "union covers all registered blocks; PASS-SUBSET at the registered reduced coverage (>= 10 blocks, >= 2 "
             "controls, >= 5 changed); otherwise BELOW-COVERAGE",
        evidence="recomputed from validated run files by wb_leafv2.compare_runs; stored trees must equal the trees "
                 "rebuilt from the records; committed compare files must agree with the recomputation",
        committed_compare_files=cached_files)
    if REGISTERED:
        h3["overall"]["basis"] = "single-run" if single else "union"
        h3["overall"]["registered"] = dict(
            pin="runs/registered-pins.json", pin_sha256=REG["pin_sha256"],
            rule="issue #203: every run and pinned compare file matched the committed pin before H3 was computed; PASS "
                 "needs basis single-run and all registered blocks, a union-assembled full coverage is PASS-UNION",
            note="the pin is a committed list binding 'registered run' to what the repository holds, NOT authentication")
    return h3


def build():
    out = {"note": "summary of committed run files, hash level, NOT A PROOF; measured, unreplicated"}
    global REG
    REG = None
    if REGISTERED:
        pin, pin_sha = lv.read_pin()        # one read of the pin; every pinned file below is read once
        REG = dict(pin_sha256=pin_sha, runs={run: lv.read_registered(D / run, pin) for run in RUNS},
                   compare_files=lv.read_registered_compare_files(D, pin))
    recs_by_run = {run: load(run) for run in RUNS}
    if not recs_by_run["run1"]:
        raise lv.EvidenceError("%s: run1 has no records; every hypothesis is read against run 1" % (D / "run1"))
    for run in RUNS:
        recs = recs_by_run[run]
        if recs:
            out[run] = summ(recs)
            out[run + "_per_tensor"] = [dict(name=r["name"], kind=r["kind"], e_stock=r["stock"]["e"], e_abl=r["abl"]["e"],
                                             int_sha256_stock=r["stock"]["int_sha256"], int_sha256_abl=r["abl"]["int_sha256"],
                                             int_entries_differing=r.get("int_entries_differing"),
                                             int_fraction_differing=r.get("int_fraction_differing"),
                                             max_abs_int_delta=r.get("max_abs_int_delta"), elements=r["elements"])
                                        for r in recs] if run == "run1" else None
    # Not registered (descriptive cross-check): PR #87's committed integer hashes for its 7 tensors.
    p87 = HERE.parent / "20261110-36-weight-binding/runs/h2h3-int.json"
    r1 = {r["name"]: r for r in recs_by_run["run1"]}
    if p87.exists() and r1:
        rows = []
        for t in json.load(open(p87))["tensors"]:
            r = r1.get(t["name"])
            if r:
                rows.append(dict(name=t["name"],
                                 e_equal=(t["exponent"]["stock"] == r["stock"]["e"] and t["exponent"]["abl"] == r["abl"]["e"]),
                                 int_sha256_equal=(t["int_sha256"]["stock"] == r["stock"]["int_sha256"]
                                                   and t["int_sha256"]["abl"] == r["abl"]["int_sha256"]),
                                 int_entries_differing_equal=(t["int_entries_differing"] == r.get("int_entries_differing"))))
        out["crosscheck_pr87"] = dict(note="not registered; PR 87 runs/h2h3-int.json vs run1", n=len(rows),
                                      all_equal=all(x["e_equal"] and x["int_sha256_equal"] and x["int_entries_differing_equal"] for x in rows),
                                      rows=rows)
    h3 = h3_block({run for run in RUNS if recs_by_run[run]})
    if h3:
        out["h3"] = h3
    return {k: v for k, v in out.items() if v is not None}


def usage_error(args):
    """None for a command line this script understands, else a message (PREREG amendment A-2 of #203)."""
    i = 0
    while i < len(args):
        x = args[i]
        if x == "--runs":
            if i + 1 >= len(args) or args[i + 1].startswith("--"):
                return "--runs needs a directory (one that does not start with --)"
            i += 1
        elif x not in ("--registered", "--check"):
            return "unknown argument %r" % (x,)
        i += 1
    return None


def main(args=()):
    global D, REGISTERED
    args = list(args)
    bad = usage_error(args)
    if bad:
        print("USAGE: summarise.py [--registered] [--check] [--runs DIR]: %s. Nothing was read or written." % bad,
              file=sys.stderr)
        return 2
    if "--runs" in args:
        D = Path(args[args.index("--runs") + 1]).resolve()
    REGISTERED = "--registered" in args
    out = build()
    text = json.dumps(out, indent=1, sort_keys=True) + "\n"
    target = D / ("summary-registered.json" if REGISTERED else "summary.json")
    if "--check" in args:
        same = target.exists() and target.read_text() == text
        print(target.name, "matches the recomputation" if same else "DIFFERS from the recomputation")
        return 0 if same else 1
    target.write_text(text)
    for run in RUNS:
        if run in out:
            print(run, json.dumps({k: v for k, v in out[run].items() if k not in ("by_family",)}, sort_keys=True))
    if "h3" in out:
        print("h3", json.dumps(out["h3"], sort_keys=True))
    if "crosscheck_pr87" in out:
        print("crosscheck_pr87", out["crosscheck_pr87"]["n"], out["crosscheck_pr87"]["all_equal"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except lv.EvidenceError as ex:
        print("REFUSED:", ex, file=sys.stderr)
        sys.exit(2)
