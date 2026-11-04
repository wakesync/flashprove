# RESULTS: 20261104-32-qwen-deltanet-m1b-twolimb

Verdict against the pre-registered threshold: **KILLED** (kill criterion: the RNG/LKP lookup smallness test was not wired into the research wide-product harness before the lane deadline). H1 and H2 were **not run**: there is no M1b proof. H3 (range, integer reference only) was run and **passes as an observation**, but it cannot carry the PASS verdict without H1/H2.

**Step 1 is therefore not a GO. Step 2 (M2, one full Qwen3.8 layer) was not started**, as the brief requires.

## What ran

`ranges_twolimb.py` (this directory). It reuses the M1 integer reference (`research/operators/qwen_deltanet/reference.py`) and the M1 realistic suite unchanged: R1..R4 x seeds 1..5 x 1,024 steps, from S = 0. Primary arm: F = 12 with delta and v split as x = 2^18 x_hi + x_lo, x_lo in [0, 2^18), required |x_hi| < 2^18; S, M, o single-limb (|x| < 2^18). Secondary arm: F = 10 with every value single-limb. The limb identity and the x_lo range are asserted on every cell of every step. Raw data: `runs/ranges-twolimb.json`. Wall time 12.3 s, CPU, synthetic, no proof.

## H3 (range): threshold 20/20 realistic runs inside the declared ranges at F = 12, including the 5 R3 seeds that failed M1

| arm | dist | max \|S\| | max \|M\| | max \|delta\| | max \|v\| | max \|delta_hi\| | max \|v_hi\| | runs fit | state divergence vs float64 (max abs, real units) |
|---|---|---|---|---|---|---|---|---|---|
| F12 two-limb | R1 | 4,730 | 3,767 | 14,591 | 20,513 | 1 | 1 | 5/5 | 0.020 |
| F12 two-limb | R2 | 10,350 | 8,409 | 29,618 | 41,290 | 1 | 1 | 5/5 | 0.020 |
| F12 two-limb | R3 | 125,548 | 78,657 | 422,167 | 552,727 | 1 | 2 | **5/5** | 0.032 |
| F12 two-limb | R4 | 19,015 | 13,937 | 32,332 | 41,565 | 1 | 1 | 5/5 | 0.021 |
| F10 single | R1 | 1,146 | 943 | 3,648 | 5,128 | n/a | n/a | 5/5 | 0.081 |
| F10 single | R2 | 2,566 | 2,102 | 7,405 | 10,322 | n/a | n/a | 5/5 | 0.083 |
| F10 single | R3 | 31,376 | 19,638 | 105,511 | 138,182 | n/a | n/a | 5/5 | 0.091 |
| F10 single | R4 | 4,732 | 3,494 | 8,071 | 10,391 | n/a | n/a | 5/5 | 0.082 |

Max values are over 5 seeds. (|x_hi| for negative x is 1 by floor convention even for small |x|.) F12 two-limb fits 20/20. F10 single-limb also fits 20/20, at a larger state divergence than F12: worst case 0.091 vs 0.032, a ratio of 2.85x; per distribution the ratio of the per-seed maxima is 3.95x (R1), 4.06x (R2), 2.85x (R3), 3.95x (R4) (all in `runs/ranges-twolimb-summary.json`, `divergence_ratio_F10_over_F12`). State S and memory read M stay below 2^18 in every F = 12 run, so the brief's choice (single-limb S and M) holds on this suite. The high limbs need at most 2 bits plus sign here, so a narrow lookup table would cover them.

**H3 as an observation: PASS.** Not a verdict: H1/H2 did not run.

**H3 is a re-derivation of M1, not new evidence** (added after review, PREREG Amendment A2). The script reuses the M1 reference and suite unchanged, and its per-run max |S|, |M|, |delta|, |v|, |o| and float64 divergence are identical to M1's `runs/ranges.json` in 240 of 240 cells (F12 arm vs M1 realistic, F10 arm vs M1's F = 10 sweep). M1's file was read at registration, and every M1 value there was below 2^19 (largest |v| 552,727), so once two limbs with |x_hi| < 2^18 were chosen, 20/20 fit followed by construction. The only new numbers are the high limbs (delta_hi, v_hi), which follow arithmetically from the delta and v maxima. Floor remainders, listed among the range-checked cells in the PREREG Metric, are **not checked** by `ranges_twolimb.py` (it calls the M1 step with check=False); they lie in [0, 2^F) by construction of the integer floor, which is an argument, not a measurement. The M1 heavy-tailed stress set (S1..S4), also named in the PREREG range metric, was not run here; M1's own file records S3 at F = 12 reaching max |S| 459,648 > 2^18, so single-limb S would not hold there (reference only, not a registered threshold).

### Spread across seeds (added after review)

The range script is deterministic: rerunning it gives byte-identical output apart from wall seconds, so there is no run-to-run spread. The spread below is across the 5 seeds of each distribution: median (min..max), sample SD. Source: `summarize_twolimb.py`, which reads the committed run file and writes `runs/ranges-twolimb-summary.json` (also has |o| and the limb fields).

| arm | dist | \|S\| | \|M\| | \|delta\| | \|v\| | divergence |
|---|---|---|---|---|---|---|
| F12 two-limb | R1 | 4,229 (3,615..4,730), SD 504 | 2,136 (1,399..3,767), SD 1,013 | 13,024 (12,016..14,591), SD 944 | 17,684 (16,888..20,513), SD 1,491 | 0.0020 (0.0011..0.0204), SD 0.0083 |
| F12 two-limb | R2 | 8,600 (7,398..10,350), SD 1,279 | 4,619 (3,043..8,409), SD 2,282 | 26,603 (24,571..29,618), SD 1,819 | 35,808 (34,282..41,290), SD 2,883 | 0.0022 (0.0014..0.0203), SD 0.0081 |
| F12 two-limb | R3 | 75,605 (70,488..125,548), SD 23,454 | 46,607 (14,864..78,657), SD 24,011 | 298,632 (285,196..422,167), SD 56,968 | 494,213 (354,411..552,727), SD 96,119 | 0.0126 (0.0091..0.0321), SD 0.0096 |
| F12 two-limb | R4 | 12,062 (8,547..19,015), SD 4,691 | 7,895 (3,656..13,937), SD 4,049 | 30,294 (25,668..32,332), SD 2,448 | 35,951 (31,540..41,565), SD 3,760 | 0.0028 (0.0017..0.0209), SD 0.0082 |
| F10 single | R1 | 1,060 (903..1,146), SD 113 | 530 (351..943), SD 252 | 3,258 (3,005..3,648), SD 236 | 4,421 (4,222..5,128), SD 373 | 0.0078 (0.0043..0.0807), SD 0.0327 |
| F10 single | R2 | 2,152 (1,848..2,566), SD 310 | 1,150 (763..2,102), SD 569 | 6,650 (6,145..7,405), SD 454 | 8,952 (8,570..10,322), SD 721 | 0.0089 (0.0053..0.0826), SD 0.0331 |
| F10 single | R3 | 18,887 (17,632..31,376), SD 5,856 | 11,684 (3,702..19,638), SD 5,996 | 74,658 (71,231..105,511), SD 14,240 | 123,553 (88,603..138,182), SD 24,030 | 0.0533 (0.0347..0.0914), SD 0.0216 |
| F10 single | R4 | 3,015 (2,135..4,732), SD 1,165 | 1,984 (916..3,494), SD 1,015 | 7,589 (6,421..8,071), SD 609 | 8,988 (7,885..10,391), SD 940 | 0.0112 (0.0065..0.0824), SD 0.0322 |

High limbs at F = 12 over all 20 runs: delta_hi is 1 in every run (SD 0); v_hi is 1 in 18 runs and 2 in 2 (R3 seeds 3 and 5), median 1, SD 0.31. The results-ledger metric `f12_max_abs_v_hi` (value 2) is a max over 20 runs; its `spread` field is null because the ledger schema has no field for this discrete count split, and the split is given in its `note` instead.

## H1, H2: not run

No two-limb relation was built in `test.cpp`, and the lookup smallness test (`blocks/iop/rng.h`, `blocks/iop/lkp.h`) was not integrated with `research/operators/qwen_deltanet/product.h`. That integration needs its own sizing (`size_run_at`-style group with the packed-cell, reads, digits and multiplicities messages), planning (`plan_rng`, `plan_lookup`, `plan_bat_sigma`), binding of an `RngShape`, and a tie between RNG's packed cells and the product oracle's columns. Today the two live in separate test fixtures (`blocks/iop/tests/rng_world.h` vs the toy product oracle) and nothing in `research/` composes them. That composition is the real engineering work of M1b, and it should get its own lane with a realistic budget. No prove/verify time or statement size versus M1 can be reported.

## Kill criterion

Triggered: "the RNG/LKP smallness test cannot be ... integrated ... within the lane deadline." Most of the lane's wall time went to reading the harness, RNG and LKP before registering. PREREG landed after the coordinator deadline, so only the range study ran. The PREREG commit (599dbaeb) is 2026-11-04T17:13:40Z against a 15:48Z deadline, so the kill criterion was already met at registration: KILLED was predetermined, not an outcome of any run (PREREG Amendment A2).

## Deviations from PREREG

- See PREREG Amendment A1 (scope cut at the deadline).
- See PREREG Amendment A2 (after review): true commit times of the PREREG (17:13:40Z) and A1 (17:15:27Z), KILLED predetermined at registration, H3 a re-derivation of M1, floor remainders not checked, stress set not run, spread added.
- Otherwise the range suite, seeds and bounds are as registered.
