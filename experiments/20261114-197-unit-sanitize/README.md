# unit.sh --sanitize and the #182 UBSan arms

**What it adds.** `prover/tests/unit.sh --sanitize` builds and runs a host (.cpp) unit test with gcc's address and undefined-behaviour sanitizers. The flags are the ones in `verifier/tests/sanitized_walk_test.sh`, plus the defines, instruction-set switches and include folders of unit.sh's default host line. The program and its logs go into `<folder>/sanitized`. That folder is made with mode 700 below the checked output directory and checked the same way. A report ends the program with status 97, so unit.sh exits 1, and the report text is in `<folder>/sanitized/<test>.log`. A `.cu` source gives exit 2. A compiler that cannot build with the sanitizers gives exit 77 and a `not run:` line. Without `--sanitize` the script behaves as before, and the default binaries are byte-identical (see RESULTS.md).

**What is checked here.** Two negative controls (`controls/`), the `.cu` refusal, the 77 path, byte identity of three default builds, and fixture identity. Then the #182 reader matrix (33 fixtures, baseline and patched reader, five repetitions) is run with sanitizers, and its categories are compared with the release series. Results: [RESULTS.md](RESULTS.md). The UBSan arm receipts are under `../20261113-182-reader-parity/runs-ubsan-20261114-2/`.

**What is not covered.** The verifier, the prover programs, GPU code, MSan and TSan. Also anything the sanitizers cannot see (see RESULTS.md).

## Reproduce
From the checkout's top, on a machine with g++ 13 and its libasan and libubsan:
```
d=$(mktemp -d)
fp-heavy-or-not taskset -c <two cores> python3 -B experiments/20261114-197-unit-sanitize/ubsan197_run2.py "$PWD" "$d"
```
(`fp-heavy-or-not` stands for your own job gate, if you have one.) The runner refuses to overwrite its output directories (`runs-2/`, `../20261113-182-reader-parity/runs-ubsan-20261114-2/`). To reproduce, use a copy with those two names changed. `--dry` prints the plan and writes nothing. The single commands it runs are recorded in each receipt's `command` field, with `<REPO>` and `<PRIVATE_BUILD>` in place of the two directories. Examples:
- `bash prover/tests/unit.sh --sanitize build tests/parameter_file_tables_test.cpp <PRIVATE_BUILD>/after`
- `<PRIVATE_BUILD>/after/sanitized/parameter_file_tables_test <REPO>/experiments/20261113-182-reader-parity/runs/supplementary-matrix/fixtures/<case>/policy.txt` (with `ASAN_OPTIONS=hard_rss_limit_mb=2048:max_allocation_size_mb=2048`)
- `bash prover/tests/unit.sh --sanitize run tests/parameter_file_one_bits_test.cpp <PRIVATE_BUILD>/after tests/configurations/pinned_no_proof_of_work/policy.txt`

`ubsan197_run.py` is run 1's runner. It is kept as executed, and its result is KILLED.

## After review (2026-11-14, PREREG amendment 2)
This section is appended; the text above describes the first version. Two things changed in `unit.sh --sanitize` after review, and nothing without `--sanitize`:
- **A sanitizer's report never ends as a pass.** For `run` and `both`, the caller's `ASAN_OPTIONS` may hold only memory bounds (`hard_rss_limit_mb=<number>`, `max_allocation_size_mb=<number>`, separated by colons), and `UBSAN_OPTIONS` and `LSAN_OPTIONS` must be unset or empty. Any other value gives exit 2 before anything is made or started. The script then sets the three variables itself for the runs, and a run whose own lines in `<test>.log` contain `runtime error:` or `Sanitizer` is a failed run whatever its status. So the sentence above, "A report ends the program with status 97, so unit.sh exits 1", is now one of two ways a report fails a run.
- **The compiler probe is private.** It is built in a new folder of its own (`sanitize_probe.<random>`, made with `mktemp -d`), and only that folder is removed. A file of yours in `<folder>/sanitized` is never removed.

**Regression cases** (58, in the repository): `python3 -B experiments/20261114-197-unit-sanitize/unit_sanitize_regress.py "$PWD" "$d/regress" "$d/regress.json"` with `d=$(mktemp -d)`. It exits 0 only if every case has its required outcome. `--dry` prints the cases and runs nothing. It places main's `unit.sh` beside the script as `prover/tests/unit_main198.sh` while its last group runs and removes it again.

**Run 3** (the confirmation run with the fixed script): `ubsan197_run3.py`, same usage as `ubsan197_run2.py` above; it writes `runs-3/` and `../20261113-182-reader-parity/runs-ubsan-20261114-3/` and refuses to overwrite them, so use a copy with those two names changed to reproduce. It runs the regression cases as one of its steps. `review_cases_oldhead.py` reproduced the two review findings with the script as it was at `e11ec537` (receipt `runs-oldhead-review/`); it refuses to run with any other `unit.sh`, so to rerun it check out `53a5f32e`.

Results of all three: [RESULTS.md](RESULTS.md), "Addendum after review". `ubsan197_run.py` and `ubsan197_run2.py` are kept as executed.
