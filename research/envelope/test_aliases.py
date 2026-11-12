#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression tests: one state file reached by several names (post-registration).

  python3 research/envelope/test_aliases.py --cp-verify bin/cp_verify [--repeats 20]
      [--client <client_verify.py>] [--out <results.json>]

Added after the second review round of PR #122 (at head c715045e) found that the client's lock
(`<state>.lock`) and its atomic rename keyed on the state path as given, not on the file: a state
file reached through a symlink, or through a hard link, released the same nonce twice, both when
the two deliveries ran at once and when they ran one after the other. These are post-registration
checks with no pre-registered threshold. Like test_concurrency.py they use the real cp_verify, the
two stored examples and their own TEST label (own keys, nonces, session), never the registered
vectors, and every client call is the command-line client in its own OS process; concurrent calls
are released together by one multiprocessing.Barrier.

The property under test, for every case: at most one RELEASE per nonce, and at most one release
file. The expected outcome for each case:

  symlink-concurrent   state.json, alias.json -> state.json, and dirlink/state.json where
                       dirlink -> the state directory. The same honest envelope delivered by 3
                       processes at once, one through each name: exactly one RELEASE, the other two
                       `REJECT: nonce-consumed`, the nonce consumed once, alias.json and dirlink still
                       symlinks, one lock file (state.json.lock), no temporary file left.
  symlink-sequential   deliver through alias.json, then through state.json, then through
                       dirlink/state.json: RELEASE, then `REJECT: nonce-consumed` twice with the
                       state byte-identical; alias.json still a symlink to state.json.
  symlink-issue        `issue` through alias.json: the request is in state.json and alias.json is
                       still a symlink; then deliver through alias.json and through state.json:
                       RELEASE, then `REJECT: nonce-consumed`.
  hardlink-concurrent  state.json and hard.json, a hard link to it (st_nlink 2). 2 processes at
                       once, one through each name: both `REJECT: error` (exit 2), all three verdict
                       lines printed, no release file, state byte-identical.
  hardlink-sequential  the same, one after the other; then `issue` through either name is refused
                       too (exit 2, state byte-identical); after hard.json is removed (st_nlink 1),
                       delivery through state.json releases once and a second delivery is
                       `REJECT: nonce-consumed`.
  relative-concurrent  3 processes at once, each with its working directory set to the state
                       directory: `state.json` (relative), `sub/../state.json` (relative with `..`)
                       and the absolute path: exactly one RELEASE, two `REJECT: nonce-consumed`.
  relative-sequential  the same three spellings one after the other: RELEASE, then `REJECT:
                       nonce-consumed` twice, state byte-identical after the first.

Pass --client to run the same tests against another client file (for example the client at
c715045e) to show that they detect the defect there. Exit 0 only if every repetition passes.
"""

import argparse
import json
import multiprocessing
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(REPO / "tools" / "manifest"))
import envelope as E  # noqa: E402
import make_vectors as MV  # noqa: E402

LABEL = "post-registration-alias-test"
VERDICT_KEYS = ("signature", "tee", "proof")


def _summ(code, stdout, stderr, wall):
    lines = stdout.rstrip("\n").split("\n")
    return {"exit": code, "last": lines[-1], "stderr": stderr[-400:], "wall_s": round(wall, 3),
            "verdict_lines": [ln.split(":")[0] for ln in lines if ln.split(":")[0] in VERDICT_KEYS],
            "stdout_tail": stdout[-600:]}


def _worker(barrier, words, cwd, queue, index):
    barrier.wait(timeout=60)
    t0 = time.time()
    done = subprocess.run(words, cwd=cwd, capture_output=True, text=True, timeout=600)
    queue.put((index, done.returncode, done.stdout, done.stderr, time.time() - t0))


def run_together(commands):
    """commands: list of (words, cwd). Each in its own OS process, all released by one barrier."""
    ctx = multiprocessing.get_context("fork")
    barrier = ctx.Barrier(len(commands))
    queue = ctx.Queue()
    procs = [ctx.Process(target=_worker, args=(barrier, w, c, queue, i))
             for i, (w, c) in enumerate(commands)]
    for p in procs:
        p.start()
    out = sorted(queue.get(timeout=900) for _ in procs)
    for p in procs:
        p.join(timeout=60)
    return [_summ(o[1], o[2], o[3], o[4]) for o in out]


def run_one(words, cwd=None):
    t0 = time.time()
    done = subprocess.run(words, cwd=cwd, capture_output=True, text=True, timeout=600)
    return _summ(done.returncode, done.stdout, done.stderr, time.time() - t0)


class Env:
    def __init__(self, client, cp_verify, root):
        self.client = str(client)
        self.cp_verify = str(cp_verify)
        self.root = pathlib.Path(root)
        build = json.loads((HERE / "vectors" / "INDEX.json").read_text())["verifier_build"]
        self.g = MV.Gen(LABEL, build)
        self.ex = self.g.fx["exact"]

    def fresh(self, name, issue=True):
        """A new directory with context, reply, proof, and (if issue) a state file holding one
        outstanding exact request and its honest envelope. Returns (dir, nonce)."""
        d = pathlib.Path(tempfile.mkdtemp(prefix=name + "-", dir=str(self.root)))
        (d / "context.json").write_bytes(E.canonical(self.g.context()))
        (d / "reply.bin").write_bytes(E.tokens_bytes(self.ex.reply))
        (d / "proof.bin").write_bytes(self.ex.proof)
        (d / "prompt.bin").write_bytes(E.tokens_bytes(self.ex.prompt))
        n = None
        if issue:
            st = self.g.state()
            n, rec = self.g.issue(st, name, "exact")
            (d / "state.json").write_bytes(E.canonical(st))
            (d / "env").write_bytes(self.g.seal(self.g.body(self.ex, rec, n)))
        return d, n

    def deliver(self, d, n, state, release):
        return [sys.executable, "-I", self.client, "deliver", "--context", str(d / "context.json"),
                "--state", str(state), "--root", str(REPO), "--deliver", n,
                "--envelope", str(d / "env"), "--reply", str(d / "reply.bin"),
                "--proof", str(d / "proof.bin"), "--now", str(MV.NOW), "--release", str(release),
                "--cp-verify", self.cp_verify]

    def issue(self, d, state, nonce):
        ex = self.ex
        return [sys.executable, "-I", self.client, "issue", "--context", str(d / "context.json"),
                "--state", str(state), "--model", ex.id, "--nonce", nonce,
                "--prompt", str(d / "prompt.bin"), "--e", str(ex.e),
                "--max-tokens", str(ex.max_tokens)]


def leftovers(*dirs):
    found = []
    for d in dirs:
        if d.is_dir():
            found += [p.name for p in d.iterdir() if p.name.endswith(".tmp")]
    return found


def releases(d, names):
    return sum((d / x).exists() for x in names)


def state_of(d):
    return E.parse_canonical((d / "state.json").read_bytes())


def case_symlink_concurrent(env, rep):
    d, n = env.fresh("symlink-concurrent-%02d" % rep)
    os.symlink("state.json", str(d / "alias.json"))
    dirlink = env.root / ("dirlink-%s" % d.name)
    os.symlink(str(d), str(dirlink))
    names = ["rel-%d" % i for i in range(3)]
    paths = [d / "state.json", d / "alias.json", dirlink / "state.json"]
    outs = run_together([(env.deliver(d, n, p, d / r), None) for p, r in zip(paths, names)])
    final = state_of(d)
    lasts = [o["last"] for o in outs]
    locks = sorted(p.name for p in d.iterdir() if p.name.endswith(".lock"))
    nrel = releases(d, names)
    ok = (lasts.count("RELEASE") == 1 and lasts.count("REJECT: nonce-consumed") == 2 and nrel == 1
          and final["consumed"] == [n] and len(final["released"]) == 1
          and os.path.islink(str(d / "alias.json")) and os.path.islink(str(dirlink))
          and locks == ["state.json.lock"] and not leftovers(d))
    dirlink.unlink()
    return {"case": "symlink-concurrent", "rep": rep, "ok": ok, "lasts": lasts,
            "release_files": nrel, "releases_of_nonce": lasts.count("RELEASE"),
            "consumed": len(final["consumed"]), "lock_files": locks,
            "alias_still_symlink": os.path.islink(str(d / "alias.json")),
            "leftover_tmp": leftovers(d)}


def case_symlink_sequential(env, rep):
    d, n = env.fresh("symlink-sequential-%02d" % rep)
    os.symlink("state.json", str(d / "alias.json"))
    dirlink = env.root / ("dirlink-%s" % d.name)
    os.symlink(str(d), str(dirlink))
    lasts, unchanged = [], []
    for i, p in enumerate([d / "alias.json", d / "state.json", dirlink / "state.json"]):
        before = (d / "state.json").read_bytes()
        o = run_one(env.deliver(d, n, p, d / ("rel-%d" % i)))
        lasts.append(o["last"])
        unchanged.append((d / "state.json").read_bytes() == before)
    nrel = releases(d, ["rel-%d" % i for i in range(3)])
    final = state_of(d)
    ok = (lasts == ["RELEASE", "REJECT: nonce-consumed", "REJECT: nonce-consumed"]
          and unchanged[1:] == [True, True] and nrel == 1 and final["consumed"] == [n]
          and os.path.islink(str(d / "alias.json"))
          and os.readlink(str(d / "alias.json")) == "state.json" and not leftovers(d))
    dirlink.unlink()
    return {"case": "symlink-sequential", "rep": rep, "ok": ok, "lasts": lasts,
            "release_files": nrel, "releases_of_nonce": lasts.count("RELEASE"),
            "state_unchanged_after_first": unchanged[1:],
            "alias_still_symlink": os.path.islink(str(d / "alias.json")),
            "leftover_tmp": leftovers(d)}


def case_symlink_issue(env, rep):
    """`issue` through the symlink: the request lands in state.json, alias.json stays a symlink,
    and then one delivery through each name releases once."""
    d, _ = env.fresh("symlink-issue-%02d" % rep, issue=False)
    (d / "state.json").write_bytes(E.canonical(env.g.state()))
    os.symlink("state.json", str(d / "alias.json"))
    n = MV.nonce(LABEL, "symlink-issue-%02d" % rep)
    iss = run_one(env.issue(d, d / "alias.json", n))
    alias_link = os.path.islink(str(d / "alias.json"))
    rec = state_of(d)["outstanding"].get(n)
    lasts = []
    if rec is not None:
        (d / "env").write_bytes(env.g.seal(env.g.body(env.ex, rec, n)))
        for i, p in enumerate([d / "alias.json", d / "state.json"]):
            lasts.append(run_one(env.deliver(d, n, p, d / ("rel-%d" % i)))["last"])
    nrel = releases(d, ["rel-0", "rel-1"])
    ok = (iss["exit"] == 0 and alias_link and rec is not None
          and lasts == ["RELEASE", "REJECT: nonce-consumed"] and nrel == 1
          and state_of(d)["consumed"] == [n] and os.path.islink(str(d / "alias.json"))
          and not leftovers(d))
    return {"case": "symlink-issue", "rep": rep, "ok": ok, "issue_exit": iss["exit"],
            "alias_still_symlink_after_issue": alias_link,
            "request_in_state_json": rec is not None, "lasts": lasts, "release_files": nrel,
            "releases_of_nonce": lasts.count("RELEASE"), "leftover_tmp": leftovers(d)}


def case_hardlink_concurrent(env, rep):
    d, n = env.fresh("hardlink-concurrent-%02d" % rep)
    os.link(str(d / "state.json"), str(d / "hard.json"))
    before = (d / "state.json").read_bytes()
    names = ["rel-0", "rel-1"]
    outs = run_together([(env.deliver(d, n, d / "state.json", d / "rel-0"), None),
                         (env.deliver(d, n, d / "hard.json", d / "rel-1"), None)])
    lasts = [o["last"] for o in outs]
    nrel = releases(d, names)
    after = (d / "state.json").read_bytes()
    ok = (lasts == ["REJECT: error", "REJECT: error"] and [o["exit"] for o in outs] == [2, 2]
          and all(o["verdict_lines"] == list(VERDICT_KEYS) for o in outs) and nrel == 0
          and after == before and (d / "hard.json").read_bytes() == before
          and os.stat(str(d / "state.json")).st_nlink == 2 and not leftovers(d))
    return {"case": "hardlink-concurrent", "rep": rep, "ok": ok, "lasts": lasts,
            "exits": [o["exit"] for o in outs], "verdict_lines": [o["verdict_lines"] for o in outs],
            "release_files": nrel, "releases_of_nonce": lasts.count("RELEASE"),
            "state_byte_identical": after == before, "leftover_tmp": leftovers(d)}


def case_hardlink_sequential(env, rep):
    d, n = env.fresh("hardlink-sequential-%02d" % rep)
    os.link(str(d / "state.json"), str(d / "hard.json"))
    before = (d / "state.json").read_bytes()
    seq = []
    for i, p in enumerate((d / "hard.json", d / "state.json")):
        o = run_one(env.deliver(d, n, p, d / ("rel-%d" % i)))
        seq.append({"path": p.name, "exit": o["exit"], "last": o["last"],
                    "verdict_lines": o["verdict_lines"]})
    issues = []
    for p in (d / "hard.json", d / "state.json"):
        o = run_one(env.issue(d, p, MV.nonce(LABEL, "hardlink-issue-%s-%02d" % (p.name, rep))))
        issues.append({"path": p.name, "exit": o["exit"], "last": o["last"]})
    refused_unchanged = (d / "state.json").read_bytes() == before
    (d / "hard.json").unlink()
    after_unlink = []
    for i in (2, 3):
        o = run_one(env.deliver(d, n, d / "state.json", d / ("rel-%d" % i)))
        after_unlink.append(o["last"])
    nrel = releases(d, ["rel-%d" % i for i in range(4)])
    final = state_of(d)
    ok = (all(s["exit"] == 2 and s["last"] == "REJECT: error"
              and s["verdict_lines"] == list(VERDICT_KEYS) for s in seq)
          and all(s["exit"] == 2 and s["last"] == "REJECT: error" for s in issues)
          and refused_unchanged and not (d / "rel-0").exists() and not (d / "rel-1").exists()
          and after_unlink == ["RELEASE", "REJECT: nonce-consumed"] and nrel == 1
          and final["consumed"] == [n] and not leftovers(d))
    return {"case": "hardlink-sequential", "rep": rep, "ok": ok, "deliveries_with_link": seq,
            "issues_with_link": issues, "state_byte_identical_while_linked": refused_unchanged,
            "after_unlink": after_unlink, "release_files": nrel,
            "releases_of_nonce": [s["last"] for s in seq].count("RELEASE")
            + after_unlink.count("RELEASE"), "leftover_tmp": leftovers(d)}


def _relative_paths(d):
    (d / "sub").mkdir()
    return ["state.json", "sub/../state.json", str(d / "state.json")]


def case_relative_concurrent(env, rep):
    d, n = env.fresh("relative-concurrent-%02d" % rep)
    paths = _relative_paths(d)
    names = ["rel-%d" % i for i in range(3)]
    outs = run_together([(env.deliver(d, n, p, d / r), str(d)) for p, r in zip(paths, names)])
    lasts = [o["last"] for o in outs]
    nrel = releases(d, names)
    final = state_of(d)
    ok = (lasts.count("RELEASE") == 1 and lasts.count("REJECT: nonce-consumed") == 2 and nrel == 1
          and final["consumed"] == [n] and len(final["released"]) == 1 and not leftovers(d))
    return {"case": "relative-concurrent", "rep": rep, "ok": ok, "lasts": lasts,
            "release_files": nrel, "releases_of_nonce": lasts.count("RELEASE"),
            "consumed": len(final["consumed"]), "leftover_tmp": leftovers(d)}


def case_relative_sequential(env, rep):
    d, n = env.fresh("relative-sequential-%02d" % rep)
    paths = _relative_paths(d)
    lasts, unchanged = [], []
    for i, p in enumerate(paths):
        before = (d / "state.json").read_bytes()
        o = run_one(env.deliver(d, n, p, d / ("rel-%d" % i)), cwd=str(d))
        lasts.append(o["last"])
        unchanged.append((d / "state.json").read_bytes() == before)
    nrel = releases(d, ["rel-%d" % i for i in range(3)])
    ok = (lasts == ["RELEASE", "REJECT: nonce-consumed", "REJECT: nonce-consumed"]
          and unchanged[1:] == [True, True] and nrel == 1 and state_of(d)["consumed"] == [n]
          and not leftovers(d))
    return {"case": "relative-sequential", "rep": rep, "ok": ok, "lasts": lasts,
            "release_files": nrel, "releases_of_nonce": lasts.count("RELEASE"),
            "state_unchanged_after_first": unchanged[1:], "leftover_tmp": leftovers(d)}


CASES = (case_symlink_concurrent, case_symlink_sequential, case_symlink_issue,
         case_hardlink_concurrent,
         case_hardlink_sequential, case_relative_concurrent, case_relative_sequential)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cp-verify", default=str(REPO / "bin" / "cp_verify"))
    ap.add_argument("--client", default=str(HERE / "client_verify.py"))
    ap.add_argument("--repeats", type=int, default=20)
    ap.add_argument("--out")
    a = ap.parse_args()
    root = pathlib.Path(tempfile.mkdtemp(prefix="fp-envelope-aliases-"))
    env = Env(pathlib.Path(a.client).resolve(), pathlib.Path(a.cp_verify).resolve(), root)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows = []
    try:
        for fn in CASES:
            for rep in range(1, a.repeats + 1):
                row = fn(env, rep)
                rows.append(row)
                print(json.dumps({k: row[k] for k in ("case", "rep", "ok", "releases_of_nonce")}),
                      flush=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    summary = {}
    for r in rows:
        s = summary.setdefault(r["case"], {"runs": 0, "passed": 0, "max_releases_of_nonce": 0,
                                           "runs_with_more_than_one_release": 0})
        s["runs"] += 1
        s["passed"] += bool(r["ok"])
        s["max_releases_of_nonce"] = max(s["max_releases_of_nonce"], r["releases_of_nonce"],
                                         r["release_files"])
        s["runs_with_more_than_one_release"] += max(r["releases_of_nonce"],
                                                    r["release_files"]) > 1
    result = {"label": LABEL, "started_utc": started,
              "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "client": pathlib.Path(a.client).name, "repeats": a.repeats,
              "affinity": sorted(os.sched_getaffinity(0)), "summary": summary, "rows": rows,
              "all_pass": all(r["ok"] for r in rows)}
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    for case, s in summary.items():
        print("%s: %d/%d passed, max releases of one nonce %d" % (
            case, s["passed"], s["runs"], s["max_releases_of_nonce"]))
    print("test_aliases: %s" % ("all ok" if result["all_pass"] else "FAILED"))
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
