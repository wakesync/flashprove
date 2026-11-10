#!/usr/bin/env python3
"""Negative and positive tests of wb_manifest.verify_opening (PR #87 review, astra item 3).

CPU only, seconds. Run from the top of the tree:
  python3 research/weight-binding/test_wb_manifest.py
Exit status 0 iff every named test passes. Each test prints PASS / FAIL with its name.

Fixtures: synthetic manifests of n = 1..40 leaves (made-up names and digests), and the real 1,199-leaf
stock manifest built from PR #68's streamed hashes on main
(experiments/20261109-8-qwen-real-weights/runs/stream-stock.json), which is what the reviewer's two
constructions used. No weight is read.
"""
import copy, hashlib, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import wb_manifest as wb  # noqa: E402

STREAM = ROOT / "experiments/20261109-8-qwen-real-weights/runs/stream-stock.json"
results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


def synthetic(n):
    t = {}
    for k in range(n):
        d = hashlib.sha256(b"synthetic-%d" % k).hexdigest()
        t["t%04d" % k] = ("BF16", (k + 1, 3), d)
    return wb.Manifest(t)


# ---- honest openings are accepted (all n = 1..40, every index) ----
ok = True
for n in range(1, 41):
    m = synthetic(n)
    hid = m.id.hex()
    for nm in m.names:
        if not wb.verify_opening(hid, m.open(nm)):
            ok = False
check("honest_openings_accepted_all_n_1_to_40", ok)

_, _, tensors = wb.tensors_from_stream(str(STREAM))
real = wb.Manifest(tensors)
rid = real.id.hex()
check("real_manifest_has_1199_leaves", len(real.names) == 1199)
check("honest_openings_accepted_real_1199", all(wb.verify_opening(rid, real.open(nm)) for nm in real.names))
op0 = real.open(real.names[0])

# ---- reviewer construction 1 (astra): honest index-0 opening, index changed to 2048 ----
bad = copy.deepcopy(op0); bad["index"] = 2048
check("astra_index_2048_of_1199_refused", not wb.verify_opening(rid, bad))
# 2048 = 0 mod 2^11 so the old walk gave the same root; also every out-of-range alias with the same low bits
aliases = [0 + k * 2048 for k in range(1, 8)] + [1199, 1200, 2047]
check("index_aliases_ge_n_refused", all(not wb.verify_opening(rid, dict(op0, index=i)) for i in aliases))
check("negative_index_refused", not wb.verify_opening(rid, dict(op0, index=-1)))
check("bool_index_refused", not wb.verify_opening(rid, dict(op0, index=False)))
check("float_index_refused", not wb.verify_opening(rid, dict(op0, index=0.0)))

# ---- reviewer construction 2 (astra): extra trailing None sibling ----
bad = copy.deepcopy(op0); bad["path"] = bad["path"] + [None]
check("astra_extra_trailing_none_refused", not wb.verify_opening(rid, bad))
bad = copy.deepcopy(op0); bad["path"] = bad["path"] + [None, None, None]
check("extra_trailing_nones_refused", not wb.verify_opening(rid, bad))
bad = copy.deepcopy(op0); bad["path"] = [None] + bad["path"]
check("extra_leading_none_refused", not wb.verify_opening(rid, bad))

# ---- other non-canonical paths ----
bad = copy.deepcopy(op0); bad["path"] = bad["path"][:-1]
check("path_too_short_refused", not wb.verify_opening(rid, bad))
bad = copy.deepcopy(op0); bad["path"][0] = bad["path"][0].upper()
check("uppercase_hex_sibling_refused", not wb.verify_opening(rid, bad))
bad = copy.deepcopy(op0); bad["path"][0] = bad["path"][0][:62]
check("short_hex_sibling_refused", not wb.verify_opening(rid, bad))
bad = copy.deepcopy(op0); bad["path"][0] = bad["path"][0] + "00"
check("long_hex_sibling_refused", not wb.verify_opening(rid, bad))
bad = copy.deepcopy(op0); bad["sha256"] = bad["sha256"].upper()
check("uppercase_leaf_digest_refused", not wb.verify_opening(rid, bad))
bad = copy.deepcopy(op0); bad["extra"] = 1
check("unknown_field_refused", not wb.verify_opening(rid, bad))

# Promoted (odd last) node: real tree, last leaf 1198 is promoted at level 0 (width 1199 is odd).
last = real.open(real.names[-1])
check("last_leaf_level0_is_promoted_none", last["path"][0] is None)
bad = copy.deepcopy(last); bad["path"][0] = "00" * 32
check("sibling_at_promoted_node_refused", not wb.verify_opening(rid, bad))
bad = copy.deepcopy(op0); bad["path"][0] = None
check("none_at_non_promoted_node_refused", not wb.verify_opening(rid, bad))
# Same length, a None in place of the level-0 sibling and that hash moved to the last level.
bad = copy.deepcopy(op0); bad["path"] = [None] + bad["path"][1:-1] + [bad["path"][0]]
check("none_substituted_for_sibling_refused", not wb.verify_opening(rid, bad))

# ---- index must match the leaf's position (not only be in range) ----
op1 = real.open(real.names[1])
check("index_of_other_leaf_refused", not wb.verify_opening(rid, dict(op0, index=1)))
check("index_swap_between_leaves_refused", not wb.verify_opening(rid, dict(op1, index=0)))

# ---- n is authenticated by the id ----
check("wrong_n_refused", not wb.verify_opening(rid, dict(op0, n=1200)))
check("wrong_n_smaller_refused", not wb.verify_opening(rid, dict(op0, n=1198)))

# ---- exhaustive mutations on small synthetic trees: every in-range index other than the true one,
# every out-of-range index below 4n, every path with one entry appended or removed ----
ok = True
for n in range(1, 41):
    m = synthetic(n)
    hid = m.id.hex()
    for k, nm in enumerate(m.names):
        op = m.open(nm)
        for i in range(-2, 4 * n):
            if i != k and wb.verify_opening(hid, dict(op, index=i)):
                ok = False
        if wb.verify_opening(hid, dict(op, path=op["path"] + [None])):
            ok = False
        if op["path"] and wb.verify_opening(hid, dict(op, path=op["path"][:-1])):
            ok = False
check("exhaustive_small_tree_index_and_length_mutations_refused", ok)

# n = 1: the path is empty; any sibling refused
m1 = synthetic(1)
o = m1.open(m1.names[0])
check("n1_empty_path_accepted", o["path"] == [] and wb.verify_opening(m1.id.hex(), o))
check("n1_extra_none_refused", not wb.verify_opening(m1.id.hex(), dict(o, path=[None])))

# ---- the H1 forged-digest control is still refused ----
bad = copy.deepcopy(op0); bad["sha256"] = "00" * 32
check("forged_digest_refused", not wb.verify_opening(rid, bad))

n_fail = sum(1 for _, c in results if not c)
print("%d tests, %d failed" % (len(results), n_fail))
sys.exit(1 if n_fail else 0)
