# PREREG: 20261111-35-qk-rmsnorm
Issue: #35. Lane: qknorm35. Date (UTC): 2026-11-11 04:55. Base commit: ec902e7d2c4c4b29cac66c5d2fabe19b2d175279.

## Hypothesis
Per-head q/k RMSNorm with epsilon and a learned per-channel gain, y_j = floor(g_j * Z_j / 2^F) with Z_j = floor(x_j * R / 2^s), R = floor(2^K / sigma), sigma = isqrt(4^m * (sum_j x_j^2 + epsI)), can be lowered as proof constraints (exact integer isqrt with two range-checked residuals, a range-checked division remainder, bit-decomposed floor remainders, an admitted gain bound in the statement) on the bounded affine product oracle, such that at head dim D=16 (toy arm) and D=256 (Qwen full-attention head dim arm) honest statements are accepted, every registered hostile case below is rejected, including complete malicious proofs, and the fixed-point output stays within the registered error threshold of a float64 RMSNorm reference.

## Metric
Statement (new operator family `qwen-qk-rmsnorm-v1`, research only): public F=12, D in {16,256}, Hq=2 query heads and Hk=1 key head (GQA shape), the public pre-norm integers xq[h][j], xk[h][j] in [-2^F,2^F), the public q gain vector gq[j] and k gain vector gk[j] (integers at scale 2^F, admitted |g_j| < 2^(F+3), i.e. |gain| < 8), and the public outputs yq, yk. Output admission: |y| < 2^(F + log2(D)/2 + 4). Verifier-pinned constants (not statement fields): epsI = round(D * 1e-6 * 2^(2F)) (Qwen rms_norm_eps 1e-6), m=8, K=45, s = K - F - log2(D)/2 - m. D is restricted to perfect squares so that sqrt(D) is a power of two. The inputs are public and pinned in-proof; binding them to a q/k projection is NOT part of this milestone (M3 / #34 job).

Per arm and seed (one run = one seed, one fresh fixture, one process):
- `honest`: accept/reject of the honest proof of each fixture distribution: `uniform` (x uniform in [-S,S)), `outlier` (one channel S-1, rest uniform in [-S/64,S/64)), `low` (|x| <= 4), `unit-spike` (x_0 = 1, rest 0, the near-zero edge), `zero` (all heads zero, y must be exactly 0). Gains uniform in [0.5, 2) at scale 2^F, q and k independent.
- Hostile, each counted as reject/accept, with the sub-case kind (`complete` = complete malicious proof: product gates all hold, prover's affine targets replaced by locally true values, unchanged verifier keeps its own targets, the harness asserts >= 1 violated relation; `statement` = honest proof bytes against a changed statement):
  1. `wrong-scale` complete: witness computed with gq[0]+1, statement with the true gq and the resulting y.
  2. `wrong-scale` statement: honest proof, statement gq[0]+1.
  3. `gain-swap` complete: q heads normalised with the k gains.
  4. `gain-over-bound` statement: one gain set to 2^(F+3) (admission must refuse).
  5. `isqrt-plus-one` complete: sigma+1 with residuals recomputed (one residual negative).
  6. `isqrt-minus-one` complete: sigma-1 with residuals recomputed.
  7. `div-rem-over` complete: R-1 with remainder rr+sigma (remainder outside [0, sigma)).
  8. `div-rem-under` complete: R+1 with remainder rr-sigma (negative remainder).
  9. `floor-rem-over` complete: Z_0+1 with remainder minus 2^s (outside range).
  10. `swapped-head` statement: honest proof, yq[0] and yq[1] swapped.
  11. `swapped-head` complete: witness normalises xq[1] in head 0 and xq[0] in head 1, statement keeps the true inputs and the swapped outputs.
  12. `wrong-vector` complete: q head 0 output is the q-norm of the k vector xk[0], witness uses xk[0] in head 0's input cells.
  13. `shared-coefficient` complete: head 0 reuses head 1's R (and its sigma).
  14. `zero-no-eps` complete (on a zero head): sigma = 0 as if epsilon were dropped; and `spike-no-eps` complete (unit-spike head): sigma = isqrt(4^m * 1) and the resulting outputs.
  Cases 1 to 13 and 15 run on the `uniform` fixture, case 14 on the `zero` and `unit-spike` fixtures. "Channel 0" in cases 1, 2 and 9 means j* = argmax_j |Z_0j| of q head 0; the gain change in case 1 is one quantum (1/2^F); if that leaves y unchanged the harness doubles the change until y changes and records the step. Every complete case recomputes the downstream witness values (R, Z, y) from its changed value, so the statement is self-consistent except for the targeted relation.
  15. `wrong-output` statement: y[0]+1. Plus `byte-flip`, `truncated`, `trailing`, `dim-replay` (D16 proof against a D256 statement or the reverse), `scale-replay` (F=14).
- Fidelity (float64 reference y_ref = g * x / sqrt(mean(x^2) + 1e-6) on the dequantized same integers x/2^F, g/2^F): per head the vector-relative L2 error ||y/2^F - y_ref|| / ||y_ref||; per arm and distribution the median and max over heads in a seed, then median and sample SD across the 10 seeds; also the max absolute element error. Zero heads: exact equality y=0.
- Descriptive only (shared loaded CPU, not a performance claim): columns, relations, proof bytes, prove and verify seconds of the `uniform` honest proof, n=10 per arm, median, sample SD, min, max.

## Acceptance threshold
PASS iff all of: (a) every honest proof accepted in every seed and arm (5 distributions x 10 seeds x 2 arms = 100); (b) every hostile sub-case rejected in every seed and arm, in both the release and the UBSan build, with zero UBSan reports; a complete malicious case whose witness violates no relation is a harness bug and counts as FAIL; (c) fidelity: for every arm and every non-zero distribution, max per-head relative L2 error <= 1e-2 over all 10 seeds; the across-seed median of per-seed median relative error <= 1e-3 for `uniform`, `outlier` and `low`, and <= 5e-3 for `unit-spike` (its single non-zero output is about 1000 output quanta at F=12, so the output floor alone is about 5e-4 to 1e-3 relative; fixed now, before any run); zero heads exactly 0. Any hostile acceptance in any seed: FAIL. Fidelity outside (c) with (a),(b) met: FAIL on fidelity, reported as such (the constraint result stands separately).

## Kill criterion
KILLED if the relation cannot be built without editing files already on main (research/operators/qwen_ops/*, qwen_deltanet_m2_build/*, qwen_conv_history/*), or if no registered run has started by 2026-11-11T06:30Z (lane deadline 07:10Z); then publish what exists as KILLED. Stop at the first registered run that accepts a hostile sub-case and report FAIL; no tuning and rerun. If the D=256 arm does not fit in the time budget, it is reported as not run (the toy arm verdict stands alone, labelled partial). Free disk below 3 GB: stop.

## Runs
Registered suite: seeds 1..10 per arm (n=10 >= 5; >= 10 for the descriptive timing), one process per (seed, arm), arms alternating per seed (odd seeds D16 then D256, even seeds D256 then D16), fixed toy coins derived from the seed, no warmup exclusion, no seed excluded. The suite runs once in the release build and once in a UBSan build (same seeds). Debug before the registered run uses ONLY seeds 901..903, disjoint from the registered seeds, under ignored `work/`, never committed as evidence. CPU only, <= 6 cores, through the shared heavy-job gate; the host is shared and loaded.

## Prior art
- zkLLM (Sun, Li, Zhang, CCS 2024): tlookup, a lookup argument for non-arithmetic tensor operations, and zkAttn for softmax; normalisation by table lookups over a quantised domain. EZKL: LayerNorm/RMS-style ops lowered to lookup tables over a bounded input range with fixed-point scales. Jolt (Arun, Setty, Thaler 2024) and Expander/GKR-style systems: lookup-centric arguments that make such tables cheap. These use tables for 1/sqrt; this lane uses exact integer isqrt with residual range checks instead (no table, no domain limit beyond the input bound), which is the standard non-native square-root gadget in arithmetic-circuit libraries.
- In this repo: PR #67 `qwen_ops` norm (bounded mean-square table, unit gain, no epsilon, no low-energy vectors, one head per proof; inputs prover-chosen); PR #66 design and the M2 build (`qwen_deltanet_m2_build/head.h`, gated RMSNorm of the DeltaNet head output: sigma = isqrt(sum o^2 + eps), Rc = floor(2^36 / sigma), 12-bit limb lookups, public per-channel constant). PR #74 (`qwen-norm-scaling-layer0`) showed on real layer-0 weights that floor placement and scale dominate norm error (it is a numerical study, no proof).
What is new here: (1) q/k RMSNorm (Qwen full attention q_norm / k_norm over head dim) as a proof relation, as opposed to the gated output norm of M2; (2) learned per-channel gains as public statement fields with an admitted bound, separate for q and k, several heads per proof with GQA shape; (3) epsilon in the relation so zero and near-zero vectors have a witness (the #67 table norm rejects them), with an extra 2^m pre-scale inside the isqrt so the floor error stays small at low energy; (4) bit-decomposition range checks on the product oracle of #67 rather than M2's two-lookup machinery (no lookup is used); (5) hostile cases specific to this operator (swapped head, wrong vector, gain swap, coefficient reuse across heads, epsilon dropped). Nothing cryptographically new.

## Amendments
