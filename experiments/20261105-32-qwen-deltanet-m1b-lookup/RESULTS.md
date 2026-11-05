# RESULTS: 20261105-32-qwen-deltanet-m1b-lookup

Issue: #32 (tracking; operators #35, state-commit #34). PR: #63 (draft). PREREG: bc38a37a, the first commit on the branch.
All numbers are **measured and unreplicated**. They come from one host and one run set, with no independent review yet.

**Verdict against the registered threshold: PASS** (H1, H2 and H3 all pass). Under the PREREG this means **GO for M2 design**. M2 itself was **not started** by this lane; that decision is Sol's.

Code and receipt: [research/operators/qwen_deltanet_lookup/](../../research/operators/qwen_deltanet_lookup/). `record.py` regenerates everything. `evidence.json` holds the commands, exit codes, timings and SHA-256 of each source.
Raw data:
- `runs/honest.jsonl`
- `runs/hostile-seed1.jsonl`
- `runs/h3b-r3.jsonl`
- `runs/ranges-twolimb.json` (H3a, from `ranges_twolimb.py`, copied unchanged from PR #52 0447df03)

## What was built

`lookup.h` composes RNG, the approximate range check of `blocks/iop/rng.h` together with its LKP digit lookup, with the M1 wide product oracle (`research/operators/qwen_deltanet/product.h`). Everything sits in **one** proximity-test group, in this order:
1. Product oracle a, b, c (toy PSC).
2. The wide affine relations.
3. RNG: Theta, then the digits and multiplicities messages, then LKP and the key claim.
4. RNG's batched row (BAT-sigma).
5. One IOPP.

The plan (`lookup_size`) counts:
- the RNG round (`plan_rng`)
- the SEND of digits and multiplicities
- the lookup (`plan_lookup`)
- RNG's equations (`plan_bat_sigma`)
- every relation and RNG claim in `plan_iopp`

The verifier is `lookup_decide`.

**How range cells are tied to product columns.** RNG's packed matrix is laid directly on row a of the product oracle: lanes = 1 and one LaidBlock, a 16-column matrix with 4,192 rows of cells padded to 8,192. So the integers RNG range-checks are the same committed cells that the affine relations read. No wiring relation is needed, and none can be dropped.

**The range cells.** Each of the following is one range cell, checked by RNG with |x| < 2^23 proven:
- S' (16,384 per token)
- M (128 per token)
- delta_lo and delta_hi (128 each per token), with delta = 2^18 delta_hi + delta_lo

Floor remainders are still exact bit decompositions, as registered.

The stage schedule is the M1 one: log-length 21, log-n 22, stages {1,1,21,21},{0,0,21,21}. It held at its first try at full shape.

## Kill criterion

**Not triggered.** The first honest 128 x 128 proof was accepted at 04:58Z, before the 05:52Z deadline. The table is 2^21 entries (limit 2^22). Peak RSS is 4.43 GB (limit 12 GB).

## H1: honest proofs (threshold 10/10)

Fixtures use the M1 recipe unchanged: seeds 1..10, R1, 64-token warm-up. Each seed runs as its own sequential process, pinned to 6 cores. The C++ lowering matches reference.py cell by cell for all seeds.

| metric | n | median | SD | min | max |
|---|---|---|---|---|---|
| accepted | 10 | | | **10/10** | |
| prove (s) | 10 | 39.18 | 0.44 | 38.79 | 40.09 |
| prove without first run (s) | 9 | 39.13 | 0.38 | 38.79 | 39.77 |
| verify (s) | 10 | 7.15 | 0.09 | 7.06 | 7.32 |
| proof bytes | 10 | 25,411,392 | 313 | 25,410,848 | 25,411,968 |
| peak RSS (KB) | 10 | 4,433,844 | 4 | 4,433,832 | 4,433,848 |

**H1: PASS.**

### Statement size vs M1 (#47)

| | M1 (#47, bit ranges) | M1b (this, RNG/LKP) |
|---|---|---|
| product table | 2^22 | 2^21 |
| product columns used | 2,338,816 | 1,141,248 (1,074,176 gates and remainder bits, plus 67,072 range cells); laid out to 1,310,720 because the range region is aligned |
| product columns per state cell per token | 35.7 | 17.4 |
| linear relations | 4,761,088 | 2,231,808 |
| relation terms | 11,430,400 | 5,174,272 |
| RNG digits | none | 2 x 8,192 cell rows x 10 combinations = 163,840 entries (2.5 per state cell per token), in their own 2-row message |
| prove median | 51.43 s | 39.18 s (-24%) |
| verify median | 11.63 s | 7.15 s (-39%) |
| proof | 50.37 MB | 25.41 MB (-50%) |
| peak RSS | 6.73 GB | 4.43 GB |

**Per-cell accounting.** For each state cell and token, 17.4 product columns break down as (counted from the builder: 268,544 non-range columns per token, plus range cells):
- 4 product gates (decay, memory read, update, output)
- 12 remainder bits (exact floor)
- 1 range cell
- the per-column M, delta and o sites amortised (about 0.4)

The 19 range bits of S' are gone. **The 12 remainder bits are now the dominant cost.** The digits are reported separately and are not added into the 17.4.

M1 ran unpinned and M1b pinned to 6 cores, both on the same shared VM. The core count does not matter here: the CPU prover runs on one thread (independent review measured 99% CPU, i.e. one core, for an M1b honest run under taskset -c 0-5). Most of the gap follows from the halved table (2^21 vs 2^22) and relation count. All timings are indicative only.

## H2: hostile proofs (threshold 100% per class)

Seed 1, real shape. For complete hostile proofs, the prover commits the tampered witness with every product gate preserved and replaces each linear row's target with its true local value (#19 style). The verifier is unchanged.

Classes c9 (limb) and c10 need an out-of-window cell. For those, the hostile prover uses `rng_prove_research` mode 1, a research copy of `rng_prove` that wraps an out-of-window combination back into [-D, D). That is the only way to send in-range digits for it. The number of wrapped combinations is logged per attack in `hostile-note` lines.

| class | what | rejected |
|---|---|---|
| c1 state | private S_1[0,0] += 1; S_3[0,0] += 1 | 2/2 |
| c2 floor-preserving | S_2[0,0] += 1, remainder bit -= 2^F, range cell moved too | 1/1 |
| c3 decay | gate operand += 1; public a_1 += 1 | 2/2 |
| c4 beta | gate operand += 1; public beta_1 += 1 | 2/2 |
| c5 floors | M[0] += 1 with remainder -= 2^2F (range cell moved); delta[0] += 1 with remainder -= 2^F (delta_lo moved) | 2/2 |
| c6 range | remainder bit flipped; one RNG low digit moved by 1 on the honest witness | 2/2 |
| c7 public | S0, k, v, q, o_4, S_4 mutations | 6/6 |
| c8 bytes | 12 bit flips, 9 truncations, 1 trailing byte, 1 wrong transcript label (M1's) | 23/23 |
| c9 limb | delta_lo += 32 x 2^18 with delta_hi -= 32 (identity holds, 0 violated relations, 5 combinations wrapped); delta_hi += 1 alone; delta_lo += 1 alone | 3/3 |
| c10 out of range | S_2[0,0] += 2^24 with its range cell, remainder lowered by 2^(F+24) (7 combinations wrapped) | 1/1 |

**Total: 44/44 rejected (810 s). H2: PASS.**

The attacks that matter most for this lane:
- **c9a** is the limb-recombination tamper. Every linear relation still holds on the tampered table, so only RNG can catch it, and it does.
- The **c6 digit** attack shows that RNG's own equation binds the digits on the honest witness.

## H3: range (threshold (a) 20/20 fit, (b) 5/5 R3 windows proved)

**(a)** This re-runs #52's `ranges_twolimb.py` unchanged: the M1 realistic suite, F = 12, 1,024 steps. Result: **20/20 fit**.
- In R3, max |delta| = 422,167 splits into |delta_hi| <= 1, and max |S| = 125,548.
- Worst divergence from float64 is 0.032.

By #52's Amendment A2, this re-derives M1's ranges and adds no evidence by itself.

**(b) New.** For each R3 seed, the test proves the T = 4 window ending at the first step where |delta| >= 2^18. That is exactly where M1's relation could not hold. **5/5 accepted**:

| R3 seed | window (steps) | max abs delta | max abs v | max abs S | prove s | verify s |
|---|---|---|---|---|---|---|
| 1 | 299..302 | 291,511 | 371,763 | 77,616 | 39.06 | 7.30 |
| 2 | 156..159 | 298,632 | 354,411 | 70,488 | 39.29 | 7.35 |
| 3 | 142..145 | 337,617 | 452,427 | 75,605 | 39.26 | 7.18 |
| 4 | 117..120 | 422,167 | 494,213 | 125,548 | 39.40 | 7.21 |
| 5 | 32..35 | 285,196 | 551,506 | 69,123 | 38.75 | 7.12 |

**H3: PASS.**

## Soundness note (argument, not a proof)

**What RNG proves.** For every range cell, |x| < 2D = 2^23. This is an approximate check: honest cells meet |x| < 2^18, so the slack is 32x. The error is 2^-N with N = 10 combinations at these research settings (target 10 bits).

**No wrap.** With cells under 2^23 and admissible public inputs (|k|, |q| <= 2^F; a, beta in [0, 2^F]; |v|, |o| < 2^31), the largest relation magnitudes are:
- |a P| <= 2^12 x 128 x 2^23 x 2^12 = 2^54
- |k delta| <= 2^12 x (2^41 + 2^23)

Both are below p, so each relation holds over the integers.

**Unique floors.** Each remainder is exactly F or 2F bits (forced booleans). Each floor n = d q + r with 0 <= r < d therefore has one integer solution. The range check only has to rule out wrap, and 2^23 does that.

**Limbs.** delta_lo is not proven to lie in [0, 2^18), only |delta_lo| < 2^23. So (delta_hi, delta_lo) is not a unique split, but delta itself is unique because it is a floor quotient. The limbs are only a range device, and the recombined delta is what the gates read.

**Precondition.** `admissible()` is a check on the public statement. It is not a relation.

## Deviations from PREREG

- PREREG said the range cells form "ONE RNG matrix of k = 16 columns". That is what ran: 8,192 padded rows x 16 columns.
- c6 used one remainder-bit flip and one RNG digit move, as registered.
- The cell-to-column formula in the PREREG text was base + c m + i. The code uses range cell k at base + k, laid i-low, which is the same mapping.
- No amendments were needed.

## Open risks

- **Exact remainders now dominate.** 12 of the 17.4 columns per cell are remainder bits. The next saving is to make remainders lookup-exact: direct LKP keys on product cells, a 2^12 table. That is not done here.
- **`rng_prove_research` is a research copy of rng_prove.** It exists only to construct hostile proofs. The honest path uses the same logic as rng_prove with __int128 sums, and the verifier is the library's `rng_verify` unchanged. It needs independent review.
- **Approximate range security.** At target 10 bits, N = 10. Production needs N about 128 or more, which means about 12.8x more digits (still small next to the product table). The RNG soundness argument in rng.h is argued on paper and not refereed.
- **Synthetic inputs.** Gate, conv and norm producers are not proved. Real Qwen post-conv v may differ from R3.
- **Hostile tests are sampled**, not exhaustive. One host, unreplicated, shared loaded VM.
