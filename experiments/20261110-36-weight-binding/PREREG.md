# PREREG: 20261110-36-weight-binding
Issue: #36 (model identity). Agenda question Q2 (weight binding), use case U1 (model substitution). Lane: q2-weight-binding. Date (UTC): 2026-11-10 20:45. Base commit: 14bc10e395b248583509ae33da3e1ae65293bb6f (origin/main).

Inputs read before registration (all on main): PR #68 `experiments/20261109-8-qwen-real-weights/` (RESULTS sections 1 to 3, `runs/diff.json`, `runs/stream-{stock,abl}.json`, `runs/layout.json`); PR #59 `experiments/20261104-58-signed-manifest/RESULTS.md` and `tools/manifest/`; PR #70 `experiments/20261109-32-qwen-m3-design/DESIGN.md` sections 1, 3.1, 6.2, 10, 11; PR #67 `experiments/20261109-35-qwen-operators/RESULTS.md`; `docs/protocol.md` sections 4 to 6; `docs/format/11-5-weights-in-the-table.md`; `blocks/frame/heads.h` (`published_id`); `weight_sums/weight_sums.py` (conversion rule, `exponent_of`, `convert`).

What this experiment is: a design (in `research/weight-binding/DESIGN.md`) plus three small CPU checks. **None of the checks is a proof.** H1 is hash-level bookkeeping over data already on main. H2 and H3 are arithmetic on real tensors. No `cp_commit`, `cp_prove` or `cp_verify` run, no GPU.

Pinned checkpoints (from #68): stock `Qwen/Qwen3.8-27B` at `37561816e66b5b9153b1b64c10968c18c1e6f4a0`; abliterated `huihui-ai/Huihui-Qwen3.8-27B-abliterated` at `739e3c5b89849f6c238ce1e5b70008612ae42cdd`.

## Hypothesis
- **H1 (hash level, data on main).** A per-tensor manifest (one leaf per tensor: name, dtype, shape, sha256 of the tensor's bytes, from #68's streamed hashes) under a Merkle root gives a verifier-held model id per pin such that, with the stock id held: the abliterated manifest is refused as a whole; an opening of the abliterated leaf is refused for each of the 70 changed tensors; and an opening of the abliterated leaf is accepted for each of the 1,129 unchanged tensors (they are the same bytes, so no statement confined to them can tell the pins apart). The same holds with the abliterated id held.
- **H2 (integer level, real tensors).** Under the repository's conversion rule for a matrix that reads no norm (`weight_sums.py`: per-tensor exponent e = the largest with RNE(2^e max|v|) <= 4,095, then w = RNE(2^e v), 16-bit two's complement), the integer tensors of the two pins differ in at least 1% of entries for each of 6 pre-chosen changed tensors, and are identical for the pre-chosen unchanged control.
- **H3 (algebraic fingerprint, toy field).** A per-tensor fingerprint, the multilinear extension of the tensor's integers evaluated at a point derived by hashing (pin-independent label, tensor name), computed modulo the toy prime 2^31 - 1, differs between the pins for 6 / 6 changed tensors and is equal for the control. This stands in for the field claim the design asks the proof to open; the toy prime is not the protocol's field and gives no security figure.

## Metric
- H1: counts of accepted / refused openings, per direction, over all 1,199 tensors; whole-manifest root comparison. Inputs: `runs/stream-stock.json`, `runs/stream-abl.json` of #68 (per-tensor sha256 of the BF16 bytes). Hash: SHA-256 with domain-separated leaf and node prefixes. Deterministic.
- Gating check before H2/H3: the SHA-256 of each fetched tensor's bytes equals #68's streamed per-tensor sha256 (14 / 14 = 7 tensors x 2 pins). If any differ, H2/H3 are not evaluated and that is reported.
- H2: per tensor, the exponent e of each pin, the number and fraction of entries whose integers differ, the SHA-256 of the integers (as `weight_sums.py` hashes them: little-endian int16), and the max |delta| in integer units.
- H3: per tensor, both fingerprints, equal or not. Wall time of one fingerprint per tensor is descriptive (n = 1 per tensor, shared loaded host, no threshold).

The 7 tensors, fixed now (first, middle and last of the changed range over the three changed families, plus one control just outside the range):
1. `model.language_model.layers.17.mlp.down_proj.weight` (changed)
2. `model.language_model.layers.17.linear_attn.out_proj.weight` (changed)
3. `model.language_model.layers.19.self_attn.o_proj.weight` (changed)
4. `model.language_model.layers.34.linear_attn.out_proj.weight` (changed)
5. `model.language_model.layers.50.mlp.down_proj.weight` (changed)
6. `model.language_model.layers.51.self_attn.o_proj.weight` (changed)
7. `model.language_model.layers.16.mlp.down_proj.weight` (control, unchanged per #68)

## Acceptance threshold
- H1 PASS: whole-manifest refused in both directions; 70 / 70 changed-tensor openings refused and 1,129 / 1,129 unchanged-tensor openings accepted, in both directions; the honest manifest of each pin accepted against its own id 1,199 / 1,199.
- H2 PASS: gating check 14 / 14, and for each of the 6 changed tensors the fraction of differing integers is >= 0.01, and the control's integers are identical (0 differing entries, equal SHA-256).
- H3 PASS: fingerprints differ 6 / 6 on changed tensors and are equal 1 / 1 on the control.

## Kill criterion
- Hard stop for the lane: 2026-11-10 23:45 UTC (18:45 EST). Fetch budget: 30 minutes of elapsed time for all 14 range fetches from the moment the first starts; if not done, H2/H3 are reported on the tensors fetched so far, labelled partial.
- If the Hub returns 401/403 for either pin: stop H2/H3, do not look for credentials, publish H1 and the design.
- Memory: one tensor pair in memory at a time, never written to disk. Peak RSS above 8 GB: stop and report.

## Runs
- H1: one deterministic run (n = 1; repeats of a hash computation are not trials).
- H2/H3: one pass over the 7 tensors, each pin fetched by HTTP range request (`8 + header_len + data_offsets` as in #68's `fetch.py`), held in memory. Pinned to cores 6-11 with taskset, run through `fp-heavy.sh` (the host is shared and loaded).
- Debug before the registered run uses only fixtures the registered suite does not use: synthetic random BF16 arrays, and the small unchanged tensor `model.language_model.layers.17.post_attention_layernorm.weight` (10,240 bytes) for the fetch path. None of the 7 registered tensors is touched before the registered run.

## Prior art
- In this repository: #59 signed manifest (client-side, detached; `conversion.committed_files` and `commitment.kind` are the signer's word unless rehashed or rederived); #68 per-tensor diff (70 / 1,199, file hashes all differ because of header metadata); #70 DESIGN 6.2 (weight-cell tie, designed and counted, not built) and section 10 (a statement must reach a layer in 17 to 51 to tell the pins apart); upstream `weight_sums/` (per-tensor SHA-256 of integers, checked by `cp_commit` at commit time, kept secret for hidden weights); `published_id` (heads.h: "The ID does not say whose weights the table contains").
- Outside: Tinfoil Modelwrap (dm-verity roothash over weight files, attested by the enclave, binds files not computation); CommitLLM and DiFR (commitment / fingerprint of model outputs); zkLLM and EZKL commit weights with a polynomial commitment and open per-layer evaluations against it, which is the pattern H3 imitates; safetensors per-tensor hashing in model registries (Hugging Face LFS hashes whole files only).
- New here: the per-tensor manifest measured against the real stock / abliterated pair, the integer-level effect of the conversion rule on an abliteration delta, and an inventory of which FlashProve relations must open against a per-tensor commitment, with main's attack findings mapped onto it.

## Amendments
(empty at registration)
