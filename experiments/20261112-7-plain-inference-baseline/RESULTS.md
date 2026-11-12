# RESULTS: plain inference baseline of the served Qwen3.8-27B through the attested route (Part of #7)

**Measured, unreplicated, through the route.** One registered batch, 2026-11-12 16:39:31Z to 16:48:12Z, 110 chat requests
(10 cells x (1 warm-up + 10 timed)), sequential, batch size 1 from this client, under the shared route lock. Attestation
`verified = true` at the debug check, at batch start and at batch end. 0 HTTP errors, 0 retries. Raw rows:
[runs/batch.jsonl](runs/batch.jsonl) (every row, warm-ups flagged, prompt text stored), statistics:
[runs/summary.json](runs/summary.json) (`python3 route_bench.py analyze`, deterministic), environment: [ENV.json](ENV.json).

## What these numbers are

Client wall time around one non-streaming HTTP request. They include a local bridge process on the client host, attested TLS,
the network path from the client host to the deployment, the engine's HTTP and scheduling layers, one request in flight from this
client at batch size 1, an engine configuration this lane does not control, and a card shared with a second loaded engine and with
other callers of the route. **A lower bound on what the card can do for this model, not a GPU benchmark.** Model, revision, dtype
and engine image are as reported by the deployment configuration (ENV.json), not independently hashed.

Reasoning tokens: no reply in any file (debug, probe, batch) carried a `reasoning_content` / `reasoning` field, and no `content`
contained a think block. So `usage.completion_tokens` here counts only visible reply tokens; whether the engine would count
reasoning tokens in `usage` when it emits them is **not observed** by this run.

## Against the registration

- Debug fixture as registered (2 requests: attestation, one 8-token chat). Admission probe sent once, as registered: rejected with
  HTTP 413 `prompt over 16000 chars`, a character limit in the route, with no token count. Amendment 1 (committed 22638a2 and
  pushed before any registered request) re-sized the prefill cells in words under 90% of that limit (16, 256, 512, 1,024, 2,048
  words) and the repeated-prompt case to 1,024 words. No second probe, no search. Decode arm unchanged.
- Requests: 115 of the 150 cap (2 debug, 1 probe, 110 cells, 2 attestation). Summed request time 525.5 s of the 1,140 s cap.
  `max_tokens` at most 256. No prompt hit the 14,400-character truncation (largest 2,048-word prompt is below it).
- PASS rules: both arms PASS (extreme cells' min/max do not overlap, every cell has 10 timed rows, every decode row ended with
  `finish_reason = length`, 40 of 40, positive slope).

## Cells (timed rows only, n = 10 each; seconds)

| cell | served prompt tokens (median) | completion tokens | median | SD | min | max |
|---|---|---|---|---|---|---|
| prefill 16 words | 41.5 | 1 | 0.382 | 0.020 | 0.346 | 0.396 |
| prefill 256 words | 292 | 1 | 0.388 | 0.020 | 0.349 | 0.404 |
| prefill 512 words | 555.5 | 1 | 0.379 | 0.022 | 0.351 | 0.401 |
| prefill 1,024 words | 1,087.5 | 1 | 0.552 | 0.021 | 0.510 | 0.572 |
| prefill 2,048 words | 2,145.5 | 1 | 0.723 | 0.019 | 0.671 | 0.741 |
| decode 16 | 32 | 16 | 1.772 | 0.068 | 1.715 | 1.941 |
| decode 64 | 32 | 64 | 6.224 | 0.226 | 6.164 | 6.923 |
| decode 128 | 32 | 128 | 12.152 | 0.187 | 11.982 | 12.654 |
| decode 256 | 32 | 256 | 24.123 | 0.335 | 23.630 | 24.566 |
| repeated prompt, 1,024 words (labelled, not in any fit) | 1,073 | 1 | 0.399 | 0.029 | 0.355 | 0.428 |

## Answer

- **Decode: 0.0931 s per generated token (OLS over 40 rows, SE 0.0004, R² 0.999), about 10.7 generated tokens per second at batch
  1 through the route.** Two-point cross-check from the 16 and 256 medians: 0.0931 s per token. Intercept 0.31 s (fixed
  per-request overhead plus prefill of the 32-token prompt).
- **Prefill: 0.000178 s per prompt token (OLS over 50 rows, SE 0.000007, R² 0.93), about 5,600 prompt tokens per second, over
  42 to 2,146 prompt tokens.** Two-point cross-check (41.5 vs 2,145.5 medians): 0.000162 s per token (6,200 per second).
  Intercept 0.33 s. The arm PASSes, but it is not linear across its range: the 16, 256 and 512-word cells overlap each other
  (medians 0.38 s), and the rise appears only from about 1,000 tokens. Below that the per-request overhead hides prefill. The
  slope is a short-prompt figure fitted mostly on the two largest cells and should not be extrapolated to long contexts.
- **Repeated prompt (labelled):** the identical 1,024-word prompt took a median 0.399 s against 0.552 s for unique 1,024-word
  prompts, ranges not overlapping. Consistent with the engine reusing a cached prefix, about 0.15 s saved per request. This is
  why the registered prefill arm uses unique prompts.
- Context only, no claim: 10.7 tokens per second is well below what a single uncontended H200 is usually quoted at for a 27B BF16
  model at batch 1. The gap is unexplained here (route overhead is in the intercept, not the slope, so candidates are the shared
  card, the second engine, CC mode and engine configuration). This run cannot separate them.

## Conditional multiple of plain inference (does not change PR #126)

Inputs, both named: (1) the merged cost model's GPU-seconds per 1,000 window tokens (`experiments/20261112-7-cost-model/
model-output.json`, `model.gpu_s_per_1k`; extrapolated, not measured, no Qwen proof exists), and (2) the fitted slopes above,
converted to route seconds per 1,000 tokens: 0.178 s (prefill), 93.1 s (decode). Script: [conditional_multiple.py](conditional_multiple.py),
output [runs/conditional_multiple.json](runs/conditional_multiple.json).

**If** proving a 1,024-token window costs what the cost model's central rate says (42.5 GPU-s per 1,000 tokens), **and if** the
plain-inference cost of that window is what this route measured, **then** proving costs about **240 times** a prompt-only (prefill)
pass of the window, and about **0.46 times** generating the window token by token at batch 1. At the high rate (86.3) the factors
are 486x and 0.93x; at the small-example rate (2,559) 14,400x and 27x. At T = 64 central: 541x and 1.03x.

Why both, and why neither is "the" multiple: proving covers the whole window (prompt plus reply) in one pass, like prefill, so the
prefill ratio is the like-for-like compute comparison; but a served reply is generated at decode speed, so the decode ratio is the
user-facing one. The units also differ: the cost model is GPU-seconds on a dedicated card; the route figure is wall seconds of
one stream on a shared card, and decode at batch 1 leaves most of the card idle (a batched server shares that time across many
streams). The decode ratio therefore overstates how cheap proving is relative to serving. Not a cost claim, not a bound.

## Not established

- Any GPU-level number: no telemetry, no engine logs, no streaming (no time-to-first-token, no inter-token latency).
- Prefill at long contexts (the route rejects prompts over 16,000 characters, about 2,500 tokens of this vocabulary).
- Batched throughput, the effect of the second engine or of other callers, whether CC mode costs anything.
- Whether `usage` counts reasoning tokens (none were emitted).
- Replication (one batch, one lane, one day).
