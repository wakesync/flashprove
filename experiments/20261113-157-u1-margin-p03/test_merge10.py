#!/usr/bin/env python3
"""Hostile-input tests for merge10.py (validation only, no weights, seconds).

Copies the four committed experiment directories merge10.py reads into a temporary tree, then:
- valid: the committed inputs reproduce runs/merged-analysis.json and runs/merge-validation.json byte for byte (exit 0);
- hostile: each malformed input must exit 2 with "INVALID, nothing written" and no traceback, and write no output.
Round-3 review cases (validation only):
- forged_pyc: a __pycache__/analyse.cpython-XY.pyc for PR #139's analyse.py, compiled from a copy whose verdict line is
  changed to PASS, with the real source's mtime and size in its header, is planted in the test tree (this case keeps
  __pycache__). A plain `import analyse` loads it (checked as a control); merge10.py must give exit 2 or the committed
  output byte for byte.
- read_once: merge10.py is run in a child process whose Path.read_bytes / read_text return the real bytes on the first
  read of a pinned file and corrupted bytes (astra's round-2 corruption for the E files, an empty JSON object otherwise)
  on any later read. It must reproduce the committed output byte for byte and read each pinned file exactly once,
  i.e. it parses or executes exactly the bytes it hashed.
Usage: python3 test_merge10.py   (exit 0 = all cases as expected)
"""
import importlib.util, json, marshal, os, shutil, subprocess, sys, tempfile
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

OUTS = ("merged-analysis.json", "merge-validation.json")
def same_as_committed(out): return all((out / f).is_file() and (out / f).read_bytes() == (HERE / "runs" / f).read_bytes() for f in OUTS)

# Round 3 (a): forged bytecode for PR #139's analyse.py, source untouched.
def plant_forged_pyc(root):
    src = root / "20261112-134-u1-margin/analyse.py"; text = src.read_text()
    evil = text.replace('    else: vd = "FAIL (mixed)"', '    else: vd = "PASS"') + "\nFORGED_PYC = True\n"
    assert '    else: vd = "FAIL (mixed)"' in text
    st = os.stat(src); cache = Path(importlib.util.cache_from_source(str(src))); cache.parent.mkdir(exist_ok=True)
    hdr = (importlib.util.MAGIC_NUMBER + (0).to_bytes(4, "little") + (int(st.st_mtime) & 0xFFFFFFFF).to_bytes(4, "little")
           + (st.st_size & 0xFFFFFFFF).to_bytes(4, "little"))
    cache.write_bytes(hdr + marshal.dumps(compile(evil, str(src), "exec")))
    return cache

def forged_pyc():
    with tempfile.TemporaryDirectory() as tmp:
        root = tree(tmp); cache = plant_forged_pyc(root); d = root / "20261112-134-u1-margin"
        # control: the plant is effective for a plain import (otherwise this case would test nothing)
        c = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import analyse; print(getattr(analyse, 'FORGED_PYC', False))", str(d)],
                           capture_output=True, text=True, cwd=tmp)
        control = c.stdout.strip() == "True"
        out = Path(tmp) / "out"; p = run(root, out)
        safe = (p.returncode == 2 and not out.exists()) or (p.returncode == 0 and same_as_committed(out))
        ok = control and safe and cache.is_file() and "Traceback" not in p.stderr
        print(f"{'ok  ' if ok else 'FAIL'} forged_pyc: control_import_uses_pyc={control} rc={p.returncode} "
              f"byte_identical={p.returncode == 0 and same_as_committed(out)} pyc_still_present={cache.is_file()}")
        if not ok: print(p.stderr[-800:], c.stderr[-400:])
        return ok

# Round 3 (b): merge10 parses exactly the bytes it hashed. Child-process mode of this file.
def read_once_child(root, out, log):
    import pathlib
    m = root / ME / "merge10.py"
    rel = [                                              # every pinned path merge10 reads (relative to experiments/)
           "20261111-8-qwen-e2e-agreement/runs/e2e-stock.json", "20261111-8-qwen-e2e-agreement/runs/e2e-abl.json",
           "20261111-8-qwen-e2e-agreement/runs/manifest-stock.json", "20261111-8-qwen-e2e-agreement/runs/manifest-abl.json",
           "20261111-8-qwen-e2e-agreement/prompts-e2e.json", "20261110-36-weight-binding/runs/manifest-stock.json",
           "20261110-36-weight-binding/runs/manifest-abl.json", "20261112-134-u1-margin/runs/manifest-stock.json",
           "20261112-134-u1-margin/runs/manifest-abl.json", "20261112-134-u1-margin/runs/analysis.json",
           "20261112-134-u1-margin/runs/d-per-position.json", "20261112-134-u1-margin/analyse.py"]
    pinned = {str((root / r).resolve()) for r in rel}
    real_rb, real_rt = pathlib.Path.read_bytes, pathlib.Path.read_text
    count = {}
    def bad_bytes(key):
        if key.endswith(("e2e-stock.json", "e2e-abl.json")):
            d = json.loads(real_rb(pathlib.Path(key)))
            kl = d["prompts"]["p03-repeat-word"]["paths"]["XS18"]["kl"]; kl[1:] = [-1.0] * (len(kl) - 1)
            return json.dumps(d).encode()
        if key.endswith(".py"): return b"raise SystemExit('second read of analyse.py was executed')\n"
        return b"{}"
    def rb(self):
        key = str(pathlib.Path(self).resolve())
        if key not in pinned: return real_rb(self)
        count[key] = count.get(key, 0) + 1
        return real_rb(self) if count[key] == 1 else bad_bytes(key)
    def rt(self, *a, **k):
        key = str(pathlib.Path(self).resolve())
        if key not in pinned: return real_rt(self, *a, **k)
        count[key] = count.get(key, 0) + 1
        return real_rt(self, *a, **k) if count[key] == 1 else bad_bytes(key).decode()
    pathlib.Path.read_bytes, pathlib.Path.read_text = rb, rt
    me = root / ME
    sys.argv = [str(m), str(me / "runs/run1"), str(me / "runs/run2"), str(out)]
    rc = None
    try:
        spec = importlib.util.spec_from_file_location("merge10_under_test", m); mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod); rc = mod.main(sys.argv)
    except SystemExit as e: rc = e.code
    finally:
        pathlib.Path.read_bytes, pathlib.Path.read_text = real_rb, real_rt
        Path(log).write_text(json.dumps(dict(rc=rc, reads={k[len(str(root.resolve())) + 1:]: v for k, v in count.items()}, n_pinned=len(pinned))))

def read_once():
    with tempfile.TemporaryDirectory() as tmp:
        root = tree(tmp); out = Path(tmp) / "out"; log = Path(tmp) / "log.json"
        p = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--read-once-child", str(root), str(out), str(log)],
                           capture_output=True, text=True, cwd=tmp)
        r = json.loads(log.read_text()) if log.is_file() else {}
        reads = r.get("reads", {})
        once = len(reads) == r.get("n_pinned") and all(v == 1 for v in reads.values())
        same = r.get("rc") == 0 and same_as_committed(out)
        ok = once and same
        print(f"{'ok  ' if ok else 'FAIL'} read_once: rc={r.get('rc')} byte_identical={same} pinned_files_read={len(reads)}/{r.get('n_pinned')} "
              f"max_reads_per_file={max(reads.values()) if reads else None}")
        if not ok: print(json.dumps(reads, indent=1), p.stderr[-800:])
        return ok

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
    extra = [forged_pyc, read_once]
    for case in extra: fails += not case()
    n = 1 + len(HOSTILE) + len(extra)
    print(f"{n - fails} of {n} cases as expected")
    return 1 if fails else 0

if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--read-once-child":
        read_once_child(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]); sys.exit(0)
    sys.exit(main())
