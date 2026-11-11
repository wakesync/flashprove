# RESULTS: 20261111-8-ref-divergence

**Verdict: PASS vs the pre-registered rule, in all 6 cells (BF16 and FP8, F = 12 / 14 / 16), 50 of 50 checks each. Measured, unreplicated, CPU, no proof. Read section 3 before using the PASS: it is a weak statement by construction, and for the FP8 arm it is close to vacuous.**

Plain summary: we wrote down exactly what "BF16 reference" and "FP8 reference" mean, and compared the committed Qwen integer operator relations of PR #67 (six table functions, the four-tap conv, the L2 and RMS norms, the rotary) with each reference on real-valued inputs that were frozen by hash before any evaluation code existed. On the held-out inputs, the integer relations never differ from a reference by more than 1.56 times that reference's own rounding error. The ratio is about 1.0 against FP8, because FP8's own error is 10 to 100 times larger than the integer error and swamps it. Outside the integer domain (stress inputs) the BF16 comparison fails by up to 337x, because the integer relations clamp their inputs. Nothing here concerns real weights, whole models or token agreement.

## 1. What was registered and run

- PREREG `PREREG.md`, first commit `b25e590` alone. Splits frozen in `a0c5f54` (`splits/MANIFEST.json`, manifest SHA-256 `503feebe613951d7ae83fd8844eacfad651416e12b5d8b7ebe2e430c724a5147`) before any evaluation code was committed or run. Harness `b056d2d`; FP8 scales frozen from calibration in `33cf923`; the held-out run was then run once (`fa06936`).
- Reference definitions are in PREREG "Reference definitions" and implemented in `refs.py`:
  - **BF16**: 8-bit exponent, 7 stored mantissa bits, RNE from float64, subnormals kept, no saturation (overflow counted; 0 occurred). Inputs and outputs rounded to BF16, compute in FP32, sequential FP32 accumulation, rotary cos/sin computed in FP32 and rounded to BF16.
  - **FP8**: OCP OFP8 E4M3 (E4M3FN), max 448, RNE, satfinite, per-op per-role FP32 scale s = 448 / amax with amax over the whole calibration split (delayed scaling), frozen in `runs/fp8-scales.json`. Dequantize in FP32, then compute as the BF16 arm, output to BF16. E5M2 is not studied.
  - **FP64**: float64 numpy, the "exact" proxy for denominators.
- Integer pipeline conversion: X = RNE(x * 2^F), clamped to the relation's domain (counted). Output y / 2^F.
- Rule: cell (arm, F) passes iff R_max = max|int - ref| / max|ref - fp64| <= 2 for all 10 ops on all 5 held-out runs.

Checks done before the registered run:
- Kill check: `xcheck.py` builds the unchanged `research/operators/qwen_ops/reference_crosscheck.cpp` and `refs.py` reproduces all **150 / 150** C++ fixture cases (19,500 output words, all five operator families, F 12/14/16, seeds 1..10). `runs/crosscheck.json`.
- Format self-test `test_formats.py` -> `runs/format-selftest.json`: BF16 rounding equals an independent bit-level RNE on 250,000 values; E4M3 rounding equals an enumerated-table rounder on 20,000 random values plus every representable value and every midpoint; hand cases for saturation and underflow.
- Debug only on seed 9001 (not a registered seed, output in ignored `work/`). The debug run surfaced one counter bug (FP8 saturations were counted after rounding, so 448 < |v| < 464 was missed); it was fixed in `0b0ae04`, before calibration. No metric definition, reference or rule changed.

## 2. Held-out results (decision split)

5 runs per cell (seeds 1001..1005). Per run: nonlinear 4,096 scalars per function, conv 1,024 outputs, l2 8,192, rms 16,384, rotary 4,096 rotated coordinates. Raw rows: `runs/heldout.jsonl` (300 rows). Aggregates: `runs/summary.json`, full table `runs/summary.md`.

| cell | checks R_max <= 2 | verdict | worst op (seed): R_max |
|---|---|---|---|
| BF16, F12 | 50 / 50 | PASS | l2 (1003): 1.55 |
| BF16, F14 | 50 / 50 | PASS | l2 (1003): 1.40 |
| BF16, F16 | 50 / 50 | PASS | rms (1001): 1.34 |
| FP8, F12 | 50 / 50 | PASS | decay-one (1001): 1.04 |
| FP8, F14 | 50 / 50 | PASS | rms (1002): 1.04 |
| FP8, F16 | 50 / 50 | PASS | rms (1002): 1.04 |

Selected per-op R_max, median [min, max] (sample SD), n = 5 runs:
- BF16 F12: l2 1.52 [1.47, 1.55] (0.033); rms 1.29 [1.26, 1.32] (0.023); decay-half 1.16 [1.08, 1.19] (0.043); silu 1.00 [0.89, 1.12] (0.088); conv 1.07 [0.98, 1.10] (0.049); rotary 1.02 [0.98, 1.07] (0.041).
- FP8 F12: every op between 0.96 and 1.04 at the extremes; e.g. rms 1.02 [0.99, 1.04] (0.017).

Context, held-out medians over 5 runs of the max abs error against FP64 (from `runs/summary.json`, printed by `context_table.py`):

| op | int (F12) | int (F16) | BF16 ref | FP8 ref |
|---|---|---|---|---|
| silu | 0.00422 | 0.00428 | 0.0277 | 0.293 |
| softplus | 0.00375 | 0.00384 | 0.0299 | 0.280 |
| sigmoid | 0.00102 | 0.000968 | 0.0026 | 0.0126 |
| decay-two | 0.00122 | 0.00115 | 0.00303 | 0.0203 |
| conv | 0.000423 | 2.6e-05 | 0.00333 | 0.0495 |
| l2 | 0.000572 | 0.000299 | 0.000803 | 0.00694 |
| rms | 0.00358 | 0.00336 | 0.0077 | 0.0758 |
| rotary | 0.000441 | 2.67e-05 | 0.00455 | 0.0384 |

Integer table functions do not improve with F (their error is set by the 1/256 input grid of the tables, as PR #67 already reported), conv and rotary do (one floor of 2^-F). The norms are limited by the 4,096-row coefficient table.

Counters on held-out (sums over 5 runs): integer clamps 0 and norm out-of-domain vectors 0 in every cell; BF16 overflows 0; FP8 saturations 2 (conv) and 1 (rotary) per F, FP8 underflow-to-zero 1 (conv).

Sign and argmax flips (reported, not part of the rule). Flips are counted between the integer output and the reference, so they mostly measure the reference's own noise near zero and near ties:
- BF16, F12: sign flips 3 / 5,120 conv outputs and 2 / 20,480 rotary coordinates, 0 elsewhere; argmax flips l2 17 / 320 vectors, rms 24 / 320, conv 0 / 1,280 chunks, rotary 0 / 320.
- FP8, F12: sign flips conv 38, rotary 38; argmax flips l2 130 / 320, rms 179 / 320, conv 20 / 1,280, rotary 24 / 320.
- The norm argmax flips are near-ties: a normalized 128- or 256-vector of i.i.d. entries has several entries within one rounding step of the maximum. They are not evidence of a routing-relevant disagreement; no routing operator (top-k) is in this set.

## 3. What the PASS does and does not mean

- By the triangle inequality R_max <= 1 + max|int - fp64| / max|ref - fp64|. So a cell passes whenever the integer pipeline's own worst error is at most the reference's worst rounding error. The rule tests "the integer relation is not a noticeably worse approximation than this reference format", not "the integer relation agrees with the reference".
- **FP8 arm: close to vacuous at these sizes.** FP8's own max error is 12 to 117 times the integer pipeline's at F12 (l2 and sigmoid lowest, conv highest; more at F16 for conv and rotary; table above), so int - fp8 is essentially fp8 - fp64 and R_max sits at 1.0 +- 0.04. The FP8 PASS says only that the committed integer relations are much more precise than an E4M3 W8A8-style recipe on these inputs.
- **BF16 arm: informative but loose.** The tightest margin is l2 at F12 (integer 0.000572 vs BF16 0.000803, R_max up to 1.55); rms is next. A threshold of 1.5 would have failed BF16 F12 on l2 in 4 of 5 runs (1.4653, 1.5205, 1.5523, 1.5306, 1.5007 for seeds 1001..1005; `runs/heldout.jsonl`). The threshold 2 was fixed before the run and is not moved here.
- Max abs error over a few thousand outputs is sensitive to single elements; R_rms is reported next to R_max for that reason (per-op medians, BF16 F12: 1.02 to 1.31; FP8: 1.00 to 1.01).
- The operators are PR #67's bounded relations: no epsilon, unit gain, no M2 isqrt norm, no DeltaNet state, no matmul. The inputs are synthetic Gaussians inside the integer domain, not activations of any model. Inputs within the domain were chosen so that no integer clamp happens; this is the regime the relations are defined for, not a property of real activations.
- The references are definitions of numerics written here, emulated in numpy; they are not a measurement of any serving engine, kernel library or GPU. FP32 transcendental functions are numpy's, not correctly rounded.
- One process per split, deterministic; "5 runs" are 5 seeds (5 independent input draws), not repeated timings.

## 4. Stress split (descriptive, no threshold)

Inputs at 3x the primary scale, no truncation (`runs/stress.jsonl`), so many inputs leave the integer domain and are clamped (e.g. 3,702 of 20,480 nonlinear scalars and 47,308 of 81,920 rms inputs over 5 runs).
- BF16 cells: 15 / 50 checks under 2 at every F. Failing ops: silu and softplus (R_max up to 337: the integer table domain ends at |x| = 8, so silu(x) is clamped near x = 8 while BF16 follows x up to about 25), decay-half (about 7), conv, l2, rms, rotary (about 130 to 315, from clamping inputs at |x| = 1). sigmoid, decay-one, decay-two stay under 2 (they saturate in the float function too).
- FP8 cells: 50 / 50 under 2, but for an uninformative reason: the FP8 scales come from the calibration amax (about 0.99 for unit-domain ops, 7.82 for the nonlinear scalar), so FP8 saturates at almost the same point as the integer clamp, and both are far from FP64.
- Reading: outside its domain the integer pipeline is wrong in the same way a saturating FP8 recipe is wrong. Domain admission (range checks on real activations, #32) is the precondition for every number in section 2.

## 5. Not established

- Any statement about Qwen3.8-27B or any model, real weights, deeper layers, whole-layer or whole-model fidelity, token agreement, first divergence, whole-reply agreement, perplexity or logit margins (all #8 items that need #5, #11 and checkpoint resources).
- The M2 / M3 DeltaNet lowerings measured in PRs #68, #74 and #88 were not re-measured; their float64 references are not replaced by these BF16 / FP8 definitions.
- E5M2, per-channel or per-block FP8 scaling, current (just-in-time) scaling, FP8 accumulation, tensor-core accumulation orders, and any specific engine's kernels.
- Sampling, routing (top-k) and index flips.
- Replication by another lane.

## 6. Reproduce

From the repository root (numpy 2.x, g++ 13; about 1 s of CPU per split):
```
python3 experiments/20261111-8-ref-divergence/splits.py --check
python3 experiments/20261111-8-ref-divergence/xcheck.py
python3 experiments/20261111-8-ref-divergence/test_formats.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 experiments/20261111-8-ref-divergence/harness.py calibrate
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 experiments/20261111-8-ref-divergence/harness.py run heldout
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 experiments/20261111-8-ref-divergence/harness.py run stress
python3 experiments/20261111-8-ref-divergence/summarise.py
python3 experiments/20261111-8-ref-divergence/context_table.py
```
`calibrate` rewrites `runs/fp8-scales.json` and `runs/calibration.jsonl`; the run rows carry a `cpu_s_seed` field that varies with the host, everything else is deterministic. ENV: `ENV.json`.

## Deviations from the PREREG

- None in definitions, splits, rule or run order.
- PREREG "Runs" says "pinned to at most 2 cores": runs used `taskset -c 14,15`.
- The FP8 saturation counter was corrected during debug (section 1), before any registered split was evaluated.
- PREREG lists max abs / RMS error of the integer pipeline vs FP64 as context only; the context table above was produced after the registered run by `context_table.py` from the committed summary, no new run.
