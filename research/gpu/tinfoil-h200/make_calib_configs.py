#!/usr/bin/env python3
"""Writes the calibration configurations C2 and C3 of experiments/20261112-7-h200-dense-calibration
(issue #140) from prover/examples/target_small_f2_roomy, and records the planner's entry counts.

usage: make_calib_configs.py --cp-verify <cp_verify> --out <new directory> [--receipts <directory>]

Each configuration is target_small_f2_roomy's policy.txt with a few shape lines changed (below), the
eight table-digest blocks (tsilu*, tsig*, trope*, texp*) removed (the verifier takes all of them or
none: `policy-tables`; with lt changed the stored rotary digest no longer matches, `table-digest-rope`),
the iota lines recomputed by verifier/tests/forest_lines.py (as research/operators/qwen_m3/planner_proxy.py
does), its KL.bin unchanged, and a layout.txt made by the repository's own recipe
(verifier/tests/other_parameters_worlds.sh): `cp_verify -plan arrays <dir> <sec>` piped into
prover/tools/pack_layout.py with the link group's message length and 4 free entries.

Entries are counted from the planner's `array:` lines, rows x columns, per link. CPU only, no GPU,
a few seconds. Nothing here says that cp_commit accepts these files (its worst-case check needs the
weights and a GPU build): that is checked in the window, and a refusal is reported (PREREG).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BASE = os.path.join(ROOT, "prover", "examples", "target_small_f2_roomy")
DIGESTS = ("tsilu", "tsig", "trope", "texp")
CONFIGS = {
    "C2": {"lt": 8, "la": 9},
    "C3": {"lt": 9, "la": 10, "f": 2048, "fe": 1024},
}


def put(lines, name, value):
    for i, x in enumerate(lines):
        if x.split(" ")[0] == name:
            lines[i] = "%s %d" % (name, value)
            return
    raise SystemExit("no line " + name)


def policy_text(overrides):
    sys.path.insert(0, os.path.join(ROOT, "verifier", "tests"))
    import forest_lines
    lines = open(os.path.join(BASE, "policy.txt")).read().split("\n")
    for k, v in overrides.items():
        put(lines, k, v)
    lines = [x for x in lines if not any(x.startswith(t) and x[len(t):len(t) + 1].isdigit() for t in DIGESTS)]
    text = "\n".join(lines)
    for k, v in forest_lines.layer(forest_lines.values_of(text), forest_lines.calls_of(text)).items():
        put(lines, k, v)
    return "\n".join(lines)


def count(arrays_text):
    links = {}
    for line in arrays_text.split("\n"):
        if line.startswith("array:"):
            p = line.split()
            links[int(p[1])] = links.get(int(p[1]), 0) + int(p[7]) * int(p[8])
    return links


def plan(cp_verify, d):
    sec = [x.split()[1] for x in open(os.path.join(d, "policy.txt")).read().split("\n") if x.startswith("sec ")][0]
    r = subprocess.run([cp_verify, "-plan", "arrays", d, sec], capture_output=True, text=True)
    if r.returncode != 4:  # 4: PLAN ONLY
        raise SystemExit("%s: planner exit %d: %s" % (d, r.returncode, (r.stdout + r.stderr)[-400:]))
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cp-verify", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--receipts")
    a = ap.parse_args()
    os.mkdir(a.out)
    summary = {}
    for cid, ov in [("C1", None)] + sorted(CONFIGS.items()):
        if ov is None:
            arrays = plan(a.cp_verify, BASE)
        else:
            d = os.path.join(a.out, cid)
            os.mkdir(d)
            with open(os.path.join(d, "policy.txt"), "w") as f:
                f.write(policy_text(ov))
            shutil.copy(os.path.join(BASE, "KL.bin"), d)
            arrays = plan(a.cp_verify, d)
            msg = [x.split()[4] for x in open(os.path.join(d, "policy.txt")).read().split("\n")
                   if x.startswith("group link ")][0]
            r = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "prover", "tools", "pack_layout.py"),
                                "--arrays", "-", msg, "4"], input=arrays, capture_output=True, text=True)
            if r.returncode != 0:
                raise SystemExit("%s: pack_layout exit %d: %s" % (cid, r.returncode, r.stderr[-400:]))
            with open(os.path.join(d, "layout.txt"), "w") as f:
                f.write(r.stdout)
            if plan(a.cp_verify, d) != arrays:  # the planner again, now with the layout beside it
                raise SystemExit("%s: the planner's arrays changed once layout.txt was there" % cid)
        links = count(arrays)
        summary[cid] = {"overrides": ov or {}, "links": len(links), "entries_total": sum(links.values()),
                        "largest_link_entries": max(links.values()), "per_link": links}
        if a.receipts:
            os.makedirs(a.receipts, exist_ok=True)
            with open(os.path.join(a.receipts, "%s.arrays.txt" % cid), "w") as f:
                f.write(arrays)
        print(cid, json.dumps({k: v for k, v in summary[cid].items() if k != "per_link"}))
    if a.receipts:
        with open(os.path.join(a.receipts, "entries.json"), "w") as f:
            f.write(json.dumps(summary, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
