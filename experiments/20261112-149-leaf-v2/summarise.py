#!/usr/bin/env python3
"""Summarise run1 (and run2 if present) of 20261112-149-leaf-v2 into runs/summary.json. Reads committed run files only.
Usage (from the top of the tree): python3 experiments/20261112-149-leaf-v2/summarise.py"""
import json, statistics
from pathlib import Path

D = Path(__file__).resolve().parent / "runs"


def load(run):
    p = D / run / "blocks.jsonl"
    return [json.loads(l) for l in open(p)] if p.exists() else []


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


def main():
    out = {"note": "summary of committed run files, hash level, NOT A PROOF; measured, unreplicated"}
    for run in ("run1", "run2", "run3"):
        recs = load(run)
        if recs:
            out[run] = summ(recs)
            out[run + "_per_tensor"] = [dict(name=r["name"], kind=r["kind"], e_stock=r["stock"]["e"], e_abl=r["abl"]["e"],
                                             int_sha256_stock=r["stock"]["int_sha256"], int_sha256_abl=r["abl"]["int_sha256"],
                                             int_entries_differing=r.get("int_entries_differing"),
                                             int_fraction_differing=r.get("int_fraction_differing"),
                                             max_abs_int_delta=r.get("max_abs_int_delta"), elements=r["elements"])
                                        for r in recs] if run == "run1" else None
    # Not registered (descriptive cross-check): PR #87's committed integer hashes for its 7 tensors.
    p87 = D.parent.parent / "20261110-36-weight-binding/runs/h2h3-int.json"
    r1 = {r["name"]: r for r in load("run1")}
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
    h3 = {}
    union, union_ok = set(), True
    for other in ("run2", "run3"):
        cmp = D / ("compare-run1-%s.json" % other)
        if cmp.exists():
            c = json.load(open(cmp))
            h3[other] = {k: v for k, v in c.items() if k != "rows"}
            for r in c["rows"]:
                union.add((r["name"], r["kind"]))
                union_ok &= r["identical"]
    if h3:
        h3["union"] = dict(n_blocks=len(union), n_controls=sum(1 for _, k in union if k == "control"),
                           n_changed=sum(1 for _, k in union if k == "changed"), all_identical=union_ok,
                           note="PREREG amendment A-1: H3 on the union of run2 and run3, each vs run1")
        out["h3"] = h3
    out = {k: v for k, v in out.items() if v is not None}
    with open(D / "summary.json", "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    for run in ("run1", "run2", "run3"):
        if run in out:
            print(run, json.dumps({k: v for k, v in out[run].items() if k not in ("by_family",)}, sort_keys=True))
    if "h3" in out:
        print("h3", json.dumps(out["h3"], sort_keys=True))
    if "crosscheck_pr87" in out:
        print("crosscheck_pr87", out["crosscheck_pr87"]["n"], out["crosscheck_pr87"]["all_equal"])


if __name__ == "__main__":
    main()
