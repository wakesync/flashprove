#!/usr/bin/env python3
"""10-prompt merge and verdict (PREREG.md merge rule). Light, no weights.

Usage: merge10.py <run1 dir> <run2 dir or -> <out dir> [<pr139 runs dir>]

- Checks PR #139's committed D file by sha256 (PREREG), then builds the 10-prompt input: PR #139's committed D for its
  9 prompts, this run's D (run 1) for p03-repeat-word. Nothing else is accepted as the full-set input.
- Fail-closed input validation (exit 2, nothing written) of every per-position value used, the p03 position count
  (512), the expected tensor coverage of this run's manifests (stock 850 + embedding row 279, abl 71).
- Gate (b) on p03 bit for bit (the issue's rule) and with PR #139's 1e-6 rule; gate (c) over this run's and PR #139's
  manifests against PR #124's and PR #87's committed hashes; gate (a) and the D vs E statistics and verdict by PR #139's
  analyse.analyse(), imported unchanged.
- Determinism: run 2's per-position arrays equal to run 1's bit for bit (if run 2 is given).
Writes <out dir>/merged-analysis.json and <out dir>/merge-validation.json, never overwrites.
Exit 0 = gates pass, verdict written; 2 = invalid input (including malformed JSON, duplicate keys, missing prompts or
keys); 3 = KILLED (validity gate); 4 = output exists.
"""
import hashlib, json, math, re, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
P139 = EXP / "20261112-134-u1-margin"

def sha_file(p):
    h = hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()

# Committed identity of PR #139's analyse.py, checked before it is imported (round-2 review hardening).
ANALYSE_SHA = "92afcd5623259c829b45a173f0ed2e40099aed5b0ee3f29492a590b3fd4b6a69"
try: _ok = sha_file(P139 / "analyse.py") == ANALYSE_SHA
except OSError: _ok = False
if not _ok:
    print("INVALID, nothing written:\n - PR #139 analyse.py: missing or sha256 is not the committed one", file=sys.stderr); sys.exit(2)
sys.path.insert(0, str(P139))
import analyse as A        # PR #139, unchanged
P124D = EXP / "20261111-8-qwen-e2e-agreement"; P124 = P124D / "runs"
P87 = EXP / "20261110-36-weight-binding" / "runs"
PID = "p03-repeat-word"; T03 = 512; TOK03 = 279
D139_SHA = "74f5fa123723b6bb8cd7c4b4c8d511a6be8c7c55a8cad4a37796c2fc9740460f"
# Committed sha256 of every other fixed (reused) input file. Round-2 review: the reused PR #124 E files were read from
# working-tree paths without an identity check, so a corrupted copy (e.g. negative XS18 KL) could change the verdict.
# Any mismatch now exits 2 with nothing written. Values are the sha256 of the files as committed on main.
PINNED_FIXED = {
    P124 / "e2e-stock.json": "1e066da307b848e007ffdf39823c9b2a245f8bcc27a7aa38c05bc54d7c5d3fa8",       # PR #124 E (stock)
    P124 / "e2e-abl.json": "614f49f56b5fb905b391de29b2357b3e9304850881010709e78b8e4f62decc88",         # PR #124 E (abl)
    P124 / "manifest-stock.json": "cbcf30147e00f2472c6b2e6938a4ea3c720b068ef16458446ef45559bf2f2e73",
    P124 / "manifest-abl.json": "2ef8f90d8c39e99b6b1fae9cf14b0fa2044b5f0a527cd40e7789268b6c014918",
    P124D / "prompts-e2e.json": "47aa61b46e142382ffa58b88f918df6ec63f1158629df5938ec00961a5242cfc",
    P87 / "manifest-stock.json": "bef43106f808d91a26731122bcbfdde0f43d353beb4354f6184c7c98176393ab",
    P87 / "manifest-abl.json": "66269fc451c52b3a5a370cb789c037e7b126a6a09b5a1203b09cbaa357ea975f",
}
# PR #139 committed files read from the PR #139 runs dir (D is D139_SHA above).
PINNED_139 = {
    "manifest-stock.json": "735fe50d3aeaf0d9f3487c50c711e9e8139d9accc8f8a75a40b99cd967ca5ba8",
    "manifest-abl.json": "cc479c57e7acf34deaf4509328219174f3e118de1ba3abfceb3067ea6b38b814",
    "analysis.json": "d7d127f697c317b5ac6198d838076adc31bca0443c5242842d6e7122f7c54a11",
}

def check_pins(R139):
    bad = []
    for p, h in [*PINNED_FIXED.items(), *((R139 / f, h) for f, h in PINNED_139.items())]:
        try: ok = sha_file(p) == h
        except OSError: ok = False
        if not ok: bad.append(f"fixed input {p.parent.name}/{p.name}: missing or sha256 is not the committed one")
    return bad
LAYER = re.compile(r"^model\.language_model\.layers\.(\d+)\.")
NORM, LM_HEAD = A.NORM, A.LM_HEAD
ARR_KEYS = ("stock_top1", "abl_top1", "stock_margin", "abl_margin", "D_kl_stock_abl", "kl_abl_stock")
OUTS = ("merged-analysis.json", "merge-validation.json")

def jl(p): return json.loads(Path(p).read_text(), object_pairs_hook=A.no_dup)

def check_p03(bad, r, where):
    if not isinstance(r, dict) or not A.is_int(r.get("T")) or r["T"] != T03:
        bad.append(f"{where}: T is not {T03}"); return
    for k in ("stock_top1", "abl_top1"): A.arr(bad, f"{where}.{k}", r.get(k), T03, A.is_int, 0, A.VOCAB - 1)
    for k in ("stock_margin", "abl_margin"): A.arr(bad, f"{where}.{k}", r.get(k), T03, A.is_num, 0.0)
    A.arr(bad, f"{where}.D_kl_stock_abl", r.get("D_kl_stock_abl"), T03, A.is_num, -1e-9)
    A.arr(bad, f"{where}.kl_abl_stock", r.get("kl_abl_stock"), T03, A.is_num, -1e-9)

def compute(argv):
    r1 = Path(argv[1]); r2 = None if argv[2] == "-" else Path(argv[2]); OUT = Path(argv[3])
    R139 = Path(argv[4]) if len(argv) > 4 else P139 / "runs"
    if any((OUT / f).exists() for f in OUTS): print("NOT RUN: output exists", file=sys.stderr); return 4
    bad = check_pins(R139)
    if bad: return invalid(bad)
    # PR #139 committed inputs
    if sha_file(R139 / "d-per-position.json") != D139_SHA: bad.append("PR #139 D file: sha256 is not the registered one")
    d139 = jl(R139 / "d-per-position.json")["prompts"]
    nine = [p for p in A.FULL if p != PID]
    if sorted(d139) != sorted(nine): bad.append("PR #139 D file: prompts are not the 9 of tier 2")
    # this run
    d1 = jl(r1 / "d-p03.json")["prompts"] if (r1 / "d-p03.json").is_file() else None
    if d1 is None or list(d1) != [PID]: bad.append("run 1: d-p03.json missing or not exactly p03-repeat-word"); d1 = None
    else: check_p03(bad, d1[PID], "run 1 p03")
    es = jl(P124 / "e2e-stock.json")["prompts"]; ea = jl(P124 / "e2e-abl.json")["prompts"]
    # merged input, validated with PR #139's own per-prompt checks on the 10 prompts
    if bad: return invalid(bad)
    merged = dict(d139); merged[PID] = d1[PID]
    frozen = {p["id"]: p["n_tokens"] for p in jl(P124D / "prompts-e2e.json")["prompts"]}
    for pid in A.FULL:
        r, T = merged[pid], frozen[pid]
        if r.get("T") != T: bad.append(f"{pid}: T is not {T}"); continue
        for k in ("stock_top1", "abl_top1"): A.arr(bad, f"{pid}.{k}", r.get(k), T, A.is_int, 0, A.VOCAB - 1)
        for k in ("stock_margin", "abl_margin"): A.arr(bad, f"{pid}.{k}", r.get(k), T, A.is_num, 0.0)
        A.arr(bad, f"{pid}.D", r.get("D_kl_stock_abl"), T, A.is_num, -1e-9)
        for leg, src in (("stock", es), ("abl", ea)):
            c = src[pid]
            A.arr(bad, f"PR124 {leg} {pid}.ref_top1", c.get("ref_top1"), T, A.is_int, 0, A.VOCAB - 1)
            A.arr(bad, f"PR124 {leg} {pid}.ref_margin", c.get("ref_margin"), T, A.is_num, 0.0)
            for arm in ("XS18", "XS20"):
                a = c["paths"][arm]; A.arr(bad, f"PR124 {leg} {pid}.{arm}.kl", a.get("kl"), T, A.is_num)
                A.arr(bad, f"PR124 {leg} {pid}.{arm}.top1_agree", a.get("top1_agree"), T, A.is_bool)
    # manifests: PR #87 hashes, PR #124 manifests, expected coverage
    b87 = {ck: {t["name"]: t["sha256"] for t in jl(P87 / f"manifest-{ck}.json")["tensors"]} for ck in ("stock", "abl")}
    o124 = {ck: jl(P124 / f"manifest-{ck}.json") for ck in ("stock", "abl")}
    changed = sorted(k for k in b87["stock"] if b87["abl"][k] != b87["stock"][k])
    exp_mine = dict(stock={n for n in b87["stock"] if LAYER.match(n)} | {NORM, LM_HEAD}, abl=set(changed) | {NORM})
    if len(changed) != A.N_CHANGED or len(exp_mine["stock"]) != 850 or len(exp_mine["abl"]) != A.N_ABL:
        bad.append("PR #87 manifests do not give 70 changed / 850 stock / 71 abl")
    mine, theirs = {}, {}
    for ck in ("stock", "abl"):
        m = jl(r1 / f"manifest-{ck}.json"); mine[ck] = m
        if (m.get("repo"), m.get("rev")) != (o124[ck]["repo"], o124[ck]["rev"]): bad.append(f"run 1 manifest {ck}: repo/rev not PR #124's")
        miss = exp_mine[ck] - set(m["tensors"]); unk = set(m["tensors"]) - exp_mine[ck]
        if miss or unk: bad.append(f"run 1 manifest {ck}: {len(miss)} expected tensors missing, {len(unk)} unexpected")
        theirs[ck] = jl(R139 / f"manifest-{ck}.json")["tensors"]
    er = mine["stock"].get("embedding_rows", {})
    if set(er) != {str(TOK03)}: bad.append(f"run 1 stock manifest: embedding rows are not exactly [{TOK03}]")
    if set(mine["abl"].get("embedding_rows", {})): bad.append("run 1 abl manifest: unexpected embedding rows")
    if bad: return invalid(bad)
    # gate (c) over this run + PR #139 (union; where both list a tensor the hashes must agree)
    union = {}; conflict = []
    for ck in ("stock", "abl"):
        u = dict(theirs[ck])
        for n, e in mine[ck]["tensors"].items():
            if n in u and u[n]["sha256"] != e["sha256"]: conflict.append(f"{ck}:{n}")
            u[n] = e
        union[ck] = u
    emb_ok = er[str(TOK03)]["sha256"] == o124["stock"]["embedding_rows"][str(TOK03)]["sha256"]
    mine_c = {ck: [n for n, e in mine[ck]["tensors"].items() if e["sha256"] != o124[ck]["tensors"].get(n, {}).get("sha256") or e["sha256"] != b87[ck][n]]
              for ck in ("stock", "abl")}
    v = dict(tr=None, d=merged, es=es, ea=ea, b87=b87,
             exp=dict(stock=exp_mine["stock"], abl=exp_mine["abl"]),
             man={ck: (union[ck], o124[ck]["tensors"]) for ck in ("stock", "abl")})
    out, nonpos = A.analyse(v)                                    # PR #139's statistics, gates (a)/(b 1e-6)/(c), verdict
    # gate (b) on p03 bit for bit (issue rule)
    bb = {}
    for leg, src, top, mar in (("stock", es, "stock_top1", "stock_margin"), ("abl", ea, "abl_top1", "abl_margin")):
        mt = np.array(d1[PID][top]); rt = np.array(src[PID]["ref_top1"]); mm = np.array(d1[PID][mar]); rm = np.array(src[PID]["ref_margin"])
        bb[leg] = dict(top1_equal=bool(np.array_equal(mt, rt)), n_top1_diff=int((mt != rt).sum()),
                       margin_bit_equal=bool(np.array_equal(mm.view(np.uint64), rm.view(np.uint64))),
                       n_margin_diff=int((mm != rm).sum()), max_abs_margin_diff=float(np.abs(mm - rm).max()))
    gb03 = all(x["top1_equal"] and x["margin_bit_equal"] for x in bb.values())
    gc_mine = not any(mine_c.values()) and emb_ok and not conflict
    valid = bool(out["gates"]["all_ok"] and gb03 and gc_mine)
    if not valid and not out["verdict"]["verdict"].startswith("KILLED"): out["verdict"]["verdict"] = "KILLED (validity gate)"
    out["gates"]["b_p03_bit_for_bit"] = dict(ok=gb03, **bb)
    out["gates"]["c_this_run"] = dict(ok=gc_mine, stock_tensors=len(mine["stock"]["tensors"]), abl_tensors=len(mine["abl"]["tensors"]),
                                      mismatch=mine_c, embedding_row_279_equal_pr124=emb_ok, conflicts_with_pr139=conflict)
    out["gates"]["all_ok"] = valid
    # p03 alone, extra percentiles (same formula as analyse.py's pooled log10r)
    D = np.array(d1[PID]["D_kl_stock_abl"]); p03 = {}
    for arm in ("XS18", "XS20"):
        Ev = np.maximum(np.array(es[PID]["paths"][arm]["kl"]), np.array(ea[PID]["paths"][arm]["kl"]))
        rr = np.where(Ev > 0, D / np.where(Ev > 0, Ev, 1), np.inf); lr = np.log10(rr[np.isfinite(rr)])
        p03[arm] = dict(n=int(len(rr)), share_gt10=float((rr > 10).mean()), share_gt100=float((rr > 100).mean()),
                        n_gt10=int((rr > 10).sum()), n_gt100=int((rr > 100).sum()),
                        log10r=dict(median=A.q(lr, 50), sd=float(lr.std()), min=float(lr.min()), max=float(lr.max()),
                                    p1=A.q(lr, 1), p10=A.q(lr, 10), p90=A.q(lr, 90)),
                        E_median=float(np.median(Ev)), E_max=float(Ev.max()), sumD_over_sumE=float(D.sum() / Ev.sum()),
                        n_E_nonpos=int((Ev <= 0).sum()))
    p03["D"] = dict(median=float(np.median(D)), max=float(D.max()), min=float(D.min()), p10=A.q(D, 10), p90=A.q(D, 90))
    p03["reverse_kl_median"] = float(np.median(d1[PID]["kl_abl_stock"]))
    p03["top1_differ"] = out["prompts"][PID]["top1_differ"]
    # determinism run 1 vs run 2
    det = None
    if r2 is not None:
        f2 = r2 / "d-p03.json"
        if not f2.is_file(): det = dict(shown=False, reason="run 2 did not write d-p03.json")
        else:
            d2 = jl(f2)["prompts"][PID]
            eq = {k: bool(np.array_equal(np.array(d1[PID][k]), np.array(d2[k]))) for k in ARR_KEYS}
            sh = {k: [hashlib.sha256(np.array(x[k]).tobytes()).hexdigest() for x in (d1[PID], d2)] for k in ARR_KEYS}
            det = dict(shown=True, all_bit_equal=all(eq.values()), equal=eq, sha256_run1_run2=sh)
    # PR #139 9-prompt numbers, unchanged, from its committed analysis
    a139 = jl(R139 / "analysis.json")
    nine_view = dict(source="experiments/20261112-134-u1-margin/runs/analysis.json (committed, unchanged)",
                     verdict=a139["verdict"], pooled_XS18=a139["pooled"]["XS18"], pooled_XS20=a139["pooled"]["XS20"],
                     D=a139["pooled"]["D"], top1_differ=a139["pooled"]["top1_differ"])
    res = dict(note="10-prompt merge per PREREG: PR #139 committed D for 9 prompts + this run's D (run 1) for p03-repeat-word; "
                    "statistics and verdict by PR #139's analyse.analyse() unchanged",
               p03_alone=p03, ten=out, nine_pr139=nine_view, determinism=det, E_nonpositive=nonpos)
    text = json.dumps(res, indent=1, allow_nan=False) + "\n"
    val = dict(pr139_d_sha256=D139_SHA, run1=str(r1.name), run2=(r2.name if r2 else None), prompts=A.FULL,
               positions=sum(merged[p]["T"] for p in A.FULL), gates={k: (g if isinstance(g, bool) else g.get("ok")) for k, g in out["gates"].items()},
               verdict=out["verdict"]["verdict"])
    summary = dict(verdict=out["verdict"], gates=val["gates"], p03_XS18=p03["XS18"], p03_D=p03["D"], top1_p03=p03["top1_differ"],
                   ten_XS18=out["pooled"]["XS18"], determinism=(det or {}).get("all_bit_equal"))
    return OUT, text, val, summary, valid

# Validation-only hardening after the PR #162 reviews: malformed or truncated JSON, duplicate keys, an absent prompt
# or arm in PR #124's E files, or any other missing key now exits 2 ("INVALID, nothing written") instead of an
# uncaught traceback (exit 1). Nothing is written before every input has been read and checked. The statistics, gates,
# verdict and the bytes written for valid input are unchanged.
MALFORMED = (KeyError, IndexError, TypeError, ValueError, AttributeError, OSError)

def main(argv):
    try: r = compute(argv)
    except MALFORMED as e:
        return invalid([f"malformed or incomplete input ({type(e).__name__}: {e})"])
    if isinstance(r, int): return r
    OUT, text, val, summary, valid = r
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "merged-analysis.json").write_text(text); (OUT / "merge-validation.json").write_text(json.dumps(val, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    return 0 if valid else 3

def invalid(bad):
    print("INVALID, nothing written:", file=sys.stderr)
    for b in bad: print(" -", b, file=sys.stderr)
    return 2

if __name__ == "__main__":
    sys.exit(main(sys.argv))
