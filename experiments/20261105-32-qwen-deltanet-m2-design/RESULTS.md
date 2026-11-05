# RESULTS: 20261105-32-qwen-deltanet-m2-design

Issue: #32. PR: #66 (draft). PREREG: 84776893, the first commit on the branch. Design: [DESIGN.md](DESIGN.md).
All numbers are **measured or counted on one host, unreplicated**. No M2 proof was built: this is a design lane.

**Verdict against the registered threshold: PASS on H1 to H5, so GO for an M2 build lane**, with arm B (lookup-exact remainders) as the primary arm. One registered item reads as a design constraint: arm A cannot hold the M2 head at T = 16 in a 2^22 table.

**Scope of that GO (post-review, #66).** At the M2 boundary every input is public, so the whole M2 statement, y included, is verifier-computable. M2 is a rehearsal of the proving machinery for M3, not a useful standalone proof, and it de-risks none of the new operator families (conv1d, the gate tables, the q/k norm), since those moved to verifier recompute. DESIGN.md section 0 says what M3 must add. The post-review corrections and the rerun are in "Post-review corrections" at the end. None of them moves a registered verdict.

Code: `research/operators/qwen_deltanet_m2/`
- `admit_proto.cpp` + `m1b_builder.h` (H5)
- `count_model.py` (H1 to H3)
- `head_reference.py` (H4)
- `record.py` regenerates everything; `evidence.json` holds commands, exit codes, timings and source SHA-256s.

Raw data in `runs/`:
- `h5-honest.jsonl`
- `h5-hostile-seed1.jsonl`
- `model.json`
- `ranges-head.json` (registered)
- `ranges-head-q-unscaled.json` and `ranges-head-delta-kernel.json` (secondary, unregistered)

## H1: counting model reproduces M1 and M1b (threshold: exact)

| | model | measured | match |
|---|---|---|---|
| M1 product columns | 2,338,816 | 2,338,816 (#47) | yes |
| M1 relations | 4,761,088 | 4,761,088 | yes |
| M1 terms | 11,430,400 | 11,430,400 | yes |
| M1 log-length | 22 | 22 | yes |
| M1b columns laid out (aligned region) | 1,310,720 | 1,310,720 (#63) | yes |
| M1b non-region columns | 1,074,176 | 1,074,176 | yes |
| M1b relations | 2,231,808 | 2,231,808 | yes |
| M1b terms | 5,174,272 | 5,174,272 | yes |
| M1b range cells | 67,072 | 67,072 | yes |
| M1b log-length | 21 | 21 | yes |

**H1: PASS.** The recurrence counts are exact. Two parts have no builder to check against yet: the gated-norm counts (about 0.8% of M2's columns) and the arm-B layout (key parts, region alignment). Those are design counts.

## H2: lookup-exact remainders at the M1b shape (threshold: B / A <= 0.5 on columns per cell and on relations)

| | arm A (exact bits = M1b) | arm B (direct LKP keys, 2^12 table) | B / A |
|---|---|---|---|
| product columns + range cells + keys, per state cell per token | 17.41 | 6.07 | **0.349** |
| relations | 2,231,808 | 609,792 | **0.273** |
| terms | 5,174,272 | 1,186,816 | 0.229 |
| table log-length | 21 | 19 | |

**H2: PASS.** The saving is about 11.3 product columns and about 24 relations per state cell per token. This answers hard rule (c): lookup-exact remainders are worth about 2.9x on columns and 3.7x on relations.

## H3: the M2 head statement at T = 16 (threshold: arm B log-length <= 22)

| | arm A | arm B |
|---|---|---|
| gate columns | 4,377,056 | 1,056,800 |
| RNG range cells | 272,384 | 272,384 |
| LKP remainder keys | 0 | 276,688 |
| relations | 9,042,944 | 2,402,432 |
| terms | 21,110,960 | 4,786,704 |
| table log-length | **23** | **21** |
| largest T with log-length <= 22 | 14 | 41 |

Layer extrapolation (48 V heads, per token):

| | arm A | arm B |
|---|---|---|
| relations | 27.1M | 7.21M |
| columns + cells + keys | 13.9M | 4.82M |

For all 48 DeltaNet layers, per token, the columns + cells + keys are 670M (arm A) and 231M (arm B). This is an extrapolation, not a measurement.

The arm-B prove time at 2^21 is estimated at about 39 s, by linear interpolation from #47 and #63. That is an estimate.

**H3: PASS for arm B.** Arm A at T = 16 does not fit 2^22. That is descriptive under the PREREG and is a constraint on the build (fallback: arm A at T <= 14, e.g. T = 8).

## H4: ranges of every cell class, whole head (threshold: 20/20)

Setup: integer reference of the whole head, R1..R4 x seeds 1..5 x 1,024 steps, conv taps U(-0.5, 0.5), 14.5 s CPU.

**Every class fit in 20/20 runs.**

| class | contract | max over 20 runs |
|---|---|---|
| S' | < 2^18 (262,144) | 150,189 |
| M | < 2^18 | 53,294 |
| delta | split at 2^18 | 282,387 (split needed in 1/20 runs; hi <= 1) |
| o (witness, new) | < 2^18 | 6,379 |
| w (norm output, new) | <= 2^12 | 4,048 |
| sigma | < 2^24 (2 limbs) | 6,454 |
| e1, e2 | [0, 2^24) | 12,148 / 7,253, min 0 |
| Rc | < 2^36 (3 limbs) | 1,431,655,765 (< 2^31) |
| rr, sigma - 1 - rr | [0, 2^24) | 4,264 / 4,583, min 0 |
| w and y floor remainders | [0, 2^24) / [0, 2^12) | min 0 |
| public v (post-conv) | < 2^31 | 527,711 |
| public y | < 2^31 | 101,976 |
| public cg | < 2^24 | 230,259 |

**H4: PASS.** No new limb split was needed. (The remainder classes are checked only for >= 0. Their upper bounds hold by the construction of floor: a remainder of floor(x / 2^w) is below 2^w.)

Divergence from float64:
- **State: 0.040 worst.** M1b's was 0.032.
- **Gated-norm output y: 1.23 worst (absolute, y up to about 25 in real units).**

This y number is a fidelity finding, not a range one. The integer o is small: the median run's max |o| is 853 and early-token rms(o) is 2 to 60 integer units at 2^F, because q carries 1/sqrt(128) and the decayed state is small. So o has a 1-ulp relative error of up to about 15%, and the scale-free norm amplifies it into y. The norm step itself adds under 0.01 (checked by applying the same norm to float and integer o).

**Design implication (not registered, secondary run):** compute o from the unscaled q (the norm is scale-invariant, so 1/sqrt(128) moves into eps x 128). This raises o about 11x in integer units:
- max |o| is 72,479, still < 2^18
- 20/20 fit
- worst y divergence is 1.19, unchanged, because the worst cases are early tokens with near-zero state

So y fidelity needs a larger F for o, or a rule for near-zero rms. **Fidelity is owned by M0/#8. M2 range soundness is unaffected.** A delta-kernel stress run (conv = pass-through) also fit 20/20, with max |delta| 582,625 and hi <= 2.

## H5: verifier-side admission (threshold: 10/10 honest, 100% hostile, R9 control accepted)

This uses `verify_from_words` on the M1b statement (D = 128, T = 4) with the merged lookup.h unchanged. It decodes 34,827 words (each canonical, each in its class), derives the relations, sizes, then verifies. Runs were pinned to 6 cores.

| metric | n | median | SD | min | max |
|---|---|---|---|---|---|
| accepted | 10 | **10/10** | | | |
| decode (s) | 10 | 0.0001 | 0 | 0.0001 | 0.0001 |
| derive relations + size (s) | 10 | 0.182 | 0.007 | 0.170 | 0.196 |
| proof verify (s) | 10 | 7.61 | 0.11 | 7.53 | 7.86 |
| prove (s) | 10 | 39.91 | 0.24 | 39.64 | 40.48 |
| proof bytes | 10 | 25,411,392 | 313 | 25,410,848 | 25,411,968 |
| peak RSS (KB) | 10 | 4,433,912 | 54 | 4,433,784 | 4,433,912 |

Admission adds about 0.18 s (2.4%) to a 7.6 s verify. The proof bytes equal #63's to the byte.

Hostile, seed 1: **34/34 at the expected stage.**

| class | what | result |
|---|---|---|
| huge-element | each of S0, a, beta, k, v, q, o, S_T set to (p + 1) / 2 | 8/8 rejected at decode |
| class-bound | each class at the first integer outside, on both sides | 16/16 rejected at decode |
| non-canonical | a_0 + p, o_0[0] + p (second encoding of the same element) | 2/2 rejected at decode |
| header / length | T = 5, F = 10, one word extra, one word short | 4/4 rejected at decode |
| in-class (control) | o_T[0] + 1, S0[0] + 1 (valid integers, wrong) | 2/2 pass decode, rejected by the proof verifier |
| **R9 control** | o' = o - 2^-F mod p, honest proof of the changed relation (0 violated relations, remainder r + 1), checked by the CURRENT path (`lookup_verify` with caller-built relations, `admissible()` skipped) | **ACCEPTED** (as expected: the hole is real) |
| **R9** | the same statement and proof through `verify_from_words` | **rejected at decode** |

**H5: PASS.** This answers hard rule (a): the entry point range-checks its own integer inputs, derives targets from them, and rejects a huge public field element on its own.

## Post-review corrections and rerun (2026-11-05, review of #66)

These are corrections after the review, not re-scored hypotheses. The registered verdicts above stand on the original runs (commit e08e5ce2). The prototype changed, so H5 was rerun on the new code. Its numbers are below and are the current receipts in `runs/`.

**Wording (must-fix 1).** S_t, M, delta, o and the norm intermediates are witness values. They are not in the statement and are computable from public inputs at the M2 boundary. There is no hiding claim. "Private" is gone from DESIGN.md, this file and the prototypes (`o_private` in count_model.py is now `o_witness`; the counts are unchanged). DESIGN.md section 0 states that M2 is a rehearsal for M3, and what M3 must add.

**Conv history (must-fix 2): option (a), public history.** The statement gains H: the last 3 pre-conv inputs of each of the 384 conv channels, 1,152 words, with |H| < 2^31. DESIGN.md section 2 gives the reasons. The admission prototype now carries H in its wire format (34,827 to 35,979 words, still the M1b statement plus H; the M2 statement is about 2 x 16,384 + 1,152 + 16 x 642 words) and decodes it with its class bound.

**Count model, second lookup's multiplicities (should-fix 1).** `layout()` now sizes the multiplicity row of both lookups:
- RNG's digit lookup: 21 planes x 2^13 = 172,032 places at T = 16 (155,648 at T = 4)
- the remainder lookup: 19 planes x 2^12 = 77,824 places (69,632 at T = 4)
- both in one row: 249,856 places at T = 16, below 2^18

The row bounds the table length but does not bind at any shape here. Counts after the correction (`runs/model.json`):

| | before | after |
|---|---|---|
| H2 columns per state cell, B / A | 0.349 | 0.349 |
| H2 relations, B / A | 0.273 | 0.273 |
| H3 arm B, T = 16: laid columns, log-length | 1,613,856, 21 | 1,613,856, 21 |
| H3 arm B, T = 16: fits 2^21 | yes | **yes** |
| H3 arm A, T = 16: log-length | 23 | 23 |
| largest T at log-length <= 22, A / B | 14 / 41 | 14 / 41 |
| cross-check: arm B with the keys as ONE 2^19 part, no parts | | 1,859,616 laid columns, log 21 (the review estimated about 1.86M) |

**Two lookup instances (should-fix 2).** Transcript separation is now a stated build requirement (DESIGN.md section 4.3), with a planned hostile challenge-replay case in the build's suite (DESIGN.md section 7). Nothing is built for it here: the prototype has one lookup.

**Derive step (should-fix 3).** The verifier's derivation is now witness-free (`build(z, true)` in m1b_builder.h). It reads only decoded public integers, so no in-class statement can make it overflow. Every failure, including sizing, is a returned verdict ("derive"), not exit(1). In honest mode the prototype checks that the witness-free derivation gives the prover's relation list exactly (columns, terms, coefficients, targets). New hostile cases:
- **derive-overflow**: every class at its extreme (|S0| = 2^18 - 1 alternating, k = q = a = beta = 2^F, |v| = 2^31 - 1 alternating, o = 2^31 - 1). A checked replay of the OLD witness path on this statement overflows i64 first at token 2. New path: returns a verdict, rejected by the proof verifier.
- **derive-random**: every word uniform in its class (fixed seed). Old path: no overflow on this draw. New path: rejected by the proof verifier.
- The whole hostile suite was also run under `-fsanitize=undefined -fno-sanitize-recover`: 41/41 as expected, 0 UBSan reports, exit 0 (`runs/h5-hostile-seed1-ubsan.jsonl`).

**H5 rerun on the new code** (seeds 1..10, pinned to 6 cores, same loaded VM):

| metric | n | median | SD | min | max |
|---|---|---|---|---|---|
| accepted | 10 | **10/10** | | | |
| derive relations + size (s) | 10 | 0.227 | 0.009 | 0.212 | 0.236 |
| proof verify (s) | 10 | 7.79 | 0.23 | 7.51 | 8.30 |
| prove (s) | 10 | 40.42 | 0.88 | 39.38 | 42.16 |
| proof bytes | 10 | 25,411,392 | 313 | 25,410,848 | 25,411,968 |
| peak RSS (KB) | 10 | 4,435,606 | 25 | 4,435,528 | 4,435,608 |

Proof bytes are identical to the first run, seed by seed. The derivation is about 0.05 s slower than the first prototype's (0.182 s). The review expected witness-free to be faster. It is not, because the cost is relation and column allocation, which is unchanged, and the box was more loaded (verify and prove medians also rose about 2%). This is indicative only.

Hostile, seed 1: **41/41 at the expected stage** (was 34/34):
- the original 34, unchanged verdicts;
- conv history: a huge element, the first value outside the class on both sides, and a non-canonical word (4 cases), all rejected at decode;
- derive-overflow and derive-random (2), rejected by the proof verifier, no exit, no UB;
- history control (1): H changed in class is ACCEPTED here, as expected, because the M1b relations read no history. That is a control, not a defence. In M2 the conv recompute reads H. The "H changed in class must fail at the proof verifier" case is in the build's suite.

## Kill criterion

Not triggered. The lane started at 14:33Z. H5 honest accept came at about 15:10Z, and all results were in by 15:30Z. Peak RSS was 4.4 GB, and free disk stayed above 30 GB.

## Deviations from PREREG

- **H1.** The registered comparison quantity for M1b "columns used" was 1,141,248 in the PREREG text, which is non-region plus range cells. The model matches both the measured laid-out length 1,310,720 and the non-region count 1,074,176; 1,141,248 = 1,074,176 + 67,072 also holds. No threshold moves.
- **H5.** The class-bound test was registered as "bound + 1 for one-sided". It ran both sides for every class (16 cases instead of 8), which is stricter.
- **H4.** The PREREG listed the float divergence of y as a metric without a threshold. It is reported, and it is large (see H4). The q-unscaled and delta-kernel runs are secondary and unregistered.
- **H3 (post-review).** The largest-T loop in count_model.py also required relations <= 2^23. That is lookup_size()'s own guard, but it was not in the PREREG's metric text ("the largest T that fits log-length 22"). It does not bind: without it the largest T is still 14 (A) and 41 (B), now also reported in model.json.
- **H3 (post-review).** The count model first omitted the multiplicity row of the second (remainder) lookup. It now sizes it. No count, log-length or verdict changes (see "Post-review corrections").
- **H5 (post-review).** The prototype was changed after the registered runs (conv history words, witness-free derivation, verdicts instead of exits, 7 more hostile cases). H5 was rerun on it and passes the same registered thresholds. The registered results.yaml metrics still point at e08e5ce2, the commit of the original receipts.
- No amendments to PREREG.md.

## Open risks

- **M2 is redundant as a standalone proof** (DESIGN.md section 0). All its inputs are public. Its value is as a rehearsal for M3, and it de-risks none of conv1d, the gate tables or the q/k norm.
- **No M2 proof exists.** Arm B needs a second LKP instance whose keys are product-oracle cells. LKP supports parts and range tables, and RNG already composes a lookup whose key claim is a laid form on a sent message. But a lookup keyed directly on message-0 cells has not been built in this repo, and the two instances' transcript separation (DESIGN.md section 4.3) is a requirement on that build, untested here. That is the build lane's main risk.
- **Verifier-recomputed nonlinearities must be bit-exact** across prover and verifier. The prototype uses float64 numpy at table points. The build needs pinned public tables (DESIGN.md section 3).
- **y fidelity is poor at F = 12** (worst 1.2 absolute) because o is small in integer units. This is a fidelity issue for M0/#8, not soundness, but it argues for a finer o scale before any fidelity claim.
- **The layer extrapolation is 48x one head.** Per-token cost for 48 layers (231M product cells, arm B) means M3 needs chunked state commitment. M2 does not address that.
- The count model's norm and arm-B layout are design counts, unchecked by a builder. Same host class, research security (N = 10), hostile classes sampled, unreplicated.

## Proposed claims (PR body only, not in claims.json)

- On the M1b statement, a verifier entry point that admits its own integer public inputs costs about 0.18 s and closes the R9 hole: a huge public field element is accepted by the current caller path and rejected by the new entry alone. Measured, unreplicated.
- Lookup-exact remainders would cut the M1b statement's product columns per state cell per token from 17.4 to 6.1 and its relations by 3.7x. Counted, not built.
