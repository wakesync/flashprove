# Same-oracle sparse affine research milestone

Extends `../shared_wires` without modifying V3/V4 or upstream. The verifier fixes 1..64 affine relations, each containing 1..8 terms `(row, column, coefficient)` and a target. Each enforces `sum(coefficient * committed_cell) = target` over the field. Rows address the same committed product oracle's MAIN part, not a second oracle or a disclosed-witness evaluator. Public coordinates and existing equality wires remain enforced.

The supported constructor checks canonical base-field coefficients/targets, row/column bounds, lengths and counts. Repeated terms sum, including cancellation; zero coefficients and redundant relations are allowed. Affine vectors, lengths, ordered terms and targets are Binder statements. The separate label `0x46504131` and `research-affine-product-v1` configuration prevent protocol confusion. Both initial GroupLoad and IOPP planning include coordinate + equality + affine counts. No new masks or detached evaluations are added. This is accounting, not a masking/security theorem.

## Reproduction

From repository root, Linux with g++ 13 or later and Python 3:

```sh
python3 research/operators/affine_rows/record.py
```

No network, GPU, full CPU-suite run, checkpoint or new dependencies. Recorder preserves compiler version, argv, exit codes, timings, source and binary hashes in `evidence.json`; core dumps are disabled. Synthetic deterministic coins, 16 columns, target 10 and query work 6 are test parameters, NOT a security level. Timing/proof-size differences versus V4 are not performance claims.

The honest fixture enforces `a[3] - 2*c[0] - 3*b[0] = 5` with `a[3]=26`, plus the existing public 2/3/120 chain. Two complete malicious proofs alter a[3] by 1 or 7 and update c[3] to keep every product valid. Every public coordinate and prior equality is explicitly checked unchanged. The hostile prover binds the TRUE affine statement but uses its truthful incorrect local target and completes IOPP. The unchanged verifier rejects both. This isolates affine enforcement from statement hashing and existing relations.

Additional tests check independent flattened Row coefficients across all 64 positions, duplicate cancellation, zero terms, no MASK/other-oracle coefficients, four statement mutations, bidirectional V4/V5 confusion, wrong label, sampled flips/cuts, trailing bytes, and an honest upper-count fixture (64 coordinates + 64 equalities + 64 affine rows, eight terms each). Eight invalid constructors abort as expected, not graceful network-parser rejection.

## Claim boundary and gaps

Research only, pending independent review. Trusted mutable in-memory runs/plans are not safe untrusted parsers; callers must not mutate dimensions/counts after sizing. The reusable coordinate planner is inherited and remains a maintenance dependency. The upper-count fixture repeats constraints; it is not 64 independent adversarial affine relations. No exhaustive coefficient/graph/length coverage, independent cryptographic verifier, formal theorem, hiding or security bound. No integer ranges or overflow/rounding semantics follow from a field relation. No full router, Booleanity, ordering/permutation, selection, normalization, model support or publisher equivalence.

Dependencies: reviewed public-coordinate/shared-wire PR #14, coverage issue #6 and port feasibility issue #11. Next proof binding should be separately scoped and independently reviewed; this milestone closes neither issue.
