# GLM-5.3-Flash KDA head slice at model scale: CPU sweep, synthetic inputs

> **Status: pre-standards / exploratory. Every number in this file is measured, unreplicated.**
> The lane was spawned before the NORTH-STAR research standards (2026-11-03 21:31Z). There is no
> PREREG.md, no pre-registered threshold, and nothing here is a PASS/FAIL against one; the branch is
> standards-exempt in the loop ledger and that gap is recorded on the `glm-layer-scale` claim. No
> number here may be used as a public headline until an independent replicate lane reproduces it.
> Env manifest: `experiments/20261103-11-glm-kda-model-scale/ENV.json`. Revised 2026-11-04 to address
> the PR #42 review (see "Revisions after review" at the end).

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

Coverage caveat: the hostile provers attack **3 fixed sites per point** (the first rounded
quotient/remainder pair, the middle bit column, output coordinate 0), and the wrong-final-state
mutation touches only the first final-state cell. "231/231 rejected" is evidence that these
constraint kinds bind at those sites, not an exhaustive per-position test.

## Scaling vs table size [measured]

**Timing caveat.** Every `prove s` / `verify s` value in this section and the next two tables is a
**single run on a heavily contended VM** (end-of-sweep load about 33 on 16 vCPUs) and is **not
reproducible to better than about 2x**: the review rerun found rerun/original prove ratios of 0.57
to 1.16 at log_len 14..19, and d=128 T=1 12-bit at 38-41 s vs 63.2 s here. Use the n=10 repeat
table below ("Repeat timings") for seconds. Columns, proof bytes and RSS are deterministic (the
review rerun matched them exactly, RSS within 30 KB) and are the reliable quantities.

Per log_len, the median (min..max) is **across the different configurations** at that size
(n = points, mixed d/T/bits; one run per point). It is not repeat variance. See the per-point
table in `results/summary.md`.

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

d = 128 (the configured head shape) [measured; seconds are single contended runs, see caveat;
fidelity columns from `results/degeneracy-d128.json`]:

| tokens | bits | log_len | columns | prove s (1 run) | verify s (1 run) | proof bytes | RSS MiB | q zero | proved outputs zero | output rel L2 err (pooled) | output usable? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 4 | 19 | 418,816 | 16.12 | 1.686 | 20,160 | 1,451 | 100% | 100% | 1.00 | **no, degenerate (output identically 0)** |
| 2 | 4 | 20 | 837,632 | 21.60 | 3.311 | 21,192 | 2,848 | 100% | 100% | 1.00 | **no, degenerate (output identically 0)** |
| 4 | 4 | 21 | 1,675,264 | 45.47 | 7.193 | 21,648 | 5,634 | 100% | 100% | 1.00 | **no, degenerate (output identically 0)** |
| 1 | 8 | 20 | 799,744 | 29.95 | 3.613 | 21,264 | 2,750 | 66% | 55% | 1.30 | **no, degenerate (error > signal)** |
| 2 | 8 | 21 | 1,599,488 | 44.11 | 6.705 | 22,000 | 5,436 | 66% | 42% | 2.24 | **no, degenerate (error > signal)** |
| 1 | 12 | 21 | 1,164,160 | 63.22 | 10.372 | 21,968 | 4,617 | 11% | 8% | 0.080 | marginal (8% error) |

At 4 bits with `f = 2` fractional bits, every entry of the pre-scaled query (`|q| <= 1/sqrt(128) ~ 0.088` at
d=128, so `q * 2^2 + 0.5 < 1`) rounds to 0, so **the proved outputs at the three 4-bit d=128 points, including the largest
proved table (T=4, 1.68M columns), are identically zero**. Those points prove a valid execution of
the fixed-point algebra on the state path but say nothing about outputs. The "max abs err" of
0.31 to 0.49 at 4-bit is all final-state error. They remain valid **prover-scale** data points
(columns, bytes, RSS, time) because the table shape does not depend on the values.

Not run (table above 2^21, plan bytes only): d=128 with (T=8, 4b), (T=4, 8b), (T=8, 8b),
(T=2, 12b), (T=4, 12b), (T=8, 12b), and d=64 T=8 12b. 77 of 84 grid points proved, 0 failed.

The log_len 21 spread (41.6 to 78.1 s) and the jump between log_len 18 and 19 include VM
contention (load average about 33 on 16 vCPUs at sweep end; other lanes ran concurrently). Treat
the per-size numbers as indicative to within about 2x.

### Repeat timings, n=10 [measured, unreplicated]

`repeat.py`: 8 points (the 6 proved d=128 points plus one each at log_len 17 and 18), 10 runs each,
same seed-7 fixture (sha256 per row) and the same `run.bin` (sha256 in ENV.json). Runs are
interleaved round-robin, 3 at a time on pinned cores 8..10, at most 2 log_len-21 points at once.
The 1-min load average is sampled before and after every run (2.2 to 6.9 on 16 vCPUs, against
about 33 for the original sweep). Hostile provers are skipped (`--skip-hostile-provers`) because
they were exercised in the sweep and in the review rerun. The 24 static mutations ran and were
rejected in all 80 runs. 80/80 ok. Raw rows: `results/repeat-t10.jsonl`; summary:
`results/repeat-t10-summary.json`; table: `repeat_table.py`.

| d | T | bits | log_len | n ok | prove s median | SD | min | max | sweep single run | verify s median | SD | min | max | sweep single run | proof bytes | RSS MiB median (min..max) | load1 min..max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 32 | 1 | 12 | 17 | 10/10 | 2.38 | 0.09 | 2.22 | 2.48 | 2.92 | 0.240 | 0.019 | 0.203 | 0.269 | 0.229 | 16896 | 295 (295..295) | 2.7..5.5 |
| 64 | 1 | 8 | 18 | 10/10 | 4.96 | 0.28 | 4.63 | 5.53 | 4.82 | 0.732 | 0.064 | 0.673 | 0.906 | 0.716 | 18224 | 672 (672..672) | 2.8..5.5 |
| 128 | 1 | 4 | 19 | 10/10 | 10.57 | 0.48 | 9.83 | 11.29 | 16.12 | 1.752 | 0.086 | 1.631 | 1.845 | 1.686 | 20160 | 1374 (1374..1374) | 2.8..6.9 |
| 128 | 2 | 4 | 20 | 10/10 | 21.46 | 0.62 | 20.61 | 22.41 | 21.60 | 3.655 | 0.170 | 3.429 | 4.038 | 3.311 | 21192 | 2696 (2696..2696) | 3.0..5.9 |
| 128 | 1 | 8 | 20 | 10/10 | 20.84 | 0.86 | 20.09 | 22.79 | 29.95 | 3.434 | 0.179 | 3.219 | 3.772 | 3.613 | 21264 | 2603 (2603..2603) | 3.3..6.9 |
| 128 | 4 | 4 | 21 | 10/10 | 43.06 | 1.53 | 42.34 | 46.28 | 45.47 | 7.177 | 0.527 | 6.637 | 8.516 | 7.193 | 21648 | 5331 (5331..5331) | 2.7..5.9 |
| 128 | 2 | 8 | 21 | 10/10 | 43.35 | 2.05 | 41.90 | 48.09 | 44.11 | 7.119 | 0.515 | 6.677 | 8.214 | 6.705 | 22000 | 5144 (5144..5144) | 3.0..5.6 |
| 128 | 1 | 12 | 21 | 10/10 | 41.12 | 1.65 | 39.37 | 44.13 | 63.22 | 5.207 | 0.275 | 4.857 | 5.709 | 10.372 | 21968 | 4335 (4335..4335) | 2.2..5.6 |

- Repeat spread is tight: prove SD is 2 to 5% of the median. For **3 of the 8 points the
  original single-run prove value lies far outside the n=10 range**: d=128 T=1 4-bit 16.12 s vs
  9.83..11.29, T=1 8-bit 29.95 vs 20.09..22.79, and T=1 12-bit 63.22 vs 39.37..44.13. The 12-bit
  verify is 10.37 vs 4.86..5.71. Those single-run values were contention, and these medians
  replace them. The repeat medians agree with the review rerun (12-bit T=1: 38.1 to 40.5 s).
- Proof bytes are identical across all repeats and match the sweep.
- RSS is identical within a point. It is 5 to 6% below the sweep, which is consistent with the sweep's max RSS also
  including the hostile-prover passes (not separately measured).
- Same host class as the original, lower load. This is still not an exclusive machine, and the
  numbers have not been independently replicated.

Least-squares fit on points with log_len >= 14 [calculated from measured; time slopes are
inflated by contention: the review's lower-load rerun at log_len <= 19 gave prove 1.042 and
verify 1.113]:

- log2(prove_s) = 1.105 * log2(columns) - 16.864 (n=47)
- log2(verify_s) = 1.149 * log2(columns) - 20.688 (n=47)
- log2(max_rss_kb) = 0.974 * log2(columns) + 2.381 (n=47)
- log2(proof_bytes) = 0.092 * log2(columns) + 12.549 (n=47)

Same fit against the padded table length `2^log_len` the prover actually allocates:

- log2(prove_s) = 1.084 * log_len - 17.007 (n=47)
- log2(verify_s) = 1.120 * log_len - 20.707 (n=47)
- log2(max_rss_kb) = 0.950 * log_len + 2.341 (n=47)
- log2(proof_bytes) = 0.091 * log_len + 12.536 (n=47)

Measured RSS is about 3.3 KiB per real column at log_len 21, or 2.25 to 2.75 KiB per padded
column (2^21). RSS follows the padded length.

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
any width for these synthetic distributions. Smallest width with max abs error < 1e-2 on every
vector: **11 bits**. Over only 8 tokens; error growth over long sequences is not measured.

**The absolute threshold is not adequate for outputs.** The query is pre-scaled by 1/sqrt(d_k), so
float outputs are small: max |o| is 0.0234 over the d=128 fidelity vectors (0.0179 at the seed-7
sweep fixtures). An absolute error of 1e-2 is about half the output scale. Relative error and
quantization degeneracy [measured, `fidelity_rel.py` -> `results/fidelity-relative.csv`,
`results/fidelity-relative.txt`; same vectors and the same integer reference as above]:

| bits | worst output rel L2 err, pooled over tokens (all 224 vectors) | worst output rel L2 err, d=128 per-token worst | worst final-state rel L2 err, d=128 | q quantized to 0, d=128 | k quantized to 0, d=128 | integer outputs == 0, d=128 |
|---|---|---|---|---|---|---|
| 4 | 15.2 | 1.00 | 5.72 | 100% | 84% | 100% |
| 6 | 12.3 | 1.00 | 6.58 | 100% | 27% | 100% |
| 8 | 5.92 | 450 | 1.99 | 69% | 6.7% | 49% |
| 10 | 1.17 | 119 | 0.48 | 20% | 1.8% | 36% |
| 11 | 0.564 | 59.5 | 0.24 | 9.5% | 0.9% | 25% |
| 12 | 0.278 | 27.9 | 0.12 | 4.8% | 0.5% | 15% |
| 14 | 0.072 | 5.80 | 0.030 | 1.1% | 0.1% | 4.5% |
| 16 | 0.0168 | 1.20 | 0.0076 | 0.3% | 0% | 1.4% |
| 20 | 0.00106 | 0.075 | 0.00048 | 0% | 0% | 0.1% |

"Pooled" = ||o_int/2^f - o_f32|| / ||o_f32|| over all tokens' outputs of one vector, worst vector.
The per-token worst is much larger because some tokens' float outputs are tiny (it divides by
near-zero norms); both are in the csv. Smallest width with pooled output **and** state relative
L2 error below 0.1 on every vector: **14 bits**; below 0.01: **17 bits**. So by a relative
criterion none of the proved widths (4, 8, 12) is adequate for outputs: 4-bit outputs are
identically zero at d >= ~32, 8-bit error exceeds the signal, and 12-bit is 8% (T=1) to 16% (T=8)
pooled at the d=128 sweep fixtures (worst single token 52%).

## Extrapolation to one full GLM-5.3-Flash KDA layer [calculated, not run]

Config (pinned): 34 of 45 layers are KDA, 64 heads, head_dim 128 (`linear_attn_config`).
Assumptions, all explicit:
1. Heads are independent and the lowering is concatenated per head (`columns_formula(...,heads=64)`),
   one table. Real cost could be lower with batching per head or higher with layer glue.
2. Only the recurrence algebra above. NOT included: q/k/v/g/beta projections from the 4096
   hidden state, short convolution (kernel 4), l2norm, exp(gate), sigmoid(beta), output norm and
   gate, output projection, residual. These are the bulk of a layer's arithmetic.
3. The prover allocates the **padded** table `2^L`, `L = ceil(log2(columns))`, and measured RSS
   tracks the padded length. So the primary estimators scale by `2^L`, not by real columns.
4. Prove time and RSS follow either the power law fitted against `log_len`, or linear scaling by
   padded length from the largest measured point (d=128, T=4, 4-bit, 2^21 padded, 45.5 s single
   contended run, 5.5 GiB). Same CPU, single thread, target 10. These two bracket each other; the
   fit's slope is below 1 for RSS and above 1 (contention-inflated) for time.
5. Target 128 would multiply proof bytes ~18x (planner) and prover/verifier work by more.

Memory (deterministic inputs, the robust part) [calculated, `summarize.py` -> `results/summary.json`]:

| bits | tokens | columns | log2 | padded L | RSS GiB (linear, padded 2^L) | RSS GiB (fit vs log_len) | superseded: RSS GiB linear by real columns | superseded: RSS GiB fit by real columns | proof KB (fit) |
|---|---|---|---|---|---|---|---|---|---|
| 8 | 1 | 51,183,616 | 25.61 | 26 | 176 | 133 | 168 | 159 | 30.9 |
| 8 | 8 | 409,468,928 | 28.61 | 29 | 1,409 | 957 | 1,345 | 1,205 | 37.5 |
| 8 | 128 | 6,551,502,848 | 32.61 | 33 | 22,537 | 13,351 | 21,518 | 17,917 | 48.5 |
| 12 | 1 | 74,506,240 | 26.15 | 27 | **352** | 256 | 245 | 229 | 32.0 |
| 12 | 8 | 596,049,920 | 29.15 | 30 | 2,817 | 1,850 | 1,958 | 1,737 | 38.8 |
| 12 | 128 | 9,536,798,720 | 33.15 | 34 | 45,074 | 25,800 | 31,322 | 25,824 | 50.2 |
| 16 | 1 | 101,007,360 | 26.59 | 27 | 352 | 256 | 332 | 308 | 33.0 |
| 16 | 8 | 808,058,880 | 29.59 | 30 | 2,817 | 1,850 | 2,654 | 2,336 | 39.9 |
| 16 | 128 | 12,928,942,080 | 33.59 | 34 | 45,074 | 25,800 | 42,463 | 34,729 | 51.6 |

Time (from contended single-run sweep timings, order of magnitude only):

| bits | tokens | padded L | prove h (linear, padded) | prove h (fit vs log_len) | superseded: prove h linear by real columns | superseded: prove h fit by real columns | verify min per layer-token (fit vs log_len) |
|---|---|---|---|---|---|---|---|
| 8 | 1 | 26 | 0.40 | 0.64 | 0.39 | 0.76 | 5.7 |
| 8 | 8 | 29 | 3.23 | 6.11 | 3.09 | 7.58 | 58 |
| 8 | 128 | 33 | 52 | 123 | 49 | 162 | 1,300 |
| 12 | 1 | 27 | **0.81** | 1.36 | 0.56 | 1.15 | 12 |
| 12 | 8 | 30 | 6.5 | 13.0 | 4.5 | 11.5 | 127 |
| 12 | 128 | 34 | 103 | 261 | 72 | 245 | 2,826 |
| 16 | 1 | 27 | 0.81 | 1.36 | 0.76 | 1.62 | 12 |
| 16 | 8 | 30 | 6.5 | 13.0 | 6.1 | 16.1 | 127 |

The fit is extrapolated 5 to 13 doublings beyond the data, so treat each pair of columns as a
bracket, not a forecast. Note also that per the fidelity section, 8 and 12 bits are not adequate
for outputs by a relative-error criterion; at 14 to 17 bits the column count (and so `L`) grows
further.

**The verifier is not succinct in the statement here**: it re-evaluates the public affine rows,
which are as large as the table, so verify grows about linearly too, roughly 12 minutes per
layer-token at 12 bits (fit). That changes the deployment story at least as much as prove time.

Reading: even the recurrence alone for one layer, one token, at 12 bits is a 2^26.15 column table
that the prover pads to **2^27** (log_len 27). Scaling linearly by padded length from the largest
measured point gives about **352 GiB RSS** and about **0.8 h** single-thread prove at the toy
target (the fit against padded length gives 256 GiB / 1.4 h). From the n=10 repeat median
(43.06 s at the same 2^21 point) the linear-padded prove is 0.77 h. From honest-only RSS (5,331 MiB,
without hostile passes) the linear-padded memory is 333 GiB. That is more than 8x this VM's
30 GiB. RSS follows the padded length and is deterministic, so the memory bracket is the robust
part; the hour figures come from contended single-run timings and are order-of-magnitude only.
The earlier "~230 to 245 GiB / 0.6 to 1.2 h" scaled by real columns and ignored padding; it was
not a lower bound and is superseded. Memory, not time, is the first wall for this prover design. A full 34-layer
forward pass multiplies by 34 before counting projections or MoE.

## Verdict

All of this is pre-standards / exploratory, measured, unreplicated.

- **Prover scale** at the real head shape (d=128): one head of the fixed-point KDA recurrence was
  proved and verified on CPU at toy soundness (target 10) up to a 2^21 table (4 tokens at 4-bit,
  2 at 8-bit, 1 at 12-bit), with every exercised hostile prover (3 fixed sites per point) and
  every static mutation rejected [measured].
- **Fidelity at those points is poor**: at 4 bits the quantized query is all zero and every proved
  output is 0 (degenerate; this includes the largest proved table); at 8 bits output error
  exceeds the signal (pooled relative error 130% to 300%, degenerate); only the **12-bit, T=1**
  point has usable outputs, with 8% pooled relative output error (16% by T=8 on the fixture
  vectors; worst single token 52%). Absolute error 0.0023 at that point looks small only because
  outputs are about 0.018 in magnitude [measured]. A relative criterion (pooled output and state
  error < 10% on every vector) needs 14 bits, which was not proved at d=128 here.
- Per-layer, per-token proving with this CPU prover: **not feasible on this hardware**
  (memory: about 352 GiB at the padded 2^27 table for 12-bit, 1 token) [calculated]. Needs either a chunked/streamed prover or per-head proofs with
  aggregation, plus GPU before any model-scale claim.
- No public claim should be made from this PR beyond "fixed-point KDA head slice up to d=128
  proved on CPU at toy soundness with synthetic inputs; at 4-bit the outputs are identically zero
  and at 8-bit error exceeds signal, so only the 12-bit 1-token point (8% relative output error)
  carries meaningful outputs", and even that only after independent replication.

## Limits

Pre-standards: no PREREG, no pre-registered threshold. One seed. The sweep is one run per
point. Repeat variance (n=10) exists only for the 8 points in the repeat table; the other 69
points' seconds are single contended runs. Shared VM with other lanes running;
toy soundness target; synthetic inputs; public prepared inputs; numpy reference, not kernel
equivalence; projections/conv/norms not lowered; state continuity across separately proved
chunks not covered.

## Reproduce

```
python3 research/model-scale/fidelity.py
python3 research/model-scale/sweep.py --jobs 6 --first-core 8 --max-log-len 21 --target 10
python3 research/model-scale/summarize.py
python3 research/model-scale/fidelity_rel.py > research/model-scale/results/fidelity-relative.txt
python3 research/model-scale/repeat.py --binary <path to run.bin> --n 10 --jobs 3   # build run.bin with the ENV.json flags
python3 research/model-scale/repeat_table.py
```

Raw rows: `results/sweep_t10.jsonl`, `results/fidelity.csv`, `results/fidelity-relative.csv`,
`results/degeneracy-d128.json`, `results/repeat-t10.jsonl` (one row per repeat run); derived:
`results/summary.json`, `results/repeat-t10-summary.json`.

## Revisions after review (2026-11-04, PR #42 must-fixes)

1. Pre-standards / exploratory / measured, unreplicated banner (top).
2. n=10 repeat timings for 8 points (table above). Single-run sweep seconds are demoted with a
   caveat.
3. Extrapolation against the padded `2^log_len`. 12-bit T=1 is L=27: about 352 GiB / 0.8 h,
   replacing 245 GiB / 0.56 h.
4. Relative fidelity and quantization degeneracy (`fidelity_rel.py`). 4-bit and 8-bit d=128
   outputs are marked degenerate, and the Verdict is restricted to 12-bit T=1.
5. Env manifest at `experiments/20261103-11-glm-kda-model-scale/ENV.json`. The original
   `research/model-scale/ENV.json` is kept unchanged.
6. Results ledger tooling is absent on main, so there is no `research/results.yaml` entry (see
   the PR body).
7. origin/main merged (merge commit).

## Totals [measured]

- Grid points: 84; proved and verified: 77; failed: 0; plan-only (above 2^21): 7.
- Static mutations rejected: 1,848 / 1,848 (24 per point).
- Complete hostile proofs rejected: 231 / 231 (3 fixed attack sites per point).
- Sweep wall clock: 3,655 s, 6 points in parallel on a 16 vCPU shared VM.
- Largest proved table: 1,675,264 columns (2^21 padded), d=128, T=4, 4-bit.
