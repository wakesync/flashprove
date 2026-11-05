# PREREG: 20261105-11-moe-topk-routing
Issue: #11 (GLM/DeepSeek operator feasibility), cross-ref #35 (operators). Lane: MoE top-k routing operator (CPU, synthetic). Date (UTC): 2026-11-05T03:04Z. Base commit: 0344ae53 (main).

Registered before any experiment code. Inputs read at registration: PORT-FEASIBILITY.md and SOURCE-RECHECK.md (planning), the pinned GLM Transformers router (`modeling_glm5_next.py` at transformers f90e93c4, `Glm5NextTextTopkRouter`, lines 144-182), the pinned DeepSeek reference gate (`inference/model.py` at publisher revision 314113f8, `class Gate`, lines 794-829), both pinned configs, the existing constraint-only prototype `research/operators/topk.py` (not a proof), and the product-oracle harness used by `research/operators/qwen_deltanet/` (PR #47). No code for this experiment existed when this was written.

## Hypothesis
A bias-corrected, stable, normalized top-k router with weighted aggregation, at the real GLM-5.3-Flash shape (288 experts, k = 8, scale 5/2) and the real DeepSeek-V4.1-Flash shape (384 experts, k = 6, scale 3/2), can be written as a fully bound integer relation on the shared committed product oracle such that (H1) honest proofs are accepted, (H2) a complete malicious prover is rejected for every pre-registered false routing claim, (H2b) the relation has exactly one satisfying routing for exhaustively enumerated small instances with exact ties, and (H3) the selection-plus-normalization part costs at most 2^15 product-oracle columns per token at the GLM shape.

## Metric
Integer semantics (NEW contract, not publisher numerics; score nonlinearities sigmoid / sqrt(softplus) are out of scope and are inputs here):
- Inputs per token: scores s_i, unsigned 16-bit; correction bias b_i, signed 16-bit; expert outputs X_i[d], signed 16-bit, d < h, h = 16 (synthetic stand-in for the routed expert output).
- Selection key K_i = E * (s_i + b_i + 2^15) + (E - 1 - i). Keys are distinct; descending key order = descending corrected score with ties to the LOWEST expert index. Selected set = the k largest keys; ordered list p_1..p_k strictly descending.
- D = sum_m s_{p_m} (ORIGINAL scores, bias never enters weights). D = 0 is inadmissible (fail closed, no epsilon).
- w_m = floor(2^12 * RSn * s_{p_m} / (RSd * D)) with RS = RSn/RSd (GLM 5/2, DeepSeek 3/2): normalization and routed scaling in ONE floor. Weights need not sum exactly.
- y[d] = floor(sum_m w_m * X_{p_m}[d] / 2^12) (weights applied to the expert output, GLM style; DeepSeek applies them before w2, which differs under integer rounding and is noted, not modelled).
- Relation (all private except as stated): one-hot selection matrix P (k x E, Boolean, rows sum to 1); sel_i = sum_m P[m,i] Boolean; gathered keys/scores/outputs by products with P; strict descending gathered keys (27-bit range); every unselected key below the last selected key (27-bit range on (1 - sel_i)(K_last - K_i) - (1 - sel_i)); score range 16 bits; quotient/remainder for weights with 0 <= r < RSd*D (21-bit ranges both sides), w 14 bits; D - 1 >= 0 (19 bits); output floor remainder 12 bits. Public: s, b, X (bound by 1-term relations at the toy statement boundary), y. Shape (E, k, h, T) fixed by the verifier.
- Per run: accept, proof bytes, product-oracle columns used, relations, terms, prove and verify wall seconds (single process), peak RSS. Per-token column counts split into selection+normalization vs aggregation.

## Acceptance threshold
PASS (GO for this operator as a research gadget) only if all hold:
- H1: honest proofs of T = 4 tokens accepted 10/10 for each arm (GLM 288/8, DeepSeek 384/6), seeds 1..10. Every fixture includes at least one exact corrected-score tie inside the selected set and one tie straddling the k boundary.
- H2: on seed 1 of each arm, a complete malicious prover (commits a full witness for a FALSE public output, consistent everywhere it can be, unchanged verifier, statement = the false claim) is rejected 100% in every class: (a1) wrong expert chosen (swap the k-th selected for the best unselected, >= 2), (a2) swapped tie order inside the selected set (>= 1) and lower/higher index swap at the k boundary tie (>= 1), (a3) bias leaking into weights (weights from s+b, >= 1), (a4) unnormalized weights (raw s scaled, >= 1), (a5) duplicate expert (>= 1), (a6) k-1 selected (one empty row, >= 1) and k+1 selected (one row selecting two experts, >= 1), plus (a7) public-statement mutations against an honest proof (s, b, X, y; >= 4) and (a8) proof byte flips (>= 8), truncations (>= 4), trailing byte, and a k-1 / k+1 shape verifier against an honest proof (>= 2). Each complete hostile witness must also violate >= 1 relation (reported).
- H2b: relation-level enumeration (no proof) at E = 16, k = 2 (all 240 ordered pairs) and k = 3 (all 3,360 ordered triples) with forced ties: exactly one candidate ordered selection admits a relation-satisfying witness, and it equals the reference.
- H3: selection+normalization (excluding the h-dependent gather/aggregation) <= 2^15 product-oracle columns per token at the GLM shape. Aggregation cost is reported per token at h = 16 and extrapolated linearly to h = 4096 (GLM residual width); if the extrapolation exceeds 2^20 columns per token, the one-hot-gather aggregation is declared NO-GO at real width (does not fail the selection gadget) and dispatch must move to a lookup/permutation design.
Anything else is FAIL, reported with the same rigor.

## Kill criterion
KILLED if no honest proof at the GLM shape is accepted by 2026-11-05T05:52Z (hour 3 of the 4 h lane budget), or peak RSS exceeds 12 GB, or table above 2^22. Any accepted hostile proof is reported immediately as a soundness failure (FAIL), not retried away.

## Runs
10 honest proofs per arm, seeds 1..10, sequential, one process each, pinned to <= 6 cores (taskset), no warmup excluded (first run reported; median also without it). Timings: n, median, SD, min/max. Shared loaded VM, another lane in parallel: indicative only, not a performance claim. Hostile suite on seed 1 per arm. H2b enumeration seeds fixed (seed 1). Research security settings of #19 (target 10 bits, 6 work bits, deterministic toy coins): relation soundness of the construction, not production security.

## Prior art
- This repository: `research/operators/topk.py` (constraint-only top-k, n <= 8, full O(n^2) sort permutation, no proof); `research/operators/qwen_deltanet` (wide affine rows on the product oracle, PR #47); upstream FlashProve proves Maverick top-1 routing (clamped argmax, lowest-index ties, input scaling) only.
- Literature: zkLLM (CCS 2024), EZKL, Jolt/Expander and OpenLLM (ePrint 2026/1578, operator-level zkSNARKs) prove dense transformer operators; top-k in SNARKs is usually done by sorting networks or permutation/lookup arguments. We found no published proof of bias-corrected (noaux_tc) top-k with unbiased normalized weights. Web search was unavailable in this lane (402), so the prior-art check is limited to the planning lane's literature scan (LIT-SCAN, 2026-11-03).
- New here: threshold-plus-ordering formulation with distinct composite keys (O(kE + E log K) instead of O(E^2) sorting), bias-in-selection-only enforced by construction, and complete false-claim provers.

## Amendments
(empty at registration)
