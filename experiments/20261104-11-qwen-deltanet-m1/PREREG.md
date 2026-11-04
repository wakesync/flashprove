# PREREG: 20261104-11-qwen-deltanet-m1
Issue: #11. Lane: Qwen3.8 Gated DeltaNet M1 (CPU, synthetic). Date (UTC): 2026-11-04T01:05Z. Base commit: 29907e5fa (main). Context: milestone M1 of the Qwen3.8-27B feasibility study (PR #28, not merged at registration; this branch is based on main and references #28). Harness: the shared product-oracle research harness used by `research/operators/glm_kda_fixedpoint/` (PR #19).

Registered before any experiment code. At registration the only inputs read were PR #28's FEASIBILITY.md and pinned config (linear_key_head_dim 128, linear_value_head_dim 128, conv kernel 4), the #19 harness source, and a harness scaling probe (synthetic product tables of 2^12..2^22 entries, 10..4,000,000 linear rows; prove/verify succeed, 2^22 entries prove in about 90 s and need about 6.5 GB RSS on this host). No DeltaNet code or range simulation existed when this was written.

## Hypothesis
One Gated DeltaNet head at the real Qwen3.8 shape (key dim 128, value dim 128, state 128 x 128) over T = 4 tokens can be written as an integer staged-floor relation on the existing committed product oracle such that (H1) honest proofs are accepted, (H2) every pre-registered hostile class is rejected, and (H3) under realistic synthetic input distributions the integer state stays inside FlashProve's smallness bound |x| < 2^18 for 1,024 steps at the chosen fixed-point format, so M2 can proceed with single-limb state cells.

## Metric
Integer semantics (chosen contract, NOT the publisher's numerics; M0 owns fidelity). Fractional bits F = 12 for every quantity. Integers k, q (L2-normalised, q also scaled by 1/sqrt(128)), v, beta and the prepared decay a = exp(g) are public, rounded to nearest at scale 2^F by the input generator (decay/beta generation by tables is out of scope, as in #19). Per token, for state S (128 x 128, index [i key, j value], scale 2^F):
```
P[j]     = sum_i S[i,j] * k[i]                      exact (scale 2^2F)
M[j]     = floor(a * P[j] / 2^(2F))                 decayed memory read, one rounding
delta[j] = floor((v[j] - M[j]) * beta / 2^F)
S'[i,j]  = floor((a * S[i,j] + k[i] * delta[j]) / 2^F)   decay and update fused, one rounding
o[j]     = floor(sum_i S'[i,j] * q[i] / 2^F)
```
Range contract: S', M, delta are signed 19-bit (|x| < 2^18, the smallness bound of docs/format/11-1-machinery.md); remainders unsigned F or 2F bits; out-of-range is a rejected statement, never saturation. Public: initial state S0 (16,384 cells), per-token a, beta, k, v, q, outputs o, final state S4.

Proof metrics, per run: honest accept (bool), proof bytes, product-table entries, linear rows, CPU prove seconds and verify seconds (wall, single process), peak RSS. Hostile metrics: accept/reject per hostile proof or mutation.
Range metric: max |S| (integers at F = 12) over 1,024 steps of the integer reference, per distribution and seed; bits needed = ceil(log2(max|S|+1)) + 1 sign bit; also max |M|, |delta|, |a*P| and the RMS / max abs divergence of the integer state from a float64 reference of the same recurrence (reported, not thresholded). A secondary sweep reports the same for F in {8, 10, 12, 14, 16}.

Synthetic distributions (no weights). Realistic suite, used for H3: k, q ~ N(0, I) then L2-normalised (q then x 1/sqrt(128)); beta = sigmoid(N(0,1)); decay a = exp(-A softplus(x + dt_bias)), A = exp(A_log), A_log = log U(1,16), dt_bias = softplus^-1(dt), dt ~ logU(1e-3, 1e-1), x ~ N(0,1) per token (Mamba2/Qwen-style init ranges); v = SiLU(z) with (R1) z ~ N(0,1), (R2) z ~ N(0, 2^2), (R3) z = 2 * t_3 (heavy tails), (R4) z AR(1) over tokens, rho 0.9, unit variance, values N(0, 2^2) marginally. Stress suite, reported only: same four v laws with a = 1 (no decay) and beta = 1.

## Acceptance threshold
GO for M2 (PASS) only if all hold:
- H1: honest proof of the T = 4 head accepted for 10/10 seeds (seeds 1..10; inputs from R1 after a 64-token integer warm-up from S = 0, so S0 is a realistic nonzero state).
- H2: 100% rejection in every hostile class, each class with at least the listed count, on seed 1: (c1) private mid-sequence state cell tampered (>= 2 proofs: token 1 and token 3); (c2) state cell changed with remainder shifted to preserve the floor equation (negative remainder, >= 1); (c3) decay tampered in one gate while the public decay is unchanged (>= 1) and public decay coordinate mutated against an honest proof (>= 1); (c4) beta tampered in the witness (>= 1) and public beta mutated (>= 1); (c5) memory read / delta rounding tampered with paired quotient/remainder shift, truncation toward zero (>= 2); (c6) one range bit flipped (>= 2); (c7) public S0, k, v, q, output and final-state mutations against an honest proof (>= 6, one each); (c8) proof byte flips (>= 10), truncations (>= 8) and one trailing byte. Complete hostile proofs follow the #19 style: the hostile prover commits the tampered witness and substitutes the true local values of every linear row as targets; the unchanged verifier must reject.
- H3: on the realistic suite, max |S| over 1,024 steps < 2^18 at F = 12 for every distribution and every one of 5 seeds (seeds 1..5); and max |M|, |delta| < 2^18 likewise.
Anything else is FAIL (reported with the same rigor). If H1 and H2 pass but H3 fails, the report states the smallest F (or the second limb) that would fit.

## Kill criterion
KILLED if the T = 4 proof at 128 x 128 cannot be built on this host within the harness (plan refused, table above 2^22 entries, or peak RSS above 12 GB), or if total compute exceeds 3 hours. Then the range study (H3) is still reported, and the proof is reported at the largest shape that fits, labelled as not the M1 shape.

## Runs
Proof: 10 honest runs, seeds 1..10, sequential, one process each, no warmup excluded (first run reported, also median without it); timings reported as n, median, SD, min/max. These are CPU timings on a shared, loaded VM: indicative only, not a performance claim. Hostile classes on seed 1 as listed above. Range study: 5 seeds x 4 realistic distributions x 1,024 steps, plus the stress suite and the F sweep (seeds 1..5). Nothing excluded unless a run crashes for a host reason (OOM by another tenant), which is then rerun and reported.
Security parameters are the #19 research test settings (target 10 bits, 6 work bits, deterministic toy coins): this measures relation soundness of the construction, not production security.

## Prior art
- This repository: `research/operators/glm_kda_slice/` (two tokens, dimension 2, rational KDA continuity) and `research/operators/glm_kda_fixedpoint/` (one token, dimension 1, signed staged floor, 50 hostile proofs), both on the shared product-oracle harness (`research/operators/{public_binding,shared_wires,affine_rows}`). PR #28 FEASIBILITY.md section 2 (recurrence is the hard part; range under 2^18 is the open question).
- Literature: Gated DeltaNet (Yang, Kautz, Hatamizadeh, ICLR 2025) and DeltaNet parallelisation (Yang et al., NeurIPS 2024) define the recurrence; Mamba2 (Dao and Gu, 2024) defines the A_log / dt_bias decay parameterisation used for the synthetic gates. zkML systems (zkLLM CCS 2024, EZKL, Jolt, Expander, Attestable's 2026 Gemma prover, CommitLLM) prove softmax-attention transformers; none we found proves a gated delta-rule recurrent state, so the 128 x 128 recurrence proof and its fixed-point range study are new here. Known general fact: the delta rule with ||k|| = 1 and beta in [0,1] applies a contraction (I - beta k k^T) to the state, so growth comes from the v inputs and from floor-rounding bias, which this study measures.

## Amendments
(empty at registration)

### A1 (2026-11-04, after results; bookkeeping only): issue linkage
Reason: independent review of PR #47 found the issue reference wrong. The header line above says "Issue: #11". The correct issue is **#33** (Qwen DeltaNet M1, one head at real state shape), under tracking issue **#32** (Qwen3.8-27B port). #11 is the GLM/DeepSeek gate issue. The experiment directory id `20261104-11-qwen-deltanet-m1` keeps its `-11-` for history and is not renamed. The registration text above is unchanged. Also noted: the header "Date (UTC): 2026-11-04T01:05Z" is later than this file's commit time (67c55fe2, 2026-11-04T00:54:23Z). The commit time is the authoritative registration time; the header value is inaccurate and left unedited. No threshold, metric, seed or run changes.

### A2 (2026-11-04, after results): wide product.h lowering is a deviation
Reason: the review asked that deviations sit here, not only in RESULTS.md. The Hypothesis registered the relation "on the existing committed product oracle". The #19 harness (`affine_rows/product.h`) caps relations at 64 and terms at 8, which cannot express 128-term reductions. The run used `research/operators/qwen_deltanet/product.h`, a wide variant on the same product oracle and the same affine-row lowering: up to 2^23 relations and 256 terms per relation, its own transcript label, every relation bound in the first query and counted in GroupLoad and plan_iopp exactly as `affine_size`. This was decided after registration and after code started (02:13Z). It does not change H1, H2 or H3 or any threshold. It was reviewed once independently (PR #47 review, 2026-11-04T04:33Z, no issue found); that is one review, not a proof.

### A3 (2026-11-04, after results; reporting only, no threshold change): public v range under the R3 law
Reason: the review found that `ranges.py` did not track the public input v, while `admissible()` in `test.cpp` refuses any statement with |v| >= 2^18. `ranges.py` now also records max |v| and the first step at which each of S, M, delta and v reaches 2^18 (`first_step_over_2_18_each`, `v_admissible`). The registered H3 metric (max |S|, |M|, |delta| < 2^18) and its field `first_step_over_2_18` are unchanged, and every pre-existing field of `runs/ranges.json` regenerated byte-identical. H3 stays **FAIL**, the verdict stays **NO-GO as registered**. v is reported, not added to the threshold.

### A4 (2026-11-04, contract wording; no code change)
Reason: review nit. Each 19-bit range check encodes x + 2^18 in 19 bits, so the relation admits x in **[-2^18, 2^18)**, one value wider at the bottom than the "|x| < 2^18" wording above. The builder and `admissible()` still enforce |x| < 2^18 on the honest side; the relation-level range is [-2^18, 2^18). The uniqueness argument for each staged floor (README, "Soundness note") holds for either range. The floor-uniqueness argument also depends on `admissible()`, a statement-side precondition checked before proving (|k|, |q| <= 2^F, a and beta in [0, 2^F], |v|, |o|, |S0|, |S_T| < 2^18). It is not a relation.
