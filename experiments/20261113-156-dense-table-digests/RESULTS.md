# RESULTS: 20261113-156-dense-table-digests

Issue #156. PREREG: `PREREG.md` (first commit, alone, db6b0601). Environment: `ENV.json`. All numbers
here are measured, unreplicated: one lane, one host, one floating-point library.

## Verdict

**PASS** against the pre-registered threshold. No amendment was made to the PREREG. Deviations are
listed below; one of them is a debug run that the PREREG did not allow.

In one paragraph: `cp_verify` now admits the 32 digest lines of the public tables in a parameter file
without experts (`NE 0`), asks the eight sigmoid lines to be 0, compares the other 24 with the SiLU,
rotary and softmax tables that it computes itself, and no longer counts `table-digests` as met for a
dense file without the lines. Every result for a file with experts is what it is on main.

## What changed

- `verifier/src/cp_verify.cpp`: the test after the scan that refused all digest lines at `NE 0` now
  refuses only a nonzero word in `tsig0` .. `tsig7`; `dense` no longer asks for the lines to be absent;
  the argument of `table-digests` is `tblAt == TBLW` for every file (PR #145's `|| dense` is gone); the
  planning call prints a line of its own for a dense file with lines. The scan of the lines and the
  three comparisons (`table-digest-silu`, `-rope`, `-exp`) are not changed: they already ran for every
  model and compared whenever the lines were there. No new refusal name, no statement word, no hash.
- `scales/policy_tables.py`: for `NE 0` it writes the three digests and eight lines `tsig<i> 0`.
- `verifier/tests/served_form_test.py`: `dense` now expects `not met: table-digests`,
  `dense-with-digests` expects met, and nine dense refusal cases are new.
- `scales/tests/test_policy_tables.py`: one new test, two rows of the rejection test removed (the tool
  no longer rejects `NE 0`); `SUITE.md` row `scales.policy_tables` counts 23 tests, not 22.
- Docs: `verifier/docs/parameter-file.md`, `docs/format/FORMAT.md` (12.3, the sigmoid row of 12.6, 13.7
  condition 10 and the row `routed-experts`, the row `policy-tables` of 13.8), `docs/qwen-port.md` open
  risk 6, `verifier/docs/plan-data.md`.
- Not changed: `prover/` (so `cp_commit`, `cp_prove` and their reader of the parameter file),
  `blocks/`, `integrations/`, `lean/`, `examples/` (`git diff --stat` against the base names no file
  under them).

## Results against each registered item

### 1. Served-form planning cases (5 runs per tree, alternating main, head)

`runs/served/` (`table.md` is the full before/after table, `main-1..5.log`, `head-1..5.log`).
Every one of the 10 runs ended `all as expected` with status 0, and the 5 runs of each tree printed
the same case lines.

| | main | head |
|---|---|---|
| cases | 47 | 56 |
| same result on main and head | | 45 of 47 |
| changed, both registered to change | | `dense`, `dense-with-digests` |
| new cases, all refusals | | 9 |

The 14 cases of the group `routed-experts` on head, all as registered:

| case | main | head |
|---|---|---|
| `dense` (no digest lines) | met | status 4, `not met: table-digests` and no other condition |
| `dense-with-digests` (the lines `policy_tables.py` computes) | on main this name was the dense file with the kit's lines: `NO: policy-tables` | status 4, met |
| `dense-with-sigmoid-digest` (the kit's own 32 lines) | (new) | `NO: policy-tables` |
| `dense-sigmoid-one-bit` (`tsig7 1`) | (new) | `NO: policy-tables` |
| `dense-partial-digests` (24 lines, no `tsig`) | (new) | `NO: policy-tables` |
| `dense-silu-altered` (one bit of a digest word) | (new) | `NO: table-digest-silu` |
| `dense-rope-altered` | (new) | `NO: table-digest-rope` |
| `dense-exp-altered` | (new) | `NO: table-digest-exp` |
| `dense-silu-table-moved` (`eg 7`, lines kept) | (new) | `NO: table-digest-silu` |
| `dense-rope-table-moved` (`theta0_lo 500000`, lines kept) | (new) | `NO: table-digest-rope` |
| `dense-exp-table-moved` (`rx 7`, lines kept) | (new) | `NO: table-digest-exp` |
| `dense-with-gcl` | `NO: policy-gcl` | `NO: policy-gcl` |
| `dense-with-rcl` | `NO: policy-rcl` | `NO: policy-rcl` |
| `NE-0` (NE 0 and nothing else) | `NO: header-absent-class` | `NO: header-absent-class` |

No "table-moved" case was refused under another name than the registered one.

`table-digests.no-lines` (a file with experts and no lines) is `not met: table-digests` on both, and the
four `table-digests.*-altered` cases with experts keep their names.

### 2. The same dense files under both binaries (one run each)

`runs/served/dense-files.tsv`; the 14 parameter files are in `runs/served/dense-files/`, with the
SHA-256 of all three files of each case in `sha256.tsv`.

- Main binary: `dense` is met; `dense-with-gcl`, `dense-with-rcl` and `NE-0` end with their own names;
  each of the other 10 files, which have digest lines, ends `NO: policy-tables`. As registered. So on
  the same bytes main refuses every dense file that states a digest, right or wrong.
- Head binary: as in the table above.
- `configuration=` for `dense` is `cc0907c9...`, under both binaries. For `dense-with-digests` on head
  it is `650e0b24...`: different, as registered. The statement line is `177 words, y at word 171` for
  both. The planning call on `dense-with-digests` prints `plan: this program's three public tables of a
  model without experts (SiLU, rotary, softmax) match the parameter file's digests (lines tsilu0 ..
  texp7); the sigmoid's lines are 0`.

### 3. Stored-proof calls (5 rounds per binary, alternating; 120 runs)

`runs/compare/` (`summary.json`, `runs.tsv`, `n2-touched.txt`, `raw-round0/`). PR #145's `compare2.py`,
unchanged.

**12 of 12 calls: one exit status, one last line and one SHA-256 after normalisation N2 over all 10
runs of both binaries. 0 differ.** The four sets are `full-size`, `full-size-clipped-gap`,
`accepted-proof`, `accepted-proof-clipped-gap`; the calls are the whole call, the whole call with `-q`,
and `-plan request`. Last lines: `YES` (4 calls), `WITHIN LIMITS: clipped-gap ...` (4), `PLAN ONLY`
(4). `n2-touched.txt` lists every line shape that N2 masked or removed: wall times only. The 12 N2
hashes are also the ones PR #145 recorded for its head (same sources as this main).

These are stored example proofs on synthetic weights. This is not a statement about any served model.

### 4. The table tool

`runs/tool/`. `scales/policy_tables.py` of both trees on the 9 parameter files under `prover/examples/`
and `prover/tests/configurations/` (all have `NE` above 0), in its three modes: **27 of 27 runs give the
same exit status, standard output and standard error on main and head.** On the dense file with its
lines main's tool rejects (status 2) and head's prints it unchanged and passes `--check`, as registered.

`scales/tests/test_policy_tables.py` (23 tests) and `scales/tests/table_ties.py` (26 checks) pass on
head, as suite rows (item 5).

### 5. Suite rows (once per tree)

`runs/suite/main.log`, `head.log`. The registered expression chose 15 rows on each tree. **15 of 15
passed on main and 15 of 15 on head; 0 failed, 0 not run.** One row was left out by the runner on both
trees: `verifier.served.form.world.kit` needs nvcc or a GPU. Among the 15: `verifier.served.form`,
`verifier.extreme_files` (2,141 calls on 2,073 files), `verifier.record_altered_sets.full` and
`.example`, `verifier.commitment_id.examples`, `verifier.call_accounting.examples`,
`verifier.example_kits`, `scales.policy_tables`, `scales.table_ties`.

### 6. Secondary: verifiers whose own table differs in one entry (not part of PASS)

`runs/mutants/`, patches in `mutants/`. Three builds of the head sources, each with one entry of one
table moved by 1 (SiLU table index 33024, which is key 256; the cosine of pair 1 at position 3;
softmax entry 5). This stands in
for a verifier whose floating-point library rounds one entry differently from the provider's. All four
binaries got the unmodified files of `dense-with-digests` (SHA-256 checked against item 2):

| binary | `dense-with-digests` | `dense` (no lines; reported, not registered) |
|---|---|---|
| head, unmutated | met | `not met: table-digests` |
| SiLU table mutated | `NO: table-digest-silu` | `not met: table-digests` |
| rotary table mutated | `NO: table-digest-rope` | `not met: table-digests` |
| softmax table mutated | `NO: table-digest-exp` | `not met: table-digests` |

As registered. The right-hand column shows why the lines are needed: without them a verifier with a
different table has nothing to compare against, and since this change it at least cannot accept.

## What is established

- A dense parameter file can state the digests of its SiLU, rotary and softmax tables, and `cp_verify`
  compares them: a wrong digest word, a table moved under an unchanged digest, and a verifier whose own
  table differs in one entry are each refused under the table's own name, in a planning call.
- A dense file without the lines, with 24 of them, or with a nonzero sigmoid word cannot meet the
  standard parameter form (not met, or `NO: policy-tables`).
- The digests that the independent Python tool computes for the dense file are the ones the verifier
  computes (this is what `dense-with-digests` being met means): two implementations, one platform library.
- For files with experts nothing moved in what was run: 45 of 47 served-form cases, 12 of 12
  stored-proof calls over 120 runs, 27 of 27 tool runs, 15 of 15 suite rows on both trees.

## What is NOT established

- **No dense proof exists, so no dense `YES` was seen and no whole call on a dense file was made.**
  Every dense result here is from a planning call (`-plan request`). The comparisons sit in the code
  that a whole call runs too, and the stored proofs with experts exercise that code in whole calls, but
  a whole call under a dense file has not been run.
- **The provers are not changed and were not built.** By reading the source, not by a run:
  `prover/common/parameter_file.h` still refuses digest lines without experts (`policy-tables`), and
  `cp_commit` asks `cp_verify -plan` whether the files can be a verification and refuses at 128 bits if
  not (`cp-commit-not-standard`). So after this change `cp_commit` should refuse a dense file both with
  the lines (its own reader) and without them (the verifier's plan), until the provers' reader follows
  the verifier's rule. Before this change a dense file without lines would have passed that plan check.
  This lane ran neither case. It is the next step for a dense commit and prove path and it is not done.
- That a prover used the tables that the lines name. With experts `cp_prove` compares its own tables
  with the lines; without experts it cannot read the lines yet.
- Agreement between two real floating-point libraries. One library was used. The mutant builds change
  one entry by hand; they do not show which entries, if any, differ between real libraries. For the
  SiLU table there is still no tie check like `scales/tests/table_ties.py` has for the softmax and
  rotary tables: the digest lines now make a difference detectable, they do not make it impossible.
- That the commitment ID changes with the lines was not measured as an ID. Measured: the printed
  `configuration=` digest differs between the dense file with and without lines. That the ID covers
  that digest is the format's rule (`docs/format/FORMAT.md`, 13.5 and R4.11), which this lane read and
  did not test.
- Nothing about Qwen's own tables (the partial rotary table, the decay tables of #136, the norm tables
  of #148) or the other limits of #35.
- No Lean file and no part of the soundness argument was changed or re-checked.
- 158 of the 173 rows of `SUITE.md` were not run, among them every GPU row and the tests of the
  provers' parameter-file reader.
- **A second caller of the table tool changes behaviour and was not tested** (found after the runs,
  by reading; added to this file after its first commit). `scales/words_to_policy.py` calls
  `policy_tables.digests()` when its base parameter file has digest lines. For a base file with `NE 0`
  and digest lines, main's converter ends with `input-policy-tables` (status 20) because `digests()`
  raised; on this branch `digests()` returns, so the converter should go on and write the dense lines.
  For `NE` above 0 the function's result is unchanged (item 4 covers the tool, not the converter). No
  row of `SUITE.md` names the converter, and this lane ran no test of it.
- `integrations/vllm/integer_model/integer_model/parameters.py` refuses `NE 0` with a message that says
  such a file "cannot carry the digests of the public tables". That sentence is now out of date for the
  verifier. It was left as it is (outside the scope; the package still requires experts).

## Deviations from the PREREG

1. **A debug run that the PREREG did not allow.** Before the registered runs I ran
   `scales/tests/test_policy_tables.py` once on the edited tree to try the new test (23 tests, OK). The
   PREREG allowed debug runs of planning calls and of `served_form_test.py` on the configuration
   `pinned` only, and that test is a registered suite row (`scales.policy_tables`, metric 4). It passed
   at the first run and no file was changed after it, so no result was fitted to it; it is still a
   run of a registered check before its registered run.
2. The allowed debug runs, for the record: one `served_form_test.py --condition routed-experts` on
   `pinned` with the head binary (14 cases, all as expected at the first run) and three single planning
   calls on its files (two with the head binary, one with the main binary). These three calls were
   not pinned to cores 12 to 15, against the PREREG's "every build and run"; each took under a second.
3. The PREREG says the head binary is built "from the branch head". The head binary and the head tree
   of items 1, 2, 4 and 6 are the code commit 90a29888. The suite's head tree (item 5) is the later
   commit 0c48f942, which adds docs and this folder's runners and changes no file under
   `verifier/src`, `verifier/tests`, `scales` or `SUITE.md`; its build printed the head build word.
   No run was made at the final head of the branch, which adds only files of this folder, docs and the
   results ledger.
4. `runs/compare/` holds the raw outputs of round 0 only (24 files); rounds 1 to 4 are not committed.
   Their SHA-256, raw and normalised, are in `runs.tsv`.
5. The suite logs are committed with the work folder written as `<WORK>` and the tree as `<REPO>`,
   as PR #145 did. Nothing else in them was changed.
6. Builds and the suite ran outside the clone, in folders of mode 700: `verifier/build.sh` and
   `run_suite.py` refuse a place below a group-writable folder, which the clone's parent is.

## Run counts

Served-form test: 5 runs per tree. Stored-proof calls: 5 rounds per binary (10 runs per call). Dense
files under both binaries, the tool comparison, the suite and the mutant runs: one run each. All are
verdict checks on deterministic programs; no timing is reported and no claim rests on a spread.

## Reproduce

From the repository's top, with a `cp_verify` built by `verifier/build.sh` from main (`$M`, in a tree
`$MT`) and from this branch (`$H`, tree `$HT`), each in a folder of your own:

```
python3 -B experiments/20261113-156-dense-table-digests/served_runs.py $M $MT $H $HT $OUT/served
python3 -B experiments/20261113-156-dense-table-digests/tool_identity.py $MT $HT $OUT/served/dense-files/routed-experts.dense-with-digests.policy.txt $OUT/tool
python3 -B experiments/20261112-135-dense-standard-form/compare2.py $M $H . $OUT/compare
python3 run_suite.py cpu <new work folder> --only '<the expression in PREREG.md, Runs>' --jobs 4
```

`$OUT` is a folder of your own that exists; each script makes its own new folder in it. The suite
line is run once in each tree. The runs here were pinned with `taskset -c 12-15`.

For item 6: `git apply experiments/20261113-156-dense-table-digests/mutants/<table>.patch` in a copy
of the tree, build, revert, and then `mutant_runs.py` (its head says how).
