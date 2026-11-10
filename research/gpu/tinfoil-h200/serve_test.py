#!/usr/bin/env python3
"""CPU test of serve.py: starts it on a scratch results dir and checks every route.
usage: python3 serve_test.py   (exit 0 = all checks passed)"""
import io
import json
import os
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def get(port, path, method="GET"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method, data=b"x" if method == "POST" else None)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main():
    checks = []
    with tempfile.TemporaryDirectory() as d:
        r = os.path.join(d, "results")
        os.makedirs(os.path.join(r, "rep1", "bundle", "out"))
        os.makedirs(os.path.join(r, "rep1", "isk"))  # must never be served
        open(os.path.join(r, "rep1", "isk", "seed.bin"), "wb").write(b"S" * 32)
        open(os.path.join(r, "rep1", "bundle", "out", "example.y"), "w").write("284\n")
        open(os.path.join(r, "stages.log"), "w").write("t STAGE job-start\n")
        port = free_port()
        p = subprocess.Popen([sys.executable, os.path.join(HERE, "serve.py"), r, str(port)], stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    if get(port, "/healthz")[0] == 200:
                        break
                except OSError:
                    time.sleep(0.1)
            c, b = get(port, "/healthz")
            checks.append(("healthz 200", c == 200 and b == b"ok\n"))
            c, b = get(port, "/status")
            s = json.loads(b)
            checks.append(("status running", c == 200 and s["state"] == "running" and s["stages"] == ["t STAGE job-start"]))
            c, b = get(port, "/files")
            paths = [f["path"] for f in json.loads(b)]
            checks.append(("files lists bundle, not isk", "rep1/bundle/out/example.y" in paths and not any("isk" in x for x in paths)))
            c, b = get(port, "/results.tar.gz")
            names = tarfile.open(fileobj=io.BytesIO(b), mode="r:gz").getnames()
            checks.append(("tarball has bundle, not isk", "results/rep1/bundle/out/example.y" in names and not any("isk" in n for n in names)))
            checks.append(("unknown path 404", get(port, "/../../etc/passwd")[0] == 404))
            checks.append(("POST refused", get(port, "/status", "POST")[0] in (404, 405, 501)))
            open(os.path.join(r, "DONE"), "w").close()
            checks.append(("status done", json.loads(get(port, "/status")[1])["state"] == "done"))
        finally:
            p.terminate()
            p.wait()
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
