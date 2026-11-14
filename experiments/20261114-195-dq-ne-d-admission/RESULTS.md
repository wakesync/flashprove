# RESULTS: 20261114-195-dq-ne-d-admission

Issue #195 (part of #163, #35). PREREG: [PREREG.md](PREREG.md), first commit `4aa4d2605415f87470f3e4c8d7830a5dda60b098`, with Amendments 1 to 5 (each committed before the runs it covers; Amendments 4 and 5 were written after review, by fix lanes). Environment and hashes: [ENV.json](ENV.json). Base `2583aca969bb9f33afc92d553dcbd2e2a69fcedc`.

## Verdict

**The observed outcomes meet the registered threshold, so the candidate is adopted on this branch. Measured, unreplicated, CPU planning only.** No stop rule of `DQ-NE-D.md` section 5 fired. The run was **not completed as first registered**: T8 ran one round in the original window, side by side; its rounds 2 to 5 were run later, alternating, in a completion run registered after review (Amendment 4, below). Several registered items are weaker than planned or still open; they are listed below and are part of the result.

No proof with dq != d exists or was checked. Both prover gates are closed and untouched. This result says nothing about an honest unequal-width proof, about reverse-direction T3, about dh = 256, rotary, or Qwen admission.

## Read this first: the rotary table can now be larger than on main, and it is bounded

Corrected after review (2026-11-14). The first version of this section said the table could reach "2^16 * 2^20 words" and that nothing was tested. Both statements are replaced; the old text is quoted under "Corrections after review".

**Answer: yes, a file can now ask for a larger rotary table than it could on main. The table stays bounded, at 2^27 u32 words (512 MiB), by a test that was already there.** This is an allocation question. Nothing here is about what the verifier accepts.

Reading, at this branch's head (the table is `cp_verify.cpp:1612-1619`, `T * dh` u32 words):

- `shape-heads` (`cp_verify.cpp:525-526`) now bounds dh only through `H dh <= 2^20`; on main it also asked `H dh = d` (`cp_verify.cpp:520-521` at the base).
- `forest-keys` (`vf_lookup_argument.h:130`, called from `cp_verify.cpp:812`, long before the table) refuses when the calls' padded keys, the sum of `Lam * J_c * T`, exceed 2^31.
- The lookup segments QK, V, CQK and CV are always present (`cp_verify.cpp:667, 675, 696, 697`) and hold `2 dq + 4 dkv >= 6 dh` columns; `Lam >= 2` (`ll >= 1`, `cp_verify.cpp:492`). So `12 T dh <= 2^31`, and `T dh`, a power of two, is **at most 2^27 on this branch**.
- On main, `d = H dh >= dh` puts eight more segments of d columns into the same sum (N1, N1H, N2, N2H, O, D, CN1, CN2: `cp_verify.cpp:669-674, 694-695`): `28 T dh <= 2^31`, so **at most 2^26 on main**.
- Between `forest-keys` and the table: the layer shifts, the no-overflow conditions (`:1441-1540`), the weight layout (`:1575-1594`) and `shape-theta0` (`:1601`). They refuse some files (the registered at-bound files never get this far) and do not change the bound.

Measured under Amendment 4, each call once, `cp_verify -plan arrays` under `prlimit --as=4294967296` and `timeout 120` (`runs-4/rotary/`, files in `runs-4/rotary/files/`, made by `rotary_files.py`):

| file | d, H, G, dh, lt | T dh | patched | base |
|---|---|---|---|---|
| P27 | 8, 1, 1, 131072, 10 | 2^27 words, 512 MiB | status 1, `NO: af-policy-kF`, peak 538,008 KiB, 6.6 s: **table completed** | `NO: shape-heads`, 5,248 KiB |
| P28 | 8, 1, 1, 262144, 10 | 2^28 words | `NO: forest-keys`, 20,864 KiB: refused before the table | `NO: shape-heads`, 5,376 KiB |
| B25 | 16384, 1, 1, 16384, 11 | 2^25 words, 128 MiB | `NO: no-wrap-H-three-digits`, 140,188 KiB | status 1, `NO: no-wrap-H-three-digits`, peak 140,060 KiB, 1.7 s: **table completed** |
| B26 | 16384, 1, 1, 16384, 12 | 2^26 words | `NO: forest-keys`, 9,216 KiB | `NO: forest-keys`, 9,216 KiB: refused before the table |

"Table completed" rests on two things together: the refusal's name is raised after the table in the source (`af-policy-kF`: `vf_attention_shape.h:223/228`, on a configuration that `cp_verify.cpp` fills at `:1960`; `no-wrap-H-three-digits`: `cp_verify.cpp:1864/1879`; both lie after `:1619` in the same function), and the peak is above the table's size. All eight outcomes are the ones Amendment 4 wrote down before the runs. They are not blind predictions: Amendment 4's author had read both round-1 reviews and both reviewers' scripts, with their reported outcomes, before writing those expectations (Amendment 4 says so). No call hit a limit. None is a valid plan, and no proof was read.

What this does and does not give:

- Largest table reached: **2^27 words (512 MiB) on this branch, 2^25 words (128 MiB) on main.** The branch's figure equals its bound, so it is the maximum.
- The factor is **between 2 and 4**. It is 4 between the two tables reached. Main's bound from the reading above is 2^26, and B26 does not settle whether main can reach it: B25 and B26 use one call list, in which the FC call is padded; a call list that splits the calls was not tried. If some file reaches 2^26 on main the factor is 2. By my count, with nothing built or run: at d = dh, H = G = 1, with the digit forms of o and d set to 0, eight calls {QK}, {N1, N1H, N2, N2H}, {O, D}, {V, G, U, UT}, {CN1, CN2, CQK}, {CV} and two small ones would hold about 15 d columns, inside the 16 d that 2^26 words leave at two layers. So I expect that main can reach 2^26 and that the factor is 2. That is an expectation from reading only; other tests on the way to the table could still refuse such a file. Both round-2 reviewers report reaching main's 2^26 words with such a split call list on the base binary, which makes the factor 2 (https://github.com/wakesync/flashprove/pull/199#issuecomment-6874787808, https://github.com/wakesync/flashprove/pull/199#issuecomment-6874790229). Those are reviewers' runs, not a measurement of this PR, so the factor this PR's receipts support stays between 2 and 4.
- A reviewer of this PR reports 2^25 as main's maximum by an argument that includes that padding (https://github.com/wakesync/flashprove/pull/199#issuecomment-6872066809); the other reviewer reports a looser bound from reading, 2^29 words on both binaries, and concludes the largest table did not grow (https://github.com/wakesync/flashprove/pull/199#issuecomment-6872158536). The receipts here contradict that conclusion (P27 against B25 and B26); they agree with the first reviewer's reached figures, and they do not establish 2^25 as main's bound.
- `cp_verify` sets itself no memory limit. A 512 MiB table is a larger allocation than any file could ask for at this place before. Whether that needs a guard of its own is the coordinator's decision; no guard is added here, because it would be a code site outside the frozen inventory.
- Not examined: other width-sized allocations before the forest tests. Both reviewers report a large pre-existing allocation there (about 4 GB in `place()` at nqk near 2^26, the same site on base and patched; see their comments). It is old behaviour, it is not a claim of this PR, and it was not run here.

## What changed

- `verifier/src/cp_verify.cpp` (`layout()`, `shape-heads`): `H * dh != d` is replaced by `!queryWidthWithinBound(H, dh)`. The name stays `shape-heads`.
- `verifier/src/vf_widths_and_bounds.h`: `QUERY_WIDTH_MOST = 2^20` and `queryWidthWithinBound(H, dh)`, the product in 128 bits, called before dq is formed.
- No other verifier source line. `vf_rejection_names.txt` unchanged. No prover file changed.
- Docs: `verifier/docs/parameter-file.md` (row H, G, dh), `docs/format/FORMAT.md` (rows `shape-heads`, `plan-tensor-layout-fill-<arr>`, `shape-words`), `docs/format/11-2-feed-forward-segment.md` (two rows).
- Tests: new `verifier/tests/query_width_bound_test.cpp`; `weights_twin_test.cpp` two shapes with dq above d; `SUITE.md` expected line of that row; `parameter_walk.py` keeps d in about half of its copies. After review (Amendment 4): two `SUITE.md` rows for the new test, plain and sanitized; `parameter_walk.py` gets a fixed batch of files with H dh != d and a count that it requires to be above zero.

## Registered cases

Planning cases: 5 rounds, both binaries, base and patched alternating first. 70 records, 0 not as registered; each kit was the same bytes in every round. Source: `runs/planning/planning-summary.json`, raw output in `runs/planning/raw/`, kits in `runs/planning/kits/`.

| case | H, G, dh, d | dq | base (5 of 5) | patched (5 of 5) | peak resident, patched |
|---|---|---|---|---|---|
| T7b above | 3, 1, 2^19, 512 | 1,572,864 | `NO: shape-heads` | `NO: shape-heads` | 11,952 KiB |
| T7b one step above | 33, 1, 32768, 512 | 2^20 + 32,768 | `NO: shape-heads` | `NO: shape-heads` | 11,956 KiB |
| T7b at the bound | 32, 1, 32768, 512 | 2^20 | `NO: shape-heads` | `NO: forest-trees` | 39,552 KiB |
| T7b at the bound (design's) | 1, 1, 2^20, 512 | 2^20 | `NO: shape-heads` | `NO: forest-trees` | 97,280 KiB |
| T2, dq above d | 3, 1, 4, 8 | 12 | `NO: shape-heads` | planned | 37,780 KiB |
| T2, dq below d | 1, 1, 4, 8 | 4 | `NO: shape-heads` | planned | 37,764 KiB |
| T7c | 63, 1, 128, 4096 | 8,064 | `NO: shape-heads` | planned | 38,884 KiB |

"Planned" is the registered meaning: `-plan arrays` status 4, `pack_layout.py` made layout.txt, `-plan accounting` status 4 with one line `THE ROUNDS: HOLD` and no `internal-` line, and `-plan request` with that layout at 0 and at 128 bits both status 4. The base binary's peak is about 12,000 KiB on every file.

- The two above-bound files are refused under `shape-heads` with the base binary's memory: the test comes before any tensor is sized.
- The two at-bound files are **not valid plans**. They get past the new test and are refused later, under `forest-trees`. The design note guessed `af-policy-kF`; the measured name is different and is still not N1's.
- T2 with dq below d planned at the first registered run; the corrected rerun that Amendment 1 allowed was not needed.
- No line `plan: not the standard parameter form` appears in any kept output. `-plan request` ran with `-q`. Whether these test shapes are in the standard form was not examined.

**T7a**, the predicate alone (`runs/compiled/run-t7a-*.json`): plain build and a build with the address and undefined-behaviour sanitizers both end `query_width_bound_test: ok (2043 checks; 959 of 1984 pairs (H, dh) with H in 1..64 and dh = 2^1..2^31 admitted)`, status 0, no sanitizer report.

**T1**, layout twins (`runs/compiled/run-twin-t1-second.json`): `weights_twin_test: ok (48 worlds, 780 units, 979500 cells, 7389952 places without a cell; 5508 checks)`. The 12 new worlds are d = 8, dq = 12 and d = 20, dq = 24 with experts, at 6 column settings. The test at its base text, built against the patched tree, prints the base line (36 worlds, 4152 checks).

**T8**, existing rows, base against patched: 10 rows counted, each with the same exit status and the same normalised hash on both binaries. **Round 1** in the original window, base and patched side by side (`runs/existing/existing-summary.json`). **Rounds 2 to 5** in a completion run registered after review (Amendment 4), one binary at a time, patched first in rounds 2 and 4, base first in rounds 3 and 5 (`runs-4/existing/completion-summary.json`, `runs-4/existing/progress.txt`): 40 row-rounds, 40 in agreement, meaning the row passes, base equals patched, and both equal the round-1 hash; 0 differences between base and patched. The five registered rounds are supplied, in these two parts; they were not run as first registered.

| row | status | outcome on both |
|---|---|---|
| example_kits | 0 | 7 parameter files, 0 not as expected |
| served_form (has the dense cases) | 0 | all as expected |
| plan_tau | 0 | 13 cases |
| kit_rounds | 0 | 3 kits, 0 not as stored |
| la_equals_lt | 1 | `NO: shape-la` |
| stored proof, accepted-proof | 0 | `YES` |
| stored proof, clipped-gap, with `-policy` | 0 | `WITHIN LIMITS: clipped-gap C=...` |
| call_accounting | 0 | 0 lines not as in the call |
| rejected-proofs, accepted-proof | 0 | 10 altered sets: all rejected |
| rejected-proofs, clipped-gap | 0 | 10 altered sets: all rejected |

`ws_build_fuzz` (sanitizers, 300,000 shapes, seed 1, built against the patched tree): status 0, `20545 built`, `refused w-shape-mW: 9059`, the same six lines as the committed `research/cpu-full-suite/full-screens/verifier.ws_build_fuzz.txt`.

## Weaker than registered, and faults of this experiment's own harness

1. **T8 ran one round in the original window, not five.** Rounds 2 to 5 were run after review under Amendment 4 (10 of 10 rows in agreement in each). That is a completion after the fact, by another lane, with the round-1 outcome known; it is not the registered execution.
2. **Sanitized planning calls: PENDING.** The one registered attempt to build the whole verifier with sanitizers hit its 120 s limit (`runs/compiled/build-cp_verify-sanitized-once.json`). Sanitized coverage is T7a and `ws_build_fuzz` only. The issue asked for the small boundary cases under UBSan: that was done for the predicate, not for the planning calls.
3. **T3: NOT ESTABLISHED.** Not attempted (time). Nothing here shows that a stored proof is rejected under a changed-H statement by proof checking.
4. **Clipped-gap stored proof, first run not counted.** The harness left out the `-policy` option; both binaries answered `NO: policy`. Kept in `runs/existing/raw/whole_clipped_gap.*` (Amendment 2).
5. **Rejected-proofs rows took three attempts.** Twice the test refused to start (its work folder check; the second time through a fault of the lane's wrapper). Receipts in `runs/existing/not-started/` (Amendment 3). These seven files had host paths replaced by placeholders after their hashes were recorded.
6. **T8 order.** In round 1 base and patched ran side by side on two cores, not alternating. Rounds 2 to 5 alternated as registered. During rounds 2 to 5 this lane's rotary, walk and compiled-test runs used the same two cores.
7. **Walk harness (N6).** The first smoke run with the patched binary printed `33 files; fault 0, unchecked 0, slow 0, large 0`; a reviewer instrumented it and reports that none of its files had H dh != d. After review the harness makes a fixed batch of such files and requires at least one to get past `shape-heads`. The same smoke invocation, patched binary, under the 4 GiB limit and `timeout 120` (`runs-4/walk/walk-width-coverage.log`): `38 files; fault 0, unchecked 0, slow 0, large 0` and `query width: 5 files with H * dh != d, 5 not refused shape-heads`. A round-2 reviewer showed that this counter also counted files refused before `shape-heads` (https://github.com/wakesync/flashprove/pull/199#issuecomment-6874790229): it counted any file whose last line was not `NO: shape-heads`. Under Amendment 5 it counts a file only on evidence that the file reached and passed the test: its call planned it, or ended with a name that the sources print only after `shape-heads` (93 names and 13 prefixes, derived by `derive_counted_names.py`, list in `runs-5/counted-names.json`); any other name, an unknown one included, does not count. Receipts in `runs-5/`: the reviewer's case (a copy with `eps1_lo 0`, refused `policy-norm`) gave status 0 and counted 5 with the harness at `07eb2f39`, and gives status 1 with 0 counted with the corrected harness, in a new negative test `parameter_walk_width_count_test.py`; the registered smoke with the corrected harness gives, patched, status 0, `38 files; fault 0, unchecked 0, slow 0, large 0` and `5 files with H * dh != d, 5 reached and passed shape-heads` (the same count as `runs-4/`), base status 1 with 0 counted, and a copy with the width batch emptied status 1. That count is harness coverage: it shows the walk hands the verifier unequal-width files that pass the new test. It is no result about a plan or a proof. The walk's usual length and the sanitized walk were not run.
8. **`FORMAT.md`, row `shape-words`.** Its "cannot fail" argument for G dh went through d and the equality. For dq != d that step is gone and was not re-derived; the row now says so. If it does fail, the call ends with that refusal by name.
9. **Kits.** The derived lines were worked out on equal-width shapes with the base binary, as registered. The T7c kit needed a line the registration had not listed (`group link`), stated in Amendment 1 before the run.
10. A build of the T1 binary raced the edit of its source and printed the base line; it is kept as `run-twin-t1.json` and is not T1. The counted run is `run-twin-t1-second.json`.

11. **The two new `SUITE.md` rows were not run by the suite runner.** `run_suite.py` could not be started in the fix lane's environment (its command was refused there and was not retried in another form). Each row's own command and pass rule, read from `SUITE.md`, was run by hand by a lane script: both pass with `query_width_bound_test: ok (2043 checks; ...)` (`runs-4/suite-rows-by-hand/`). That `run_suite.py` reads and runs the two rows is **not verified** by this PR. Both round-2 reviewers report running them through `run_suite.py` with both passing (https://github.com/wakesync/flashprove/pull/199#issuecomment-6874787808, https://github.com/wakesync/flashprove/pull/199#issuecomment-6874790229); that is a reviewers' report, not a run of this PR. The row added under Amendment 5, `verifier.parameter_walk_width_count`, was likewise run by a lane script with the row's command, not by the runner (`runs-5/regress-width-count-test.*`).

## Not run

The full suite (and so the two new rows through the runner); the `extreme_files`, `clang_build`, sanitized-walk rows; anything with a GPU, a prover, weights or a proof made here; the Lean model (unchanged, and it does not cover this).

## Corrections after review (2026-11-14, under PREREG Amendment 4)

Two reviews of head `0c6b12a2bd95021e4225cbc8662357e7f6541497` asked for changes: https://github.com/wakesync/flashprove/pull/199#issuecomment-6872066809 and https://github.com/wakesync/flashprove/pull/199#issuecomment-6872158536. No file under `runs/` was changed. No verifier source and no prover file was changed. New receipts are under `runs-4/`. The sentences below were replaced in place above; each is quoted as it stood.

1. Section "Read this first: one open risk found late, not tested", replaced whole. It said: "Found by reading the source 25 minutes before the lane's stop; **not tested, not measured**." and "So the table has at most about 2^16 * 2^15 words there. With the equality gone, dh is bounded only by `shape-heads` at 2^20 while d can stay small, so a file that passes the tests in between could ask for a rotary table of up to 2^16 * 2^20 words." and "Whether another file (other `nmin`, `lidb`, `lt`) gets past `forest-trees`, the no-overflow conditions and `w-shape-mW` to the table with a large dh was not examined." Why: the figure 2^16 * 2^20 cannot be reached. `forest-keys` bounds the table at 2^27 words on this branch, and the section now gives the trace, four witness files on both binaries, and a plain answer. The risk the old text pointed at is real in direction (the table can be larger than on main) and wrong in size.
2. Verdict: "**The registered threshold is met, so the candidate is adopted on this branch. Measured, unreplicated, CPU planning only.** No stop rule of `DQ-NE-D.md` section 5 fired. Several registered items are weaker than planned or still open; they are listed below and are part of the result." Why: it read as a completed registered run. T8 was one of five rounds. The PREREG's Runs section says of this: "T8 script rows run 5 rounds on each binary in the same alternation; rounds not finished by 03:25Z are reported as not run, with the count." Its acceptance section says: "T8 identical on every row run" and "Anything less is PARTIAL or FAIL, reported as such, and then **the widened admission is not adopted**". So the registration allowed fewer rounds if reported, and the threshold was over the rows run; the side-by-side order was a deviation that Amendment 2 disclosed after round 1 had started. The adoption stands on the observed outcomes; the next reviewers can judge it with these two quotations and the completion run in front of them.
3. T8 paragraph: "**T8**, existing rows, base against patched (`runs/existing/existing-summary.json`): 10 rows counted, each with the same exit status and the same normalised hash on both binaries, **one round** (five were registered)." Why: rounds 2 to 5 now exist, as a completion run.
4. Weaker-than-registered item 1: "1. **T8 is one round, not five.** Outputs are deterministic text, and the planning cases did run five rounds; T8's repeat was not done." Item 6: "6. **T8 order.** Base and patched ran side by side on two cores, not alternating." Item 7: "7. **Walk harness (N6).** One short smoke run with the patched binary: `33 files; fault 0, unchecked 0, slow 0, large 0`. Whether any of those files had dq != d was not checked. The walk's usual length and the sanitized walk were not run." Why: each is now answered by a receipt under `runs-4/`, and item 7's first run is known, from a reviewer's report, to have made no unequal-width file.
5. Header line: "with Amendments 1 to 3 (each committed before the runs it covers)." and the "What changed" tests line, which ended "`parameter_walk.py` keeps d in about half of its copies." Why: Amendment 4 and its test changes exist.
6. Item 11 and the first words of "Not run" are new.

Still open after these corrections, unchanged: no proof with dq != d exists or was checked; T3 in both directions is NOT ESTABLISHED; planning calls under UBSan are PENDING (a reviewer reports that a UBSan-only `-O0 -g0` build of the whole verifier completes and that the seven planning cases pass under it with no report, https://github.com/wakesync/flashprove/pull/199#issuecomment-6872066809; that is a reviewer's report, not a run of this PR); the `FORMAT.md` `shape-words` paragraph for dq != d is not re-derived; the full suite was not run; Qwen is not admitted. Status: measured, unreplicated.

## Corrections after review, round 2 (2026-11-14, under PREREG Amendment 5)

The round-2 reviews of head `07eb2f3993c5891815af330cbc1055e6e6257536` split: https://github.com/wakesync/flashprove/pull/199#issuecomment-6874787808 approves, https://github.com/wakesync/flashprove/pull/199#issuecomment-6874790229 asks for changes. No file under `runs/` or `runs-4/` was changed, no verifier source and no prover file, no reported number. New receipts are under `runs-5/`. The sentences below were changed in place above; each is quoted as it stood.

1. Rotary section: "All eight outcomes are the ones Amendment 4 wrote down before the runs. No call hit a limit." Why: it did not say, next to the results, that those expectations were written with both round-1 reviews and the reviewers' scripts known; now it does.
2. Rotary section, the factor: "That is an expectation from reading only; other tests on the way to the table could still refuse such a file." Why: both round-2 reviewers report reaching main's 2^26; added as their report, the PR's own statement unchanged.
3. Weaker-than-registered item 7, which ended: "and `query width: 5 files with H * dh != d, 5 not refused shape-heads`. That count is harness coverage: it shows the walk hands the verifier unequal-width files that pass the new test. It is no result about a plan or a proof. The walk's usual length and the sanitized walk were not run." Why: the counter behind that line counted files refused before the test. It now fails closed; the recorded count on the registered smoke is unchanged at 5 of 5, and the counter's meaning is corrected.
4. Item 11: "That `run_suite.py` reads and runs the two rows is **not verified**." Why: the reviewers' runner runs are cited as their report, and the new row is named.
5. Header: "with Amendments 1 to 4 (each committed before the runs it covers; Amendment 4 was written after two reviews, by a fix lane)." Why: Amendment 5 exists.

Still open, unchanged: as listed under the round-1 corrections above. Also not done here: a follow-up for the pre-existing `place()` allocation and an optional rotary guard or caller resource budget, which both round-2 reviewers suggest; that is the coordinator's decision.
