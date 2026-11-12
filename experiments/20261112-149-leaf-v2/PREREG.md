# PREREG: 20261112-149-leaf-v2
Issue: #149 (part of #36, tracking #32). Lane: leafv2149. Date (UTC): 2026-11-12 22:10. Base commit: d247f4c01edc20f7317e587cc1b27ba4ae61ceae (origin/main).

Conversion leaf v2 on real bytes, restricted to the 70 tensors that differ between the two pins (PR #68 `experiments/20261109-8-qwen-real-weights/runs/diff.json`) plus 8 registered control tensors that are byte-identical across pins. CPU only, hash level, **not a proof**. No `cp_commit` / `cp_prove` / `cp_verify`, no GPU, no spend. Out of scope (issue #149): the other block classes (norm gains, folded norms, conv taps, cA, dt_bias), the full 722-block tree for a pin (55.6 GB per pin), any proof-side opening or key-file change, publishing integer hashes beyond this experiment's run files.

Pinned checkpoints (from #68, unchanged): stock `Qwen/Qwen3.8-27B` at `37561816e66b5b9153b1b64c10968c18c1e6f4a0`; abliterated `huihui-ai/Huihui-Qwen3.8-27B-abliterated` at `739e3c5b89849f6c238ce1e5b70008612ae42cdd`. Tensor offsets and expected hashes: #68 `runs/stream-{stock,abl}.json`. Config: #91 `experiments/20261111-91-conversion-id/runs/config-{stock,abl}.json`.

### Registered tensor set (78 blocks per pin)
Changed (70, all BF16, all class `matrix_plain` in `wb_conv.classify`): `model.language_model.layers.L.mlp.down_proj.weight` for L = 17..51 (35, shape 5120 x 17408); `linear_attn.out_proj.weight` for L in 17..51 with L mod 4 != 3 (26, shape 5120 x 6144); `self_attn.o_proj.weight` for L in {19, 23, 27, 31, 35, 39, 43, 47, 51} (9, shape 5120 x 6144). This is exactly the set with `same: false` in #68 `diff.json`; the runner reads it from that file and asserts the count 70 and the family split 35 / 26 / 9.

Controls (8, `same: true` in #68, the same three projection kinds in the two layers on each side of the changed band, so both linear-attention and full-attention layers are covered): layer 15 `mlp.down_proj`, `self_attn.o_proj`; layer 16 `linear_attn.out_proj`, `mlp.down_proj`; layer 52 `linear_attn.out_proj`, `mlp.down_proj`; layer 55 `mlp.down_proj`, `self_attn.o_proj` (layers 15 and 55 are full-attention, 16 and 52 linear-attention, per the pinned `layer_types`).

### Rule (unchanged code)
The executable matrix rule already on main, `research/weight-binding/wb_int.py` (`fetch`, `bf16_to_f32`, `to_int`, used unchanged by import): BF16 -> binary32 exactly; e = the largest exponent with RNE(2^e max|v|) <= 4,095 (`exponent_of`, the logic of `weight_sums/weight_sums.py`); w = RNE(2^e v) computed in binary64; int16. This is `wb_conv.STEP_MATRIX`, the step of class `matrix_plain`, which reads no norm. The runner asserts, via `wb_conv.classify` on the pinned config, that every one of the 78 blocks is `matrix_plain` with a single source (itself) before any byte is fetched.

int_sha256_b = SHA-256 of the int16 little-endian, row-major (C-order, shape as in the checkpoint) bytes of w. e_b = the integer exponent.

### Leaf v2
Leaf object v2 = the #91 leaf object (block, cls, sources with checkpoint-leaf hashes, rule step and params, built by `wb_conv.leaf_obj` unchanged) plus two fields: `"e": <int>` and `"int_sha256": <64 lowercase hex>`. Leaf hash `H(0x00 || "fp-wb-conv-leaf-v2" || len||canonical-json(leaf))` with #91's `_canon`; node hash as #91 with tag `fp-wb-conv-node-v2`; odd node promoted. Tree over the 78 blocks of a pin, sorted by name. Subset id `H("fp-wb-conv-subset-v2" || checkpoint id || len||rule version || config pin || n (8 LE) || root)`. The word "subset" is in the tag on purpose: this is not a conversion id for the model (that needs all 722 blocks).

## Hypothesis
- **H1 (inputs).** For all 156 fetched tensors (78 per pin) the SHA-256 of the fetched BF16 bytes equals #68's committed per-tensor hash.
- **H2 (pin separation).** For each of the 8 controls, e_b and int_sha256_b are identical across the two pins; for each of the 70 changed tensors, int_sha256_b differs across pins (#87 H2 predicts every changed tensor differs in integers), so the leaf v2 differs. e_b is reported per tensor; it is not required to differ.
- **H3 (determinism).** A second, independent run (fresh process, fresh fetch, reversed tensor order) gives byte-identical leaf objects (e_b, int_sha256_b) for every block it covers, and the same subset root and subset id per pin.
- **H4 (hostile leaves).** Holding the honest stock subset id, a verifier using the extended opening check refuses every hostile opening, including the two new fields: e_b off by +1 and -1, e_b as a string, e_b as a bool, e_b missing, int_sha256_b with one hex digit changed, int_sha256_b set to the other pin's value, int_sha256_b uppercase, int_sha256_b truncated, int_sha256_b missing, an extra leaf field; plus #100's existing mutation kinds applied to v2 leaves (rule step swap, rule param added, source hash changed, class changed) and opening-level mutations (config pin, rule version, checkpoint id, index, path element, extra path element, extra field). Every honest stock opening (78) verifies, and for each of the 70 changed blocks the abliterated leaf (with the stock path) is refused under the stock subset id.

## Metric
- H1: count of tensors whose fetched sha256 equals #68's, out of 156 (per run).
- H2: per tensor: e_b per pin, int_sha256_b per pin, count of differing int16 entries, fraction differing, max |delta| at the same index (when e_b agrees). Counts: controls with identical (e_b, int_sha256_b) out of 8; changed tensors with differing int_sha256_b out of 70.
- H3: count of blocks with byte-identical canonical leaf JSON across runs, out of the blocks run 2 covers; root and id equality per pin.
- H4: hostile openings refused out of constructed, per mutation kind; honest accepted out of 78.
- Also reported (not thresholded): fetch seconds and conversion seconds per tensor, peak RSS, free disk at start and end.

## Acceptance threshold
- H1: 156 / 156 in run 1 (and in run 2 for the tensors it covers).
- H2: 8 / 8 controls identical in both fields; 70 / 70 changed tensors with differing int_sha256_b.
- H3: 100% of the blocks covered by run 2 byte-identical, with run 2 covering all 78 blocks of both pins; if the time budget forces it, run 2 covers at least 10 blocks per pin, of which at least 2 are controls and at least 5 are changed blocks (run 2 goes in reversed order, so it starts at layer 55 and 52 controls and the high-layer changed blocks), and H3 is then reported as PASS on the covered subset only, with the reduced coverage stated.
- H4: 100% of hostile openings refused, at least 10 hostile kinds touching the two new fields; 78 / 78 honest accepted; 70 / 70 abliterated leaves refused under the stock id.
Any miss is FAIL for that hypothesis. A changed tensor with identical integers is the negative result the issue names (abliteration below the conversion's resolution) and is reported tensor by tensor.

## Kill criterion
Lane hard stop 2026-11-13T00:30Z. Run 1 budget: 50 min elapsed from the moment `fp-heavy.sh` grants the slot (logged). Run 2 budget: 40 min from its slot grant, and run 2 is not started after 2026-11-13T00:00Z. A run past its budget is stopped (by pid) and reported with what it completed; the remainder is listed as not run. Disk: the runner checks free space before every tensor and stops with a blocker if it is under 21 GB. A 401 / 403 from the hub stops the run (no credential search). If #68's hashes do not match, H1 is FAIL and that tensor is excluded from H2 (reported, not dropped silently).

## Runs
- Run 1: all 78 blocks x 2 pins, in the registered order (sorted name), one tensor in memory at a time per pin (stock fetched, hashed, converted, freed; then abliterated), via `fp-heavy.sh taskset -c 12-15`. One fetch stream at a time.
- Run 2: same code, fresh process, reversed order, all 78 x 2 if the budget allows (otherwise the subset rule above).
- The hostile suite (H4) runs twice on the run-1 output; the second run's JSON must be identical to the first.
- Determinism over n = 2 runs per tensor (78 tensors x 2 pins); the issue asks for two runs and the lane brief for at least 5 tensors repeated; this design repeats all 156 if run 2 completes. Hashes are deterministic, so median / SD are not meaningful; per-tensor timings are reported with n, median, min, max.
- No seeds (no randomness; all values are hashes and exact conversions).
- Debug before the registered runs: only on fixtures outside the registered set: synthetic arrays (as `wb_int.selftest`) and the stock `model.language_model.layers.0.linear_attn.out_proj.weight` (unchanged across pins, not in the registered 78) to exercise the fetch path. No registered tensor is fetched before run 1 and the hostile suite is not run on registered output before run 1 completes. Debug outputs are not committed.
- Nothing excluded except as the kill criterion states.

## Prior art
- Within this repo: #68 (per-tensor BF16 sha256 and the 70-tensor diff), #87 (`wb_int.py`: integer conversion of 6 changed tensors + 1 control, all 6 differ in integers), #91 / PR #100 (conversion id leaf v1: binds sources and the rule as text, not e_b or int_sha256_b; the hostile-leaf suite extended here).
- Model identity by file or chunk hash (Hugging Face revision sha, safetensors shard sha256, OpenSSF model-signing / Sigstore) binds the float bytes, not the integers a proof consumes.
- zkML weight commitments: EZKL (quantisation by its own calibration, scales in the settings file, weights committed as circuit params), zkLLM (Sun et al. 2024, commits quantised weights, quantisation outside the statement), Jolt / Expander (generic provers, no model identity). TEE attestation (H100 CC, TDX / SEV-SNP; Phala, Atoma, Nillion) measures file hashes. To our reading none of them publishes, per block, the conversion exponent and a hash of the converted integers inside an id that a CPU verifier can recompute from the public float checkpoint.
- New here: leaf v2 with e_b and int_sha256_b computed by an executable rule on real bytes for 78 blocks of each pin, the pin-separation check against #68's diff, a two-run determinism check, and hostile tests on the two new fields. Not new: Merkle trees, SHA-256, RNE quantisation.

## Amendments

### A-1, 2026-11-12 22:30 UTC (after run 1 and the stopped run 2; before any further fetch)
What happened: run 1 completed 78 / 78 blocks (slot 22:07:33Z, 891 s). Run 2 (slot 22:23:31Z, reversed) stopped itself after 8 blocks (4 controls, 4 changed) because host free disk fell below the registered 21 GB floor (20.42 GB at 22:24:54Z). The runner writes only kilobytes; the drop came from other work on the shared host and kept falling (18.7 GB at 22:28Z). Run 2's 8 blocks are below the H3 subset minimum of 10.
Registered now, nothing else changes: a run 3 with the same code and command (fresh process, reversed order, budget 2400 s from its slot grant), started only if free disk is at least 22 GB and the time is before 2026-11-13T00:00Z; the runner's per-tensor 21 GB floor stays. Run 3 starts again from the top of the reversed order, so it repeats run 2's 8 blocks (a third pass on those) before the rest. H3 is then evaluated on the union of blocks covered by run 2 and run 3, each compared with run 1 (any mismatch in either is FAIL). If the disk does not recover in time, H3 is reported on run 2's 8 blocks as BELOW the registered coverage (not PASS), with the reason. Run 1's committed files and run 2's files are not modified.
