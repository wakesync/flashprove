#!/usr/bin/env python3
"""Conversion leaf v2 on real bytes, issue #149 (experiments/20261112-149-leaf-v2). HASH LEVEL, NOT A PROOF.

Leaf v2 = the #91 leaf object (wb_conv.leaf_obj, unchanged) plus "e" (the block's exponent) and
"int_sha256" (SHA-256 of the int16 little-endian row-major integers), computed by the executable matrix
rule of wb_int.py (fetch / bf16_to_f32 / to_int, imported unchanged). Restricted to the 70 tensors #68
found different plus 8 registered byte-identical controls, all class matrix_plain (rule STEP_MATRIX, no
norm). The tree over those 78 blocks gives a SUBSET id (tag fp-wb-conv-subset-v2), not a model
conversion id (that needs all 722 blocks).

Bytes are fetched by HTTP range request into memory, one tensor per pin at a time, never written to disk.

Usage (from the top of the tree):
  wb_leafv2.py run <outdir> [--reverse] [--budget-s SECONDS]   fetch, hash, convert; writes outdir/blocks.jsonl
  wb_leafv2.py tree <outdir>                                    leaves + trees + subset ids -> outdir/leaves-v2.json
  wb_leafv2.py compare <outdirA> <outdirB> <out.json>           byte-level comparison of two runs (H3)
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


def load_records(outdir):
    recs = {}
    for line in open(Path(outdir) / "blocks.jsonl"):
        r = json.loads(line)
        recs[r["name"]] = r
    return recs


def tree(outdir):
    recs = load_records(outdir)
    names, _ = registered()
    assert set(recs) == set(names), "tree needs all 78 blocks (have %d)" % len(recs)
    conv = conversions()
    out = {}
    for pin in ("stock", "abl"):
        s = SubsetV2(conv[pin], recs, pin)
        out[pin] = dict(checkpoint_id=conv[pin].ck.id.hex(), config_pin=conv[pin].pin.hex(), n=len(s.names),
                        root=s.root.hex(), subset_id=s.id.hex(), leaf_hashes=[x.hex() for x in s.lv[0]],
                        leaves=s.leaf_objs)
    d = dict(note="conversion leaf v2 subset (78 matrix_plain blocks), hash level, NOT A PROOF, NOT a model conversion id",
             leaf_tag=LEAF_TAG.decode(), node_tag=NODE_TAG.decode(), id_tag=ID_TAG.decode(), rule_version=wc.RULE_VERSION,
             pins=out)
    with open(Path(outdir) / "leaves-v2.json", "w") as f:
        json.dump(d, f, indent=1, sort_keys=True)
        f.write("\n")
    print("stock subset id", out["stock"]["subset_id"], "abl subset id", out["abl"]["subset_id"])


def compare(a, b, outp):
    ra, rb = load_records(a), load_records(b)
    common = sorted(set(ra) & set(rb))
    rows, same = [], 0
    for n in common:
        ok = True
        for pin in ("stock", "abl"):
            for k in ("sha256", "e", "int_sha256"):
                if ra[n][pin][k] != rb[n][pin][k]:
                    ok = False
        same += ok
        rows.append(dict(name=n, kind=ra[n]["kind"], identical=ok))
    d = dict(n_a=len(ra), n_b=len(rb), n_common=len(common), n_identical=same,
             n_common_controls=sum(1 for r in rows if r["kind"] == "control"),
             n_common_changed=sum(1 for r in rows if r["kind"] == "changed"), rows=rows)
    la, lb = Path(a) / "leaves-v2.json", Path(b) / "leaves-v2.json"
    if la.exists() and lb.exists():
        ja, jb = json.load(open(la)), json.load(open(lb))
        d["roots_equal"] = {p: ja["pins"][p]["root"] == jb["pins"][p]["root"] for p in ("stock", "abl")}
        d["ids_equal"] = {p: ja["pins"][p]["subset_id"] == jb["pins"][p]["subset_id"] for p in ("stock", "abl")}
        d["leaves_file_sha256_equal"] = hashlib.sha256(la.read_bytes()).hexdigest() == hashlib.sha256(lb.read_bytes()).hexdigest()
    json.dump(d, open(outp, "w"), indent=1, sort_keys=True)
    print("compare", {k: v for k, v in d.items() if k != "rows"})


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "run":
        bud = float(a[a.index("--budget-s") + 1]) if "--budget-s" in a else None
        run(a[1], reverse="--reverse" in a, budget_s=bud)
    elif a and a[0] == "tree":
        tree(a[1])
    elif a and a[0] == "compare":
        compare(a[1], a[2], a[3])
    else:
        print(__doc__)
        sys.exit(2)
