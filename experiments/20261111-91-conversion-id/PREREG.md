# PREREG: 20261111-91-conversion-id
Issue: #91 (part of #36). Lane: wb91b. Date (UTC): 2026-11-11 01:35. Base commit: 1ef75fd3 (origin/main).

Builds three pieces that PR #87 (`research/weight-binding/DESIGN.md` sections 2.0, 2.3, 2.4, 3 A12, 5) left as design only: the conversion id (object 2 of DESIGN 2.0), the config pin inside it (attack A12), and a count of the table-side cost of the key-file claim over the 722 effective text blocks. CPU only. Everything here is hash-level bookkeeping and counting. **None of it is a proof**, no `cp_commit` / `cp_prove` / `cp_verify` is run, and no soundness or Fiat-Shamir figure is claimed beyond the fixed-pair bound #87 states.

Pinned checkpoints (from #68, unchanged): stock `Qwen/Qwen3.8-27B` at `37561816e66b5b9153b1b64c10968c18c1e6f4a0`; abliterated `huihui-ai/Huihui-Qwen3.8-27B-abliterated` at `739e3c5b89849f6c238ce1e5b70008612ae42cdd`. Inputs: #68's `runs/stream-{stock,abl}.json` (per-tensor name, dtype, shape, sha256) and each pin's `config.json` fetched at the pinned revision (a few KB, hashed and committed).

## Hypothesis
- **H1 (conversion id, rules bound).** A conversion id built in the DESIGN 2.0 order (checkpoint id -> rule version -> config pin -> one leaf per effective block carrying block name, ordered source leaf names with their checkpoint-leaf hashes, tensor class, rule step string and parameters) is deterministic, differs between the stock and abliterated pins, and changes when any single element of any leaf is mutated: for each of the 8 effective/folded tensor classes (plain matrix, matrix with a folded (1 + w) norm, lm_head with the final norm folded in, conv1d taps direct, gated-norm gain with sqrt(128), cA = RNE(2^e exp(A_log)), dt_bias at 2^F, q/k norm gains) a mutated-rule negative test (wrong rule step, gain form g instead of 1 + w, missing or reordered source leaf, wrong source hash) makes a verifier holding the honest id refuse.
- **H2 (config pin, A12).** The config pin (SHA-256 of a canonical encoding of the function-changing `config.json` fields) is in the conversion id; changing any one pinned field (layer-type schedule, rms_norm_eps, rope theta, head counts, conv kernel width, hidden size, vocab size) with the tensors unchanged changes the id and the verifier refuses.
- **H3 (inventory in code).** The builder refuses unless the 851 text source tensors split exactly as 498 matrices + 224 weight-cell tensors + 129 folded norms (722 effective blocks), and every folded norm is named as a source by at least one block. A dropped, extra or reclassified tensor makes the build raise.
- **H4 (reproducible).** Building both pins' conversion ids twice from committed inputs gives byte-identical manifest JSON and the same ids.
- **H5 (count, table side).** The table-side cost of the key-file claim (one MLE evaluation per effective block at a derived point, DESIGN 2.0 object 3) is counted from the 722 blocks' shapes by a committed script: total elements, total padded elements (sum of 2^ceil(log2 n_b)), sum of variables, and field multiplications for the direct fold evaluation (one multiply per pair per round, about sum of padded n_b). Reported as a count, not a measurement.

## Metric
- H1, H2: number of hostile cases refused out of number constructed (per class, per field); stock id != abliterated id; honest rebuild accepted.
- H3: builder raises on every injected inventory error (drop one tensor of each kind, add one unknown name, reclassify one).
- H4: SHA-256 of the two builds' output files equal, per pin.
- H5: the counts above, integers, plus the counting script path. Deterministic, n = 1 (a count has no variance).

## Acceptance threshold
- H1: 100% of hostile cases refused, at least one per tensor class (8 classes) and at least 4 mutation kinds; honest rebuild accepted for both pins; stock != abliterated.
- H2: 100% of single-field config mutations refused, at least 7 fields.
- H3: 100% of injected inventory errors raise; honest inventory is exactly 851 = 498 + 224 + 129.
- H4: byte-identical rebuilds for both pins.
- H5: script committed and its output committed; any number cited appears in a committed run file.
A miss on any of these is reported as FAIL for that hypothesis.

## Kill criterion
Deadline 2026-11-11T03:55Z. Stop at the deadline with whatever is built; unbuilt items are listed as open in RESULTS.md. If the pinned `config.json` cannot be fetched (gated / 401 / 403), H2 is evaluated on the field set from #68's layout and stated as such, not with fetched configs. If #68's inventory does not reproduce 851 = 498 + 224 + 129, H3 is FAIL and the discrepancy reported.

## Runs
Deterministic code, so variance is not meaningful: H1 to H4 are unit tests run once (and the whole suite rerun once to show it repeats); H4 builds each pin twice. H5 is a count, n = 1. No seeds (all points and ids are hashes). Nothing excluded.

## Prior art
- Model identity by file hash (Hugging Face revision sha, safetensors shard sha256) and signed manifests (#59 here; Sigstore model signing / OpenSSF model-signing spec, which hashes files or file chunks): these bind bytes, not the integer model a proof uses, and not the config. #68 showed all 18 shard hashes differ while 1,129 tensors are equal.
- zkML systems that commit weights: EZKL (weights as circuit constants or hashed params, quantization done by its own calibration, the scale settings are in the circuit settings file), zkLLM (Sun et al. 2024, tlookup / zkAttn, commits quantized weights with a Pedersen-style commitment, quantization rule outside the statement), Jolt / Expander (generic provers, no model-level identity). None of these, to our reading, binds a per-tensor float-to-integer conversion rule (including non-linear derived cells like exp(A_log) and folded norm gains with a (1 + w) form) and an architecture config into a public, CPU-recomputable id that a verifier holds before the commitment exists.
- TEE attestation (H100 CC, TDX / SEV-SNP; Phala, Atoma, Nillion) measures the loaded code and sometimes the weight files' hashes, again bytes rather than the converted integers.
- New here: the conversion id of #87 DESIGN 2.0 object 2 as code, with per-class rule steps and the config pin as leaves, hostile tests per class, and the inventory enforced in code. Not new: Merkle trees, SHA-256 domain separation, MLE evaluation by folding.

## Amendments

### 2026-11-11 03:25 UTC: review fixes (PR #100 reviews by astra and opus at 29d8b5f3)
Written after the original code and runs, before any code change below. The original registration above, the code at d39c98dc and the run files in `runs/` stay as they are; the corrected code is a new commit and its receipts go to a new directory `runs-fix100/`.

**Registration note (protocol deviation of the original run).** ENV.json records one stock build to /tmp and one full test-suite run on the working tree before code commit d39c98dc, on the registered inputs. LANE-COMMON-1109 forbids running the registered suite before its registered run, and this PREREG did not name a separate debug fixture. Those runs were exploratory/debug; their outputs were not committed, and the committed `runs/` files were written by `run_wb91.sh` after d39c98dc. It is reported as a deviation in RESULTS.md and the PR body.

**Findings being fixed (all reproduced against 29d8b5f3 by this lane, with a lane script outside the repo, before any change):**
1. Top-level `tie_word_embeddings` is not pinned (only `text_config` is read); `true` with unchanged tensors verifies under the stock id.
2. The config encoding is not injective: a float is encoded as `{"f64": hex}` and the same object is accepted as input, so `rms_norm_eps` or `partial_rotary_factor` replaced by that object verify under the stock id.
3. `text_config.attention_bias` is not pinned; `true` verifies under the stock id.
4. A config without `text_config` (fields hoisted to the top level) verifies under the stock id (`cfg.get("text_config", cfg)` fallback).

**Changes (code, after this amendment):**
- Config pin v2 (`fp-wb-config-v2`): a strict schema runs before hashing. `text_config` must be present (no fallback). Every pinned field has a fixed JSON type (int never bool, float finite, `rope_parameters` an object with an exact key set); anything else raises ConfigError. Unknown keys in `text_config` or at the top level raise ConfigError (fail closed); the known keys left out of the pin are listed in code with the reason. The pin encoding is a typed tag per value (each value becomes [type tag, payload]), injective by construction, and the schema rejects the old `{"f64": ...}` shape where a float is expected.
- Pinned in addition: top-level `tie_word_embeddings`, `model_type`, `architectures`; `text_config.attention_bias`, `text_config.model_type`. Unsupported values fail closed: top-level and `text_config` `tie_word_embeddings` must both be false (they must agree; the converter has a separate lm_head block), `attention_bias` must be false (the inventory has no projection biases), `rope_parameters.partial_rotary_factor` must equal `text_config.partial_rotary_factor`.
- Leaf encoding unchanged for honest leaves (so the block leaves and the root do not change). The leaf canonicaliser now refuses floats and non-string keys, `leaf_well_formed` checks each class's parameter key set and the `norm_role` value, and a malformed opening returns False instead of raising.
- The conversion id changes because the config pin changes. Old and new ids are both reported.

**Corrected-code run (registered now).** After the code commit: `bash research/weight-binding/run_wb91.sh experiments/20261111-91-conversion-id/runs-fix100` (2 builds per pin, the full suite twice, the count). Acceptance: every new hostile config case refused (top-level `tie_word_embeddings` true; top-level and text values disagreeing; `rms_norm_eps`, `partial_rotary_factor` and the nested `rope_parameters.partial_rotary_factor` given as `{"f64": hex}` aliases; `attention_bias` true; `text_config` removed with the fields hoisted; an unknown text key; an int given as bool / float), all original tests still pass, byte-identical rebuilds, and the count numbers unchanged (the count depends on shapes only). Any failure is reported as such.

**Debugging fixture (not the registered suite).** Before the code commit, the new schema and canonical encoding are debugged only on a synthetic 4-layer config written by the lane (not either pinned config.json and not #68's stream files), calling the schema/pin functions directly. No `Conversion` build and no `test_wb_conv.py` run before the code commit.
