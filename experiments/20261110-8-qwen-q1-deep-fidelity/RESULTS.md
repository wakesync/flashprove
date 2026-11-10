# RESULTS: 20261110-8-qwen-q1-deep-fidelity

Issue #8, part of #32. PREREG: [PREREG.md](PREREG.md) (commit 07a5417). Code at run: 8917714. Run files: commit 27f5cda (committed as the run left them, except the scratch prefix in six `runs/*.time` headers, see Deviations). Status: **measured, unreplicated. Negative against the pre-registered bar.** Nothing here is proved; this is integer reference arithmetic against a float64 reference on the CPU.

## Plain-language summary
- No integer arm meets the A2 fidelity bar at layer 16 or layer 20, on either checkpoint. **H1 is false**: XS18 (= PR #74's X3-r2) fails on all three targets.
- The failures are in the **max**, not the median. XS18's median rel_y is 0.0019 to 0.0029, 3 to 5 times under the bar, but a few (prompt, head) pairs reach 0.25 to 0.38, and nearly all of them are on the repeated-word prompt p03 (T16 also has p04).
- More state precision helps steadily (median rel_y halves or better per 2 bits of FS up to 18), but even FS = 20 leaves max rel_y at 0.07 to 0.11.
- End to end on the stock checkpoint (4 short prompts, 96 positions), replacing every DeltaNet layer's heads by XS18 keeps top-1 on all 96 positions, KL median 1.6e-7 and max 0.0025 nats. This is descriptive and has no threshold.
- The abliterated end-to-end run (stage E) **did not finish**. It stopped after layer 45 of 63, and no logits exist for it.

## Run record
`runs/run.progress`: slot granted 21:31:28Z. A 21:31:28 to 21:54:11, B to 21:56:57, C16 / C20s / C20a to 22:04:49, D to 22:18:58, all rc=0. E started 22:18:58Z. The last line of `runs/stageE.log` is abl layer 45 at 651.9 s (about 22:29:50Z). There is no `end E` line, `runs/stageE.time` is empty, and no process was alive when this was checked at 22:40Z. The lane session that owned the run disappeared from the session store at about 22:30Z, and the stage process went with it. No exit code was recorded. E was not restarted. A restart at 22:40Z would have been past the registered stage cut-off (22:46Z = grant + 75 min) before it could do useful work, and a full E takes about 18 min of the remaining 20 before the 23:00Z compute hard stop. So it could not have finished inside the registered limits, and those limits were not moved.

Forward sanity check (registered): REF's top-1 after p01 is token 25358 (" Tokyo"). **PASS** (`runs/e2e-stock.json`, `sanity_pass: true`).

## Per target and arm vs the bar
Bar (PREREG): median rel_y <= 0.01, max rel_y <= 0.05, median rel_S <= 0.01, max rel_S <= 0.05 over 480 pairs, no guard error, 480 / 480 in the stated honest classes. For every arm and target: n = 480, 0 guard errors, 480 / 480 in classes. So every verdict below comes from the error stats.

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

- **H1 (XS18 passes T16, T20s and T20a): FALSE.**
- **Q1 answer per target: none passes.** Best arm (lowest median rel_y, inside its classes) is XS20 on all three targets: T16 median 0.00158 / max 0.107; T20s 0.00122 / 0.0737; T20a 0.00123 / 0.0734.
- Pairs with rel_y > 0.05: XS18 has 22 (T16, prompts p03 and p04), 14 (T20s, p03 only) and 14 (T20a, p03 only). XS20 has 9 (T16, p03) and 2 (T20s and T20a, heads 36 and 37, p03). Head lists are in `runs/summary.md`.
- P taken apart (C4 base, under registered rounding R): R carries the accuracy. C4+R and C4+RU are within a few percent of C4P, while C4+U and C4+G without R are 6 to 8 times worse at the median. This matches PR #74's finding at layer 0. Gates at 2^18 (XS18 vs XS18-noG) and k_hat at 2^16 (XS18-K16) change little. Dropping the finer public stage (XS18-noU) roughly triples the median.

## Slow-decay heads and the state-precision rule
Slow heads (median 1 - a < 2^-9): T16 14 of 48, T20s 16, T20a 16.
- Slow bucket, XS18: T16 rel_y median 0.00313 / max **0.205** (fails), rel_S 0.00375 / 0.152. T20s 0.00188 / 0.0405, rel_S 0.00102 / 0.0289 (passes). T20a 0.00199 / 0.0397, rel_S 0.00102 / 0.0289 (passes).
- Slow bucket, XS20: T16 0.00151 / **0.0791** (fails), rel_S 0.00125 / 0.0625. T20s and T20a pass.
- Rule (smallest FS whose slow bucket passes on every target with a non-empty bucket): **no FS in {12, ..., 20} passes**. The registered answer is "more than 2^20, or the limit is not the state scale". The fast bucket also fails the max at every FS (XS20 fast max 0.107 / 0.0737 / 0.0734), so the max failures are not specific to slow heads.

## Context (descriptive, no threshold)
- Head-level BF16 emulation (C0 rows' `bf16_rel_y`): median 0.0050 / 0.0053 / 0.0052, max 0.0121 / 0.0132 / 0.0106 (T16 / T20s / T20a). XS18 and XS20 have lower medians than BF16 emulation but higher maxima.
- Mixer-output error over the residual norm (`resid frob`, n = 10 prompts), XS18: median 0.000218 (T16), 0.000281 (T20s), 0.000282 (T20a); XS20: 0.000106 / 0.000176 / 0.000177.
- **U1 reading, layer 20** (`runs/u1-layer20.jsonl`): stock-vs-abl float mixer-output difference over the residual norm, per prompt: median 0.00268, min 0.00123, max 0.00460 (n = 10). The residual-input difference at layer 20 is median 0.00669. XS18's honest mixer error at T20 (median 0.00028, max 0.0019) is about 10 times smaller than the checkpoint difference at the median, but its per-prompt max (0.0019) overlaps the low end of the difference range (min 0.0012). XS20's maximum (0.00051) is below the difference minimum. This compares sizes at one layer. It does not say whether a proof would detect the substitution.

## End to end, stock (stage D; descriptive)
Subset E = p01, p07, p08, p09, 96 positions (`runs/e2e-stock.json`, `runs/e2e-stock-divergence.jsonl`).
- INT (every DeltaNet layer's heads replaced by XS18): top-1 agrees 96 / 96; KL(REF || INT) median 1.59e-7, min 4.0e-14, max 0.00251 nats; max |logit diff| / std median 0.0059, max 0.150. No OverflowError (0 failed prompts). Final-layer residual relative difference 0.00094 to 0.00304 per prompt.
- BF16H (heads by BF16 emulation, context): 96 / 96; KL median 1.72e-6, max 0.00298; max logit diff / std median 0.0147, max 0.475.
- Per prompt (INT): p01 13 / 13, p07 23 / 23, p08 39 / 39, p09 21 / 21.

## End to end, abliterated (stage E): NOT FINISHED
Layers 17 to 45 ran (`runs/stageE.log`, `runs/e2e-abl-divergence.jsonl`, 29 rows). The run stopped with no logits, no `e2e-abl.json` and no exit record. Residual relative difference vs REF after layer 45 (partial, descriptive only): INT 0.00108 to 0.00252, BF16H 0.00187 to 0.00309 per prompt. No top-1, KL or logit figure exists for the abliterated checkpoint.

## Deviations
1. **Stage E not finished** (session loss, see Run record). It is reported as not finished and was not rerun. Registered limits are unchanged.
2. **Scratch path in `runs/*.time`.** `/usr/bin/time -v` wrote the absolute scratch path into the "Command being timed" line of six files (arms-T16/T20s/T20a.time, stageA/B/D.time). The repository forbids host paths, so before the first commit the prefix was replaced by `<SCRATCH>` (`scrub_time_paths.py`), the same placeholder PR #74 uses. sha256 before and after each file are in `runs/scrub-time-paths.json`. No other byte of any run file was changed.
3. `runs/summary.json` existed from a peek during the run (22:19Z, before E). It was regenerated after the run by `summarise_q1.py` and is committed with the summary, not with the run files.
4. The lane that registered the run lost its session at about 22:30Z. This write-up, the summary and the ledger row come from a successor lane under the same registered limits. No PREREG amendment was needed, because no registered limit or definition changed.

## Not established
- Abliterated end-to-end agreement (stage E): not finished.
- Any proof, soundness of any arm (PR #74 RESULTS 8.2), or detection of model substitution.
- Layers other than 16 and 20 per layer, long prompts or generation end to end, and in_proj / out_proj / attention / MLP in integers.
- Replication: one deterministic run, one lane.

## Raw data
`runs/arms-T16.jsonl`, `runs/arms-T20s.jsonl`, `runs/arms-T20a.jsonl` (per pair rows), `runs/e2e-stock.json`, `runs/e2e-stock-divergence.jsonl`, `runs/e2e-abl-divergence.jsonl` (partial), `runs/u1-layer20.jsonl`, `runs/manifest-{stock,abl}.json` (sha256 of every fetched tensor), `runs/run.progress`, `runs/stage*.log`, `runs/*.time`. Summary: `runs/summary.json`, `runs/summary.md` (`python3 summarise_q1.py <scratch>`; it needs the prep files in scratch to compute decay buckets).
