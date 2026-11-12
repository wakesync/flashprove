# PREREG: 20261112-7-plain-inference-baseline

Issue: #7. Lane: h200base7. Date (UTC): 2026-11-12 16:25. Base commit: d96cdda066f443a9b0c0f481b30eaaf45108ae65.

Plain (unproved) inference speed of the served abliterated Qwen3.8-27B, measured as wall time per request through an existing
attested serving route to one H200 (vLLM, BF16, single stream). It supplies the denominator that the merged cost model
(`experiments/20261112-7-cost-model/`, PR #126) could not state: "proof cost as a multiple of plain inference".

What the numbers will include, stated before any run: a local bridge process on the client host, attested TLS, the network path
from the client host to the deployment, the serving engine's own HTTP and scheduling layers, one request at a time (batch size 1
from this client), an engine configuration this lane does not control, and a card that is shared with a second loaded engine and
with other callers of the same route. The result is a lower bound on what the card can do for this model, not a GPU benchmark.

## Hypothesis

Through this route, with one request in flight from this client, wall time per request is (a) increasing and close to linear in
the served `usage.prompt_tokens` at `max_tokens = 1`, and (b) increasing and close to linear in the served
`usage.completion_tokens` at a fixed short prompt, so that a fixed per-request overhead (intercept), seconds per prompt token and
seconds per generated token can each be stated, with the extreme cells of each arm separated by non-overlapping min/max ranges.

## Metric

- Wall seconds per request, `time.monotonic()` on the client around one HTTP POST to the bridge, from just before the request is
  sent to just after the full JSON body is read. Non-streaming (the route always sends `stream=false`), so time-to-first-token
  is not observable; prefill and decode are separated by design (two arms below).
- Token counts: the served `usage.prompt_tokens` and `usage.completion_tokens` of each response. No client-side token estimates
  enter any fit. `finish_reason` is recorded for every row.
- Per cell: n, median, SD (sample), min, max of wall seconds; median of served token counts.
- Fits (ordinary least squares over the timed rows, warm-ups excluded):
  - Prefill arm: wall = a_p + b_p x prompt_tokens. b_p = seconds per prompt token; a_p = fixed overhead plus one decode step.
  - Decode arm: wall = a_d + b_d x completion_tokens. b_d = seconds per generated token; a_d = fixed overhead plus prefill of the
    fixed short prompt.
  - Reported as rates: 1 / b_p prompt tokens per second, 1 / b_d generated tokens per second. Also a two-point slope from the
    medians of the largest and smallest cell of each arm, as a cross-check of the fit.
- Repeated-prompt case (labelled separately, not part of either fit): the same prompt text sent every time, to show what the
  engine does with a prompt it may have cached. Compared with the unique-prompt cell of the same target length.
- Whether reasoning tokens are counted in `usage`: recorded per row from the presence of a non-empty `reasoning_content` /
  `reasoning` field in the reply, and stated in RESULTS.md.

## Acceptance threshold

- PASS (rate stated as measured): in each arm, the min/max ranges of the smallest and largest cell do not overlap, AND every
  timed cell of the decode arm finished with `finish_reason = length` in at least 8 of its 10 timed rows, AND the OLS slope is
  positive. A rate that passes is reported as "measured, unreplicated, through the route".
- If one arm fails, that arm's rate is reported as NOT resolved (number shown, labelled unresolved) and the other arm stands
  on its own. No claim is made from overlapping ranges.
- The cost-model multiple is written only as a conditional statement naming both inputs (the cost model's GPU-seconds per
  window token, the rate measured here), and only for an arm that passed.

## Kill criterion

- Attestation `verified` is not `true` at the start: no timed requests at all, publish the negative.
- HTTP 429 or 503: wait 30 s, retry once; a second failure stops the batch. The batch is not restarted; cells with fewer than 10
  timed rows are reported as short and do not count toward PASS.
- Any other HTTP error or a transport timeout (120 s): record the row, continue; two such errors in a row stop the batch.
- Caps (hard): at most 150 requests in total from this lane, including the probe, attestation checks and debug requests;
  `max_tokens` at most 256; at most 20 minutes of summed request time (the runner stops sending when the sum passes 1,140 s).
- Lane hard stop 2026-11-12T18:05:00Z: whatever has been collected is committed and written up as partial.

## Runs

Design. All requests: `temperature = 0`, `seed = 1112`, one user message, no system message, sequential, all under the shared
route lock (`flock`), waiting if another lane holds it.

1. Debug (2 requests, not in any statistic, separate fixture): one short request with a prompt that no registered cell uses
   ("Name one prime number."), `max_tokens = 8`, to check the runner's parsing; and one `GET /attestation`. Logged to
   `runs/debug.jsonl`.
2. Admission probe (exactly 1 request, not in any statistic): a unique random-word prompt built to about 8,192 served tokens
   (word count calibrated from nothing: 8,192 words of the fixed vocabulary below), `max_tokens = 1`. If it is admitted, its
   `usage.prompt_tokens` gives the words-to-tokens ratio used to size the cells, and every cell below is run. If it is
   rejected, the error text's stated limit (if any) is recorded and every prefill cell whose target exceeds 90% of that limit
   is dropped, without a second probe. No search.
3. Prefill arm (unique prompts): targets of about 128, 1,024, 2,048, 4,096 and 8,192 served prompt tokens, `max_tokens = 1`.
   Every prompt is a fresh random sequence from a fixed 512-word vocabulary drawn with a per-request seed (prompt seed =
   1112000 + request index), starting with a random 16-hex-digit tag, so no two prompts share a prefix beyond the chat template's
   first few tokens. Prompt text is stored for every row.
4. Decode arm: fixed short prompt "Count upward from 1, writing every number in words, separated by commas. Do not stop."
   with `max_tokens` in {16, 64, 128, 256}. The same prompt every time (its prefill is a constant small part of the intercept).
5. Repeated-prompt case (labelled, separate): one fixed random prompt of the 4,096 target, sent identically every time,
   `max_tokens = 1`.

Counts: 10 cells (5 prefill, 4 decode, 1 repeated), each 1 warm-up + 10 timed = 110 requests. Plus 1 probe, 2 debug, and 2
attestation checks (start of the registered batch and end) = 115 requests. Under the 150 cap.

Ordering: round 0 is the warm-up round, rounds 1 to 10 are timed. In each round every cell is sent once, in an order shuffled
with `random.Random(1112 + round)`. Interleaving spreads drift from other callers across cells instead of onto one cell.
Warm-ups are logged with `warmup: true` and excluded from every statistic.

Exclusions: rows with an HTTP error are excluded from the statistics and listed. Decode rows with `finish_reason` other than
`length` are kept in the raw data and in the fit (the fit uses the served completion count), and counted against the PASS rule
above. Nothing else is excluded.

Seeds: request seed 1112; prompt seeds 1112000 + index; order seeds 1112 + round.

## Prior art

- Serving-engine benchmarks: vLLM's own `benchmark_latency` / `benchmark_serving` (TTFT, TPOT, ITL with streaming), the
  MLPerf Inference LLM scenarios, and vendor numbers for H100/H200 decode at batch 1. They measure the engine on the box; this
  lane cannot (no streaming, no shell, a shared card), so its numbers are route-level and are not comparable to those as GPU
  figures.
- Proof-overhead framing: upstream FlashProve's guide/performance.md compares proving to plain prefill on Maverick (FP8, 8 H100s),
  calculated, not reproduced here. zkML systems (EZKL, zkLLM, Jolt, Expander) report proof time against plain inference of much
  smaller models; TEE inference (H100 CC, Phala, Atoma, Nillion) reports CC-on overheads of a few percent on the engine. None
  gives a plain Qwen3.8-27B rate on this route.
- New here: a pre-registered, route-level plain inference rate of the exact checkpoint the FlashProve Qwen port targets, split
  into prefill and decode by design, used only as a conditional denominator for the cost model.

## Amendments

(empty at registration)

### Amendment 1 (2026-11-12 16:40 UTC, after the admission probe, before any registered request)

The single admission probe (8,192 words, 55,593 characters, `max_tokens = 1`) was rejected by the route with HTTP 413
`prompt over 16000 chars`. This is a character limit in the route in front of the engine, not the engine's context limit, and
it carries no token count, so the words-to-tokens ratio could not be read from the probe. Per the registered rule (no second
probe, no search), prefill cells are re-sized against 90% of the stated limit (14,400 characters) in words of the fixed
vocabulary (mean 6.76 characters per word including the space), not in tokens:

- Prefill arm (unique prompts): 16, 256, 512, 1,024 and 2,048 words (the last is about 13,900 characters, under the cap; any
  prompt over 14,400 characters would be truncated at a word boundary, and is recorded). Served `usage.prompt_tokens` is still
  the fit's x variable, so the token sizes are whatever the engine reports.
- Repeated-prompt case: 1,024 words, compared with the 1,024-word unique cell.
- Decode arm, ordering, seeds, warm-ups, exclusions, PASS and kill rules unchanged. Requests: 3 used (2 debug, 1 probe) + 110
  cells + 2 attestation = 115, under 150.

Consequence stated in advance: the prefill arm covers at most a few thousand prompt tokens, so the seconds-per-prompt-token
rate measured here is for short prompts through this route, and says nothing about the long-context prefill the cost model's
window sizes involve.
