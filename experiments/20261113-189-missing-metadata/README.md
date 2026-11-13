# Reproduce the leaf-v2 missing-metadata boundary

This follow-up tests how the existing reader treats copied evidence when metadata is missing. It proves no cryptographic statement and changes no reader behavior. The comparator rebuilds canonical leaves and complete trees from validated record files; the summariser recomputes H3 rather than trusting cached comparisons. Neither checks integer hashes against model weights. Without metadata, recorded completion/direction cannot be checked.

Requirements: Python and numpy versions recorded in `ENV.json`, Linux for `taskset`, repository inputs at base commit `4991f69acbc9db0c9cd0bc80b79ad658078e3737` or the same input bytes. No network or weights are needed. Use a **new output directory**; never overwrite committed receipts. From the repository root:

```sh
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
O=$(mktemp -d)
taskset -c 10,11 python3 experiments/20261113-189-missing-metadata/reproduce.py --out "$O/reproduction"
taskset -c 10,11 python3 research/weight-binding/test_wb_leafv2_evidence.py "$O/evidence-tests.json"
diff -r experiments/20261113-189-missing-metadata/runs/registered "$O/reproduction"
cmp experiments/20261113-189-missing-metadata/runs/evidence-tests.json "$O/evidence-tests.json"
```

All six fixed arms and five repetitions are implemented in `reproduce.py`, independently of the evidence-suite fixture helpers. Every arm copies committed source files into its own private temporary directory, removes the copied summary, applies only its named mutation, and calls the unchanged comparator and summariser in separate subprocesses. JSON receipts include all outcomes. A truncated/reordered full PASS halts immediately with exit 2. Unexpected outcomes return 1; all expectations met returns 0. Source hashes are compared in a `finally` block. Refusal text can vary with the Python JSON decoder, so byte-equal receipts are an additional reproducibility check, not the only correctness criterion.

`runs/registered/summary.json` contains per-arm n, median, sample SD, min/max for common-block counts and the full-PASS indicator. Refused comparisons have no block-count statistic. Per-repetition files retain full outputs; `runs/evidence-tests.json` retains every suite expectation. See `RESULTS.md` for the verdict, limitations and the recommendation to require metadata for registered evidence in a separately registered change. Original PR #151 run files are read-only throughout.
