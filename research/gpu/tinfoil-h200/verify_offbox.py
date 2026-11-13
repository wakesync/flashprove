#!/usr/bin/env python3
"""Off-box verification of an H200 job's results (RUNBOOK.md step 8), on CPU, after restore.

Checks EVERY response that the job was registered to produce, against the run's own commitment ID,
with a cp_verify built by the operator from the pinned commit, and fails closed:

  * a STRUCTURAL preflight comes first, before any run is verified (any problem here stops the check
    with FAIL: no run is verified, cp_verify is never started and no copy is made):
    - which parent directories are trusted. If --results is relative, or absolute and below the
      working directory the tool was started in, the working directory and its own parents are
      trusted (they are the operator's; a link among them is the operator's choice), and nothing
      below the working directory is. If --results is absolute and not below the working directory,
      only / is trusted. Every component of --results below the trusted directory, for
      `--results h200-x/results` both the extraction root h200-x and results, is checked with lstat
      and opened with O_NOFOLLOW, one at a time from a descriptor of the trusted directory: a symbolic
      link (or anything but a directory) at any of them is a FAIL. A `..` component in --results is a
      usage error. The results directory then stays open as that descriptor for the whole check.
    - below it the tree is walked through directory descriptors, never following a link: every
      entry, at every depth, must be a directory or a regular file with one hard link (st_nlink ==
      1). A symbolic link (to a file or a directory, inside or outside the tree), a hard-linked file,
      a device, a fifo or a socket is a FAIL. So is a component named isk (run_job.sh never exports
      isk/) or a tree deeper than 32 levels.
    - results/SHA256SUMS must exist (a regular file), list exactly the regular files of the tree but
      itself (no path outside results/, no ghost, no omission), and match each one.
    - one commitment ID per run: two expected runs whose cp_commit.log name the same commitment ID
      are a FAIL (the PREREG registers a fresh commitment per run; a byte copy of a run is not a
      second run).
    After this the set of files is fixed: the checker reads only files of that set, each opened one
    path component at a time from the results directory's descriptor with O_NOFOLLOW and checked
    with fstat to be the same regular file (device and inode) that the walk saw. cp_verify never
    reads the archive: each run's bundle is copied into a fresh private directory, every file
    checked against SHA256SUMS while it is copied, and cp_verify runs there. At the end --results is
    opened again the same way (it must be the same directory) and the tree walked again; any change
    during the check is a FAIL.
  * cp_verify must not write its inputs. After every cp_verify call the files that call was given
    (config/, ivk/, the request, the answer, the proof) are hashed again and compared with what they
    were before the call, and the private copy's listing (names, types, sizes, inodes) must be the
    same; after a run's last call its whole private copy is hashed again against SHA256SUMS. Any
    change is a FAIL of the run and of the whole check, and no further run is verified. This can only
    be seen after cp_verify has run: such a check FAILs after invocation, with the archive and
    everything outside the private copy unchanged (only the private copy was written).
  * the expected runs come from the REGISTERED plan given on the command line, never from the archive:
    `--plan '<FP_CALIB>'` (calibration mode; the #140 window passes the PREREG's value) or
    `--no-calibration` (the #43 job alone), one of the two is required, and `--repeats N` is required.
    Expected: the #43 cold run (`quickstart` with FP_ONBOX_BUILD=1, `cold` with 0, or none), the warm
    repeats rep1..repN (each one response, `example`), and every calibration run <id>-1..<id>-<repeats>
    of the plan (each <requests> responses r01..rNN).
  * the archive's own metadata is only cross-checked, never used to choose what is expected: in
    calibration mode results/calib-plan.txt (the job writes it) must exist, be non-empty and name the
    same plan; with --no-calibration it must be absent. results/steps.tsv must exist. Otherwise FAIL.
  * the archive must not hold a run the registration did not name: any directory in results/ that is
    not an expected run, and any run-shaped step row in steps.tsv or run file (<run>.exit, .verdict,
    .stdout, .time, .windows) of a run not expected (an extra repeat, C2-4, C3-4, rep11), is a FAIL.
    So is a --repeats smaller than the job's (its extra repeats are unexpected runs) or larger
    (missing runs).
  * a run passes only if its cp_commit.log has one commitment ID, every expected response has its
    request, answer and proof in the bundle, cp_verify exits 0 with the last line YES on each of them,
    and the bundle has no response that the plan did not expect (a mixed tree is a failure).
  * a missing run, a withheld out/ (the on-box verifier did not accept it), a missing or rejected
    response, a cp_verify timeout, or a response the plan did not expect: that run FAILS. An early
    failure is never hidden by later YES: every response is checked and reported.
  * the registered mutation cases (research/gpu/local-verify: proof bit flip, answer bit flip,
    request bit flip, proof truncated by one byte, wrong commitment ID) on the first response of
    every run that passed (--mutations first, the default; `all` for every response; `none` to skip,
    which makes the overall verdict FAIL, since the PREREG requires them): each must make cp_verify
    exit nonzero with a last line starting NO. One accepted mutation fails the run. Every mutation
    gets its own fresh private copy (a new temporary directory; config/, ivk/ and the one response,
    each file copied from the checked descriptor into a file created there with O_CREAT|O_EXCL); only
    that copy is written, never the archive and never anything outside the copy.
  * the overall verdict is PASS only if every expected run passed, the archive checks above found
    nothing, and at least one run was expected.

Exit status: 0 PASS, 1 FAIL, 2 usage error (nothing checked). A JSON report goes to --report.
It never contacts any host. SHA256SUMS checks the archive's integrity only; it does not show that the
producer ran the registered plan (that is what --plan, --repeats and the unexpected-run check are for),
and `sha256sum -c` is not a link-safety check (it follows links): the file boundary above is.
Run it from the directory that holds the extracted tree, with a relative --results (RUNBOOK step 8).

usage: python3 verify_offbox.py --cp-verify PATH --results DIR (--plan FP_CALIB | --no-calibration)
                                --repeats N [--cold quickstart|cold|none] [--mutations first|all|none]
                                [--timeout S] [--report FILE]
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile

ENTRY = re.compile(r"^([A-Za-z0-9_]{1,16}):([1-9][0-9]?):([1-9][0-9]?):([1-9][0-9]?):([1-9][0-9]{0,4})$")
ID_LINE = re.compile(r"^commitment ID: *([0-9a-f]{64}) *$")
RESP = re.compile(r"^(.+)\.(req|y|proof)$")
MUTATIONS = ("proof-bitflip", "answer-bitflip", "request-bitflip", "proof-truncated", "wrong-id")
# names run_job.sh gives to runs: the cold run, the warm repeats, the calibration runs <id>-<j>
RUN_NAME = re.compile(r"^(quickstart|cold|rep[0-9]+|[A-Za-z0-9_]{1,16}-[0-9]+)$")
RUN_FILE = re.compile(r"^(.+)\.(exit|verdict|stdout|time|windows)$")
SUM_LINE = re.compile(r"^([0-9a-f]{64}) [ *]\./(.+)$")
MAX_DEPTH = 32
_O_DIR = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0)
_O_FILE = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
_O_NEW = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
_O_RW = os.O_RDWR | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


class Usage(Exception):
    pass


class Boundary(Exception):
    """A read that would leave the checked set of files (never expected after a clean scan)."""


class InputWritten(Exception):
    """cp_verify changed a file of its private copy (seen only after the call)."""


def results_path(given):
    """(trusted base directory, [components below it]) for --results. The working directory and its
    parents are trusted when --results is relative or absolute below the working directory; for any
    other absolute path only / is. Everything below the base is checked by open_results()."""
    if given == "" or any(p == ".." for p in given.split("/")):
        raise Usage("--results must not contain a '..' component")
    cwd = os.getcwd()
    if os.path.isabs(given):
        norm = os.path.normpath(given)
        if norm.startswith(cwd.rstrip("/") + "/"):
            base, rel = cwd, norm[len(cwd.rstrip("/")) + 1:]
        else:
            base, rel = "/", norm.lstrip("/")
    else:
        base, rel = cwd, os.path.normpath(given)
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if not parts:
        raise Usage("--results must name a directory below the working directory (not the directory itself)")
    return base, parts


def open_results(base, parts):
    """Opens base (trusted, followed), then each component of parts with lstat + O_NOFOLLOW from the
    descriptor of the one before. Returns (descriptor of the results directory or None, problems)."""
    try:
        fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0))
    except OSError as e:
        return None, ["working directory unreadable: %s" % e.strerror]
    for i, p in enumerate(parts):
        label = "/".join(parts[:i + 1])
        what = "the results directory" if i == len(parts) - 1 else "a parent of the results directory below the working directory"
        try:
            st = os.stat(p, dir_fd=fd, follow_symlinks=False)
        except OSError as e:
            os.close(fd)
            return None, ["--results %s (%s) unreadable: %s" % (label, what, e.strerror)]
        if stat.S_ISLNK(st.st_mode):
            os.close(fd)
            return None, ["--results %s (%s) is a symbolic link; only the working directory and its parents "
                          "are trusted" % (label, what)]
        if not stat.S_ISDIR(st.st_mode):
            os.close(fd)
            return None, ["--results %s (%s) is not a directory" % (label, what)]
        try:
            nfd = os.open(p, _O_DIR, dir_fd=fd)
        except OSError as e:
            os.close(fd)
            return None, ["--results %s (%s) could not be opened without following a link: %s" % (label, what, e.strerror)]
        os.close(fd)
        fd = nfd
    return fd, []


def parse_plan(text):
    """FP_CALIB as run_job.sh's calib_ok accepts it, duplicates refused: [(id, requests, repeats)]."""
    out, seen = [], set()
    for e in text.split():
        m = ENTRY.match(e)
        if not m:
            raise Usage("malformed plan entry %r" % e)
        cid, n, k, r, t = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))
        if n > 64 or k > 16 or k > n or r > 20 or t > 86400:
            raise Usage("plan entry out of range %r" % e)
        if cid in seen:
            raise Usage("plan names %s twice" % cid)
        seen.add(cid)
        out.append((cid, n, r))
    return out


def expected_runs(plan, repeats, cold):
    runs = []
    if cold != "none":
        runs.append((cold, ["example"]))
    runs += [("rep%d" % i, ["example"]) for i in range(1, repeats + 1)]
    for cid, n, r in plan:
        for j in range(1, r + 1):
            runs.append(("%s-%d" % (cid, j), ["r%02d" % i for i in range(1, n + 1)]))
    return runs


class Archive:
    """The results tree as the walk found it, below an open descriptor of the results directory
    (open_results). Every read goes through open_file(), which only opens a path of the walked set,
    one component at a time from that descriptor with O_NOFOLLOW, and checks that it is the same
    regular file (device, inode) the walk saw."""

    def __init__(self, fd):
        self.fd = fd
        self.files = {}  # rel -> (st_dev, st_ino, st_size, st_mtime_ns)
        self.dirs = {""}
        self.problems = []
        self.sums = None  # rel -> sha256 from SHA256SUMS, set once checksum_problems found nothing

    def scan(self):
        self.files, self.dirs, self.problems = {}, {""}, []
        st = os.fstat(self.fd)
        self.root_id = (st.st_dev, st.st_ino)
        self._walk("", os.dup(self.fd), 0)
        return self

    def _walk(self, rel, dfd, depth):
        try:
            if depth > MAX_DEPTH:
                self.problems.append("tree deeper than %d levels at %s" % (MAX_DEPTH, rel))
                return
            try:
                names = sorted(os.listdir(dfd))
            except OSError as e:
                self.problems.append("directory %s unreadable: %s" % (rel or ".", e.strerror))
                return
            for name in names:
                r = os.path.join(rel, name) if rel else name
                if name == "isk":
                    self.problems.append("%s: a component named isk (never exported)" % r)
                    continue
                try:
                    st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
                except OSError as e:
                    self.problems.append("%s unreadable: %s" % (r, e.strerror))
                    continue
                m = st.st_mode
                if stat.S_ISLNK(m):
                    self.problems.append("%s is a symbolic link (only directories and regular files are allowed)" % r)
                elif stat.S_ISDIR(m):
                    try:
                        sub = os.open(name, _O_DIR, dir_fd=dfd)
                    except OSError as e:
                        self.problems.append("%s could not be opened without following a link: %s" % (r, e.strerror))
                        continue
                    if (os.fstat(sub).st_dev, os.fstat(sub).st_ino) != (st.st_dev, st.st_ino):
                        os.close(sub)
                        self.problems.append("%s changed while it was walked" % r)
                        continue
                    self.dirs.add(r)
                    self._walk(r, sub, depth + 1)
                elif stat.S_ISREG(m):
                    if st.st_nlink != 1:
                        self.problems.append("%s is a hard-linked file (%d links)" % (r, st.st_nlink))
                    else:
                        self.files[r] = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
                else:
                    self.problems.append("%s is not a directory or a regular file (mode %o)" % (r, stat.S_IFMT(m)))
        finally:
            os.close(dfd)

    def snapshot(self):
        return self.root_id, dict(self.files), set(self.dirs)

    def isfile(self, rel):
        return rel in self.files

    def isdir(self, rel):
        return rel in self.dirs

    def listdir(self, rel):
        pre = rel + "/" if rel else ""
        out = set()
        for p in list(self.files) + list(self.dirs):
            if p and p.startswith(pre):
                out.add(p[len(pre):].split("/", 1)[0])
        return sorted(out)

    def open_file(self, rel):
        """A read-only descriptor of the walked regular file rel; raises Boundary otherwise."""
        if rel not in self.files:
            raise Boundary("%s is not a checked file of the archive" % rel)
        parts = rel.split("/")
        if any(p in ("", ".", "..") for p in parts):
            raise Boundary("%s is not a plain path below the results directory" % rel)
        fd = os.dup(self.fd)
        try:
            for p in parts[:-1]:
                nfd = os.open(p, _O_DIR, dir_fd=fd)
                os.close(fd)
                fd = nfd
            ffd = os.open(parts[-1], _O_FILE, dir_fd=fd)
        except OSError as e:
            raise Boundary("%s: %s" % (rel, e.strerror))
        finally:
            os.close(fd)
        st = os.fstat(ffd)
        dev, ino = self.files[rel][:2]
        if not stat.S_ISREG(st.st_mode) or (st.st_dev, st.st_ino) != (dev, ino):
            os.close(ffd)
            raise Boundary("%s changed since the walk" % rel)
        return ffd

    def read_bytes(self, rel):
        with os.fdopen(self.open_file(rel), "rb") as f:
            return f.read()

    def read_text(self, rel):
        return self.read_bytes(rel).decode(errors="replace")

    def sha256(self, rel):
        h = hashlib.sha256()
        with os.fdopen(self.open_file(rel), "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def copy_to(self, rel, dst):
        """Copies the checked file rel into a NEW file dst (O_CREAT|O_EXCL|O_NOFOLLOW: never an existing
        file, never through a link), hashing what it copies: the copy must match SHA256SUMS."""
        if self.sums is None or rel not in self.sums:
            raise Boundary("%s is not listed in SHA256SUMS" % rel)
        src = self.open_file(rel)
        try:
            out = os.open(dst, _O_NEW, 0o600)
        except OSError:
            os.close(src)
            raise
        h = hashlib.sha256()
        with os.fdopen(src, "rb") as fi, os.fdopen(out, "wb") as fo:
            for chunk in iter(lambda: fi.read(1 << 20), b""):
                h.update(chunk)
                fo.write(chunk)
        if h.hexdigest() != self.sums[rel]:
            raise Boundary("%s changed since SHA256SUMS was checked" % rel)


def checksum_problems(ar):
    """results/SHA256SUMS (run_job.sh's finalisation, `./name` paths) must list every regular file but
    itself, nothing else, and match each one."""
    if not ar.isfile("SHA256SUMS"):
        return ["results/SHA256SUMS missing"]
    listed, probs = {}, []
    for line in ar.read_text("SHA256SUMS").splitlines():
        m = SUM_LINE.match(line)
        if not m:
            probs.append("SHA256SUMS: unreadable line %r" % line[:80])
            continue
        rel = os.path.normpath(m.group(2))
        if rel.startswith("/") or rel == ".." or rel.startswith("../"):
            probs.append("SHA256SUMS lists %s, a path outside results/" % m.group(2))
            continue
        listed[rel] = m.group(1)
    present = set(ar.files) - {"SHA256SUMS"}
    for rel in sorted(present - set(listed)):
        probs.append("SHA256SUMS does not list %s" % rel)
    for rel in sorted(listed):
        if rel not in present:
            probs.append("SHA256SUMS lists %s, which is not a regular file in results/" % rel)
        elif ar.sha256(rel) != listed[rel]:
            probs.append("SHA256SUMS mismatch: %s" % rel)
    if not probs:
        ar.sums = dict(listed)
    return probs


def commitment_id(ar, rel):
    if not ar.isfile(rel):
        return None
    ids = [m.group(1) for m in (ID_LINE.match(line) for line in ar.read_text(rel).splitlines()) if m]
    return ids[0] if len(set(ids)) == 1 else None


def call(cp_verify, cwd, name, cid, timeout):
    args = [cp_verify, "config", "ivk", "in/%s.req" % name, "out/%s.y" % name, "out/%s.proof" % name, "-id", cid]
    try:
        p = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"exit": "timeout", "last_line": None}
    except OSError as e:
        return {"exit": "error", "last_line": str(e)}
    lines = p.stdout.decode(errors="replace").strip().splitlines()
    return {"exit": p.returncode, "last_line": lines[-1].strip() if lines else ""}


def _private_listing(d):
    """{relative path: (type, size, inode, mtime_ns, ctime_ns)} of every entry of the private copy d,
    links not followed. A write, an append, a new or removed or replaced file all change it."""
    out = {}
    for top, dirs, files in os.walk(d, followlinks=False):
        for n in dirs + files:
            p = os.path.join(top, n)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            out[os.path.relpath(p, d)] = (stat.S_IFMT(st.st_mode), st.st_size, st.st_ino, st.st_mtime_ns, st.st_ctime_ns)
    return out


def _private_digests(d, rels):
    """{rel: sha256 or a reason} of the private copy's files rels, opened without following a link."""
    out = {}
    for rel in rels:
        try:
            fd = os.open(os.path.join(d, rel), _O_FILE)
        except OSError as e:
            out[rel] = "unreadable: %s" % e.strerror
            continue
        h = hashlib.sha256()
        with os.fdopen(fd, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        out[rel] = h.hexdigest()
    return out


def guarded_call(cp_verify, d, name, cid, timeout):
    """call() on the private copy d, with the inputs of that call (config/, ivk/, the request, the
    answer, the proof) hashed before and after, and the whole copy's listing compared. Returns the
    call's result; raises InputWritten if cp_verify changed anything in d (seen only after the call)."""
    listing = _private_listing(d)
    given = sorted(r for r, v in listing.items() if stat.S_ISREG(v[0]) and r.split(os.sep, 1)[0] in ("config", "ivk"))
    given += ["in/%s.req" % name, "out/%s.y" % name, "out/%s.proof" % name]
    digests = _private_digests(d, given)
    r = call(cp_verify, d, name, cid, timeout)
    after_listing = _private_listing(d)
    after = _private_digests(d, given)
    changed = sorted(x for x in given if after.get(x) != digests.get(x))
    changed += sorted(x for x in set(listing) | set(after_listing)
                      if listing.get(x) != after_listing.get(x) and x not in changed)
    if changed:
        e = InputWritten("cp_verify changed its private input copy while checking %s (%s)"
                         % (name, ", ".join(changed[:6]) + (" ..." if len(changed) > 6 else "")))
        e.result = r
        raise e
    return r


def _inside(d, p):
    """p's real path is strictly inside d's real path."""
    rd = os.path.realpath(d)
    return os.path.realpath(p).startswith(rd + os.sep)


def _open_copy(d, rel):
    """A read-write descriptor of the private copy d/rel: a regular file inside d, opened without
    following a link."""
    p = os.path.join(d, rel)
    if not _inside(d, p):
        raise Boundary("mutation target %s leaves its copy" % rel)
    fd = os.open(p, _O_RW)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise Boundary("mutation target %s is not a regular file" % rel)
    return fd


def flip(d, rel, offset):
    fd = _open_copy(d, rel)
    try:
        size = os.fstat(fd).st_size
        if size == 0:
            return False
        offset %= size
        b = os.pread(fd, 1, offset)[0]
        os.pwrite(fd, bytes([b ^ 1]), offset)
    finally:
        os.close(fd)
    return True


def stage_copy(ar, bundle, names, tmp):
    """A fresh private directory with config/, ivk/ and the responses names (None: every file of in/
    and out/), each file copied from the checked archive file into a new file and checked against
    SHA256SUMS. Nothing in it is a link; nothing outside it is written."""
    d = tempfile.mkdtemp(dir=tmp)
    for part in ("config", "ivk", "in", "out"):
        os.mkdir(os.path.join(d, part), 0o700)
    parts = ("config", "ivk") if names is not None else ("config", "ivk", "in", "out")
    rels = [r for r in sorted(ar.files) if any(r.startswith("%s/%s/" % (bundle, p)) for p in parts)]
    for n in names or ():
        rels += ["%s/in/%s.req" % (bundle, n), "%s/out/%s.y" % (bundle, n), "%s/out/%s.proof" % (bundle, n)]
    for rel in rels:
        sub = rel[len(bundle) + 1:]
        dst = os.path.join(d, sub)
        os.makedirs(os.path.dirname(dst), 0o700, exist_ok=True)
        if not _inside(d, dst):
            raise Boundary("copy target %s leaves its copy" % sub)
        ar.copy_to(rel, dst)
    return d


def mutate(ar, bundle, name, cid, case, tmp):
    """A fresh private copy with one mutation applied; returns (copy dir, commitment ID to use)."""
    d = stage_copy(ar, bundle, [name], tmp)
    if case == "proof-bitflip":
        rel = "out/%s.proof" % name
        flip(d, rel, os.path.getsize(os.path.join(d, rel)) // 2)
    elif case == "answer-bitflip":
        flip(d, "out/%s.y" % name, 0)
    elif case == "request-bitflip":
        rel = "in/%s.req" % name
        flip(d, rel, os.path.getsize(os.path.join(d, rel)) - 1)
    elif case == "proof-truncated":
        fd = _open_copy(d, "out/%s.proof" % name)
        try:
            os.ftruncate(fd, max(0, os.fstat(fd).st_size - 1))
        finally:
            os.close(fd)
    elif case == "wrong-id":
        cid = cid[:-1] + "%x" % (int(cid[-1], 16) ^ 1)
    return d, cid


def check_run(ar, cp_verify, run, names, mutations, timeout, tmp):
    rep = {"run": run, "expected": len(names), "responses": {}, "mutations": {}, "problems": [], "commitment_id": None}
    bundle = run + "/bundle"
    if not ar.isdir(run):
        rep["problems"].append("run directory missing")
    elif not ar.isdir(bundle + "/out"):
        why = "out/ withheld (on-box verifier did not accept)" if ar.isfile(run + "/withheld.txt") else "out/ missing"
        rep["problems"].append(why)
    cid = commitment_id(ar, run + "/cp_commit.log") if ar.isdir(run) else None
    rep["commitment_id"] = cid
    if ar.isdir(run) and cid is None:
        rep["problems"].append("no single commitment ID in cp_commit.log")
    for part in ("config", "ivk", "in"):
        if ar.isdir(run) and not ar.isdir("%s/%s" % (bundle, part)):
            rep["problems"].append("bundle/%s missing" % part)
    if rep["problems"]:
        for n in names:
            rep["responses"][n] = {"verdict": "FAIL", "why": "not checked: " + rep["problems"][0]}
        rep["verdict"] = "FAIL"
        return rep
    # responses present that the plan did not expect (a mixed tree, e.g. a stale r02 next to r01)
    for sub in ("in", "out"):
        for f in ar.listdir("%s/%s" % (bundle, sub)):
            m = RESP.match(f)
            if m and m.group(1) not in names:
                rep["problems"].append("unexpected response file %s/%s" % (sub, f))
    # cp_verify reads a private copy of the run's bundle (every file checked against SHA256SUMS while
    # copied), never the archive itself; it must not write that copy either (guarded_call)
    try:
        cwd = stage_copy(ar, bundle, None, tmp)
        try:
            for n in names:
                files = ["in/%s.req" % n, "out/%s.y" % n, "out/%s.proof" % n]
                missing = [f for f in files if not ar.isfile("%s/%s" % (bundle, f))]
                if missing:
                    rep["responses"][n] = {"verdict": "FAIL", "why": "missing " + ", ".join(missing)}
                    continue
                try:
                    r = guarded_call(cp_verify, cwd, n, cid, timeout)
                except InputWritten as e:
                    e.result["verdict"] = "FAIL"
                    rep["responses"][n] = e.result
                    raise
                r["verdict"] = "YES" if r["exit"] == 0 and r["last_line"] == "YES" else "FAIL"
                rep["responses"][n] = r
            # after the run's last call: the whole private copy is still what SHA256SUMS lists
            staged = {rel[len(bundle) + 1:]: h for rel, h in ar.sums.items()
                      if any(rel.startswith("%s/%s/" % (bundle, p)) for p in ("config", "ivk", "in", "out"))}
            now = _private_digests(cwd, sorted(staged))
            files_now = {r for r, v in _private_listing(cwd).items() if not stat.S_ISDIR(v[0])}
            diff = sorted(x for x in staged if now.get(x) != staged[x]) + sorted(files_now - set(staged))
            if diff:
                raise InputWritten("the private copy of %s differs from SHA256SUMS after cp_verify ran (%s)"
                                   % (run, ", ".join(diff[:6])))
        finally:
            shutil.rmtree(cwd, ignore_errors=True)
        bad = [n for n in names if rep["responses"][n]["verdict"] != "YES"]
        if bad:
            rep["problems"].append("responses not accepted: " + " ".join(bad))
        if mutations != "none" and not bad:
            for n in (names if mutations == "all" else names[:1]):
                for case in MUTATIONS:
                    d, mid = mutate(ar, bundle, n, cid, case, tmp)
                    try:
                        r = guarded_call(cp_verify, d, n, mid, timeout)
                    except InputWritten as e:
                        rep["mutations"]["%s/%s" % (n, case)] = dict(e.result, rejected=False)
                        raise
                    finally:
                        shutil.rmtree(d, ignore_errors=True)
                    r["rejected"] = r["exit"] not in (0, "timeout", "error") and (r["last_line"] or "").startswith("NO")
                    rep["mutations"]["%s/%s" % (n, case)] = r
                    if not r["rejected"]:
                        rep["problems"].append("mutation %s of %s not rejected" % (case, n))
    except InputWritten as e:
        rep["problems"].append(str(e))
        rep["input_written"] = str(e)
    rep["verdict"] = "PASS" if not rep["problems"] else "FAIL"
    return rep


def registration_problems(ar, run_names, calibration, plan_text):
    """Cross-checks of the archive against the registration. Returns a list of problems (empty = ok)."""
    probs = []
    expected = set(run_names)
    if calibration:
        if not ar.isfile("calib-plan.txt"):
            what = "is not a regular file" if ar.isdir("calib-plan.txt") else "missing"
            probs.append("results/calib-plan.txt %s (the job writes it whenever FP_CALIB is set)" % what)
        else:
            on_disk = ar.read_text("calib-plan.txt")
            if on_disk.strip() == "":
                probs.append("results/calib-plan.txt is empty")
            elif on_disk.split() != plan_text.split():
                probs.append("results/calib-plan.txt (%r) differs from the registered --plan" % on_disk.strip())
    elif ar.isfile("calib-plan.txt") or ar.isdir("calib-plan.txt"):
        probs.append("results/calib-plan.txt present, but --no-calibration was given")
    for e in ar.listdir(""):
        if ar.isdir(e) and e not in expected:
            probs.append("unexpected run directory %s (not in the registered plan/repeats)" % e)
        m = RUN_FILE.match(e)
        if m and RUN_NAME.match(m.group(1)) and m.group(1) not in expected:
            probs.append("unexpected run file %s (not in the registered plan/repeats)" % e)
    if not ar.isfile("steps.tsv"):
        probs.append("results/steps.tsv missing")
    else:
        for line in ar.read_text("steps.tsv").splitlines():
            name = line.split("\t", 1)[0].strip()
            if RUN_NAME.match(name) and name not in expected:
                probs.append("steps.tsv has a step %s that is not in the registered plan/repeats" % name)
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cp-verify", required=True)
    ap.add_argument("--results", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", help="the registered FP_CALIB (calibration mode)")
    mode.add_argument("--no-calibration", action="store_true", help="the #43 job alone, no FP_CALIB")
    ap.add_argument("--repeats", type=int, required=True, help="the registered FP_REPEATS")
    ap.add_argument("--cold", choices=("quickstart", "cold", "none"), default="quickstart")
    ap.add_argument("--mutations", choices=("first", "all", "none"), default="first")
    ap.add_argument("--timeout", type=float, default=900)
    ap.add_argument("--report")
    a = ap.parse_args(argv)
    try:
        if a.repeats < 0 or a.repeats > 100:
            raise Usage("--repeats 0 to 100")
        if not (os.path.isfile(a.cp_verify) and os.access(a.cp_verify, os.X_OK)):
            raise Usage("--cp-verify is not an executable file")
        if not os.path.lexists(a.results):
            raise Usage("--results does not exist")
        base, parts = results_path(a.results)
        cp_verify = os.path.abspath(a.cp_verify)
        calibration = a.plan is not None
        plan_text = a.plan if calibration else ""
        if calibration and plan_text.strip() == "":
            raise Usage("empty or whitespace-only --plan (for the #43 job alone use --no-calibration)")
        plan = parse_plan(plan_text)
        runs = expected_runs(plan, a.repeats, a.cold)
        if not runs:
            raise Usage("nothing expected: refusing to pass an empty check")
    except Usage as e:
        print("verify_offbox: usage error: %s" % e, file=sys.stderr)
        return 2
    # the trusted base (the working directory and its parents) is followed; every component of
    # --results below it, the extraction root included, must be a real directory (open_results)
    fd, structural = open_results(base, parts)
    ar = None
    if fd is not None:
        ar = Archive(fd).scan()
        structural += ar.problems
    if not structural:
        try:
            structural += checksum_problems(ar)
        except Boundary as e:
            structural.append("archive read refused: %s" % e)
    if not structural:
        # a fresh commitment per run (PREREG), checked before any run: a byte copy is not a second run
        seen = {}
        try:
            for run, _ in runs:
                cid = commitment_id(ar, run + "/cp_commit.log")
                if cid:
                    seen.setdefault(cid, []).append(run)
        except Boundary as e:
            structural.append("archive read refused: %s" % e)
        for cid, rs in sorted(seen.items()):
            if len(rs) > 1:
                structural.append("runs %s share one commitment ID (each run must be a fresh commitment)" % " ".join(rs))
    summary = {"verdict": "FAIL", "runs_expected": len(runs), "runs_passed": 0,
               "responses_expected": sum(len(n) for _, n in runs), "mutations": a.mutations,
               "mode": "calibration" if calibration else "no-calibration",
               "plan": plan_text.strip(), "repeats": a.repeats, "cold": a.cold,
               "structural_problems": structural, "archive_problems": list(structural),
               "input_written": None, "runs": []}
    if structural:
        for p in structural:
            print("FAIL archive: %s" % p)
        print("OVERALL FAIL: the archive is not a checked tree of regular files with one commitment per run; "
              "no run was verified (%d structural problems)" % len(structural))
        return finish(a, summary, 1)
    archive = registration_problems(ar, [r for r, _ in runs], calibration, plan_text)
    for p in archive:
        print("FAIL archive: %s" % p)
    reports = []
    before = ar.snapshot()
    try:
        with tempfile.TemporaryDirectory(prefix="fp-verify-offbox-") as tmp:
            for run, names in runs:
                rep = check_run(ar, cp_verify, run, names, a.mutations, a.timeout, tmp)
                reports.append(rep)
                print("%s %s (%d responses)%s" % (rep["verdict"], run, len(names),
                                                   "" if rep["verdict"] == "PASS" else ": " + "; ".join(rep["problems"])))
                if rep.get("input_written"):
                    summary["input_written"] = rep["input_written"]
                    archive.append("cp_verify wrote its private input copy (%s); no further run was verified. "
                                   "This is seen only after the call: the archive and everything outside the "
                                   "private copy are checked unchanged below" % run)
                    print("FAIL archive: %s" % archive[-1])
                    break
    except Boundary as e:
        archive.append("archive read refused during the run checks: %s" % e)
        print("FAIL archive: %s" % archive[-1])
    fd2, again = open_results(base, parts)
    if fd2 is None or again:
        archive.append("the results path changed while it was checked")
        print("FAIL archive: %s" % archive[-1])
    else:
        after = Archive(fd2).scan()
        if after.problems or after.snapshot() != before:
            archive.append("the results tree changed while it was checked")
            print("FAIL archive: %s" % archive[-1])
        os.close(fd2)
    os.close(fd)
    ok = (len(reports) == len(runs) and all(r["verdict"] == "PASS" for r in reports)
          and a.mutations != "none" and not archive)
    summary.update({"verdict": "PASS" if ok else "FAIL", "runs_passed": sum(r["verdict"] == "PASS" for r in reports),
                    "archive_problems": archive, "runs": reports})
    if a.mutations == "none":
        print("mutation checks skipped: the PREREG requires them, so the overall verdict is FAIL")
    print("OVERALL %s: %d of %d runs passed, %d archive problems" % (summary["verdict"], summary["runs_passed"],
                                                                  len(runs), len(archive)))
    return finish(a, summary, 0 if ok else 1)


def finish(a, summary, rc):
    if a.report:
        with open(a.report, "w") as f:
            json.dump(summary, f, indent=1)
    return rc


if __name__ == "__main__":
    sys.exit(main())
