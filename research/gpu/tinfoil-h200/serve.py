#!/usr/bin/env python3
"""Read-only results server for the H200 prover job. Phase 1: written and tested on CPU only.

usage: serve.py <results dir> [port]

GET /healthz          200 "ok" once the server runs (the enclave's healthcheck)
GET /status           JSON: state (running | done | failed), the last stage lines, file count
GET /results.tar.gz   the whole results directory as a tar.gz (public bundles and logs only:
                      run_job.sh never copies isk/ here)
GET /files            JSON list of files with sizes
Anything else: 404. There is no way to start, stop or change a job over HTTP, and no request body
is read. Fetch through the attested client, e.g.
  tinfoil http get https://<domain>/status --enclave <domain> --repo <owner>/<repo>@<tag>
"""
import io
import json
import os
import sys
import tarfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.realpath(sys.argv[1]) if len(sys.argv) > 1 else "/work/results"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8080


def state():
    if os.path.exists(os.path.join(ROOT, "DONE")):
        return "done"
    if os.path.exists(os.path.join(ROOT, "FAILED")):
        return "failed"
    return "running"


def files():
    out = []
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d != "isk"]  # belt and braces: never served
        for n in sorted(names):
            p = os.path.join(base, n)
            if os.path.islink(p):
                continue
            out.append({"path": os.path.relpath(p, ROOT), "bytes": os.path.getsize(p)})
    return out


def tarball():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for f in files():
            t.add(os.path.join(ROOT, f["path"]), arcname="results/" + f["path"], recursive=False)
    return buf.getvalue()


class H(BaseHTTPRequestHandler):
    server_version = "fp-h200-results/1"

    def send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            return self.send(200, b"ok\n", "text/plain")
        if self.path == "/status":
            stages = []
            p = os.path.join(ROOT, "stages.log")
            if os.path.exists(p):
                with open(p, encoding="utf-8", errors="replace") as f:
                    stages = f.read().splitlines()[-20:]
            body = {"state": state(), "stages": stages, "files": len(files())}
            return self.send(200, json.dumps(body, indent=1).encode() + b"\n", "application/json")
        if self.path == "/files":
            return self.send(200, json.dumps(files(), indent=1).encode() + b"\n", "application/json")
        if self.path == "/results.tar.gz":
            return self.send(200, tarball(), "application/gzip")
        return self.send(404, b"not found\n", "text/plain")

    def log_message(self, fmt, *args):  # one line per request, no headers, no bodies
        sys.stderr.write("%s %s\n" % (self.command, self.path))


if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
