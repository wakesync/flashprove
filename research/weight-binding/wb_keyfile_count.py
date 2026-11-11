#!/usr/bin/env python3
"""Table-side cost of the key-file claim (DESIGN.md 2.0 object 3, 2.2): one multilinear evaluation per
effective text block at a derived point. Issue #91. COUNTED from shapes, not measured, not a proof.

For each of the 722 effective blocks of the conversion id (wb_conv), n_b = number of integers the block
commits (product of its source shape), v_b = ceil(log2 n_b) variables, padded size 2^v_b. Counted:
  - total committed integers, total padded entries (sum 2^v_b), padding overhead;
  - sum of v_b (point coordinates the verifier derives, one hash each);
  - field multiplications to evaluate MLE_b(z_b) by the standard fold (round i halves the array, one
    multiplication per surviving pair): sum over b of (2^v_b - 1);
  - equivalently via the eq-table route (build eq(z, .) with 2^v_b - 1 mults, then a 2^v_b inner
    product): 2 x 2^v_b - 1 per block. Reported as an alternative, not the minimum.
Also the same for the 851-source-tensor count the first #87 version used, to show the gap.

The proof-side cost (how the key file's batched claim is opened against the committed table, e.g. one
random linear combination of the 722 claims and one opening) depends on the commitment scheme and is
NOT counted here.

Usage: wb_keyfile_count.py <stream-stock.json> <config-stock.json> <out.json>
"""
import collections, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wb_conv as wc  # noqa: E402
import wb_manifest as wbm  # noqa: E402


def nvars(n):
    return max(0, (n - 1).bit_length())


def count(shapes):
    tot = pad = vars_ = fold = eq = 0
    for s in shapes:
        n = 1
        for d in s:
            n *= d
        v = nvars(n)
        tot += n
        pad += 1 << v
        vars_ += v
        fold += (1 << v) - 1
        eq += 2 * (1 << v) - 1
    return dict(blocks=len(shapes), integers=tot, padded_entries=pad, padding_overhead=round(pad / tot - 1, 6),
                point_coordinates=vars_, fold_mults=fold, eq_route_mults=eq)


def main(stream, cfg_path, out):
    _, _, t = wbm.tensors_from_stream(stream)
    c = wc.Conversion(t, json.load(open(cfg_path)))
    per_cls = collections.defaultdict(list)
    for o in c.leaf_objs:
        per_cls[o["cls"]].append(t[o["block"]][1])
    eff = count([t[b][1] for b in c.names])
    text_src = [t[n][1] for n in t if n.startswith(wc.LM) or n == "lm_head.weight"]
    d = dict(label="COUNTED from tensor shapes, not measured, not a proof; proof-side opening cost not counted",
             conversion_id=c.id.hex(), effective=eff, by_class={k: count(v) for k, v in sorted(per_cls.items())},
             text_source_851=count(text_src),
             largest_block=max(((b, t[b][1]) for b in c.names), key=lambda x: x[1][0] * (x[1][1] if len(x[1]) > 1 else 1))[0])
    assert eff["blocks"] == 722
    with open(out, "w") as f:
        json.dump(d, f, indent=1)
        f.write("\n")
    print(json.dumps(dict(effective=eff, text_source_851=d["text_source_851"]), indent=1))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    main(*sys.argv[1:])
