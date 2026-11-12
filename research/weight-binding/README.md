# research/weight-binding

Agenda Q2 (weight binding) for use case U1 (model substitution: did the provider serve the model it
claims?). Part of #36. Design: [DESIGN.md](DESIGN.md). Results: [experiments/20261110-36-weight-binding/RESULTS.md](../../experiments/20261110-36-weight-binding/RESULTS.md).

## What is proved

The original #87/#100 files below make no proof. The new [keyfile research adapter](keyfile/README.md)
adds per-tensor evaluation claims to the existing CPU small-key WF/BATT/LIN fixture, with a separate
research key format. It is not production cp_verify or a Qwen proof, and establishes no soundness level.
The original hash-level work has a design and these CPU checks:
- `wb_manifest.py`: a per-tensor manifest (Merkle tree over one leaf per tensor: name, dtype, shape,
  SHA-256 of the tensor's bytes) and a verifier that holds only a 32-byte model id. Hash level only.
- `wb_int.py`: fetches named tensors of both pinned checkpoints by HTTP range request (in memory),
  checks the bytes against #68's streamed hashes, converts them to integers by the rule of
  `weight_sums/weight_sums.py` (matrix, no norm), counts differences, and computes a toy multilinear
  fingerprint mod 2^31 - 1 at a pin-independent point.
- `wb_count.py`: counted costs of the design from main's shapes and counts (`count_m3.py`, #70 RESULTS).
- `wb_inventory.py`: counted source-to-effective inventory: every one of the 1,199 source tensors
  classified as matrix block, folded norm, weight cell (direct, scaled, derived, fixed-F, q/k norm),
  visual or MTP. Names only.
- `test_wb_manifest.py`: 29 named tests of the opening verifier, including the two malformed
  openings the PR #87 review built (index 2048 of 1,199; extra trailing None). CPU, seconds.
- `rerun_pr87.sh`, `compare_rerun.py`: the PR #87 rerun of H1 and the count with committed code
  into `runs-rerun-pr87/`, and its comparison with `runs/`.
- `wb_conv.py` (issue #91, PR #100): the conversion id of DESIGN 2.0 object 2, hash level. Order:
  checkpoint id (from `wb_manifest.py`) -> rule version string -> config pin -> block count -> Merkle
  root over one leaf per effective text block (722). A leaf carries the block name, its class (9
  classes), its ordered sources as (name, checkpoint-leaf hash) and the rule step text with its
  parameters. The builder enforces the inventory 851 = 498 + 224 + 129 (722 effective blocks) and
  every tensor shape against the pinned config. Functions: `config_fields` (strict config schema),
  `config_pin`, `classify`, `check_shapes`, `Conversion` (build, `open(block)`), `leaf_well_formed`,
  `verify_conv_opening` (one block leaf against a held id), `verify_conversion` (whole recompute).
- Config pin v2 (after the PR #100 reviews): `text_config` must exist; 24 `text_config` fields and 3
  top-level fields (`architectures`, `model_type`, `tie_word_embeddings`) are pinned with fixed types;
  any key outside the pinned set and a listed known-unpinned set refuses; only the supported variant
  builds (both `tie_word_embeddings` false, `attention_bias` false, equal `partial_rotary_factor`
  copies). The pin hashes a typed tree ([type tag, payload] per value), so the encoding is injective.
  The first version (`runs/`) hashed only `text_config` and encoded floats as `{"f64": hex}`, which a
  config could supply literally; see the experiment's RESULTS "Corrected run".
- `test_wb_conv.py`: 128 named tests of `wb_conv` (honest, per-class hostile leaf mutations, opening
  mutations, same-tensor config substitutions, inventory errors, scope). Exit 0 iff all pass.
- `wb_keyfile_count.py`: counted table-side cost of the key-file claim (one multilinear evaluation per
  effective block, flat padding). Counted from shapes, not measured.
- `run_wb91.sh <outdir>`: the #91 run: both pins built twice, the test suite twice, the count.

## What the verifier recomputes

In `wb_manifest.py`: first that the opening is canonical for its claimed leaf count n (0 <= index
< n; path length equal to the tree depth for n; a `None` sibling exactly at a promoted odd last
node; every hash 64 lowercase hex), then the leaf from the claimed (name, dtype, shape, digest), the
path to the root, and the id; it compares with the id it holds. n is authenticated by the id.
Nothing else. The canonical check was added after the H1 run (PR #87 review); the original `runs/`
were produced without it, `runs-rerun-pr87/` with it, and the counts are equal.

## What is not covered by the original hash-level files

The keyfile adapter's separate scope and limitations are in [its README](keyfile/README.md).
For the original files below: any proof relation; the commitment ID of `cp_commit`; the Qwen weight table and its range proof;
norm-folded tensors at integer level; 64 of the 70 changed tensors at integer level; the protocol's
field; the evaluation responses of DESIGN 2.0 (designed, not built). The conversion id and the
config pin (A12) are built (`wb_conv.py`) but only at hash level, with these limits: the leaf has no
exponent e_b or integer hash int_sha256_b (that needs the 55.6 GB conversion per pin); the rule steps
are bound as text and no converter here runs them on real bytes; the folded constant c = 1.0 is a
placeholder; which config fields change the function is a judgement (fail closed on unknown keys,
but the known-unpinned list in `wb_conv.py` is a choice); only one model variant is supported; nothing
binds the committed table to the conversion id inside a proof. The 333 visual and 15 MTP tensors are in the H1 id but outside U1 scope; any Fiat-Shamir or
grinding security bound (DESIGN 2.0 states only the fixed-pair Schwartz-Zippel bound). The
verifier raises an exception, rather than returning false, on some malformed inputs (n = 2^64,
a tensor name with an unpaired surrogate), and compares the held id case-sensitively. See
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
python3 research/weight-binding/test_wb_manifest.py   # 29 named verifier tests, exit 0 iff all pass
O=experiments/20261110-36-weight-binding/runs-rerun-pr87   # sibling of runs/, not inside it
research/weight-binding/rerun_pr87.sh                 # PR #87 rerun into $O/ (tests, H1, count, compare)
python3 research/weight-binding/wb_inventory.py $O/inventory.json
```

Conversion id, config pin, tests and count (issue #91). CPU, seconds, no network, no weights. Write
into a fresh directory (never into a committed `runs*/` directory) and compare:

```sh
O=$(mktemp -d)
bash research/weight-binding/run_wb91.sh "$O"
diff -r -x python.txt "$O" experiments/20261111-91-conversion-id/runs-fix100   # expect no output
python3 research/weight-binding/test_wb_conv.py      # 128 / 128 PASS, exit 0
```

The first-run files in `experiments/20261111-91-conversion-id/runs/` were made by the v1 code at
d39c98dc and are not reproduced by the current code (the config pin changed, so the ids did).

Note: the commands for `runs/` above reproduce the original files, but the original H1 outputs and
`counted.json` were written before their scripts were committed (RESULTS deviations 4, 5); the
reproduction from committed code is `runs-rerun-pr87/`.

`run_registered.sh` was run through the host's heavy-job gate and pinned with `taskset -c 6-11`
(it calls taskset itself). The H1 outputs are deterministic. H2/H3 outputs are deterministic
except the fetch and fingerprint times.
