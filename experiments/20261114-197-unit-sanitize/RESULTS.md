# Results: 20261114-197-unit-sanitize (issue #197, part of #182)

## Verdict
**Run 1: KILLED** at a registered kill criterion. **Run 2, under PREREG amendment 1: PASS on every registered item.** Measured, unreplicated. Deterministic functional outcomes, not timings.

Plain summary: `prover/tests/unit.sh` now has an opt-in `--sanitize` switch for host tests. Without it, the script builds the same binaries byte for byte. With it, two planted bugs are caught, a `.cu` source is refused, and a compiler without the sanitizers gives "not run" (77). The #182 reader matrix, built with the address and undefined-behaviour sanitizers, gives the same category as the release series on all 330 calls, and no sanitizer report.

## Run 1 (`ubsan197_run.py`, receipts `runs/` and `../20261113-182-reader-parity/runs-ubsan-20261114/`)
Slot granted 2026-11-14T03:37:46Z, stopped 03:38:13Z.
- Fixture identity: 82 of 82 regenerated files equal the committed supplementary hashes; expectations equal (`runs/fixture-identity.json`).
- Default-build identity: 3 of 3 binaries byte-identical (`runs/default-build-identity.json`). The runner reported "g++ lines identical False" because it did not replace the two arms' different output-directory names; the traced lines differ only there (see the file).
- Signed-overflow control: reported (exit 1, `runtime error: signed integer overflow`). `.cu`: exit 2, nothing made. Compiler without sanitizers: exit 77, `not run: ...`.
- **Heap-read control `controls/control_heap_read.cpp`: exit 1, status 97, but reported by the undefined-behaviour sanitizer's object-size check** (`runtime error: load of address ... with insufficient space for an object of type 'int'`), not with the registered `ERROR: AddressSanitizer: heap-buffer-overflow`. The bug was caught; the registered text was not seen. Kill criterion: UBSan arms not run (`runs-ubsan-20261114/summary.json`: NOT RUN).

## Run 2 (`ubsan197_run2.py`, receipts `runs-2/` and `../20261113-182-reader-parity/runs-ubsan-20261114-2/`)
Amendment 1 (committed before run 2) replaced the heap-read control by `controls/control_heap_read_v2.cpp` (read through a `volatile` pointer), fixed the g++ line comparison and kept the caller's PATH out of receipts. Slot granted 03:43:25Z, done 03:44:42Z (77.3 s elapsed).

| registered item | threshold | measured | file |
|---|---|---|---|
| signed-overflow control | exit 1 + UBSan text | exit 1, `runtime error: signed integer overflow` | `runs-2/harness-controls.json` |
| heap-read control (v2) | exit 1 + ASan text | exit 1, `ERROR: AddressSanitizer: heap-buffer-overflow`, 0 bytes after a 32-byte region | same |
| `.cu` with `--sanitize` | exit 2 | exit 2, no output directory made | same |
| g++ without sanitizers | exit 77 + `not run: ` | exit 77, `not run: control_signed_overflow: this machine's g++ cannot build ...`, no binary | same |
| default binaries | byte-identical | 3 of 3 identical, g++ lines identical | `runs-2/default-build-identity.json` |
| open_above copies | test exit 0 | `folder_look_copies_test.py` exit 0 | same |
| fixture identity | all equal | 82 of 82 equal; 23 verifier-made files not regenerated (the reader does not read them) | `runs-2/fixture-identity.json` |
| sanitized builds | (prerequisite) | 6 of 6 exit 0, 7.1 to 8.5 s each; baseline sources hash-equal to #182's | `../20261113-182-reader-parity/runs-ubsan-20261114-2/builds.json` |
| positive controls | 4 pass, no sanitizer text | 4 of 4 `passes`, exit 0 | `runs-2/positive-controls.json` |
| UBSan arms: category mismatches vs release | 0 each repetition | 0,0,0,0,0 (median 0, SD 0, min/max 0/0, n=5; 66 calls each) | `.../runs-ubsan-20261114-2/summary.json` |
| UBSan arms: sanitizer reports | 0 each repetition | 0,0,0,0,0 (median 0, SD 0, min/max 0/0, n=5) | same |
| UBSan arms: mismatches vs #182 expectations | (reported) | 0 each repetition | same |

Release run of the controls (information only, not a criterion): signed overflow exit 1 (the program's own return value, no report), heap read exit 0.

## What this does not establish
- Sanitizer coverage is only what these paths exercise: the reader's parse and limit admission on 33 synthetic policy files and the two parameter-file tests. Not the verifier, not cp_commit or cp_prove, not GPU code, not MSan or TSan.
- The sanitizers cannot see an overflow inside one object, a read of memory never written, a data race, or code no fixture reaches (as `verifier/tests/sanitized_walk_test.sh` also says).
- The v2 heap-read control was chosen after a throwaway program of the same shape gave the ASan text (disclosed in amendment 1). The first control's result stays on record.
- No dense producer path, dense key or proof. #182's verifier planning calls were not re-run (not part of the UBSan arms).
- One host, one compiler (g++ 13.3.0). Measured, unreplicated.

## Deviations
- Run 1 killed; run 2 under amendment 1 (above). Run 1 receipts are kept; one field (caller PATH in `runs/harness-controls.json`) redacted before its first commit.
- Sanitized runs have no address-space cap (ASan reserves large virtual ranges), as the PREREG states; bounded by CPU-time limit, ASAN_OPTIONS memory bounds and the heavy-job gate.
- The base `unit.sh` was placed temporarily at `prover/tests/unit_base197.sh` during item 2 and removed by the runner afterwards; it is not committed.

## Addendum after review, 2026-11-14: two harness fixes and confirmation run 3 (PREREG amendment 2)

This section is appended. The text above is unchanged and describes the harness as it was at `1f7e5fd2`.

**Verdict: run 3 PASS on every registered item; no count differs from run 2's. Measured, unreplicated.**

Plain summary: two reviews of run 2 reproduced its numbers and found two faults in the new `--sanitize` path of `prover/tests/unit.sh`. A caller's sanitizer setting could make a run that had a sanitizer report end as `passes`, and the compiler probe could delete a file of the caller's. Both are fixed. The fixes were registered first (amendment 2), the findings were reproduced with the old script, and the whole registered series was run again with the fixed script (run 3): same result as run 2, plus 58 of 58 new regression cases as required.

### The two findings, with the old script and with the fixed one
Old script: `unit.sh` as at `e11ec537` (SHA-256 `a228d3bd...`), run at commit `53a5f32e`, receipt `runs-oldhead-review/review-cases.json` (`review_cases_oldhead.py`). Fixed script: `unit.sh` as at `7364ab57` (SHA-256 `c7f12d2e...`), receipt `runs-3/regression-cases.json`.

| case | old script | fixed script |
|---|---|---|
| `UBSAN_OPTIONS=exitcode=0`, `--sanitize run` of `controls/control_signed_overflow.cpp` (both reviews) | **exit 0, `passes`**, report in the log | exit 2, refused before the program starts, no `passes` |
| `ASAN_OPTIONS=exitcode=0`, `--sanitize run` of `controls/control_heap_read_v2.cpp` (both reviews) | **exit 0, `passes`**, report in the log | exit 2, refused, no `passes` |
| `LSAN_OPTIONS=exitcode=0` on the heap-read control (not tried by the reviews) | **exit 0, `passes`**, report in the log | exit 2, refused, no `passes` |
| `LSAN_OPTIONS=exitcode=0` on the signed-overflow control | exit 1 | exit 2, refused |
| `ASAN_OPTIONS=log_path=<elsewhere>` on the heap-read control | exit 1, but the report is **not in `<test>.log`** (it went to `<elsewhere>.<pid>`) | exit 2, refused, no such file made |
| a report in a process that ends with status 0 (`controls/control_report_status0.cpp`, no caller variable; with the old script, a private copy of that source) | **exit 0, `passes`**, report in the log | exit 1, `status 0, and a sanitizer's report in the log`, `fails` |
| failing compiler, pre-existing `<out>/sanitized/sanitize_probe` (astra review) | exit 77, **the caller's file is gone** | exit 77, `not run: ...`, the file and six other sentinels present with the same bytes, folder listing unchanged |

### What the fix is, and why it is closed
With `--sanitize`, for `run` and `both`:
1. **The caller's settings are checked before anything is made or started.** `ASAN_OPTIONS` may hold only `hard_rss_limit_mb=<number>` and `max_allocation_size_mb=<number>`, separated by colons (or be empty or unset). `UBSAN_OPTIONS` and `LSAN_OPTIONS` must be unset or empty. Anything else is exit 2 with a line that names the variable. The check is a whole-string match, so a space, comma or newline as a separator, an `include=` file, or any other key is refused.
2. **The script sets the three variables itself for the runs**: `exitcode=97`, `log_path=stderr`, `halt_on_error=1`, `abort_on_error=0`, after the caller's memory bounds. Since the caller's string can hold only the two memory keys, the script's values are the only ones for every other key.
3. **Each run's own lines in `<test>.log` are read**: a line with `runtime error:` or `Sanitizer` makes it a failed run whatever its status.

- *Exit code*: a caller cannot supply `exitcode` in any of the three variables (1), the script supplies 97 (2), and a report with status 0 that appears anyway fails through the log (3; group C shows this path alone, with the status forced to 0 from inside the program).
- *Log destination*: a caller cannot supply `log_path` (1), and the script sets the standard error stream (2), which the run appends to `<test>.log`, where (3) reads it.
- *Recovery and halt*: a caller cannot supply `halt_on_error` or `abort_on_error` (1); the script sets them (2); the build has `-fno-sanitize-recover=all`; and a report after which the program went on and returned 0 would still fail through (3).
- *Suppression*: a caller cannot supply `suppressions` or `include` (1).

Limits of this, stated plainly: the check is of these three variables' values. A caller who controls the rest of the environment (`PATH`, `LD_PRELOAD`, the compiler itself) is outside it, as for every script here. A test program that closes or redirects its own standard error stream would take a report out of the log; by the script's settings the status would then still be 97, but that combination was not run here. A program that both hides its stream and restarts itself with its own sanitizer settings, as the group C control does on purpose for the second half, could get past both checks. Such a program is a hostile test, not a hostile caller, and is outside this fix. A test that prints the word `Sanitizer` or `runtime error:` on its own fails under `--sanitize`: that is the safe direction, and the head comment says so.

**The probe.** The compiler probe is built in a folder that the call makes with `mktemp -d` (`<folder>/sanitized/sanitize_probe.<random>`), as the SHA probe of the default path already does; the call removes the one file it may have made there and that folder, nothing else. Every removal that a `--sanitize` call can reach was checked against the same promise. The new code path has two, that `rm -f "$probe/probe"` and `rmdir "$probe"`. The only others in the script are the SHA probe's (unchanged since before this PR, reached when a run dies with SIGILL): it too works in a `mktemp -d` folder of its own and removes its three files and that folder. `<test>`, `<test>.build.log`, `<test>.log` and `sanitize_settings.cpp` are overwritten by name, not removed, as the head comment now says for all four; with a compiler that cannot build with the sanitizers the call ends before any of them is written (group D: sentinels at exactly those names keep their bytes).

**Memory bounds still work.** The only sanitizer variable any runner sets is `ASAN_OPTIONS=hard_rss_limit_mb=2048:max_allocation_size_mb=2048` (`ubsan197_run.py`, `ubsan197_run2.py`, and the new `ubsan197_run3.py`); the #182 runners set none. That value is accepted (group A: both controls still fail with status 97 under it; run 3's negative and positive controls ran under it through `unit.sh`). The 330 reader calls start the sanitized program directly, not through `unit.sh`, so they are not affected: all 330 run 3 calls have the same exit status, standard output, standard error and category as run 2's.

### Regression cases (in the repository)
`experiments/20261114-197-unit-sanitize/unit_sanitize_regress.py`, run as `python3 -B experiments/20261114-197-unit-sanitize/unit_sanitize_regress.py <checkout> <new private folder> <new receipt.json>`; exit 0 only if all 58 cases have their required outcome. Run 3 runs it and stops if it fails. Receipt: `runs-3/regression-cases.json`.

| group | what | cases | as required |
|---|---|---|---|
| A | accepted settings (none; the runners' bounds; one bound; empty) on both controls: exit 1, `status 97`, text in the log, no `passes` | 8 | 8 |
| B | 16 hostile settings on both controls with `run`, one with `both`: exit 2, variable named, program not started, no `passes`, no file elsewhere. Includes the two reviewer cases and two log-destination cases (`ASAN_OPTIONS=log_path=...`, `UBSAN_OPTIONS=log_path=...`) on each control | 33 | 33 |
| C | a report with status 0 (`controls/control_report_status0.cpp`): exit 1, text in the log, no `passes` | 1 | 1 |
| D | the probe: failing compiler with `build` and with `both` (7 sentinels, exit 77, `not run:`, same bytes, listing unchanged); working compiler (3 sentinels kept, only the program, its build log and the settings source added) | 3 | 3 |
| E | without `--sanitize`, main's `unit.sh` (`cdde9629`, byte-identical to the base commit's) against the fixed one, 13 usage, folder and run cases: same exit status | 13 | 13 |
| | total | 58 | 58 |

Group E, reported beyond the requirement: the standard-output lines are equal in 13 of 13; the standard-error text is equal in 10 of 13, and the 3 that differ are the usage-text cases, where the text names the option (by design since `3a1ea485`). For information only: the group C source built and run without `--sanitize` exits 0 with `passes` and no sanitizer text (the default path does not read the log for reports).

### Run 3 against its registered thresholds (`ubsan197_run3.py`, receipts `runs-3/` and `../20261113-182-reader-parity/runs-ubsan-20261114-3/`)
One invocation at `7364ab57`, slot granted 2026-11-14T05:29:08Z, done 05:30:47Z (98.8 s of a 1200 s budget), cores 0-1.

| registered item | threshold | run 3 | run 2 | file |
|---|---|---|---|---|
| signed-overflow control | exit 1 + UBSan text | exit 1, text in log | same | `runs-3/harness-controls.json` |
| heap-read control (v2) | exit 1 + ASan text | exit 1, text in log | same | same |
| `.cu` with `--sanitize` | exit 2, nothing made | exit 2, nothing made | same | same |
| g++ without sanitizers | exit 77 + `not run: ` | exit 77, `not run: ...`, no binary | same | same |
| default binaries, main's `unit.sh` vs fixed | byte-identical, g++ lines identical | 3 of 3, 3 of 3; same SHA-256 as run 2's binaries | 3 of 3 | `runs-3/default-build-identity.json` |
| open_above copies | test exit 0 | exit 0 | exit 0 | same |
| fixture identity | all equal | 82 of 82 | 82 of 82 | `runs-3/fixture-identity.json` |
| sanitized builds | (prerequisite) | 6 of 6 exit 0, 8.1 to 9.9 s | 6 of 6 | `.../runs-ubsan-20261114-3/builds.json` |
| regression cases (new) | 58 as required | 58 of 58 | not part of run 2 | `runs-3/regression-cases.json` |
| positive controls | 4 pass, no sanitizer text | 4 of 4 | 4 of 4 | `runs-3/positive-controls.json` |
| reader matrix: category mismatches vs release | 0 each repetition | 0,0,0,0,0 (median 0, SD 0, min/max 0/0, n=5; 66 calls each, 330 in all) | same | `.../runs-ubsan-20261114-3/summary.json` |
| reader matrix: sanitizer reports | 0 each repetition | 0,0,0,0,0 (median 0, SD 0, min/max 0/0, n=5) | same | same |
| reader matrix: status failures (new rule) | 0 | 0,0,0,0,0 | rule not in run 2 | same |
| reader matrix: mismatches vs #182 expectations | (reported) | 0 each repetition | same | same |

The new status rule counts a reader call as failed, whatever category was printed, if its exit status differs from the release receipt's for the same case and arm or is not 0, 1 or 2. Run 3 also stops at once on a positive control that fails or shows sanitizer text. Both were asked for in review for future runs; `ubsan197_run.py` and `ubsan197_run2.py` are unchanged.

### What this does not establish
Everything under "What this does not establish" above still holds. In addition:
- Run 3 confirms the registered series with the fixed script on the same host and compiler. It is not an independent replication. Status stays measured, unreplicated.
- The fail-closed property is shown for the 58 cases above, not proven for every possible value; the argument for other values is the whole-string check in point 1.
- Not the verifier, not cp_commit or cp_prove, not GPU code, and #182 is not declared complete.

### Deviations (this addendum)
- Amendment 2's heading time is 17 s later than its commit; see the PREREG's outcome entry.
- Debugging before run 3 used two more throwaway programs than amendment 2 names, and the regression script was tried once on throwaway programs with `--debug-throwaway` (PREREG outcome entry). No registered program ran with the changed script before run 3.
- `--sanitize run` with a compiler that lacks the sanitizers still exits 2 when nothing was built (reviewer note): not changed. `run` never calls the compiler, and 2 is the script's documented status for `run` without a built program; the head comment now says so in words.
