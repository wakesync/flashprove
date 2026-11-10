# research/weight-binding

Agenda Q2 (weight binding) for use case U1 (model substitution: did the provider serve the model it
claims?). Part of #36. Design: [DESIGN.md](DESIGN.md). Results: [experiments/20261110-36-weight-binding/RESULTS.md](../../experiments/20261110-36-weight-binding/RESULTS.md).

## What is proved

**Nothing.** No file here makes or checks a proof. This directory has a design and three CPU
checks:
- `wb_manifest.py`: a per-tensor manifest (Merkle tree over one leaf per tensor: name, dtype, shape,
  SHA-256 of the tensor's bytes) and a verifier that holds only a 32-byte model id. Hash level only.
- `wb_int.py`: fetches named tensors of both pinned checkpoints by HTTP range request (in memory),
  checks the bytes against #68's streamed hashes, converts them to integers by the rule of
  `weight_sums/weight_sums.py` (matrix, no norm), counts differences, and computes a toy multilinear
  fingerprint mod 2^31 - 1 at a pin-independent point.
- `wb_count.py`: counted costs of the design from main's shapes and counts (`count_m3.py`, #70 RESULTS).

## What the verifier recomputes

In `wb_manifest.py`: the leaf from the claimed (name, dtype, shape, digest), the path to the root,
and the id; it compares with the id it holds. Nothing else.

## What is not covered

Any proof relation; the commitment ID of `cp_commit`; the Qwen weight table and its range proof;
norm-folded tensors; 64 of the 70 changed tensors at integer level; the protocol's field. See
RESULTS.md "What is established and what is not".

## Reproduce

From the top of the tree. Python 3.12, numpy 2.4.3. No token; both repos are public.

```sh
R=experiments/20261109-8-qwen-real-weights/runs
E=experiments/20261110-36-weight-binding/runs
python3 research/weight-binding/wb_manifest.py demo $R/stream-stock.json $R/stream-abl.json $E/h1-manifest-demo.json
python3 research/weight-binding/wb_manifest.py build $R/stream-stock.json $E/manifest-stock.json
python3 research/weight-binding/wb_manifest.py build $R/stream-abl.json $E/manifest-abl.json
python3 research/weight-binding/wb_int.py selftest
research/weight-binding/run_registered.sh        # H2/H3: 7 tensors x 2 pins, about 786 MB per pin over HTTP, 3.8 GB peak RSS
python3 research/weight-binding/wb_count.py      # writes $E/counted.json
```

`run_registered.sh` was run through the host's heavy-job gate and pinned with `taskset -c 6-11`
(it calls taskset itself). The H1 outputs are deterministic. H2/H3 outputs are deterministic
except the fetch and fingerprint times.
