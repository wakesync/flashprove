# RESULTS: 20261111-8-qwen-e2e-agreement

**Verdict: PASS vs the pre-registered bar in all 4 cells (XS18 and XS20, stock and abliterated). H1 (XS18) and H2 (XS20) hold. Measured, unreplicated, CPU, one deterministic run, no proof. Only the DeltaNet head computation is lowered. in_proj, out_proj, full attention, MLP, every norm and lm_head stay float64 in every path.**

## Plain-language summary

We ran the whole 64-layer Qwen3.8-27B model twice over the same 10 frozen prompts (1,461 positions), once on the stock checkpoint and once on the abliterated one. Each time, the integer DeltaNet head arithmetic (arm XS18 or XS20) replaced the float heads in all 48 DeltaNet layers, and we compared each next-token prediction with the float64 model's.
- The integer path picks the same top token as the float model at 1,460 or 1,461 of 1,461 positions in each of the 4 cells. The 3 flips are all on the digits prompt, at positions where the float model's top two logits are within 0.009 of each other.
- The typical next-token distribution differs by KL about 2e-6 to 3e-6 nats (median). The worst single position is 0.0057 nats. The bar was 1e-4 for the median and 0.1 for the max.
- The heads that miss PR #88's per-head bar sit mostly on the repeated-word prompt (also on repeated punctuation and digits). On the repeated-word prompt the logits move the most of any prompt, but not by enough to change a top-1 token or get near the bar.
- This says the integer head lowering keeps the model's outputs, under these conditions. It says nothing about proofs, soundness, or integer versions of the other layers.

## 1. Run record

- PREREG `PREREG.md`: first commit `436280e` alone, a one-line wording fix in the next commit (before any code). Amendment A-1 (BF16H count 608, not 612) was written during the run, before any registered output was read. No definition, threshold or limit changed.
- Code at the run: `661d4d4` (`e2e.py`, `run_e2e.sh`, `prompts-e2e.json`). Debug before the run on the fixture "The capital of Italy is" (not a suite prompt) only, stock layers 0 to 3, plus synthetic logits (`runs/debug-fixture/fixture.json`): duplicate paths bit-equal, save/load and resume bit-equal, streaming KL vs dense within 1.1e-14, ties broken to the lowest id. A timing probe before the PREREG computed no metric (PREREG "Runs").
- `runs/progress.log`: heavy slot granted 2026-11-11T23:16:54Z, hard stop 02:01:54Z, end rc=0 at 2026-11-12T01:07:04Z. One process, no resume needed (`runs/progress.log.jsonl` has one `start` and no `resume` entry). `time -v` (`runs/run.time`): 1:50:09 wall, 33,654 s user, 548% CPU, max RSS 8.06 GB (under the 14 GB stop), exit 0. Host shared and loaded (load average about 10 to 12). Order as registered: shared stock layers 0 to 16, then abl 17 to 63 and abl logits (done 00:21Z), then stock 17 to 63 and stock logits.
- Forward sanity check (registered): REF's top-1 after p01 is " Tokyo" (25358) on both checkpoints.
- Guard errors: none (no `errors-*.jsonl` written).
- Weights (`runs/manifest-check.json`, run after the job ended): every tensor fetched here has the same sha256 as PR #88's committed manifests where both exist (stock 850 / 850, abl 385 / 385, embedding rows 208 / 208), and matches PR #68's `diff.json` hashes for all 850 stock and 624 abl tensors. Of the 624 tensors fetched from both checkpoints (layers 17 to 63, final norm, lm_head), 70 differ, exactly the 70 PR #68 lists as changed (2 per layer in 17 to 51). So the abl leg ran the abliterated weights, and the stock leg the stock ones.
- Determinism (registered instead of repeats): REF#2 and XS18#2 on p01, p04 and p09 are bit-identical to REF and XS18 after every layer (64 layers on the abl leg, 47 on the stock leg) and in every logit metric, on both legs (`runs/summary.json` `determinism`). Five or more repeats of a deterministic forward would give the same numbers, so the spread reported is over positions and prompts.
- Cross-check, post hoc, not registered (`xcheck_pr88.py` -> `runs/xcheck-pr88.json`): on PR #88's 4 end-to-end prompts, this run's stock XS18 and BF16H top-1 lists equal PR #88's committed ones, and the per-position KL differs by at most 5.2e-15 nats (different batching and BLAS scheduling, same code).
- Watching during the run (disclosed): the per-layer residual divergence (`runs/divergence-abl.jsonl`) was looked at a few times while the run went on, before any logits existed. It changed nothing; the bar is fixed.

## 2. Registered cells vs the bar

Bar: top-1 agreement >= 99.0% of 1,461 positions, KL(REF || arm) median <= 1e-4 nats, max <= 0.1 nats, no guard error. Source `runs/summary.json`, table `runs/summary.md`, raw per-position values in `runs/e2e-{stock,abl}.json`.

| cell | top-1 agree | KL median (nats) | KL p99 | KL max | KL SD over positions | max logit diff / REF logit SD, median (max) | verdict |
|---|---|---|---|---|---|---|---|
| XS18 stock | 1,460 / 1,461 (99.93%) | 3.16e-6 | 4.26e-4 | 0.00279 | 1.49e-4 | 0.0191 (3.56) | **PASS** |
| XS20 stock | 1,461 / 1,461 (100%) | 1.99e-6 | 1.36e-4 | 0.00240 | 1.17e-4 | 0.0130 (3.45) | **PASS** |
| XS18 abl | 1,460 / 1,461 (99.93%) | 2.95e-6 | 3.47e-4 | 0.00566 | 2.15e-4 | 0.0193 (3.17) | **PASS** |
| XS20 abl | 1,460 / 1,461 (99.93%) | 1.95e-6 | 1.53e-4 | 0.00294 | 1.39e-4 | 0.0128 (3.90) | **PASS** |
| BF16H stock (context, 608 positions) | 608 / 608 | 2.72e-5 | 2.20e-3 | 0.00570 | 4.40e-4 | 0.236 (3.76) | no bar |
| BF16H abl (context, 608 positions) | 608 / 608 | 1.86e-5 | 2.21e-3 | 0.00834 | 5.97e-4 | 0.238 (4.08) | no bar |

H1 (XS18 passes on both checkpoints): **holds.** H2 (XS20 on both): **holds.**

Spread over the 10 per-prompt values (`spread_over_prompts` in `runs/summary.json`):
- Top-1 fraction per prompt: median 1.0, min 0.9961 (p06a, 255 / 256), max 1.0 in every cell (SD 0.0012, or 0 for XS20 stock).
- Per-prompt KL medians: XS18 stock 2.5e-9 to 9.7e-6 (median 5.3e-7), XS20 stock 3.9e-9 to 4.2e-6, XS18 abl 4.8e-9 to 6.2e-6, XS20 abl 2.4e-9 to 5.7e-6.
- Per-prompt KL max: XS18 stock 4.9e-6 to 0.00279, XS20 stock 3.4e-6 to 0.0024, XS18 abl 4.2e-6 to 0.00566, XS20 abl 2.3e-6 to 0.00294.

**Top-1 flips (all of them):**
- XS18 stock: p06a pos 109, REF 19 -> 17, REF top-1 margin 0.0088 logits, KL 5.8e-5.
- XS18 abl and XS20 abl: p06a pos 81, REF 16 -> 18, REF margin 0.0018 logits, KL 8.8e-6 / 7.0e-6.
- XS20 stock: none.
All 3 are near-ties in the float model (margins under 0.01 logits), where the next-token distribution is barely changed (KL under 1e-4).

**Reading the max logit difference column.** At most positions the largest single-logit difference is about 0.02 REF logit SDs for the integer arms, about 10 times smaller than BF16H's 0.24. The max over positions is 3.2 to 3.9 SD for the integer arms and 3.8 to 4.1 for BF16H. So at a few positions one logit moves a lot, but the KL stays small, which means that logit carries little probability. Which tokens these are was not analysed.

## 3. Where the per-head outliers sit, and whether they move the logits (descriptive, registered without a threshold)

Closed loop: at each of the 48 DeltaNet layers, the float64 heads were also run on the arm path's own head inputs, and rel_y per (prompt, layer, head) was logged (`runs/heads-{abl,stock}.jsonl`; 48 layers x 48 heads = 2,304 pairs per prompt and arm). Counts over all 48 layers per checkpoint are in `runs/heads-local.json` (`heads_local.py`). The stock leg reuses the shared layers 0 to 16 logged once in `heads-abl.jsonl`. Note that the per-prompt head table in `runs/summary.md` reads each leg's file only, so for stock it covers layers 17 to 63 only. Use `heads-local.json` for the full count.

Pairs with closed-loop rel_y > 0.05 (of 2,304 per prompt), and that prompt's end-to-end numbers (XS18 / XS20):

| prompt | heads > 0.05, stock | heads > 0.05, abl | rel_y max | top-1 agree (stock, abl) | KL max stock | KL max abl |
|---|---|---|---|---|---|---|
| p03-repeat-word (512) | 353 / 77 | 352 / 77 | 1.04 / 0.459 | 512, 512 (all) | 0.00279 / 0.00240 | 0.00566 / 0.00294 |
| p04-repeat-punct (64) | 46 / 6 | 46 / 6 | 0.388 / 0.079 | 64, 64 (all) | 0.00200 / 9.7e-5 | 1.1e-5 / 2.3e-6 |
| p06a-digits-256 (256) | 6 / 4 | 6 / 4 | 0.193 / 0.093 | 255 / 256 (stock), 255 / 255 (abl) | 3.5e-4 / 1.1e-4 | 1.2e-4 / 3.9e-5 |
| the other 7 prompts | 0 / 0 | 0 / 0 | at most 0.043 / 0.040 | all | at most 0.0025 / 3.5e-4 | at most 0.0023 / 2.4e-4 |

- On p03, 15.3% of XS18's (layer, head) pairs (3.3% for XS20) are over 0.05. They are spread over most DeltaNet layers (XS18: 33 distinct layers between 0 and 57), not concentrated in one. The worst pair is layer 6, head 24 (rel_y 1.04 XS18, 0.46 XS20), on both checkpoints. On this prompt the residual stream after the last layer differs from REF by 6.1% to 6.5% (XS18) and 7.0% to 7.3% (XS20) in relative L2, against at most 1.5% on every other prompt (BF16H: 13.5% to 13.8% on p03). So the per-head outliers do move the hidden state. The logits move less: p03 holds the largest single-position KL in every cell (stock XS18 0.00279, the largest of its 10 prompts, and the same holds for the other three cells), but its median KL (2.9e-6 to 4.4e-6) is in the same range as ordinary prompts, and no top-1 changes.
- The 3 top-1 flips are on p06a, the prompt with few outliers (6 / 4). The prompt with the most outliers (p03) has none. Over 10 prompts, the per-head outliers go with the largest residual drift and the largest single-position KL, not with top-1 changes. That is a co-occurrence over 10 prompts and 2 arms, not a causal attribution to particular heads.
- XS20 has about a quarter of XS18's outlier pairs on p03 and about half its KL max on abl, consistent with the state precision being what limits the repeated-word prompt (PR #88's slow-decay reading). Descriptive.
- On p04 the stock and abl logits differ in KL max (0.0020 vs 1.1e-5 for XS18) although the head counts are equal. The checkpoints differ from layer 17 on, so the same head error lands in different downstream weights. Not analysed further.

## 4. What this establishes, and what it does not

Established (measured, unreplicated, one deterministic CPU run): with XS18 or XS20 in place of the DeltaNet head computation in every DeltaNet layer, and everything else in float64, Qwen3.8-27B's teacher-forced next-token predictions on these 10 prompts match the float64 reference to the registered bar, on both the stock and the abliterated checkpoint. This includes the repeated-word prompt that fails PR #88's per-head bar and three prompts of at least 256 tokens.

**Not established:**
- No proof, no soundness. The arms are numerical lowerings, not sound proof-ready relations (PR #74 RESULTS 8.2). Nothing here says a verifier would accept or reject anything.
- in_proj, out_proj, attention, MLP, norms and lm_head in integers: all float64 here. The end-to-end error of a fully integer model is not measured and may be larger.
- Free-running generation. Teacher forcing only: each path sees the true prefix. A single flip in generation changes everything after it. Agreement over generated replies is not measured.
- Generality: 10 prompts, at most 512 tokens, English-heavy, one chat template. p10-long-mixed (1,008 tokens) and longer contexts were left out for CPU time. Behaviour at several thousand tokens of repetitive context is not known, and p03 shows that repetition is where the error grows.
- The float64 reference is a numpy reimplementation of the pinned `modeling_qwen3_5.py` (PR #88), not torch or a serving stack. Agreement with a BF16 serving deployment is not measured (BF16H here only emulates the heads).
- Whether these error sizes are small against the stock-vs-abl difference at the output (U1 substitution): not measured here. Both checkpoints were run, but their outputs were not compared with each other.
- The bar itself: the KL max of 0.1 nats turned out to be about 18 times above the worst observed value. The result also passes a much tighter max (0.01 nats), but that tighter bar was not registered and is not a claim.
- Replication by an independent lane: not done.

## 5. Deviations

- A-1: BF16H subset count 608, not 612 (arithmetic slip; subset unchanged; no bar).
- `runs/summary.md`'s per-prompt head counts for stock cover layers 17 to 63 only (the summariser reads one file per leg). The registered descriptive reading is computed over all 48 layers by `heads_local.py` -> `runs/heads-local.json`. The verdict is unaffected (heads have no bar).
- `runs/run.time`'s "Command being timed" line had the scratch directory replaced by `<SCRATCH>` before commit (`scrub_time_path.py`, `runs/scrub-time-path.json`, 1 replacement, no number changed).
- Post hoc, not registered: `xcheck_pr88.py` and the KL-0.01 remark in section 4.

## 6. Raw data

`runs/e2e-stock.json`, `runs/e2e-abl.json` (per position: top-1 of REF and each path, REF margin, KL, max diff / SD), `runs/divergence-{stock,abl}.jsonl` (per layer residual relative difference and determinism flags), `runs/heads-{stock,abl}.jsonl` (closed-loop per-head rel_y), `runs/manifest-{stock,abl}.json` (sha256 of every fetched tensor), `runs/manifest-check.json`, `runs/progress.log`, `runs/progress.log.jsonl`, `runs/run.log`, `runs/run.time`, `runs/summary.json`, `runs/summary.md`, `runs/heads-local.json`, `runs/xcheck-pr88.json`, `runs/debug-fixture/`.
