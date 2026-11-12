#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression tests for concurrent client processes and output failures (post-registration).

  python3 research/envelope/test_concurrency.py --cp-verify bin/cp_verify [--repeats 20]
      [--client <client_verify.py>] [--out <results.json>]

These tests were added after the registered run of experiments/20261111-9-client-envelope, after
two reviews of PR #122 found that concurrent client processes on one state file could release a
nonce twice or lose a consumption, and that a release-file error after verification consumed the
nonce. They are post-registration checks with no pre-registered threshold. They use the real
cp_verify, the two stored examples, and their own TEST label (own keys, nonces, session), never the
registered vectors. Every client call is the command-line client in its own OS process; concurrent
calls are started together behind a multiprocessing.Barrier.

Cases (each concurrent case repeated --repeats times, default 20):
  same-nonce       the same honest envelope delivered by N=3 processes at once on one state file:
                   exactly one RELEASE, the others `REJECT: nonce-consumed`, the nonce consumed once.
  distinct-nonces  two outstanding requests (exact seq 1, clipped seq 2) delivered at once by two
                   processes: both RELEASE, both consumed, none outstanding; a replay of either
                   envelope afterwards: `REJECT: nonce-consumed`, state unchanged.
  issue-vs-deliver `issue` of a new request racing `deliver` of an outstanding one: both changes are
                   in the final state (the delivered nonce consumed, the new one outstanding,
                   next_seq advanced).
  release-dir-missing  --release inside a directory that does not exist: exit 2, `REJECT: error`,
                   no release file, state file byte-identical.
  post-commit-failure  the release path is taken by another file after the checks and after the
                   output was prepared, just before it is put in place (simulated by a wrapper that
                   creates that file and then calls the client's own place_release): exit 3,
                   `CONSUMED-UNRELEASED`, the nonce consumed, the other file untouched, no
                   temporary file left; a second delivery: `REJECT: nonce-consumed`.
Every case also checks that no temporary file is left next to the state or release files.

Pass --client to run the same tests against another client file (for example the pre-fix client),
to show they fail there. Exit 0 only if every repetition of every case passes.
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

LABEL = "post-registration-concurrency-test"

WRAPPER = r'''
import importlib.util, os, pathlib, sys
spec = importlib.util.spec_from_file_location("client_verify", sys.argv[1])
cv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv)
if not hasattr(cv, "place_release"):
    print("no place_release in this client: post-commit step not separable")
    print("NOT-APPLICABLE")
    sys.exit(97)
original = cv.place_release
def intruder(tmp, path):
    pathlib.Path(path).write_bytes(b"another writer took this path")
    return original(tmp, path)
cv.place_release = intruder
sys.exit(cv.main(sys.argv[2:]))
'''


def _worker(barrier, words, queue, index):
    barrier.wait(timeout=60)
    t0 = time.time()
    done = subprocess.run(words, capture_output=True, text=True, timeout=600)
    queue.put((index, done.returncode, done.stdout, done.stderr, time.time() - t0))


def run_together(commands):
    """Start every command in its own OS process, all released by one barrier."""
    ctx = multiprocessing.get_context("fork")
    barrier = ctx.Barrier(len(commands))
    queue = ctx.Queue()
    procs = [ctx.Process(target=_worker, args=(barrier, c, queue, i))
             for i, c in enumerate(commands)]
    for p in procs:
        p.start()
    out = [queue.get(timeout=900) for _ in procs]
    for p in procs:
        p.join(timeout=60)
    out.sort()
    return [{"exit": o[1], "last": o[2].rstrip("\n").split("\n")[-1], "stdout": o[2],
             "stderr": o[3][-400:], "wall_s": round(o[4], 3)} for o in out]


def run_one(words):
    done = subprocess.run(words, capture_output=True, text=True, timeout=600)
    return {"exit": done.returncode, "last": done.stdout.rstrip("\n").split("\n")[-1],
            "stdout": done.stdout, "stderr": done.stderr[-400:]}


class Env:
    def __init__(self, client, cp_verify, root):
        self.client = str(client)
        self.cp_verify = str(cp_verify)
        self.root = pathlib.Path(root)
        build = json.loads((HERE / "vectors" / "INDEX.json").read_text())["verifier_build"]
        self.g = MV.Gen(LABEL, build)

    def fresh(self, name):
        d = pathlib.Path(tempfile.mkdtemp(prefix=name + "-", dir=str(self.root)))
        (d / "context.json").write_bytes(E.canonical(self.g.context()))
        return d

    def deliver_words(self, d, n, env_file, fx, release, state=None):
        reply = d / ("reply-%s.bin" % fx.name)
        reply.write_bytes(E.tokens_bytes(fx.reply))
        proof = d / ("proof-%s.bin" % fx.name)
        proof.write_bytes(fx.proof)
        return [sys.executable, "-I", self.client, "deliver", "--context", str(d / "context.json"),
                "--state", str(state or d / "state.json"), "--root", str(REPO), "--deliver", n,
                "--envelope", str(env_file), "--reply", str(reply), "--proof", str(proof),
                "--now", str(MV.NOW), "--release", str(release), "--cp-verify", self.cp_verify]


def leftovers(*dirs):
    found = []
    for d in dirs:
        if d.is_dir():
            found += [p.name for p in d.iterdir() if p.name.endswith(".tmp")]
    return found


def case_same_nonce(env, rep, n_procs=3):
    g = env.g
    ex = g.fx["exact"]
    d = env.fresh("same-nonce-%02d" % rep)
    st = g.state()
    n, rec = g.issue(st, "same-%02d" % rep, "exact")
    (d / "state.json").write_bytes(E.canonical(st))
    envf = d / "env"
    envf.write_bytes(g.seal(g.body(ex, rec, n)))
    cmds = [env.deliver_words(d, n, envf, ex, d / ("release-%d.bin" % i)) for i in range(n_procs)]
    outs = run_together(cmds)
    final = E.parse_canonical((d / "state.json").read_bytes())
    lasts = [o["last"] for o in outs]
    released = [(d / ("release-%d.bin" % i)).exists() for i in range(n_procs)]
    ok = (lasts.count("RELEASE") == 1 and lasts.count("REJECT: nonce-consumed") == n_procs - 1
          and sum(released) == 1 and final["consumed"] == [n] and len(final["released"]) == 1
          and not final["outstanding"] and not leftovers(d))
    return {"case": "same-nonce", "rep": rep, "ok": ok, "lasts": lasts, "released": released,
            "consumed": len(final["consumed"]), "released_records": len(final["released"]),
            "leftover_tmp": leftovers(d), "walls": [o["wall_s"] for o in outs]}


def case_distinct(env, rep):
    g = env.g
    ex, cg = g.fx["exact"], g.fx["clipped"]
    d = env.fresh("distinct-%02d" % rep)
    st = g.state()
    na, ra = g.issue(st, "distinct-a-%02d" % rep, "exact")
    nb, rb = g.issue(st, "distinct-b-%02d" % rep, "clipped")
    (d / "state.json").write_bytes(E.canonical(st))
    ea, eb = d / "env-a", d / "env-b"
    ea.write_bytes(g.seal(g.body(ex, ra, na)))
    eb.write_bytes(g.seal(g.body(cg, rb, nb)))
    outs = run_together([env.deliver_words(d, na, ea, ex, d / "release-a.bin"),
                         env.deliver_words(d, nb, eb, cg, d / "release-b.bin")])
    final = E.parse_canonical((d / "state.json").read_bytes())
    both = ([o["last"] for o in outs] == ["RELEASE", "RELEASE"]
            and (d / "release-a.bin").read_bytes() == E.tokens_bytes(ex.reply)
            and (d / "release-b.bin").read_bytes() == E.tokens_bytes(cg.reply)
            and sorted(final["consumed"]) == sorted([na, nb]) and not final["outstanding"]
            and len(final["released"]) == 2)
    replays = []
    for tag, n, e, fx in (("a", na, ea, ex), ("b", nb, eb, cg)):
        before = (d / "state.json").read_bytes()
        rel = d / ("replay-%s.bin" % tag)
        o = run_one(env.deliver_words(d, n, e, fx, rel))
        replays.append({"last": o["last"], "exit": o["exit"], "released": rel.exists(),
                        "state_changed": (d / "state.json").read_bytes() != before})
    replay_ok = all(r["last"] == "REJECT: nonce-consumed" and r["exit"] == 1
                    and not r["released"] and not r["state_changed"] for r in replays)
    return {"case": "distinct-nonces", "rep": rep, "ok": both and replay_ok and not leftovers(d),
            "lasts": [o["last"] for o in outs], "consumed": len(final["consumed"]),
            "outstanding": len(final["outstanding"]), "replays": replays,
            "leftover_tmp": leftovers(d), "walls": [o["wall_s"] for o in outs]}


def case_issue_vs_deliver(env, rep):
    g = env.g
    ex = g.fx["exact"]
    d = env.fresh("issue-deliver-%02d" % rep)
    st = g.state()
    n, rec = g.issue(st, "issued-first-%02d" % rep, "exact")
    (d / "state.json").write_bytes(E.canonical(st))
    envf = d / "env"
    envf.write_bytes(g.seal(g.body(ex, rec, n)))
    new = MV.nonce(LABEL, "issued-during-delivery-%02d" % rep)
    prompt = d / "prompt.bin"
    prompt.write_bytes(E.tokens_bytes(ex.prompt))
    issue = [sys.executable, "-I", env.client, "issue", "--context", str(d / "context.json"),
             "--state", str(d / "state.json"), "--model", ex.id, "--nonce", new,
             "--prompt", str(prompt), "--e", str(ex.e), "--max-tokens", str(ex.max_tokens)]
    outs = run_together([env.deliver_words(d, n, envf, ex, d / "release.bin"), issue])
    final = E.parse_canonical((d / "state.json").read_bytes())
    ok = (outs[0]["last"] == "RELEASE" and outs[1]["exit"] == 0
          and final["consumed"] == [n] and list(final["outstanding"]) == [new]
          and final["next_seq"] == 3 and not leftovers(d))
    return {"case": "issue-vs-deliver", "rep": rep, "ok": ok,
            "lasts": [o["last"] for o in outs], "consumed": final["consumed"] == [n],
            "new_outstanding": new in final["outstanding"], "next_seq": final["next_seq"],
            "leftover_tmp": leftovers(d)}


def case_release_dir_missing(env):
    g = env.g
    ex = g.fx["exact"]
    d = env.fresh("release-dir-missing")
    st = g.state()
    n, rec = g.issue(st, "release-dir-missing", "exact")
    (d / "state.json").write_bytes(E.canonical(st))
    before = (d / "state.json").read_bytes()
    envf = d / "env"
    envf.write_bytes(g.seal(g.body(ex, rec, n)))
    rel = d / "missing" / "release.bin"
    o = run_one(env.deliver_words(d, n, envf, ex, rel))
    after = (d / "state.json").read_bytes()
    ok = (o["exit"] == 2 and o["last"] == "REJECT: error" and not rel.exists() and after == before
          and not leftovers(d))
    return {"case": "release-dir-missing", "ok": ok, "exit": o["exit"], "last": o["last"],
            "released": rel.exists(), "state_byte_identical": after == before,
            "leftover_tmp": leftovers(d)}


def case_post_commit_failure(env):
    g = env.g
    ex = g.fx["exact"]
    d = env.fresh("post-commit-failure")
    st = g.state()
    n, rec = g.issue(st, "post-commit-failure", "exact")
    (d / "state.json").write_bytes(E.canonical(st))
    envf = d / "env"
    envf.write_bytes(g.seal(g.body(ex, rec, n)))
    wrapper = d / "wrapper.py"
    wrapper.write_text(WRAPPER)
    rel = d / "release.bin"
    words = env.deliver_words(d, n, envf, ex, rel)
    words = [sys.executable, "-I", str(wrapper), env.client] + words[3:]
    o = run_one(words)
    final = E.parse_canonical((d / "state.json").read_bytes())
    intruder_kept = rel.exists() and rel.read_bytes() == b"another writer took this path"
    again_rel = d / "release-again.bin"
    before = (d / "state.json").read_bytes()
    again = run_one(env.deliver_words(d, n, envf, ex, again_rel))
    ok = (o["exit"] == 3 and o["last"] == "CONSUMED-UNRELEASED" and final["consumed"] == [n]
          and intruder_kept and not leftovers(d) and again["last"] == "REJECT: nonce-consumed"
          and not again_rel.exists() and (d / "state.json").read_bytes() == before)
    return {"case": "post-commit-failure", "ok": ok, "exit": o["exit"], "last": o["last"],
            "nonce_consumed": final["consumed"] == [n], "other_file_untouched": intruder_kept,
            "leftover_tmp": leftovers(d), "second_delivery": again["last"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cp-verify", default=str(REPO / "bin" / "cp_verify"))
    ap.add_argument("--client", default=str(HERE / "client_verify.py"))
    ap.add_argument("--repeats", type=int, default=20)
    ap.add_argument("--out")
    a = ap.parse_args()
    root = pathlib.Path(tempfile.mkdtemp(prefix="fp-envelope-concurrency-"))
    env = Env(pathlib.Path(a.client).resolve(), pathlib.Path(a.cp_verify).resolve(), root)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows = []
    try:
        for fn in (case_same_nonce, case_distinct, case_issue_vs_deliver):
            for rep in range(1, a.repeats + 1):
                row = fn(env, rep)
                rows.append(row)
                print(json.dumps({k: row[k] for k in ("case", "rep", "ok", "lasts")}), flush=True)
        for fn in (case_release_dir_missing, case_post_commit_failure):
            row = fn(env)
            rows.append(row)
            print(json.dumps(row), flush=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    summary = {}
    for r in rows:
        s = summary.setdefault(r["case"], {"runs": 0, "passed": 0})
        s["runs"] += 1
        s["passed"] += bool(r["ok"])
    result = {"label": LABEL, "started_utc": started,
              "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "client": pathlib.Path(a.client).name, "repeats": a.repeats,
              "affinity": sorted(os.sched_getaffinity(0)), "summary": summary, "rows": rows,
              "all_pass": all(r["ok"] for r in rows)}
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    for case, s in summary.items():
        print("%s: %d/%d passed" % (case, s["passed"], s["runs"]))
    print("test_concurrency: %s" % ("all ok" if result["all_pass"] else "FAILED"))
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
