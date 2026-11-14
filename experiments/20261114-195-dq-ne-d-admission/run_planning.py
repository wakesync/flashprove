#!/usr/bin/env python3
"""Registered planning cases of experiment 20261114-195-dq-ne-d-admission: T7b, T2, T7c.

usage: run_planning.py <repo> <base cp_verify> <patched cp_verify> <new work folder> <output folder> <round, 1 to 5>
       run_planning.py summarise <output folder>

One call runs one round (so that no single command needs more than two minutes of CPU): it makes
each case's kit (kits.py; the same bytes every round, which summarise checks by hash), then runs
each binary on a fresh copy of it, base first in odd rounds and patched first in even rounds:
  -plan arrays; if it lists arrays, prover/tools/pack_layout.py makes layout.txt;
  -plan accounting <kit> 128; if that plans, -plan request with the layout at 0 and at 128 bits.
T7b kits keep the source kit's layout.txt and get the accounting call only.
Every cp_verify call has a 4 GiB address-space limit and a 110 s wall limit. Its output, with the
work folder's path replaced by <work>, goes to <output folder>/raw/. No proof is read or made.
"""
import importlib.util
import json
import os
import pathlib
import resource
import shutil
import struct
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("kits", HERE / "kits.py")
kits = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kits)

SMALL = "prover/tests/configurations/pinned_no_proof_of_work"
T2_LINES = {"lmS": "10", "kFD": "12", "ranges-part": "10"}
T7C_LINES = {"lmS": "10", "table": "11,32,402653184,44040191,0,18", "ranges-part": "13", "group link": "1,18,17,17,15"}
# name: (kind, the changed lines, expected last line on base, expectation on patched)
CASES = {
    "T7b-above": ("bound", {"d": "512", "H": "3", "G": "1", "dh": str(1 << 19)}, "NO: shape-heads", "NO: shape-heads"),
    "T7b-one-step-above": ("bound", {"d": "512", "H": "33", "G": "1", "dh": "32768"}, "NO: shape-heads", "NO: shape-heads"),
    "T7b-at-exact": ("bound", {"d": "512", "H": "32", "G": "1", "dh": "32768"}, "NO: shape-heads", "refused-not-shape-heads"),
    "T7b-at-design": ("bound", {"d": "512", "H": "1", "G": "1", "dh": str(1 << 20)}, "NO: shape-heads", "refused-not-shape-heads"),
    "T2-dq-above-d": ("plan", dict(T2_LINES, d="8", H="3", G="1", dh="4"), "NO: shape-heads", "planned"),
    "T2-dq-below-d": ("plan", dict(T2_LINES, d="8", H="1", G="1", dh="4"), "NO: shape-heads", "planned"),
    "T7c-dq-8064": ("plan", dict(T7C_LINES, d="4096", H="63", G="1", dh="128"), "NO: shape-heads", "planned"),
}


def call(args, cwd, keep, work):
    """One cp_verify call: status, last line, counted lines, peak resident KiB (wait4), seconds."""
    t0 = time.time()
    p = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (kits.AS_LIMIT, kits.AS_LIMIT)))
    timer = time.time() + 110
    chunks, timed_out = [], False
    import select
    while True:
        left = timer - time.time()
        if left <= 0:
            timed_out = True
            p.kill()
            break
        if select.select([p.stdout], [], [], left)[0]:
            b = os.read(p.stdout.fileno(), 1 << 16)
            if not b:
                break
            chunks.append(b)
    p.stdout.close()
    _, st, ru = os.wait4(p.pid, 0)
    p.returncode = 0
    status = "timeout" if timed_out else os.WEXITSTATUS(st) if os.WIFEXITED(st) else "signal %d" % os.WTERMSIG(st)
    text = b"".join(chunks).decode(errors="replace").replace(str(work), "<work>")
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_text(text)
    lines = text.splitlines()
    return {"status": status, "last": lines[-1] if lines else "", "lines": lines, "peak_rss_kib": ru.ru_maxrss, "seconds": round(time.time() - t0, 2)}


def one(repo, binary, src, kind, work, raw, tag):
    """All calls of one binary on a fresh copy of one kit."""
    kit = work / "play" / tag
    shutil.copytree(src, kit)
    out = {}
    if kind == "plan":
        a = call([binary, "-plan", "arrays", tag, "128"], work / "play", raw / (tag + ".arrays.txt"), work)
        n = sum(l.startswith("array:") for l in a["lines"])
        out["arrays"] = {"status": a["status"], "last": a["last"], "array_lines": n, "peak_rss_kib": a["peak_rss_kib"]}
        if a["status"] == 4 and n:
            l = next(x.split()[4] for x in (kit / "policy.txt").read_text().splitlines() if x.startswith("group link "))
            r = subprocess.run([sys.executable, "-B", str(repo / "prover/tools/pack_layout.py"), "--arrays", "-", l, "4"],
                               input="\n".join(a["lines"]) + "\n", capture_output=True, text=True)
            out["pack_layout"] = {"status": r.returncode, "said": r.stderr.strip()[:120]}
            if r.returncode == 0:
                (kit / "layout.txt").write_text(r.stdout)
    c = call([binary, "-plan", "accounting", tag, "128"], work / "play", raw / (tag + ".accounting.txt"), work)
    out["accounting"] = {"status": c["status"], "last": c["last"], "peak_rss_kib": c["peak_rss_kib"], "seconds": c["seconds"],
                         "rounds_hold_lines": sum(l.startswith("accounting: THE ROUNDS: HOLD") for l in c["lines"]),
                         "internal_lines": sum("internal-" in l for l in c["lines"]),
                         "not_standard_form": [l[:200] for l in c["lines"] if l.startswith("plan: not the standard parameter form")]}
    out["planned"] = bool(c["status"] == 4 and c["last"] == "PLAN ONLY: no proof was checked" and out["accounting"]["rounds_hold_lines"] == 1 and not out["accounting"]["internal_lines"])
    if kind == "plan" and out["planned"]:
        T = 1 << int(next(x.split()[1] for x in (kit / "policy.txt").read_text().splitlines() if x.startswith("lt ")))
        (kit / "req").write_bytes(struct.pack("<%dI" % (T + 2), *([0] * T + [T - 1, T])))
        (kit / "y").write_bytes(struct.pack("<I", 0))
        for bits in ("0", "128"):
            q = call([binary, "-plan", "request", tag + "/policy.txt", tag + "/KL.bin", bits, "-layout", tag + "/layout.txt", "-prompt", tag + "/req", "-reply", tag + "/y", "-q"],
                     work / "play", raw / (tag + ".request-%s.txt" % bits), work)
            out["request_%s" % bits] = {"status": q["status"], "last": q["last"], "peak_rss_kib": q["peak_rss_kib"], "internal_lines": sum("internal-" in l for l in q["lines"])}
    shutil.rmtree(kit)
    return out


def held(name, which, r):
    """Whether one binary's outcome on one case is the registered one."""
    kind, _, base_last, patched = CASES[name]
    a = r["accounting"]
    if which == "base":
        return a["status"] == 1 and a["last"] == base_last
    if patched == "planned":
        return bool(r["planned"] and r.get("arrays", {}).get("status") == 4 and r.get("pack_layout", {}).get("status") == 0
                    and all(r.get("request_%s" % b, {}).get("status") == 4 and not r["request_%s" % b]["internal_lines"] for b in ("0", "128")))
    if patched == "refused-not-shape-heads":
        return a["status"] == 1 and a["last"].startswith("NO: ") and a["last"] != "NO: shape-heads" and "internal-" not in a["last"]
    return a["status"] == 1 and a["last"] == patched


def summarise(outdir):
    import hashlib
    records, kit_hashes = [], {}
    files = sorted(outdir.glob("planning-round-*.json"))
    for f in files:
        data = json.loads(f.read_text())
        records += data["records"]
        for name, digest in data["kit_sha256"].items():
            kit_hashes.setdefault(name, set()).add(digest)
    summary = {}
    for name in CASES:
        for which in ("base", "patched"):
            rows = [r for r in records if r["case"] == name and r["binary"] == which]
            summary["%s.%s" % (name, which)] = {
                "n": len(rows), "as_registered": sum(r["as_registered"] for r in rows),
                "outcomes": sorted({"%s | %s" % (r["accounting"]["status"], r["accounting"]["last"]) for r in rows}),
                "peak_rss_kib_max": max([0] + [max([r["accounting"]["peak_rss_kib"]] + [r[k]["peak_rss_kib"] for k in ("arrays", "request_0", "request_128") if k in r]) for r in rows]),
                "not_standard_form": sorted({l for r in rows for l in r["accounting"]["not_standard_form"]})}
    bad = sum(1 for r in records if not r["as_registered"])
    one_kit = all(len(v) == 1 for v in kit_hashes.values())
    (outdir / "planning-summary.json").write_text(json.dumps({"round_files": [f.name for f in files], "records": len(records), "not_as_registered": bad,
                                                             "each_kit_same_bytes_every_round": one_kit, "kit_sha256": {k: sorted(v) for k, v in kit_hashes.items()}, "cases": summary}, indent=1) + "\n")
    for key, s in summary.items():
        print("%-28s n=%d as registered=%d peak %d KiB | %s" % (key, s["n"], s["as_registered"], s["peak_rss_kib_max"], " ;; ".join(s["outcomes"])))
    print("run_planning.py summarise: %d round files, %d records, %d not as registered; each kit the same bytes every round: %s" % (len(files), len(records), bad, one_kit))
    return 1 if bad or not one_kit else 0


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "summarise":
        return summarise(pathlib.Path(sys.argv[2]).resolve())
    if len(sys.argv) != 7 or sys.argv[6] not in ("1", "2", "3", "4", "5"):
        sys.exit(__doc__)
    import hashlib
    repo, work, outdir = pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[4]).resolve(), pathlib.Path(sys.argv[5]).resolve()
    binaries = {"base": str(pathlib.Path(sys.argv[2]).resolve()), "patched": str(pathlib.Path(sys.argv[3]).resolve())}
    rnd = int(sys.argv[6])
    work.mkdir(parents=True)
    outdir.mkdir(parents=True, exist_ok=True)
    raw = outdir / "raw"
    kitdir = outdir / "kits"
    records, kit_sha = [], {}
    for name, (kind, changes, _, _) in CASES.items():
        src = work / "kits" / name
        if kind == "bound":  # plain substitution of four lines; the source kit's other files as they are
            shutil.copytree(repo / SMALL, src)
            text = (src / "policy.txt").read_text()
            for k, v in changes.items():
                lines = text.split("\n")
                hit = [i for i, l in enumerate(lines) if l.startswith(k + " ")]
                assert len(hit) == 1, (name, k)
                lines[hit[0]] = "%s %s" % (k, v)
                text = "\n".join(lines)
            (src / "policy.txt").write_text(text)
        else:
            kits.make(str(repo), str(repo / SMALL), str(src), changes)
        (kitdir / name).mkdir(parents=True, exist_ok=True)
        if rnd == 1:
            shutil.copyfile(src / "policy.txt", kitdir / name / "policy.txt")
        kit_sha[name] = hashlib.sha256((src / "policy.txt").read_bytes() + (src / "KL.bin").read_bytes()).hexdigest()
    for name, (kind, _, _, _) in CASES.items():
        for which in (("base", "patched") if rnd % 2 else ("patched", "base")):
            tag = "%s.%s.%d" % (name, which, rnd)
            r = one(repo, binaries[which], work / "kits" / name, kind, work, raw, tag)
            ok = held(name, which, r)
            records.append({"case": name, "binary": which, "round": rnd, "as_registered": ok, **r})
            print("%-20s %-7s round %d: %s | accounting status %s, %s | peak %d KiB" % (name, which, rnd, "as registered" if ok else "NOT AS REGISTERED",
                  r["accounting"]["status"], r["accounting"]["last"][:60], r["accounting"]["peak_rss_kib"]), flush=True)
            (outdir / ("planning-round-%d.json" % rnd)).write_text(json.dumps({"round": rnd, "kit_sha256": kit_sha, "records": records}, indent=1) + "\n")
    bad = sum(1 for r in records if not r["as_registered"])
    print("run_planning.py: round %d, %d records, %d not as registered" % (rnd, len(records), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
