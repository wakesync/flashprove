# Reproduce the leaf-v2 missing-metadata boundary and the #189 stop-rule finding

This follow-up tests how the existing leaf-v2 reader treats copied evidence when metadata is missing, altered or substituted. It proves no cryptographic statement and changes no reader behaviour.

**Result: issue #189's stop rule fired (blocking finding).** Truncated, reordered or substituted copies of run 3 can get a full H3 `PASS`. See `RESULTS.md` for the verdict, the table of cases, the limits and the recommendation.

In plain language:

- **What is proved:** nothing. This is a hash-level study of two readers on committed files.
- **What the readers recompute:** `wb_leafv2.py compare` rebuilds canonical leaves (and, for a complete run, the tree) from validated record files and compares run 1 with another run block by block. `summarise.py` recomputes that comparison for run 2 and run 3 and reports H3 on the **union** of the blocks the two cover.
- **What is not covered:** neither reader checks integer hashes against model weights. Neither can tell which run produced a record, whether a run was executed in the direction its file order suggests, or whether "run 3" is a copy of run 1. Without `run-meta.json`, recorded completion and direction are unchecked; with it, they are checked only for consistency, not authenticity.

Requirements: Python and numpy versions recorded in `ENV.json`, Linux for `taskset`, repository inputs at base commit `4991f69acbc9db0c9cd0bc80b79ad658078e3737` or the same input bytes. No network or weights are needed. Use a **new output directory**; never overwrite committed receipts. From the repository root:

```sh
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
O=$(mktemp -d)

# 1. The six registered arms (2026-11-13): 30 of 30 expected outcomes, exit 0
taskset -c 10,11 python3 experiments/20261113-189-missing-metadata/reproduce.py --out "$O/reproduction"
diff -r experiments/20261113-189-missing-metadata/runs/registered "$O/reproduction"            # expect no output

# 2. The review-driven stop-rule cases (PREREG amendment A-1, 2026-11-14): 115 of 115 as registered, exit 0
taskset -c 12,13 python3 experiments/20261113-189-missing-metadata/stoprule_cases.py --out "$O/stoprule"
diff -r -x env.json experiments/20261113-189-missing-metadata/runs/stoprule-20261114 "$O/stoprule"   # expect no output

# 3. The evidence suite with the stop-rule cases: 231 / 231 over 82 cases, exit 0
taskset -c 12,13 python3 research/weight-binding/test_wb_leafv2_evidence.py "$O/evidence-tests.json"
cmp experiments/20261113-189-missing-metadata/runs/evidence-tests-stoprule-20261114.json "$O/evidence-tests.json"
```

Exit status 0 in step 2 means every case gave the outcome registered for it, **including the full `PASS` outcomes**: it is a reproduction of the finding, not a clean bill for the reader. In `runs/stoprule-20261114/summary.json`, `stop_rule_fired` is `true` and `cases_with_full_pass_on_altered_run3` lists the 13 cases.

`reproduce.py` implements the six fixed arms and five repetitions, independently of the evidence-suite fixture helpers. A truncated/reordered full PASS in those arms halts it with exit 2; unexpected outcomes return 1.

`stoprule_cases.py` was written for amendment A-1. It imports neither `reproduce.py`, the evidence suite nor the reader. Each of its 23 cases copies the committed runs into a private temporary directory, removes the copied summary, applies only its named alteration and calls the unchanged comparator (run 1 against run 3, and run 1 against run 2) and the unchanged summariser in separate subprocesses. It then checks the reader's report against the fixture files themselves, parsed with the `json` module only: every block counted as covered must be present in the supplied files, and every block reported identical must have equal `e`, `int_sha256` and fetched-bytes `sha256`. A disagreement there stops the run with exit 3 (reported coverage or agreement that the files do not contain, a more serious finding than the one recorded); a changed committed source file gives exit 4; a case that differs from its registered outcome gives exit 1.

Receipts. `runs/registered/` (2026-11-13): `summary.json` with per-arm n, median, sample SD, min/max for common-block counts and the full-PASS indicator, per-repetition files, before/after source hashes. `runs/stoprule-20261114/` (2026-11-14): `summary.json` with the same statistics per case plus union counts and how many union blocks only run 2 supplies, 115 per-repetition files, before/after source hashes, `env.json`. `runs/evidence-tests.json` is the suite receipt of 2026-11-13 (177 expectations); `runs/evidence-tests-stoprule-20261114.json` is the current one (231). Nothing under `runs/registered/` and neither earlier suite receipt was modified.

Byte equality of receipts is an additional reproducibility check, not the correctness criterion: refusal text can vary with the Python JSON decoder. For step 2 a second invocation on the recording host, made after the recorded run, compared equal on every file except `env.json`, which differs only in its timestamp. Original PR #151 run files are read-only throughout.
