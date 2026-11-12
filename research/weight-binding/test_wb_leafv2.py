#!/usr/bin/env python3
"""Hostile-leaf suite for conversion leaf v2 (issue #149, H4). HASH LEVEL, NOT A PROOF.

Extends #100's opening tests (test_wb_conv.py) to the two new leaf fields e and int_sha256.
Input: a run directory with blocks.jsonl (all 78 blocks). Output: JSON of every check.

Usage: test_wb_leafv2.py <rundir> <out.json>
"""
import copy, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wb_leafv2 as lv  # noqa: E402
import wb_conv as wc  # noqa: E402

RES = []


def check(group, name, cond):
    RES.append(dict(group=group, name=name, ok=bool(cond)))


def main(rundir, outp):
    recs = lv.load_records(rundir)
    names, changed = lv.registered()
    assert set(recs) == set(names)
    conv = lv.conversions()
    S = lv.SubsetV2(conv["stock"], recs, "stock")
    A = lv.SubsetV2(conv["abl"], recs, "abl")
    SID = S.id.hex()

    check("honest", "all 78 stock openings verify", all(lv.verify_opening_v2(SID, S.open(b)) for b in S.names))
    check("honest", "all 78 abliterated openings verify under the abliterated id",
          all(lv.verify_opening_v2(A.id.hex(), A.open(b)) for b in A.names))
    check("honest", "stock subset id != abliterated subset id", S.id != A.id)
    nref = 0
    for b in sorted(changed):
        op = S.open(b)
        op["leaf"] = copy.deepcopy(A.leaf_objs[A.index[b]])
        nref += not lv.verify_opening_v2(SID, op)
    check("honest", "abliterated leaf (stock path) refused under stock id, %d of 70 changed blocks" % nref, nref == 70)
    nctl = 0
    for b in lv.CONTROLS:
        op = S.open(b)
        op["leaf"] = copy.deepcopy(A.leaf_objs[A.index[b]])
        nctl += lv.verify_opening_v2(SID, op) and A.leaf_objs[A.index[b]]["e"] == S.leaf_objs[S.index[b]]["e"]
    check("controls", "abliterated control leaves are identical to stock and verify under the stock id (%d of 8)" % nctl,
          nctl == 8)

    # ---- hostile mutations of the two new fields, on every changed block and every control
    def mut_open(b, fn):
        op = S.open(b)
        leaf = copy.deepcopy(op["leaf"])
        fn(leaf, b)
        op["leaf"] = leaf
        return lv.verify_opening_v2(SID, op)

    def flip_hex(h):
        c = "0" if h[17] != "0" else "1"
        return h[:17] + c + h[18:]

    def other_pin(leaf, b):
        leaf["int_sha256"] = A.leaf_objs[A.index[b]]["int_sha256"]

    new_kinds = {
        "e + 1": lambda l, b: l.__setitem__("e", l["e"] + 1),
        "e - 1": lambda l, b: l.__setitem__("e", l["e"] - 1),
        "e as string": lambda l, b: l.__setitem__("e", str(l["e"])),
        "e as bool": lambda l, b: l.__setitem__("e", True),
        "e as float": lambda l, b: l.__setitem__("e", float(l["e"])),
        "e missing": lambda l, b: l.pop("e"),
        "int_sha256 one hex digit changed": lambda l, b: l.__setitem__("int_sha256", flip_hex(l["int_sha256"])),
        "int_sha256 uppercase": lambda l, b: l.__setitem__("int_sha256", l["int_sha256"].upper()),
        "int_sha256 truncated": lambda l, b: l.__setitem__("int_sha256", l["int_sha256"][:63]),
        "int_sha256 missing": lambda l, b: l.pop("int_sha256"),
        "int_sha256 all zero": lambda l, b: l.__setitem__("int_sha256", "0" * 64),
        "e and int_sha256 swapped": lambda l, b: (l.__setitem__("e", l["int_sha256"]), l.__setitem__("int_sha256", "%064x" % 12)),
        "extra leaf field": lambda l, b: l.__setitem__("int_sha256_alt", l["int_sha256"]),
    }
    for kname, fn in new_kinds.items():
        tot = 0
        ref = 0
        for b in S.names:
            tot += 1
            ref += not mut_open(b, fn)
        check("new-field", "%s refused (%d of %d blocks)" % (kname, ref, tot), ref == tot)
    tot = ref = 0
    for b in sorted(changed):
        tot += 1
        ref += not mut_open(b, other_pin)
    check("new-field", "int_sha256 set to the abliterated value refused (%d of %d changed blocks)" % (ref, tot), ref == tot)
    tot = ref = 0
    for b in sorted(changed):
        def both(l, b=b):
            l["e"] = A.leaf_objs[A.index[b]]["e"]
            l["int_sha256"] = A.leaf_objs[A.index[b]]["int_sha256"]
        tot += 1
        ref += not mut_open(b, both)
    check("new-field", "e and int_sha256 both set to the abliterated values refused (%d of %d)" % (ref, tot), ref == tot)

    # ---- #100 mutation kinds on v2 leaves
    b0 = S.names[0]
    old_kinds = {
        "rule step swapped to STEP_FOLDED": lambda l, b: l["rule"].__setitem__("step", wc.STEP_FOLDED),
        "rule param added": lambda l, b: l["rule"]["params"].__setitem__("c_f32", wc._f32hex(1.0)),
        "rule round changed": lambda l, b: l["rule"]["params"].__setitem__("round", "RNA"),
        "source hash changed": lambda l, b: l["sources"][0].__setitem__(1, "%064x" % 7),
        "class changed to matrix_norm_folded": lambda l, b: l.__setitem__("cls", "matrix_norm_folded"),
        "block renamed": lambda l, b: l.__setitem__("block", l["block"].replace("weight", "weight2")),
        "float in params": lambda l, b: l["rule"]["params"].__setitem__("x", 1.5),
        "cls = []": lambda l, b: l.__setitem__("cls", []),
    }
    for kname, fn in old_kinds.items():
        tot = ref = 0
        for b in S.names:
            tot += 1
            ref += not mut_open(b, fn)
        check("v1-kind", "%s refused (%d of %d)" % (kname, ref, tot), ref == tot)

    # ---- opening level
    for fld, val in (("config_pin", "%064x" % 1), ("rule_version", "fp-qwen3.8-conv-rules-v0"),
                     ("checkpoint_id", conv["abl"].ck.id.hex()), ("n", 77), ("index", 1)):
        op = S.open(b0)
        op[fld] = val
        check("opening", "%s changed refused" % fld, not lv.verify_opening_v2(SID, op))
    op = S.open(b0)
    op["path"][0] = "%064x" % 3
    check("opening", "path element changed refused", not lv.verify_opening_v2(SID, op))
    op = S.open(b0)
    op["path"].append(None)
    check("opening", "extra path element refused", not lv.verify_opening_v2(SID, op))
    op = S.open(b0)
    op["extra"] = 1
    check("opening", "extra field refused", not lv.verify_opening_v2(SID, op))
    op = S.open(b0)
    op["leaf"] = {k: op["leaf"][k] for k in ("block", "cls", "sources", "rule")}
    check("opening", "v1 leaf (no e, no int_sha256) refused under the v2 id", not lv.verify_opening_v2(SID, op))
    # a v1 conversion-id opening is not a v2 opening
    check("opening", "v1 conversion-id opening of the same block refused under the v2 id",
          not lv.verify_opening_v2(SID, conv["stock"].open(b0)))

    npass = sum(r["ok"] for r in RES)
    out = dict(note="hostile leaf-v2 suite, hash level, NOT A PROOF", subset_id_stock=SID, subset_id_abl=A.id.hex(),
               n_checks=len(RES), n_pass=npass, n_new_field_kinds=len(new_kinds) + 2, results=RES)
    with open(outp, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    print("leafv2 tests %d / %d pass" % (npass, len(RES)))
    return npass == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1], sys.argv[2]) else 1)
