#!/usr/bin/env python3
"""Read-only results server for the H200 prover job. Untested draft: written and tested on CPU only.

usage: serve.py <results dir> [port]

GET /healthz          200 "ok" once the server runs (the enclave's healthcheck)
GET /status           JSON: state (running | finalising | done | failed), the last stage lines
                      (read from the tail of stages.log only), file count
GET /results.tar.gz   the whole results directory as a tar.gz, streamed (not built in memory);
                      at most ARCHIVE_SLOTS archives at a time, otherwise 503. Range is ignored.
GET /files            JSON list of files with sizes
Anything else: 404. There is no way to start, stop or change a job over HTTP, and no request body
is read. Fetch through the attested client (RUNBOOK.md, step 5).

File boundary, the same for every route: a file is served only if it is a regular file, no part of
its path below the results directory is a symbolic link, its resolved path lies inside the results
directory, it is not below a directory named isk, and it is opened with O_NOFOLLOW (so a link
created between the check and the open is refused too). run_job.sh never copies isk/ here; the
isk rule is a second line of defence.

The job is finished only when its marker (DONE or FAILED) AND SHA256SUMS exist: run_job.sh writes
the marker, then SHA256SUMS last. Between the two the state is "finalising".
"""
import json
import os
import stat
import sys
import tarfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.realpath(sys.argv[1]) if len(sys.argv) > 1 else "/work/results"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
STATUS_TAIL_BYTES = 64 * 1024  # /status reads at most this much of stages.log, from the end
STATUS_LINES = 20
ARCHIVE_SLOTS = 2  # concurrent /results.tar.gz streams
REQUEST_SLOTS = 16  # concurrent requests of any kind
ARCHIVE_SEM = threading.BoundedSemaphore(ARCHIVE_SLOTS)
REQUEST_SEM = threading.BoundedSemaphore(REQUEST_SLOTS)


def _inside(path):
    """True if path is ROOT or below it and no component below ROOT is a symbolic link."""
    ap = os.path.abspath(path)
    if os.path.commonpath([ROOT, ap]) != ROOT:
        return False
    rel = os.path.relpath(ap, ROOT)
    if rel == ".":
        return True
    cur = ROOT
    for part in rel.split(os.sep):
        if part in ("", ".", "..") or part == "isk":
            return False
        cur = os.path.join(cur, part)
        try:
            if stat.S_ISLNK(os.lstat(cur).st_mode):
                return False
        except OSError:
            return False
    return os.path.realpath(ap) == ap


def open_regular(rel):
    """Open ROOT/rel read-only under the file boundary above; returns (fd, size) or None."""
    p = os.path.join(ROOT, rel)
    if not _inside(p):
        return None
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0))
    except OSError:
        return None
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        os.close(fd)
        return None
    return fd, st.st_size


def is_regular(rel):
    p = os.path.join(ROOT, rel)
    if not _inside(p):
        return False
    try:
        return stat.S_ISREG(os.lstat(p).st_mode)
    except OSError:
        return False


def state():
    final = is_regular("SHA256SUMS")
    if is_regular("DONE"):
        return "done" if final else "finalising"
    if is_regular("FAILED"):
        return "failed" if final else "finalising"
    return "running"


def files():
    out = []
    for base, dirs, names in os.walk(ROOT):  # os.walk does not descend into linked directories
        dirs[:] = sorted(d for d in dirs if d != "isk" and _inside(os.path.join(base, d)))
        for n in sorted(names):
            rel = os.path.relpath(os.path.join(base, n), ROOT)
            if not is_regular(rel):
                continue
            out.append({"path": rel, "bytes": os.lstat(os.path.join(ROOT, rel)).st_size})
    return out


def status_tail():
    o = open_regular("stages.log")
    if o is None:
        return []
    fd, size = o
    try:
        start = max(0, size - STATUS_TAIL_BYTES)
        os.lseek(fd, start, os.SEEK_SET)
        data = os.read(fd, STATUS_TAIL_BYTES)
    finally:
        os.close(fd)
    lines = data.decode("utf-8", errors="replace").splitlines()
    if start > 0 and lines:
        lines = lines[1:]  # the first line may be cut
    return lines[-STATUS_LINES:]


def stream_tarball(out):
    """Writes the archive to out as it goes; memory use is a buffer, not the archive."""
    with tarfile.open(fileobj=out, mode="w|gz") as t:
        for f in files():
            o = open_regular(f["path"])
            if o is None:
                continue
            fd, size = o
            with os.fdopen(fd, "rb") as fh:
                info = tarfile.TarInfo("results/" + f["path"])
                info.size = size
                info.mode = 0o644
                info.mtime = int(os.fstat(fh.fileno()).st_mtime)
                t.addfile(info, fh)  # reads exactly size bytes; a file that shrank aborts the stream


class H(BaseHTTPRequestHandler):
    server_version = "fp-h200-results/2"
    timeout = 60  # a client that stalls loses its connection and its slot

    def send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not REQUEST_SEM.acquire(blocking=False):
            return self.send(503, b"busy\n", "text/plain")
        try:
            return self.route()
        finally:
            REQUEST_SEM.release()

    def route(self):
        if self.path == "/healthz":
            return self.send(200, b"ok\n", "text/plain")
        if self.path == "/status":
            body = {"state": state(), "stages": status_tail(), "files": len(files())}
            return self.send(200, json.dumps(body, indent=1).encode() + b"\n", "application/json")
        if self.path == "/files":
            return self.send(200, json.dumps(files(), indent=1).encode() + b"\n", "application/json")
        if self.path == "/results.tar.gz":
            if not ARCHIVE_SEM.acquire(blocking=False):
                return self.send(503, b"archive busy, retry\n", "text/plain")
            try:
                # HTTP/1.0 without Content-Length: the body ends when the connection closes.
                self.send_response(200)
                self.send_header("Content-Type", "application/gzip")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    stream_tarball(self.wfile)
                except (OSError, tarfile.TarError) as e:
                    sys.stderr.write("archive aborted: %s\n" % type(e).__name__)
                    self.close_connection = True
            finally:
                ARCHIVE_SEM.release()
            return None
        return self.send(404, b"not found\n", "text/plain")

    def log_message(self, fmt, *args):  # one line per request, no headers, no bodies
        sys.stderr.write("%s %s\n" % (self.command, self.path))


class Server(ThreadingHTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    Server(("0.0.0.0", PORT), H).serve_forever()
