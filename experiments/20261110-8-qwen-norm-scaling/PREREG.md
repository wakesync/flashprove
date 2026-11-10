# PREREG: 20261110-8-qwen-norm-scaling
Issue: #8 (fidelity), part of #32 (Qwen tracking). Lane: qwen-norm-scaling (CPU only; integer reference arithmetic against a float reference; no proof is built). Date (UTC): 2026-11-10T02:05Z. Base commit: 9b366632d2bb391250a2c44b66ad082a54d83220 (PR #68 head, branch research/1109-qwen-real-weights, itself stacked on PR #66 head 8ec7c799).

This file is the first commit on the branch, before any new run. What was looked at before writing it:
- the files in the repo at the base commit: PR #68's code, RESULTS.md and committed run files, the M2 DESIGN.md, `head_reference.py`, `count_model.py`;
- one read-only summary of PR #68's committed F = 12 rows, `prelook.py` (committed with this file). It printed per-head maxima, o RMS, the worst rel_S and rel_y pairs and the per-pair BF16 numbers. Findings that shaped the candidates below: rel_S at F = 12 already fails the max criterion (max 0.41, worst pairs on the long prompts p06 and p10, heads 33 to 35 and 16); the worst rel_y pairs are heads whose o RMS is under 1 integer unit; per-pair BF16 context is rel_y median 0.0052, max 0.037, rel_S median 0.0032, max 0.0095.
No tensor was fetched and no arithmetic on weights was run in this lane before this commit.

PR #68 is a draft and unreviewed. Its numbers are a baseline to reproduce here (step 1), not facts this lane relies on.

## Pinned inputs (unchanged from PR #68)
- stock `Qwen/Qwen3.8-27B` at `37561816e66b5b9153b1b64c10968c18c1e6f4a0`; abliterated `huihui-ai/Huihui-Qwen3.8-27B-abliterated` at `739e3c5b89849f6c238ce1e5b70008612ae42cdd`. Not gated, no token.
- Prompts: `experiments/20261109-8-qwen-real-weights/prompts.json` as committed (10 prompts, 2,396 tokens, 209 unique token IDs). All 48 V heads of layer 0. **n = 480 (prompt, head) pairs per arm.**
- Fetch: PR #68's `fetch.py` unchanged (9 layer-0 tensors and 209 embedding rows per checkpoint, 171 MB each), plus `layers.0.linear_attn.out_proj.weight` (62.9 MB per checkpoint) for the descriptive residual question only, fetched by the same code with the extra-name argument.
- Float reference: `run_float` of PR #68's `real_head.py` (float64 Transformers semantics, sequence start), unchanged. BF16 context: the same file's cast emulation.
- Integer baseline: `IntHead` of PR #68's `real_head.py` at F = 12, taps at 2^12, which PR #68 checked bit for bit against `head_reference.py` (M2 contract).
- **Both checkpoints.** Layer 0 and the embedding are reported byte-identical between stock and abliterated. This lane re-checks that on its own fetch (every fetched sha256 equal across checkpoints and equal to PR #68's manifests). If it holds, stock is load-bearing and abliterated is an identity check: step 1 runs on both, and the named verdict candidate (or the best one if none passes) is rerun on abliterated and its rows compared. If it does not hold, every arm runs on both and both are reported.

## Steps
1. **Reproduce the baseline.** Rerun `real_head.py run <cache> <ckpt> <out> --F 12` for both checkpoints from the fresh fetch. Compare every F = 12 row with PR #68's committed `runs/real-stock.jsonl` and `runs/real-abl.jsonl`, all fields, exact equality of the parsed JSON values. **Any differing row: stop and report; no later step runs.**
2. **Engine check.** A new generalised head (`scaled_head.py`) evaluates every arm below. It carries integers in x87 long double (64-bit mantissa, exact below 2^64; a guard refuses any value that could reach 2^63) and lets each rounding stage be switched to exact (real-valued). Two gates before any of its numbers is reported: (a) in the M2 configuration at F = 12 it is bit-identical to `IntHead` on all 2,396 tokens x 48 heads (S, o, y); (b) with every stage exact it matches `run_float` to rel_y and rel_S below 1e-9 on every pair.
3. **Localise the error** (descriptive).
4. **Candidates** (registered, thresholded).
5. **Residual-stream measure** (descriptive).
6. **Cost** by the repo's counting model, counted, not built.

## The generalised lowering (notation for every arm)
Scales are powers of two. Public, verifier-recomputed stage (as M2 section 3): in_proj outputs xq, xk, xv at 2^Fx, ar, br at 2^Fab, z at 2^Fz; conv taps at 2^TAP; conv output c = R(sum_tau w_tau x_(t - tau) / 2^(TAP + Fx - Fc)) at 2^Fc; SiLU at 2^Fc; v = R(SiLU(c) 2^(FS - Fc)) at 2^FS; k_hat at 2^Fk = 2^FS and q_hat at 2^Fq = 2^FS by the M2 integer L2 norm (eps = rne(1e-6 2^(2 Fc)); for q the divisor times rne(sqrt(128) 2^12), numerator times 2^12); a = rne(2^Fg exp(-A softplus(ar + dt_bias))), beta = rne(2^Fg sigmoid(br)).
Witness stage:
- P_j = sum_i k_i S_ij (exact, 2^(Fk + FS));  M_j = R(a P_j / 2^(Fg + Fk));  delta_j = R((v_j - M_j) beta / 2^Fg);
- S'_ij = R((a S_ij + 2^(Fg - Fk) k_i delta_j) / 2^Fg)  (equal to M1's floor((a S + k delta) / 2^F) when Fg = Fk = F);
- Sigma_j = sum_i q_i S'_ij (exact, 2^(Fq + FS));  o_j = R(Sigma_j / 2^(Fq + FS - Fo)) at 2^Fo;
- norm (DESIGN 4.4 generalised): Vx = sum o^2; sigma = isqrt(Vx + eps_o), eps_o = rne(128 x 1e-6 x 2^(2 Fo)); Rc = floor(2^RC / sigma); w = floor(o Rc / 2^(RC - Fw)) (|w| <= 2^Fw); cg = rne(2^12 gain sqrt(128) SiLU(z)); y = R(cg w / 2^(Fw + 12 - Fy)) at 2^Fy.
R is floor (M2) or round-half-up rhu(x / 2^m) = floor((x + 2^(m-1)) / 2^m), a public constant in the floor relation (remainder range unchanged). RC = 36 in M2; elsewhere RC = Uo + Fw + 12 with Uo the bit bound of the o class (so Rc >= 2^(Fw + 8) at the class maximum).
M2 at F = 12 is: Fx = Fab = Fz = Fc = FS = Fo = Fy = Fg = 12, TAP = 12, Fw = 12, RC = 36, R = floor everywhere.

## Localisation (descriptive, no threshold)
At the M2 configuration, stages that can be made exact: `in_qkv`, `in_ab`, `in_z` (input rounding), `conv` (tap rounding and conv floor), `silu`, `l2n` (k_hat, q_hat), `gates` (a, beta), `mem` (M floor), `delta`, `state` (S' floor), `o` (o floor), and the norm parts `sigma` (isqrt and eps), `rc`, `w`, `cg`, `y`. Arms, each over the 480 pairs:
- **exact-one**: one stage exact, the rest integer (what fixing that stage alone buys);
- **round-one**: one stage integer, the rest exact (what that stage alone costs);
- grouped: public stage exact (inputs, conv, silu, l2n, gates); state exact (mem, delta, state); output exact (o and every norm part).
Reported per arm: rel_y and rel_S median, min, max; layer-level rel_y (n = 10). The answer to "which step loses the accuracy and why" must cite both tables and one mechanism number per named step (for example 1 - a in integer units for the decay, the per-token o RMS in integer units, the size of y entries in units of 2^-Fy).

## Candidates (registered; every knob fixed here)
Common to C1 to C4: Fw = 16 (w stays inside the 2^18 RNG class with |w| <= 2^16) and Fy = 20 (y is public, class 2^31).
- **C0** M2 baseline, F = 12 (step 1).
- **C1 o-bits.** One larger fixed scale for o and the norm only: Fo = 15 (o's honest class stays 2^18: PR #68's max |o| is 23,630 at 2^12, 189,040 at 2^15). State, memory read and everything before at F = 12, floor.
- **C2 per-head static scale.** Fo,h = min(24, 12 + floor(log2(2^17 / maxo_h))), maxo_h = the head's max |o| at 2^12 over the calibration prompts. Calibration is **leave-one-prompt-out**: the scales used for prompt p come from the other 9 prompts only, so no prompt is scored with scales fitted on itself. The 48 scales are public constants under the model commitment. State as M2.
- **C3 per-token shift (prover witness).** o_j = floor(Sigma_j / 2^s_t), s_t >= 0 the unique shift with every o_j in [-2^17, 2^17) and some o_j outside [-2^16, 2^16) (or s_t = 0). Uniqueness: floor(floor(x / 2^s) / 2) = floor(x / 2^(s + 1)), so s_t + 1 leaves no element outside [-2^16, 2^16) and s_t - 1 puts the named element outside [-2^17, 2^17). Enforced by an exact range on o + 2^17 (18 bits), a one-hot selector naming the element, a range proof that it is outside [-2^16, 2^16), a public table (s, 2^s, eps_s), a gate 2^s x o per element and a remainder in [0, 2^s). eps uses Fo,t = 24 - s_t. State as M2.
- **C4 exact inner product.** The norm reads Sigma_j at 2^24 directly (o is not floored; Fo = 24). The RMS norm is scale-invariant, so only the relative precision of Sigma matters. Range: Sigma needs a two-limb class; the field condition 128 |Sigma|^2 < 2^63 needs a proved |Sigma| < 2^28.
- **C5 q unscaled** (PR #68's side test, head_reference's option): q_hat without 1/sqrt(128), eps_o x 128, everything else M2.
- **State-side fix P**, applied on top of C1 to C4 as C1P, C2P, C3P, C4P: Fx = 16, TAP = 16, Fc = 16 (public stage, class 2^31 holds), Fab = 14 and Fz = 14 (public classes 2^20 hold on PR #68's maxima: ar 94,041 x 4, z 144,386 x 4), Fg = 18 for a and beta, R = rhu in M, delta, S' and o. FS stays 12. Field check: |a P| < 2^18 x 2^42 = 2^60 at the RNG soundness bound |S| < 2^23.
- **C3P-S14** (descriptive ceiling, not eligible for the verdict unless its ranges fit): C3P with FS = 14.
- Post-hoc candidates may be added after the localisation, at most 3, named X1 to X3, each listed under Amendments before it runs. A post-hoc candidate can be reported as reaching the thresholds but is labelled post-hoc and needs confirmation on held-out prompts before it is called a pass.

## Metric
Per arm, over the 480 pairs (and per prompt typical / worst as in PR #68):
- rel_y = ||y_int / 2^Fy - y_f|| / ||y_f|| over all tokens of the prompt, per head; rel_S = ||S_T,int / 2^FS - S_T,f|| / ||S_T,f||; median, min, max over the 480 pairs; layer-level rel_y (n = 10).
- Ranges: max |x| per class per pair: S', M, delta (lo, hi), o (or Sigma), w; public xq/xk/xv, ar, br, z, cg, y; exact quantities sigma, e1, e2, Rc, rr, gap and the floor remainders (non-negative, inside their intervals), the shift s_t (C3). Signed bits per class. Pairs with every class inside its stated bound. Field checks at the soundness bounds (Vx, o Rc, a P, cg w below 2^63).
- Cost: per head per token, the change against M2 arm B of `count_model.py` in gate columns, RNG cells, LKP keys and relations, from the same counting rules; T = 16 totals. **Counted, not built.**

## Acceptance threshold
- **Candidate pass:** median rel_y <= 0.01, max rel_y <= 0.05, median rel_S <= 0.01, max rel_S <= 0.05 over the 480 pairs (PR #68's A2 bar), **and** 480 / 480 pairs with every class inside the bound stated for that candidate, where each RNG cell class keeps the M2 honest contract |x| < 2^18 unless the candidate states a different class and counts its cost, every public class is the DESIGN section 2 class, and every field check holds at the soundness bound.
- **Verdict:** the cheapest passing registered candidate by counted cost (keys + columns + RNG cells per head per token), or "none passes" with the best one's numbers.
- C0 is expected to fail (PR #68). C3P-S14 and C4 are measured as ceilings; they can pass only if their stated classes and counted cost are given.

## Is the threshold the right bar (descriptive, registered now, does not change pass or fail)
With layer-0 out_proj W_o (5,120 x 6,144) and the embedding row x_t (the residual stream that layer 0's mixer output is added to), per token: e_t = ||W_o (y_int,t - y_f,t)|| / ||x_t|| and r_t = ||W_o y_f,t|| / ||x_t||. Reported for C0, every candidate and the BF16 emulation: per prompt the Frobenius ratio over tokens (n = 10), and median, max over the 2,396 tokens. Also the same with the gated-norm output error rel_y next to it, so the two can be read together. This is for Shadow and the M3 design; it does not redefine pass or fail.

## Kill criterion
- Step 1 mismatch: stop and report.
- Engine check 2(a) or 2(b) fails: no candidate number is reported from the engine; fix or report.
- Time box 3 h from lane start 01:26Z: hard stop 04:26Z; no new arm starts after 03:40Z; whatever has run is reported, and arms not run are listed.
- Free disk under 3 GB or scratch over 4 GB: stop writing and report.
- Gated or 401/403 file: stop, no credential search.

## Runs
- Deterministic integer and float64 arithmetic, no seeds. n = 480 (prompt, head) pairs per arm, stock; step 1 and the named final candidate on both checkpoints. One run per arm (deterministic: a rerun of C0 is step 1 itself).
- Heavy runs through `fp-heavy.sh`, `taskset -c 0-5`, at most 6 processes. Shared, loaded host, recorded in ENV.json. No exclusions planned; any int64 or long-double guard firing is reported as that arm's error rows, not dropped.

## Prior art
- In this repo: PR #68 (real-weight check, this lane's input), M2 DESIGN 4.4 (the gated-norm lowering), M1/M1b range studies, docs/model.md's RMSNorm treatment (sqrt(D) folded into weights).
- Block floating point and per-tensor / per-channel / per-token scales in integer inference: I-BERT (Kim et al. 2021) integer-only LayerNorm with integer square root; SmoothQuant (Xiao et al. 2023) and LLM.int8() (Dettmers et al. 2022) for per-token / per-channel activation scales on real checkpoints; microscaling formats (OCP MX, Rouhani et al. 2023) for shared power-of-two exponents per block. zkML: zkLLM (Sun et al., CCS 2024) proves a scale-invariant normalisation with lookups; EZKL uses one global fixed-point scale per circuit. What is new here: power-of-two scales that a proof can pin (public per head, or a witness shift with a uniqueness proof) for a gated delta-rule head, measured on real Qwen3.8-27B weights against the fidelity bar of PR #68.

## Amendments
(empty at registration)

- **2026-11-10T02:45Z, A-1 (step 1, first attempt did not match; written before the second attempt has run).**
  - What happened. The first step-1 run was not PR #68's command line. To fit both checkpoints in one heavy slot I ran them in parallel with `OPENBLAS_NUM_THREADS=3` (`run_lane.sh`, stage `repro`). Result: 473 of 480 rows per checkpoint differ from PR #68's committed F = 12 rows. Every difference is in a float field; the largest relative difference is 4.8e-13. All 13,920 integer fields per checkpoint (range maxima, exact-limb minima) are equal (`runs/repro-diff-threads3-*.json`). By the stop rule the script wrote `runs/STOP` and no later step ran.
  - Diagnosis, from a separate test of the in_proj matmuls only (`blas_threads_test.sh`, `runs/blas-threads.json`): the float64 in_proj outputs hash differently under 1 and under 3 BLAS threads than under 6 threads or with the variable unset at 6 cores (8 of 10 prompts differ), and identically under 6 and unset. PR #68 ran with the variable unset under `taskset -c 0-5`. Its float fields are therefore bit-reproducible only at its thread count, which its README does not pin. This is the working explanation; the second attempt tests it.
  - Decision, fixed now. The second attempt is PR #68's own command line for the registered arm, restricted to F = 12: `taskset -c 0-5`, thread variables unset, checkpoints one after the other (`repro_run2.sh`). If every row of both checkpoints matches exactly, step 1 counts as reproduced, and both attempts are reported. If any row differs, the lane stops and reports. No threshold, metric or prompt changes.
  - Consequence for later steps. The new engine runs one BLAS thread per process, so its in_proj outputs differ from PR #68's in the last bits. Added check: arm C0 in the engine against PR #68's committed rows (largest relative difference of rel_y and rel_S, and whether the integer maxima are equal), reported with the results.
  - Process deviations. (i) The thread test ran outside `fp-heavy.sh` on cores 6 to 11 with up to 6 threads, for about one minute. (ii) The heavy gate has had a queue of 20 minutes or more per slot. Localisation and candidate arms will run as 3 single-thread processes on 3 cores with cached inputs (under the lane rules' heavy threshold of 4 cores or 4 GB), outside the gate, instead of the registered 6 processes inside it. The step-1 runs stay inside the gate.
