# RESULTS: 20261112-131-served-reply-agreement

**Verdict vs PREREG: H0 PASS, H1 (XS18) PASS, H2 (XS20) PASS.** Measured, unreplicated. No proof, no soundness claim.

## In plain language

An attested H200 serving deployment (vLLM, BF16) of the abliterated Qwen3.8-27B generated greedy replies (temperature 0, at most 64 tokens) to 10 harmless prompts. We fed each reply back through a float64 CPU forward of the same pinned checkpoint and through the XS18 / XS20 paths (integer DeltaNet heads, the rest float64), and asked at each of the 291 reply positions whether each path picks the token that was served.

- float64, XS18 and XS20 each pick the served token at **287 of 291** positions (98.6%; bar 98%).
- XS18 and XS20 pick **the same token as float64 at 291 of 291** reply positions (bar 99%), and at 226 of 226 prompt positions (descriptive).
- All 4 misses are the same in all three paths: float64 itself picks a different token from the served one. They are **serving-precision effects (BF16 GPU vs float64), not lowering effects**. Lowering effects: 0 for XS18, 0 for XS20.
- 8 of 10 replies are reproduced at every position by every path. On those 8 prompts, a greedy run of float64, XS18 or XS20 from the same prompt would have produced the same reply token sequence as rebuilt here. That does not hold for q02 and q09.
- The serving deployment returned identical text on all 3 repetitions of each of the 10 prompts.

## Collection (served side)

- Attestation summary `verified: true` before the batch (`runs/attestation.json`; only that flag and our timestamp are kept).
- Requests: lane total 33 of the 60 allowed. 2 were the template probe (1 attestation, 1 chat; not measured, `runs/template-probe.json`), 31 were the batch (1 attestation, 30 chat). No 429/503, no retries, no errors (`runs/batch-summary.json`). Batch wall time 94.6 s, including the bridge, attested TLS and the network path; not a GPU number.
- Served model identity as reported by the deployment configuration (not independently hashed): huihui-ai/Huihui-Qwen3.8-27B-abliterated @ 739e3c5b..., bfloat16, vLLM engine image sha256:4a2f33a8....
- Every reply had an empty reasoning field. 8 replies stopped (`stop`), q09 and q10 hit 64 tokens (`length`).
- Serving determinism: the 3 repetitions of each prompt are text-identical and report the same usage counts (10 of 10 prompts; `runs/served-ids.json`, `reps_text_identical`). The route gives no token ids, so token-level identity across repetitions is not observed.

## Token-id reconstruction and exclusions

Rule fixed in PREREG (template learned on one probe request beforehand): pinned template with thinking disabled, pinned tokenizer, reply + `<|im_end|>` on `stop`. **10 of 10 prompts included, 0 excluded.** For every prompt the rebuilt prompt count equals `usage.prompt_tokens` and the rebuilt reply count equals `usage.completion_tokens`; decoding the rebuilt reply ids gives back the served text exactly. Measured positions: 291 (reply) and 226 (prompt, descriptive). Equal counts are necessary, not sufficient for equal ids (see "What is not established").

## Three-way table (`runs/summary.md`, `runs/summary.json`)

| prompt | reply tokens | served = REF | served = XS18 | served = XS20 | REF = XS18 | REF = XS20 | whole reply REF / XS18 / XS20 |
|---|---|---|---|---|---|---|---|
| q01 | 2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | yes / yes / yes |
| q02 | 36 | 34/36 | 34/36 | 34/36 | 36/36 | 36/36 | no / no / no |
| q03 | 8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | yes / yes / yes |
| q04 | 10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | yes / yes / yes |
| q05 | 23 | 23/23 | 23/23 | 23/23 | 23/23 | 23/23 | yes / yes / yes |
| q06 | 4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | yes / yes / yes |
| q07 | 27 | 27/27 | 27/27 | 27/27 | 27/27 | 27/27 | yes / yes / yes |
| q08 | 53 | 53/53 | 53/53 | 53/53 | 53/53 | 53/53 | yes / yes / yes |
| q09 | 64 | 62/64 | 62/64 | 62/64 | 64/64 | 64/64 | no / no / no |
| q10 | 64 | 64/64 | 64/64 | 64/64 | 64/64 | 64/64 | yes / yes / yes |
| **all** | **291** | **287/291** | **287/291** | **287/291** | **291/291** | **291/291** | 8 / 8 / 8 of 10 |

Spread over the 10 prompts of the per-prompt fraction "served = path": median 1.0, min 0.944 (q02), max 1.0, population SD 0.018, identical for REF, XS18 and XS20. "REF = XS18 / XS20": 1.0 on every prompt.

## Every disagreement (`runs/summary.json` `disagreement_positions`, `runs/disagreement-text.json`)

| prompt | reply pos | served | float64, XS18, XS20 all pick | float64 top-2 margin (logits) | kind |
|---|---|---|---|---|---|
| q02 | 30 | " like" (1040) | "," (11) | 0.212 | serving precision |
| q02 | 32 | " or" (466) | " and" (321) | 1.386 | serving precision |
| q09 | 10 | " in" (303), start of " inky" | " dark" (6121) | 0.074 | serving precision |
| q09 | 45 | " safely" (20359) | " to" (310) | 1.066 | serving precision |

In each case the served text continues with the served token, re-encoding the remaining served text canonically starts with the served id, and float64's pick is not a prefix of the remaining served text. So these are not re-tokenisation artefacts of the kind "same text, other ids" (descriptive check added after the run, `disagreement_text.py`). Two of the four are near-ties (margin under 0.25 logits). Two have float64 top-2 margins of about 1.1 and 1.4 logits, which is larger than one might expect from BF16 rounding alone. We do not know why. It could be BF16 accumulation through 64 layers, a kernel or batching difference in the serving engine, or a difference between the served weights or configuration and the pinned revision as read here. Counts cannot tell these apart, and the route exposes no logits. Because the replies are teacher-forced, a miss at one position does not change the input at later positions.

Stop positions (`runs/stop-ids.json`): on all 8 replies that stopped, float64, XS18 and XS20 all pick `<|im_end|>` (248046), with float64 top-2 margins from 8.4 to 16.5 logits. The accepted set {248046, 248044} was not needed.

## Controls

- Determinism: REF#2 and XS18#2 on q01 and q02 are bit-identical to REF and XS18 in the residual after each of the 64 layers and in the top-1 picks (`runs/divergence-abl.jsonl`, `det_bit_equal`; `runs/summary.json` `determinism`).
- Weights: 226 stock tensors (layers 0 to 16 and the embedding rows used) and 624 abl tensors (layers 17 to 63, final norm, lm_head) were fetched by range request. Every sha256 matches PR #124's committed manifests for the same revisions (0 mismatches; 70 shared embedding rows also match; `runs/manifest-check.json`).
- Sanity bar (float64 vs served >= 80%): 98.6%, met.
- Run: one heavy job, through the big-memory lock and `fp-heavy.sh`, `taskset -c 0-5`, MemAvailable 12.5 GB at start. Slot granted 16:12:35Z, finished rc 0 at 16:47:55Z (35:20 wall, registered hard stop 17:52:35Z not reached), max RSS 7.26 GB (`runs/progress.log`, `runs/run-time.json`).
- Debug before the registered run (as registered): the template-probe sequence (22 tokens, not a suite prompt), stock layers 0 to 3, timing only. No suite prompt and no lm_head row were touched before the registered run.
- Descriptive, not registered: the closed-loop per-head error log (`runs/heads-abl.jsonl`) and per-layer residual drift (`runs/divergence-abl.jsonl`) are committed as PR #124's code writes them. They are not analysed here.

## What is NOT established

- **No proof and no soundness.** Only the DeltaNet head computation is integer. in_proj, out_proj, attention, MLP, norms and lm_head are float64. The arms are numerical lowerings, not sound relations.
- **Token ids are reconstructed, not observed.** The route returns text and counts only. Equal counts plus an exact decode round trip leave open a non-canonical generation of the same text with the same number of tokens. The 287 agreeing positions make that unlikely to matter, but it is not excluded.
- **Served model identity** is as reported by the deployment configuration and is not hashed here. The 4 misses with margins above 1 logit are unexplained (see above).
- **Small n.** 10 short prompts, 291 reply positions, one checkpoint (abliterated), greedy only, at most 64 tokens. One deterministic CPU run. All replies were collected within about 10 minutes (probe 15:59Z, batch 16:08Z to 16:10Z), from one deployment state.
- "A greedy integer run would have produced the reply" holds only for the 8 fully matched replies and only under teacher forcing with reconstructed ids. No free-running generation was done on the CPU.
- The 98% bar for served vs float64 was fixed before the data. With n = 291 the minimum passing count is 286 (0.98 x 291 = 285.2); 287 is one position above it. One more miss would still pass, two more would fail.
- Not replicated. Unchanged behaviour of the abliterated model vs stock is not studied.

## Deviations from PREREG

- None in the measurement. Descriptive additions after the run, all labelled as such: `disagreement_text.py` (decoded text at the 4 misses), `stop_ids.py` (which end id each path picked, which the PREREG asked to report), `check_manifests.py` compares with PR #124's manifests (same code path) rather than PR #88's.
- The identifier scrub named in the lane rules (`REVIEW69-ASTRA-scrub.py`) could not run (its clone no longer exists). The same private identifier list was checked with the coordinator's file scrubber over every published file: 0 matches. This is a process note, not part of the result.

## Raw data

`runs/replies.jsonl` (30 served replies), `runs/served-ids.json` (rebuilt ids, inclusion), `runs/forward.json` (per-position top-1 of every path and float64 top-2 margin for all 517 input positions), `runs/summary.json` / `summary.md`, `runs/disagreement-text.json`, `runs/stop-ids.json`, `runs/divergence-abl.jsonl`, `runs/heads-abl.jsonl`, `runs/manifest-*.json`, `runs/manifest-check.json`, `runs/progress.log*`, `runs/run.log`, `runs/run-time.json`, `ENV.json`.
