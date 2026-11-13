#!/usr/bin/env python3
"""Static test of the contract between the Dockerfile's image stages and tinfoil-config.draft.yml.

No docker build, no docker run, no network beyond the loopback interface: it parses the Dockerfile (stages, their
FROM chain, the apt packages each stage installs, ENV) and the config's text, and checks:
  * the healthcheck's executable is installed in BOTH stages the config may run (`final`, through its
    FROM chain, and `runtime`), as an apt package of that stage's chain (PR #141 review round 1:
    the runtime stage has no curl, and the healthcheck used curl);
  * the healthcheck asks for the port and path the server serves (serve.py's port, run_job.sh's
    FP_PORT default, EXPOSE, the shim's upstream-port and paths);
  * the healthcheck command itself works: it is run against serve.py on a free local port (the port
    swapped in the command text only) and must exit 0, and exit nonzero with no server;
  * `final` is the last stage (a build without --target gives the image with the compiler), it is the
    one stage whose chain installs the toolkit (nvcc), and the stage/flag pairing holds: the config's
    FP_ONBOX_BUILD "1" needs `final`, and `runtime` sets FP_ONBOX_BUILD=0 itself;
  * every file the runtime and final stages COPY from this directory exists.
Applying these facts to a built image is not tested here (no docker); the image receipts are separate.

usage: python3 image_contract_test.py   (exit 0 = all passed)
"""
import ast
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# an executable -> the Ubuntu package that provides it in these stages
PROVIDES = {"python3": "python3", "curl": "curl", "wget": "wget", "flock": "util-linux", "git": "git",
            "time": "time", "nvcc": None}


def read(name):
    with open(os.path.join(HERE, name)) as f:
        return f.read()


def stages(dockerfile):
    """[(name, base, body)] in file order; continuation lines joined."""
    text = re.sub(r"\\\n", " ", dockerfile)
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"FROM\s+(\S+)(?:\s+AS\s+(\S+))?$", s, re.I)
        if m:
            out.append([m.group(2) or "", m.group(1), []])
        elif out:
            out[-1][2].append(s)
    return [(n, b, body) for n, b, body in out]


def apt_packages(body):
    pk = set()
    for s in body:
        for m in re.finditer(r"apt-get install\s+(.*?)(?:&&|$)", s):
            pk |= {w for w in m.group(1).split() if not w.startswith("-")}
    return pk


def chain(st, name):
    by = {n: (b, body) for n, b, body in st}
    out = []
    while name in by:
        out.append(name)
        name = by[name][0]
    return out


def env_of(body):
    env = {}
    for s in body:
        if s.upper().startswith("ENV "):
            for k, v in re.findall(r"(\w+)=(\S+)", s[4:]):
                env[k] = v
    return env


def free_port():
    s = socket.socket()
    s.bind(("localhost", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    results = []

    def check(label, ok):
        results.append((label, bool(ok)))

    df, cfg = read("Dockerfile"), read("tinfoil-config.draft.yml")
    st = stages(df)
    names = [n for n, _, _ in st]
    body = {n: b for n, _, b in st}
    pk = {n: set().union(*(apt_packages(body[c]) for c in chain(st, n))) for n in names}

    m = re.search(r"^\s*test:\s*(\[.*\])\s*$", cfg, re.M)
    check("config has a healthcheck test in exec form", m is not None)
    test = ast.literal_eval(m.group(1)) if m else []  # a YAML flow list of double-quoted strings
    check("healthcheck is [\"CMD\", executable, ...]", len(test) >= 2 and test[0] == "CMD")
    exe = test[1] if len(test) >= 2 else ""
    check("healthcheck executable %r has a known providing package" % exe, PROVIDES.get(exe))
    for stage in ("final", "runtime"):
        check("stage %s exists" % stage, stage in names)
        check("healthcheck executable %r installed in stage %s (apt: %s)" % (exe, stage, PROVIDES.get(exe)),
              PROVIDES.get(exe) in pk.get(stage, set()))
    check("(regression) curl is not installed in stage runtime, so the healthcheck must not use it",
          "curl" not in pk.get("runtime", set()) and exe != "curl")

    text = " ".join(test)
    port = re.search(r"https?://localhost:(\d+)(/\S*?)['\"]", text)
    check("healthcheck targets a local port and path", port is not None)
    hport, hpath = (int(port.group(1)), port.group(2)) if port else (None, None)
    serve = read("serve.py")
    check("serve.py binds all IPv4 interfaces (loopback reachable)", 'Server(("0.0.0.0", PORT)' in serve)
    if hport is None:
        # no parsable localhost:<port>/<path>: one readable FAIL line per dependent check, not a TypeError
        for label in ("serve.py default port == healthcheck port", "serve.py answers the healthcheck path",
                      "run_job.sh FP_PORT default == healthcheck port", "stage final EXPOSEs the healthcheck port",
                      "stage runtime EXPOSEs the healthcheck port", "shim upstream-port == healthcheck port",
                      "shim paths include the healthcheck path"):
            check(label + " (no healthcheck port/path parsed)", False)
    else:
        check("serve.py default port == healthcheck port",
              re.search(r"else (\d+)$", re.search(r"^PORT = .*$", serve, re.M).group(0)).group(1) == str(hport))
        check("serve.py answers the healthcheck path", 'self.path == "%s"' % hpath in serve)
        check("run_job.sh FP_PORT default == healthcheck port", "FP_PORT=${FP_PORT:-%d}" % hport in read("run_job.sh"))
        for stage in ("final", "runtime"):
            check("stage %s EXPOSEs %d" % (stage, hport), "EXPOSE %d" % hport in body.get(stage, []))
        check("shim upstream-port == healthcheck port", re.search(r"upstream-port:\s*%d\b" % hport, cfg) is not None)
        check("shim paths include the healthcheck path", re.search(r"^\s*-\s*%s\s*$" % re.escape(hpath), cfg, re.M) is not None)

    check("final is the last stage (a build without --target gives it)", names and names[-1] == "final")
    check("final's chain installs the toolkit (nvcc in PATH via the toolkit stage)",
          "toolkit" in chain(st, "final") and any("nvcc --version" in s for s in body.get("toolkit", [])))
    check("runtime's chain does not include the toolkit stage", "toolkit" not in chain(st, "runtime"))
    check("runtime sets FP_ONBOX_BUILD=0", env_of(body.get("runtime", [])).get("FP_ONBOX_BUILD") == "0")
    fob = re.search(r'FP_ONBOX_BUILD:\s*"(\d)"', cfg)
    check("config FP_ONBOX_BUILD \"1\" pairs with the default (last) stage final",
          fob is not None and fob.group(1) == "1" and names[-1] == "final")
    check("run_job.sh refuses FP_ONBOX_BUILD=1 without nvcc", "FP_ONBOX_BUILD=1 needs the compiler" in read("run_job.sh"))
    for stage in ("final", "runtime"):
        for s in body.get(stage, []):
            if s.upper().startswith("COPY ") and "--from=" not in s:
                srcs = s.split()[1:-1]
                check("stage %s: COPY sources exist: %s" % (stage, " ".join(srcs)),
                      all(os.path.exists(os.path.join(HERE, x.rstrip("/"))) for x in srcs))

    # run the healthcheck command against serve.py (port swapped in the text only)
    if test and hport:
        with tempfile.TemporaryDirectory(prefix="fp-image-contract-") as d:
            p = free_port()
            cmd = [a.replace(":%d/" % hport, ":%d/" % p) for a in test[1:]]
            exe_path = sys.executable if cmd[0] == "python3" else cmd[0]
            r = subprocess.run([exe_path] + cmd[1:], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
            check("healthcheck command exits nonzero with no server", r.returncode != 0)
            srv = subprocess.Popen([sys.executable, os.path.join(HERE, "serve.py"), d, str(p)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                rc = None
                for _ in range(50):
                    r = subprocess.run([exe_path] + cmd[1:], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                    rc = r.returncode
                    if rc == 0:
                        break
                    time.sleep(0.1)
                check("healthcheck command exits 0 against serve.py (%s)" % shlex.join(test[1:2]), rc == 0)
            finally:
                srv.terminate()
                srv.wait(timeout=10)

    for label, ok in results:
        print(("PASS " if ok else "FAIL ") + label)
    print("%d of %d checks passed" % (sum(ok for _, ok in results), len(results)))
    return 0 if results and all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
