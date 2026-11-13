# RESULTS: 20261113-157-u1-margin-p03

**Verdict: FAIL (mixed) on the full registered set (10 prompts, 1,461 positions). All three conditions fail.** Measured, unreplicated.

## Plain summary
PR #139 left out one of the 10 registered prompts, p03-repeat-word (" the" repeated 512 times), the prompt with PR #124's largest lowering error E. This PR computes the float64 stock-vs-abliterated distance D on it and applies PR #139's unchanged rule to all 10 prompts.

On p03 the two checkpoints are almost the same: D has a median of 2.1e-5 nats and is more than 10 times E at only 20% of the 512 positions (102). Summed over the prompt, D is about the same size as E (sum D / sum E = 0.91). Adding p03 moves the pooled share of positions with D > 10 E from 0.933 (9 prompts) to 0.676 (10 prompts), and the share with D > 100 E from 0.656 to 0.439, so the second condition, which passed on the subset, now fails too. This is the negative case the issue described: on deterministic repetition the output-level difference between stock and abliterated is of the same order as the head-only lowering error, so an output-level check cannot separate them there at this E.

## Validity gates (all pass)
- (a) p01 last-position top-1 is " Tokyo" (25358) on both checkpoints (PR #139's committed record, re-checked on the merged input).
- (b) p03, bit for bit (the issue's rule): this run's REF top-1 and margins equal PR #124's committed `ref_top1` / `ref_margin` at all 512 positions on both checkpoints, 0 differing top-1, 0 differing margins, max absolute margin difference 0.0. This checks the whole chain, including stock layers 0 to 16 that were recomputed here. On the 9 merged prompts, PR #139's 1e-6 rule, re-evaluated: max absolute margin difference 0.0 over all 1,461 positions.
- (c) This run fetched 850 stock tensors (layers 0 to 63, final norm, `lm_head`), embedding row 279 and 71 abliterated tensors (the 70 that differ, plus the final norm). Every sha256 equals PR #124's committed manifest and PR #87's committed hash; the embedding row equals PR #124's; no conflict with PR #139's manifests. PR #139's committed D file matched its registered sha256 (74f5fa12...0460f) before it was used.

## 1. p03-repeat-word alone (512 positions; `runs/merged-analysis.json` p03_alone)
XS18, E = max(E_stock, E_abl):
- share D > 10 E: **0.199** (102 / 512); share D > 100 E: **0.037** (19 / 512).
- log10(D / E): median 0.64, SD 0.61, min -2.20, p1 -0.99, p10 -0.07, p90 1.21, max 3.19.
- D: median 2.1e-5 nats, min 9.3e-6, max 1.7e-3 (p10 1.3e-5, p90 4.4e-5). Reverse KL median 2.0e-5.
- E (XS18): median 4.6e-6, max 5.7e-3. sum D / sum E = 0.91.
- Top-1: REF_stock and REF_abl pick the same token at all 512 positions (PR #124's committed `ref_top1` gives the same, 0).
- XS20 (descriptive): share D > 10 E 0.303, D > 100 E 0.033, median log10 ratio 0.78.

No position of p03 has E <= 0.

## 2. The registered verdict on all 10 prompts (1,461 positions)
| | value | bar | |
|---|---|---|---|
| pooled share D > 10 E | 0.676 (987 / 1,461) | >= 0.95 | fail |
| pooled share D > 100 E | 0.439 (642 / 1,461) | >= 0.50 | fail |
| prompts with share(D > 10 E) >= 0.90 | 7 of 10 | >= 8 | fail |

Pooled share(D > 10 E) is between 0.50 and 0.95, so the label is "mixed" (PREREG). The prompts that carry the failure: p03-repeat-word (0.199), p04-repeat-punct (0.781), p06a-digits-256 (0.840). log10(D / E) over all positions: median 1.69, SD 1.21, min -2.20, p1 -0.70, p10 0.35, p90 3.37, max 5.73. D median 5.1e-5 nats. Top-1 differs between the two references at 23 of 1,461 positions, all on the 9 prompts PR #139 ran (PR #124's committed count: 23).

Per prompt (XS18): share D > 10 E / D > 100 E / D median / top-1 differ
- p01-ordinary-short (13): 1.000 / 1.000 / 1.1e-3 / 0
- p07-chat-ordinary (23): 0.957 / 0.913 / 3.0e-5 / 0
- p08-chat-refusal (39): 1.000 / 1.000 / 1.6e-3 / 1
- p09-multilingual (21): 1.000 / 1.000 / 4.3e-3 / 0
- p02-ordinary-paragraph (107): 1.000 / 0.944 / 7.7e-3 / 2
- **p04-repeat-punct (64): 0.781 / 0.422 / 2.6e-5 / 0**
- p05-code (144): 0.986 / 0.708 / 1.2e-5 / 0
- **p03-repeat-word (512): 0.199 / 0.037 / 2.1e-5 / 0** (this PR)
- **p06a-digits-256 (256): 0.840 / 0.164 / 1.2e-4 / 3**
- p11-chat-long (282): 0.979 / 0.911 / 7.2e-3 / 17

Secondary (XS20, descriptive): share D > 10 E 0.746, D > 100 E 0.492, 9 of 10 prompts at >= 0.90 (p03 is the one below). The one XS20 position with E <= 0 (p11 t = 279, as in PR #139) counts as +inf.

## 3. PR #139's 9-prompt numbers, unchanged (its committed `runs/analysis.json`)
FAIL (mixed), subset: share D > 10 E 0.933 (885 / 949), D > 100 E 0.656 (623 / 949), 7 of 9 prompts. Condition (2) passed on the subset; with p03 added it fails. The 9 prompts' own per-prompt numbers do not change (same committed D).

## Determinism (variance statement)
The forward is deterministic float64, so the registered variance check is a repeat run compared bit for bit. Run 2 (same job, separate scratch, same code and cores) gives per-position D, reverse KL, both top-1 arrays and both margins **bit-identical** to run 1 (all 6 arrays equal; sha256 of the D array 49613a32...a54bde in both; `runs/merged-analysis.json` determinism). The two `d-p03.json` files differ only in their `seconds` field (wall time of the `lm_head` pass, 31.1 s and 31.4 s). With run 1 also matching PR #124's committed REF values bit for bit, the p03 numbers have no run-to-run spread on this stack; their spread is over positions only, as reported above.

## What is NOT established
- E is head-only (PR #124, XS18 / XS20). A fully integer model (#150, #132) may have a larger E, which would only make the margin smaller; that is not measured here.
- Teacher-forced, per position. Nothing about served replies, sampled text, refusal behaviour, or any verifier's acceptance rule. Top-1 tokens are reported as ids only.
- The PREREG bars (10x, 100x, 95%, 90%) are the registered ones; no claim that they are the right bars for a real check.
- Why D is small on repetition is not analysed. The data are consistent with the issue's guess (on deterministic continuations the two checkpoints nearly coincide), but no mechanism was tested.
- One host, one software stack. Bit-for-bit agreement with PR #124's committed REF values (a separate run on 2026-11-11, different core range) is the cross-check; no other machine was used.

## Deviations
- The layer-16 state that PR #139 used was not found, so stock layers 0 to 16 were recomputed for p03 in each run (registered in the PREREG before code). Gate (b) passed bit for bit, so the recomputed chain is the same forward that produced PR #124's REF values.
- None of the 9 prompts was rerun; their D is PR #139's committed file, checked by sha256.
- No amendment to the PREREG.

## Runs and cost
One heavy job, slot granted 2026-11-13T02:54:02Z (`runs/progress.log`), `taskset -c 10-15`, 6 BLAS threads, 6 head workers. Run 1: 24 min 28 s wall, peak RSS 7.35 GB (`runs/run1/run.time`). Run 2: 19 min 59 s wall, peak RSS 7.36 GB (`runs/run2/run.time`). Whole job 44 min 27 s (n = 2 runs, descriptive, not a performance claim; the host was shared and loaded). Weights streamed, nothing cached; free disk stayed above 59 GB.

## Files
`runs/run1/d-p03.json` (per-position D, reverse KL, both top-1s and margins, run 1), `runs/run2/d-p03.json` (run 2), `runs/run{1,2}/manifest-{stock,abl}.json`, `runs/run{1,2}/progress.log.jsonl`, `runs/run{1,2}/run.time`, `runs/run{1,2}/divergence-*.jsonl`, `runs/run{1,2}/resid-abl-vs-stock.jsonl`, `runs/progress.log`, `runs/merged-analysis.json` (the result), `runs/merge-validation.json`, `runs/debug-fixture.json`. Code: `u1_p03.py`, `run_p03.sh`, `merge10.py`, `add_results_row.py`. Reproduce: README.md.
