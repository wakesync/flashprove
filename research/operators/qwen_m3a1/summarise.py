#!/usr/bin/env python3
"""Summary of the registered runs (runs/*.json, each written once by run_registered.py) into runs/summary.json.
Usage: summarise.py <runs_dir>"""
import json, statistics, sys
from pathlib import Path

EXPECT = {"H": False, "C": True}


def main():
    runs = Path(sys.argv[1])
    honest, cases = [], {}
    for p in sorted(runs.glob("*.json")):
        if not (p.name.startswith("honest-") or p.name.startswith("case-")):
            continue
        rec = json.loads(p.read_text())
        last = json.loads(rec["stdout"][-1])
        if p.name.startswith("honest"):
            honest.append(dict(last, wall_s=rec["wall_s"], max_rss_kb_time=rec["max_rss_kb_time"]))
        else:
            cases[last["case"]] = dict(accepted=last["accepted"], trace_why=last["trace_why"], lin_why=last["lin_why"],
                                       expected_accepted=EXPECT[last["case"][0]], exit=rec["exit"], peak_rss_kb=last["peak_rss_kb"])

    def stat(k):
        v = [h[k] for h in honest]
        return dict(n=len(v), median=statistics.median(v), sd=round(statistics.stdev(v), 4) if len(v) > 1 else 0, min=min(v), max=max(v))
    out = dict(
        label="measured, unreplicated, one shared host, cores 2-7",
        honest=dict(accepted=sum(h["accepted"] for h in honest), n=len(honest),
                    prove_s=stat("prove_s"), verify_s=stat("verify_s"), commit_s=stat("commit_s"), wall_s=stat("wall_s"),
                    peak_rss_kb=stat("peak_rss_kb"), trace_proof_bytes=stat("trace_proof_bytes"), lin_proof_bytes=stat("lin_proof_bytes"),
                    fixed=dict((k, honest[0][k]) for k in ("cells", "product_columns_used", "log_length", "relations", "table_matrix", "table_rows", "table_ell", "table_log_n"))),
        cases=cases,
        all_cases_as_expected=all(c["accepted"] == c["expected_accepted"] and c["exit"] == 0 for c in cases.values()),
    )
    (runs / "summary.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(dict(honest_accepted=out["honest"]["accepted"], all_cases_as_expected=out["all_cases_as_expected"],
                          prove_s=out["honest"]["prove_s"], verify_s=out["honest"]["verify_s"], peak_rss_kb=out["honest"]["peak_rss_kb"])))


if __name__ == "__main__":
    main()
