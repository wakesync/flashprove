# PREREG: 20261113-181-independent-e2e
Issue: #181, part of #8. Lane: recomp181. Date (UTC): 2026-11-13.
Source main: `59bff9a4608e0cc720d58d7c30823a8838fa43e4`.

## Hypothesis
An independently implemented strict reader of PR #124's committed records recovers the four registered XS18/XS20 x stock/abl decisions, denominators and flip identities without using the original aggregation implementation.

## Metric
Independent aggregation only, not a new forward or whole-experiment replication.
Source directory: `experiments/20261111-8-qwen-e2e-agreement`.
Read the prompt manifest and per-position records, source PREREG, divergence and head-error records directly. Never import, execute or copy `summarise.py`. Never use `summary.json` as aggregation input. Write independent output before opening comparison targets. Hash source files against the manifest below, including the documented absence of error logs. No historical data edits.

Fixed denominator: 10 distinct prompts, 1,461 positions per registered cell. Exact prompt IDs and lengths are frozen below. BF16H has its original five-prompt, 608-position subset and is context only, never a fifth registered cell. Every per-position array must have exactly T entries and T must match the frozen prompt length. Token IDs must be genuine integers in [0,248320), flags genuine booleans. Duplicate JSON object keys, duplicate prompt IDs, missing/extra keys or records, nonfinite values and shape inconsistencies are invalid evidence, not exclusions.

Fields to recover for each cell: position and prompt counts; top-1 agreement from REF/path IDs, independently checked against every stored flag; all flips with checkpoint, arm, prompt, zero-based position, REF/path ID and REF margin; pooled KL median, maximum, minimum, sample SD (n-1) and nearest-rank p99 (sorted index ceil(.99*n)-1); per-prompt equivalents; count/list of negative KL with locations and values; guard, sanity, residual and logit determinism predicates; the three bars separately and combined decision. Retain negative KL without clamping. Values in [-1e-12,0) are allowed as flagged roundoff; below -1e-12 invalidates evidence. This tolerance does not relax any acceptance bar.

Layer coverage: stock 0..63; abl records 17..63 plus shared stock 0..16, exactly once. Layers congruent to 3 modulo 4 are full_attention, others linear_attention. Require complete per-prompt divergence coverage of each path, six determinism flags per layer (REF#2 and XS18#2 on p01, p04, p09), and complete 48-head local-error arrays for XS18, XS20 and XS18#2 at every linear-attention layer on their respective prompt subsets. All error/divergence magnitudes must be finite and nonnegative. Error logs are absent at source; an unexpected error log makes input invalid, never PASS. Completeness and absence of recorded errors are the guard predicate, not proof that the producer actually checked every overflow.

Sanity: recompute p01 REF last-token ID == 25358 and check both saved sanity fields. Determinism: all saved residual bit-equality flags true, REF#2 residual differences zero, XS18#2 residual differences equal XS18, REF#2 top-1 equals REF and maxdiff_over_std exactly zero, XS18#2 all four per-position arrays exactly equal XS18. REF#2 KL retains permitted negative roundoff rather than requiring exact zero. These validate recorded determinism, not a rerun. Any false predicate prevents PASS.

## Acceptance threshold
Exact equality for denominators, token IDs, flags, flip identities and categorical decisions. Floating comparisons to full-precision original aggregates: abs(a-b) <= 1e-12 + 1e-10*max(abs(a),abs(b)). Rounded ledger values are checked within half a unit of their last stated digit (with a binary rounding allowance of 1e-12 relative). Flip margins use the full-precision tolerance.

Three original inclusive bars: agreement >=99% tested by integer arithmetic (100*agree >=99*n), KL median <=1e-4, KL maximum <=0.1. No epsilon at threshold edges. Even-length median averages the middle two. All three bars and guard/sanity/determinism must hold for PASS. Any denominator, flip or decision mismatch is a negative replication result. Other aggregate discrepancies are reported, not repaired or hidden. Unavailable ingredients yield NOT RECOMPUTABLE for affected fields and no PASS receipt. Invalid inputs exit nonzero with no newly created PASS output. Comparison exits nonzero on any mismatch.

## Kill criterion
Hard stop 2026-11-13T21:40:00Z. CPU only on two assigned cores; no weights, model forward, GPU, heavy slot, spend or service requests. Each execution must take less than 2 minutes CPU and 1 GB RSS; stop and report partial if exceeded. Stop writes if free disk falls below 3 GB. Unavailable data, failed integrity or denominator checks are negative results, not grounds to change the registration or historical files.

## Runs
Five deterministic independent-reader executions on the same committed inputs, retaining separate receipts and checking byte-identical outputs. No inference, sampling, seeds or performance claim. These are repeatability checks, not five independent measurements. Report within-position/per-prompt spread and deterministic agreement across executions. Before the registered executions, debug only on newly constructed synthetic records with synthetic token IDs and short arrays, never a subset copied from the measured suite. Adversarial tests cover missing/extra/duplicate prompt and layer records, truncated arrays, inconsistent T, token/flag disagreement, duplicate JSON keys, NaN/Inf and overflowed numbers, missing/false determinism fields, negative KL tolerance, altered input hashes, guard errors, and values exactly on and immediately outside every threshold.

## Prior art
This is an aggregation audit of merged PR #124, its PREREG and committed JSON/JSONL records. Its antecedents are merged PRs #68, #74 and #88 as named in that PREREG. It supplies no new quantisation, zkML relation or TEE evidence. The new contribution is a standalone standard-library reader with strict admission checks, explicit numeric edge rules and hostile synthetic fixtures, not the original summarizer or measurement machinery.

Independence disclosure: this lane did not produce PR #124. The Astra model family previously reviewed PR #124, visibly recorded in the local review-state receipt. The first six lines of that receipt were inspected to establish involvement and exposed a prose statement that earlier aggregation matched. This is not blind or cross-model-family replication. No previous reviewer code or numeric output is used. Before registration, source PREREG, JSON schemas, and the producer's error-record/determinism serialization sections were inspected. Original summary/ledger values have not been opened as comparison targets. Their bytes are hashed without interpreting them below.

## Frozen prompt denominator
- `p01-ordinary-short`: 13 positions; token-ID SHA-256 `2cca76740dee621ab47d3ab708871b7f462f2e139e792434ca917877d1e41e8d`.
- `p07-chat-ordinary`: 23 positions; token-ID SHA-256 `6c815fa81b9a953e2f526a9afbc833d0963ffddd9c2aa4b3e096ebd113d379d4`.
- `p08-chat-refusal`: 39 positions; token-ID SHA-256 `bceae405712d64acf228b1b7fd56f06f88d97833575745dd9f0e6c4e8cc7a612`.
- `p09-multilingual`: 21 positions; token-ID SHA-256 `a5a10f4d2371fc47f12fedc7030ac4097072645b7e35a652bda47a8fb511c4d4`.
- `p02-ordinary-paragraph`: 107 positions; token-ID SHA-256 `2337e63fe9ac554a284e81e9632fdfc0840eac8b03029389c4b31eb288828095`.
- `p04-repeat-punct`: 64 positions; token-ID SHA-256 `fcabb1ef8898583e560edd84507d1fb13bec2497a1ea580abfda24bb0177b787`.
- `p05-code`: 144 positions; token-ID SHA-256 `6ddfad3f37dbf6a50303596f06a3c99fb96bffd3b84fbe138be65e1b152b492d`.
- `p03-repeat-word`: 512 positions; token-ID SHA-256 `d35abf6c86c63b1f613e04eea1fab9d8b2ec750e89c949738545ff2e1ea5d5dc`.
- `p06a-digits-256`: 256 positions; token-ID SHA-256 `a32cbab1be6fdf708def7840337a94ef5b0cfb4b78f0cd5155bdfd9786f51b92`.
- `p11-chat-long`: 282 positions; token-ID SHA-256 `06b69c88e68d19735155435454e066422da4db842b361298dee2b68b220a23d9`.

## Input SHA-256 manifest
Paths relative to the source directory. `null` means required absent.
```json
{
  "PREREG.md": "8c5c63023fc950ae987aba03269b50bc91e4e468c0a18cc3e185de98b51b08d7",
  "prompts-e2e.json": "47aa61b46e142382ffa58b88f918df6ec63f1158629df5938ec00961a5242cfc",
  "e2e.py": "df03592b3ab27508914eead2903b983fef23319a7a2102fdfcdd3cbe65630def",
  "runs/e2e-stock.json": "1e066da307b848e007ffdf39823c9b2a245f8bcc27a7aa38c05bc54d7c5d3fa8",
  "runs/e2e-abl.json": "614f49f56b5fb905b391de29b2357b3e9304850881010709e78b8e4f62decc88",
  "runs/divergence-stock.jsonl": "e8426b0bf9ce30866aa7a9e4a5ede4554cd4c6dfc60f783e41b322b2983ff427",
  "runs/divergence-abl.jsonl": "e5d39dfd607caf02ee17ed2ec4c4918b41e86a2a8b8380f70e5aeb976a95dc81",
  "runs/heads-stock.jsonl": "0f41fa1512a2822e6f15cde34bda56cf0898604a257083bb258db08cc510876a",
  "runs/heads-abl.jsonl": "69c68c06de605fdcd648994c242aaa3359bae8c80d0dbd69ae6f118ce058286e",
  "runs/errors-stock.jsonl": null,
  "runs/errors-abl.jsonl": null
}
```

## Comparison-target SHA-256 manifest
Not aggregation inputs, read only after independent output exists. Paths relative to repository.
```json
{
  "experiments/20261111-8-qwen-e2e-agreement/runs/summary.json": "ece7a07561fb974ed559020147b619db25dfb65860369d39aaa68baf52d0cf89",
  "experiments/20261111-8-qwen-e2e-agreement/RESULTS.md": "5e832366018ee8f9692228fa79260aecdce3cb24ea6ed0100260d41ad2609519",
  "research/results.yaml": "30dc21088fc2b8a5f69a5a94826ea6a4c319b2c9caa134b7d23c1d4fe597f7bd"
}
```

## Amendments
(empty at registration)
