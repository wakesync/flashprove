# PREREG: 20261104-32-qwen-deltanet-m1b-twolimb
Issue: #32 (tracking; M1 was #33). Lane: Qwen M1b two-limb fix (CPU, synthetic). Date (UTC): 2026-11-04T17:15Z. Base commit: ce4ceef0 (main). Context: M1 (PR #47, experiments/20261104-11-qwen-deltanet-m1/) proved one 128 x 128 Gated DeltaNet head at T = 4 (H1 10/10, H2 40/40) but FAILED H3: at F = 12 delta reaches 422,167 > 2^18 and heavy-tailed public v reaches 552,727 > 2^18 (R3, 0/5 seeds). Decision recorded in the lane brief (approved 2026-11-04): keep F = 12, split delta and v into two limbs, keep S and M single-limb, and use the lookup-based smallness test (blocks/iop/rng.h + blocks/iop/lkp.h) instead of per-bit decomposition. Secondary arm: F = 10 single-limb, comparison only.

Registered before any M1b code. Inputs read at registration: M1 PREREG/RESULTS/ranges.json, research/operators/qwen_deltanet/ (reference.py, test.cpp, product.h), blocks/iop/rng.h, blocks/iop/lkp.h, blocks/iop/tests/rng_world.h, docs/format/11-1-machinery.md (smallness test).

## Hypothesis
At F = 12, representing delta and v as two signed limbs, x = x_hi * 2^18 + x_lo with x_lo in [0, 2^18) and x_hi in [-2^18, 2^18), and range-checking every limb, S and M with the lookup smallness test (RNG + LKP) on the same committed product oracle, gives a T = 4, 128 x 128 head relation that (H1) accepts honest proofs, (H2) rejects every pre-registered hostile class, and (H3) admits every M1 realistic-suite run, including R3, with no range violation.

## Metric
Relation: the M1 staged-floor recurrence unchanged (P, M, delta, S', o as in the M1 PREREG), with v and delta replaced by their limb recombination in every product gate and linear relation that reads them. Limb identity x = 2^18 x_hi + x_lo is one linear relation per cell. Range: S', M, x_lo, x_hi cells and floor remainders range-checked by RNG/LKP digits (window per docs/format/11-1-machinery.md); no per-bit columns for these cells. Out-of-range stays a rejected statement, never saturation.
Proof metrics per run: honest accept (bool), proof bytes, product-table entries, linear rows, RNG matrix rows/columns, CPU prove s, verify s, peak RSS KiB. Compared to M1 medians (prove 51.43 s, verify 11.63 s, 50,365,792 B, 2,338,816 gates, 4,761,088 relations).
Range metric (integer reference, no proof): for every M1 realistic run (R1..R4 x seeds 1..5, 1,024 steps, F = 12) and the M1 heavy-tailed set, max |S|, |M|, |x_hi|, |x_lo| and whether each is inside its declared limb range. Secondary arm F = 10 single-limb: same range table plus state divergence vs float64, reported only.

## Acceptance threshold
PASS (GO for Step 2 / M2) only if all hold:
- H1: honest proof of the T = 4 head at F = 12 with two-limb delta and v accepted for 10/10 seeds (seeds 1..10, M1 fixture recipe: R1 after a 64-token warm-up).
- H2: 100% rejection in every M1 hostile class c1..c8 with at least the M1 counts, plus (c9) limb tampering: x_lo += 2^18 with x_hi -= 1 (out-of-range low limb, identity preserved) for delta and for v (>= 2), and x_hi tampered alone (>= 1), on seed 1.
- H3: on the M1 realistic suite at F = 12 (R1..R4 x seeds 1..5 x 1,024 steps), every S, M, limb cell and remainder is inside its declared range in 20/20 runs, and the R3 seeds that failed M1 (5/5) now fit.
Anything else is FAIL. If the lookup smallness test cannot be wired into the research harness within the kill budget, the result is KILLED (not FAIL) and the range study H3 is still reported if it ran.

## Kill criterion
KILLED if any of: the RNG/LKP smallness test cannot be planned and bound with the wide product oracle on this host (plan refused, shape fault, or not integrated) within the lane deadline (2026-11-04 15:48Z per lane coordinator); table above 2^22 entries or peak RSS above 12 GB; total compute above 3 hours; host free disk below 3 GB. A partial (two-limb relation with bit-decomposition ranges, no lookup) may be reported only as an amendment, labelled as not the registered construction.

## Runs
Proof: 10 honest runs, seeds 1..10, sequential, one process each; timings n, median, SD, min/max, first run reported, CPU shared loaded VM, indicative only. Hostile: seed 1, classes above. Range: 20 realistic runs at F = 12 plus the F = 10 secondary arm (20 runs). Exclusions only for host faults (OOM by another tenant), rerun and reported. Security: #19 research test settings (target 10 bits, 6 work bits, deterministic toy coins); relation soundness, not production security.

## Prior art
- This repository: M1 (experiments/20261104-11-qwen-deltanet-m1/, research/operators/qwen_deltanet/), the KDA slices (research/operators/glm_kda_{slice,fixedpoint}/), the RNG smallness test (blocks/iop/rng.h, after Lyubashevsky-Nguyen-Seiler 2020/1448 section 2.7 and Gentry-Halevi-Lyubashevsky 2021/1397 section 3.4) and LKP lookup (blocks/iop/lkp.h, Papini-Haböck 2023/1284; Bootle et al. 2018/380). Limb splitting for range is standard in zkML (zkLLM CCS 2024, EZKL lookup decomposition, Jolt's lookup-based instruction decomposition, Expander). New here: limb splitting applied to the gated delta-rule recurrence on this harness with the approximate range check.
- Literature on the recurrence: Gated DeltaNet (Yang, Kautz, Hatamizadeh, ICLR 2025); Mamba2 decay parameterisation (Dao, Gu 2024).

## Amendments
- A1 (2026-11-04T17:20Z, after code): the lane deadline had passed when PREREG was registered. Scope was cut to the H3 range study, run on the integer reference with no proof (`ranges_twolimb.py`). The RNG/LKP integration, H1 and H2 were not attempted, so the kill criterion is triggered and the verdict is KILLED. H3 numbers are reported as an observation only. Thresholds were not changed.
