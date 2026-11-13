#!/usr/bin/env python3
"""Hostile-input tests for merge10.py (validation only, no weights, seconds).

Copies the four committed experiment directories merge10.py reads into a temporary tree, then:
- valid: the committed inputs reproduce runs/merged-analysis.json and runs/merge-validation.json byte for byte (exit 0);
- hostile: each malformed input must exit 2 with "INVALID, nothing written" and no traceback, and write no output.
Usage: python3 test_merge10.py   (exit 0 = all cases as expected)
"""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
DIRS = ("20261113-157-u1-margin-p03", "20261112-134-u1-margin", "20261111-8-qwen-e2e-agreement", "20261110-36-weight-binding")
ME = DIRS[0]

def tree(tmp):
    root = Path(tmp) / "experiments"
    for d in DIRS: shutil.copytree(EXP / d, root / d, ignore=shutil.ignore_patterns("__pycache__"))
    return root

def run(root, out, extra=()):
    me = root / ME
    return subprocess.run([sys.executable, str(me / "merge10.py"), str(me / "runs/run1"), str(me / "runs/run2"), str(out), *extra],
                          capture_output=True, text=True, cwd=me)

def edit_text(p, f): p.write_text(f(p.read_text()))

def edit_json(p, f):
    d = json.loads(p.read_text()); f(d); p.write_text(json.dumps(d))

# hostile cases: (name, mutation(root))
def truncated_run1(r): edit_text(r / ME / "runs/run1/d-p03.json", lambda s: s[: len(s) // 2])
def dupkey_run1(r): edit_text(r / ME / "runs/run1/d-p03.json", lambda s: s.replace('{"note": ', '{"note": "x", "note": ', 1))
def truncated_run2(r): edit_text(r / ME / "runs/run2/d-p03.json", lambda s: s[:-10])
def absent_e_stock(r): edit_json(r / "20261111-8-qwen-e2e-agreement/runs/e2e-stock.json", lambda d: d["prompts"].pop("p03-repeat-word"))
def absent_e_abl_other(r): edit_json(r / "20261111-8-qwen-e2e-agreement/runs/e2e-abl.json", lambda d: d["prompts"].pop("p05-code"))
def absent_xs18(r): edit_json(r / "20261111-8-qwen-e2e-agreement/runs/e2e-abl.json", lambda d: d["prompts"]["p03-repeat-word"]["paths"].pop("XS18"))
def truncated_e(r): edit_text(r / "20261111-8-qwen-e2e-agreement/runs/e2e-stock.json", lambda s: s[:1000])
def malformed_manifest(r): edit_text(r / ME / "runs/run1/manifest-abl.json", lambda s: s.replace("{", "[", 1))
def manifest_no_tensors(r): edit_json(r / ME / "runs/run1/manifest-stock.json", lambda d: d.pop("tensors"))
def missing_prompts_file(r): (r / "20261111-8-qwen-e2e-agreement/prompts-e2e.json").unlink()
def dupkey_p87(r): edit_text(r / "20261110-36-weight-binding/runs/manifest-stock.json", lambda s: s.replace("{", '{"x": 1, "x": 2, ', 1))
def run2_wrong_prompt(r): edit_text(r / ME / "runs/run2/d-p03.json", lambda s: s.replace('"p03-repeat-word"', '"p03-other"', 1))

# Round-2 review (astra) reproduction: materially negative reused PR #124 E on p03 XS18 in both legs. Before the pins
# this gave exit 0 PASS; the fixed inputs are now checked against their committed sha256 and it must exit 2.
def _neg_e(d):
    kl = d["prompts"]["p03-repeat-word"]["paths"]["XS18"]["kl"]; kl[1:] = [-1.0] * (len(kl) - 1)
def negative_e_xs18_both(r):
    for leg in ("stock", "abl"): edit_json(r / f"20261111-8-qwen-e2e-agreement/runs/e2e-{leg}.json", _neg_e)
def negative_e_one_value(r):
    def f(d): d["prompts"]["p05-code"]["paths"]["XS20"]["kl"][0] = -1e-3
    edit_json(r / "20261111-8-qwen-e2e-agreement/runs/e2e-abl.json", f)
def e_whitespace_only(r): edit_text(r / "20261111-8-qwen-e2e-agreement/runs/e2e-stock.json", lambda s: s + "\n")
def p124_manifest_changed(r): edit_text(r / "20261111-8-qwen-e2e-agreement/runs/manifest-abl.json", lambda s: s + " ")
def p87_manifest_changed(r): edit_text(r / "20261110-36-weight-binding/runs/manifest-abl.json", lambda s: s + " ")
def p139_analysis_changed(r): edit_text(r / "20261112-134-u1-margin/runs/analysis.json", lambda s: s + " ")
def p139_analyse_py_changed(r): edit_text(r / "20261112-134-u1-margin/analyse.py", lambda s: s + "\n")

HOSTILE = [truncated_run1, dupkey_run1, truncated_run2, absent_e_stock, absent_e_abl_other, absent_xs18, truncated_e,
           malformed_manifest, manifest_no_tensors, missing_prompts_file, dupkey_p87, run2_wrong_prompt,
           negative_e_xs18_both, negative_e_one_value, e_whitespace_only, p124_manifest_changed, p87_manifest_changed,
           p139_analysis_changed, p139_analyse_py_changed]
PINNED_CASES = {negative_e_xs18_both, negative_e_one_value, e_whitespace_only, p124_manifest_changed, p87_manifest_changed,
                p139_analysis_changed, p139_analyse_py_changed}

def main():
    fails = 0
    with tempfile.TemporaryDirectory() as tmp:
        root = tree(tmp); out = Path(tmp) / "out-valid"
        p = run(root, out)
        same = all((out / f).read_bytes() == (HERE / "runs" / f).read_bytes() for f in ("merged-analysis.json", "merge-validation.json")) if p.returncode == 0 else False
        ok = p.returncode == 0 and same
        print(f"{'ok  ' if ok else 'FAIL'} valid: rc={p.returncode} byte_identical={same}"); fails += not ok
    for case in HOSTILE:
        with tempfile.TemporaryDirectory() as tmp:
            root = tree(tmp); case(root); out = Path(tmp) / "out"
            p = run(root, out)
            ok = p.returncode == 2 and "INVALID, nothing written" in p.stderr and "Traceback" not in p.stderr and not out.exists()
            if case in PINNED_CASES: ok = ok and "sha256 is not the committed one" in p.stderr   # refused by the pin check
            print(f"{'ok  ' if ok else 'FAIL'} {case.__name__}: rc={p.returncode} wrote={out.exists()} traceback={'Traceback' in p.stderr}")
            if not ok: print(p.stderr[-800:])
            fails += not ok
    print(f"{1 + len(HOSTILE) - fails} of {1 + len(HOSTILE)} cases as expected")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
