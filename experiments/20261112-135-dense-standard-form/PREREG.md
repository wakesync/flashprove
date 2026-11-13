# PREREG: 20261112-135-dense-standard-form

Issue: #135 (part of #35, tracking #32). Lane: dense135. Date (UTC): 2026-11-12 21:10. Base commit: c810b3e998c45c14fc0c422cf3cb69ec72ab47df (main).

Scope: milestone items 1 to 4 of #135 only. No other #35 limit (query width, head dimension 256,
rotary, q/k norm, sigmoid gate, hybrid schedule, segment cap). No dense proof is made or checked.
No change to the Lean model or to the soundness argument.

## Hypothesis

A change confined to the arguments that `cp_verify` passes to `servedForm()` (verifier/src/cp_verify.cpp,
the `notServed` expression of the request stage) lets the served-form test's case `routed-experts.dense`
(NE 0, no router, no expert weight kinds, no clamps, no digest lines, layout made again) meet the
standard parameter form, while (a) the cases `dense-with-digests`, `dense-with-gcl`, `dense-with-rcl` and
`NE-0` still refuse with `policy-tables`, `policy-gcl`, `policy-rcl` and `header-absent-class`, (b) every
other served-form case gives the result it gives on main, and (c) every registered call on the stored
proofs gives the same exit status, the same last line and the same output bytes as on main, apart from
the source digest after `build=`.

### The exact change registered

Let `dense` be `h.NE == 0 && !RCL && !GCL && tblAt == 0`. In the `servedForm({...})` call of the request
stage, and nowhere else:

| condition | main | head |
|---|---|---|
| `routed-experts` | `h.NE > 0` | `h.NE > 0 \|\| dense` |
| `both-clamps` | `RCL && GCL` | `(RCL && GCL) \|\| dense` |
| `table-digests` | `tblAt == TBLW` | `tblAt == TBLW \|\| dense` |

For NE above 0, `dense` is false and the three booleans are those of main, term for term. No parser rule,
refusal, shape test, statement word, hash, plan or accounting line changes. The refusals that already
make NE 0 imply no router digit form (`header-absent-class`), no expert weight kinds (`header-absent-kind`),
no `rcl`/`gcl` (`policy-rcl`, `policy-gcl`) and no digest lines (`policy-tables`) stay as they are; `dense`
restates the last three so the standard form does not depend on their order.

Docs touched only where they state the condition: verifier/docs/parameter-file.md (table of the standard
form), docs/format/FORMAT.md (12.3 and the list in 14.x of the standard form), docs/qwen-port.md open risk 6
(narrowed, not closed), the served-form test's head comment and its expectation for `dense`.

### Per removed condition: why vacuous at NE 0, registered before code

- `routed-experts`: at NE 0 there is no router and no routed expert, so there is nothing for the condition to
  require; the parser already refuses every expert class digit form and every expert weight kind at NE 0.
- `both-clamps`: `rcl` clamps the router's logits and `gcl` the key of the gate table read through the router
  sigmoid's table. Both are refused at NE 0 (`policy-rcl`, `policy-gcl`); with no router there is no router
  logit, and `gcl` is defined only with experts. Prediction: vacuous for `rcl`. For `gcl`, RESULTS must say
  whether a dense layer's SiLU key can leave 16 bits without the clamp (then a prompt has no proof; the
  parameter file's own text says `gcl` does not change the proved function, only which prompts have a proof).
- `table-digests`: **predicted NOT vacuous.** Of the four public tables only the sigmoid table (tsig) is
  MoE-only (its statement words are 0 at NE 0). The SiLU, rotary and softmax tables are used by a dense model
  too. At NE 0 the parser refuses all 32 lines, so on head a dense YES pins those three tables only by the
  verifier's own floating-point computation, which it writes into the statement (bound into the first
  chain's first query), and not by lines covered by the commitment ID. RESULTS must state this as a
  disclosed weakening of what a dense YES says compared with a Maverick YES, not as vacuous. The stronger
  form (digest lines at NE 0 with tsig 0) changes a parser rule and the policy_tables tool, and is out of
  this milestone.

## Metric

1. Served-form planning cases: for each of the 47 cases listed by `served_form_test.py --list` on
   `prover/tests/configurations/pinned_no_proof_of_work`, the planning call's exit status, its refusal
   name or its list of unmet conditions; main binary vs head binary, same case files.
2. Stored-proof calls (registered list below): exit status, last line, and the SHA-256 of stdout+stderr
   after normalisation N; main vs head.
3. Verifier suite rows: pass/fail per row of `run_suite.py cpu --only <regex below>`; main vs head.

Normalisation N (the only one): the 64 hex digits after every `build=` are replaced by `<build>`, and lines
that begin `seconds:` are removed (wall times). Nothing else is changed before hashing.

### Registered list of stored-proof calls (Maverick-shaped and the small kits)

For each D in `examples/full-size`, `examples/full-size-clipped-gap`, `examples/accepted-proof`,
`examples/accepted-proof-clipped-gap`:
- the whole call `cp_verify D/config D/ivk D/example.req D/example.y D/example.proof -id $(cat D/ID.txt)`,
  with `-policy` as its README gives it for the two clipped-gap sets;
- the same call with `-q`;
- `cp_verify -plan request D/config/policy.txt D/config/KL.bin 128 -layout D/config/layout.txt -prompt D/example.req -reply D/example.y -q`
  (the planning call on the same files; if its argument form differs, the form `served_form_test.py` uses).
Plus `served_form_test.py` in full (both binaries) and `--list`.

The full-size set is the Llama 4 Maverick shape (48 layers, 128 routed experts, synthetic weights). No
Maverick proof on Meta's weights is stored in the repository, so none is in the list.

## Acceptance threshold

PASS if and only if all hold:
- `routed-experts.dense` on head: status 4, no line `plan: not the standard parameter form`, both
  one-time-files lines present (the test's "met" rule).
- `dense-with-digests` -> `policy-tables`, `dense-with-gcl` -> `policy-gcl`, `dense-with-rcl` -> `policy-rcl`,
  `NE-0` -> `header-absent-class`, on head, as on main.
- every other served-form case: same status and same result on head as on main (46 of 47 identical, the 47th
  is `dense`).
- every registered stored-proof call: same exit status, same last line, same normalised SHA-256 on head as on
  main.
- every registered suite row that passes on main passes on head (served-form row with the updated
  expectation).

## Kill criterion

- Immediate stop and FAIL: any stored-proof call with a different exit status, last line or normalised hash;
  any served-form case other than `dense` whose result changes; any refused dense variant that passes.
  Report which condition couples the two.
- Stop and report a negative if the dense case cannot be admitted by the registered change alone (it needs
  a parser, shape, statement or hash change).
- Hard stop for the lane: 2026-11-12T23:20:00Z wall clock, queue time included. Run budget: the main-vs-head
  runs end within 60 minutes of the first run's start (logged); what is not run by then is reported as not run.

## Runs

- CPU only, no model weights. Every build and run through the host's heavy-job gate, pinned to 4 cores.
- Two binaries: `cp_verify` built by `verifier/build.sh` from main at the base commit (a worktree of the same
  clone) and from the branch head.
- Each stored-proof call: 2 runs per binary (ordering main, head, main, head). If the two runs of one binary
  differ after N, repeat that call 5 times per binary and report the spread; otherwise determinism is stated
  with the hashes. These are verdict and byte checks, not performance measurements: no timing is claimed.
- Suite: `./run_suite.py cpu <work> --only '^(build\.verifier|verifier\.served|verifier\.call_accounting|verifier\.commitment_id|verifier\.record_altered_sets\.(example|full)|verifier\.example_kits|verifier\.extreme_files$|verifier\.plan_tau|verifier\.kit_rounds)' --jobs 4`,
  once per tree. Rows that need a GPU or nvcc are left out by the runner and listed as not run.
- Debug of the new code: only the planning call on the `dense` case files written by hand from the kit
  (no registered stored-proof call is run before its registered run).
- Excluded: nothing. A row that is not run on this host (missing tool) is listed with the runner's reason.

## Prior art

- In zkML systems that prove transformer inference (zkLLM, EZKL, Jolt-based and Expander-based provers,
  DeepProve), a dense MLP is the default layer and mixture-of-experts is the extension; none of them has a
  "served form" gate of this kind, so there is no outside design to copy. The relevant prior art is internal:
  `verifier/tests/served_form_test.py` case "dense" (main), `experiments/20261109-32-qwen-m3-design/DESIGN.md`
  section 4 and section 9 row "#35-limits", `docs/qwen-port.md` open risk 6, and the parameter file page's
  table of the standard form. What is new here is only the per-condition argument for NE 0 and the
  byte-identity evidence that the Maverick path is untouched.
- Table pinning by digests (FORMAT.md R15.3, verifier/HASHES.md) is the repository's own answer to
  floating-point library drift; this lane does not extend it to NE 0 (see table-digests above).

## Amendments


### Amendment 1, 2026-11-12 21:27 UTC (after code, during the registered runs)

The first registered stored-proof run (`runs/compare-1`, normalisation N, 2 rounds per binary) showed that the whole calls print wall times outside lines that begin `seconds:`: the stage headers (`---- stage key ---- 1 thread(s), 1.547 s`), per-step lines ending `0.052 s`, and indented `   seconds:` lines. So N leaves times in, and two runs of the SAME binary already give different hashes. This is a fault of the registered normalisation, not a difference between main and head. The planning calls carry no times and gave one hash on both binaries in that run.

Change, as the Runs section foresaw for nondeterministic output: a second run `compare2.py` (normalisation N2) with 5 rounds per binary, alternating main, head. N2 = N plus: a line whose text after leading blanks begins `seconds:` is removed, and every `<digits>.<digits> s` is replaced by `<t> s`. N2 also writes `n2-touched.txt`, the list of every line shape it removed or masked, so a reader can check that only wall times were touched. The acceptance threshold is unchanged except that "normalised SHA-256" now means N2. compare-1 is kept as run and reported as is. Run budget and hard stop unchanged.
