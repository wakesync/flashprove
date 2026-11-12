# RESULTS: 20261112-134-u1-margin

**Verdict: FAIL (mixed), subset result.** It ran on 9 of the 10 registered prompts (949 of 1,461 positions). p03-repeat-word was left out under PREREG Amendment A-1 tier 2, because the slot was granted at 18:25:18Z. Measured, unreplicated.

## Plain summary
The float64 stock and abliterated Qwen3.8-27B give different next-token distributions. At the median position that difference (D) is about 280 times PR #124's head-only integer lowering error (E). It is not uniformly large, though. On about 7% of positions D is within 10x of E, mostly on the repeated-punctuation and digits prompts, so the registered bar fails. On chat and ordinary-text prompts, D is more than 10x E at 96 to 100% of positions. The two float64 references pick a different top-1 token at 23 of 949 positions, which matches PR #124's committed count exactly.

## Validity gates (all pass)
- (a) p01 last-position top-1 is " Tokyo" (25358) on both checkpoints.
- (b) This run's REF top-1 and margins reproduce PR #124's committed `ref_top1` / `ref_margin` on both checkpoints at all 949 positions. The max absolute margin difference is 0.0, so they are bit-identical (`runs/analysis.json` gates.b_reproduce). This also checks the external x16 state end to end.
- (c) Every fetched tensor's sha256 matches PR #124's committed manifests: 624 stock and 71 abl tensors (the 70 changed ones plus the final norm), 0 mismatches.

## Numbers vs the registered bar (XS18, E = max(E_stock, E_abl); `runs/analysis.json`)
| | value | bar | |
|---|---|---|---|
| pooled share D > 10 E | 0.933 (885 / 949) | >= 0.95 | fail |
| pooled share D > 100 E | 0.656 | >= 0.50 | pass |
| prompts with share(D > 10 E) >= 0.90 | 7 of 9 | >= 8 (80% of prompts run, A-1) | fail |

log10(D / E) over positions: median 2.45, SD 0.97, min -1.97, p1 0.41, p10 1.16, p90 3.67, max 5.73. D median 3.8e-4 nats (min 2.5e-12, max 1.67). E (XS18) median 2.4e-6, max 2.5e-3.
Secondary (XS20, descriptive): share D > 10 E 0.985, D > 100 E 0.740, 9 of 9 prompts at >= 0.90.

Positions with E <= 0 (the registered exception: the ratio counts as +inf in the shares and is left out of the finite log10 statistics). XS18: none. XS20: one, p11-chat-long t = 279, where E_stock = -7.1e-15 and E_abl = 0.0 in PR #124's committed files and D = 2.5e-12 (the smallest D of the run). It is counted as above both 10 E and 100 E in the XS20 shares, and the XS20 log10 statistics are over the other 948 positions (`postreview/input-validation.json`).

Per prompt (XS18): share D > 10 E / D > 100 E / D median / top-1 differ (PR #124 count)
- p01-ordinary-short (13): 1.000 / 1.000 / 1.1e-3 / 0 (0)
- p07-chat-ordinary (23): 0.957 / 0.913 / 3.0e-5 / 0 (0)
- p08-chat-refusal (39): 1.000 / 1.000 / 1.6e-3 / 1 (1)
- p09-multilingual (21): 1.000 / 1.000 / 4.3e-3 / 0 (0)
- p02-ordinary-paragraph (107): 1.000 / 0.944 / 7.7e-3 / 2 (2)
- **p04-repeat-punct (64): 0.781 / 0.422 / 2.6e-5 / 0 (0)**
- p05-code (144): 0.986 / 0.708 / 1.2e-5 / 0 (0)
- **p06a-digits-256 (256): 0.840 / 0.164 / 1.2e-4 / 3 (3)**
- p11-chat-long (282): 0.979 / 0.911 / 7.2e-3 / 17 (17)

The failing prompts are both deterministic-continuation prompts (punctuation, digits). There the two checkpoints nearly coincide.

## Integer-arm flip positions (PR #124)
- p06a t = 109 (stock XS18 flip): D = 1.6e-3, E = 5.8e-5, D/E = 27.
- p06a t = 81 (abl XS18 and XS20 flip): D = 4.1e-4, E (XS18) = 8.8e-6, D/E = 47; XS20 D/E = 58.

## What is NOT established
- Nothing on p03-repeat-word (512 positions, not run). That prompt holds PR #124's largest E values, but its D was never computed, so the direction in which it would move the shares is unknown. The registered full-set result does not exist.
- E is head-only (PR #124). A fully integer model (MLP, attention, projections; #132) may have a larger E.
- This is teacher-forced and per-position. It says nothing about served replies, sampled text, any acceptance rule, or verifier design. It is one deterministic run, with spread over positions only.
- Refusal behaviour is not judged. Top-1 differences are reported as ids only (`runs/analysis.json` prompts.*.differ_positions).

## Deviations
PREREG Amendment A-1, registered before the run: start from PR #124's x16 state (sha256 6d495e1b...), a fused single pass, the real-weight fixture dropped, and grant-time prompt tiers. Condition (3) was rescaled to 80% of the prompts run. No other changes before the run.

Notes on A-1 (added after review, PREREG Amendments A-2 and A-3):
- **Time of A-1.** A-1 is headed "2026-11-12T17:50Z", but it was committed at 17:39:26Z (commit c56e972a). The heading was a clock estimate; the commit time is the record. Either way A-1 comes before the slot grant at 18:25:18Z and before any D existed.
- **What A-1 left alone and what it changed.** A-1's heading says "no metric, threshold or hard stop changes". The numerical cutoffs are unchanged: 0.95 and 0.50 for the pooled shares, and 0.90 per prompt. The prompt count of condition (3) did change: "at least 8 of the 10 prompts" became "at least 80% of the prompts run", rounded up, which is 8 of 9 on the tier that ran. The result is 7 of 9, so condition (3) fails under that rule and would also fail a literal 8.
- **The subset was chosen with E visible.** The tiers were written after PR #124's per-position E had been read, and the prompt left out of tier 2 (p03) has PR #124's largest E, so that fact was available when the tier was defined. A-1 records why a subset was run (the time left before the hard stop) and each tier's size. It does not say why p03 is the prompt that tier 2 drops. p03 is the largest prompt (512 of the 1,461 positions), so dropping it saves the most time, but that is an inference, not a recorded reason. No D existed for any prompt at that time.

## Changes after review (no rerun of the model, no number changed)
The first review round of PR #139 found that `analyse.py`, as committed for the registered run, accepted incomplete evidence. With both tensor manifests emptied it still reported the manifest gate as passed, with 0 tensors compared. With the D file also cut down to p08-chat-refusal it reported PASS, with the " Tokyo" check skipped and 1 prompt needed of 1 run. The committed result was not produced that way: its evidence is complete (`postreview/input-validation.json`). Both reviewers also report that they recomputed the numbers above from the committed files with their own scripts; those are the reviewers' statements, in the PR comments [6834296442](https://github.com/wakesync/flashprove/pull/139#issuecomment-6834296442) and [6834351986](https://github.com/wakesync/flashprove/pull/139#issuecomment-6834351986), and their scripts are not in this repository.

`analyse.py` was changed after the run (PREREG Amendment A-2 item 4). It now refuses to give a verdict (exit 2, nothing written) unless:
- the prompts are exactly the registered tier for the logged grant time, each with the frozen prompt's number of positions;
- every value it uses is present, finite and of the right type;
- the manifests hold exactly the expected fetched tensors with their hashes (624 stock, 71 abliterated);
- `runs/progress.log` shows one grant, the matching tier line and one clean end before the hard stop.

The " Tokyo" check must be true, and each fetched tensor's hash must also equal PR #87's. The D against E formulas and the thresholds are untouched.

Part of this goes beyond the registered gates (PREREG Amendment A-3). The registered gate (c) compares hashes "where both exist", which is what the old script did. Requiring the full set of expected tensors and equality with PR #87's hashes are requirements added after the results were known. The check that the log shows a clean end before the registered hard stop is also new in the script. They can only refuse or KILL an input that was accepted before, never the reverse, and the committed run meets all of them.

Receipts, all under `postreview/` (new files; nothing under `runs/` was modified):
- `analysis.json`: the changed script run on the committed `runs/` inputs. It is byte-identical to the committed `runs/analysis.json` (sha256 d7d127f6...54a11): FAIL (mixed), 885 / 949 above 10 E, 623 / 949 above 100 E, 7 of 9 prompts. `reproduction.json` records the comparison and `input-validation.json` what was checked.
- `negative-tests.json`: `test_analyse.py`, 39 cases on temporary copies of the committed run files. 1 unchanged copy reproduces the committed analysis; 31 incomplete, malformed or wrong-tier inputs are refused, including the two reviewer cases above; 5 complete inputs that fail a gate give KILLED; 1 checks that an existing analysis is not overwritten; 1 is the documented limit below. All 39 behave as stated.
- `negative-tests-on-prereview-script.json`: the same 39 cases against the script as it was for the registered run. Only 2 behave as stated (the unchanged copy and the documented limit). Of the 31 inputs that should be refused, that script wrote a verdict for 23: PASS for 2 (both p08-only copies), FAIL (mixed) for 17 and KILLED for 4. The other 8 stopped on a Python error and wrote nothing. The 5 gate-failure cases did give KILLED, but with exit status 0. It also overwrote the existing analysis file.

Limit of the new validation: the tier is read from the grant time in the run's own `runs/progress.log`, which is not authenticated. A copy whose log, tier line and D file are all rewritten to another registered tier is accepted as that tier. The validation ties the prompt set to the logged grant time; it does not prove the log.

## Files
`runs/d-per-position.json` (raw per-position D, reverse KL, both top-1s and margins), `runs/analysis.json`, `runs/progress.log*`, `runs/run.log`, `runs/run.time`, `runs/manifest-{stock,abl}.json`, `runs/resid-abl-vs-stock.jsonl`, `runs/debug-synth.json`. Code: `u1_fused.py` (registered driver), `u1_margin.py` (helpers `two_way`, `final_hidden`; its `run` / `fixture` commands were not used), `run_fused.sh`, `analyse.py`, `add_results_row.py`. Post-review: `test_analyse.py`, `compare_postreview.py`, `postreview/`.

Reproduce the analysis from the committed files (seconds, no weights): `python3 analyse.py runs <new dir>`, then `python3 test_analyse.py`. `analyse.py` does not overwrite an existing `analysis.json`, so give it a new output directory.

Reproduce the run: `flock <bigmem.lock> fp-heavy.sh taskset -c 6-11 bash run_fused.sh <scratch> <x16.npz>`. The `x16.npz` state (REF residuals after layer 16, from PR #124's run scratch) is not in the repository; only its sha256 is logged, and validity gate (b) checks it end to end. So a third party cannot rerun the registered job from the committed files alone. `u1_margin.py run <scratch> <runs>` without an x16 argument computes layers 0 to 16 itself; that path was not run on real weights by this lane.
