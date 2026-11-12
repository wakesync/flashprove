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
- Nothing on p03-repeat-word (512 positions, not run). That prompt holds PR #124's largest E values, so including it would likely lower the shares. The registered full-set result does not exist.
- E is head-only (PR #124). A fully integer model (MLP, attention, projections; #132) may have a larger E.
- This is teacher-forced and per-position. It says nothing about served replies, sampled text, any acceptance rule, or verifier design. It is one deterministic run, with spread over positions only.
- Refusal behaviour is not judged. Top-1 differences are reported as ids only (`runs/analysis.json` prompts.*.differ_positions).

## Deviations
PREREG Amendment A-1, registered before the run: start from PR #124's x16 state (sha256 6d495e1b...), a fused single pass, the real-weight fixture dropped, and grant-time prompt tiers. Condition (3) was rescaled to 80% of the prompts run. No other changes.

## Files
`runs/d-per-position.json` (raw per-position D, reverse KL, both top-1s and margins), `runs/analysis.json`, `runs/progress.log*`, `runs/run.log`, `runs/run.time`, `runs/manifest-{stock,abl}.json`, `runs/resid-abl-vs-stock.jsonl`, `runs/debug-synth.json`. Code: `u1_fused.py` (registered driver), `u1_margin.py` (helpers `two_way`, `final_hidden`; its `run` / `fixture` commands were not used), `run_fused.sh`, `analyse.py`, `add_results_row.py`. Reproduce: `flock <bigmem.lock> fp-heavy.sh taskset -c 6-11 bash run_fused.sh <scratch> <x16.npz>`, then `python3 analyse.py`.
