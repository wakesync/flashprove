#!/usr/bin/env python3
"""Check of the summariser's determinism-coverage guard (added after review, PREREG Amendment A-1). CPU only, seconds.

Works on copies of three committed run files in a temporary directory. The committed files under runs/ are read, never
written. No serving request, no forward pass.

1. Unchanged copy: `summarise_served.py <copy>` must exit 0 and write summary.json and summary.md that are
   byte-identical to the committed ones (the guard changes no number and no verdict).
2. Incomplete or malformed determinism records must exit non-zero and write no summary:
   63 layer rows, 1 layer row, 0 rows, a duplicated layer, a layer out of range, a missing duplicate key, an extra
   duplicate key, a non-boolean equality value, a duplicate path missing from forward.json.
3. A complete record with one false equality must exit 0 and give the registered "NOT DETERMINISTIC" verdict in all
   three cells (unchanged behaviour).

Usage: python3 test_summarise_served.py [receipt.json]   exit 0 iff every case behaves as stated."""
import copy, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent; R = HERE / "runs"
INPUTS = ("served-ids.json", "forward.json", "divergence-abl.jsonl")
OUTPUTS = ("summary.json", "summary.md")

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def fresh(tmp, name):
    d = Path(tmp) / name; d.mkdir()
    for f in INPUTS: shutil.copyfile(R / f, d / f)
    return d

def run(d):
    p = subprocess.run([sys.executable, str(HERE / "summarise_served.py"), str(d)], capture_output=True, text=True)
    return p.returncode, [f for f in OUTPUTS if (d / f).exists()]

def rows(d): return [json.loads(l) for l in open(d / "divergence-abl.jsonl")]
def put_rows(d, rs): (d / "divergence-abl.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rs))

def m_63(d): put_rows(d, rows(d)[:63])
def m_1(d): put_rows(d, rows(d)[:1])
def m_0(d): put_rows(d, [])
def m_dup_layer(d):
    rs = rows(d); rs[63] = copy.deepcopy(rs[62]); put_rows(d, rs)
def m_layer_out_of_range(d):
    rs = rows(d); rs[63]["layer"] = 64; put_rows(d, rs)
def m_missing_key(d):
    rs = rows(d); del rs[10]["det_bit_equal"]["XS18#2|q02"]; put_rows(d, rs)
def m_extra_key(d):
    rs = rows(d); rs[10]["det_bit_equal"]["REF#2|q03"] = True; put_rows(d, rs)
def m_non_bool(d):
    rs = rows(d); rs[10]["det_bit_equal"]["REF#2|q01"] = 1; put_rows(d, rs)
def m_forward_dup_missing(d):
    fw = json.load(open(d / "forward.json")); del fw["prompts"]["q02"]["paths"]["XS18#2"]
    (d / "forward.json").write_text(json.dumps(fw))
def m_false_equality(d):
    rs = rows(d); rs[40]["det_bit_equal"]["XS18#2|q01"] = False; put_rows(d, rs)

REJECT = [("layer_rows_63", m_63), ("layer_rows_1", m_1), ("layer_rows_0", m_0), ("duplicated_layer", m_dup_layer),
          ("layer_out_of_range", m_layer_out_of_range), ("missing_duplicate_key", m_missing_key),
          ("extra_duplicate_key", m_extra_key), ("non_boolean_value", m_non_bool),
          ("forward_duplicate_path_missing", m_forward_dup_missing)]

def main():
    before = {f: sha(R / f) for f in INPUTS + OUTPUTS}
    cases = []; ok = True
    with tempfile.TemporaryDirectory() as tmp:
        d = fresh(tmp, "unchanged"); rc, wrote = run(d)
        same = {f: (d / f).exists() and (d / f).read_bytes() == (R / f).read_bytes() for f in OUTPUTS}
        good = rc == 0 and all(same.values())
        cases.append(dict(case="unchanged_copy", expect="exit 0, summary byte-identical to committed", exit_code=rc,
                          byte_identical=same, summary_sha256={f: sha(d / f) for f in wrote}, ok=good)); ok &= good
        for name, mut in REJECT:
            d = fresh(tmp, name); mut(d); rc, wrote = run(d)
            good = rc != 0 and not wrote
            cases.append(dict(case=name, expect="non-zero exit, no summary written", exit_code=rc, summary_files_written=wrote, ok=good)); ok &= good
        d = fresh(tmp, "false_equality"); m_false_equality(d); rc, wrote = run(d)
        v = json.load(open(d / "summary.json"))["verdict"] if "summary.json" in wrote else None
        good = rc == 0 and v is not None and set(v.values()) == {"NOT DETERMINISTIC"}
        cases.append(dict(case="false_equality_complete_record", expect="exit 0, every cell NOT DETERMINISTIC", exit_code=rc, verdict=v, ok=good)); ok &= good
    after = {f: sha(R / f) for f in INPUTS + OUTPUTS}
    untouched = before == after; ok &= untouched
    out = dict(what="summarise_served.py determinism-coverage guard, checked on temporary copies of committed run files",
               committed_sha256=before, committed_run_files_untouched=untouched, cases=cases, all_ok=bool(ok))
    text = json.dumps(out, indent=1) + "\n"
    if len(sys.argv) > 1: Path(sys.argv[1]).write_text(text)
    for c in cases: print("ok  " if c["ok"] else "FAIL", c["case"], "exit", c["exit_code"])
    print("committed run files untouched:", untouched); print("ALL OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)

if __name__ == "__main__": main()
