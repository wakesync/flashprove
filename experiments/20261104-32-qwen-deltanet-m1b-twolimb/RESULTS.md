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

Max values are over 5 seeds. (|x_hi| for negative x is 1 by floor convention even for small |x|.) F12 two-limb fits 20/20. F10 single-limb also fits 20/20, at about 3x the F12 state divergence (0.091 vs 0.032 worst case). State S and memory read M stay below 2^18 in every F = 12 run, so the brief's choice (single-limb S and M) holds on this suite. The high limbs need at most 2 bits plus sign here, so a narrow lookup table would cover them.

**H3 as an observation: PASS.** Not a verdict: H1/H2 did not run.

## H1, H2: not run

No two-limb relation was built in `test.cpp`, and the lookup smallness test (`blocks/iop/rng.h`, `blocks/iop/lkp.h`) was not integrated with `research/operators/qwen_deltanet/product.h`. That integration needs its own sizing (`size_run_at`-style group with the packed-cell, reads, digits and multiplicities messages), planning (`plan_rng`, `plan_lookup`, `plan_bat_sigma`), binding of an `RngShape`, and a tie between RNG's packed cells and the product oracle's columns. Today the two live in separate test fixtures (`blocks/iop/tests/rng_world.h` vs the toy product oracle) and nothing in `research/` composes them. That composition is the real engineering work of M1b, and it should get its own lane with a realistic budget. No prove/verify time or statement size versus M1 can be reported.

## Kill criterion

Triggered: "the RNG/LKP smallness test cannot be ... integrated ... within the lane deadline." Most of the lane's wall time went to reading the harness, RNG and LKP before registering. PREREG landed after the coordinator deadline, so only the range study ran.

## Deviations from PREREG

- See PREREG Amendment A1 (scope cut at the deadline).
- No other deviations: the range suite, seeds and bounds are as registered.
