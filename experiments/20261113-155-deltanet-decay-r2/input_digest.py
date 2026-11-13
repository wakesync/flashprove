#!/usr/bin/env python3
"""Content digest of the input arrays, independent of the .npz container bytes (written after the registered run,
bookkeeping only; no arm is evaluated here).

Why: PREREG.md pins the 48 input files by the sha256 of their bytes, and .npz is a zip container. Whether a
re-recording with PR #146's record.py gives the same file bytes was not tested by this lane. This digest is over the
array contents only (name, dtype, shape, raw little-endian bytes), so a replication can compare a re-recorded
directory with the one used here whatever the container bytes are.

usage: input_digest.py <ar_dir> [--write]     prints the digest; --write stores runs/input-content.json
       input_digest.py <ar_dir> --compare     exit 0 iff the directory's content equals runs/input-content.json
"""
import hashlib, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decay_r2 as R
SU = R.SU


def layer_digest(path):
    d = np.load(path); h = hashlib.sha256()
    for k in sorted(d.files):
        a = np.ascontiguousarray(d[k]); a = a.astype(a.dtype.newbyteorder("<"), copy=False)
        h.update(json.dumps([k, a.dtype.str, list(a.shape)]).encode()); h.update(a.tobytes())
    return h.hexdigest(), sorted(d.files)


def digest(ar_dir):
    out = {}
    for i in SU.DELTANET_LAYERS:
        n = f"ar-L{i:02d}.npz"; hx, keys = layer_digest(Path(ar_dir) / n)
        out[n] = dict(content_sha256=hx, arrays=len(keys))
    allh = hashlib.sha256("".join(f"{v['content_sha256']}  {k}\n" for k, v in sorted(out.items())).encode()).hexdigest()
    return dict(what="sha256 over (array name, dtype, shape, raw little-endian bytes) of every array in each layer file, arrays in name order",
                layers=out, all_layers_sha256=allh)


if __name__ == "__main__":
    dg = digest(sys.argv[1]); p = HERE / "runs" / "input-content.json"
    if "--compare" in sys.argv:
        want = json.loads(p.read_text()); ok = want["layers"] == dg["layers"]
        print("content equal to runs/input-content.json:", ok); sys.exit(0 if ok else 1)
    if "--write" in sys.argv:
        try: dg["file_bytes_match_prereg_list"] = bool(R.check_inputs(sys.argv[1]))
        except SU.Incomplete: dg["file_bytes_match_prereg_list"] = False
        p.write_text(json.dumps(dg, indent=1) + "\n")
    print(json.dumps(dict(all_layers_sha256=dg["all_layers_sha256"], layers=len(dg["layers"]))))
