# RESULTS: 20261113-182-reader-parity

## Verdict: PARTIAL, blocked before compilation

This is an **untested patch proposal**, not evidence that issue #182 is resolved.
PREREG.md was the first and only file in commit `3d9321c`; implementation followed it.
The first baseline release build was refused by the existing `prover/tests/unit.sh`
output-directory safety check: an ancestor of the requested output directory was writable
by group/others and had no sticky bit. The script explicitly reported that nothing ran.
The lane's instruction forbids rerunning a refused command in another form, so the lane
neither relocated this build nor invoked a compiler directly, changed directory permissions,
or altered the safety check. This is an environment/safety blocker, not a verifier-rule blocker.

The refusal is retained in `runs/build/before-release-parameter_file_tables_test.txt`.
`runs/build/attempt.json` records the requested command and exit categories. Host-specific
paths in the text receipt are replaced by `<REPO>` and `<WORKSPACE>`; no outcome text is changed.
The unit script returned status 2; the orchestration process stopped with status 1.
There are **zero compiled binaries and zero executed registered cases**. Binary hashes,
runtime variance, and the required pre-change reproduction are consequently unavailable,
not zero-valued successful measurements. Source SHA-256 values are in `runs/source-hashes.json`.

## Proposed change (static reading only)

`prover/common/parameter_file.h` replaces only the experts-only table-line rule in
`limit_missed()` with a zero-sigmoid predicate. At NE 0 with digest lines present, every
`tsig0` through `tsig7` value must be zero. The predicate is vacuous with experts or without
lines. The parser's all-or-none group, order, duplicates and numeric encoding logic is
unchanged. All other limit rules, including rcl/gcl and absent classes/kinds, are unchanged.
This describes source intent, **not demonstrated behavior**.

`prover/tests/parameter_file_tables_test.cpp` is an uncompiled CPU-only probe that reports
parse and limit outcomes separately. It is not yet an implemented synthetic regression suite.
No verifier source or digest algorithm was changed. Historical experiment files were not changed.

## Required outcome matrix: not run

| Registered category | CPU parse | CPU admission | cp_verify planning/standard form |
| --- | --- | --- | --- |
| Dense own-digest form, before and after | not run | not run | not run |
| Dense no digest lines | not run | not run | not run |
| Partial, reordered and duplicate digest words | not run | not run | not run |
| Dense nonzero sigmoid, each word position | not run | not run | not run |
| Changed SiLU, rotary and softmax digest words | not run | not run | not run |
| Invalid word encoding | not run | not run | not run |
| Dense rcl/gcl and absent-class/absent-kind | not run | not run | not run |
| Experts-present forms and malformed controls | not run | not run | not run |
| Existing one_bits/one_place regression tests | not run | not run | not applicable |

Both release and UBSan runtime coverage are missing. This fails to establish the preregistered
acceptance threshold. There is no PASS, no claim that malformed groups remain rejected at runtime,
and no claim that experts-present outcomes have been preserved experimentally.

## Boundary and limitations

The reader does not recompute table hashes. Main's verifier, not this proposed reader predicate,
compares its public tables to supplied digests and enforces table-digests as a standard-form
condition. The intended difference between parseable no-digest files and standard-form files
must still be measured, as must rejection of syntactically admitted incorrect digests.
No dense proof, producer-path support, converter behavior, model forward pass, key production,
cp_commit/cp_prove execution or Qwen model support is established. No performance result exists.

## Deviations and next step

The preregistered suite, fixture generation, release/UBSan builds and repetitions were not
completed because the first build was refused. Only the source proposal and probe are delivered.
A separately authorized continuation needs a safe output location accepted by the existing
unit harness, then the complete registered matrix and source/binary receipts before this draft
can be considered for review or merge. Do not treat documentation describing the older reader
as superseded by a measured result from this partial lane.
