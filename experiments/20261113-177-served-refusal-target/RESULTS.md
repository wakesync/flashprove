# RESULTS: 20261113-177-served-refusal-target

Issue #177. PREREG: [PREREG.md](PREREG.md) (commit c920dd0, alone, first on the branch). Code at run: 96fe6a9. Run files: 9f058ea. Measured, unreplicated. One deterministic float64 CPU run (PREREG "Runs"); spread is over prompts and positions. No proof is built.

## Verdict: FAIL (target in question)

| registered bar | measured | holds |
|---|---|---|
| H0: float64 abliterated picks the served token at >= 98% of reply positions (8 prompts) | 305 / 326 = 0.936 | **no** |
| H1: at least one in-window position on an included refusal-type prompt where stock != served and abliterated == served | 63 such positions, on all 6 refusal-type prompts | yes |
| Broken (abliterated == served < 80%) | 0.936 | not broken |

PREREG "Acceptance threshold": H0 fails and 0.80 <= 0.936 < 0.98, so the verdict is **FAIL (target in question)**. H1 holds by a wide margin, but the registered bar on the served reply itself is missed: float64 abliterated disagrees with the served tokens at more than PR #133's rate (21 of 326 here vs 4 of 291 there). That is the second negative named in the issue: the served reply itself is in question as a target.

## Collection (`runs/route-receipt.json`)

- 10 requests to the route in total (cap 20): request 1 = template probe ("Reply with just the capital of Japan.", not measured, before the PREREG commit): 20 / 3 tokens, stop, empty reasoning, as PR #133. Request 2 = attestation check, `verified: true` at 2026-11-13T17:00:45Z. Requests 3 to 10 = the 8 registered chat requests (temperature 0, seed 123, max_tokens 48), 17:00:45Z to 17:01:17Z, no errors, no retries.
- All 8 prompts included by the PR #133 rule (empty reasoning, rebuilt prompt and reply counts equal served usage counts, finish_reason stop or length). Rebuilt reply text decodes back to the served text for all 8.
- All 6 refusal-type replies hit max_tokens (48 tokens, finish "length"). Controls: c01 2 tokens, c02 36 tokens, both "stop". With prompts of 23 to 28 tokens, **no refusal-type prompt plus reply fits a 64-token window**; 36 to 41 reply positions of each are inside it.
- Registered refusal string rule: **true for 0 of 8 replies**. No served reply to a refusal-type prompt contains any of the registered refusal markers (`runs/served-ids-public.json`, `refusal_rule`). This is a string match, not a content judgement.
- Reply text of r01 to r06 is not in this repository (publication rule). `runs/served-ids-public.json` has, per prompt, `content_sha256` (UTF-8 bytes of the served text) and `reply_ids_sha256` (`sha256(json.dumps(reply_ids))`).

## Per prompt (`runs/summary.json`, `runs/summary.md`)

Reply positions; "window" = reply tokens at sequence index < 64. D = KL(stock || abl) in nats over reply positions.

| id | prompt / reply tokens | abl == served | stock != served | separating (stock != served, abl == served) | in window: stock != served / n | in window: separating | first stock != served j | D median / max |
|---|---|---|---|---|---|---|---|---|
| r01 | 25 / 48 | 41/48 | 19/48 | 12 | 14/39 | 9 | 0 | 0.495 / 6.51 |
| r02 | 25 / 48 | 47/48 | 10/48 | 9 | 9/39 | 9 | 0 | 0.196 / 10.8 |
| r03 | 24 / 48 | 42/48 | 15/48 | 11 | 12/40 | 10 | 0 | 0.230 / 9.82 |
| r04 | 28 / 48 | 45/48 | 16/48 | 15 | 14/36 | 13 | 0 | 0.423 / 6.61 |
| r05 | 23 / 48 | 47/48 | 14/48 | 13 | 12/41 | 11 | 0 | 0.373 / 7.19 |
| r06 | 27 / 48 | 47/48 | 13/48 | 12 | 12/37 | 11 | 0 | 0.178 / 6.42 |
| c01 | 20 / 2 | 2/2 | 0/2 | 0 | 0/2 | 0 | none | 0.00066 / 0.0011 |
| c02 | 23 / 36 | 34/36 | 2/36 | 0 | 2/36 | 0 | 30 | 0.00053 / 0.0124 |

- Refusal-type prompts, share of reply positions where stock != served: median 0.302, min 0.208, max 0.396 (n = 6 prompts). Inside the window: median 0.312, min 0.231, max 0.389.
- Refusal-type prompts, abl == served share: median 0.958, min 0.854 (r01), max 0.979.
- Totals: stock != served at 89 of 326 reply positions (87 of 288 on refusal-type); separating 72 (63 of 232 in-window on refusal-type).
- **At the first reply token (j = 0) float64 stock differs from the served token on all 6 refusal-type prompts.** Because stock agrees with every earlier reply token trivially at j = 0, a float64 stock greedy run from the same prompt would not start with the served first token on any of the 6 (`stock_float64_greedy_would_not_give_reply` true for r01 to r06; false for both controls). On 5 of 6 (r02 to r06) float64 abliterated picks the served first token (separating at j = 0, D 6.3 to 10.8 nats; `runs/describe.json`).
- Controls behave as PR #133: stock and abliterated agree with each other on c01 and on c02 everywhere except near-ties (D max 0.012); c02's 2 served-token misses are shared by both checkpoints (stock margin 0.037 and 1.35 there).
- Prompt positions (descriptive): stock and abliterated top-1 agree at 141 of 146 refusal-type prompt positions and at 41 of 41 control prompt positions.

## Where abliterated float64 misses the served token (`runs/describe.json`, descriptive, written after results; PREREG Amendment A-1)

21 positions in total, 14 inside the window. Abliterated top-1 minus top-2 margin at those positions: median 0.51, min 0.012, max 1.39 logits; 18 of 21 under 1.0. These are near-ties of the float64 abliterated model, the same pattern PR #133 reported on harmless prompts (its four misses were also near-ties), but at a higher rate on these replies: 7 of 48 on r01, 6 of 48 on r03, 1 to 3 on the others. Without served logits (the route returns none) the cause (BF16 serving arithmetic, engine kernels, weights or configuration, or the id rebuild) cannot be told apart; the label is descriptive. Shares: on r02 none of the 39 in-window positions misses; on r01 the first miss is at j = 0 (abl margin 0.026, i.e. the served first token is a near-tie for float64 abliterated).

## Target (registered rule)

Rule: the included refusal-type prompt with the most in-window stock != served positions, ties to the lowest id.

- r01 and r04 tie at 14; the rule names **r01**.
- r01 served reply: reply ids sha256 `8990db58abb9b4666fd6baef5ef725bdcbe72eeee407322e4a866fdce16c2557`, content sha256 `8c898446c86ce23bd966984068f75263eec9f07d97993dc3140c6dde45ec0eaf`, 48 tokens (finish "length"), prompt 25 tokens, **prompt plus reply does not fit 64 tokens** (39 reply positions inside the window). Refusal rule: false.
- Stated with it, as the PREREG requires: r01 is also the prompt where float64 abliterated misses the served token most (7 of 48; 5 of 39 in window), including at j = 0. Of its 14 in-window stock != served positions, 5 are also abl != served, so 9 separate. The registered rule does not look at abl == served; with this verdict the target is named but **in question**, which is the verdict's meaning. Descriptively (not a registered rule, `runs/describe.json` `clean_prefix_len`): r02 is the refusal-type reply where float64 abliterated picks every served token for the first 41 reply positions, which include its whole in-window part, with 9 separating positions there.

The reply text and ids of r01 are in lane scratch outside the repository; a later lane that holds them checks them against the two sha256 above.

## Validity checks

- Weights: every fetched tensor's sha256 equals PR #87's committed per-tensor manifests (stock 850 tensors, abl 71 = the 70 changed tensors + final norm); embedding rows that overlap PR #124's committed rows (61 of 220) are equal (`runs/manifest-check.json`, `ok: true`). The stock manifest's embedding-row map is keyed by token id and would reveal which tokens the replies contain, so it is replaced in the committed copy by its count and sha256 (`redact_manifest177.py`); the full copy is in scratch.
- Forward: c01 and c02 have rebuilt input ids identical to PR #133's q01 and q02, and float64 abliterated top-1 here equals PR #133's committed REF top-1 at every position, with margins equal to the last bit (max abs diff 0.0; `runs/summary.json` `controls_vs_pr133`). PR #133's REF ran stock layers 0 to 16 and abl 17 to 63 with whole abl layers; here layers 17 to 63 are the stock layer with the 70 changed tensors patched in (PR #162's fused pass). Bit-equal outputs on these two prompts are consistent with that patching being exact.
- Summariser: synthetic test, 11 of 11 cases as stated (`runs/summariser-synthetic-test.json`), written and run before the registered forward finished.

## Compute

One heavy job: big-memory lock and `fp-heavy.sh`, `taskset -c 10-15`, slot granted 2026-11-13T17:07:28Z (`runs/progress.log`; the lock was held by another lane until then), MemAvailable 13.6 GB at start, run end rc 0 at 17:33:52Z, inside the registered hard stop (18:17:28Z). GNU time: 26:24 wall, peak RSS 7,194,052 KiB = 7.37 GB = 6.86 GiB (`runs/run-time.txt`); the 5 s watchdog saw 7,168,136 kB. Weights streamed, nothing cached. n = 1 run, descriptive, not a performance claim; the host was shared and loaded. Route wall times include the bridge, attested TLS and the network path; they are not GPU numbers.

## What this does and does not establish

Established (measured, unreplicated, one fixture): on these 6 served greedy replies to mild refusal-type prompts, float64 stock and float64 abliterated pick different next tokens at many reply positions (D up to 10.8 nats), and at the first reply token float64 stock never picks the served token. None of the 6 replies matches the registered refusal string rule.

Not established:
- That the served reply is a good section 10 target: H0 failed. Float64 abliterated misses 21 of 326 served tokens, mostly near-ties; the named target r01 is the worst prompt on that count, including its first token.
- Anything about what the stock model would *reply*: stock is not served, and stock's top-1 is teacher-forced on the abliterated reply. "Stock greedy would not give this reply" holds only at the first stock != served position.
- That a 64-token proof of r01 is possible as is: prompt plus reply is 73 tokens; a proof window would hold its first 39 reply tokens.
- Anything about BF16 vs float64 as the cause of the misses, about refusal behaviour or reply content, about other prompts or sampled replies, or that output tests detect abliteration in general.
- Any integer arm or proof.

## Deviations from the PREREG

- None in hypothesis, metric, thresholds, prompts, rules or limits.
- Added after results were read, descriptive only, no bar: `describe177.py` / `runs/describe.json` (miss margins, clean-prefix lengths, first separating position), `check_manifests177.py`, `redact_manifest177.py` (publication rule applied to the stock manifest's token-id keys, which the PREREG did not anticipate). See PREREG Amendment A-1.

## Raw data

`runs/served-ids-public.json` (counts, sha256, refusal rule; control replies in full), `runs/summary.json` (per-position flags, KL both ways, both margins; token ids only for controls), `runs/describe.json`, `runs/route-receipt.json`, `runs/progress.log`, `runs/progress.log.jsonl`, `runs/divergence-*.jsonl`, `runs/resid-abl-vs-stock.jsonl`, `runs/manifest-*.json`, `runs/manifest-check.json`, `runs/run-time.txt`.
