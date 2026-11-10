#!/usr/bin/env python3
"""CPU test of serve.py: starts it on a scratch results dir and checks every route, the file boundary
(isk/, symbolic links, a link to a file in a sibling directory), the tail-only /status, the streamed
archive and the archive concurrency cap.
usage: python3 serve_test.py [--serve PATH_TO_serve.py]   (exit 0 = all checks passed)"""
import argparse
import importlib.util
import io
import json
import os
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SENTINEL = b"SENTINEL-must-never-be-served"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def get(port, path, method="GET"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method, data=b"x" if method == "POST" else None)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def wait_up(port):
    for _ in range(100):
        try:
            if get(port, "/healthz")[0] == 200:
                return True
        except OSError:
            time.sleep(0.1)
    return False


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", default=os.path.join(HERE, "serve.py"))
    serve = ap.parse_args().serve
    checks = []
    with tempfile.TemporaryDirectory() as d:
        r = os.path.join(d, "results")
        sib = os.path.join(d, "sibling", "isk")  # a sibling directory beside results/, like a run's isk/
        write(os.path.join(sib, "seed.bin"), SENTINEL)
        write(os.path.join(r, "rep1", "isk", "seed.bin"), SENTINEL)  # must never be served
        write(os.path.join(r, "rep1", "bundle", "out", "example.y"), b"284\n")
        write(os.path.join(r, "stages.log"), b"t STAGE job-start\n")
        port = free_port()
        p = subprocess.Popen([sys.executable, serve, r, str(port)], stderr=subprocess.DEVNULL)
        try:
            checks.append(("server up", wait_up(port)))
            c, b = get(port, "/healthz")
            checks.append(("healthz 200", c == 200 and b == b"ok\n"))
            c, b = get(port, "/status")
            s = json.loads(b)
            checks.append(("status running", c == 200 and s["state"] == "running" and s["stages"] == ["t STAGE job-start"]))
            c, b = get(port, "/files")
            paths = [f["path"] for f in json.loads(b)]
            checks.append(("files lists bundle, not isk", "rep1/bundle/out/example.y" in paths and not any("isk" in x for x in paths)))
            c, b = get(port, "/results.tar.gz")
            t = tarfile.open(fileobj=io.BytesIO(b), mode="r:gz")
            names = t.getnames()
            checks.append(("tarball has bundle, not isk", "results/rep1/bundle/out/example.y" in names and not any("isk" in n for n in names)))
            checks.append(("tarball content intact", t.extractfile("results/rep1/bundle/out/example.y").read() == b"284\n"))
            checks.append(("unknown path 404", get(port, "/../../etc/passwd")[0] == 404))
            checks.append(("POST refused", get(port, "/status", "POST")[0] in (404, 405, 501)))

            # Review item 6: stages.log as a symbolic link to a sentinel in a sibling directory.
            os.rename(os.path.join(r, "stages.log"), os.path.join(r, "stages.real"))
            os.symlink(os.path.join(sib, "seed.bin"), os.path.join(r, "stages.log"))
            c, b = get(port, "/status")
            checks.append(("status does not follow a stages.log link", c == 200 and SENTINEL not in b and json.loads(b)["stages"] == []))
            os.unlink(os.path.join(r, "stages.log"))
            os.rename(os.path.join(r, "stages.real"), os.path.join(r, "stages.log"))
            # Links of other shapes: a file link and a directory link to the sibling, a marker link.
            os.symlink(os.path.join(sib, "seed.bin"), os.path.join(r, "rep1", "leak.txt"))
            os.symlink(os.path.dirname(sib), os.path.join(r, "linkdir"))
            all_bodies = b"".join(get(port, x)[1] for x in ("/status", "/files"))
            _, tb = get(port, "/results.tar.gz")
            tnames = tarfile.open(fileobj=io.BytesIO(tb), mode="r:gz").getnames()
            raw = b"".join(tarfile.open(fileobj=io.BytesIO(tb), mode="r:gz").extractfile(n).read() for n in tnames)
            checks.append(("no route serves a linked file or directory", SENTINEL not in all_bodies and SENTINEL not in raw
                           and not any("leak" in n or "linkdir" in n for n in tnames)))
            os.symlink(os.path.join(sib, "seed.bin"), os.path.join(r, "DONE"))
            checks.append(("a linked DONE marker is not a finished job", json.loads(get(port, "/status")[1])["state"] == "running"))
            os.unlink(os.path.join(r, "DONE"))

            # /status reads only the tail of a long stages.log.
            with open(os.path.join(r, "stages.log"), "wb") as f:
                for i in range(60000):
                    f.write(b"t STAGE line %d\n" % i)
            c, b = get(port, "/status")
            st = json.loads(b)["stages"]
            checks.append(("status shows the last 20 lines of a long log", len(st) == 20 and st[-1] == "t STAGE line 59999" and st[0] == "t STAGE line 59980"))

            # done only when the marker and SHA256SUMS exist (run_job.sh writes SHA256SUMS last).
            write(os.path.join(r, "DONE"), b"")
            checks.append(("marker without SHA256SUMS is finalising", json.loads(get(port, "/status")[1])["state"] == "finalising"))
            write(os.path.join(r, "SHA256SUMS"), b"")
            checks.append(("status done", json.loads(get(port, "/status")[1])["state"] == "done"))
            os.unlink(os.path.join(r, "DONE"))
            write(os.path.join(r, "FAILED"), b"why\n")
            checks.append(("status failed", json.loads(get(port, "/status")[1])["state"] == "failed"))
        finally:
            p.terminate()
            p.wait()

        # Archive concurrency cap, in process: with every archive slot taken, a new request gets 503.
        spec = importlib.util.spec_from_file_location("serve_under_test", serve)
        argv = sys.argv
        sys.argv = [serve, r, "0"]
        try:
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
        finally:
            sys.argv = argv
        sem = getattr(m, "ARCHIVE_SEM", None)
        if sem is None:
            checks.append(("archive concurrency is capped", False))
        else:
            srv = m.ThreadingHTTPServer(("127.0.0.1", 0), m.H)
            th = threading.Thread(target=srv.serve_forever, daemon=True)
            th.start()
            held = 0
            while sem.acquire(blocking=False):
                held += 1
            try:
                c, _ = get(srv.server_address[1], "/results.tar.gz")
                checks.append(("archive concurrency is capped (503 when full)", c == 503 and held >= 1))
            finally:
                for _ in range(held):
                    sem.release()
            c, _ = get(srv.server_address[1], "/results.tar.gz")
            checks.append(("archive served again once a slot is free", c == 200))
            srv.shutdown()
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    print("%d of %d checks passed" % (sum(ok for _, ok in checks), len(checks)))
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
