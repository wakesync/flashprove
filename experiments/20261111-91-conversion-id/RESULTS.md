# RESULTS: 20261111-91-conversion-id (issue #91, part of #36)

Hash-level bookkeeping and counting on CPU. **Not a proof.** No `cp_commit` / `cp_prove` / `cp_verify`, no weight read, no GPU. No soundness or Fiat-Shamir figure beyond the fixed-pair bound PR #87 states. Measured, unreplicated.

Code: `research/weight-binding/wb_conv.py` (conversion id), `test_wb_conv.py` (named tests), `wb_keyfile_count.py` (count), `run_wb91.sh` (the run). First run at d39c98dc (committed before the run, ENV.json), raw output `runs/`. **After review (PR #100), the config pin was found incomplete and non-injective; corrected code 49d10b0, corrected run `runs-fix100/` (ENV-fix100.json), section "Corrected run" below. The conversion ids in force are the corrected ones.**

## Corrected run (PR #100 review fixes, PREREG amendment 2026-11-11)

Both reviews at 29d8b5f3 found same-tensor config changes that verified under the honest stock id. This lane reproduced each one before changing code:
- top-level `tie_word_embeddings` true (opus must-fix 1; only `text_config` was read);
- `rms_norm_eps`, `partial_rotary_factor` and the nested `rope_parameters.partial_rotary_factor` replaced by the object `{"f64": hex}` of the same value (astra must-fix 1; the v1 encoding turned floats into exactly that object and accepted it as input);
- `text_config.attention_bias` true (astra must-fix 2; HF builds q/k/v/o bias parameters the checkpoint does not have);
- `text_config` removed and its fields hoisted to the top level (opus nonblocking; `cfg.get("text_config", cfg)` fallback).

So the first run's H2 PASS (12 of 12) was right for the 12 cases tested, but the pin did not cover every function-changing field, and the threshold's intent (any single function-changing change refused) was not met. The fix is config pin v2 (`wb_conv.py` `config_fields`, `config_pin`):
- strict schema before hashing: `text_config` required; 24 `text_config` fields and 3 top-level fields (`architectures`, `model_type`, `tie_word_embeddings`) pinned, each with a fixed type (int never bool, finite float only, `rope_parameters` an exact 5-key object); any key outside pinned + a listed known-unpinned set refuses (fail closed); the known-unpinned keys are listed in code with the reason;
- supported values only: both `tie_word_embeddings` false (so top-level and `text_config` must agree, and tied embeddings are refused, since the converter has a separate lm_head block), `attention_bias` false, the two `partial_rotary_factor` copies equal, `model_type`s and `architectures` the Qwen3.5 ones;
- the pin hashes a typed tree (`fp-wb-config-v2`): each value becomes [type tag, payload], so 1, 1.0, true and a float vs any object all encode differently;
- the leaf canonicaliser refuses floats and non-string keys (honest leaves carry none, so leaf bytes are unchanged); `leaf_well_formed` now checks each class's parameter key set and `norm_role`; a malformed opening (e.g. `leaf.cls = []`) returns False instead of raising.

| check (corrected run, `runs-fix100/`) | result | file |
|---|---|---|
| new same-tensor config cases refused | **26 of 26** A12-fix tests pass: 21 same-tensor config cases refused, namely the reproduced findings (6 cases: top-level tie, the three `{f64}` aliases, attention_bias, hoisted text_config), both / text-only `tie_word_embeddings` true, top-level flag removed, `attention_bias` removed, rope prf disagreeing, extra rope key, `mrope_section` permuted, unknown text and top-level keys, bool for int, float for int, NaN eps, other `model_type` / `architectures` / text `model_type`; plus the vision-config change accepted (out of U1 scope) and 4 encoding unit checks | `runs-fix100/tests-1.json` (group `A12-fix`) |
| original suite | all 98 original tests still pass (one label corrected: "head_dim 128" -> "head_dim 256") | `runs-fix100/tests-1.json` |
| opening robustness | 4 new opening tests pass (lm_head relabelled `matrix_norm_folded` now not well formed, extra param key, `cls = []` and a float param return False) | `runs-fix100/tests-1.json` |
| total | **128 / 128 PASS**, twice, identical JSON | `runs-fix100/tests-{1,2}.json` |
| byte-identical rebuild | stock 5b0ee1d6... twice, abliterated 73fa0446... twice | `runs-fix100/build-sha256.txt` |
| count (H5) | unchanged (depends on shapes only): 26,895,337,984 integers, 38,414,602,240 padded, 38,414,601,518 fold mults | `runs-fix100/keyfile-count.json` |

**Conversion ids changed** (only the config pin changed; checkpoint ids, all 722 leaves and the Merkle root are identical to the first run):
- config pin (both pins, same config.json): 9d132dae... (v1) -> dad1aa0120b86537c1a966518e711299a3f0447f8312b6a763075efe168c25f3 (v2);
- stock: 43a318967b61eb06fb447bfca66b0924e994f66c5c6cf7568416607e138f2dba -> **8df5699dfba60657fccecb4bc96bc80c135c46cd9fd367e06c95c3e5aaf6927f**;
- abliterated: 8ff69e08a512b32f940bf7145c686b933c80b1b1ad685350e11dd3e343525f8a -> **3682c94c48022fd93db78631c3510dca3e6901087eaca3dda2d88e87c14a7ac1**.

**Which mechanism refuses each of the 12 original A12 cases** (`runs-fix100/tests-1.json` key `a12_mechanism`; opus review nonblocking): 6 build and are refused by the pin alone (rms_norm_eps, rope_theta, hidden_act, full_attention_interval, mamba_ssm_dtype, output_gate_type); 4 by the shape check (num_attention_heads, num_key_value_heads, linear_conv_kernel_dim, attn_output_gate); 1 by the inventory (layer_types swap); and partial_rotary_factor alone is now refused by the schema (its rope copy disagrees; changing both copies changes the pin). In all 11 cases that pass the schema, the pin also changes.

## Verdict per hypothesis (first run, `runs/`, code d39c98dc; superseded for H2 by the corrected run above)

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
2. **The rule strings are descriptions, not executable code.** The id binds which rule text is used; no converter here implements STEP_FOLDED with g = RN32(1 + w), STEP_CA, STEP_GATED, STEP_QK or STEP_DT on real bytes. In particular the binary32 order of (1 + w) and the binary64 (RN64) exp for cA are fixed in the text only. `weight_sums.py` still multiplies g as stored.
3. The folded constant c is 1.0 here (`c_f32` = 3f800000) as a placeholder: whether Qwen needs a sqrt(width) or attention-scale constant like the Maverick rule (`NORM_CONSTANT`, `QUERY_CONSTANT`) is open and would change the id.
4. Which config fields are function-changing is still a judgement, but since the corrected run it fails closed: 24 text + 3 top-level fields are pinned with types, and any key not in the pinned or the listed known-unpinned set refuses. Known-unpinned (reason in `wb_conv.py`): `max_position_embeddings`, `use_cache`, `attention_dropout`, `initializer_range`, `dtype`, token ids, the MTP fields, the vision config and vision token ids, `language_model_only`, `transformers_version`. The vision config and MTP fields are out of U1 scope (as #87); their tensors are still under the checkpoint id. Only one variant is supported (untied embeddings, no attention bias); another variant needs its own inventory, not just a different pin.
5. The dt_bias class and F = 12 are the #70 candidate values; a different F gives a different id by design.
6. No proof binds the committed table to this id; the key-file claim, the point derivation from the commitment ID and its Fiat-Shamir analysis remain as #87 left them.
7. The count assumes flat padding per block; a row x column layout or the 11.5 placement could pad differently.

## Deviations
- PREREG lists 8 classes; the code has 9 because the embedding (four-digit unit, eres) is its own class. All 8 registered classes are covered.
- H2 lists 7 example fields; 12 were tested.
- **Debug run of the registered suite before the registered run (protocol deviation, disclosed after review).** One stock build to /tmp and one full test-suite run on the working tree, on the registered inputs, happened before code commit d39c98dc (ENV.json `runs.debug_before_run`). LANE-COMMON-1109 forbids that and the PREREG named no separate debug fixture. Outputs were not committed; the committed `runs/` files were all written by `run_wb91.sh` after d39c98dc. The checks are deterministic hashes, so no number depends on it, but it is a deviation. Registration note: PREREG `## Amendments` 2026-11-11.
- **Config pin incomplete in the first run** (PR #100 reviews): see "Corrected run". Fixed after a dated PREREG amendment (5a58a27), code 49d10b0, new receipts in `runs-fix100/` (the first run's files are unchanged). The conversion ids changed.
- The amendment heading says 03:25 UTC; it was committed at 03:21 UTC, before the code commit (03:25 UTC). The order (amendment, code, run) is what the git history shows.
- For the corrected run, debugging used only a synthetic 4-layer config written by the lane, calling the schema / pin functions (as the amendment registers); no build or suite run on the registered inputs before 49d10b0.
