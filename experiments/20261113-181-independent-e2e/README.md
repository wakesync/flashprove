# Independent committed-data XS18/XS20 audit

This code recomputes PR #124's four registered numerical decisions from committed per-position records. It proves no cryptographic statement. The reader checks exact input hashes, strict JSON/JSONL schemas, frozen prompt/path denominators, shared-prefix layer coverage, token-ID agreement, supplied KL statistics and recorded sanity/determinism predicates. It does not execute any model code or read the original summary. A separate comparison command opens the original targets only after the independent receipt exists.

See `PREREG.md` (first commit alone, two reader amendments and one dated post-comparison review amendment) and `RESULTS.md`. Successful runs use `ENV-r3.json`; earlier environment/log files retain failed-closed attempts. This is aggregation-only corroboration of the same measurements. Prior review by this model family is disclosed in RESULTS. No whole-experiment replication or headline is supported.

## Reproduce from repository root
Python 3.10+ and the standard library only. Use CPU affinity appropriate to your environment; the recorded lane used cores 14-15. No downloads or network are needed once git objects for the pinned source commit are present.

```sh
python3 experiments/20261113-181-independent-e2e/recomp181_tests.py
python3 experiments/20261113-181-independent-e2e/recomp181_compare_tests.py
python3 experiments/20261113-181-independent-e2e/recomp181_admission_tests.py
python3 experiments/20261113-181-independent-e2e/recomp181_reader.py --source experiments/20261111-8-qwen-e2e-agreement --output independent-local.json
python3 experiments/20261113-181-independent-e2e/recomp181_compare.py --repo . --independent independent-local.json --output comparison-local.json
```

Repeat the reader command with four fresh output names to check five deterministic receipts. The reader refuses existing output paths. Outputs are stable JSON, SHA-256 recorded in `runs/repeatability-r3.json`. The comparison reads target blobs at the source main SHA from PREREG, so the new ledger row cannot change the baseline. `runs/comparison.json` contains 494 comparisons with zero mismatches; the original `summary.json` is a comparison target only. Never invoke the producer's summarizer or forward to reproduce this audit.

The comparator CLI now admits the receipt before opening any targets: exact schemas, frozen input digests, complete cell/flip identities, pooled/per-prompt denominators and internally consistent statistics, predicates and status. `recomp181_admission.py` does not rerun the reader or authenticate the claimed digests. Its CLI tests mutate disposable copies of the saved receipt; they are post-review regression tests, not new measurements. `compare()` is the low-level target-comparison function used with synthetic aggregates in unit tests; callers needing frozen-receipt admission must use the CLI.

`runs/comparison-post-review-validation.json` is the fresh post-review validation, not a replacement for the original registered comparison. It keeps all 494 original comparisons unchanged numerically and adds kind labels: 479 independent-versus-target checks, the 14 reviewer-listed fixed expectations, and one additional `summary.bars` threshold-contract check. These are not 494 independent confirmations. See RESULTS for the precise count correction and seven-case before/after record.

`recomp181_reader.aggregate()` accepts a synthetic contract for tests. The CLI always supplies the frozen ten-prompt denominator and exact source manifest; it exposes no flag to relax those checks. Pure tests exercise parser/semantic checks independently of hashes so corruption is not rejected only because a digest changed.

## Failure interpretation
Invalid evidence exits 2 and creates no receipt. Structurally valid evidence missing a bar/sanity/determinism prerequisite exits 1, produces a NEGATIVE receipt and marks affected cells FAIL. A comparison discrepancy is NEGATIVE with a mismatch report and nonzero exit. Missing required target ingredients also exit nonzero, not a successful replication. Do not patch historical data to obtain a match.

The reader validates an unkeyed hash manifest committed with its registration. It is an evidence-consistency check, not an authenticity signature or a sound proof about a forward computation. Full logits and model weights are neither required nor reconstructed.
