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
