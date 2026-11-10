# RESULTS: 20261105-32-qwen-deltanet-m2-design

Issue: #32. PR: #66 (draft). PREREG: 84776893, the first commit on the branch. Design: [DESIGN.md](DESIGN.md).
All numbers are **measured or counted on one host, unreplicated**. No M2 proof was built: this is a design lane.

**Verdict against the registered threshold: PASS on H1 to H5, so GO for an M2 build lane**, with arm B (lookup-exact remainders) as the primary arm. One registered item reads as a design constraint: arm A cannot hold the M2 head at T = 16 in a 2^22 table.

**Third review (2026-11-09): changes requested at 8ec7c799, addressed in this revision.** The design's norm relied on a bound on a verifier-derived coefficient (|cg| < 2^24) that no section made the verifier check. That is now a derive-stage admission rule in DESIGN.md (sections 2, 3.1, 4.5, 7), tested at design level only: there is no M2 verifier to test it on. See "Third review" below. Whether the review is satisfied is for a re-review at the new head to decide. No registered verdict moves, and the GO is for a build that implements the rule.

**Scope of that GO (post-review, #66).** At the M2 boundary every input is public, so the whole M2 statement, y included, is verifier-computable. M2 is a rehearsal of the proving machinery for M3, not a useful standalone proof, and it de-risks none of the new operator families (conv1d, the gate tables, the q/k norm), since those moved to verifier recompute. DESIGN.md section 0 says what M3 must add. The post-review corrections and the rerun are in "Post-review corrections" at the end. None of them moves a registered verdict.

Code: `research/operators/qwen_deltanet_m2/`
- `admit_proto.cpp` + `m1b_builder.h` (H5)
- `count_model.py` (H1 to H3)
- `head_reference.py` (H4)
- `norm_alias_regression.py` + `norm_alias_expected.json` (third review: design-level regression of the derived-value admission rule)
- `record.py` regenerates everything; `evidence.json` holds commands, exit codes, timings and source SHA-256s.

Raw data in `runs/`:
- `h5-honest.jsonl`
- `h5-hostile-seed1.jsonl`
- `model.json`
- `ranges-head.json` (registered)
- `ranges-head-q-unscaled.json` and `ranges-head-delta-kernel.json` (secondary, unregistered)
- third-review rerun, new files, nothing overwritten: `h5-honest-r3.jsonl`, `h5-hostile-seed1-r3.jsonl`, `h5-hostile-seed1-ubsan-r3.jsonl`, `h5-honest-ubsan-r3.jsonl`, `model-r3.json`, `norm-alias-regression-r3.json`

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
| terms (as first counted; superseded, see "Third review" and Deviations) | 21,110,960 | 4,786,704 |
| terms, for the lowering of DESIGN.md 4.4.1 (counted for that one lowering; no builder checks it) | 21,107,440 | 4,782,496 |
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

The last three rows are measured maxima on the synthetic suite at gain 1. They are not what makes the bounds hold. The third review pointed out that the design used "public cg < 2^24" as a fact without a verifier check. v and cg are now derive-stage admission checks (DESIGN.md 3.1); y is a statement word, checked at decode.

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
- **Checked arithmetic (second review).** A second independent review ran UBSan on the first prototype. It found signed i64 overflow at `aP = Pj * a` (m1b_builder.h) on an in-class statement with every value at its extreme, all one sign: S0 = 2^18 - 1, k = a = 2^12, v = o = 2^31 - 1. Every i64 product, sum and difference in `build()` now goes through checked helpers. An overflow sets a flag, and the verifier rejects at "derive" instead of wrapping. The review's statement is now in the suite twice:
  - through the witness-free entry: no overflow, rejected by the proof verifier;
  - through the old witness path, kept as a checked control: the overflow is caught (first at token 2) and the statement is rejected at derive.
  The alternating-sign extremes statement above was also added through the checked witness path, and is rejected at derive.
- The whole hostile suite was also run under `-fsanitize=undefined -fno-sanitize-recover`: **44/44** as expected, **0 UBSan reports**, exit 0 (`runs/h5-hostile-seed1-ubsan.jsonl`, `record.py ubsan`).

**H5 rerun on the new code** (seeds 1..10, pinned to 6 cores, same loaded VM):

| metric | n | median | SD | min | max |
|---|---|---|---|---|---|
| accepted | 10 | **10/10** | | | |
| derive relations + size (s) | 10 | 0.222 | 0.013 | 0.207 | 0.249 |
| proof verify (s) | 10 | 7.75 | 0.13 | 7.51 | 7.85 |
| prove (s) | 10 | 40.74 | 0.42 | 39.95 | 41.48 |
| proof bytes | 10 | 25,411,392 | 313 | 25,410,848 | 25,411,968 |
| peak RSS (KB) | 10 | 4,435,608 | 46 | 4,435,480 | 4,435,608 |

These are the numbers with checked arithmetic. The intermediate pass, before checked arithmetic, gave derive 0.227 s, verify 7.79 s and prove 40.42 s. Proof bytes are identical to the first run, seed by seed. The derivation is about 0.04 s slower than the first prototype's (0.182 s). The review expected witness-free to be faster. It is not, because the cost is relation and column allocation, which is unchanged, and the box was more loaded (verify and prove medians also rose about 2%). This is indicative only.

Hostile, seed 1: **44/44 at the expected stage** (was 34/34):
- the original 34, unchanged verdicts;
- conv history: a huge element, the first value outside the class on both sides, and a non-canonical word (4 cases), all rejected at decode;
- derive-overflow (4) and derive-random (1): the witness-free entry rejects at the proof verifier; the checked witness-path control rejects at derive; no exit, no UB;
- history control (1): H changed in class is ACCEPTED here, as expected, because the M1b relations read no history. That is a control, not a defence. In M2 the conv recompute reads H. The "H changed in class must fail at the proof verifier" case is in the build's suite.

## Third review: derived-value admission, norm term counts, rerun (2026-11-09)

A third independent review (a different model family) requested changes at 8ec7c799. These are corrections to the design text and the count model. They are not re-scored hypotheses. The C++ prototype did not change: its sources have the same SHA-256 as at 8ec7c799 (`evidence.json`, `compile@r3`).

### M1: the bound on the derived norm coefficient was not a checked rule

**The finding, reproduced.** DESIGN.md 4.4 claimed |cg w| < 2^47. That needs |cg| < 2^24. cg is recomputed by the verifier from the gain and z, the gain had no bound, and no section made the verifier check cg. The review gave 22 cases where the y floor relation holds mod p for a y that is not the integer floor (o_0 in {4096, 8192}, cg_0 = 2^52 .. 2^62).

`norm_alias_regression.py` rebuilds them from the equations of DESIGN.md 4.4 in plain Python integers. It imports nothing from the review. It is a reimplementation, not a blind replication: its author read the review's script first, and the case parameters (o_0, the cg range) and the compatible-statement construction are the review's.

| check | result |
|---|---|
| the 22 cases are aliases when the rule is absent: relation holds mod p, fails over the integers, every listed witness range holds, alias y in its class and not the true floor | **22 of 22** |
| each has a complete compatible statement (16-token recurrence giving that o, state constant; a = 4096, beta = 0, q_0 = 362) and a float64 gain that reproduces its cg | 22 of 22 |
| the same 22, field by field against the review's rows (its evidence file, which is not in this repository): o, cg, w, sigma, Rc, e1, e2, rr, gap, remainders, alias y, true y, S0, gain | 22 rows, 0 differ |
| with the rule (reject at derive unless \|cg\| < 2^24): verdict | 22 of 22 rejected at derive. This is true by construction (each case has cg >= 2^52), so it tests the script's rule, not a verifier. |

What these are: counterexamples to the design contract as it was written. What they are not: forged proofs (no M2 builder or verifier exists), a break of the M1b admission prototype (it has no norm), or an attack by a prover (the gain is a verifier-fixed constant, about 1.3e11 to 1.4e14 here).

**The fix: option (a), a verifier check.** DESIGN.md 3.1: after the recompute stage and before any relation or field conversion, the verifier checks every derived value against its class and rejects at "derive" otherwise. It is written as a requirement in DESIGN.md sections 2 (class table), 3 and 3.1 (rule, reasons, audit), 4.5 (step 3a) and 7 (build requirement with the regression cases). Option (b), restricting constants so the bound is proved, was not taken: it holds only for |gain| <= 1.41, has to be redone for every table and constant, and does not carry to M3.

**Boundary and no-wrap, design level** (same script):

| check | n | result |
|---|---|---|
| \|cg\| = 2^24 - 1, both signs, every channel and one channel: admitted, honest y accepted, y + 1 rejected, floor unique mod p | 4 | 4 of 4 |
| \|cg\| = 2^24, both signs, every channel and one channel: rejected at derive | 4 | 4 of 4 |
| y floor, pairs (cg, w) in their bounds incl. the 8 corners: the only solution mod p in the y class is the integer floor | 200,000 (fixed seed) | 0 mismatches |
| largest magnitude of the y floor identity under the rule | 1 | 149,533,556,211,712 (2^47.09), below p |
| no-wrap ledger, 11 closed identities of the recurrence and the norm | 11 | all below p; largest 2^60.0 (Rc sigma) |

**Audit of the other derived values** (DESIGN.md 3.1 has the table). Result: **one more gap of the same kind, and one unstated check.**
- **v (found by this audit).** M1b's no-wrap argument used |v| < 2^31, and M1b checked it at decode, because v was a statement word. In M2 v is recomputed (SiLU of the conv output), the conv taps are unbounded, and the design did not say the verifier checks it. The delta floor has the same kind of alias for a derived v of 2^52 to 2^62: 11 of 11 on that one relation (not a whole statement), each rejected at derive under the rule. Boundary: 2^31 - 1 admitted with a unique floor, 2^31 rejected, both signs, 4 of 4.
- **a and beta.** In class if the tables are built as specified. The design did not state that the verifier checks them. It does now, with a table-build check.
- **k and q.** In class for every input, by the L2 norm itself (|u_i| <= isqrt(sum u^2 + 17)). Sampled: 774 vectors at magnitudes up to 2^40, max |k| 4,096, max |q| 362. The check cannot fire; it guards a build error.
- **Recompute intermediates.** The conv accumulator and the L2 sum of squares can pass 64 bits for extreme constants or inputs. DESIGN.md 3.1 requires 128-bit or checked arithmetic there.
- Slack: with the other values at their class maxima, no identity wraps until k or a reach 2^22, beta 2^33.0, q 2^34, cg 2^41 or v 2^52.

**Completeness cost of the rule, stated plainly.** The cg check cannot fire for |gain| <= 1.41: over every in-class z (2,097,151 values, float64 formula of `head_reference.py`), max |cg| is 11,863,272 at gain 1 and 16,727,213 at gain 1.41; at gain 1.4143 it is 16,778,225, over the bound. A head with a larger gain can be refused on some inputs. **The real Qwen gains were not measured in this lane.** The v check can fire on in-class inputs if the SiLU table has no clamp; the build's pinned table has to bound it.

**The prototype has no guard, because it has no such stage.** `admit_proto.cpp` works on the M1b statement: a, beta, k, v and q are statement words, class-checked at decode, and there is no recompute stage and no norm. So no C++ changed, and the rule is **not tested through any verifier**. It is a build requirement (DESIGN.md 7), with the boundary cases and the 22 aliases as required cases of the build's suite.

### S1: norm term counts

The review found that the count model's norm **term** counts did not implement one lowering of the documented equations. It derived the gate, range-cell, key, relation and layout counts from closed forms of its own, without this model, and they matched.

DESIGN.md 4.4.1 now gives the lowering relation by relation (S1 to S8 per token, C1 to C6 per channel), and `count_model.py` counts exactly that. It asserts the closed forms (arm B 16D + 26 = 2,074 terms per token, arm A 193D + 815 = 25,519) and asserts that no gate, range, key, relation or layout count moved.

| M2 head, T = 16 | arm A | arm B |
|---|---|---|
| terms, before (`runs/model.json`) | 21,110,960 | 4,786,704 |
| terms, lowering of DESIGN.md 4.4.1 (`runs/model-r3.json`) | 21,107,440 | 4,782,496 |
| change | -3,520 | -4,208 |
| the review's totals, for its own direct-substitution lowering (not adopted) | 21,180,592 | 4,786,656 |
| gate columns, range cells, keys, relations, laid columns, log-length, largest T | unchanged | unchanged |

Every other leaf of `model-r3.json` equals `model.json`: the only differences are these two term totals (which also appear under `remainder_savings`) and the new `norm_terms` block. The M1 and M1b term counts, which are checked against measured statements (H1), did not change: they have no norm.

The review's totals differ from this lowering by exactly 16 x (35D + 92) = 73,152 (arm A) and 16 x (2D + 4) = 4,160 (arm B), which is operand reuse: this lowering ties the Rc and sigma operands to existing cells, the review's rebuilds them from their pieces. Both are valid. **The term counts remain counts for one stated lowering, unchecked by a builder.** No hypothesis reads them.

### Rerun at the new code (prototype sources unchanged)

Setup: same host, shared and loaded (other proving jobs ran at the same time), pinned to 6 cores (10 to 15), through the host's two-slot heavy-job gate, binaries built at commit f5c09762, whose C++ sources equal 8ec7c799's. Raw files have the suffix `-r3`. Timings are indicative only.

**Receipt gap, disclosed.** After the -O2 honest and hostile runs had finished, the -O2 binary was recompiled once more by mistake (a `build` step run a second time, at commit bae6f8f1). So `evidence.json`'s `compile@r3` and `fixtures@r3` describe that later build, not the build the -O2 runs used, and `env@r3` describes the last step that ran (the count model and the norm regression, at commit 9a84ded8). The binary the -O2 runs used no longer exists and its hash was not recorded. What does hold: each run key (`honest@r3`, `hostile@r3`, `hostile_ubsan@r3`, `honest_ubsan@r3`) records its own commit (f5c09762), its own cores (10-15) and the SHA-256 of the C++ sources at the time it ran, and those hashes equal the later build's and 8ec7c799's. A further recompile of the same sources with the same flags gave a byte-identical binary (SHA-256 10fbdebb...de7cf5), which supports, but does not prove, that the earlier binary was the same. The UBSan binary was not rebuilt. The fixtures are byte-identical to the registered run's. No raw run file was touched.

| build | metric | n | median | SD | min | max |
|---|---|---|---|---|---|---|
| -O2 | accepted | 10 | **10/10** | | | |
| -O2 | prove (s) | 10 | 39.88 | 0.81 | 39.65 | 41.70 |
| -O2 | derive relations + size (s) | 10 | 0.223 | 0.012 | 0.206 | 0.242 |
| -O2 | proof verify (s) | 10 | 7.65 | 0.33 | 7.28 | 8.09 |
| -O2 | proof bytes | 10 | 25,411,392 | 313 | 25,410,848 | 25,411,968 |
| -O2 | peak RSS (KB) | 10 | 4,435,604 | 86 | 4,435,372 | 4,435,608 |
| UBSan | accepted | 10 | **10/10** | | | |
| UBSan | prove (s) | 10 | 66.17 | 0.64 | 65.13 | 67.12 |
| UBSan | derive relations + size (s) | 10 | 0.369 | 0.016 | 0.342 | 0.383 |
| UBSan | proof verify (s) | 10 | 13.21 | 0.22 | 12.87 | 13.67 |

Honest, seeds 1..10: proof bytes are equal, seed by seed, to the receipts at 8ec7c799. Every process exited 0 with empty stderr, in both builds. The UBSan honest run is new in this rerun (0 reports); it was not registered.

Hostile suite, seed 1, n = 1 run per build (the cases are deterministic):

| build | at the expected stage | rejected | intended accepts (controls) | by stage | UBSan reports | wall (s) |
|---|---|---|---|---|---|---|
| -O2 | **44/44** | 42 | 2 | decode 35, derive 2, proof 5, accept 2 | n/a | 133 |
| UBSan (`-fsanitize=undefined -fno-sanitize-recover`) | **44/44** | 42 | 2 | decode 35, derive 2, proof 5, accept 2 | **0**, exit 0, stderr empty | 229 |

The two accepts are the suite's controls: the R9 statement through the old caller path, and a changed conv history on the M1b relations, which read no history. **No case changed stage:** the case list and the stage of every case equal the receipts at 8ec7c799, in both builds, and the detail lines (first overflow token of the old path, R9 details) are equal too.

Design-level regression (`norm_alias_regression.py`, 3.6 s, no proof): exit 0, output equal to the committed expected file. Count model: exit 0, both assertions hold.

**What this rerun shows and does not show.** It shows the prototype behaves as before. It could not show anything about the new rule, because the prototype has no stage the rule applies to.

## Kill criterion

Not triggered. The lane started at 14:33Z. H5 honest accept came at about 15:10Z, and all results were in by 15:30Z. Peak RSS was 4.4 GB, and free disk stayed above 30 GB.

## Deviations from PREREG

- **H1.** The registered comparison quantity for M1b "columns used" was 1,141,248 in the PREREG text, which is non-region plus range cells. The model matches both the measured laid-out length 1,310,720 and the non-region count 1,074,176; 1,141,248 = 1,074,176 + 67,072 also holds. No threshold moves.
- **H5.** The class-bound test was registered as "bound + 1 for one-sided". It ran both sides for every class (16 cases instead of 8), which is stricter.
- **H4.** The PREREG listed the float divergence of y as a metric without a threshold. It is reported, and it is large (see H4). The q-unscaled and delta-kernel runs are secondary and unregistered.
- **D5, 24-bit remainders in arm B (second review).** PREREG D5 registered a 24-bit (2F) remainder as two 12-bit key limbs **plus one recombination relation**. DESIGN.md 4.3 and count_model.py instead put both limbs directly into the floor relation, with coefficients 1 and 2^12, and have no recombination relation. The two are equivalent: the floor relation reads lo + 2^12 hi either way. The direct form saves one relation per 24-bit remainder. This was not disclosed in the first version of this file. Cost of the registered form:
  - M1b shape (T = 4): one M floor per value column per token, so +512 relations (609,792 to 610,304). Relations B / A stay **0.273** (0.2735), and columns are unchanged (0.349).
  - M2 head (T = 16): the M floor and the norm's w floor per j per token (+4,096), plus the norm's 24-bit scalars if recombined too. That is under 0.3% of 2.40M relations, the ratio stays 0.266, and the table stays 2^21.
  - No threshold or verdict moves. The build may use either form, and should state which.
- **H3 (post-review).** The largest-T loop in count_model.py also required relations <= 2^23. That is lookup_size()'s own guard, but it was not in the PREREG's metric text ("the largest T that fits log-length 22"). It does not bind: without it the largest T is still 14 (A) and 41 (B), now also reported in model.json.
- **H3 (post-review).** The count model first omitted the multiplicity row of the second (remainder) lookup. It now sizes it. No count, log-length or verdict changes (see "Post-review corrections").
- **H5 (post-review).** The prototype was changed after the registered runs (conv history words, witness-free derivation, verdicts instead of exits, checked i64 arithmetic, 10 more hostile cases). H5 was rerun on it and passes the same registered thresholds. The registered results.yaml metrics still point at e08e5ce2, the commit of the original receipts.
- **H3 terms (third review).** The M2 head's relation-term totals at T = 16 changed, because the norm's terms were first counted without one stated lowering. Old: 21,110,960 (arm A), 4,786,704 (arm B), in `runs/model.json`. New: 21,107,440 and 4,782,496, in `runs/model-r3.json`, for the lowering of DESIGN.md 4.4.1. Change: -3,520 and -4,208 (0.02% and 0.09%). Terms are a registered H3 metric with no threshold. Columns, relations, range cells, keys, log-length and largest T are unchanged, so no threshold or verdict moves. The old file is kept.
- **Design contract (third review).** DESIGN.md's verifier now also rejects a statement whose recomputed k, q, a, beta, v or cg is outside its class (|cg| < 2^24, |v| < 2^31, a and beta in [0, 2^F], |k| and |q| <= 2^F). PREREG D6 registered "decodes each word itself ... derives every relation target and coefficient from the decoded integers"; it did not register a check on the derived coefficients. This narrows the set of admitted statements. No registered number changes: H5 ran on the M1b statement, where these values are statement words already checked at decode.
- **H5 (third review).** H5 was rerun a third time (tag r3), on unchanged prototype sources, and an honest run under UBSan was added (not registered). Same thresholds, same result. The registered results.yaml metrics still point at e08e5ce2.
- No amendments to PREREG.md.

## Open risks

- **M2 is redundant as a standalone proof** (DESIGN.md section 0). All its inputs are public. Its value is as a rehearsal for M3, and it de-risks none of conv1d, the gate tables or the q/k norm.
- **No M2 proof exists.** Arm B needs a second LKP instance whose keys are product-oracle cells. LKP supports parts and range tables, and RNG already composes a lookup whose key claim is a laid form on a sent message. But a lookup keyed directly on message-0 cells has not been built in this repo, and the two instances' transcript separation (DESIGN.md section 4.3) is a requirement on that build, untested here. That is the build lane's main risk.
- **Unchecked arithmetic on public inputs (second review).** The first prototype's verifier derivation overflowed signed i64 (UB) at `aP = Pj * a` on an in-class all-extremes statement. No soundness break was seen. It is now fixed in the prototype: the derivation is witness-free, every i64 operation in `build()` is checked and rejects at "derive" on overflow, and the hostile suite is clean under UBSan. For the M2 build this is a requirement (DESIGN.md 4.5): no unchecked arithmetic on public inputs, and a UBSan run of the hostile suite. It stays an open risk until the build's verifier passes that run.
- **Derived-value admission is specified, not built (third review).** The rule that closes the norm alias (reject at derive unless every recomputed k, q, a, beta, v, cg is in its class) exists in DESIGN.md and in a Python regression of the design equations. No verifier implements it, and no proof system has been run against the 22 alias statements. It stays an open risk until the M2 build's `verify_m2` passes the cases of DESIGN.md section 7. The audit that found the second gap (v) was done by the lane that wrote the design, on the relations the design lists; an independent audit has not been done.
- **Real gains are unknown here.** The cg bound 2^24 cannot be tripped for |gain| <= 1.41. The real Qwen gated-norm gains were not measured in this lane. If they are larger, some statements are refused until the bound is raised (the no-wrap argument has room up to about 2^41) and the y class is re-derived.
- **Verifier-recomputed nonlinearities must be bit-exact** across prover and verifier. The prototype uses float64 numpy at table points. The build needs pinned public tables (DESIGN.md section 3).
- **y fidelity is poor at F = 12** (worst 1.2 absolute) because o is small in integer units. This is a fidelity issue for M0/#8, not soundness, but it argues for a finer o scale before any fidelity claim.
- **The layer extrapolation is 48x one head.** Per-token cost for 48 layers (231M product cells, arm B) means M3 needs chunked state commitment. M2 does not address that.
- The count model's norm and arm-B layout are design counts, unchecked by a builder. The norm's term counts are for one stated lowering (DESIGN.md 4.4.1). Same host class, research security (N = 10), hostile classes sampled, unreplicated.

## Proposed claims (PR body only, not in claims.json)

- On the M1b statement, a verifier entry point that admits its own integer public inputs costs about 0.18 s and closes the R9 hole: a huge public field element is accepted by the current caller path and rejected by the new entry alone. Measured, unreplicated.
- Lookup-exact remainders would cut the M1b statement's product columns per state cell per token from 17.4 to 6.1 and its relations by 3.7x. Counted, not built.
