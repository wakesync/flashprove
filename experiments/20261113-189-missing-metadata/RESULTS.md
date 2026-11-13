# RESULTS: missing-metadata boundary (issue #189)

**PASS against this follow-up's registered contract**, measured, unreplicated. This is a deterministic reader regression, not a new conversion experiment or proof result. The original leaf-v2 reader and summariser are unchanged. The after-merge [auditor's observation](https://github.com/wakesync/flashprove/pull/151#issuecomment-6863785743) motivated the fixture; the numbers below come from this lane's independently written scratch-copy runner.

## Outcomes

`runs/registered/summary.json` records all 30 expected outcomes across six arms and five fresh temporary copies per arm. Each per-repetition receipt `runs/registered/rep{1..5}-<arm>.json` retains input hashes, return codes, sanitized stdout/stderr, and JSON outputs from the comparator and summary. Unchanged run1 and the legitimate partial run2 are present in every arm.

| Arm | Comparator | Recomputed H3 | Common blocks: median, sample SD, min/max (n=5) |
|---|---|---|---|
| `baseline` | identical-complete | PASS | 78, 0, 78/78 |
| `complete-no-meta` | identical-complete | PASS | 78, 0, 78/78 |
| `cut-no-meta-tree-cache` | identical-partial | PASS-SUBSET | 77, 0, 77/77 |
| `cut-meta-kept` | refused | refused | not reported on refusal |
| `cut-tree-kept` | refused | refused | not reported on refusal |
| `reordered-no-meta-tree-cache` | refused | refused | not reported on refusal |

The full H3 PASS indicator is 1 for each baseline/complete-no-meta replay (median 1, SD 0, min/max 1/1); it is 0 in every cut/reordered replay (median 0, SD 0, min/max 0/0), n=5 per arm. Both complete arms have 78 identical blocks; the accepted prefix has 77. These repetitions show repeatability of this deterministic file replay, not conversion variance or independent implementations. There is no timing comparison or speed claim.

All cuts remove the last complete line of run3, preserving newline termination. The metadata-kept arm removes tree/cache so metadata is the reason for refusal (`done=78` versus 77 records). The tree-kept arm removes metadata/cache so the original stored tree is the reason (`incomplete run`). The reorder swaps lines at zero-based indices 3 and 40 and removes metadata/tree/cache; it is refused on `record order`. The complete-no-meta arm removes **only** run3 metadata. Receipt hashes in `runs/registered/source-before.json` and `source-after.json` agree: no committed source-run file was changed.

The issue's blocking stop rule did not fire. None of the tested truncated or noncanonically reordered inputs gave comparator `identical-complete` or H3 `PASS`. This is a bounded fixture result, not a universal guarantee about every input or every possible union of runs.

## Regression suite

`research/weight-binding/test_wb_leafv2_evidence.py` adds five cases covering the missing-metadata cut, metadata-kept cut without tree/cache, tree-kept cut without metadata/cache, complete missing-metadata control, and noncanonical reorder without metadata/tree/cache. The suite ran once after the independent experiment: **177/177 expectations across 64 cases**, receipt `runs/evidence-tests.json`. This includes the prior cases and original committed-summary equality checks. The original receipt `experiments/20261112-149-leaf-v2/runs-fix151/evidence-tests.json` is unchanged.

## Boundary and recommendation

Missing metadata disables the checks against recorded completion and direction, not the structural checks on the records. The reader still requires a prefix of canonical forward or reverse block order and validates identities, shapes and derived flags. Without metadata, an accepted ordered prefix does not show it came from a registered stopped run. A complete metadata-free record set can still give `PASS`; this is coverage/agreement, not provenance.

**Recommend requiring `run-meta.json` by default when ingesting registered-run evidence.** Silent acceptance weakens an otherwise useful consistency contract without changing the success-like label. An explicitly requested exploratory metadata-free mode could preserve standalone hash comparison, but should mark completion/direction as unchecked and not imply registered-run provenance. Requiring metadata alone does not authenticate it, verify historical execution, or prevent a consistent rewrite of every input. It is not a cryptographic fix.

This is a written recommendation only. No behavior change is made in `wb_leafv2.py` or the original summariser. A future behavior change requires its own dated PREREG amendment and review. The original experiment's RESULTS receives only a dated append-only limits addendum, leaving everything above it intact.

## Limits and deviations

- No deviation from this follow-up's registration. The first branch commit contains PREREG alone; fixture code and execution follow it. No debug fixture run or discarded registered attempt occurred.
- No weights, conversion, model inference, GPU, provider request, attestation, proof generation, or independent implementation. No H1/H2/H4 result is strengthened by replaying their existing records.
- Reuses the unchanged production readers; the fixture construction is independent of the existing evidence suite, not a second implementation of the reader.
- Six fixed arms do not exhaust malformed inputs. In particular this is not a claim that every possible record permutation must fail; both canonical forward and reverse orders are allowed when metadata is absent.
- Missing leaf-v2 CI jobs and the original runs' missing run-file CPU pin remain separate follow-ups. This run's actual affinity and toolchain are in `ENV.json`.
- Shared CPU host, cores 10-11. The repetitions are measured, unreplicated and not a public performance headline.
