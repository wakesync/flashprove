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
- `wb_leafv2.py` (issue #149, experiment `20261112-149-leaf-v2`): conversion leaf v2 on real bytes for
  a SUBSET of blocks: the 70 tensors #68 found different plus 8 registered byte-identical controls (all
  class `matrix_plain`). Per block it fetches the BF16 bytes of both pins (memory only, one tensor at a
  time), checks them against #68's hashes, runs `wb_int.py`'s matrix rule (imported unchanged) and adds
  two fields to the #91 leaf object: `e` (the exponent) and `int_sha256` (SHA-256 of the int16
  little-endian row-major integers). The tree over those 78 blocks gives a subset id (tag
  `fp-wb-conv-subset-v2`), which is NOT a model conversion id (that needs all 722 blocks).
  `verify_opening_v2` checks a v2 opening: v1 structure, `e` a plain int in [-64, 64], `int_sha256` 64
  lowercase hex, then path and id. Hash level, not a proof.
- `test_wb_leafv2.py`: 38 named checks on the leaf-v2 subset (honest, 15 kinds of mutation of the two
  new fields, 8 #100 mutation kinds on v2 leaves, opening-level). `run_leafv2.sh <outdir> [--reverse]`:
  the #149 run (fetch + convert, then tree and the suite twice).
- Reading leaf-v2 run files (added after review round 1 of PR #151, PREREG A-3 of the experiment).
  `wb_leafv2.load_records` is the one loader for a run directory's `blocks.jsonl`; `tree`, `compare`,
  `test_wb_leafv2.py` and the experiment's `summarise.py` all use it. It refuses (`EvidenceError`, exit
  status 2) a duplicate record for a block (an identical duplicate too), a name outside the registered
  78, a wrong kind, malformed fields, a derived flag that does not follow from the record's own fields
  or from #68's hash and shape, a record order that is not a prefix of the registered order or of its
  reverse, and a count or order that disagrees with `run-meta.json` **when present**. Without that
  file, recorded completion and direction are unchecked; an accepted prefix is not evidence that
  a run stopped under its registration. Complete metadata-free input may still report H3 `PASS`.
  **Known blocking finding (issue #189, 2026-11-14): H3 `PASS` is not evidence of provenance.** The
  summary reports H3 on the union of run 2 and run 3, and no record says which run produced it. A
  metadata-free run 3 that was reordered into forward order and cut to 70 or more lines, or whose
  records are run 1's, gets a full `PASS`; so does a forward cut with metadata edited to agree. The
  coverage is real (run 2 supplies the missing blocks) and no hash match is false; what cannot be
  checked is that run 3 is a complete, independent, registered run. Not fixed here. See the dated
  limits addenda of [2026-11-13](../../experiments/20261112-149-leaf-v2/RESULTS.md#limits-addendum-2026-11-13-missing-metadata-issue-189)
  and [2026-11-14](../../experiments/20261112-149-leaf-v2/RESULTS.md#limits-addendum-2026-11-14-the-issue-189-stop-rule-fired-blocking-finding).
  **Registered mode (issue #203, opt-in; experiment `20261114-203-leafv2-registered-pin`).**
  `compare ... --registered` and `summarise.py --registered` first check every registered run directory
  (and, for the summary, both compare files) against the committed pin
  `experiments/20261112-149-leaf-v2/runs/registered-pins.json`: a missing, extra-consumed, symlinked or
  changed `blocks.jsonl` / `run-meta.json` / `leaves-v2.json`, a symlinked or renamed run directory, or
  an absent pin is refused (exit 2). The registered summary adds `h3.overall.basis` (`single-run` or
  `union`); a union that reaches 78 blocks with no single run doing so is `PASS-UNION`, not `PASS`. All
  23 #191 stop-rule cases are refused in registered mode; the committed runs give `PASS` with basis
  `single-run` (`runs/summary-registered.json`). **The pin is a committed list that binds "registered
  run" to what the repository holds. It is not authentication:** whoever can change the repository can
  change the pin together with a run (defeat case D2 then gives a full `PASS`), and files the readers do
  not consume are not checked. **The default mode is unchanged:** without `--registered` the 13 full-`PASS`
  inputs of the #189 finding still give `PASS`, so the #189 stop rule is answered only for evidence read
  in registered mode against the registered runs, not in general.
  **Read once (PREREG amendments A-1 / A-2 of that experiment, after review round 1 of PR #205).** In
  registered mode each pinned file is read exactly once; the SHA-256 is taken over those bytes and the
  same bytes are parsed, and no pinned path is opened, stat'ed or listed again. A registered result is
  therefore a statement about bytes with the pinned hash at the moment they were read, not about what
  the directory holds afterwards; the symlink and file-type checks made by path before the read can
  still be raced. `compare` refuses (exit 2, `USAGE:`) a missing output path, a path that starts with
  `--` and any other argument than `--registered`; `summarise.py` refuses unknown arguments. Valid
  invocations are unchanged.
  `load_leaves` accepts a stored
  `leaves-v2.json` only if it is byte for byte the tree rebuilt from those records. `compare` compares
  the canonical leaf-v2 JSON per block and pin and the fetched-bytes hash, computes root and id equality
  on rebuilt trees, and writes a `status`: `identical-complete`, `identical-partial` (a run that
  covers fewer blocks, such as run 2), `no-common-blocks` or `mismatch` (exit status 1). What this
  does not do: it cannot check `e` or `int_sha256` against the weights (that needs the bytes), so a
  record altered consistently is accepted as a record and shows up only as a difference from another run.
- `test_wb_leafv2_evidence.py`: regression expectations on altered temporary copies of the
  committed #149 run files (duplicates, altered or truncated stored trees, dropped or reordered
  records, swapped payloads, flipped flags, edited compare files, and optional metadata). Each of
  `compare`, the hostile suite and `summarise.py` must produce the specified refusal or coverage result;
  the unaltered files must pass. The complete metadata-free control also passes; the metadata-free cut
  of run 3's last line in its original order gives H3 `PASS-SUBSET`. The 18 cases named
  `stop-rule-189-*` pin the current outcome of the issue #189 finding, including 13 altered copies of
  run 3 that get a full H3 `PASS`: they record present behaviour as a known blocking finding, not a
  contract, and a registered reader change is expected to change them. No network, no weights. It
  tests readers, not conversion. Issue #203: in those 18 cases the summary expectation is now
  `summarise.py --registered`, refused; the unchanged default-mode outcome is kept next to it as
  `pin203-default-mode-limit-*`. Cases `pin203-*` replay all 23 #191 cases in registered mode and try
  to defeat the pin (D1 to D12 in that experiment's PREREG). Cases `pin203-r2-*` (amendments A-1 / A-2)
  change a pinned file just before its one read (refused), swap run 3 after the last read (the result is
  that of the registered bytes; the next reading is refused), and give the two command lines a missing
  output path or an unknown flag (exit 2).

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
norm-folded tensors at integer level; 64 of the 70 changed tensors at integer level (in these original
files; leaf v2 below converts all 70 and 8 controls); the protocol's
field; the evaluation responses of DESIGN 2.0 (designed, not built). The conversion id and the
config pin (A12) are built (`wb_conv.py`) but only at hash level, with these limits: the v1 leaf has no
exponent e_b or integer hash int_sha256_b (the full tree needs the 55.6 GB conversion per pin; leaf v2
adds them for 78 blocks only); the rule steps
are bound as text and no converter here runs them on real bytes; the folded constant c = 1.0 is a
placeholder; which config fields change the function is a judgement (fail closed on unknown keys,
but the known-unpinned list in `wb_conv.py` is a choice); only one model variant is supported; nothing
binds the committed table to the conversion id inside a proof. The 333 visual and 15 MTP tensors are in the H1 id but outside U1 scope; any Fiat-Shamir or
grinding security bound (DESIGN 2.0 states only the fixed-pair Schwartz-Zippel bound). The
verifier raises an exception, rather than returning false, on some malformed inputs (n = 2^64,
a tensor name with an unpaired surrogate), and compares the held id case-sensitively. See
RESULTS.md "What is established and what is not".

Leaf-v2 run files carry no provenance the readers can check: an H3 `PASS` shows that the supplied
records agree with run 1 and together cover the 78 blocks, not that an independent complete run took
place (issue #189 stop-rule finding, see above). Registered mode (issue #203) adds a check against a
committed pin of the registered runs' file hashes; that binds the files to the repository's history and
is not authentication of how they were produced.

Leaf v2 (`wb_leafv2.py`, issue #149) covers only the 78 registered `matrix_plain` blocks; the
norm-folded matrices, the embedding, lm_head and the weight cells have no `e` / `int_sha256` yet, and
the subset id is not a conversion id for the model. It binds which integers the rule produces from the
pinned bytes; it does not bind a commitment or a proof to them.

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

Conversion leaf v2 (issue #149). CPU, network: fetches 9.41 GB (8.76 GiB) per pin by range request
(memory only, about 2.2 GB peak RSS), about 15 minutes on the shared host. Write into a fresh directory:

```sh
O=$(mktemp -d)
bash research/weight-binding/run_leafv2.sh "$O"            # registered order; --reverse for runs 2 and 3
cmp "$O/leaves-v2.json" experiments/20261112-149-leaf-v2/runs/run1/leaves-v2.json   # expect no output
cmp "$O/tests-1.json" experiments/20261112-149-leaf-v2/runs/run1/tests-1.json
python3 research/weight-binding/wb_leafv2.py compare "$O" experiments/20261112-149-leaf-v2/runs/run1 "$O/compare.json"   # exit 0, status identical-complete
```

Leaf v2 from the committed run files only (no network, no weights, seconds to about half a minute):

```sh
O=$(mktemp -d)
E=experiments/20261112-149-leaf-v2
python3 research/weight-binding/test_wb_leafv2.py $E/runs/run1 "$O/tests.json"      # 38 / 38, exit 0
cmp "$O/tests.json" $E/runs/run1/tests-1.json                                        # expect no output
python3 research/weight-binding/wb_leafv2.py compare $E/runs/run1 $E/runs/run3 "$O/compare.json"   # exit 0
python3 $E/summarise.py --check                                                      # exit 0: runs/summary.json is current
python3 $E/summarise.py --registered --check                                         # exit 0: runs/summary-registered.json is current
python3 research/weight-binding/wb_leafv2.py compare $E/runs/run1 $E/runs/run3 "$O/c.json" --registered   # exit 0
python3 experiments/20261114-203-leafv2-registered-pin/make_pins.py --check           # exit 0: the pin is the regeneration
python3 research/weight-binding/test_wb_leafv2_evidence.py "$O/evidence.json"        # 361 / 361, exit 0
cmp "$O/evidence.json" experiments/20261114-203-leafv2-registered-pin/runs/evidence-tests-r2-1.json
```

The current receipt is `experiments/20261114-203-leafv2-registered-pin/runs/evidence-tests-r2-1.json`
(361 expectations over 145 cases; `-r2-2.json` is a second run, byte-identical). It belongs to the code
after PREREG amendments A-1 / A-2 of issue #203. `runs/evidence-tests-1.json` and `-2.json` in the same
directory (346 expectations over 136 cases) belong to the code before those amendments and stay as
committed; all 346 are present unchanged in the current receipt. The paragraph below describes the #191
receipt, which also stays as committed.

The current receipt includes the issue #189 metadata-boundary cases and the 18 stop-rule cases (231
expectations over 82 cases). Exit 0 there means the suite saw the outcomes it pins, including the
full-`PASS` outcomes of the stop-rule finding; it does not mean the reader refuses altered evidence.
The older receipts remain unchanged and describe the earlier suites:
`experiments/20261113-189-missing-metadata/runs/evidence-tests.json` (177 expectations) and
`runs-fix151/evidence-tests.json` (162). Receipts quote
refusal messages, some from Python's JSON decoder, so other Python versions may word them differently.
The suite asserts expectations and exit status; see the [follow-up reproduction guide](../../experiments/20261113-189-missing-metadata/README.md)
for the two independent fixture runners, measurements and limitations.

The first-run files in `experiments/20261111-91-conversion-id/runs/` were made by the v1 code at
d39c98dc and are not reproduced by the current code (the config pin changed, so the ids did).

Note: the commands for `runs/` above reproduce the original files, but the original H1 outputs and
`counted.json` were written before their scripts were committed (RESULTS deviations 4, 5); the
reproduction from committed code is `runs-rerun-pr87/`.

`run_registered.sh` was run through the host's heavy-job gate and pinned with `taskset -c 6-11`
(it calls taskset itself). The H1 outputs are deterministic. H2/H3 outputs are deterministic
except the fetch and fingerprint times.
