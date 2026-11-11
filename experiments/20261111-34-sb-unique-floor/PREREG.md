# PREREG: 20261111-34-sb-unique-floor
Issue: #34. Lane: sblower34b. Date (UTC): 2026-11-11 09:40. Base commit: 7c40dd9f (origin/main).

Context. PR #71 (`experiments/20261109-34-qwen-state-commit/`) left the chunked low-rank form SB "not established". Under an M1b-style lowering (quotient range-checked only to |x| < 2^23, remainder exact, relation checked in the Goldilocks field, p = 2^64 - 2^32 + 1) its M and o floors at decay-table scale GB = 18 have a second valid (quotient, remainder) pair for every floor tested (`runs/sb-alias-gb18.json`), and inputs that pass `chunk.cpp`'s public admission reach 65 to 67 bit numerators. This experiment specifies a lowering for the SB floor steps, checks whether its witness is unique on a registered set, and counts its volume. Reference arithmetic and a relation checker only. No proof, no backend.

## Hypothesis
Lowering L (below: exact remainder range `0 <= r < 2^k` by full lookup keys, quotient range tied to the contract `-2^18 <= Q < 2^18` by exact keys, and admitted operand bounds that give a proved numerator bound `|N| <= 2^62`) accepts exactly one witness, equal to the integer floor, for every floor of every input in the registered set, at D = 32, C in {16, 64}, for at least one of the two decay-table scales GB in {12, 18}.

### Lowering L (fixed now)
For each SB floor `Q = floor(N / 2^k)` (M and o: k = 2F + GB; S_out: k = F + GB; F = 12), the prover commits Q and r, and the relation checker accepts iff all of:
1. `2^k * Q + r = N (mod p)`, N recomputed by the checker from committed operands in the field (as in #71's formulas, `sb_ref.chunk_sb`).
2. r is the sum of ceil(k / 12) limbs, each limb proved in its exact range by a lookup (12-bit limbs, the last limb of width k mod 12 if nonzero), so `0 <= r < 2^k` exactly.
3. `Q + 2^18` is decomposed into a 12-bit and a 7-bit limb, each in its exact range, so `-2^18 <= Q < 2^18` exactly. Same for delta (`|delta| < 2^18`, the M1 contract `reference.BOUND`; a single cell replaces #71's delta_lo/delta_hi pair).
4. Operand admission, checked per token: `0 <= a, beta <= 2^F`; `|S_in| < 2^18` per cell (chain contract); `sum_i k_i^2 <= NB` and `sum_i q_i^2 <= NB` with `NB = 2^(2F) + 2^(F+3)` (committed squared norm plus an exact range check of `NB - norm2`). Honest rounding of a unit vector at 2^F stays under NB at D = 32.

Uniqueness argument (to be checked, not assumed). With Q in a window of 2^19 and r in [0, 2^k), `2^k Q + r` ranges over an integer interval of width 2^(k+19). If `k + 19 < 64` and `2^(k+19) < p`, two accepted witnesses for the same N would differ by a nonzero multiple of p inside that interval: impossible when the width is below p. Correctness (the unique witness is the integer floor) also needs the true integer N to satisfy `|N| + 2^(k+19) < p`, so the field relation is the integer relation. The numerator bound comes from the admission: `|k . S_col| <= ||k||_2 ||S_col||_2 <= sqrt(NB) sqrt(D) (2^18 - 1)`, `|k_t . k_s| <= NB`, `G[t][s] <= 2^GB`, `|delta| < 2^18`, so for M: `|N| <= 2^F 2^GB sqrt(NB) sqrt(D) 2^18 + (C - 1) 2^GB NB 2^18`, for o the same with C terms, for S_out: `2^F 2^GB 2^18 + C 2^GB 2^F 2^18` (|k_i| <= sqrt(NB)). The script computes these bounds exactly in integers (integer square-root ceilings).

The decay-table floor `G[t][s] = floor(G[t-1][s] a_t / 2^F)` and the delta floor `delta = floor((v - M) beta / 2^F)` get the same treatment (k = F; G in [0, 2^GB] by exact keys; delta in the 2^18 window above; `|v| < 2^31` admitted as in `chunk.cpp`).

## Metric
Per arm (GB in {12, 18}) x C in {16, 64}:
1. **Second witnesses.** For every floor of every registered input: the number of accepted (Q', r') with (Q', r') != (Q, r) under L, found by exact enumeration of the congruence `2^k (Q' - Q) + (r' - r) = m p` over every integer m allowed by the windows (the construction of #71's `sb_alias.shifts`, with L's windows). Reported as count of floors with > 1 accepted witness over floors checked.
2. **Proved numerator bound.** The exact integer bound on |N| implied by L's admission (formulas above), per floor type, in bits, and whether `|N|max + 2^(k+19) < p`.
3. **Honest completeness.** Honest witnesses (integer floors of `sb_ref.chunk_sb` arithmetic) accepted by the checker, runs accepted / runs.
4. **Volume.** Committed values per head per token under L (quotients, remainder limbs, range limbs of quotients, norm cells and their range limbs, decay-table entries and their remainder limbs, Gram entries), next to #71's counted SB formula (`count_r2.per_head`, same GB and C, D = 32), and the difference = extra committed columns per token. Counted, not measured, one count per committed value, 12-bit lookup keys (#71's convention).
Controls: (a) the same enumeration with #71's M1b window (|Q| < 2^23) at GB = 18 must find second witnesses (reproduces #71's construction at D = 32); (b) mutated witnesses (Q + 1 with r - 2^k, r + 1, Q - 1 with r + 2^k) must be rejected by the checker.

## Acceptance threshold
PASS for an arm (GB, C) iff: 0 floors with a second accepted witness on the registered set, AND the proved numerator bound satisfies `|N|max + 2^(k+19) < p` for every floor type, AND honest completeness is 20/20 runs, AND the volume is counted. Hypothesis PASS iff at least one GB passes at both C = 16 and C = 64. Control (a) must find second witnesses, else the enumerator is broken and the result is KILLED.

## Kill criterion
If for an arm the proved bound exceeds the field budget (`|N|max + 2^(k+19) >= p`, i.e. no lowering of this form keeps numerators inside Goldilocks), that arm is FAIL with the bound in bits reported; an enumeration that finds no second witness on samples does not rescue it. If both GB fail this way: overall FAIL, report the bounds. Lane hard stop 2026-11-11T10:55Z: whatever is unrun is reported KILLED. Registered runs get 30 min elapsed from the moment the fp-heavy gate grants the slot (logged); unrun cells at that point are KILLED.

## Runs
- Registered set, per (GB, C): distributions R1, R2, R3, R4 x seeds 1..5 (20 runs), D = 32 (`reference.D` set to 32 for this study, token generator otherwise unchanged), 256 tokens per run after a 64-token M1 warm-up, every floor of every chunk checked. Plus an adversarial admitted set: the two #71 edge inputs (S_in at 2^18 - 1 with one-hot k, all-ones q at max norm; S_in = 2^16 - 1 with k, q scaled to max norm) and 200 random admitted chunks per (GB, C), seed 1111, operands drawn uniformly at the edges of their admitted ranges (S_in cells +-(2^18 - 1), k and q random sign vectors at norm sqrt(NB), a and beta in {0, 2^F}, v +-(2^31 - 1)). An adversarial input whose honest quotients leave L's contract is rejected (counted, not a uniqueness case).
- Deterministic (exact integer arithmetic), so one run per seed is the measurement; variance across seeds and distributions is reported as median/min/max of per-run numerator bits.
- Debug: only on R1 seed 99 at D = 32 (not in the registered set), before the registered run.
- Excluded: nothing. Everything runs on cores 8-11 through `fp-heavy.sh` if over 2 min.

## Prior art
- zkLLM (Sun et al., CCS 2024): tlookup for non-arithmetic ops and zkAttn; rescaling by lookup of a remainder in a fixed range, quotient bound implied by the tensor's range. Same remainder idea, no chunked recurrence.
- Jolt (Arun, Setty, Thaler 2024) and the Jolt lookup-division instructions: DIV/REM via advice quotient and remainder plus range/lookup constraints `r < d` and a no-overflow condition on `d q + r`. L is that pattern specialised to power-of-two divisors with an explicit field-wrap budget.
- EZKL (Halo2): fixed-point rescaling by division with range-checked remainder and lookup-table-bounded outputs; the bound on the input to the division is what keeps it sound in the field.
- In-repo: #67 (M1b lookup range checks, |x| < 2^23 proved for a range cell), #71 (SB reference, `sb_alias.py` second-solution construction, 65 to 67 bit admitted numerators).
New here: a uniqueness check with exact enumeration for the SB floors under explicit windows, a numerator bound from committed-norm admission (operand norms are not checked by #71's admission), and the counted cost of both.

## Amendments
(empty at registration)
- 2026-11-11 10:02 UTC, after code, before the registered run (debug only on R1 seed 99, not in the registered set). Clarifies the PREREG line "An adversarial input whose honest quotients leave L's contract is rejected". The checker walks a chunk's floors in dependency order (G, then per token M, delta, o, then S_out). At the first floor whose honest quotient leaves L's window, that floor is still enumerated (its operands are all in-window, so its numerator is inside the proved bound) and the chunk is then rejected; later floors are not enumerated because their numerators depend on a value no witness of L can commit. The first debug pass enumerated those later floors too and reported 66-bit numerators and second witnesses on them, which is not a case L admits. Also: control (a) is required to find second witnesses at GB = 18 only (at GB = 12 #71 found none either).
