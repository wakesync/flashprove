# RESULTS: 20261111-91-conversion-id (issue #91, part of #36)

Hash-level bookkeeping and counting on CPU. **Not a proof.** No `cp_commit` / `cp_prove` / `cp_verify`, no weight read, no GPU. No soundness or Fiat-Shamir figure beyond the fixed-pair bound PR #87 states. Measured, unreplicated.

Code: `research/weight-binding/wb_conv.py` (conversion id), `test_wb_conv.py` (98 named tests), `wb_keyfile_count.py` (count), `run_wb91.sh` (the run). Run at d39c98dc (committed before the run, ENV.json). Raw output: `runs/`.

## Verdict per hypothesis

| H | threshold | result | file |
|---|---|---|---|
| H1 conversion id, per-class rules bound | 100% of hostile cases refused, >= 1 per class (8), >= 4 mutation kinds; honest accepted; stock != abliterated | **PASS**: 9 block classes (the 8 registered plus the embedding split out) x 4 generic mutations = 36 refused, plus 17 class-specific mutations refused (gain form g vs 1 + w, norm source dropped / reordered / swapped, final norm replaced by layer 63's input norm, cA map exp -> identity and binary64 -> binary32, dt_bias F and class bound, sqrt(128) dropped, q/k gain 1 + v -> v, conv kernel, embedding eres), plus 7 opening-level mutations; all 722 honest stock openings verify; stock id 43a31896... != abliterated id 8ff69e08...; the abliterated opening is refused under the stock id for each of the 70 blocks that read one of the 70 changed source tensors | `runs/tests-1.json`, `runs/tests-1.log` |
| H2 config pin (A12) | 100% of single-field changes refused, >= 7 fields | **PASS**: 12 of 12 single-field changes refused with the tensors unchanged (layer schedule, rms_norm_eps, rope_theta, partial_rotary_factor, attention heads, KV heads, conv kernel, hidden_act, full_attention_interval, attn_output_gate, mamba_ssm_dtype, output_gate_type); a missing pinned field refused; 22 fields pinned | `runs/tests-1.json` |
| H3 inventory in code | every injected error raises; honest = 851 = 498 + 224 + 129 | **PASS**: honest inventory {text 851, matrix 498, cell 224, folded_norm 129, effective 722}; 11 of 11 injected errors raise (drop a matrix / cell / folded norm / q-norm / lm_head / embedding, unknown extra tensor, attention tensor in a DeltaNet layer, a layer-64 tensor, a shape change, an expected table off by one) | `runs/tests-1.json` |
| H4 byte-identical rebuild | identical bytes per pin | **PASS**: two builds per pin, sha256 stock c39b9aa1... twice, abliterated 270a90b2... twice; the test suite run twice gives identical JSON | `runs/build-sha256.txt`, `runs/tests-{1,2}.json` |
| H5 key-file table count | script + output committed | **done (counted)**: below | `runs/keyfile-count.json` |

## H5: table-side cost of the key-file claim (counted from shapes)

One multilinear evaluation per effective text block at a derived point (DESIGN 2.0 object 3), 722 blocks, each block padded flat to 2^ceil(log2 n_b):

- committed integers: **26,895,337,984** (equal to the #70 count DESIGN 5 cites, an independent cross-check of the 722-block inventory);
- padded entries: 38,414,602,240 (**42.8%** padding overhead, mostly from blocks just above a power of two: the embedding and lm_head are each 1,271,398,400 integers padded to 2^31, 68.9%);
- point coordinates to derive: 14,110 (one hash each);
- field multiplications, fold evaluation (2^v_b - 1 per block): **38,414,601,518**; the eq-table route is 76,829,203,758. A fold that skips the zero padding needs about the integer count instead (26.9 G); not implemented, so not claimed;
- per class: matrices with a folded norm 368 blocks, 23.4 G fold mults; plain matrices 128 blocks, 10.7 G; embedding 2.15 G; lm_head 2.15 G; the 224 weight-cell tensors together 3.17 M (0.008% of the total). The cells are negligible; the cost is the 498 matrices.
- the 851-source-tensor count of the first #87 version: 38,415,659,008 padded entries, so the 129 folded norms are 1.06 M padded entries; the 722 vs 851 distinction matters for the leaf count, not for the cost.

This is the cost of the evaluation itself (what a verifier recomputing y_b from open weights, or the prover, does). The proof-side cost of opening the batched claim against the committed table depends on the commitment scheme and is **not counted**.

## What is and is not established

Established (hash level, measured unreplicated): a conversion id in the DESIGN 2.0 order whose leaves bind, per effective block, the class, the ordered source leaves (as checkpoint-leaf hashes) and the rule step with its parameters; the config pin inside it; the 851 = 498 + 224 + 129 split enforced by the builder against the pinned config's layer schedule and shapes; byte-identical rebuilds of both pins.

Not established / open:
1. **e_b and int_sha256_b are not in the leaf** (DESIGN 2.0 lists them). They need the 55.6 GB per pin converted; leaf v1 binds them only indirectly (source hashes + rule). A leaf v2 with them is the next step.
2. **The rule strings are descriptions, not executable code.** The id binds which rule text is used; no converter here implements STEP_FOLDED with g = RN32(1 + w), STEP_CA, STEP_GATED, STEP_QK or STEP_DT on real bytes. In particular the binary32 order of (1 + w) and the RN32 of exp for cA are fixed in the text only. `weight_sums.py` still multiplies g as stored.
3. The folded constant c is 1.0 here (`c_f32` = 3f800000) as a placeholder: whether Qwen needs a sqrt(width) or attention-scale constant like the Maverick rule (`NORM_CONSTANT`, `QUERY_CONSTANT`) is open and would change the id.
4. Which config fields are function-changing is a judgement (22 pinned; e.g. `max_position_embeddings`, `use_cache`, token ids are not). The vision config and MTP fields are not in the pin (visual / MTP out of U1 scope, as #87); visual / MTP tensors are still under the checkpoint id.
5. The dt_bias class and F = 12 are the #70 candidate values; a different F gives a different id by design.
6. No proof binds the committed table to this id; the key-file claim, the point derivation from the commitment ID and its Fiat-Shamir analysis remain as #87 left them.
7. The count assumes flat padding per block; a row x column layout or the 11.5 placement could pad differently.

## Deviations
- PREREG lists 8 classes; the code has 9 because the embedding (four-digit unit, eres) is its own class. All 8 registered classes are covered.
- H2 lists 7 example fields; 12 were tested.
