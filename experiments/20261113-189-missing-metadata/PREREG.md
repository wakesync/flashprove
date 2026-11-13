# PREREG: 20261113-189-missing-metadata

Issue: #189. Lane: meta189. Date (UTC): 2026-11-13.
Base commit: 4991f69acbc9db0c9cd0bc80b79ad658078e3737.

## Hypothesis

The unchanged leaf-v2 readers accept an ordered line-boundary prefix without metadata only as partial H3 evidence, refuse the same truncation with original metadata or stored tree retained, and refuse noncanonical reordered records even without metadata.

## Metric

Categorical comparator and recomputed H3 summary outcomes, common/identical block counts, and unexpected full-coverage outcomes per fixture. Inputs are copies of the committed `experiments/20261112-149-leaf-v2/runs` at the base above. No weights are fetched or converted. The independent fixture builder will not import the evidence suite's fixture helpers.

Arms: (1) authentic baseline, (2) complete run3 with only its metadata removed, (3) run3 final complete line removed, with its metadata, stored tree and cached comparison removed, (4) the same cut with original metadata retained but tree/cache removed, (5) the same cut with original stored tree retained but metadata/cache removed, (6) two nonadjacent run3 lines exchanged with metadata/tree/cache removed. Run1 and the legitimate partial run2 stay unchanged in every arm. The comparator and summary are evaluated separately, including on refusals. Store exact sanitized refusal reasons and JSON output for accepted comparisons/summaries. Hash source inputs before/after to verify read-only handling.

## Acceptance threshold

All five repetitions of every arm must agree: baseline and complete-metadata-absent controls give `identical-complete` and H3 `PASS`; cut without metadata/tree/cache gives `identical-partial` and `PASS-SUBSET`, never full PASS; cut with metadata, cut with tree, and noncanonical reorder give explicit evidence refusals. The new evidence-suite regression must pin the missing-metadata boundary, and all existing evidence-suite checks must pass. No claim of exhaustive malformed-input coverage.

## Kill criterion

If any truncated or reordered fixture reports full H3 `PASS` or comparator `identical-complete`, stop immediately, retain the blocking receipt, and report the finding instead of continuing this milestone. Stop on unexpected source mutation. Light CPU only, pinned to cores 10-11, no GPU, model, weights, paid API, serving or attestation request. Each light invocation has a 120-second timeout; do not escalate to heavy work. Hard lane stop: 2026-11-13T22:25:00Z, including waiting and integration time.

## Runs

Five fresh scratch copies per arm, fixed arm order as listed above, no warmup, no randomness (seeds: none), no exclusions. Each arm is deterministic replay, not an independent conversion or cross-platform replication. Report raw outcomes and n, median, sample SD, min/max for numeric common-block counts and full-PASS indicator; repetitions do not estimate model or conversion variance. No performance claim. Run the extended leaf-v2 evidence suite once after the independent fixture experiment and retain its receipt. No debug runs on the registered fixtures before the recorded run; syntax checking is allowed. Any failed invocation is retained and disclosed, not silently replaced.

## Prior art

This is a contract/documentation follow-up to the leaf-v2 hash-level evidence reader and PR #151, not a new proof scheme. Relevant prior work is `research/weight-binding/wb_leafv2.py`, `research/weight-binding/test_wb_leafv2_evidence.py`, and `experiments/20261112-149-leaf-v2/summarise.py` on main. The motivation is the auditor's missing-metadata observation at https://github.com/wakesync/flashprove/pull/151#issuecomment-6863785743, not yet independently rerun by this lane. Existing tests cover declared partial runs, truncation with metadata, record-order corruption and stale comparisons. This follow-up independently constructs the metadata-absent fixture, pins its present contract, adds an append-only dated limits addendum to the original RESULTS, and recommends whether future readers should require metadata. Reader behavior will not change here; any such change requires its own dated registration and review.

## Amendments
