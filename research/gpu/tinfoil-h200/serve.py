#!/usr/bin/env python3
"""Read-only results server for the H200 prover job. Untested draft: written and tested on CPU only.

usage: serve.py <results dir> [port]

GET /healthz          200 "ok" once the server runs (the enclave's healthcheck)
GET /status           JSON: state (running | finalising | done | failed), the last stage lines
                      (read from the tail of stages.log only), file count
GET /results.tar.gz   the whole results directory as a tar.gz, streamed (not built in memory);
                      at most ARCHIVE_SLOTS archives at a time, otherwise 503. Range is ignored.
GET /files            JSON list of files with sizes
Anything else: 404. A request line over 64 KiB: 414. There is no way to start, stop or change a job
over HTTP, and no request body is read. Fetch through the attested client (RUNBOOK.md, step 5).

File boundary, the same for every route. The results directory is opened once, by path, and that
descriptor is kept (ROOT_FD). Every later open is relative to a descriptor that is already inside
the results directory, one path component at a time: a directory with O_NOFOLLOW | O_DIRECTORY,
the last component with O_NOFOLLOW, and every opened object is checked with fstat (a directory or a
regular file, nothing else). A path given by name is therefore never resolved by the kernel as a
whole, and no symbolic link is followed at any depth: a link where a directory or a file was
expected, whether it was there before the request or swapped in during it, makes the open fail and
the entry is left out. The walk behind /files and /results.tar.gz holds the descriptor of the
directory it lists and opens each entry relative to it, so a parent directory that is renamed or
replaced while the archive is streamed cannot lead the server outside the results directory. No
component may be named isk (run_job.sh never copies isk/ here; this rule is a second line of
defence). A file is served from the descriptor that was checked, never reopened by name.

The job is finished when its marker and its checksums exist: run_job.sh writes the marker (DONE or
FAILED), then SHA256SUMS last. If sealing fails, run_job.sh writes FAILED and SEAL-FAILED instead
of SHA256SUMS. "done" requires DONE and SHA256SUMS and neither FAILED nor SEAL-FAILED; "failed"
requires FAILED and one of SHA256SUMS or SEAL-FAILED; a marker alone is "finalising".

Connections: at most CONN_SLOTS are handled at once. A connection beyond that is answered 503 by
the accepting thread and closed, without a handler thread being started for it.
"""
import errno
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
MAX_DEPTH = 16  # the walk does not go deeper than this below the results directory
ARCHIVE_SLOTS = 2  # concurrent /results.tar.gz streams
CONN_SLOTS = 16  # concurrent connections of any kind, enforced before a handler thread exists
ARCHIVE_SEM = threading.BoundedSemaphore(ARCHIVE_SLOTS)
CONN_SEM = threading.BoundedSemaphore(CONN_SLOTS)
_O_DIR = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0)
_O_FILE = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)

_root_lock = threading.Lock()
ROOT_FD = None


def root_fd():
    """The results directory's descriptor, opened once and kept (the root of every open)."""
    global ROOT_FD
    with _root_lock:
        if ROOT_FD is None:
            fd = os.open(ROOT, _O_DIR)
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                os.close(fd)
                raise OSError(errno.ENOTDIR, ROOT)
            ROOT_FD = fd
        return ROOT_FD


def _name_ok(part):
    return part not in ("", ".", "..", "isk") and "/" not in part and "\0" not in part


def _open_at(dir_fd, name, want_dir):
    """Opens one component relative to dir_fd, no link followed; returns (fd, stat) or None."""
    if not _name_ok(name):
        return None
    try:
        fd = os.open(name, _O_DIR if want_dir else _O_FILE, dir_fd=dir_fd)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
    except OSError:
        os.close(fd)
        return None
    if (want_dir and not stat.S_ISDIR(st.st_mode)) or (not want_dir and not stat.S_ISREG(st.st_mode)):
        os.close(fd)
        return None
    return fd, st


def open_regular(rel):
    """Opens ROOT/rel as a regular file, one component at a time from ROOT_FD; (fd, size) or None."""
    parts = rel.split("/")
    if not parts or not all(_name_ok(p) for p in parts):
        return None
    try:
        cur = os.dup(root_fd())
    except OSError:
        return None
    try:
        for i, part in enumerate(parts):
            last = i == len(parts) - 1
            o = _open_at(cur, part, want_dir=not last)
            if o is None:
                return None
            os.close(cur)
            cur = o[0]
            if last:
                fd, cur = cur, None
                return fd, o[1].st_size
        return None
    finally:
        if cur is not None:
            os.close(cur)


def is_regular(rel):
    o = open_regular(rel)
    if o is None:
        return False
    os.close(o[0])
    return True


def state():
    sealed = is_regular("SHA256SUMS")
    failed = is_regular("FAILED")
    seal_failed = is_regular("SEAL-FAILED")
    if failed:
        return "failed" if (sealed or seal_failed) else "finalising"
    if is_regular("DONE"):
        return "done" if (sealed and not seal_failed) else "finalising"
    if seal_failed:
        return "finalising"
    return "running"


def walk(dir_fd=None, prefix="", depth=0):
    """Yields (relative path, fd, stat) for every regular file below the results directory, in
    sorted order. Each entry is opened relative to its parent's descriptor; the caller closes fd."""
    if dir_fd is None:
        try:
            dir_fd = os.dup(root_fd())
        except OSError:
            return
    try:
        try:
            names = sorted(os.listdir(dir_fd))
        except OSError:
            return
        for name in names:
            if not _name_ok(name):
                continue
            # One no-follow open per entry; what it is comes from fstat of that descriptor.
            try:
                fd = os.open(name, _O_FILE, dir_fd=dir_fd)
            except OSError:
                continue  # a link (ELOOP), gone, or unreadable
            try:
                st = os.fstat(fd)
            except OSError:
                os.close(fd)
                continue
            if stat.S_ISREG(st.st_mode):
                yield prefix + name, fd, st
            elif stat.S_ISDIR(st.st_mode) and depth + 1 < MAX_DEPTH:
                yield from walk(fd, prefix + name + "/", depth + 1)  # closes fd
            else:
                os.close(fd)  # FIFO, socket, device, or too deep
    finally:
        os.close(dir_fd)


def files():
    out = []
    for rel, fd, st in walk():
        os.close(fd)
        out.append({"path": rel, "bytes": st.st_size})
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
    """Writes the archive to out as it goes; memory use is a buffer, not the archive. Every file is
    read from the descriptor the walk opened and checked."""
    with tarfile.open(fileobj=out, mode="w|gz") as t:
        for rel, fd, st in walk():
            with os.fdopen(fd, "rb") as fh:
                info = tarfile.TarInfo("results/" + rel)
                info.size = st.st_size
                info.mode = 0o644
                info.mtime = int(st.st_mtime)
                t.addfile(info, fh)  # reads exactly size bytes; a file that shrank aborts the stream


class H(BaseHTTPRequestHandler):
    server_version = "fp-h200-results/3"
    timeout = 60  # a client that stalls loses its connection and its slot

    def send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        return self.route()

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
        # A request line that could not be parsed (too long, malformed) leaves command/path unset.
        sys.stderr.write("%s %s\n" % (getattr(self, "command", None) or "-", (getattr(self, "path", None) or "-")[:200]))


BUSY = b"HTTP/1.0 503 Service Unavailable\r\nContent-Type: text/plain\r\nContent-Length: 5\r\nConnection: close\r\n\r\nbusy\n"


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def process_request(self, request, client_address):
        # The connection bound is taken here, in the accepting thread, before a thread exists.
        if not CONN_SEM.acquire(blocking=False):
            try:
                request.settimeout(1)
                request.sendall(BUSY)
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            CONN_SEM.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            CONN_SEM.release()


if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    root_fd()
    Server(("0.0.0.0", PORT), H).serve_forever()
