# 20261113-156-dense-table-digests

Issue #156. Start with `RESULTS.md` (verdict, numbers, what is not established, deviations).
`PREREG.md` was committed first, alone, and was not amended. `ENV.json` has the commits, the build
words and the host.

## In plain words

`cp_verify` computes a few lookup tables with floating-point functions (SiLU, rotary positions,
softmax exponentials, and for models with routed experts a sigmoid). Two machines whose math
libraries round one entry differently would compute different tables. For models with experts the
parameter file therefore states a digest of each table, and the verifier refuses if its own table
has another digest.

A parameter file without experts (`NE 0`, "dense") could not state those digests: the verifier
refused the lines. This change lets a dense file state them and makes them required:

- the lines for the SiLU, rotary and softmax tables are compared with the verifier's own tables;
- the eight sigmoid lines must be 0, because a dense model has no sigmoid table;
- a dense file without the lines can no longer meet the standard parameter form, so no call under
  it can end with an acceptance.

For files with experts the rule is unchanged, and nothing moved in what was run (`RESULTS.md` says
what was run and what was not).

## What the verifier recomputes

The three tables, from the parameter file's numbers and the platform's `exp`, `pow`, `cos`, `sin`,
and their digests. It compares each digest with the file's lines before it uses a word of a proof.

## What is not covered

- No proof without experts exists. Every dense result here comes from a planning call
  (`cp_verify -plan request`), which reads no proof. No dense acceptance was seen.
- The provers (`cp_commit`, `cp_prove`) were not changed and not built. Their reader of the
  parameter file still refuses the lines without experts.
- One math library was used. The "mutant" builds move one table entry by hand to stand in for a
  second library.
- No Lean file and no part of the soundness argument was touched.

`RESULTS.md`, "What is NOT established", has the full list.

## Files

| file | what it is |
|---|---|
| `served_runs.py` | runs the served-form test 5 times per tree, compares main and head with the registered results, and gives the dense case files to both binaries |
| `tool_identity.py` | checks that `scales/policy_tables.py` prints the same bytes on main and head for every parameter file with experts |
| `mutant_runs.py`, `mutants/*.patch` | the secondary check: verifiers whose own table differs in one entry. The patches are never applied to the branch |
| `runs/served/` | logs of the 10 served-form runs, the before/after table, the dense files and their hashes |
| `runs/compare/` | the stored-proof comparison (PR #145's `compare2.py`, unchanged) |
| `runs/tool/`, `runs/suite/`, `runs/mutants/` | the tool comparison, the two suite logs, the mutant runs |

## Reproduce

The exact commands are in `RESULTS.md`, "Reproduce". They need two builds of `cp_verify`
(`verifier/build.sh`, from main and from this branch), each in a folder of your own, about two
minutes each on one core, no GPU and no model weights.
