# FAIL (target in question): teacher-forced stock/abliterated comparison on one fixture

Issue #177 (part of #36, informs #32 DESIGN section 10 and #8). PREREG: [PREREG.md](PREREG.md) (first commit c920dd0, alone). Results: [RESULTS.md](RESULTS.md).

## What this is, in plain language

The program wants to prove one real abliterated reply end to end (DESIGN section 10). That proof only says something about *which* model ran if the stock model would not have given the same reply. Here an attested H200 serving deployment (vLLM, BF16) of the abliterated checkpoint answered 6 mild refusal-type prompts (break-ins, a paywall, a ticket) and 2 harmless controls, greedily. Each reply is fed back, token by token, through float64 CPU forwards of both checkpoints (stock and abliterated), and at every reply position we ask which checkpoint's top choice is the served token. The registered rule names r01, but H0 failed: **FAIL (target in question)**, not a validated carry-forward target. Stock's own reply was not generated. This is a teacher-forced comparison on the abliterated deployment's own greedy replies, one fixture, not a detector or proof. The r02 observation in RESULTS is descriptive only, not a replacement target.

**Nothing here is proved.** No proof is built or verified. All arithmetic on the CPU side is float64.

- **Served side:** model identity (repository, revision, dtype, engine image) as reported by the deployment configuration, not independently hashed. The route returns text, `finish_reason` and `usage` counts, no token ids and no logprobs. Ids are rebuilt from text with the pinned tokenizer and template (PR #133's `rebuild_ids.py`, unchanged) and accepted only if they match the served counts. Equal counts are necessary, not sufficient.
- **Publication rule (issue #177):** the reply text of the refusal-type prompts and their reply token ids are not in this repository. Committed: prompt text and ids, counts, finish_reason, sha256 of reply content and of reply ids (`sha256(json.dumps(ids))`), per-position flags, KL both ways, both margins, and the refusal-rule outcome. Control replies are committed in full. The text lives in lane scratch outside the repo, so a later lane can rebuild the same ids and check them against the sha256 here.
- **Not covered:** sampled replies; any integer arm or proof; any claim that output tests detect abliteration in general (one fixture, not a detector); judging reply content (the refusal rule is a registered string match only); serving the stock checkpoint.

## Files

| file | what it does |
|---|---|
| `PREREG.md` | registration and amendments |
| `prompts-refusal.json` | the 8 frozen user messages (r01..r06 refusal-type, c01/c02 = PR #133's q01/q02) |
| `served_route177.py` | PR #133's `served_route.py` with max_tokens 48, one repetition, a lane-wide cap of 20 requests persisted across batches |
| `rebuild177.py` | imports PR #133's `rebuild_ids.py` unchanged; applies the inclusion rule and the refusal string rule; writes the private full rebuild (scratch) and `runs/served-ids-public.json` |
| `forward177.py` | the CPU forward: PR #162's `u1_p03.forward` (stock layers 0..16 shared, 17..63 fused with the 70 changed tensors) and PR #139's `final_hidden` / `two_way`, unchanged; new: the multi-prompt input state. Output is private (top-1 ids reveal the reply) |
| `run177.sh` | the registered run under its start-by, hard stop and 5 s RSS / disk watchdog |
| `summarise177.py` | flags, counts, window counts, bars, target; public `runs/summary.json` / `summary.md` without reply ids for refusal-type prompts |
| `test_summarise177.py` | 23 synthetic regression tests, including missing/duplicate records, explicit exclusions and missing arms; original receipt in `runs/summariser-synthetic-test.json` is preserved |
| `describe177.py` | descriptive, after results (PREREG A-1): margins at abliterated misses, clean-prefix lengths, first separating position -> `runs/describe.json` |
| `check_manifests177.py` | fetched tensor sha256 vs PR #87's per-tensor manifests, embedding rows vs PR #124 -> `runs/manifest-check.json` |
| `redact_manifest177.py` | replaces the stock manifest's token-id-keyed embedding-row map by count + sha256 (publication rule, PREREG A-1) |
| `env177.py`, `add_results_row177.py` | `ENV.json`, the `research/results.yaml` row |

Changes relative to reused code: none inside the reused files. `forward177.py` builds a state of 8 prompts where `u1_p03.py` built p03 alone, and writes per-position output instead of `d-p03.json`. The route client differs from PR #133's in max_tokens (48), repetitions (1) and the request cap (20, counted across batches).

## Reproduce

From this directory, with a scratch directory `$X` outside the repo, Python 3.12, numpy 2.4.3, network access to huggingface.co:

```
python3 rebuild177.py <dir with pinned tokenizer.json + chat_template.jinja> $X/replies.jsonl prompts-refusal.json $X/served-ids-private.json runs/served-ids-public.json   # jinja2 + tokenizers 0.23.3
fp-heavy.sh taskset -c 10-15 bash run177.sh $X/fw $X/served-ids-private.json $X/forward-private.json
python3 summarise177.py $X/forward-private.json $X/served-ids-private.json runs $X/detail-private.json --pr133 ../20261112-131-served-reply-agreement/runs/forward.json ../20261112-131-served-reply-agreement/runs/served-ids.json
python3 test_summarise177.py  # synthetic tests only; does not overwrite the original receipt
python3 check_manifests177.py              # before redact_manifest177.py
python3 describe177.py runs/summary.json runs/describe.json
```

`$X/replies.jsonl` (the served replies) cannot be regenerated without access to a serving deployment; `served_route177.py collect <state.json> prompts-refusal.json <out>` with `BRIDGE_URL`, `BRIDGE_KEY_FILE`, `BRIDGE_MODEL` set is how they were collected. A later lane that holds the scratch replies checks them against the `content_sha256` and `reply_ids_sha256` in `runs/served-ids-public.json`.
