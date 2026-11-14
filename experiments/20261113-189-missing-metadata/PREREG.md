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

### A-1, 2026-11-14 (UTC): the stop rule fired in review; registration of the review-driven reproduction

Written before any new fixture code exists on this branch. Everything above `## Amendments` is unchanged.

**What was found, and when.** After the six registered arms had run and been published at `bdc059a4c7302b8787c18c5c038468e89c5415d9`, both round-1 reviewers reported inputs outside those six arms for which a truncated, reordered or substituted run 3 gets a full H3 `PASS` once run 3's metadata, stored tree and cached comparison are removed: [first review](https://github.com/wakesync/flashprove/pull/191#issuecomment-6866086584), [second review](https://github.com/wakesync/flashprove/pull/191#issuecomment-6867478542). Their explanation: without metadata the loader accepts a prefix of either canonical order, and H3 is reported on the union of run 2 and run 3, so run 2's eight reverse-order blocks complete a forward prefix of 70 or more blocks. That is the event named in issue #189's stop rule and in the kill criterion above. The figures in those two comments are the reviewers', not yet rerun by this lane at the time of writing.

**What does not change.** No registered arm, expectation, threshold or run file changes. The 30 receipts under `runs/registered/` and `runs/evidence-tests.json` stay as committed. The six-arm outcomes stand as measured. What changes is the reading of them: the hypothesis says an ordered prefix without metadata is accepted "only as partial H3 evidence", and the registered arms tested one cut position in one direction. If the cases below reproduce, the result of this follow-up is "stop rule fired (blocking finding)", not PASS, and the milestone stops there. The stop rule is not narrowed, reworded or declared resolved by this amendment.

**Review-driven cases, registered now.** Each case is built from the committed `experiments/20261112-149-leaf-v2/runs` in a private temporary directory by a new script, `stoprule_cases.py`, written for this amendment (it imports neither `reproduce.py` nor the evidence suite). Run 1 and run 2 are untouched unless the case says otherwise. "Forward k" means: run 3's lines put into forward registered order, first k lines kept. Unless stated, run 3's metadata, stored tree and cached comparison are removed.

1. Forward 77, 76, 71, 70 (reviewers: comparator `identical-partial`, H3 `PASS`, union 78).
2. Forward 69, 60, 39, 10, 1 (boundary controls; reviewers report `PASS-SUBSET` or `BELOW-COVERAGE` for 60, 39, 10, 1; 69 is this lane's own boundary case, expected `PASS-SUBSET` with union 77).
3. The whole of run 3 in forward order (reviewers: `identical-complete`, `PASS`).
4. Run 1's records as run 3's `blocks.jsonl` (reviewers: `identical-complete`, `PASS`).
5. Run 1's whole directory as run 3, keeping its own metadata and stored tree, cached comparison removed; and the same with the metadata removed (reviewers: `identical-complete`, `PASS`).
6. Run 1's first 70 lines as run 3 (reviewer: `PASS`).
7. Records taken alternately from run 1 and run 3 by block name, in forward registered order (reviewer: `identical-complete`, `PASS`).
8. Run 1's first 39 lines followed by forward run 3 lines 39 to 69 (reviewer: `PASS`).
9. Forward 77 and forward 70, each with metadata edited to agree (`done` = k, `reverse` false, `stopped` non-null), stored tree and cached comparison removed (reviewers: `PASS`).
10. Controls the reviewers report as not a full PASS: run 3's original-order last-line cut (`PASS-SUBSET`, the registered arm 3 input); the original-order last-line cut then reversed (refused); run 2's records as run 3 (`BELOW-COVERAGE`); run 1 and run 3 lines alternated by raw line index (refused); run 2 reversed into forward order with its own metadata kept (refused).

Five fresh private copies per case, fixed order, no randomness, no exclusions. Each replay calls the unchanged `wb_leafv2.py compare run1 run3` and the unchanged `summarise.py --runs` in separate subprocesses, 120 seconds each. Recorded per replay: return codes, sanitised output, comparator status and counts, H3 status and union counts. A reviewer case that does not reproduce is recorded and reported as such, with the output. Receipts go under a new directory, `runs/stoprule-20261114/`; nothing existing is overwritten. Source hashes are taken before and after.

**Independent coverage cross-check, and a second stop rule.** For every accepted replay the script recomputes, from the fixture's own files and without the reader, which registered blocks each run file contains and whether each common block's `e`, `int_sha256` and fetched-bytes `sha256` agree with run 1. If the reader reports a block as covered that no supplied run file contains, or reports a block identical whose hashes differ, the script stops: that would be a different and more serious finding than the one above (invented coverage or a false hash match), and it is reported on its own.

**Regression cases.** The leaf-v2 evidence suite gets insertion-only cases that pin the current behaviour of each input in items 1 to 9, including the full-`PASS` ones. They are labelled as the stop-rule finding, not as a contract the reader should keep. The suite is run once afterwards; its receipt gets a new file name. `research/weight-binding/wb_leafv2.py` and the original `summarise.py` are not changed.

**Debugging.** The new script is debugged only on forward 50, which is not in the list above, plus syntax checks. No listed case is run before the recorded run.

**Limits.** Light CPU only, cores 12-13, shared host. No model, weights, GPU, paid API, serving or attestation request. Hard stop for this amendment's work: 2026-11-14T01:45:00Z, including integration.
