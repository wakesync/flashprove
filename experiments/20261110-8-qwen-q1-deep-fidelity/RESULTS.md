# RESULTS: 20261110-8-qwen-q1-deep-fidelity

Issue #8, part of #32. PREREG: [PREREG.md](PREREG.md) (commit 07a5417). Code at run: 8917714. Run files: commit 27f5cda (committed as the run left them, except the scratch prefix in six `runs/*.time` headers, see Deviations). Status: **measured, unreplicated. Negative against the pre-registered bar.** Nothing here is proved; this is integer reference arithmetic against a float64 reference on the CPU.

**Revision 2026-11-11 (after two reviews of PR #88, PREREG amendment A-1).** Class counts, the registered best arm and every SD below come from the derived summary v2 (`runs/summary-v2.json`, `runs/summary-v2.md`, written by `summarise_q1_v2.py` from the committed run files and `runs/o-sign-recheck.jsonl`). The v1 summary (`runs/summary.json`) is left as committed; its medians, minima and maxima are unchanged in v2. Items marked **post hoc** are interpretations that were not registered quantities in the PREREG; they are descriptive and carry no verdict.

## Plain-language summary
- No integer arm meets the A2 fidelity bar at layer 16 or layer 20, on either checkpoint. **H1 is false**: XS18 (= PR #74's X3-r2) fails on all three targets.
- The failures are in the **max**, not the median. XS18's median rel_y is 0.0019 to 0.0029, 3 to 5 times under the bar, but a few (prompt, head) pairs reach 0.25 to 0.38. (Post hoc: nearly all of those pairs are on the repeated-word prompt p03; T16 also has p04.)
- Under the registered class text (o in [-2^17, 2^17)), 11 pairs in 10 X-family cells have o = +2^17 and are out of class. The first write-up said 480 / 480 for every cell; that used a looser check inherited from PR #74. The registered best arm is therefore XS18-K16 on T16 and T20s and XS18 on T20a, not XS20. No verdict changes.
- More state precision helps steadily (median rel_y halves or better per 2 bits of FS up to 18), but even FS = 20 leaves max rel_y at 0.07 to 0.11.
- End to end on the stock checkpoint (4 short prompts, 96 positions), replacing every DeltaNet layer's heads by XS18 keeps top-1 on all 96 positions, KL median 1.6e-7 and max 0.0025 nats. This is descriptive and has no threshold.
- The abliterated end-to-end run (stage E) **did not finish**. It stopped after layer 45 of 63, and no logits exist for it.

## Run record
`runs/run.progress`: slot granted 21:31:28Z. A 21:31:28 to 21:54:11, B to 21:56:57, C16 / C20s / C20a to 22:04:49, D to 22:18:58, all rc=0. E started 22:18:58Z. The last line of `runs/stageE.log` is abl layer 45 at 651.9 s (about 22:29:50Z). There is no `end E` line, `runs/stageE.time` is empty, and no process was alive when this was checked at 22:40Z. The lane session that owned the run disappeared from the session store at about 22:30Z, and the stage process went with it. No exit code was recorded. E was not restarted. At 22:40Z a restart would still have started before the registered stage cut-off (22:46Z = grant + 75 min), and the estimated 18 min for a full E nominally fits in the 20 min left before the 23:00Z compute hard stop. With no margin for queueing in the heavy gate or for a slower host, the successor lane decided conservatively not to risk a run that would probably be killed at the hard stop. That was a judgement under uncertain runtime, not a demonstrated impossibility. The registered limits were not moved.

Forward sanity check (registered): REF's top-1 after p01 is token 25358 (" Tokyo"). **PASS** (`runs/e2e-stock.json`, `sanity_pass: true`).

## Per target and arm vs the bar
Bar (PREREG): median rel_y <= 0.01, max rel_y <= 0.05, median rel_S <= 0.01, max rel_S <= 0.05 over 480 pairs, no guard error, 480 / 480 in the stated honest classes. For every arm and target: n = 480 and 0 guard errors. Classes under the PREREG text (amendment A-1): 480 / 480 in 32 cells; 479 in T16 XS16, T20s XS16 / XS18 / XS20 / XS18-noG, T20a XS20 / XS18-K16 / XS18-noU / XS18-noG; 478 in T16 XS20 (pairs with o = +2^17, listed in `runs/summary-v2.md`). Every cell already fails on its error stats, so the class correction changes no verdict.

rel_y median / max, rel_S median / max (from `runs/summary.json`, table in `runs/summary.md`):

| arm | T16 (stock L16) | T20s (stock L20) | T20a (abl L20) | verdict |
|---|---|---|---|---|
| C0 | 1.54 / 14.9, 0.981 / 30.8 | 0.943 / 13.0, 0.345 / 7.72 | 0.944 / 13.1, 0.344 / 7.72 | FAIL x3 |
| C4P | 0.114 / 2.23, 0.132 / 3.75 | 0.0653 / 3.60, 0.0382 / 1.08 | 0.0664 / 3.60, 0.0383 / 1.08 | FAIL x3 |
| C4+R | 0.112 / 2.26, 0.131 / 3.75 | 0.0666 / 3.63, 0.0384 / 1.08 | 0.0673 / 3.57, 0.0384 / 1.08 | FAIL x3 |
| C4+U | 0.701 / 13.7, 0.983 / 30.8 | 0.505 / 7.79, 0.345 / 7.71 | 0.507 / 7.80, 0.344 / 7.71 | FAIL x3 |
| C4+G | 0.688 / 13.8, 0.992 / 30.7 | 0.514 / 7.78, 0.346 / 7.72 | 0.512 / 7.80, 0.346 / 7.71 | FAIL x3 |
| C4+RU | 0.114 / 2.22, 0.132 / 3.75 | 0.066 / 3.61, 0.0382 / 1.08 | 0.0666 / 3.60, 0.0383 / 1.08 | FAIL x3 |
| XS12 | 0.114 / 2.22, 0.132 / 3.75 | 0.0638 / 3.61, 0.0382 / 1.08 | 0.0657 / 3.61, 0.0383 / 1.08 | FAIL x3 |
| XS14 | 0.0316 / 1.32, 0.0356 / 1.64 | 0.0194 / 2.26, 0.0104 / 0.416 | 0.0197 / 2.26, 0.0104 / 0.416 | FAIL x3 |
| XS16 | 0.00904 / 0.870, 0.00906 / 0.609 | 0.00587 / 1.05, 0.00273 / 0.185 | 0.00595 / 1.05, 0.00275 / 0.185 | FAIL x3 (medians pass, max fails) |
| XS18 | 0.00289 / 0.378, 0.00246 / 0.263 | 0.00192 / 0.249, 0.000912 / 0.0599 | 0.00199 / 0.247, 0.000915 / 0.0600 | FAIL x3 (medians pass, max fails) |
| XS20 | 0.00158 / 0.107, 0.00108 / 0.0625 | 0.00122 / 0.0737, 0.000651 / 0.0134 | 0.00123 / 0.0734, 0.000646 / 0.0134 | FAIL x3 (max rel_y fails) |
| XS18-K16 | 0.00282 / 0.379, 0.00235 / 0.263 | 0.00179 / 0.246, 0.000698 / 0.0599 | 0.00186 / 0.246, 0.000697 / 0.0600 | FAIL x3 |
| XS18-noG | 0.00292 / 0.377, 0.00253 / 0.262 | 0.00195 / 0.248, 0.000946 / 0.0598 | 0.00200 / 0.248, 0.000953 / 0.0600 | FAIL x3 |
| XS18-noU | 0.00996 / 0.370, 0.00833 / 0.242 | 0.00651 / 0.277, 0.00333 / 0.0591 | 0.00658 / 0.277, 0.00332 / 0.0593 | FAIL x3 |

Spread (sample SD, denominator n - 1, over the 480 pairs of one deterministic execution; not repeated runs) and pairs inside the PREREG classes, from `runs/summary-v2.json`. Format: rel_y SD / rel_S SD / in classes.

| arm | T16 | T20s | T20a |
|---|---|---|---|
| C0 | 1.87 / 4.2 / 480 | 1.74 / 1.4 / 480 | 1.74 / 1.4 / 480 |
| C4P | 0.243 / 0.323 / 480 | 0.279 / 0.121 / 480 | 0.279 / 0.121 / 480 |
| C4+R | 0.244 / 0.323 / 480 | 0.28 / 0.12 / 480 | 0.28 / 0.121 / 480 |
| C4+U | 1.42 / 4.2 / 480 | 1.28 / 1.4 / 480 | 1.28 / 1.4 / 480 |
| C4+G | 1.44 / 4.02 / 480 | 1.29 / 1.37 / 480 | 1.29 / 1.37 / 480 |
| C4+RU | 0.243 / 0.323 / 480 | 0.28 / 0.121 / 480 | 0.279 / 0.121 / 480 |
| XS12 | 0.242 / 0.323 / 480 | 0.279 / 0.121 / 480 | 0.279 / 0.121 / 480 |
| XS14 | 0.159 / 0.175 / 480 | 0.166 / 0.0597 / 480 | 0.166 / 0.0598 / 480 |
| XS16 | 0.0919 / 0.0774 / 479 | 0.0686 / 0.0247 / 479 | 0.0683 / 0.0247 / 480 |
| XS18 | 0.039 / 0.028 / 480 | 0.0218 / 0.00753 / 479 | 0.0218 / 0.00753 / 480 |
| XS20 | 0.0108 / 0.00696 / 478 | 0.00673 / 0.00147 / 479 | 0.00676 / 0.00147 / 479 |
| XS18-K16 | 0.039 / 0.0281 / 480 | 0.0219 / 0.00758 / 480 | 0.0218 / 0.00759 / 479 |
| XS18-noG | 0.0389 / 0.028 / 480 | 0.0218 / 0.00799 / 479 | 0.0217 / 0.008 / 479 |
| XS18-noU | 0.0382 / 0.0256 / 480 | 0.0218 / 0.00698 / 480 | 0.0218 / 0.00699 / 479 |

- **H1 (XS18 passes T16, T20s and T20a): FALSE.** (It fails on the error stats on all three targets; under the PREREG classes T20s XS18 is also out of class on 1 pair.)
- **Q1 answer per target: none passes.** Registered best arm (lowest median rel_y among arms with 480 / 480 pairs inside the PREREG classes): **XS18-K16 on T16** (median 0.00282, max 0.379, SD 0.0390), **XS18-K16 on T20s** (0.00179 / 0.246, SD 0.0219), **XS18 on T20a** (0.00199 / 0.247, SD 0.0218). The first write-up named XS20 on all three; under the PREREG class text XS20 is out of class on 2 (T16) or 1 (T20s, T20a) pairs (amendment A-1).
- Descriptive, not the registered pick: XS20 has the lowest median of all arms on every target, T16 0.00158 / max 0.107 (SD 0.0108), T20s 0.00122 / 0.0737 (SD 0.00673), T20a 0.00123 / 0.0734 (SD 0.00676), with 478, 479 and 479 of 480 pairs in class. It also fails the bar on max rel_y.
- **Post hoc** (not a registered quantity; counted for XS18 and XS20 only): pairs with rel_y > 0.05. XS18 has 22 (T16, prompts p03 and p04), 14 (T20s, p03 only) and 14 (T20a, p03 only). XS20 has 9 (T16, p03) and 2 (T20s and T20a, heads 36 and 37, p03). Head lists are in `runs/summary-v2.md`.
- P taken apart (C4 base, registered arms): C4+R and C4+RU are within a few percent of C4P at the median, while C4+U and C4+G without R are 6 to 8 times worse. Gates at 2^18 (XS18 vs XS18-noG) and k_hat at 2^16 (XS18-K16) change the median little. Dropping the finer public stage (XS18-noU) roughly triples the median. **Post hoc reading:** this is consistent with registered rounding R carrying most of the accuracy in bundle P, as PR #74 found at layer 0; the arms were registered, this interpretation was not.

## Slow-decay heads and the state-precision rule
Slow heads (median 1 - a < 2^-9): T16 14 of 48, T20s 16, T20a 16.
- Slow bucket, XS18: T16 rel_y median 0.00313 / max **0.205** (fails), rel_S 0.00375 / 0.152. T20s 0.00188 / 0.0405, rel_S 0.00102 / 0.0289 (passes). T20a 0.00199 / 0.0397, rel_S 0.00102 / 0.0289 (passes).
- Slow bucket, XS20: T16 0.00151 / **0.0791** (fails), rel_S 0.00125 / 0.0625. T20s and T20a pass.
- Rule (smallest FS whose slow bucket passes on every target with a non-empty bucket, registered): **no FS in {12, ..., 20} passes**. The registered answer is "more than 2^20, or the limit is not the state scale". Slow-bucket SD of rel_y: XS18 0.0222 / 0.00628 / 0.00625, XS20 0.00854 / 0.00197 / 0.00197 (T16 / T20s / T20a, `runs/summary-v2.json`).
- **Post hoc:** the fast bucket also fails the max at every FS (XS20 fast max 0.107 / 0.0737 / 0.0734). Read as "the max failures are not specific to slow heads"; this reading was not registered.

## Context (descriptive, no threshold)
- Head-level BF16 emulation (C0 rows' `bf16_rel_y`): median 0.0050 / 0.0053 / 0.0052, max 0.0121 / 0.0132 / 0.0106, SD 0.00094 / 0.00093 / 0.00089 (T16 / T20s / T20a, n = 480). XS18 and XS20 have lower medians than BF16 emulation but higher maxima.
- Mixer-output error over the residual norm (`resid frob`, n = 10 prompts), XS18: median 0.000218 (T16), 0.000281 (T20s), 0.000282 (T20a), SD 0.00067 / 0.00052 / 0.00052; XS20: 0.000106 / 0.000176 / 0.000177, SD 0.00015 / 0.00013 / 0.00013.
- **U1 reading, layer 20** (`runs/u1-layer20.jsonl`; registered as descriptive, no threshold): stock-vs-abl float mixer-output difference over the residual norm, per prompt: median 0.00268, min 0.00123, max 0.00460, SD 0.00101 (n = 10). The residual-input difference at layer 20 is median 0.00669 (SD 0.00245). The registered best arm on T20s (XS18-K16) and on T20a (XS18) has honest mixer error median 0.00026 / 0.00028, max 0.0019 / 0.0019: about 10 times smaller than the checkpoint difference at the median, but its per-prompt max overlaps the low end of the difference range (min 0.0012). **Post hoc:** XS20 (out of class on 1 pair per T20 target) has maximum 0.00051, below the difference minimum. This compares sizes at one layer. It does not say whether a proof would detect the substitution.

## End to end, stock (stage D; descriptive)
Subset E = p01, p07, p08, p09, 96 positions (`runs/e2e-stock.json`, `runs/e2e-stock-divergence.jsonl`).
- INT (every DeltaNet layer's heads replaced by XS18): top-1 agrees 96 / 96; KL(REF || INT) median 1.59e-7, min 4.0e-14, max 0.00251, SD 0.000257 nats (n = 96 positions); max |logit diff| / std median 0.0059, max 0.150, SD 0.0206. No OverflowError (0 failed prompts). Final-layer residual relative difference 0.00094 to 0.00304 per prompt.
- BF16H (heads by BF16 emulation, context): 96 / 96; KL median 1.72e-6, max 0.00298, SD 0.000334; max logit diff / std median 0.0147, max 0.475, SD 0.0513.
- Per prompt (INT): p01 13 / 13, p07 23 / 23, p08 39 / 39, p09 21 / 21.

## End to end, abliterated (stage E): PARTIAL, NOT FINISHED
Layers 17 to 45 ran (`runs/stageE.log`, `runs/e2e-abl-divergence.jsonl`, 29 rows). The run stopped with no logits, no `e2e-abl.json` and no exit record. Residual relative difference vs REF after layer 45 (partial, descriptive only): INT 0.00108 to 0.00252, BF16H 0.00187 to 0.00309 per prompt. No top-1, KL or logit figure exists for the abliterated checkpoint.

## Deviations
1. **Stage E not finished** (session loss, see Run record). It is reported as not finished and was not rerun. Registered limits are unchanged.
2. **Scratch path in `runs/*.time`.** `/usr/bin/time -v` wrote the absolute scratch path into the "Command being timed" line of six files (arms-T16/T20s/T20a.time, stageA/B/D.time). The repository forbids host paths, so before the first commit the prefix was replaced by `<SCRATCH>` (`scrub_time_paths.py`), the same placeholder PR #74 uses. sha256 before and after each file are in `runs/scrub-time-paths.json`. No other byte of any run file was changed.
3. `runs/summary.json` existed from a peek during the run (22:19Z, before E). It was regenerated after the run by `summarise_q1.py` and is committed with the summary, not with the run files.
4. The lane that registered the run lost its session at about 22:30Z. This write-up, the summary and the ledger row come from a successor lane under the same registered limits. No registered limit or definition changed.
5. **Class predicate looser than the PREREG text (found in review, amendment A-1).** `summarise_q1.py` reused PR #74's `summarise.bounds("X1")`, max |o| < 2^17 + 1, which admits o = +2^17; the registered X-family class is o in [-2^17, 2^17). Mechanism (reading of `scaled_head.py`): the per-token shift is chosen on floor so that floor(Sigma / 2^s) is in [-2^17, 2^17), then o is rounded half up, which can carry 2^17 - 1 to +2^17. `recheck_o_sign.py` recomputed the signed o range for the 17 X-family rows with max |o| = 2^17 (`runs/o-sign-recheck.jsonl`, one process through the heavy gate under taskset 0 to 5, 1 BLAS thread; the run's prep files as inputs): 11 have o = +2^17, 6 reach only -2^17. Class counts and the best arm are restated from `runs/summary-v2.json`. PR #74's own X rows may have the same issue; not checked here.
6. **SD added after review.** v1 reported median, min and max only. v2 adds the sample SD (n - 1) of every distribution; it is the spread over pairs (or prompts, or positions) of one deterministic execution, not over repeated runs.

## Not established
- Abliterated end-to-end agreement (stage E): not finished.
- Any proof, soundness of any arm (PR #74 RESULTS 8.2), or detection of model substitution.
- Layers other than 16 and 20 per layer, long prompts or generation end to end, and in_proj / out_proj / attention / MLP in integers.
- Replication: one deterministic run, one lane.

## Raw data
`runs/arms-T16.jsonl`, `runs/arms-T20s.jsonl`, `runs/arms-T20a.jsonl` (per pair rows), `runs/e2e-stock.json`, `runs/e2e-stock-divergence.jsonl`, `runs/e2e-abl-divergence.jsonl` (partial), `runs/u1-layer20.jsonl`, `runs/manifest-{stock,abl}.json` (sha256 of every fetched tensor), `runs/run.progress`, `runs/stage*.log`, `runs/*.time`. Summary: `runs/summary.json`, `runs/summary.md` (v1, `python3 summarise_q1.py <scratch>`; it needs the prep files in scratch to compute decay buckets). Derived summary v2 (current): `runs/summary-v2.json`, `runs/summary-v2.md` (`python3 summarise_q1_v2.py`, no scratch needed; it reads `runs/o-sign-recheck.jsonl`, from `python3 recheck_o_sign.py <scratch>`).
