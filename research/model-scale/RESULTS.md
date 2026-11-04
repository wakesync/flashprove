# GLM-5.3-Flash KDA head slice at model scale: CPU sweep, synthetic inputs

Part of #11. Not model support. Not a checkpoint run. CPU only, synthetic inputs, no weights
downloaded, no GPU. Labels below: **[measured]** = read from `results/*.jsonl|csv|json`
produced by the scripts in this directory; **[calculated]** = arithmetic on measured numbers
or on the closed-form column count, never executed.

## What was proved

One KDA head of the pinned Transformers recurrence (`recurrent_kimi_delta_attention`, config and
modeling file pinned by SHA256 in `ENV.json`, same pins as `research/operators/glm_kda_slice`),
in signed fixed point, per token:

```
D = floor(S * g / 2^f)          mem = floor(sum_i D * k / 2^f)     A = v - mem
delta = floor(A * beta / 2^f)   U = floor(k * delta / 2^f)         S' = D + U
o = floor(sum_i S' * q / 2^f)
```

`bits` in {4, 8, 12}, `f = bits - 2`, every rounded/linear intermediate range checked to
`[-2^(bits-1), 2^(bits-1))`, overflow rejects (no wrap, no saturation). 4-bit reproduces the
PR19 staged-floor contract (asserted at sweep start). Inputs `g, k, v, beta, q` and the initial
state are public and already prepared (post-exp decay, post-l2norm, query pre-scaled); host-side
quantization is outside the proof. Lowered onto the same-oracle product table (product cells,
shared wires, sparse affine rows with at most 8 terms, bit decompositions) and proved with the
unchanged CPU prover (`EngineCpu`, single thread per point).

Grid: `d_k = d_v` in {2, 4, 8, 16, 32, 64, 128} x tokens {1, 2, 4, 8} x bits {4, 8, 12} = 84 points.
Points whose table exceeds 2^21 columns were not run (plan bytes only). One seed (7) per point.

**Security setting: target 10 bits, query work 6 bits.** This is a toy setting chosen so the
sweep fits in RAM and time. Prover/verifier work and proof size at a production target (128) are
NOT measured here; `plan_t128.txt` holds planner-only proof byte counts at target 128 (e.g.
387,280 bytes at log_len 21 vs 22,160 at target 10) [calculated by the unchanged planner].

## Per-point adversarial checks [measured]

Every proved point ran, after the honest prove + 3 verifies:
- 24 static rejections: 16 single-bit proof flips, 4 truncations, 1 trailing byte, wrong public
  output coordinate, wrong public final-state cell, cross-domain transcript label.
- 3 complete hostile provers: flipped private range bit, paired quotient/remainder change that
  keeps `p = 2^f q + r` (truncation toward zero instead of floor), and a full forgery of a wrong
  public output (statement and table both changed, local targets substituted).

The runner exits nonzero if any honest proof fails or any attack is accepted. Totals are in
the summary block at the end of this file.

## Scaling vs table size [measured]

Medians per log_len over every proved point at that size (n = points, mixed d/T/bits; one run
per point, so spread is across configurations, not repeated runs). See the per-point table in
`results/summary.md`.

| log_len | n | columns (min..max) | prove s median (min..max) | verify s median (min..max) | proof bytes median (min..max) | max RSS MiB median (min..max) |
|---|---|---|---|---|---|---|
| 8 | 1 | 160..160 | 0.00 (0.00..0.00) | 0.001 (0.001..0.001) | 8688 (8688..8688) | 30 (30..30) |
| 9 | 3 | 316..466 | 0.01 (0.01..0.01) | 0.001 (0.001..0.001) | 9104 (9104..9168) | 30 (30..30) |
| 10 | 5 | 520..1016 | 0.02 (0.02..0.02) | 0.002 (0.002..0.002) | 9904 (9808..10032) | 30 (30..30) |
| 11 | 7 | 1040..2032 | 0.04 (0.03..0.04) | 0.004 (0.003..0.005) | 10608 (10320..10736) | 30 (30..30) |
| 12 | 7 | 2080..4064 | 0.07 (0.07..0.08) | 0.008 (0.005..0.010) | 11744 (11584..11904) | 30 (30..30) |
| 13 | 7 | 4160..8128 | 0.14 (0.12..0.15) | 0.017 (0.010..0.023) | 12176 (12048..12336) | 30 (30..36) |
| 14 | 6 | 10480..14848 | 0.28 (0.26..0.29) | 0.032 (0.027..0.038) | 14224 (14048..14432) | 52 (46..55) |
| 15 | 6 | 19472..28672 | 0.60 (0.55..0.63) | 0.074 (0.054..0.079) | 15536 (15248..15696) | 101 (85..104) |
| 16 | 6 | 38944..55552 | 1.10 (1.07..1.14) | 0.145 (0.110..0.156) | 16348 (16184..16608) | 193 (170..198) |
| 17 | 6 | 74976..107520 | 3.27 (2.92..4.25) | 0.299 (0.229..0.593) | 16944 (16800..17024) | 371 (313..381) |
| 18 | 6 | 149952..215040 | 4.85 (4.53..5.00) | 0.708 (0.519..0.754) | 18160 (17968..18288) | 711 (615..739) |
| 19 | 6 | 293952..422400 | 15.31 (12.40..16.12) | 1.606 (1.081..2.352) | 20096 (19776..20448) | 1405 (1188..1451) |
| 20 | 6 | 587904..844800 | 21.52 (19.66..29.95) | 3.217 (2.244..3.613) | 21228 (21168..21488) | 2752 (2309..2852) |
| 21 | 5 | 1164160..1675264 | 45.47 (41.59..78.13) | 7.193 (5.924..10.372) | 21872 (21648..22000) | 5436 (4617..5634) |

d = 128 (the configured head shape) [measured]:

| tokens | bits | log_len | columns | prove s | verify s | proof bytes | RSS MiB | max abs err vs f32 |
|---|---|---|---|---|---|---|---|---|
| 1 | 4 | 19 | 418,816 | 16.12 | 1.686 | 20,160 | 1,451 | 0.421 |
| 2 | 4 | 20 | 837,632 | 21.60 | 3.311 | 21,192 | 2,848 | 0.485 |
| 4 | 4 | 21 | 1,675,264 | 45.47 | 7.193 | 21,648 | 5,634 | 0.311 |
| 1 | 8 | 20 | 799,744 | 29.95 | 3.613 | 21,264 | 2,750 | 0.0356 |
| 2 | 8 | 21 | 1,599,488 | 44.11 | 6.705 | 22,000 | 5,436 | 0.0424 |
| 1 | 12 | 21 | 1,164,160 | 63.22 | 10.372 | 21,968 | 4,617 | 0.00234 |

Not run (table above 2^21, plan bytes only): d=128 with (T=8, 4b), (T=4, 8b), (T=8, 8b),
(T=2, 12b), (T=4, 12b), (T=8, 12b), and d=64 T=8 12b. 77 of 84 grid points proved, 0 failed.

The log_len 21 spread (41.6 to 78.1 s) and the jump between log_len 18 and 19 include VM
contention (load average about 33 on 16 vCPUs at sweep end; other lanes ran concurrently). Treat
the per-size numbers as indicative to within about 2x.

Least-squares fit on points with log_len >= 14 [calculated from measured]:

- log2(prove_s) = 1.105 * log2(columns) - 16.864 (n=47)
- log2(verify_s) = 1.149 * log2(columns) - 20.688 (n=47)
- log2(max_rss_kb) = 0.974 * log2(columns) + 2.381 (n=47)
- log2(proof_bytes) = 0.092 * log2(columns) + 12.549 (n=47)

Measured RSS is about 3.3 KiB per column at log_len 21.

Prover time and RSS are close to linear in columns (slope near 1); proof size grows
logarithmically (about 0.6 KB per doubling at target 10). Verify time is also near linear here
because the verifier re-evaluates the public affine statement (the relation list is as large as
the table); it is not succinct in the statement size for this lowering.

## Fidelity vs bit width [measured, numpy float32 reference]

From `results/fidelity-summary.json` (224 vectors per width: 7 dims x 4 token counts x 8 seeds,
max |error| over final state and every output, in real units, against a numpy float32 port of
the pinned recurrence; not the publisher's fused kernels, not torch):

| bits | max abs err (all) | at d=128, T=8 |
|---|---|---|
| 4 | 0.573 | 0.485 |
| 6 | 0.208 | 0.208 |
| 8 | 0.0580 | 0.0580 |
| 10 | 0.0160 | 0.0160 |
| 11 | 0.00903 | 0.00903 |
| 12 | 0.00346 | 0.00346 |
| 14 | 0.000909 | 0.000909 |
| 16 | 0.000230 | 0.000230 |
| 20 | 1.37e-5 | 1.37e-5 |
| 24 | 9.42e-7 | 9.42e-7 |

Error halves per added bit as expected for floor rounding. No overflow and no clipped inputs at
any width for these synthetic distributions. Smallest width with max error < 1e-2 on every
vector: **11 bits**. Over only 8 tokens; error growth over long sequences is not measured.

## Extrapolation to one full GLM-5.3-Flash KDA layer [calculated, not run]

Config (pinned): 34 of 45 layers are KDA, 64 heads, head_dim 128 (`linear_attn_config`).
Assumptions, all explicit:
1. Heads are independent and the lowering is concatenated per head (`columns_formula(...,heads=64)`),
   one table. Real cost could be lower with batching per head or higher with layer glue.
2. Only the recurrence algebra above. NOT included: q/k/v/g/beta projections from the 4096
   hidden state, short convolution (kernel 4), l2norm, exp(gate), sigmoid(beta), output norm and
   gate, output projection, residual. These are the bulk of a layer's arithmetic.
3. Prove time and RSS follow the fitted power laws (or, as a lower bound, scale linearly from the
   largest measured point). Same CPU, single thread, target 10.
4. Target 128 would multiply proof bytes ~18x (planner) and prover/verifier work by more.

Two estimators: the fitted power law, and linear scaling from the largest measured point
(d=128, T=4, 4-bit, 1.68M columns, 45.5 s, 5.5 GiB). Single thread, target 10.

| bits | tokens | columns | log2 | prove h (fit) | prove h (linear) | RSS GiB (fit) | RSS GiB (linear) | verify min (fit) | proof KB (fit) |
|---|---|---|---|---|---|---|---|---|---|
| 8 | 1 | 51,183,616 | 25.61 | 0.76 | 0.39 | 159 | 168 | 7.1 | 30.9 |
| 8 | 8 | 409,468,928 | 28.61 | 7.58 | 3.09 | 1,205 | 1,345 | 77.5 | 37.5 |
| 8 | 128 | 6,551,502,848 | 32.61 | 162 | 49 | 17,917 | 21,518 | 1,873 | 48.5 |
| 12 | 1 | 74,506,240 | 26.15 | 1.15 | 0.56 | 229 | 245 | 10.9 | 32.0 |
| 12 | 8 | 596,049,920 | 29.15 | 11.5 | 4.49 | 1,737 | 1,958 | 119 | 38.8 |
| 12 | 128 | 9,536,798,720 | 33.15 | 245 | 72 | 25,824 | 31,322 | 2,884 | 50.2 |
| 16 | 1 | 101,007,360 | 26.59 | 1.62 | 0.76 | 308 | 332 | 15.5 | 33.0 |
| 16 | 8 | 808,058,880 | 29.59 | 16.1 | 6.09 | 2,336 | 2,654 | 169 | 39.9 |

The fit is extrapolated 4 to 12 doublings beyond the data and its slope above 1 is partly VM
contention, so treat the two columns as a bracket, not a forecast.

Reading: even the recurrence alone for one layer, one token, at 12 bits is a ~2^26 column table,
roughly 0.6 to 1.2 hours single-thread CPU prove and ~230 to 245 GiB RSS at the toy target,
about 8x this VM's 30 GiB. Memory, not time, is the first wall for this prover design. A full 34-layer
forward pass multiplies by 34 before counting projections or MoE.

## Verdict

- Feasibility of the KDA recurrence operator at the real head shape (d=128) and real-ish bit
  widths: **shown** for one head, 4 tokens at 4-bit, 2 tokens at 8-bit, 1 token at 12-bit,
  with every hostile prover rejected [measured]. At 12 bits the fixed-point output stays within
  0.0035 of the float32 reference [measured].
- Per-layer, per-token proving with this CPU prover: **not feasible on this hardware**
  (memory) [calculated]. Needs either a chunked/streamed prover or per-head proofs with
  aggregation, plus GPU before any model-scale claim.
- No public claim should be made from this PR beyond "fixed-point KDA head slice up to d=128
  proved on CPU at toy soundness with synthetic inputs".

## Limits

One seed, one run per point (no variance across repeats); shared VM with other lanes running;
toy soundness target; synthetic inputs; public prepared inputs; numpy reference, not kernel
equivalence; projections/conv/norms not lowered; state continuity across separately proved
chunks not covered.

## Reproduce

```
python3 research/model-scale/fidelity.py
python3 research/model-scale/sweep.py --jobs 6 --first-core 8 --max-log-len 21 --target 10
python3 research/model-scale/summarize.py
```

Raw rows: `results/sweep_t10.jsonl`, `results/fidelity.csv`; derived: `results/summary.json`.

## Totals [measured]

- Grid points: 84; proved and verified: 77; failed: 0; plan-only (above 2^21): 7.
- Static mutations rejected: 1,848 / 1,848 (24 per point).
- Complete hostile proofs rejected: 231 / 231 (3 per point).
- Sweep wall clock: 3,655 s, 6 points in parallel on a 16 vCPU shared VM.
- Largest proved table: 1,675,264 columns (2^21 padded), d=128, T=4, 4-bit.
