# RESULTS: 20261111-34-sb-unique-floor (issue #34)

Verdict: **FAIL** on every arm against the registered threshold. Reference arithmetic and a relation checker only: no proof, no backend, synthetic gates. Numbers are measured, unreplicated (deterministic integer arithmetic); volumes are counted, not measured.

Plain summary:
- Lowering L (exact remainder range, quotient range tied to the 2^18 contract, committed squared norms of k and q) gives a **unique witness on every floor checked**: 0 second witnesses over about 880,000 honest floors per arm and 202 adversarial admitted chunks per arm, at GB = 12 and GB = 18, C = 16 and 64. The #71 construction (M1b window |Q| < 2^23) on the same floors finds a second witness for **100%** of M and o floors at GB = 18 (327,456 of 327,456 at C = 16) and none at GB = 12, which reproduces #71 at D = 32.
- At **GB = 12** the proved numerator bounds fit Goldilocks (M and o 59 bits at C = 16, 61 at C = 64, plus the 19-bit window, under 64). The arm still FAILS: honest completeness is **19 of 20** runs, because on R3 seed 3 one honest delta leaves the single-cell 2^18 window that L registered (#71 carries delta as two limbs; L narrowed it).
- At **GB = 18** the arm FAILS the kill criterion: the proved M and o numerator bounds are **65 bits (C = 16) and 67 bits (C = 64)**, so no lowering of this form keeps them inside the field; finding no second witness on samples does not rescue it.
- Volume under L at D = 32: 970 (GB 12, C 16), 922 (GB 12, C 64), 1,098 (GB 18, C 16), 1,002 (GB 18, C 64) committed values per head per token, against #71's SB formula at the same D: 648.5, 624.5, 776.5, 704.5. Extra: **321.5 at C = 16 and 297.5 at C = 64** (both GB).

Raw data: `runs/sb-unique.json` (one file, all arms, per-run rows, tallies, bounds, controls, counts). Code: `research/operators/qwen_state_commit/sb_unique.py`, `sb_unique_lib.py` (commit 2e6e4a37).

## Registered set, per arm (R1..R4 x seeds 1..5, D = 32, 64 warm-up + 256 tokens)

| arm | floors checked (G / M / delta / o / S_out) | second witnesses | honest runs fully accepted | proved bound bits M, o / S_out / delta / G | fits field | verdict |
|---|---|---|---|---|---|---|
| GB 12, C 16 | 43,520 / 163,744 / 163,729 / 163,712 / 326,656 | 0 | 19 / 20 | 59, 59 / 47 / 44 / 25 | yes | FAIL (completeness) |
| GB 12, C 64 | 166,400 / 163,232 / 163,217 / 163,200 / 80,896 | 0 | 19 / 20 | 61, 61 / 49 / 44 / 25 | yes | FAIL (completeness) |
| GB 18, C 16 | 43,520 / 163,744 / 163,729 / 163,712 / 326,656 | 0 | 19 / 20 | 65, 65 / 53 / 44 / 31 | **no** | FAIL (kill: bound) |
| GB 18, C 64 | 166,400 / 163,232 / 163,217 / 163,200 / 80,896 | 0 | 19 / 20 | 67, 67 / 55 / 44 / 31 | **no** | FAIL (kill: bound) |

"Fits field" is `bound + 2^(k+19) < p` (G uses its own GB + 1 bit window). Floor counts differ slightly between M, delta and o because the R3 seed 3 run is rejected at its first out-of-window delta and later floors of that chunk are not enumerated (PREREG amendment, committed 09:44:27Z before the run; its own stamp says 10:02 in error, corrected in a second amendment). The failing run is the same R3 seed 3 that failed #71's drift bound; it is the heaviest-tailed input (Student t, 3 degrees of freedom).

Observed numerator bits per run (max over the run; median / min / max over the 20 runs):
- GB 12: M 49 / 47 / 53, o 47 / 45 / 50, S_out 38 / 36 / 41, delta 27 / 26 / 31, G 24.
- GB 18: M 55 / 53 / 59, o 53 / 51 / 56, S_out 44 / 42 / 47, delta 27 / 26 / 31, G 30.
Same at C = 16 and C = 64 to within one bit (see `run_bits` in the run file). Honest numerators sit 6 to 8 bits under the proved bound; the gap is the admission, not the data.

## Adversarial admitted set (2 edge chunks + 200 random edge chunks, seed 1111, per arm)

Every one of the 202 chunks passes L's operand admission and **every one is rejected** by L: its honest quotient leaves L's window at some floor (C = 16: first out-of-window floor is an M in 100, a delta in 101, an o in 1). So this set tests uniqueness only on the floors before rejection: per arm 7,171 to 7,306 M floors, 3,617 to 3,713 o floors, 3,749 to 3,849 delta floors and 27,472 (C 16) or 420,160 (C 64) decay-table floors, with **0 second witnesses**. Largest numerator reached: 57 bits (GB 12), 63 bits (GB 18). It does **not** test a complete admitted chunk whose numerators sit at the proved bound: none of the 202 survives to S_out. The PREREG anticipated this ("rejected, counted, not a uniqueness case").

## Controls
- (a) #71's M1b window (|Q| < 2^23) on the registered M and o floors: second witnesses for **0 of 327,456** (GB 12, C 16), 0 of 326,432 (GB 12, C 64), **327,456 of 327,456** (GB 18, C 16) and **326,432 of 326,432** (GB 18, C 64). The enumerator finds what #71 found; required at GB = 18, met.
- (b) mutated witnesses (Q + 1 with r - 2^k, Q - 1 with r + 2^k, r + 1, Q + 2^22): **0 accepted** of 3,445,440 (C 16) and 2,947,776 (C 64) per arm.

## Why GB = 12 is unique and GB = 18 is not provably so
Under L, a second witness for the same field residue needs `2^k (Q' - Q) + (r' - r) = m p` with m != 0, inside an integer interval of width 2^(k+19). For the M and o floors k = 2F + GB: 43 + 19 = 62 bits at GB = 12 is below p, so any second witness is impossible (enumeration agrees: 0), and correctness also needs the true numerator below p - 2^(k+19), which the proved bound gives (59 or 61 bits). At GB = 18, k + 19 = 61 is still below p, so the enumeration finds no second witness on these floors; but the proved bound on |N| is 65 or 67 bits, so the field residue the checker sees can differ from the integer numerator, and the accepted (unique) witness is then not the integer floor. That is the registered kill: the operand admission of L (norm of k and q, |S| < 2^18, |delta| < 2^18) is too loose for 2^18 decay tables at D = 32. The dominant term is `(C - 1) 2^GB NB 2^18`, the Gram-times-delta sum; it grows with C, which is why C = 64 is 2 bits worse.

## Counted volume (per V head, per token, D = 32)

| arm | #71 SB formula (count_r2.per_head at D = 32) | L | extra | extra items |
|---|---|---|---|---|
| GB 12, C 16 | 648.5 | 970.0 | 321.5 | S_out quotient range limbs 2 D^2/C, decay-table range limbs, M/delta/o quotient range limbs 6 D, norm cells and slack limbs 8, minus delta_hi (D) |
| GB 12, C 64 | 624.5 | 922.0 | 297.5 | same |
| GB 18, C 16 | 776.5 | 1,098.0 | 321.5 | same |
| GB 18, C 64 | 704.5 | 1,002.0 | 297.5 | same |

Convention is #71's: one count per committed value, 12-bit keys. Both columns exclude the committed operands (k, q, v, a, beta) and every sumcheck, lookup and commitment overhead. The item list is in `runs/sb-unique.json` (`count.L_items`). L at GB = 12 is **not a working lowering** (completeness failed), so these counts are of the registered specification, not of a sound and complete one.

## What is NOT established
- SB is still not sound end to end, not built, and not recommended for M3. No proof, no backend, no prover costs here.
- No result at D = 128 (the real head) or on real gate statistics; at D = 128 the norm term `sqrt(D)` adds 1 bit to every M and o bound.
- GB = 12 with a two-limb delta (as #71) would fix the completeness miss, but that changes the window and the bound and was not registered or run.
- GB = 18 needs a tighter admission (for example a bound on the Gram sum or on the delta norm, or a multi-word relation for M and o); none is specified or costed here.
- The adversarial set never reaches the proved bound with a complete chunk; uniqueness at the bound rests on the interval argument, checked by enumeration only below it.

## Deviations from the PREREG
- Amendment (committed 09:44:27Z in 2e6e4a37, before the registered run; stamped 10:02 in error, corrected by a second time-only amendment): a chunk is rejected at its first out-of-window floor and later floors are not enumerated; control (a) required only at GB = 18.
- None else. Seeds, sizes and arms as registered. Run took 92.1 s inside the 30 min budget.
