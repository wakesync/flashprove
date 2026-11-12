# RESULTS: 20261112-135-dense-standard-form

Issue #135 (part of #35). PREREG: [PREREG.md](PREREG.md) (first commit 06b69f22f2cac21af4f0228538613e0c159a88a8, Amendment 1 dated 2026-11-12 21:27 UTC). Environment: [ENV.json](ENV.json).

## Verdict: PASS (measured, unreplicated), with one disclosed weakening

Against the registered threshold (Amendment 1 for the hash normalisation):

| registered criterion | result | evidence |
|---|---|---|
| `routed-experts.dense` is met on head (status 4, no line `plan: not the standard parameter form`, both one-time-files lines) | met | `runs/served/head-1.log`, `runs/dense-plan/dense-plan-head.txt` |
| `dense-with-digests` -> `policy-tables`, `dense-with-gcl` -> `policy-gcl`, `dense-with-rcl` -> `policy-rcl`, `NE-0` -> `header-absent-class` on head, as on main | all four as on main | `runs/served/*.log` |
| every other served-form case: same status and result on head as on main | 46 of 47 cases identical; the 47th is `routed-experts.dense` | table below |
| every registered stored-proof call: same exit status, last line and normalised SHA-256 on head as on main | 12 of 12 calls, 5 rounds per binary, 120 runs, one N2 hash per call | `runs/compare-2/summary.json`, `runs/compare-2/runs.tsv` |
| registered suite rows that pass on main pass on head | **not run** (see "What was not run") | |

The one registered criterion that was not run is the suite subset. The served-form row of that subset is the same script as the served-form runs above, so its outcome on both trees is known; the other rows were not run by this lane.

## What changed

`verifier/src/cp_verify.cpp`, request stage, the arguments of `servedForm()` and nothing else:

```
const bool dense = h.NE == 0 && !RCL && !GCL && tblAt == 0;
routed-experts:  h.NE > 0            ->  h.NE > 0 || dense
both-clamps:     RCL && GCL          ->  (RCL && GCL) || dense
table-digests:   tblAt == TBLW       ->  tblAt == TBLW || dense
```

For NE above 0, `dense` is false and the three arguments are main's, term for term. No parser rule, refusal, shape test, statement word, hash, plan or accounting line changes. The test's expectation for `dense` moved from `not met: routed-experts, both-clamps, table-digests` to `met`, and its head comment says why. Docs: `verifier/docs/parameter-file.md` (table of the standard form, and a new bullet "A dense file" with the per-condition argument), `docs/format/FORMAT.md` (12.3, 13.7 conditions 8 and 10, the table of names), `docs/qwen-port.md` open risk 6 (narrowed, not closed).

**No change to the Lean model or to the soundness argument.** The Lean soundness theorem covers the Maverick-shaped model only (`docs/qwen-port.md`, risk 7); it says nothing about a dense file before or after this change.

## Per removed condition: why it may count as met at NE 0

- `routed-experts`: vacuous. With NE 0 there is no router and no routed expert. The parser already refuses any expert class digit form (`header-absent-class`) and any expert weight kind (`header-absent-kind`) at NE 0.
- `both-clamps`: vacuous for `rcl` (it clamps the router's logits; there is no router). For `gcl` the repository's own text (`verifier/docs/parameter-file.md`, "The gate's clamp") says the clamp does not change the proved function, only which prompts have a proof, and the parser refuses it at NE 0 because the clamp is laid out in the router sigmoid's table. So a dense file proves the same function as it would with a clamp, on fewer prompts. **Not established here:** whether a dense model's SiLU key fits 16 bits on real prompts, that is, how many prompts lose their proof without the clamp. That needs ranges from a real dense model.
- `table-digests`: **not vacuous; a disclosed weakening.** Of the four public tables only the sigmoid table is for experts alone (its statement words are 0 at NE 0). The SiLU, rotary and softmax tables are used by a dense model too, and the parser refuses their 32 digest lines at NE 0 (`policy-tables`). Under a dense file these three tables are therefore fixed only by the verifier's own floating-point computation, which it writes into the statement that the first chain binds, not by lines that the commitment ID covers. `softmax-table` and `rotary-table` still hold, so the softmax and rotary tables are computed only at values that `scales/tests/table_ties.py` checks; the SiLU table has no such condition. A dense `YES` thus does not show that the prover's and the verifier's libraries gave the same three tables. Closing this needs digest lines at NE 0 (with `tsig` 0), a parser and `scales/policy_tables.py` change that is outside this milestone.

What still binds the remaining tables and files under a dense file: the configuration digest (`configuration=`, all three configuration files byte for byte, in every chain's first query and in the ID), the statement (built by the verifier, including its own table digests), and every other standard-form condition, all unchanged.

## Served-form planning cases, before and after

`verifier/tests/served_form_test.py` on `prover/tests/configurations/pinned_no_proof_of_work`. Main: the test file at base with the main binary (`runs/served/main-1.log`, `served_form_test.py: all as expected`). Head: the branch's test file with the head binary (`runs/served/head-1.log`, `all as expected`). Table made by `served_table.py` from those two logs: 47 cases, changed: `routed-experts.dense` only. A first head run (21:18 UTC) also printed `all as expected` but its log was not kept; it is not counted.

| case | main | head |
|---|---|---|
| `none.kit` | met | met |
| `none.asked-above` | NO: security-bits | NO: security-bits |
| `profile.prof-19` | NO: policy-profile | NO: policy-profile |
| `routed-experts.NE-0` | NO: header-absent-class | NO: header-absent-class |
| **`routed-experts.dense`** | **not met: routed-experts, both-clamps, table-digests** | **met** |
| `routed-experts.dense-with-digests` | NO: policy-tables | NO: policy-tables |
| `routed-experts.dense-with-gcl` | NO: policy-gcl | NO: policy-gcl |
| `routed-experts.dense-with-rcl` | NO: policy-rcl | NO: policy-rcl |
| `five-limbs.no-xl` | not met: five-limbs | not met: five-limbs |
| `both-clamps.no-gcl` | not met: both-clamps | not met: both-clamps |
| `both-clamps.no-rcl` | not met: both-clamps | not met: both-clamps |
| `prompt-source.toksrc-0`, `toksrc-2` | NO: statement-required | NO: statement-required |
| `placement-table.no-layout` | NO: plan-layout | NO: plan-layout |
| `table-digests.no-lines` | not met: table-digests | not met: table-digests |
| `table-digests.{silu,sigmoid,rope,exp}-altered` | NO: table-digest-{silu,sigmoid,rope,exp} | same |
| `table-digests.{last-missing,two-swapped,behind-a-call}` | NO: policy-tables | NO: policy-tables |
| `no-range-words.eg-7`, `smax-2047` | not met: no-range-words | same |
| `three-bytes.S-32`, `S-44` | NO: af-policy-wd | same |
| `ring-degree.D-32` | not met: ring-degree | same |
| `one-placement.stream`, `stream-halves` | not met: one-placement | same |
| `one-placement.control`, `halves-control` | met | met |
| `softmax-table.S-11`, `S-13`, `rx-7` | not met: softmax-table | same |
| `rotary-table.theta` / `control` | not met: rotary-table / met | same |
| `norm-shifts.{first,second,last}-norm` / `control` | not met: norm-shifts / met | same |
| `two-codes.{batch,one-time,both}` / `control` | not met: two-codes / met | same |
| `one-shift.{first,last}-group` / `control` | not met: one-shift / met | same |

Grouped rows stand for one row per case in the script's output; every case's exact status and text is in the two logs.

The same dense case files under both binaries (`runs/dense-plan/`): the two planning outputs differ in exactly one line, `plan: not the standard parameter form (routed-experts, both-clamps, table-digests): ..`, present on main and absent on head, plus one wall time. Statement length (177 words), `h_par=` and `configuration=` are the same.

`table-digests.no-lines` (NE 4, no digest lines) still misses `table-digests` on head: the admission is for NE 0 only.

## Stored-proof calls, main vs head

Four stored sets: `examples/full-size` (Llama 4 Maverick shape, 48 layers, 128 routed experts, synthetic weights, exact match), `examples/full-size-clipped-gap`, `examples/accepted-proof`, `examples/accepted-proof-clipped-gap`. Three calls each: the whole call with `-id` (and `-policy` for the clipped-gap sets), the same with `-q`, and the planning call `-plan request` on the set's files. No proof on Meta's real Maverick weights is stored in the repository, so none was run.

**compare-2** (Amendment 1, N2, 5 rounds per binary, alternating main, head): 12 of 12 calls, 120 runs, 0 differ. Per call (first 16 hex digits of the N2 SHA-256; full digests in `runs/compare-2/runs.tsv`):

| call | status | last line | N2 hash, all 10 runs |
|---|---|---|---|
| full-size.whole | 0 | YES | 2014e9ec6dd39979 |
| full-size.whole-q | 0 | YES | 2bf7ca47e9a91a4c |
| full-size.plan-request | 4 | PLAN ONLY: no proof was checked | 59d524c64682c877 |
| full-size-clipped-gap.whole | 0 | WITHIN LIMITS: clipped-gap C=25856 theta=512 cap=1 s=15 sh=8 | e413e3fdaa1d9a53 |
| full-size-clipped-gap.whole-q | 0 | same | 9d551657c853f754 |
| full-size-clipped-gap.plan-request | 4 | PLAN ONLY: no proof was checked | 6f576c625f05f86c |
| accepted-proof.whole | 0 | YES | 5b40cc1d966a8b67 |
| accepted-proof.whole-q | 0 | YES | d7f168f5c4ddf8b8 |
| accepted-proof.plan-request | 4 | PLAN ONLY: no proof was checked | e32676beb0921761 |
| accepted-proof-clipped-gap.whole | 0 | WITHIN LIMITS: clipped-gap C=9244130 theta=323343 cap=1 s=16 sh=8 | 674ed535473d895b |
| accepted-proof-clipped-gap.whole-q | 0 | same | b11c9f3ca3f2be29 |
| accepted-proof-clipped-gap.plan-request | 4 | PLAN ONLY: no proof was checked | 318c697a809f5665 |

`runs/compare-2/n2-touched.txt` lists every line shape that N2 removed or masked across the 120 runs: only stage headers with their seconds, per-step lines ending in seconds, and `seconds:` lines. Raw outputs of round 0 (main and head, 24 files) are in `runs/compare-2/raw-round0/`; `build=` there differs between the two binaries, as it must.

**compare-1** (the registered N, 2 rounds per binary), kept as run: status and last line identical between main and head for all 12 calls; the four planning calls gave one N hash on both binaries; the eight whole calls gave a different N hash on every run, also between two runs of the same binary, because N left wall times in. That was a fault of the registered normalisation (Amendment 1), not a difference between the binaries.

## What was not run

- The registered suite subset (`run_suite.py cpu --only ...`, once per tree). It was queued behind the host's two-slot heavy-job gate from 21:22 UTC; both slots were held by other lanes' jobs and it had not started when this file was written. Rows not run therefore include `build.verifier`, `verifier.call_accounting.examples`, `verifier.commitment_id.examples`, `verifier.record_altered_sets.example/.full`, `verifier.example_kits`, `verifier.extreme_files`, `verifier.plan_tau`, `verifier.kit_rounds`. The served-form row `verifier.served.form` runs the same script as the runs above. [If the suite finishes before the lane's hard stop, its logs are added under `runs/suite/` in a later commit and this paragraph is replaced by a dated note.]
- `verifier.served.form.world.kit` and every GPU row: need a GPU or worlds made by `cp_commit`/`cp_prove`.

## What is not established

- No dense proof exists, so no dense `YES` was seen. That `cp_verify` reaches `YES` on a real dense proof is a later milestone (#135 "Out of scope"); a dense commit/prove path may fail elsewhere.
- `cp_commit` makes a planning call of the `cp_verify` beside it and refuses a non-standard file at 128 bits (`cp-commit-not-standard`). With the head verifier it would no longer refuse a dense file for these three conditions. No `cp_commit` was built or run here.
- Whether dropping `gcl` costs a dense model provable prompts (SiLU key ranges on a real dense model).
- That the SiLU, rotary and softmax tables agree between prover and verifier libraries under a dense file (see `table-digests` above).
- Any other #35 limit (query width, head dimension 256, partial rotary, q/k norm, sigmoid gate, hybrid schedule, segment cap): untouched, still refused or unmet.
- Lean: no change, no new theorem.

## Reproduce

From the repository root, with two verifier builds (main at c810b3e9, head at this branch) in folders of your own (`verifier/build.sh - <folder>`; it refuses group-writable parents):

```
python3 -B verifier/tests/served_form_test.py <head>/cp_verify prover/tests/configurations/pinned_no_proof_of_work <new folder>
python3 -B experiments/20261112-135-dense-standard-form/compare2.py <main>/cp_verify <head>/cp_verify . <new folder>
python3 -B experiments/20261112-135-dense-standard-form/served_table.py <log on main> <log on head>
```

The main log needs main's copy of `verifier/tests/served_form_test.py` (`git show c810b3e9:verifier/tests/served_form_test.py`), whose expectation for `dense` is the old one.
