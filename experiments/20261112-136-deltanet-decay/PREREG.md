# PREREG: 20261112-136-deltanet-decay

Issue: #136 (part of #35, informs #8, tracking #32). Lane: decay136 (CPU only, no proof, no table digest change). Date (UTC): 2026-11-12T21:15Z (clock estimate; the commit time is the record). Base commit: c810b3e998c45c14fc0c422cf3cb69ec72ab47df (main).

This file is the first commit of the experiment, alone, before any experiment code and before any activation is recorded. What was read before writing it: issue #136; `experiments/20261109-32-qwen-m3-design/DESIGN.md` sections 5.0, 5.2, 5.3, 8.2; `research/operators/qwen_ops/tables.py` and `README.md` (table format v1); PR #68's `real_head.py` (`heads`, `run_float`) and `runs/weight-stats.json` (layer 0 quantiles only); PR #88's `q1_forward.py`; PR #124's `e2e.py`, `PREREG.md`, `RESULTS.md`, `prompts-e2e.json`, `runs/progress.log.jsonl`, `runs/run.time`. No activation of any layer on any registered prompt has been looked at by this lane.

## Question
How often does the DeltaNet softplus input x = ar + dt_bias leave table format v1's domain [-8, 8), how often is the decay exponent g below one v1 row step (1/256), on which layers and V heads, and which of a few registered table designs keeps the decay a = exp(-g) within a registered error of float64, on real Qwen3.8-27B abliterated activations.

## Hypothesis
H (falsifiable): table design T2 (below) meets the acceptance threshold on every one of the 48 DeltaNet layers x 48 V heads x registered prompts of the abliterated checkpoint, and T0 and T1 do not.
Each of the four arms gets its own PASS / FAIL; H is judged on T0, T1, T2 only. Any combination of verdicts is a valid outcome and is reported as measured.

## Setup (fixed now)
- Checkpoint: huihui-ai/Huihui-Qwen3.8-27B-abliterated@739e3c5b89849f6c238ce1e5b70008612ae42cdd, as PR #124's "abl" leg: layers 0 to 16 and the embedding read from Qwen/Qwen3.8-27B@37561816e66b5b9153b1b64c10968c18c1e6f4a0 (byte-identical in both, PR #68), layers 17 to 63, final norm and lm_head from the abliterated repo. Weights by HTTP range request into memory, one layer at a time, via PR #88's `q1_forward.Ckpt`; sha256 of every fetched tensor recorded and checked against PR #124's committed `runs/manifest-{stock,abl}.json` after the run.
- Forward: PR #88's float64 numpy forward, imported unchanged (`q1_forward.layer_step` with mode "REF", i.e. `deltanet_inputs`, `head_out(..., "REF")` = `real_head.run_float`, `attention`, `mlp`). One path only (REF), closed loop, teacher-forced on the prompt tokens.
- Logging hook (the only addition; no forward code is edited): a new driver in this directory calls `q1_forward.deltanet_inputs(L, x)` once per DeltaNet layer and prompt, records the returned `ar` (in_proj_a output, shape (T, 48)) and the layer's `A = exp(A_log)` and `dt_bias` (both from the same tuple), then advances the residual with the same tuple through `head_out(hd, "REF")`, out_proj and `mlp` exactly as `layer_step` does (same expressions, so the residual is the one `layer_step` would produce; checked bit-equal against `layer_step` on the debug fixture). From these: x = ar + dt_bias, g = A softplus(x) (softplus = `np.logaddexp(0, x)`, as `run_float`), a = exp(-g), all float64. This is exactly the decay `run_float` applies (it uses exp(g) with g = -A softplus(x)).
- Sanity check of the forward (registered): after layer 63, the final norm and lm_head, REF's top-1 at the last position of p01 is " Tokyo" (25358), as in PR #124 on the abl leg. Only that one position's logits are computed.

## Prompt set (fixed now)
Primary set S10: all 10 prompts of PR #124's `prompts-e2e.json` (sha256 47aa61b46e142382ffa58b88f918df6ec63f1158629df5938ec00961a5242cfc, token ids as committed): p01-ordinary-short (13), p07-chat-ordinary (23), p08-chat-refusal (39), p09-multilingual (21), p02-ordinary-paragraph (107), p04-repeat-punct (64), p05-code (144), p03-repeat-word (512), p06a-digits-256 (256), p11-chat-long (282); 1,461 tokens.
Reduced set S7 (used only under the rule in "Runs"): p01, p07, p08, p09, p02, p04, p05; 411 tokens.
Debug fixture (not a suite prompt): "The capital of Italy is" (`q1_forward.FIXTURE`), stock layers 0 to 3. All code is debugged on this fixture and on synthetic x only; no run of any size on a registered prompt before the registered run.

## Table designs (integer emulation, fixed now; F = 12 throughout unless stated)
Common front end, from DESIGN 5.0 / 5.3:
- ar_int = floor(2^12 ar) (the in_proj floor of DESIGN 5.1); dt_int = RNE(2^12 dt_bias) (its own class, |dt_int| < 2^17); X = ar_int + dt_int (x at 2^12).
- cA_h = RNE(2^(e_A) A_h), with e_A per layer the largest e in 1..24 with RNE(2^e max_h A_h) <= 4,095 (the honest conversion of `research/operators/qwen_m3/bounds.py` completeness check); s_A = e_A.
- Softplus table: v1 `softplus-f12` as pinned (`research/operators/qwen_ops/tables/softplus-f12.i64le`, row i at x = (i - 2048)/256), key i = floor(X / 16) + 2048.
- g_int = floor(cA_h sp / 2^(s_A)) (g at 2^12).
- Coarse exp table: format v1 grid, row i = RNE(2^12 exp(-(i - 2048)/256)), generated with the pinned integer generator `tables.expq` / `tables.nearest` (imported unchanged; this table is not on main, it is the "exp(-x) on [0, 8)" table DESIGN 5.2 requests, in v1 layout), key i = floor(g_int / 16) + 2048.
- a_arm = (table output) / 2^12.

Arms:
- **T0** (v1 as published): reject if a softplus key or an exp key is outside [0, 4096). A rejected (token, head) has no a; it counts as a failure of its cell.
- **T1** (v1, clamp): keys clamped to [0, 4095] (saturating), no reject.
- **T2** (T1 + fine exp, DESIGN 5.3): if g_int < 4096 (g < 1), a = RNE(2^12 exp(-g_int / 4096)) / 2^12 from a 4,096-row table keyed on g_int directly (step 2^-12), generated the same way; otherwise the T1 coarse lookup.
- **T3** (the one extra arm): T2 plus a softplus passthrough above the domain: if X >= 8 * 2^12, sp = X (softplus(x) - x = softplus(-x) < 3.4e-4 for x >= 8, i.e. under 1.4 units at 2^12); below -8 the clamp of T1. This is the "saturating below, identity above" semantics, as cheap as a range check.

Descriptive only (no verdict, labelled as such in RESULTS): the T3 error split by source (cA rounding alone, softplus key step alone, g key step alone, output rounding alone, each with the other steps in float64), and T3 with the internal scale F' in {14, 16, 18} for sp, g, the fine key and the output (keys at the same v1 softplus row grid), to name the step a failing head would need.

## Metric
For each arm, DeltaNet layer l (48), V head h (48), prompt p, over the tokens t of p (all in float64 from the integer outputs):
- e_tok(l,h,p) = max_t |a_arm(t) - a(t)|, and the median over t.
- P(t) = prod_{s <= t} a(s) (the state decay accumulated from token 0), P_arm likewise; e_cum(l,h,p) = max_t |P_arm(t) - P(t)| (absolute, P in [0, 1]); also max_t |ln P_arm(t) - ln P(t)|, descriptive.
- Reject count (T0).
Per layer and head over all tokens of the set: share of x outside [-8, 8) (split x < -8, x >= 8), share of g < 1/256, min / median / max of x, g, a, with n.
Spread: medians and maxima over tokens, over (l, h, p) cells, per layer and per head; share counts with their n.

## Acceptance threshold
An arm PASSES iff on every (l, h, p) cell of the set that was run: no rejected lookup, e_tok <= 2^-9 (half a BF16 ulp on [0.5, 1): no worse per token than rounding a to BF16), and e_cum <= 0.01. Otherwise it FAILS, and RESULTS names the failing layers and heads, with counts out of 2,304 x prompts.
H holds iff T2 PASSES and T0 and T1 FAIL.

## Kill criterion
- Lane hard stop 2026-11-12T23:30Z (wall clock, includes queue time). Forward hard stop 23:05Z: if the forward has not finished, it is stopped (by pid) and the verdict is computed on the DeltaNet layers completed, labelled PARTIAL with the layer count; no layer is extrapolated.
- If the heavy slot (`bigmem.lock` then `fp-heavy.sh`) is not granted by 22:15Z, S7 is run instead of S10 (logged; not an amendment, the rule is fixed here). If S10 is running and the per-layer rate logged after layer 4 projects completion after 23:00Z, it is stopped and S7 started only if S7 projects within the stop; otherwise S10 continues to the stop as PARTIAL.
- MemAvailable under 10 GB at start: do not start, wait (counts against the stop). RSS over 14 GB: stop, KILLED for that run.
- Sanity (Tokyo) fails: KILLED, the activations are not used for a verdict.

## Runs
One deterministic forward (n = 1 per token; the numbers are deterministic functions of the weights and prompts). Determinism check instead of repeats: on the debug fixture, the driver run twice gives bit-identical x. Variance reported over tokens, prompts and (layer, head) cells, as in "Metric", n stated each time. No exclusions; every token of every prompt in the set, every DeltaNet layer reached, every V head. Cores 6 to 11 (`taskset -c 6-11`), BLAS threads 6, no worker pool (one path only). Raw per-(l, h, p) tables committed compressed (under 20 MB total); raw per-token x is kept in scratch, not committed if over budget.

## Prior art
In this repo: PR #68 (layer-0 weights: dt_bias in [-5.72, 19.25], A in [0.0038, 0.34], decay at a = 0 median 0.998, `runs/weight-stats.json`); PR #67 / `research/operators/qwen_ops` (table format v1, domain [-8, 8), step 1/256, fail closed, fixed decay constants c in {1/2, 1, 2}, no learned A_log / dt_bias); DESIGN M3 (PR #70 line, `20261109-32-qwen-m3-design`: softplus then cA product then exp lookup, the fine g table suggestion, the domain risk flagged and not measured); PR #74 / #88 / #124 (XS arms compute the gates in float and round at 2^-18, which is what passed end to end). Outside: zkLLM (Sun et al. 2024, tlookup for non-arithmetic ops with range splitting), EZKL and Jolt (lookup arguments with fixed-domain tables; out-of-domain inputs are either range-reduced or rejected), Mamba / Gated DeltaNet reference kernels (softplus with a linear passthrough above a threshold, `F.softplus(threshold=20)` style). What is new: per-head measurement of the softplus domain and decay step on the real 27B model's activations, and a registered comparison of table semantics against float64, which no lane has done.

## Amendments
(empty at registration)
