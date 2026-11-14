#!/usr/bin/env python3
"""Evidence-handling regression tests for conversion leaf v2 (issue #149, PR #151 review round 1).
HASH LEVEL, NOT A PROOF. No network, no weights, no new run of the registered experiment.

Every case copies the committed run files of experiments/20261112-149-leaf-v2/runs into a temporary
directory, alters the copy the way a reviewer did (or a closely related way), and asks the three readers
of that evidence what they make of it:
  compare    wb_leafv2.compare_runs(run1, <run>)            the H3 comparison
  suite      test_wb_leafv2.py <run>                        the hostile-opening suite (H4)
  summarise  experiments/20261112-149-leaf-v2/summarise.py  the summary and the overall H3 status
Each reader must either refuse the altered copy (EvidenceError, exit 2) or report the difference
(compare status "mismatch" / partial coverage, summary status other than PASS). An altered copy that a
reader accepts as the full passing result is a test failure. The committed files themselves must pass
unchanged (case "baseline"), and the regenerated summary must equal the committed runs/summary.json.
Issue #189 additionally pins optional metadata: removing only metadata from a complete run is accepted;
a line-boundary cut with metadata/tree/cache absent is partial, not a full PASS. These cases document
current behavior, not a recommendation to accept metadata-free evidence as a registered stopped run.
Issue #189 stop-rule finding (2026-11-14, found in review of PR #191): the sentence above about an altered
copy never being accepted as the full passing result does not hold in general. The cases named
"stop-rule-189-..." at the end pin inputs for which a truncated, reordered or substituted run 3 gets a full
H3 PASS: H3 is reported on the union of run 2 and run 3, and the reader cannot check where records came
from. Those cases record CURRENT behaviour as a known blocking finding. They are not a contract the reader
should keep, and a separately registered change of the reader is expected to change them.

Usage (from the top of the tree): test_wb_leafv2_evidence.py [out.json]     exit 0 iff every expectation holds
"""
import contextlib, copy, hashlib, io, json, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wb_leafv2 as lv  # noqa: E402

ROOT = HERE.parent.parent
EXP = ROOT / "experiments/20261112-149-leaf-v2"
SRC = EXP / "runs"
SUMM = str(EXP / "summarise.py")
SUITE = str(HERE / "test_wb_leafv2.py")
CLI = str(HERE / "wb_leafv2.py")
CMP = {"run2": "compare-run1-run2.json", "run3": "compare-run1-run3.json"}
RES = []
TMP = None


# ---------------------------------------------------------------- fixture helpers
def fixture(tag):
    runs = TMP / tag / "runs"
    for run in ("run1", "run2", "run3"):
        shutil.copytree(SRC / run, runs / run)
    for f in CMP.values():
        shutil.copy2(SRC / f, runs / f)
    return runs


def lines(runs, run="run3"):
    return (runs / run / "blocks.jsonl").read_text().splitlines()


def put(runs, ls, run="run3"):
    (runs / run / "blocks.jsonl").write_text("".join(l + "\n" for l in ls))


def recs(runs, run="run3"):
    return [json.loads(l) for l in lines(runs, run)]


def put_recs(runs, rs, run="run3"):
    put(runs, [json.dumps(r, sort_keys=True) for r in rs], run)


def first(rs, kind):
    return next(i for i, r in enumerate(rs) if r["kind"] == kind)


def flip(h, i=0):
    return h[:i] + ("0" if h[i] != "0" else "1") + h[i + 1:]


def leaves(runs, run="run3"):
    return json.loads((runs / run / "leaves-v2.json").read_text())


def put_leaves(runs, d, run="run3"):
    (runs / run / "leaves-v2.json").write_text(json.dumps(d, indent=1, sort_keys=True) + "\n")


def e_plus_1_consistent(r, pin="stock"):
    """Change e in one pin and make every derived field follow, as a runner that really saw that e would."""
    r[pin]["e"] += 1
    r["e_equal"] = False
    r.pop("int_fraction_differing")
    r.pop("max_abs_int_delta")
    r["int_entries_differing"] = None


def rebuild(runs, run="run3"):
    """Rebuild the stored tree and the compare file of an altered run, so only the records disagree with run1."""
    with contextlib.redirect_stdout(io.StringIO()):
        lv.tree(str(runs / run))
        lv.compare(str(runs / "run1"), str(runs / run), str(runs / CMP[run]))


def recompare(runs, run="run3"):
    with contextlib.redirect_stdout(io.StringIO()):
        lv.compare(str(runs / "run1"), str(runs / run), str(runs / CMP[run]))


# ---------------------------------------------------------------- the three readers
def py(args):
    return subprocess.run([sys.executable] + args, capture_output=True, text=True, cwd=str(ROOT))


def r_compare(runs, run="run3"):
    try:
        d = lv.compare_runs(runs / "run1", runs / run)
        return d["status"], d
    except lv.EvidenceError as ex:
        return "refused", str(ex)


def r_suite(runs, run="run3"):
    out = runs / ("suite-%s.json" % run)
    r = py([SUITE, str(runs / run), str(out)])
    if r.returncode == 2:
        return "refused", r.stderr
    return ("pass" if r.returncode == 0 else "check-failed"), (json.loads(out.read_text()) if out.exists() else r.stderr)


def r_summarise(runs, run=None):
    r = py([SUMM, "--runs", str(runs)])
    if r.returncode == 2:
        return "refused", r.stderr
    if r.returncode != 0:
        return "error", r.stderr
    s = json.loads((runs / "summary.json").read_text())
    return s.get("h3", {}).get("overall", {}).get("status", "no-h3"), s


READERS = {"compare": r_compare, "suite": r_suite, "summarise": r_summarise}


def clean(msg):
    return " ".join(str(msg).replace(str(TMP), "<fixture>").replace(str(ROOT), "<repo>").split())[:300]


def expect(case, runs, reader, outcome, reason=None, run="run3", also=None):
    got, detail = READERS[reader](runs, run)
    ok = got == outcome
    why = ""
    if got in ("refused", "error", "check-failed") and isinstance(detail, str):
        why = clean(detail)
        if reason is not None and reason not in detail:
            ok = False
    elif reason is not None:
        ok = False
    if ok and also is not None:
        ok = bool(also(detail))
    RES.append(dict(case=case, reader=reader, run=run, expected=outcome, expected_reason=reason, got=got, reason=why, ok=ok))
    return detail


def refused_by_all(case, runs, reason, run="run3", suite=True):
    expect(case, runs, "compare", "refused", reason, run)
    if suite:
        expect(case, runs, "suite", "refused", reason, run)
    expect(case, runs, "summarise", "refused", reason, run)


# ---------------------------------------------------------------- cases
def main(outp=None):
    global TMP
    with tempfile.TemporaryDirectory(prefix="wb-leafv2-evidence-") as tmp:
        TMP = Path(tmp)
        cases()
    npass = sum(r["ok"] for r in RES)
    out = dict(note="evidence-handling regression tests for leaf v2 run files (review round 1 of PR 151); altered copies of "
                    "the committed run files must be refused or reported as different, never accepted as the passing result; "
                    "hash level, NOT A PROOF",
               n_cases=len({r["case"] for r in RES}), n_checks=len(RES), n_pass=npass, results=RES)
    out["note_189"] = ("issue #189 stop-rule finding: the cases named stop-rule-189-* pin CURRENT behaviour, including "
                       "altered copies of run 3 that get a full H3 PASS on the union with run 2 or by substitution; "
                       "a blocking finding about what the reader can check, not a contract")
    if outp:
        with open(outp, "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
            f.write("\n")
    for r in RES:
        if not r["ok"]:
            print("FAIL", json.dumps(r, sort_keys=True))
    print("leafv2 evidence tests %d / %d pass (%d cases)" % (npass, len(RES), out["n_cases"]))
    return npass == len(RES)


def cases():
    committed_suite_sha = hashlib.sha256((SRC / "run1/tests-1.json").read_bytes()).hexdigest()

    # ---- the committed files, unaltered, must pass everywhere and reproduce the committed outputs
    runs = fixture("baseline")
    expect("baseline", runs, "compare", "identical-complete",
           also=lambda d: d["n_identical"] == 78 and all(d["roots_equal"].values()) and all(d["ids_equal"].values())
           and d["leaves_file_sha256_equal"] is True)
    expect("baseline", runs, "compare", "identical-partial", run="run2",
           also=lambda d: d["n_common"] == 8 and d["n_identical"] == 8 and "roots_equal" not in d)
    for run in ("run1", "run3"):
        expect("baseline", runs, "suite", "pass", run=run,
               also=lambda d, run=run: d["n_pass"] == 38 and d["n_checks"] == 38 and
               hashlib.sha256((runs / ("suite-%s.json" % run)).read_bytes()).hexdigest() == committed_suite_sha)
        (runs / ("suite-%s.json" % run)).unlink()
    expect("baseline", runs, "summarise", "PASS",
           also=lambda s: s["h3"]["union"] == dict(n_blocks=78, n_controls=8, n_changed=70, all_identical=True,
                                                    note=s["h3"]["union"]["note"])
           and (runs / "summary.json").read_bytes() == (SRC / "summary.json").read_bytes())
    for f in CMP.values():       # the recomputed comparison reproduces every field of the committed compare files
        old = json.loads((SRC / f).read_text())
        new = lv.compare_runs(SRC / "run1", SRC / f[len("compare-run1-"):-len(".json")])
        RES.append(dict(case="baseline", reader="compare", run=f, expected="committed fields reproduced", expected_reason=None,
                        got="committed fields reproduced" if all(new.get(k) == v for k, v in old.items()) else "differs",
                        reason="", ok=all(new.get(k) == v for k, v in old.items())))
    r = py([SUMM, "--check"])
    RES.append(dict(case="baseline", reader="summarise --check", run="committed", expected="rc 0", expected_reason=None,
                    got="rc %d" % r.returncode, reason="", ok=r.returncode == 0))

    # ---- duplicate records (Astra must-fix 1; opus nonblocking 1)
    runs = fixture("dup-identical-control-first")        # Astra: identical duplicated control
    ls = lines(runs)
    put(runs, [ls[first(recs(runs), "control")]] + ls)
    refused_by_all("dup-identical-control-first", runs, "duplicate record")

    runs = fixture("dup-identical-control-last")         # opus: exact duplicate line appended
    ls = lines(runs)
    put(runs, ls + [ls[first(recs(runs), "control")]])
    refused_by_all("dup-identical-control-last", runs, "duplicate record")

    runs = fixture("dup-conflicting-control-first")      # Astra: control with stock e + 1 prepended, honest record later
    ls = lines(runs)
    bad = json.loads(ls[first(recs(runs), "control")])
    bad["stock"]["e"] += 1
    put(runs, [json.dumps(bad, sort_keys=True)] + ls)
    refused_by_all("dup-conflicting-control-first", runs, "e_equal")

    runs = fixture("dup-conflicting-consistent-first")   # same, with every derived field made to follow the changed e
    ls = lines(runs)
    bad = json.loads(ls[first(recs(runs), "control")])
    e_plus_1_consistent(bad)
    put(runs, [json.dumps(bad, sort_keys=True)] + ls)
    refused_by_all("dup-conflicting-consistent-first", runs, "duplicate record")

    runs = fixture("dup-conflicting-consistent-last")
    ls = lines(runs)
    bad = json.loads(ls[first(recs(runs), "control")])
    e_plus_1_consistent(bad)
    put(runs, ls + [json.dumps(bad, sort_keys=True)])
    refused_by_all("dup-conflicting-consistent-last", runs, "duplicate record")

    for where in ("first", "last"):                      # opus: corrupted copy (int_sha256 all zero) before / after the honest one
        case = "dup-zero-int-hash-%s" % where
        runs = fixture(case)
        ls = lines(runs)
        bad = json.loads(ls[first(recs(runs), "control")])
        bad["stock"]["int_sha256"] = "0" * 64
        b = json.dumps(bad, sort_keys=True)
        put(runs, [b] + ls if where == "first" else ls + [b])
        # the copy is refused on its own (its int_sha256_equal flag no longer follows from its fields),
        # before the duplicate check is reached; the consistent variants above reach the duplicate check
        refused_by_all(case, runs, "int_sha256_equal")

    runs = fixture("dup-in-partial-run2")                # the legitimate partial run must not hide a duplicate either
    ls = lines(runs, "run2")
    put(runs, ls + [ls[0]], "run2")
    expect("dup-in-partial-run2", runs, "compare", "refused", "duplicate record", run="run2")
    expect("dup-in-partial-run2", runs, "summarise", "refused", "duplicate record", run="run2")

    # ---- stored tree altered, records untouched (Astra must-fix 2; opus leaves tamper)
    runs = fixture("leaf-byte-flip")                     # Astra: one hex character of a stored stock leaf's int_sha256
    d = leaves(runs)
    d["pins"]["stock"]["leaves"][0]["int_sha256"] = flip(d["pins"]["stock"]["leaves"][0]["int_sha256"])
    put_leaves(runs, d)
    refused_by_all("leaf-byte-flip", runs, "stored tree is not the tree rebuilt")

    runs = fixture("swap-leaf-objects")                  # Astra: two stored leaf objects swapped
    d = leaves(runs)
    ll = d["pins"]["stock"]["leaves"]
    ll[0], ll[1] = ll[1], ll[0]
    put_leaves(runs, d)
    refused_by_all("swap-leaf-objects", runs, "stored tree is not the tree rebuilt")

    runs = fixture("leaf-e-plus-1")                      # opus: stored leaf e + 1, root untouched
    d = leaves(runs)
    d["pins"]["stock"]["leaves"][0]["e"] += 1
    put_leaves(runs, d)
    refused_by_all("leaf-e-plus-1", runs, "stored tree is not the tree rebuilt")

    runs = fixture("stored-root-changed")                # stored root string changed, leaves untouched
    d = leaves(runs)
    d["pins"]["abl"]["root"] = flip(d["pins"]["abl"]["root"], 5)
    put_leaves(runs, d)
    refused_by_all("stored-root-changed", runs, "stored tree is not the tree rebuilt")

    runs = fixture("stored-tree-reformatted")            # same JSON value, different bytes: the file sha would differ
    (runs / "run3/leaves-v2.json").write_text(json.dumps(leaves(runs), sort_keys=True))
    refused_by_all("stored-tree-reformatted", runs, "formatting")

    runs = fixture("leaf-flip-in-run1")                  # the reference run is validated the same way
    d = leaves(runs, "run1")
    d["pins"]["stock"]["leaves"][3]["int_sha256"] = flip(d["pins"]["stock"]["leaves"][3]["int_sha256"], 9)
    put_leaves(runs, d, "run1")
    expect("leaf-flip-in-run1", runs, "compare", "refused", "stored tree is not the tree rebuilt")
    expect("leaf-flip-in-run1", runs, "suite", "refused", "stored tree is not the tree rebuilt", run="run1")
    expect("leaf-flip-in-run1", runs, "summarise", "refused", "stored tree is not the tree rebuilt")

    # ---- truncation (Astra; opus)
    runs = fixture("truncated-leaf-json")                # Astra: summary used to reuse the stale successful comparison
    p = runs / "run3/leaves-v2.json"
    p.write_text(p.read_text()[:-30])
    refused_by_all("truncated-leaf-json", runs, "not valid JSON")

    for cut in (30, 300):                                # Astra cut 30 bytes, opus 300
        case = "truncated-blocks-%d" % cut
        runs = fixture(case)
        p = runs / "run3/blocks.jsonl"
        p.write_text(p.read_text()[:-cut])
        refused_by_all(case, runs, "not newline-terminated")

    runs = fixture("garbage-line")
    ls = lines(runs)
    put(runs, ls[:5] + ["{not json"] + ls[5:])
    refused_by_all("garbage-line", runs, "not valid JSON")

    # ---- dropped blocks (Astra drop_block; opus drop-block)
    runs = fixture("drop-last-block")                    # Astra: last record removed, run-meta still says 78
    put(runs, lines(runs)[:-1])
    refused_by_all("drop-last-block", runs, "run-meta.json")

    runs = fixture("drop-middle-block")                  # opus: record 20 removed
    ls = lines(runs)
    put(runs, ls[:20] + ls[21:])
    refused_by_all("drop-middle-block", runs, "record order")

    runs = fixture("drop-last-block-meta-edited")        # run-meta edited to 77 but still "not stopped"
    put(runs, lines(runs)[:-1])
    m = json.loads((runs / "run3/run-meta.json").read_text())
    m["done"] = 77
    (runs / "run3/run-meta.json").write_text(json.dumps(m, indent=1, sort_keys=True))
    refused_by_all("drop-last-block-meta-edited", runs, "not stopped")

    runs = fixture("drop-last-block-stored-tree-kept")   # a declared partial run with a full stored tree next to it
    put(runs, lines(runs)[:-1])
    m["stopped"] = "fixture: stopped before the last block"
    (runs / "run3/run-meta.json").write_text(json.dumps(m, indent=1, sort_keys=True))
    expect("drop-last-block-stored-tree-kept", runs, "compare", "refused", "incomplete run")
    expect("drop-last-block-stored-tree-kept", runs, "suite", "refused", "all 78 blocks are needed")
    expect("drop-last-block-stored-tree-kept", runs, "summarise", "refused", "incomplete run")

    runs = fixture("consistent-partial-77")              # a self-consistent partial run: legitimate, but never full coverage
    put(runs, lines(runs)[:-1])
    (runs / "run3/run-meta.json").write_text(json.dumps(m, indent=1, sort_keys=True))
    (runs / "run3/leaves-v2.json").unlink()
    expect("consistent-partial-77", runs, "compare", "identical-partial",
           also=lambda d: d["n_common"] == 77 and d["n_identical"] == 77 and "roots_equal" not in d)
    expect("consistent-partial-77", runs, "suite", "refused", "all 78 blocks are needed")
    expect("consistent-partial-77", runs, "summarise", "refused", "stale or altered")       # committed compare file says 78
    recompare(runs)
    expect("consistent-partial-77 (compare file regenerated)", runs, "summarise", "PASS-SUBSET",
           also=lambda s: s["h3"]["union"]["n_blocks"] == 77 and s["h3"]["union"]["all_identical"] is True)

    # ---- missing metadata boundary (#189, independently reproduced before adding these cases)
    runs = fixture("missing-meta-cut-last")
    put(runs, lines(runs)[:-1])
    (runs / "run3/run-meta.json").unlink()
    (runs / "run3/leaves-v2.json").unlink()
    (runs / CMP["run3"]).unlink()
    expect("missing-meta-cut-last", runs, "compare", "identical-partial",
           also=lambda d: d["n_common"] == 77 and d["n_identical"] == 77 and "roots_equal" not in d)
    expect("missing-meta-cut-last", runs, "suite", "refused", "all 78 blocks are needed")
    expect("missing-meta-cut-last", runs, "summarise", "PASS-SUBSET",
           also=lambda s: s["h3"]["union"]["n_blocks"] == 77 and s["h3"]["union"]["all_identical"] is True
           and s["h3"]["run3"]["status"] == "identical-partial")

    runs = fixture("meta-kept-cut-last-no-tree-cache")
    put(runs, lines(runs)[:-1])
    (runs / "run3/leaves-v2.json").unlink()
    (runs / CMP["run3"]).unlink()
    refused_by_all("meta-kept-cut-last-no-tree-cache", runs, "run-meta.json")

    runs = fixture("missing-meta-cut-last-tree-kept")
    put(runs, lines(runs)[:-1])
    (runs / "run3/run-meta.json").unlink()
    (runs / CMP["run3"]).unlink()
    expect("missing-meta-cut-last-tree-kept", runs, "compare", "refused", "incomplete run")
    expect("missing-meta-cut-last-tree-kept", runs, "suite", "refused", "all 78 blocks are needed")
    expect("missing-meta-cut-last-tree-kept", runs, "summarise", "refused", "incomplete run")

    runs = fixture("missing-meta-complete")
    (runs / "run3/run-meta.json").unlink()
    expect("missing-meta-complete", runs, "compare", "identical-complete",
           also=lambda d: d["n_common"] == 78 and d["n_identical"] == 78 and all(d["roots_equal"].values()))
    expect("missing-meta-complete", runs, "suite", "pass", also=lambda d: d["n_pass"] == d["n_checks"] == 38)
    expect("missing-meta-complete", runs, "summarise", "PASS",
           also=lambda s: (runs / "summary.json").read_bytes() == (SRC / "summary.json").read_bytes())

    runs = fixture("missing-meta-reordered-no-tree-cache")
    ls = lines(runs)
    ls[3], ls[40] = ls[40], ls[3]
    put(runs, ls)
    (runs / "run3/run-meta.json").unlink()
    (runs / "run3/leaves-v2.json").unlink()
    (runs / CMP["run3"]).unlink()
    refused_by_all("missing-meta-reordered-no-tree-cache", runs, "record order")

    # ---- altered records (opus flip, e + 1, payload swap, line order; Astra payload swap)
    runs = fixture("swap-block-payloads-0-1")            # Astra: pin payloads of the first two records swapped
    rs = recs(runs)
    for pin in ("stock", "abl"):
        rs[0][pin], rs[1][pin] = rs[1][pin], rs[0][pin]
    put_recs(runs, rs)
    refused_by_all("swap-block-payloads-0-1", runs, "is not #68's")

    runs = fixture("swap-block-payloads-same-shape")     # two blocks of the same family and shape
    rs = recs(runs)
    i = first(rs, "changed")
    j = next(k for k in range(i + 1, len(rs)) if rs[k]["stock"]["shape"] == rs[i]["stock"]["shape"] and rs[k]["kind"] == "changed")
    for pin in ("stock", "abl"):
        rs[i][pin], rs[j][pin] = rs[j][pin], rs[i][pin]
    put_recs(runs, rs)
    refused_by_all("swap-block-payloads-same-shape", runs, "sha_matches_68")

    runs = fixture("swap-line-order-only")               # opus 2b: content unchanged, two lines exchanged
    ls = lines(runs)
    ls[3], ls[40] = ls[40], ls[3]
    put(runs, ls)
    refused_by_all("swap-line-order-only", runs, "record order")

    runs = fixture("record-int-hash-flip")               # opus: one hex digit of a changed block's stock int_sha256
    rs = recs(runs)
    i = first(rs, "changed")
    rs[i]["stock"]["int_sha256"] = flip(rs[i]["stock"]["int_sha256"], 5)
    put_recs(runs, rs)
    refused_by_all("record-int-hash-flip", runs, "stored tree is not the tree rebuilt")
    rebuild(runs)                                        # tree and compare file rebuilt: now only run1 disagrees
    expect("record-int-hash-flip (tree and compare file rebuilt)", runs, "compare", "mismatch",
           also=lambda d: d["n_identical"] == 77 and d["roots_equal"] == {"stock": False, "abl": True}
           and d["ids_equal"] == {"stock": False, "abl": True} and d["leaves_file_sha256_equal"] is False)
    expect("record-int-hash-flip (tree and compare file rebuilt)", runs, "summarise", "FAIL",
           also=lambda s: s["h3"]["union"]["all_identical"] is False and s["h3"]["run3"]["status"] == "mismatch")
    expect("record-int-hash-flip (tree and compare file rebuilt)", runs, "suite", "pass",
           also=lambda d: d["subset_id_stock"] != leaves(runs, "run1")["pins"]["stock"]["subset_id"])
    r = py([CLI, "compare", str(runs / "run1"), str(runs / "run3"), str(runs / "cli-compare.json")])
    RES.append(dict(case="record-int-hash-flip (tree and compare file rebuilt)", reader="compare (command line)", run="run3",
                    expected="rc 1", expected_reason=None, got="rc %d" % r.returncode, reason="", ok=r.returncode == 1))

    runs = fixture("control-e-plus-1")                   # opus: abl e + 1 on a control, flags left as they were
    rs = recs(runs)
    rs[first(rs, "control")]["abl"]["e"] += 1
    put_recs(runs, rs)
    refused_by_all("control-e-plus-1", runs, "e_equal")

    runs = fixture("control-e-plus-1-consistent")        # same with every derived field following, tree rebuilt
    rs = recs(runs)
    e_plus_1_consistent(rs[first(rs, "control")], "abl")
    put_recs(runs, rs)
    refused_by_all("control-e-plus-1-consistent", runs, "stored tree is not the tree rebuilt")
    with contextlib.redirect_stdout(io.StringIO()):
        lv.tree(str(runs / "run3"))
    expect("control-e-plus-1-consistent (tree rebuilt, committed compare file kept)", runs, "summarise", "refused", "stale or altered")
    recompare(runs)
    expect("control-e-plus-1-consistent (tree and compare file rebuilt)", runs, "compare", "mismatch",
           also=lambda d: d["n_identical"] == 77 and d["roots_equal"] == {"stock": True, "abl": False})
    expect("control-e-plus-1-consistent (tree and compare file rebuilt)", runs, "summarise", "FAIL",
           also=lambda s: s["h3"]["union"]["all_identical"] is False)

    # ---- names, kinds, derived flags, field shapes
    def one(case, reason, fn, run="run3"):
        runs = fixture(case)
        rs = recs(runs, run)
        fn(rs)
        put_recs(runs, rs, run)
        if run == "run3":
            refused_by_all(case, runs, reason)
        else:
            expect(case, runs, "compare", "refused", reason, run=run)
            expect(case, runs, "summarise", "refused", reason, run=run)

    one("unknown-block-name", "is not one of the 78 registered blocks",
        lambda rs: rs[2].__setitem__("name", rs[2]["name"].replace("weight", "weight2")))
    one("control-marked-changed", "is not the registered kind", lambda rs: rs[first(rs, "control")].__setitem__("kind", "changed"))
    one("changed-marked-control", "is not the registered kind", lambda rs: rs[first(rs, "changed")].__setitem__("kind", "control"))
    one("fetched-hash-changed-flag-kept", "sha_matches_68",
        lambda rs: rs[4]["stock"].__setitem__("sha256", flip(rs[4]["stock"]["sha256"], 7)))
    one("sha-matches-flag-flipped", "sha_matches_68", lambda rs: rs[4]["abl"].__setitem__("sha_matches_68", False))
    one("bytes-identical-flag-flipped", "bytes_identical", lambda rs: rs[4].__setitem__("bytes_identical", not rs[4]["bytes_identical"]))
    one("int-sha256-equal-flag-flipped", "int_sha256_equal",
        lambda rs: rs[first(rs, "changed")].__setitem__("int_sha256_equal", True))
    one("int-hash-uppercase", "64 lowercase hex", lambda rs: rs[1]["stock"].__setitem__("int_sha256", rs[1]["stock"]["int_sha256"].upper()))
    one("e-as-bool", "e must be an int", lambda rs: rs[1]["stock"].__setitem__("e", True))
    one("e-as-string", "e must be an int", lambda rs: rs[1]["stock"].__setitem__("e", str(rs[1]["stock"]["e"])))
    one("extra-record-field", "record fields are not exactly", lambda rs: rs[1].__setitem__("note", "x"))
    one("extra-pin-field", "fields are not exactly", lambda rs: rs[1]["abl"].__setitem__("int_sha256_alt", "0" * 64))
    one("fraction-inconsistent", "int_fraction_differing",
        lambda rs: rs[first(rs, "changed")].__setitem__("int_fraction_differing", 0.25))
    one("entries-zero-on-changed", "int_fraction_differing",
        lambda rs: rs[first(rs, "changed")].__setitem__("int_entries_differing", 0))
    one("elements-wrong", "elements", lambda rs: rs[1].__setitem__("elements", rs[1]["elements"] + 1))
    one("unknown-name-in-partial-run2", "is not one of the 78 registered blocks",
        lambda rs: rs[0].__setitem__("name", "model.language_model.layers.0.linear_attn.out_proj.weight"), run="run2")

    runs = fixture("run-meta-reverse-flipped")
    m3 = json.loads((runs / "run3/run-meta.json").read_text())
    m3["reverse"] = False
    (runs / "run3/run-meta.json").write_text(json.dumps(m3, indent=1, sort_keys=True))
    refused_by_all("run-meta-reverse-flipped", runs, "does not match reverse")

    # ---- the committed compare files are not a cache the summary trusts (Astra must-fix 2)
    for case, fn in (("compare-file-count-edited", lambda c: c.__setitem__("n_identical", 77)),
                     ("compare-file-row-edited", lambda c: c["rows"][0].__setitem__("identical", False)),
                     ("compare-file-root-flag-edited", lambda c: c["roots_equal"].__setitem__("stock", False)),
                     ("compare-file-extra-claim", lambda c: c.__setitem__("verdict", "PASS"))):
        runs = fixture(case)
        c = json.loads((runs / CMP["run3"]).read_text())
        fn(c)
        (runs / CMP["run3"]).write_text(json.dumps(c, indent=1, sort_keys=True))
        expect(case, runs, "summarise", "refused", "stale or altered")

    runs = fixture("compare-file-without-its-run")
    shutil.rmtree(runs / "run3")
    expect("compare-file-without-its-run", runs, "summarise", "refused", "a comparison without its run")

    runs = fixture("compare-files-removed")              # nothing is read from them: same result without them
    for f in CMP.values():
        (runs / f).unlink()
    expect("compare-files-removed", runs, "summarise", "PASS",
           also=lambda s: s["h3"]["overall"]["committed_compare_files"] == {} and s["h3"]["union"]["n_blocks"] == 78
           and s["h3"]["run3"]["status"] == "identical-complete")

    runs = fixture("run2-only")                          # registered partial coverage stays legitimate, and is not PASS
    shutil.rmtree(runs / "run3")
    (runs / CMP["run3"]).unlink()
    expect("run2-only", runs, "summarise", "BELOW-COVERAGE",
           also=lambda s: s["h3"]["union"] == dict(n_blocks=8, n_controls=4, n_changed=4, all_identical=True,
                                                    note=s["h3"]["union"]["note"]) and "run3" not in s)

    # ---- command-line exit codes
    runs = fixture("cli")
    r = py([CLI, "compare", str(runs / "run1"), str(runs / "run3"), str(runs / "cli-compare.json")])
    RES.append(dict(case="cli", reader="compare (command line)", run="run3", expected="rc 0", expected_reason=None,
                    got="rc %d" % r.returncode, reason="", ok=r.returncode == 0))
    ls = lines(runs)
    put(runs, ls + [ls[0]])
    for cmd in (["compare", str(runs / "run1"), str(runs / "run3"), str(runs / "cli-compare.json")], ["tree", str(runs / "run3")]):
        before = (runs / "run3/leaves-v2.json").read_bytes()
        r = py([CLI] + cmd)
        okk = r.returncode == 2 and "duplicate record" in r.stderr and (runs / "run3/leaves-v2.json").read_bytes() == before
        RES.append(dict(case="cli", reader="%s (command line)" % cmd[0], run="run3", expected="rc 2", expected_reason="duplicate record",
                        got="rc %d" % r.returncode, reason=clean(r.stderr), ok=okk))
    stoprule_189()


# ---------------------------------------------------------------- issue #189 stop-rule finding
def stoprule_189():
    """Issue #189 stop-rule finding (PREREG amendment A-1 of experiments/20261113-189-missing-metadata).

    CURRENT behaviour, pinned so that a change is noticed. NOT a contract the reader should keep.
    With run 3's metadata, stored tree and cached comparison removed (or its metadata edited to agree), a
    truncated, reordered or substituted run 3 can get a full H3 PASS:
      - the loader accepts a prefix of either canonical order when run-meta.json is absent;
      - the summary reports H3 on the union of run 2 and run 3 (PREREG A-1 of the #149 experiment), and
        run 2 holds the last 8 registered blocks, so a forward prefix of 70 or more blocks is completed;
      - nothing in a record says which run produced it, so run 1's own records are accepted as run 3.
    The coverage is real (each expectation below also checks that the reported union is exactly the set of
    blocks present in the run 2 and run 3 files) and every compared hash really is equal. What cannot be
    checked is provenance: that run 3 is a complete, independent, registered run. "forward" below means
    run 3's lines put into forward registered order (the committed run 3 is stored in reverse order)."""
    P = "stop-rule-189-"

    def strip(runs, meta=True, tree=True):
        if meta:
            (runs / "run3/run-meta.json").unlink()
        if tree:
            (runs / "run3/leaves-v2.json").unlink()
        (runs / CMP["run3"]).unlink()

    def pin(case, runs, n3, status3, overall, union, suite):
        f = {run: {json.loads(l)["name"] for l in lines(runs, run)} for run in ("run2", "run3")}
        expect(case, runs, "compare", status3,
               also=lambda d: d["n_common"] == n3 and d["n_identical"] == n3 and len(f["run3"]) == n3
               and ("roots_equal" in d) == (n3 == 78))
        if suite == "pass":
            expect(case, runs, "suite", "pass", also=lambda d: d["n_pass"] == d["n_checks"] == 38)
        else:
            expect(case, runs, "suite", "refused", "all 78 blocks are needed")
        expect(case, runs, "summarise", overall,
               also=lambda s: s["h3"]["union"]["n_blocks"] == union == len(f["run2"] | f["run3"])
               and s["h3"]["union"]["all_identical"] is True
               and s["h3"]["run3"]["status"] == status3 and s["h3"]["run3"]["n_common"] == n3
               and s["h3"]["run2"]["status"] == "identical-partial" and s["h3"]["run2"]["n_common"] == 8)

    # forward prefixes of run 3, metadata / tree / cache removed: 70 or more blocks are completed by run 2
    for k, overall, union in ((77, "PASS", 78), (76, "PASS", 78), (71, "PASS", 78), (70, "PASS", 78),
                              (69, "PASS-SUBSET", 77), (60, "PASS-SUBSET", 68), (39, "PASS-SUBSET", 47),
                              (10, "PASS-SUBSET", 18), (1, "BELOW-COVERAGE", 9)):
        case = P + "forward-%d" % k
        runs = fixture(case)
        fwd = lines(runs)[::-1]
        strip(runs)
        put(runs, fwd[:k])
        pin(case, runs, k, "identical-partial", overall, union, "refused")

    case = P + "forward-78-whole"                         # the whole of run 3 reordered into forward order
    runs = fixture(case)
    fwd = lines(runs)[::-1]
    strip(runs)
    put(runs, fwd)
    pin(case, runs, 78, "identical-complete", "PASS", 78, "pass")

    case = P + "run1-records-as-run3"                     # substitution: H3 then compares run 1 with itself
    runs = fixture(case)
    strip(runs)
    put(runs, lines(runs, "run1"))
    pin(case, runs, 78, "identical-complete", "PASS", 78, "pass")

    for keep_meta in (True, False):                       # run 1's whole directory as run 3
        case = P + "run1-dir-as-run3-" + ("meta-kept" if keep_meta else "no-meta")
        runs = fixture(case)
        shutil.rmtree(runs / "run3")
        shutil.copytree(runs / "run1", runs / "run3")
        (runs / CMP["run3"]).unlink()
        if not keep_meta:
            (runs / "run3/run-meta.json").unlink()
        pin(case, runs, 78, "identical-complete", "PASS", 78, "pass")

    case = P + "run1-first-70-as-run3"                    # substitution and truncation
    runs = fixture(case)
    strip(runs)
    put(runs, lines(runs, "run1")[:70])
    pin(case, runs, 70, "identical-partial", "PASS", 78, "refused")

    case = P + "alternate-run1-run3-by-name"              # records taken alternately from two runs, canonical order
    runs = fixture(case)
    r1, fwd = lines(runs, "run1"), lines(runs)[::-1]
    strip(runs)
    put(runs, [r1[i] if i % 2 == 0 else fwd[i] for i in range(78)])
    pin(case, runs, 78, "identical-complete", "PASS", 78, "pass")

    case = P + "splice-run1-39-forward-run3-39-69"        # run 1's first 39 lines, then forward run 3 lines 39 to 69
    runs = fixture(case)
    r1, fwd = lines(runs, "run1"), lines(runs)[::-1]
    strip(runs)
    put(runs, r1[:39] + fwd[39:70])
    pin(case, runs, 70, "identical-partial", "PASS", 78, "refused")

    for k in (77, 70):                                    # metadata present and edited to agree: still a full PASS
        case = P + "forward-%d-meta-consistent" % k
        runs = fixture(case)
        fwd = lines(runs)[::-1]
        strip(runs, meta=False)
        put(runs, fwd[:k])
        m = json.loads((runs / "run3/run-meta.json").read_text())
        m.update(done=k, reverse=False, stopped="fixture: stopped after %d blocks" % k)
        (runs / "run3/run-meta.json").write_text(json.dumps(m, indent=1, sort_keys=True))
        pin(case, runs, k, "identical-partial", "PASS", 78, "refused")


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else None) else 1)
