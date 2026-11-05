# RESULTS: 20261105-11-moe-topk-routing

Issue #11, cross-ref #35. PREREG committed first (8360dfc4, 2026-11-05T03:05Z), before any code. Code: `research/operators/moe_topk/`. Raw: `runs/`, `../../research/operators/moe_topk/evidence.json`. Measured, unreplicated, research security settings (target 10 bits), shared CPU VM pinned to 6 cores.

## Verdict: PASS (GO for the selection + normalization gadget). Aggregation by one-hot gather: NO-GO at real width (pre-registered rule; does not fail the gadget).

| | threshold | GLM 288/8 | DeepSeek 384/6 | status |
|---|---|---|---|---|
| H1 honest proofs, T = 4 | 10/10 per arm | 10/10 | 10/10 | PASS |
| H2 complete hostile provers + mutations, seed 1 | 100% per class | 36/36 | 36/36 | PASS |
| H2b unique satisfying routing, E = 16 | exactly 1, = reference | k=2: 1 of 256; k=3: 1 of 4,096 | (same contract) | PASS |
| H3 selection + normalization columns per token | <= 2^15 = 32,768 | 20,537 | 24,689 | PASS |
| H3 aggregation extrapolated to h = 4096 | <= 2^20 or NO-GO for one-hot dispatch | 9.52M | 9.51M | NO-GO (dispatch) |

## H1: honest proofs (n = 10 per arm, seeds 1..10)

| | GLM 288/8 | DeepSeek 384/6 |
|---|---|---|
| Accepted | 10/10 | 10/10 |
| Prove s, median (SD) [min, max] | 3.109 (0.106) [3.026, 3.340] | 3.170 (0.047) [3.110, 3.265] |
| Prove s without first run (n = 9), median [min, max] | 3.118 [3.074, 3.340] | 3.156 [3.110, 3.265] |
| Verify s, median (SD) [min, max] | 0.774 (0.016) [0.748, 0.801] | 0.866 (0.027) [0.832, 0.903] |
| Proof bytes, median [min, max] | 3,176,192 [3,175,664, 3,176,368] | 3,176,240 [3,175,536, 3,176,464] |
| Peak RSS | 578 MiB | 607 MiB |
| Product-oracle columns used (table 2^18) | 230,884 | 247,364 |
| Relations / terms | 465,416 / 1,024,624 | 499,496 / 1,106,496 |
| Selection + normalization columns per token | 20,537 | 24,689 |
| Aggregation columns per token (h = 16) | 37,184 | 37,152 |

Every one of the 80 tokens has an exact corrected-score tie between the rank-1 and rank-2 experts and an exact tie straddling the k boundary (generator invariant, asserted). In 70 of 80 tokens (35 of 40 per arm) the correction bias changes the selected set relative to unbiased top-k. The C++ witness reproduces `reference.py` (independent Python sort + big-int floor) indices, weights and outputs exactly for every token.

Timings are a 2^18-column statement at T = 4 on a shared VM: indicative only, not a performance claim.

## H2: hostile (seed 1 per arm, unchanged verifier)

Complete hostile prover: commits a full forged witness (every cell made as consistent as the forged choice allows), states the forged public output, replaces each row target with its local value, and the verifier checks against the forged statement. Same result for both arms:

| class | count | rejected | min violated relations (GLM / DeepSeek) |
|---|---|---|---|
| a1 wrong expert (k-th replaced by best unselected; first replaced and re-sorted; lowest-scored replaces k-th) | 3 | 3 | 1 / 1 |
| a2 tie order (rank 0/1 exact tie swapped; boundary tie, higher index chosen) | 2 | 2 | 1 / 1 |
| a3 bias leaks into weights (gathered score wire carries s+b) | 1 | 1 | 9,216 / 9,216 |
| a4 unnormalized weights (denominator claimed 2^16) | 1 | 1 | 32 / 24 |
| a5 duplicate expert (slot 1; last slot) | 2 | 2 | 2 / 2 |
| a6 k-1 selected (empty row) | 1 | 1 | 282 / 380 |
| a6 k+1 selected (one row selects two experts) | 1 | 1 | 2 / 2 |
| a7 public mutations vs honest proof (s selected, s unselected, b, X, y twice) | 6 | 6 | n/a |
| a8 bit flips (10), truncations (5), trailing byte | 16 | 16 | n/a |
| a8 other transcript label (DeltaNet wide) | 1 | 1 | n/a |
| a8 honest proof vs k-1 and k+1 statements | 2 | 2 | n/a |
| total | 36 | 36 | |

Note on a2 (ranks 0/1 swap): the forged public output equals the honest one (equal corrected score, weights and expert outputs move together, the sum is unchanged), so this attack forges the routing witness, not the output; it is still rejected. Every other forged class changes the stated output.

## H2b: relation-level uniqueness (no proof)

E = 16, seed 1, two adjacent exact ties in the top k + 1 for both fixtures. Every ordered k-tuple with repetition was lowered as one-hot rows with honest weight/output cells for that choice, and all relations evaluated: k = 2, 256 tuples (240 distinct), 1 satisfying; k = 3, 4,096 tuples (3,360 distinct), 1 satisfying; both equal the reference routing.

## H3: cost

Selection + normalization per token is E (3k + 45) + 57 k + 26 (k - 1) + 19 + k columns (exact for both arms): linear in E, dominated by the 26-bit threshold range per expert (16 more for the score range). At the real shapes it fits the 2^15 budget with 37% (GLM) and 25% (DeepSeek) headroom.

Aggregation by one-hot gather is k h (E + 1) + 12 h columns per token, 9.52M (GLM) and 9.51M (DeepSeek at h = 4096; its real width 5120 gives 11.9M) at real width: about 9x over the pre-registered 2^20 line. Per the pre-registered rule, dispatch must move to a lookup / memory-argument design (gather expert rows by the proved index `p_m` from a committed expert-output table).

## Amendments to report (also in PREREG "Amendments")

See PREREG A1. No threshold, seed or run change.

## Not shown

Score nonlinearity and gate matmul, expert FFNs, FP8/FP4, GLM group stage (config n_group = 1), DeepSeek vision bias and k = 1 non-normalization, DeepSeek weight placement (before w2), fidelity, production security, Lean, GPU. Hostile classes are sampled, not exhaustive; the uniqueness argument is written in the README and brute-forced at E = 16 only.
