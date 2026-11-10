#!/usr/bin/env python3
"""Per-tensor weight manifest under a Merkle root, and a verifier that holds only the root (the model id).

HASH LEVEL ONLY. THIS IS NOT A PROOF. It shows what a per-tensor commitment can and cannot tell
apart, using the per-tensor SHA-256 of the BF16 bytes that PR #68 streamed for both pinned
checkpoints (experiments/20261109-8-qwen-real-weights/runs/stream-{stock,abl}.json). No weight is
read here. In a real statement the leaves would be per-tensor roots of the committed integer table,
and the opening would be inside the proof (DESIGN.md section 3).

Leaf of tensor t (sorted by name):
  H(0x00 || "fp-wb-leaf-v1" || len||name || len||dtype || len||shape-json || sha256(bytes))
Node: H(0x01 || "fp-wb-node-v1" || left || right). An odd node is promoted unchanged.
Model id: H("fp-wb-id-v1" || n_tensors (8 bytes LE) || root).
H = SHA-256. The leaf index is fixed by the sorted name list, which is part of the id through n and
the leaf contents; an opening names its index and the verifier recomputes the leaf from the claimed
(name, dtype, shape, digest).

Usage:
  wb_manifest.py build <stream.json> <out-manifest.json>
  wb_manifest.py demo <stream-stock.json> <stream-abl.json> <out.json>
"""
import hashlib, json, struct, sys, time


def _h(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.digest()


def _lp(b):
    return struct.pack("<Q", len(b)) + b


def leaf_hash(name, dtype, shape, digest_hex):
    return _h(b"\x00", b"fp-wb-leaf-v1", _lp(name.encode()), _lp(dtype.encode()),
              _lp(json.dumps(list(shape), separators=(",", ":")).encode()), bytes.fromhex(digest_hex))


def node_hash(a, b):
    return _h(b"\x01", b"fp-wb-node-v1", a, b)


def tensors_from_stream(path):
    """name -> (dtype, shape, sha256 hex) from a #68 stream file."""
    s = json.load(open(path))
    out = {}
    for shard in s["shards"].values():
        for name, t in shard["tensors"].items():
            assert name not in out, name
            out[name] = (t["dtype"], tuple(t["shape"]), t["sha256"])
    return s["repo"], s["rev"], out


def levels(leaves):
    lv = [leaves]
    while len(lv[-1]) > 1:
        cur, nxt = lv[-1], []
        for i in range(0, len(cur), 2):
            nxt.append(node_hash(cur[i], cur[i + 1]) if i + 1 < len(cur) else cur[i])
        lv.append(nxt)
    return lv


def model_id(n, root):
    return _h(b"fp-wb-id-v1", struct.pack("<Q", n), root)


class Manifest:
    def __init__(self, tensors):
        self.names = sorted(tensors)
        self.tensors = tensors
        self.leaves = [leaf_hash(n, *tensors[n]) for n in self.names]
        self.lv = levels(self.leaves)
        self.root = self.lv[-1][0]
        self.id = model_id(len(self.names), self.root)
        self.index = {n: i for i, n in enumerate(self.names)}

    def open(self, name):
        """Opening of one tensor: (index, n, name, dtype, shape, digest, path)."""
        i = self.index[name]
        path, j = [], i
        for cur in self.lv[:-1]:
            sib = j ^ 1
            path.append(cur[sib].hex() if sib < len(cur) else None)
            j //= 2
        d, s, h = self.tensors[name]
        return dict(index=i, n=len(self.names), name=name, dtype=d, shape=list(s), sha256=h, path=path)


def verify_opening(held_id_hex, op):
    """True iff the opening recomputes the verifier-held id. The verifier holds only the 32-byte id."""
    cur, j = leaf_hash(op["name"], op["dtype"], op["shape"], op["sha256"]), op["index"]
    for sib in op["path"]:
        if sib is not None:
            s = bytes.fromhex(sib)
            cur = node_hash(cur, s) if j % 2 == 0 else node_hash(s, cur)
        j //= 2
    return model_id(op["n"], cur).hex() == held_id_hex


def verify_manifest(held_id_hex, tensors):
    return Manifest(tensors).id.hex() == held_id_hex


def build(stream, out):
    repo, rev, t = tensors_from_stream(stream)
    m = Manifest(t)
    json.dump(dict(note="hash-level per-tensor manifest, NOT A PROOF", repo=repo, rev=rev, n=len(m.names),
                   root=m.root.hex(), model_id=m.id.hex(),
                   tensors=[dict(name=n, dtype=t[n][0], shape=list(t[n][1]), sha256=t[n][2]) for n in m.names]),
              open(out, "w"), indent=1)
    print(repo, rev, len(m.names), m.id.hex())


def demo(stock_path, abl_path, out):
    t0 = time.time()
    pins = {}
    for tag, p in (("stock", stock_path), ("abl", abl_path)):
        repo, rev, t = tensors_from_stream(p)
        pins[tag] = dict(repo=repo, rev=rev, tensors=t, m=Manifest(t))
    a, b = pins["stock"], pins["abl"]
    assert a["m"].names == b["m"].names, "name lists differ"
    names = a["m"].names
    changed = [n for n in names if a["tensors"][n] != b["tensors"][n]]
    same = [n for n in names if a["tensors"][n] == b["tensors"][n]]
    res = dict(note="HASH LEVEL ONLY. NOT A PROOF. Leaves are #68's per-tensor sha256 of the BF16 bytes.",
               inputs=dict(stock=stock_path.split("experiments/")[-1], abl=abl_path.split("experiments/")[-1]),
               n_tensors=len(names), n_changed=len(changed), n_same=len(same),
               ids={k: v["m"].id.hex() for k, v in pins.items()},
               roots={k: v["m"].root.hex() for k, v in pins.items()},
               revs={k: v["rev"] for k, v in pins.items()}, directions={})
    for held, other in (("stock", "abl"), ("abl", "stock")):
        hid = pins[held]["m"].id.hex()
        om = pins[other]["m"]
        d = dict(held_id=hid,
                 own_manifest_accepted=verify_manifest(hid, pins[held]["tensors"]),
                 other_manifest_accepted=verify_manifest(hid, pins[other]["tensors"]),
                 own_openings_accepted=sum(verify_opening(hid, pins[held]["m"].open(n)) for n in names),
                 other_changed_openings_accepted=sum(verify_opening(hid, om.open(n)) for n in changed),
                 other_unchanged_openings_accepted=sum(verify_opening(hid, om.open(n)) for n in same))
        # Control: a forged opening that claims the other pin's digest with this pin's path must fail.
        n0 = changed[0]
        forged = pins[held]["m"].open(n0)
        forged["sha256"] = pins[other]["tensors"][n0][2]
        d["forged_digest_with_honest_path_accepted"] = verify_opening(hid, forged)
        res["directions"][f"held_{held}"] = d
    fam = {}
    for n in changed:
        f = n.split(".")[-3] + "." + n.split(".")[-2]
        fam[f] = fam.get(f, 0) + 1
    res["changed_by_family"] = fam
    res["changed_layers"] = sorted({int(n.split(".layers.")[1].split(".")[0]) for n in changed})
    res["opening_bytes_path_entries"] = len(a["m"].open(names[0])["path"])
    res["seconds"] = round(time.time() - t0, 3)
    json.dump(res, open(out, "w"), indent=1)
    for k, v in res["directions"].items():
        print(k, json.dumps(v))
    print("changed", len(changed), "same", len(same), "layers", res["changed_layers"][0], "..", res["changed_layers"][-1])


def leaves(stock_path, abl_path, out):
    """Unregistered (amendment A1): the leaf-level view. A Merkle opening carries its tree's path, so an
    opening taken from the other pin's tree recomputes the other pin's root even where the leaf is the
    same. What a statement confined to unchanged tensors cannot see is the leaf itself. Counts equal
    leaves, and checks the splice: the held pin's own path with the other pin's leaf."""
    pins = {}
    for tag, p in (("stock", stock_path), ("abl", abl_path)):
        _, rev, t = tensors_from_stream(p)
        pins[tag] = dict(rev=rev, tensors=t, m=Manifest(t))
    a, b = pins["stock"]["m"], pins["abl"]["m"]
    eq = [n for n in a.names if a.leaves[a.index[n]] == b.leaves[b.index[n]]]
    ne = [n for n in a.names if a.leaves[a.index[n]] != b.leaves[b.index[n]]]
    res = dict(note="HASH LEVEL ONLY. NOT A PROOF. Unregistered, amendment A1.", leaves_equal=len(eq), leaves_differ=len(ne))
    for held, other in (("stock", "abl"), ("abl", "stock")):
        hm, om = pins[held]["m"], pins[other]["m"]
        hid = hm.id.hex()
        acc_eq = acc_ne = 0
        for n in a.names:
            op = hm.open(n)
            op["sha256"] = pins[other]["tensors"][n][2]  # the other pin's leaf on the held pin's path
            ok = verify_opening(hid, op)
            if n in set(eq):
                acc_eq += ok
            else:
                acc_ne += ok
        res[f"held_{held}"] = dict(splice_unchanged_accepted=acc_eq, splice_changed_accepted=acc_ne)
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    if sys.argv[1] == "leaves":
        leaves(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "build":
        build(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "demo":
        demo(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(__doc__)
