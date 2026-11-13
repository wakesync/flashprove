# PREREG: 20261113-156-dense-table-digests

Issue: #156 (part of #35, follows #135 and PR #145, tracking #32). Lane: digest156. Date (UTC): 2026-11-13 01:35. Base commit: 17d216d4f81d3e5ecc6011a2fa2c698b8993bf55 (main).

Scope: the bounded milestone of #156 only. A dense parameter file (`NE 0`) may carry the 32 lines of the
public tables' digests, and must carry them to meet the standard parameter form. No dense proof is made
or checked (none exists). No new table (not Qwen's partial rotary table, not the decay tables of #136,
not the norm tables of #148). No other #35 limit. No change to `cp_commit`, `cp_prove` or their parser
(`prover/common/parameter_file.h`). No change to the Lean model or to the soundness argument.

## Hypothesis

`cp_verify` can admit the 32 digest lines at `NE 0` under the rule below, and require them for the
condition `table-digests` of a dense file, such that (a) a dense file with the right lines meets the
standard parameter form, (b) a dense file without lines, with a part of the lines, with a nonzero
sigmoid word, or with a SiLU, rotary or softmax digest that is not the digest of the table that the
verifier computes is not accepted, each with the registered name, and (c) for every file with `NE` above 0
every served-form result and every registered stored-proof call gives the same exit status, the same last
line and the same normalised output as on main.

### The exact rule change registered

Parser (`verifier/src/cp_verify.cpp`):

1. The scan of the digest lines (`polScan`) is not changed: the lines are all 32 or none, directly behind
   one another, in the order `tsilu0..7`, `tsig0..7`, `trope0..7`, `texp0..7`, before the first call line,
   one word each (`policy-tables` otherwise). So a dense file states its digests in the same 32 lines and
   the same position as a file with experts.
2. The test after the scan (`polLayout`), on main `if (PS.tblAt && !h.NE) refuse("policy-tables")`, becomes:
   at `NE 0` with the lines present, each of the eight words `tsig0` .. `tsig7` must be 0; a nonzero word
   ends `NO: policy-tables`. Reason for 0 and not "absent": at `NE 0` the verifier forms no sigmoid table
   and writes eight zero words at the sigmoid digest's place in the statement, so with this rule the
   file's 32 lines are, word for word, the 32 words that the verifier writes into the statement, with and
   without experts, and the all-or-none rule of the scan stays one rule.
3. The three comparisons `tblHeld(0, .., "table-digest-silu")`, `tblHeld(2, .., "table-digest-rope")` and
   `tblHeld(3, .., "table-digest-exp")` are not changed. They already run for every model and compare
   whenever the lines are present, so at `NE 0` they now compare the dense file's lines with the
   verifier's own SiLU, rotary and softmax tables and refuse before a word of a proof is used.
   `tblHeld(1, ..)` stays inside the branch for experts.

Standard form (the arguments of `servedForm()` in the request stage):

| term | main (after PR #145) | head |
|---|---|---|
| `dense` | `h.NE == 0 && !RCL && !GCL && tblAt == 0` | `h.NE == 0 && !RCL && !GCL` |
| `routed-experts` | `h.NE > 0 \|\| dense` | the same expression |
| `both-clamps` | `(RCL && GCL) \|\| dense` | the same expression |
| `table-digests` | `tblAt == TBLW \|\| dense` | `tblAt == TBLW` |

For `NE` above 0, `dense` is false on main and on head, so all three arguments are main's, term for term.
For `NE 0`: `routed-experts` and `both-clamps` are met as after PR #145 (now also with lines);
`table-digests` is met only with the 32 lines, so PR #145's waiver is withdrawn.

One printed line: the planning call's line `plan: this program's four public tables match the parameter
file's digests (lines tsilu0 .. texp7)` is printed unchanged for `NE` above 0. For a dense file with lines
it is replaced by a line of its own wording that says three tables and that the sigmoid lines are 0 (a
dense model has no fourth table to match). No other output line, statement word, hash, plan or accounting
line changes. No new refusal name: `verifier/src/vf_rejection_names.txt` is not changed.

Tool (`scales/policy_tables.py`): for a file with `prof 20` and `NE 0` it computes the SiLU, rotary and
softmax digests as for `NE` above 0 and writes eight lines `tsig<i> 0`; `--check` compares against those.
For `NE` above 0 its output is byte for byte what it is on main. It still shares no code with the verifier.

Docs, only where they state the rule: `verifier/docs/parameter-file.md` (table 9, "Digests of the public
tables", "A dense file"), `docs/format/FORMAT.md` (12.3, 13.7 condition 10 and the row `routed-experts`,
the rows `policy-tables` and of the sigmoid digest), `docs/qwen-port.md` open risk 6 (narrowed, not
closed), the head comment of `verifier/tests/served_form_test.py`, the docstring of `policy_tables.py`.

## Metric

1. Served-form planning cases (`verifier/tests/served_form_test.py` on
   `prover/tests/configurations/pinned_no_proof_of_work`): for each case the planning call's exit status
   and its refusal name or list of unmet conditions. Main: main's test file with the main binary (47
   cases). Head: the branch's test file with the head binary (the 47 plus the new dense cases).
2. The dense case files under both binaries: each dense case's three files, as the head test wrote them,
   given to the main binary and to the head binary by the same planning call; exit status and refusal or
   unmet list, and for the cases that are not refused the printed `configuration=` and statement length.
3. Stored-proof calls: the 12 calls of PR #145's `experiments/20261112-135-dense-standard-form/compare.py`
   (four stored sets, three calls each), run by that folder's `compare2.py` unchanged: exit status, last
   line, SHA-256 after its normalisation N2 (build word and wall times masked; `n2-touched.txt` lists
   every line shape touched).
4. `scales/tests/test_policy_tables.py` and `scales/tests/table_ties.py` on head: pass or fail.
5. Verifier suite rows: pass or fail per row of `run_suite.py cpu --only <expression below>`, main vs head.
6. Secondary, mutated-table builds (run only under the time condition in Runs): a build of the head
   sources with a committed patch that changes one entry of one table the verifier computes (one build
   per table: SiLU, rotary, softmax), run by the planning call on the unmodified `dense-with-digests`
   files; exit status and refusal name. This models a verifier whose floating-point library gives
   another table than the provider's.

## Acceptance threshold

PASS if and only if all of these hold on head.

Dense cases (all in the group `routed-experts`; "the dense file" is main's case `dense`: `NE 0`, no
router, no experts' weight kinds, no clamps, layout made again):

| case | files | registered result |
|---|---|---|
| `dense` | the dense file, no digest lines | status 4, `not met: table-digests` and no other condition |
| `dense-with-digests` | the dense file with the 32 lines that `policy_tables.py` computes for it (sigmoid words 0) | status 4, met (no line `plan: not the standard parameter form`, both one-time-files lines) |
| `dense-with-sigmoid-digest` | the dense file with the kit's own 32 lines (its sigmoid digest is not 0; these are the files of main's `dense-with-digests`) | `NO: policy-tables` |
| `dense-sigmoid-one-bit` | `dense-with-digests` with `tsig7 1` | `NO: policy-tables` |
| `dense-partial-digests` | `dense-with-digests` without the eight `tsig` lines (24 lines) | `NO: policy-tables` |
| `dense-silu-altered` | `dense-with-digests` with one bit of the last SiLU word flipped | `NO: table-digest-silu` |
| `dense-rope-altered` | the same for a rotary word | `NO: table-digest-rope` |
| `dense-exp-altered` | the same for the last softmax word | `NO: table-digest-exp` |
| `dense-silu-table-moved` | `dense-with-digests` with a line `eg 7` added and the digest lines kept (the SiLU table changes, its stated digest does not) | `NO: table-digest-silu` |
| `dense-rope-table-moved` | `dense-with-digests` with `theta0_lo` set to the other value that `rotary-table` allows, digest lines kept | `NO: table-digest-rope` |
| `dense-exp-table-moved` | `dense-with-digests` with `rx 7`, digest lines kept | `NO: table-digest-exp` |
| `dense-with-gcl`, `dense-with-rcl`, `NE-0` | as on main | `NO: policy-gcl`, `NO: policy-rcl`, `NO: header-absent-class`, as on main |

If a "table-moved" case is refused under another name because another test on the moved value runs
first, that is reported as it is and the case counts as failed for this threshold (it is still a
refusal, and RESULTS says which name).

Everything else:

- every served-form case other than `dense` and `dense-with-digests` that exists on main: the same
  status and the same result on head as on main (45 of 47; `table-digests.no-lines`, a file with experts
  and no lines, still `not met: table-digests`);
- under the main binary the files of `dense-with-digests` and of every other dense case with lines end
  `NO: policy-tables`, and the files of `dense` are met (this is main's behaviour, shown on the same bytes);
- the `configuration=` printed for `dense-with-digests` differs from the one printed for `dense` (the
  lines are bytes of the parameter file, which the configuration digest and so the commitment ID cover),
  and the statement length is the same;
- every registered stored-proof call: same exit status, same last line, same N2 SHA-256 on head as on
  main, in all runs;
- `policy_tables.py` on every parameter file under `prover/examples/` and `prover/tests/configurations/`
  that has `NE` above 0 prints the same bytes on head as on main; `test_policy_tables.py` and
  `table_ties.py` pass;
- every registered suite row that passes on main passes on head.

Secondary (reported separately, not part of PASS): each mutated-table build refuses the unmodified
`dense-with-digests` files with `table-digest-silu`, `table-digest-rope`, `table-digest-exp` for its
table, and the unmutated head binary accepts them.

## Kill criterion

- Immediate stop and FAIL, per #156: any stored-proof call with a different exit status, last line or N2
  hash; any served-form case with `NE` above 0 whose result changes; a dense file with an altered SiLU,
  rotary or softmax digest, a nonzero sigmoid word or a part of the lines that is not refused. Report
  which rule couples the two.
- Stop and report a negative if the lines cannot be admitted at `NE 0` by the registered rule alone (for
  example because the statement layout or a hash ties the sigmoid digest to the router in a way that
  needs a statement or hash change).
- Hard stop for the lane: 2026-11-13T03:55:00Z wall clock. Run budget: the registered runs end by
  03:30Z; what is not run by then is reported as not run, and the verdict is given on what ran.

## Runs

- CPU only, no model weights, no GPU. Every build and run pinned to cores 12 to 15 (`taskset -c 12-15`),
  on a shared host loaded by other lanes. The host's heavy-job gate is not used: the lane's task rules
  say build and test only, no heavy slot; ENV.json records this.
- Two binaries: `cp_verify` built by `verifier/build.sh` from main at the base commit and from the branch
  head.
- Served-form test: 5 runs per tree (main's test file with the main binary; the branch's with the head
  binary), each in a new folder. These are verdict checks, not performance measurements; the 5 runs must
  print the same case lines.
- Dense case files under both binaries: one run each (deterministic planning calls), files kept.
- Stored-proof calls: `compare2.py`, 5 rounds per binary, alternating main, head (120 runs).
- Suite: `./run_suite.py cpu <work> --only '^(build\.verifier|verifier\.served|verifier\.call_accounting|verifier\.commitment_id|verifier\.record_altered_sets\.(example|full)|verifier\.example_kits|verifier\.extreme_files$|verifier\.plan_tau|verifier\.kit_rounds|scales\.policy_tables|scales\.table_ties)' --jobs 4`,
  once per tree, after the runs above. Rows that the runner leaves out on this host are listed as not run.
- Secondary, mutated-table builds: only if every run above has finished before 03:10Z. Otherwise not run
  and reported so.
- Debug of the new code and of the new test cases, before the registered runs: planning calls and
  `served_form_test.py` on `prover/tests/configurations/pinned` or `pinned_no_proof_of_work_roomy` only,
  which the registered runs do not use. `served_form_test.py` is not run on
  `pinned_no_proof_of_work`, and no stored-proof call is run, before its registered run.
- Seeds: none; no run draws randomness.
- Excluded: nothing. A run that fails for a reason outside the change (host, missing tool) is listed with
  its log.

## Prior art

- In the repository: table pinning by digests is the format's own answer to drift between floating-point
  libraries (`docs/format/FORMAT.md` R15.3 and 12.6, `verifier/HASHES.md`, `scales/policy_tables.py`,
  `scales/tests/table_ties.py`). PR #145 (`experiments/20261112-135-dense-standard-form/`) admitted a
  dense file to the standard form and disclosed that its SiLU, rotary and softmax tables are then not
  pinned by lines that the commitment ID covers. This lane extends the existing digest lines to `NE 0`;
  it adds no mechanism.
- Outside, from general knowledge of the designs and not from a literature search made for this lane: in
  zkML systems that prove inference with lookup arguments (zkLLM's tlookup, arXiv:2404.16109; EZKL on
  Halo2 lookups; Jolt and Expander based provers; DeepProve) the lookup tables are public inputs of the
  circuit or part of its fixed description, so prover and verifier agree on them through the verifying
  key or the circuit description, not through a separate digest line. The question of two libraries
  rounding a table entry differently is the table maker's dilemma (Lefèvre, Muller, Tisserand, RR-1998-12,
  cited in `scales/policy_tables.py`). TEE systems (H100 confidential computing, TDX, SEV-SNP based
  services) attest a software image and have no counterpart of a table digest in a statement.
- What is new here: nothing outside this repository. Inside it: the rule for the sigmoid words at `NE 0`,
  the dense negative cases, and the evidence that files with experts are untouched.

## Amendments

