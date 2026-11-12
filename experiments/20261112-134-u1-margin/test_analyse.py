#!/usr/bin/env python3
"""Negative tests for analyse.py's input validation (added after review, PREREG Amendment A-2). CPU only, seconds.

Works on copies of four committed run files in a temporary directory. The committed files under runs/ are read, never
written. No model forward, no weights, no network.

1. Unchanged copy: `analyse.py <copy>` must exit 0 and write an analysis.json that is byte-identical to the committed
   runs/analysis.json (the validation changes no number and no verdict).
2. INVALID cases must exit 2 and write nothing: evidence that is missing, malformed, non-finite, duplicated, or not
   the registered prompt tier. The first two are the reviewer's cases (both manifests' tensor lists emptied; the same plus
   only p08-chat-refusal kept in the D file). The script as committed for the registered run accepted both, and
   returned PASS for the second.
3. KILLED cases must exit 3 and write an analysis.json whose verdict is "KILLED (validity gate)": the evidence is
   complete, but gate (a), (b) or (c) fails.
4. An existing analysis.json in the output dir must not be overwritten (exit 4).
5. Documented limit, expected exit 0: a copy whose progress.log, tier line and D prompts are all rewritten to a
   consistent registered tier 3 is accepted as a tier 3 subset. The tier is read from the run's own log, and that log
   is not authenticated. The validation binds the prompt set to the logged grant time; it does not prove the log.

Usage: python3 test_analyse.py [receipt.json] [--analyse <path to an analyse.py>]
Exit 0 iff every case behaves as stated. --analyse runs the same cases against another copy of the script (used to
record what the pre-review script did; that copy must sit in a tree with the PR #124 and PR #87 files beside it)."""
import hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent; R = HERE / "runs"
INPUTS = ("d-per-position.json", "manifest-stock.json", "manifest-abl.json", "progress.log")
OUTPUTS = ("analysis.json", "input-validation.json")
T3 = ["p01-ordinary-short", "p07-chat-ordinary", "p08-chat-refusal", "p09-multilingual", "p06a-digits-256", "p11-chat-long"]
P = "model.language_model."

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(d, f): return json.loads((d / f).read_text())
def jd(d, f, o): (d / f).write_text(json.dumps(o))
def log(d): return (d / "progress.log").read_text().splitlines()
def putlog(d, ls): (d / "progress.log").write_text("\n".join(ls) + "\n")

def empty_manifests(d):
    for ck in ("stock", "abl"):
        m = jl(d, f"manifest-{ck}.json"); m["tensors"] = {}; jd(d, f"manifest-{ck}.json", m)
def keep_only(d, ids):
    x = jl(d, "d-per-position.json"); x["prompts"] = {p: x["prompts"][p] for p in ids}; jd(d, "d-per-position.json", x)
def prompt_edit(fn):
    def mut(d):
        x = jl(d, "d-per-position.json"); fn(x["prompts"]); jd(d, "d-per-position.json", x)
    return mut
def manifest_edit(ck, fn):
    def mut(d):
        m = jl(d, f"manifest-{ck}.json"); fn(m["tensors"]); jd(d, f"manifest-{ck}.json", m)
    return mut
def log_edit(fn):
    def mut(d): putlog(d, fn(log(d)))
    return mut

def m_reviewer_subset(d): empty_manifests(d); keep_only(d, ["p08-chat-refusal"])
def m_truncate(p):
    for k in ("stock_top1", "stock_margin", "abl_top1", "abl_margin", "D_kl_stock_abl"): p["p05-code"][k] = p["p05-code"][k][:-1]
def m_short_T(p):
    m_truncate(p); p["p05-code"]["T"] -= 1
def m_extra_prompt(p): p["p03-repeat-word"] = dict(p["p04-repeat-punct"])
def m_tier3_log(ls):
    return ["slot granted 2026-11-12T18:30:00Z", "tier 3 prompts " + ",".join(T3)] + ls[2:]
def m_consistent_tier3(d): putlog(d, m_tier3_log(log(d))); keep_only(d, T3)
def swap(old, new): return lambda ls: [l.replace(old, new) for l in ls]
def first_sha(t):
    n = sorted(t)[0]; t[n]["sha256"] = "0" * 64
def m_duplicate_key(d):
    t = (d / "d-per-position.json").read_text(); k = '"prompts": {'
    assert t.count(k) == 1
    (d / "d-per-position.json").write_text(t.replace(k, k + '"p08-chat-refusal": [], '))   # a plain parser keeps the later, real entry

INVALID = [
    ("reviewer_empty_manifests", empty_manifests),
    ("reviewer_p08_only_and_empty_manifests", m_reviewer_subset),
    ("p08_only_full_manifests", lambda d: keep_only(d, ["p08-chat-refusal"])),
    ("p01_dropped_no_tokyo_check", prompt_edit(lambda p: p.pop("p01-ordinary-short"))),
    ("tier3_prompts_under_a_tier2_grant", lambda d: keep_only(d, T3)),
    ("extra_prompt_not_in_tier", prompt_edit(m_extra_prompt)),
    ("position_arrays_truncated", prompt_edit(m_truncate)),
    ("positions_fewer_than_frozen_prompt", prompt_edit(m_short_T)),
    ("D_nan", prompt_edit(lambda p: p["p02-ordinary-paragraph"]["D_kl_stock_abl"].__setitem__(5, float("nan")))),
    ("D_null", prompt_edit(lambda p: p["p02-ordinary-paragraph"]["D_kl_stock_abl"].__setitem__(5, None))),
    ("D_negative", prompt_edit(lambda p: p["p02-ordinary-paragraph"]["D_kl_stock_abl"].__setitem__(5, -0.25))),
    ("margin_infinite", prompt_edit(lambda p: p["p07-chat-ordinary"]["abl_margin"].__setitem__(0, float("inf")))),
    ("top1_boolean", prompt_edit(lambda p: p["p07-chat-ordinary"]["stock_top1"].__setitem__(0, True))),
    ("top1_out_of_vocabulary", prompt_edit(lambda p: p["p07-chat-ordinary"]["stock_top1"].__setitem__(0, 248320))),
    ("D_file_not_json", lambda d: (d / "d-per-position.json").write_text("{")),
    ("D_file_duplicate_prompt_key", m_duplicate_key),
    ("D_file_missing", lambda d: (d / "d-per-position.json").unlink()),
    ("stock_tensor_missing", manifest_edit("stock", lambda t: t.pop(P + "layers.40.mlp.down_proj.weight"))),
    ("stock_lm_head_missing", manifest_edit("stock", lambda t: t.pop("lm_head.weight"))),
    ("abl_changed_tensor_missing", manifest_edit("abl", lambda t: t.pop(P + "layers.17.mlp.down_proj.weight"))),
    ("abl_final_norm_missing", manifest_edit("abl", lambda t: t.pop(P + "norm.weight"))),
    ("abl_unexpected_tensor", manifest_edit("abl", lambda t: t.__setitem__(P + "layers.60.mlp.down_proj.weight", dict(t[P + "layers.17.mlp.down_proj.weight"])))),
    ("tensor_entry_without_sha256", manifest_edit("stock", lambda t: t[sorted(t)[0]].pop("sha256"))),
    ("manifest_missing", lambda d: (d / "manifest-abl.json").unlink()),
    ("progress_log_missing", lambda d: (d / "progress.log").unlink()),
    ("grant_time_moved_to_tier1_with_9_prompts", log_edit(swap("slot granted 2026-11-12T18:25:18Z", "slot granted 2026-11-12T18:10:00Z"))),
    ("tier_line_says_tier3_under_a_tier2_grant", log_edit(lambda ls: [ls[0], "tier 3 prompts " + ",".join(T3)] + ls[2:])),
    ("grant_after_last_tier", log_edit(swap("slot granted 2026-11-12T18:25:18Z", "slot granted 2026-11-12T18:36:00Z"))),
    ("run_end_nonzero", log_edit(swap("end rc=0", "end rc=137"))),
    ("run_end_after_hard_stop", log_edit(swap("end rc=0 2026-11-12T18:46:41Z", "end rc=0 2026-11-12T18:51:00Z"))),
    ("run_end_line_missing", log_edit(lambda ls: [l for l in ls if not l.startswith("end ")])),
]
KILLED = [
    ("tokyo_wrong_on_stock", prompt_edit(lambda p: p["p01-ordinary-short"]["stock_top1"].__setitem__(-1, 1)), "a_tokyo"),
    ("top1_differs_from_pr124", prompt_edit(lambda p: p["p11-chat-long"]["abl_top1"].__setitem__(100, 1)), "b_reproduce"),
    ("margin_differs_from_pr124", prompt_edit(lambda p: p["p05-code"]["stock_margin"].__setitem__(3, p["p05-code"]["stock_margin"][3] + 1e-3)), "b_reproduce"),
    ("stock_tensor_sha256_changed", manifest_edit("stock", first_sha), "c_manifest"),
    ("abl_tensor_sha256_changed", manifest_edit("abl", first_sha), "c_manifest"),
]

def main():
    args = sys.argv[1:]; script = HERE / "analyse.py"
    if "--analyse" in args:
        i = args.index("--analyse"); script = Path(args[i + 1]).resolve(); args = args[:i] + args[i + 2:]
    receipt = args[0] if args else None
    before = {f: sha(R / f) for f in INPUTS + ("analysis.json",)}
    cases = []; ok = True

    def fresh(tmp, name, mut=None):
        d = Path(tmp) / name; d.mkdir()
        for f in INPUTS: shutil.copyfile(R / f, d / f)
        if mut: mut(d)
        return d
    def run(d):
        p = subprocess.run([sys.executable, str(script), str(d)], capture_output=True, text=True)
        return p.returncode, [f for f in OUTPUTS if (d / f).exists()], p.stderr.strip().splitlines()
    def add(**c):
        nonlocal ok
        cases.append(c); ok &= c["ok"]

    with tempfile.TemporaryDirectory() as tmp:
        d = fresh(tmp, "unchanged"); rc, wrote, _ = run(d)
        same = (d / "analysis.json").exists() and (d / "analysis.json").read_bytes() == (R / "analysis.json").read_bytes()
        add(case="unchanged_copy", expect="exit 0, analysis.json byte-identical to the committed runs/analysis.json", exit_code=rc,
            byte_identical=same, analysis_sha256=sha(d / "analysis.json") if "analysis.json" in wrote else None,
            verdict=jl(d, "analysis.json")["verdict"]["verdict"] if "analysis.json" in wrote else None, ok=rc == 0 and same)
        for name, mut in INVALID:
            d = fresh(tmp, name, mut); rc, wrote, err = run(d)
            v = jl(d, "analysis.json")["verdict"]["verdict"] if "analysis.json" in wrote else None
            add(case=name, expect="exit 2 (INVALID), nothing written", exit_code=rc, files_written=wrote, verdict_if_written=v,
                reasons=[l[3:] for l in err if l.startswith(" - ")][:4], ok=rc == 2 and not wrote)
        for name, mut, gate in KILLED:
            d = fresh(tmp, name, mut); rc, wrote, _ = run(d)
            a = jl(d, "analysis.json") if "analysis.json" in wrote else None
            v = a["verdict"]["verdict"] if a else None
            g = a["gates"][gate] if a else None; g = g.get("ok") if isinstance(g, dict) else g
            add(case=name, expect=f"exit 3, verdict KILLED (validity gate), gate {gate} false", exit_code=rc, verdict=v, gate=gate, gate_value=g,
                ok=rc == 3 and v == "KILLED (validity gate)" and g is False)
        d = fresh(tmp, "no_overwrite"); (d / "analysis.json").write_text("sentinel\n"); rc, _, _ = run(d)
        kept = (d / "analysis.json").read_text() == "sentinel\n"
        add(case="existing_output_not_overwritten", expect="exit 4, existing analysis.json left as it was", exit_code=rc, existing_file_unchanged=kept, ok=rc == 4 and kept)
        d = fresh(tmp, "consistent_tier3", m_consistent_tier3); rc, wrote, _ = run(d)
        a = jl(d, "analysis.json") if "analysis.json" in wrote else None
        vd = a["verdict"] if a else {}
        add(case="documented_limit_consistent_tier3_log_and_prompts",
            expect="exit 0 as a 6-prompt tier 3 subset: the tier comes from the run's own log, which is not authenticated", exit_code=rc,
            prompts_run=vd.get("prompts_run"), prompts_needed=vd.get("prompts_needed"), subset=vd.get("subset"), verdict=vd.get("verdict"),
            ok=rc == 0 and vd.get("prompts_run") == 6 and vd.get("subset") is True)
    after = {f: sha(R / f) for f in INPUTS + ("analysis.json",)}
    untouched = before == after; ok &= untouched
    out = dict(what="analyse.py input validation, checked on temporary copies of committed run files; no model forward",
               script="analyse.py of this directory" if script == HERE / "analyse.py" else "another copy of analyse.py (see the file name of this receipt)",
               script_sha256=sha(script), committed_sha256=before, committed_run_files_untouched=untouched,
               n_cases=len(cases), n_ok=sum(1 for c in cases if c["ok"]), cases=cases, all_ok=bool(ok))
    if receipt: Path(receipt).write_text(json.dumps(out, indent=1) + "\n")
    for c in cases: print("ok  " if c["ok"] else "FAIL", c["case"], "exit", c["exit_code"])
    print("committed run files untouched:", untouched); print(f"{out['n_ok']}/{out['n_cases']} cases as stated;", "ALL OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)

if __name__ == "__main__": main()
