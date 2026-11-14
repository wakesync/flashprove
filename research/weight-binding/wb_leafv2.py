#!/usr/bin/env python3
"""Conversion leaf v2 on real bytes, issue #149 (experiments/20261112-149-leaf-v2). HASH LEVEL, NOT A PROOF.

Leaf v2 = the #91 leaf object (wb_conv.leaf_obj, unchanged) plus "e" (the block's exponent) and
"int_sha256" (SHA-256 of the int16 little-endian row-major integers), computed by the executable matrix
rule of wb_int.py (fetch / bf16_to_f32 / to_int, imported unchanged). Restricted to the 70 tensors #68
found different plus 8 registered byte-identical controls, all class matrix_plain (rule STEP_MATRIX, no
norm). The tree over those 78 blocks gives a SUBSET id (tag fp-wb-conv-subset-v2), not a model
conversion id (that needs all 722 blocks).

Bytes are fetched by HTTP range request into memory, one tensor per pin at a time, never written to disk.

Evidence handling (added after review round 1 of PR #151, no change to the conversion, the leaf, the tree
or the opening verifier): `load_records` is the one validated loader for a run directory's blocks.jsonl,
used by tree, compare, the hostile suite and the experiment's summarise.py. It refuses (EvidenceError)
duplicate records (identical ones too), unknown names, wrong kinds, malformed fields, derived flags that
do not follow from the record's own fields or from #68's hashes, and a record count or order that does
not match run-meta.json. `load_leaves` accepts a stored leaves-v2.json only if it is byte for byte the
tree rebuilt from the validated records. `compare` works on those validated inputs, compares the
canonical leaf JSON per block (the H3 metric as registered), and gives an explicit status. A registered
partial run (fewer than 78 records, in order, matching its run-meta.json) stays legitimate and is
reported as partial coverage, not as a failure and not as full coverage.

Registered mode (issue #203, experiments/20261114-203-leafv2-registered-pin, opt-in, the default is unchanged):
`compare_runs(a, b, registered=True)` and `compare ... --registered` first check each run directory against
the committed pin file experiments/20261112-149-leaf-v2/runs/registered-pins.json (check_registered): the
directory must not be a symlink, its name must be a pinned run, and each consumed file (blocks.jsonl,
run-meta.json, leaves-v2.json) must be a regular file exactly when the pin lists it, with the pinned SHA-256.
Otherwise EvidenceError (exit 2). The pin is a committed list that binds "registered run" to what the
repository holds. It is NOT authentication: anyone who can change the repository can change the pin with
the runs. Files the readers do not consume are not checked.

Usage (from the top of the tree):
  wb_leafv2.py run <outdir> [--reverse] [--budget-s SECONDS]   fetch, hash, convert; writes outdir/blocks.jsonl
  wb_leafv2.py tree <outdir>                                    leaves + trees + subset ids -> outdir/leaves-v2.json
  wb_leafv2.py compare <outdirA> <outdirB> <out.json>           byte-level comparison of two runs (H3)
  wb_leafv2.py compare <outdirA> <outdirB> <out.json> --registered   the same, after the registered-pin check
Exit status of tree and compare: 0 ok (compare: no mismatch on the common blocks), 1 compare found a
mismatch, 2 the evidence was refused (message on stderr).
"""
import hashlib, json, os, resource, shutil, struct, sys, time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wb_conv as wc  # noqa: E402
import wb_int as wi  # noqa: E402
import wb_manifest as wbm  # noqa: E402

ROOT = HERE.parent.parent
R68 = ROOT / "experiments/20261109-8-qwen-real-weights/runs"
R91 = ROOT / "experiments/20261111-91-conversion-id/runs"
STREAM = {"stock": R68 / "stream-stock.json", "abl": R68 / "stream-abl.json"}
CONFIG = {"stock": R91 / "config-stock.json", "abl": R91 / "config-abl.json"}
LM = "model.language_model.layers."
CONTROLS = [LM + s for s in ("15.mlp.down_proj.weight", "15.self_attn.o_proj.weight",
                             "16.linear_attn.out_proj.weight", "16.mlp.down_proj.weight",
                             "52.linear_attn.out_proj.weight", "52.mlp.down_proj.weight",
                             "55.mlp.down_proj.weight", "55.self_attn.o_proj.weight")]
MIN_FREE = 21 * 10**9
LEAF_TAG, NODE_TAG, ID_TAG = b"fp-wb-conv-leaf-v2", b"fp-wb-conv-node-v2", b"fp-wb-conv-subset-v2"
V2_KEYS = {"block", "cls", "sources", "rule", "e", "int_sha256"}


# ---------------------------------------------------------------- registered set
def registered():
    d = json.load(open(R68 / "diff.json"))
    changed = sorted(t["tensor"] for t in d["tensors"] if not t["same"])
    fam = {}
    for n in changed:
        f = n.split(".", 4)[-1]
        fam[f] = fam.get(f, 0) + 1
    assert len(changed) == 70, len(changed)
    assert fam == {"mlp.down_proj.weight": 35, "linear_attn.out_proj.weight": 26, "self_attn.o_proj.weight": 9}, fam
    same = {t["tensor"]: t for t in d["tensors"] if t["same"]}
    for c in CONTROLS:
        assert c in same and same[c]["sha256_stock"] == same[c]["sha256_abl"], c
    names = sorted(changed + CONTROLS)
    assert len(set(names)) == 78
    return names, set(changed)


def conversions():
    out = {}
    for pin in ("stock", "abl"):
        _, _, t = wbm.tensors_from_stream(str(STREAM[pin]))
        out[pin] = wc.Conversion(t, json.load(open(CONFIG[pin])))
    return out


def check_classes(conv, names):
    """Every registered block must be matrix_plain with one source (itself) and rule STEP_MATRIX, in both pins."""
    for pin, c in conv.items():
        for n in names:
            o = c.leaf_objs[c.index[n]]
            assert o["cls"] == "matrix_plain", (pin, n, o["cls"])
            assert [s[0] for s in o["sources"]] == [n], (pin, n)
            assert o["rule"]["step"] == wc.STEP_MATRIX, (pin, n)


# ---------------------------------------------------------------- rule on bytes
def convert(pin, name):
    t0 = time.time()
    data, t, fsec = wi.fetch(pin, str(STREAM[pin]), name)
    h = hashlib.sha256(data).hexdigest()
    t1 = time.time()
    e, w = wi.to_int(wi.bf16_to_f32(data, tuple(t["shape"])))
    ib = w.astype("<i2").tobytes()       # int16 little endian, C order
    ih = hashlib.sha256(ib).hexdigest()
    csec = time.time() - t1
    del data, ib
    return dict(sha256=h, sha_matches_68=(h == t["sha256"]), shape=list(t["shape"]), e=int(e), int_sha256=ih,
                fetch_s=round(fsec, 2), convert_s=round(csec, 2), total_s=round(time.time() - t0, 2)), w


def run(outdir, reverse=False, budget_s=None):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    names, changed = registered()
    conv = conversions()
    check_classes(conv, names)
    order = list(reversed(names)) if reverse else names
    began = time.time()
    log = open(out / "blocks.jsonl", "w")
    meta = dict(started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), reverse=reverse, budget_s=budget_s,
                n_registered=len(names), free_disk_start=shutil.disk_usage(str(out)).free, stopped=None)
    done = 0
    for name in order:
        free = shutil.disk_usage(str(out)).free
        if free < MIN_FREE:
            meta["stopped"] = "free disk %d < 21 GB before %s" % (free, name)
            break
        if budget_s is not None and time.time() - began > budget_s:
            meta["stopped"] = "budget %d s reached before %s" % (budget_s, name)
            break
        rs, ws = convert("stock", name)
        ra, wa = convert("abl", name)
        rec = dict(name=name, kind="changed" if name in changed else "control", stock=rs, abl=ra,
                   bytes_identical=(rs["sha256"] == ra["sha256"]),
                   e_equal=(rs["e"] == ra["e"]), int_sha256_equal=(rs["int_sha256"] == ra["int_sha256"]))
        if rs["e"] == ra["e"]:
            d = ws.reshape(-1).astype(np.int32) - wa.reshape(-1).astype(np.int32)
            nz = int(np.count_nonzero(d))
            rec.update(int_entries_differing=nz, int_fraction_differing=nz / d.size, elements=int(d.size),
                       max_abs_int_delta=int(np.abs(d).max()))
            del d
        else:
            rec.update(int_entries_differing=None, elements=int(ws.size))
        del ws, wa
        rec["free_disk"] = free
        rec["rss_max_kb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        log.write(json.dumps(rec, sort_keys=True) + "\n")
        log.flush()
        done += 1
        print("block", done, name, rec["kind"], "e", rs["e"], ra["e"], "int_equal", rec["int_sha256_equal"],
              "sha68", rs["sha_matches_68"], ra["sha_matches_68"], "s", rs["total_s"], ra["total_s"], flush=True)
    meta.update(done=done, seconds=round(time.time() - began, 1), free_disk_end=shutil.disk_usage(str(out)).free,
                rss_max_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    json.dump(meta, open(out / "run-meta.json", "w"), indent=1, sort_keys=True)
    print("done", json.dumps(meta), flush=True)


# ---------------------------------------------------------------- leaf v2 + tree
def leaf_v2(base_obj, e, int_sha256):
    o = dict(base_obj)
    o["e"] = e
    o["int_sha256"] = int_sha256
    return o


def leaf_hash(obj):
    return wbm._h(b"\x00", LEAF_TAG, wbm._lp(wc._canon(obj)))


def node_hash(a, b):
    return wbm._h(b"\x01", NODE_TAG, a, b)


def levels(leaves):
    lv = [leaves]
    while len(lv[-1]) > 1:
        cur = lv[-1]
        lv.append([node_hash(cur[i], cur[i + 1]) if i + 1 < len(cur) else cur[i] for i in range(0, len(cur), 2)])
    return lv


def subset_id(ck_id, pin, n, root, rule_version=wc.RULE_VERSION):
    return wbm._h(ID_TAG, ck_id, wbm._lp(rule_version.encode()), pin, struct.pack("<Q", n), root)


class SubsetV2:
    def __init__(self, conv, records, pin):
        self.conv = conv
        self.names = sorted(records)
        self.leaf_objs = [leaf_v2(conv.leaf_objs[conv.index[n]], records[n][pin]["e"], records[n][pin]["int_sha256"])
                          for n in self.names]
        self.lv = levels([leaf_hash(o) for o in self.leaf_objs])
        self.root = self.lv[-1][0]
        self.id = subset_id(conv.ck.id, conv.pin, len(self.names), self.root)
        self.index = {b: i for i, b in enumerate(self.names)}

    def path(self, i):
        p, j = [], i
        for cur in self.lv[:-1]:
            s = j ^ 1
            p.append(cur[s].hex() if s < len(cur) else None)
            j //= 2
        return p

    def open(self, block):
        i = self.index[block]
        return dict(checkpoint_id=self.conv.ck.id.hex(), config_pin=self.conv.pin.hex(), rule_version=wc.RULE_VERSION,
                    n=len(self.names), index=i, leaf=self.leaf_objs[i], path=self.path(i))


def leaf_v2_well_formed(obj):
    """v1 structural check on the v1 part, then the two new fields: e an int (not bool) in [-64, 64],
    int_sha256 exactly 64 lowercase hex."""
    if not isinstance(obj, dict) or set(obj) != V2_KEYS:
        return "leaf v2 fields"
    e = obj["e"]
    if not isinstance(e, int) or isinstance(e, bool) or not -64 <= e <= 64:
        return "e"
    if not wbm._is_hex32(obj["int_sha256"]):
        return "int_sha256"
    return wc.leaf_well_formed({k: obj[k] for k in ("block", "cls", "sources", "rule")})


def verify_opening_v2(held_id_hex, op):
    try:
        return _verify(held_id_hex, op)
    except (TypeError, ValueError, KeyError, AttributeError, OverflowError):
        return False


def _verify(held_id_hex, op):
    keys = {"checkpoint_id", "config_pin", "rule_version", "n", "index", "leaf", "path"}
    if not isinstance(op, dict) or set(op) != keys:
        return False
    if leaf_v2_well_formed(op["leaf"]) is not None:
        return False
    if not (wbm._is_hex32(op["checkpoint_id"]) and wbm._is_hex32(op["config_pin"]) and isinstance(op["rule_version"], str)):
        return False
    shape = dict(index=op["index"], n=op["n"], name="x", dtype="x", shape=[], sha256="0" * 64, path=op["path"])
    if wbm.canonical_opening(shape) is not None:
        return False
    cur, j = leaf_hash(op["leaf"]), op["index"]
    for sib in op["path"]:
        if sib is not None:
            s = bytes.fromhex(sib)
            cur = node_hash(cur, s) if j % 2 == 0 else node_hash(s, cur)
        j //= 2
    sid = subset_id(bytes.fromhex(op["checkpoint_id"]), bytes.fromhex(op["config_pin"]), op["n"], cur, op["rule_version"])
    return sid.hex() == held_id_hex


# ---------------------------------------------------------------- validated evidence (run directories)
class EvidenceError(ValueError):
    """A run directory is malformed, duplicated, or inconsistent with the registered set or with itself.
    Raised instead of normalising bad evidence into a result."""


REC_KEYS = {"name", "kind", "stock", "abl", "bytes_identical", "e_equal", "int_sha256_equal",
            "int_entries_differing", "elements", "free_disk", "rss_max_kb"}
REC_DIFF_KEYS = {"int_fraction_differing", "max_abs_int_delta"}    # written only when e is equal across pins
PIN_KEYS = {"sha256", "sha_matches_68", "shape", "e", "int_sha256", "fetch_s", "convert_s", "total_s"}


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x >= 0


def _check_record(r, where, names, changed, streams):
    """Structural and self-consistency checks on one blocks.jsonl record. It cannot check e or int_sha256
    against the weights (that needs the bytes); it checks everything the committed files determine."""
    def bad(msg):
        raise EvidenceError("%s: %s" % (where, msg))

    if not isinstance(r, dict):
        bad("record is not a JSON object")
    name = r.get("name")
    if not isinstance(name, str) or name not in names:
        bad("name %r is not one of the %d registered blocks" % (name, len(names)))
    for pin in ("stock", "abl"):
        p = r.get(pin)
        if not isinstance(p, dict) or set(p) != PIN_KEYS:
            bad("%s fields are not exactly %s" % (pin, sorted(PIN_KEYS)))
        if not wbm._is_hex32(p["sha256"]) or not wbm._is_hex32(p["int_sha256"]):
            bad("%s sha256 / int_sha256 must be 64 lowercase hex" % pin)
        if not wbm._is_int(p["e"]) or not -64 <= p["e"] <= 64:
            bad("%s e must be an int in [-64, 64]" % pin)
        _, shape, sha68 = streams[pin][name]
        if p["shape"] != list(shape):
            bad("%s shape %r is not #68's %r" % (pin, p["shape"], list(shape)))
        if not isinstance(p["sha_matches_68"], bool) or p["sha_matches_68"] != (p["sha256"] == sha68):
            bad("%s sha_matches_68 does not follow from sha256 and #68's hash for this block" % pin)
        if not all(_num(p[k]) for k in ("fetch_s", "convert_s", "total_s")):
            bad("%s timings must be non-negative numbers" % pin)
    s, a = r["stock"], r["abl"]
    e_equal = s["e"] == a["e"]
    if not (REC_KEYS <= set(r) <= REC_KEYS | REC_DIFF_KEYS):
        bad("record fields are not exactly the runner's")
    if r["kind"] != ("changed" if name in changed else "control"):
        bad("kind %r is not the registered kind of this block" % (r["kind"],))
    for k, v in (("bytes_identical", s["sha256"] == a["sha256"]), ("e_equal", e_equal),
                 ("int_sha256_equal", s["int_sha256"] == a["int_sha256"])):
        if not isinstance(r[k], bool) or r[k] != v:
            bad("%s is %r but the record's own fields give %r" % (k, r[k], v))
    if (set(r) & REC_DIFF_KEYS) != (REC_DIFF_KEYS if e_equal else set()):
        bad("int_fraction_differing and max_abs_int_delta must be present exactly when e is equal across pins")
    elements = 1
    for x in s["shape"]:
        elements *= x
    if s["shape"] != a["shape"] or not wbm._is_int(r["elements"]) or r["elements"] != elements:
        bad("elements does not equal the product of the shape")
    if e_equal:
        nz, mx = r["int_entries_differing"], r["max_abs_int_delta"]
        if not wbm._is_int(nz) or not 0 <= nz <= elements:
            bad("int_entries_differing must be an int in [0, elements]")
        if not _num(r["int_fraction_differing"]) or r["int_fraction_differing"] != nz / elements:
            bad("int_fraction_differing is not int_entries_differing / elements")
        if not wbm._is_int(mx) or mx < 0 or (mx == 0) != (nz == 0):
            bad("max_abs_int_delta is inconsistent with int_entries_differing")
        if (nz == 0) != r["int_sha256_equal"]:
            bad("int_entries_differing and int_sha256_equal disagree")
    elif r["int_entries_differing"] is not None:
        bad("int_entries_differing must be null when e differs across pins")
    if not (wbm._is_int(r["free_disk"]) and r["free_disk"] >= 0 and wbm._is_int(r["rss_max_kb"]) and r["rss_max_kb"] >= 0):
        bad("free_disk / rss_max_kb must be non-negative ints")


def _load(outdir, require_all=False):
    d = Path(outdir)
    p = d / "blocks.jsonl"
    names, changed = registered()
    streams = {pin: wbm.tensors_from_stream(str(STREAM[pin]))[2] for pin in ("stock", "abl")}
    try:
        raw = p.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as ex:
        raise EvidenceError("%s: cannot read (%s)" % (p, ex))
    if text and not text.endswith("\n"):
        raise EvidenceError("%s: last line is not newline-terminated (truncated file?)" % p)
    recs, line_of, nameset = {}, {}, set(names)
    for i, line in enumerate(text.split("\n")[:-1], 1):
        where = "%s line %d" % (p, i)
        try:
            r = json.loads(line)
        except ValueError as ex:
            raise EvidenceError("%s: not valid JSON (%s)" % (where, ex))
        _check_record(r, where, nameset, changed, streams)
        if r["name"] in recs:
            raise EvidenceError("%s: duplicate record for block %s (first at line %d); duplicates are refused, "
                                "identical or not" % (where, r["name"], line_of[r["name"]]))
        recs[r["name"]] = r
        line_of[r["name"]] = i
    order = list(recs)
    fwd, rev = names[:len(order)], list(reversed(names))[:len(order)]
    if order != fwd and order != rev:
        raise EvidenceError("%s: record order is neither a prefix of the registered order nor of its reverse "
                            "(a block is missing, moved or out of place)" % p)
    mp = d / "run-meta.json"
    if mp.exists():
        try:
            meta = json.loads(mp.read_text())
        except ValueError as ex:
            raise EvidenceError("%s: not valid JSON (%s)" % (mp, ex))
        if not isinstance(meta, dict) or meta.get("done") != len(order) or meta.get("n_registered") != len(names):
            raise EvidenceError("%s: says done=%r of %r, blocks.jsonl has %d records of %d registered"
                                % (mp, meta.get("done") if isinstance(meta, dict) else None,
                                   meta.get("n_registered") if isinstance(meta, dict) else None, len(order), len(names)))
        if not isinstance(meta.get("reverse"), bool) or order != (rev if meta["reverse"] else fwd):
            raise EvidenceError("%s: record order does not match reverse=%r" % (mp, meta.get("reverse")))
        if meta.get("stopped") is None and len(order) != len(names):
            raise EvidenceError("%s: says the run was not stopped, but blocks.jsonl has %d of %d records"
                                % (mp, len(order), len(names)))
    if require_all and len(recs) != len(names):
        raise EvidenceError("%s: all %d blocks are needed here (have %d)" % (p, len(names), len(recs)))
    return recs, hashlib.sha256(raw).hexdigest()


def load_records(outdir, require_all=False):
    """The one validated loader for a run directory's blocks.jsonl: name -> record, in file order.
    Raises EvidenceError on a duplicate (identical or not), an unknown name, a wrong kind, malformed fields,
    derived flags that do not follow from the record or from #68's hashes, an order that is not a prefix of
    the registered order (or its reverse), or disagreement with run-meta.json when that file is present.
    A partial run is accepted unless require_all is set."""
    return _load(outdir, require_all)[0]


def tree_doc(recs, conv=None):
    """The leaves-v2.json document of a complete, validated record set."""
    conv = conv or conversions()
    out = {}
    for pin in ("stock", "abl"):
        s = SubsetV2(conv[pin], recs, pin)
        out[pin] = dict(checkpoint_id=conv[pin].ck.id.hex(), config_pin=conv[pin].pin.hex(), n=len(s.names),
                        root=s.root.hex(), subset_id=s.id.hex(), leaf_hashes=[x.hex() for x in s.lv[0]],
                        leaves=s.leaf_objs)
    return dict(note="conversion leaf v2 subset (78 matrix_plain blocks), hash level, NOT A PROOF, NOT a model conversion id",
                leaf_tag=LEAF_TAG.decode(), node_tag=NODE_TAG.decode(), id_tag=ID_TAG.decode(), rule_version=wc.RULE_VERSION,
                pins=out)


def tree_bytes(doc):
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()


def _first_diff(a, b, path="$"):
    if type(a) is not type(b):
        return path
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return "%s.%s" % (path, k)
            d = _first_diff(a[k], b[k], "%s.%s" % (path, k))
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return path + " (length)"
        for i, (x, y) in enumerate(zip(a, b)):
            d = _first_diff(x, y, "%s[%d]" % (path, i))
            if d:
                return d
        return None
    return None if a == b else path


def load_leaves(outdir, recs, conv=None):
    """Validated loader for a run directory's stored leaves-v2.json. The file is accepted only if it is byte
    for byte the tree `tree` builds from the directory's validated records: same leaf objects in the same
    order, same leaf hashes, roots, subset ids, checkpoint ids and config pins. Returns the document."""
    p = Path(outdir) / "leaves-v2.json"
    names, _ = registered()
    if len(recs) != len(names):
        raise EvidenceError("%s: a stored tree next to an incomplete run (%d of %d records)" % (p, len(recs), len(names)))
    try:
        raw = p.read_bytes()
    except OSError as ex:
        raise EvidenceError("%s: cannot read (%s)" % (p, ex))
    want = tree_doc(recs, conv)
    if raw == tree_bytes(want):
        return want
    try:
        got = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as ex:
        raise EvidenceError("%s: not valid JSON (%s)" % (p, ex))
    raise EvidenceError("%s: stored tree is not the tree rebuilt from blocks.jsonl (first difference at %s)"
                        % (p, _first_diff(got, want) or "byte level only: formatting"))


def tree(outdir):
    recs = load_records(outdir, require_all=True)
    d = tree_doc(recs)
    with open(Path(outdir) / "leaves-v2.json", "wb") as f:
        f.write(tree_bytes(d))
    print("stock subset id", d["pins"]["stock"]["subset_id"], "abl subset id", d["pins"]["abl"]["subset_id"])


# ---------------------------------------------------------------- registered-run pin (issue #203, opt-in)
PIN_PATH = ROOT / "experiments/20261112-149-leaf-v2/runs/registered-pins.json"   # committed; test seam only
PIN_CONSUMED = ("blocks.jsonl", "leaves-v2.json", "run-meta.json")


def load_pin():
    """The committed registered-run pin. Always read from PIN_PATH, never from a run directory or its parent."""
    p = Path(PIN_PATH)
    try:
        pin = json.loads(p.read_text())
    except (OSError, ValueError, UnicodeDecodeError) as ex:
        raise EvidenceError("registered pin %s: cannot read (%s)" % (p.name, ex))
    ok = (isinstance(pin, dict) and isinstance(pin.get("runs"), dict) and isinstance(pin.get("compare_files"), dict)
          and pin.get("consumed_names") == list(PIN_CONSUMED)
          and all(isinstance(v, dict) and set(v) <= set(PIN_CONSUMED) and all(wbm._is_hex32(h) for h in v.values())
                  for v in pin["runs"].values())
          and all(wbm._is_hex32(h) for h in pin["compare_files"].values()))
    if not ok:
        raise EvidenceError("registered pin %s: malformed" % p.name)
    return pin


def _pinned_file(f, want, what):
    if f.is_symlink():
        raise EvidenceError("registered pin: %s is a symlink" % what)
    if not f.is_file():
        raise EvidenceError("registered pin: %s is pinned but missing or not a regular file" % what)
    got = hashlib.sha256(f.read_bytes()).hexdigest()
    if got != want:
        raise EvidenceError("registered pin: %s has sha256 %s..., the pin says %s..." % (what, got[:12], want[:12]))


def check_registered(rundir, pin=None):
    """Refuse (EvidenceError) a run directory that is not byte for byte the registered run of that name."""
    pin = pin if pin is not None else load_pin()
    d = Path(rundir)
    run = os.path.basename(os.path.normpath(os.path.abspath(str(d))))
    if d.is_symlink():
        raise EvidenceError("registered pin: run directory %s is a symlink" % run)
    if run not in pin["runs"]:
        raise EvidenceError("registered pin: %s is not a registered run (pinned: %s)" % (run, ", ".join(sorted(pin["runs"]))))
    if not d.is_dir():
        raise EvidenceError("registered pin: run directory %s is missing" % run)
    want = pin["runs"][run]
    for name in PIN_CONSUMED:
        f = d / name
        if name in want:
            _pinned_file(f, want[name], "%s/%s" % (run, name))
        elif f.exists() or f.is_symlink():
            raise EvidenceError("registered pin: %s/%s is present but not pinned for %s" % (run, name, run))
    return run


def check_registered_compare_files(runsdir, pin=None):
    """Each pinned compare file in runsdir must be a regular file with the pinned SHA-256."""
    pin = pin if pin is not None else load_pin()
    for name, want in sorted(pin["compare_files"].items()):
        _pinned_file(Path(runsdir) / name, want, name)


def pin_sha256():
    return hashlib.sha256(Path(PIN_PATH).read_bytes()).hexdigest()


def compare_runs(a, b, registered=False):
    if registered:
        pin = load_pin()
        check_registered(a, pin)
        check_registered(b, pin)
        d = _compare_runs(a, b)
        d["registered_pin_sha256"] = pin_sha256()
        return d
    return _compare_runs(a, b)


def _compare_runs(a, b):
    """H3 comparison of two run directories, on validated evidence only (EvidenceError otherwise).
    Per common block and pin: the canonical leaf-v2 JSON built from each run's record must be byte-identical
    (the registered H3 metric), and so must the fetched-bytes sha256. For a complete run the tree is rebuilt
    from the records, and a stored leaves-v2.json must equal that rebuild, so roots_equal / ids_equal /
    leaves_file_sha256_equal are statements about validated trees, not about stored strings.
    status: identical-complete (all 78 common, no mismatch), identical-partial (fewer common blocks, no
    mismatch: registered partial coverage), no-common-blocks, or mismatch."""
    (ra, sha_a), (rb, sha_b) = _load(a), _load(b)
    names, _ = registered()
    conv = conversions()
    common = sorted(set(ra) & set(rb))
    rows, same = [], 0
    for n in common:
        ok = ra[n]["kind"] == rb[n]["kind"]
        for pin in ("stock", "abl"):
            base = conv[pin].leaf_objs[conv[pin].index[n]]
            la = wc._canon(leaf_v2(base, ra[n][pin]["e"], ra[n][pin]["int_sha256"]))
            lb = wc._canon(leaf_v2(base, rb[n][pin]["e"], rb[n][pin]["int_sha256"]))
            if la != lb or ra[n][pin]["sha256"] != rb[n][pin]["sha256"]:
                ok = False
        same += ok
        rows.append(dict(name=n, kind=ra[n]["kind"], identical=ok))
    d = dict(n_a=len(ra), n_b=len(rb), n_common=len(common), n_identical=same,
             n_common_controls=sum(1 for r in rows if r["kind"] == "control"),
             n_common_changed=sum(1 for r in rows if r["kind"] == "changed"), rows=rows)
    inputs = dict(a_blocks_sha256=sha_a, b_blocks_sha256=sha_b)
    docs = {}
    for tag, rd, recs in (("a", a, ra), ("b", b, rb)):
        stored = (Path(rd) / "leaves-v2.json").exists()
        if len(recs) == len(names):
            docs[tag] = load_leaves(rd, recs, conv) if stored else tree_doc(recs, conv)
            if stored:
                inputs[tag + "_leaves_sha256"] = hashlib.sha256(tree_bytes(docs[tag])).hexdigest()
        elif stored:
            load_leaves(rd, recs, conv)     # raises: a stored tree next to an incomplete run
    trees_ok = True
    if len(docs) == 2:
        d["roots_equal"] = {p: docs["a"]["pins"][p]["root"] == docs["b"]["pins"][p]["root"] for p in ("stock", "abl")}
        d["ids_equal"] = {p: docs["a"]["pins"][p]["subset_id"] == docs["b"]["pins"][p]["subset_id"] for p in ("stock", "abl")}
        trees_ok = all(d["roots_equal"].values()) and all(d["ids_equal"].values())
        if "a_leaves_sha256" in inputs and "b_leaves_sha256" in inputs:
            d["leaves_file_sha256_equal"] = inputs["a_leaves_sha256"] == inputs["b_leaves_sha256"]
            trees_ok = trees_ok and d["leaves_file_sha256_equal"]
    if same != len(common) or not trees_ok:
        status = "mismatch"
    elif len(common) == len(names):
        status = "identical-complete"
    elif common:
        status = "identical-partial"
    else:
        status = "no-common-blocks"
    d["inputs"] = inputs
    d["status"] = status
    return d


def compare(a, b, outp, registered=False):
    d = compare_runs(a, b, registered=registered)
    with open(outp, "w") as f:
        json.dump(d, f, indent=1, sort_keys=True)
    print("compare", {k: v for k, v in d.items() if k != "rows"})
    return d["status"] != "mismatch"


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if a and a[0] == "run":
            bud = float(a[a.index("--budget-s") + 1]) if "--budget-s" in a else None
            run(a[1], reverse="--reverse" in a, budget_s=bud)
        elif a and a[0] == "tree":
            tree(a[1])
        elif a and a[0] == "compare":
            sys.exit(0 if compare(a[1], a[2], a[3], registered="--registered" in a[4:]) else 1)
        else:
            print(__doc__)
            sys.exit(2)
    except EvidenceError as ex:
        print("REFUSED:", ex, file=sys.stderr)
        sys.exit(2)
