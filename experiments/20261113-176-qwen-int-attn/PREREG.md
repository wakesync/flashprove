# PREREG: 20261113-176-qwen-int-attn
Issue: #176 (part of #8, informs #35 and #32). Lane: attn176 (CPU only; integer reference arithmetic against a float64 reference; no proof, relation or verifier change). Date (UTC): 2026-11-13T16:25Z (clock estimate; the commit time is the record). Base commit: 59bff9a4608e0cc720d58d7c30823a8838fa43e4 (main).

This file is the first commit of the experiment, alone, before any experiment code and before any activation is recorded. Read before writing it, all on main at the base commit: issue #176; `docs/model.md` sections 1, 2, 4, 6; `verifier/src/vf_attention_shape.h` (`shape()`, N1 to N9); `scales/README.md` "The exponent of each cell" and "The shifts"; `research/operators/qwen_ops/DQ-NE-D.md` section 4; `experiments/20261110-8-qwen-q1-deep-fidelity/q1_forward.py` (PR #88: `Ckpt`, `rms0`, `attention`, `layer_step`, `head_out`); `experiments/20261111-8-qwen-e2e-agreement/` (PR #124: `e2e.py`, `prompts-e2e.json`, `run.time`); `experiments/20261112-148-norm-class/` (PREREG, RESULTS section 1). Nothing was run for this lane before this file, except exact integer arithmetic on constants (the N4 numbers below and u0).

## Why
Every end-to-end fidelity number on main keeps Qwen3.8-27B's 16 full-attention layers (3, 7, ..., 63) in float64 (PR #124 RESULTS, PR #138 PREREG, PR #152 RESULTS "Not a fully integer layer"). Upstream's proved integer attention (`docs/model.md` 6: q, k, v clamped to 2,047, integer scores, max-subtracted shift, softmax table EX, floor-divided mean) has never been run on Qwen. Two unknowns decide the attention design for #35: whether Qwen's q, k, v (after its q/k RMSNorm and partial rotary) fit a 12-bit class at a fitted scale with acceptable per-head error, and what the narrower clamp that the attention sub-proof's `af-no-wrap-N4` admits at dh = 256 costs in accuracy.

## The N4 clamp, recomputed (exact integer arithmetic, not a measurement)
`vf_attention_shape.h`: Smax = dh x CLAMP^2, C = u0 << sh, and N4 refuses unless 6 Smax + 2 C + 3 x 65,536 < 2^32 = 4,294,967,296. `af-policy-C` admits C only with C + 65,536 <= 2^24, so the largest admitted C is 2^24 - 65,536 = 16,711,680.
- dh = 256, CLAMP = 2,047: 6 Smax = 6,436,161,024 > 2^32. Refused by N4 at every C.
- dh = 256, CLAMP = 1,665, C = 16,711,680: 6 x 256 x 1,665^2 + 2 x 16,711,680 + 196,608 = 4,258,137,600 + 33,423,360 + 196,608 = 4,291,757,568 < 4,294,967,296. Passes.
- CLAMP = 1,666 at the same C: 4,296,873,984 >= 2^32. Refused. So 1,665 is the largest clamp that passes N4 at every admitted C.
- At C = 0: CLAMP = 1,672 gives 4,294,213,632 (passes), 1,673 gives 4,299,351,552 (refused).
- With this lane's softmax table (expS = 12, rx = 8) u0 = 2,307 (least u with rne(4,096 exp(-u / 256)) = 0), so C = 2,307 x 2^sh <= 9,449,472 for every sh in the admitted 4..12; C1665 passes N4 at all of them.
Passing N4 is not admission: Qwen's attention is still refused elsewhere (dq != d, partial rotary, theta0, dh > 128 for `rotaryServed`; DQ-NE-D.md section 4). Only N4 is checked here, and only as arithmetic.

## Hypothesis
H1 (C2047): with q, k, v lowered by `docs/model.md` 6 steps 2 (clamp only), 3 and 4 at clamp 2,047 and the registered fit rule, every one of the 16 full-attention layers of the abliterated checkpoint meets PR #88's A2 per-head bar on PR #124's 10 frozen prompts. H2 (C1665): the same at clamp 1,665. Each is falsified by one failing layer. A failure is a valid result and a design input for #35 (C2047 fail: 12-bit q/k is too coarse for Qwen at dh = 256; C2047 pass and C1665 fail: the sub-proof needs a wider field budget at dh = 256 rather than a narrower clamp).

## Setup (fixed now)
**Checkpoint.** Abliterated: huihui-ai/Huihui-Qwen3.8-27B-abliterated@739e3c5b89849f6c238ce1e5b70008612ae42cdd for layers 17 to 63, on stock layers 0 to 16 (Qwen/Qwen3.8-27B@37561816e66b5b9153b1b64c10968c18c1e6f4a0), byte-identical between the two (PR #68 `runs/diff.json`), and stock embedding rows (identical), exactly as PR #124's abl leg. Weights streamed per layer by PR #88's `Ckpt` (HTTP range requests into memory), no checkpoint cache; every fetched tensor's sha256 in `runs/manifest-*.json`, compared afterwards with PR #124's committed manifests. No stock leg. No final norm, no lm_head, no logits.

**Prompts.** All 10 of PR #124's frozen prompts, read unchanged from `experiments/20261111-8-qwen-e2e-agreement/prompts-e2e.json` (1,461 tokens, longest p03-repeat-word 512).

**REF and open loop.** One float64 stream REF runs PR #88's forward unchanged (`layer_step`, with DeltaNet heads by `head_out(.., "REF")` in spawned workers as PR #124's `e2e.head_task`, imported unchanged) through layers 0 to 62, and to the input of layer 63. At each full-attention layer l in {3, 7, ..., 63} the REF input x_l is recorded (scratch, outside the repo) and both arms run open loop on that same x_l. REF continues with PR #88's float `attention` output, so no arm's error enters a later layer. Nothing here says anything about compounding, logits or tokens.

**What is lowered (both arms).** In `q1_forward.attention`, the projections, input RMSNorm, q/k RMSNorm (with gain 1 + w), partial rotary (64 of 256 dims, theta 1e7), the sigmoid output gate and o_proj stay float64 exactly as there. From the rotated q, k and v to the head output o:
1. Fold the score scale into q: qf = q_rot / 16 (1 / sqrt(256), an exact power of two), kf = k_rot, vf = v.
2. Exponents per layer (`scales/README.md` "The exponent of each cell" step 1, in-sample): with mx_q = max |qf| over all prompts, tokens, heads and dims of the layer (likewise mx_k, mx_v), E_x = the largest integer E with mx_x x 2^E <= CL, where CL is the arm's clamp.
3. Softmax shift per layer (registered rule, the per-layer form of "The exponent of each cell" step 3): a score s has exponent E_q + E_k, the table key has exponent rx = 8, so sh = E_q + E_k - 8. If sh > 12, sh := 12 and E_q := 8 + 12 - E_k (coarser q, as step 3 does). If sh < 4, sh := 4 and E_q := 8 + 4 - E_k (finer q; entries that no longer fit are clamped and counted). 4 and 12 are the bounds `af-policy-sh` admits. Every adjustment is logged.
4. qw = RNE(2^E_q qf), kw = RNE(2^E_k kf), vw = RNE(2^E_v vf) (round half to even, numpy `rint`); q = clamp(qw; CL), k = clamp(kw; CL), v = clamp(vw; CL).
5. `docs/model.md` 6 step 4, integers, causal, GQA (query head h reads key-value head floor(h / 6)): s_ij = sum_c q_i[h][c] k_j[g][c]; m_i = max_{j<=i} s_ij; u_ij = floor((m_i - s_ij) / 2^sh); e_ij = EX[u_ij] if u_ij < u0 else 0, EX[u] = rne(2^12 exp(-u / 2^8)) computed as in section 4 (float64, numpy `rint`), u0 = 2,307; Z_i = sum_j e_ij; acc_i[c] = sum_j e_ij v_j[g][c]; o_i[h][c] = floor((2 acc_i[c] + Z_i) / (2 Z_i)).
6. De-scale: o_arm = o / 2^E_v (float64), then the float gate and o_proj as in `attention`.
Score and accumulator sums may be evaluated with float64 BLAS on integer-valued arrays, because every product and partial sum is an integer below 2^53 (|s| <= 256 x 2,047^2 < 2^31; |acc| <= 512 x 4,096 x 2,047 < 2^33); the code checks this against Python / int64 integer arithmetic on the debug fixture and on synthetic arrays, and asserts that every score and accumulator array is integer-valued and below 2^52 in the registered run.

**Arms.** **C2047**: CL = 2,047 (upstream's clamp; N4 refuses it at dh = 256). **C1665**: CL = 1,665 (passes N4 at every admitted C). Same fit rule, same code; only CL changes.

**Float reference for the metric.** o_float: the float64 softmax head output of `attention` before the gate, on the same q_rot, k_rot, v (same arithmetic as PR #88: scores / 16, causal mask, max-subtract, exp, normalise).

## Metric
Per (arm, layer, prompt, head h in 0..23), over all tokens of the prompt (Frobenius norm over tokens x 256 dims):
- **rel_y (the bar's metric)** = ||o_arm[h] - o_float[h]|| / ||o_float[h]||.
Per (arm, layer, prompt) and per (arm, layer), recorded with exact counts and denominators:
- over-clamp fraction of qw, kw, vw entries (|x| > CL), with the denominators;
- max |qw|, |kw|, |vw| at the fitted scale; E_q, E_k, E_v, sh and any sh adjustment;
- max |s| over all scores against Smax = 256 x CL^2;
- count of e_ij = 0 from u_ij >= u0 (descriptive);
- descriptive, no bar: rel of the layer's attention contribution after gate and o_proj, ||mix_arm - mix_float|| / ||mix_float||;
- per-layer seconds and the run's peak RSS.
Per layer and arm, the spread is over the 240 (prompt, head) pairs: median, max, min, and the count over 0.01 and over 0.05.

## Acceptance threshold
PR #88's A2 bar, unchanged in its rel_y part: a layer passes for an arm iff median rel_y <= 0.01 and max rel_y <= 0.05 over its 240 (prompt, head) pairs. An arm PASSES iff all 16 attention layers pass and the determinism check below holds. (A2's rel_S part and honest-class part concern DeltaNet state and do not apply to attention; over-clamp fractions are reported, not gated: in-sample fitting makes them 0 by construction except after a sh < 4 adjustment.)

## Kill criterion
- Compute: **75 minutes of elapsed time from the moment the heavy slot is granted** (logged as the first line of `runs/progress.log`), and a **compute hard stop at 2026-11-13T17:40:00Z** wall clock, whichever comes first. The run script's watchdog kills the job by pid at either. Time waiting for the lock counts against the hard stop. Neither moves after registration. Lane hard stop 2026-11-13T18:00:00Z.
- Memory: start only with MemAvailable >= 12 GB; the watchdog (poll every 2 s) kills the job if the job's process tree RSS exceeds 14 GB. Disk: stop if free disk drops under 21 GB (decimal), checked at start and after every layer. A 401 / 403 on a weight fetch: stop, no credential search.
- State (REF stream after every layer) is saved in scratch so a lost process resumes at the next layer with the same code; a resume is logged and is not a rerun.
- **Partial run.** If a stop cuts the run, RESULTS reports per-layer numbers for the attention layers done and no all-layer verdict (an arm with a failing layer among those done is reported as such; that cannot be undone by layers not run). There is no reduced layer set.

## Runs
Deterministic float64 and integer arithmetic, no seeds. A repeat of a deterministic computation gives identical numbers, so there are **no reruns for variance**; the registered result is the per-arm bar over all (prompt, layer, head) cells, and the spread reported is over (prompt, head) pairs per layer. **Determinism check:** at every attention layer, arm C2047 is computed a second time on p01 and p09 as separate calls; its integer o must be bit-identical, else no arm passes.
- Heavy work only through the shared gate: `flock <bigmem lock> fp-heavy.sh taskset -c 10-15 /usr/bin/time -v ...`, 6 cores, BLAS threads 6 in the main process, 6 spawned DeltaNet head workers with 1 BLAS thread each. Host shared and loaded; recorded in ENV.json.
- No exclusions.
- **Debug before the registered run (disclosed now).** New code is debugged only on PR #88's fixture "The capital of Italy is" (5 tokens, not in the suite) through stock layers 0 to 3, and on synthetic arrays (numpy `default_rng(0)`). Checks: the lane's float re-implementation of the attention mixer reproduces `q1_forward.attention` bit for bit on the fixture at layer 3; integer step 5 equals a pure Python-int reference on synthetic arrays (several T, sh, clamps); the RNE / clamp / counters on synthetic values with known counts; the fit and sh rule on synthetic maxima; save / load equality. Debug outputs on the fixture are committed as debug, not results. No registered prompt and no layer above 3 is touched before the registered run.

## Prior art
In this repo: upstream's integer attention and its sub-proof (`docs/model.md` 6, `vf_attention_shape.h`), proved for Maverick at dh = 128, clamp 2,047; the fit rule (`scales/README.md`); DQ-NE-D.md section 4 (N4 refuses dh = 256 at 2,047); PR #109 (q/k RMSNorm proof constraint, not used here); PR #67 (rotary tables, not used here); PR #88 / #124 / #138 / #152 (Qwen float64 forward, prompts, open-loop pattern; attention always float64). Outside: integer-only softmax and attention for transformers (I-BERT, Kim et al. 2021, polynomial i-exp; Softermax, Stevens et al. 2021, base-2 softmax with integer max subtraction), 8-bit attention quantisation studies (Q8BERT, LLM.int8() keeps attention matmuls in higher precision for outlier features; SageAttention, Zhang et al. 2024, INT8 Q/K with smoothing of K), and zkML systems that prove softmax by lookup (zkLLM, Sun et al. CCS 2024, tlookup with a fixed-point exp table; EZKL and Jolt-style lookup arguments). None of these reports an integer, max-subtracted, table-exponential attention at a 12-bit (or the N4-limited 1,665) clamp on a 27B hybrid model's real activations at head size 256. **New here:** upstream's exact integer attention arithmetic run open loop on all 16 full-attention layers of abliterated Qwen3.8-27B, at the upstream clamp and at the N4-limited clamp, against a fixed per-head bar.

## Amendments
