# RESULTS: 20261117-211-sampling-worksheet

Issue #211 (part of #7). Two results, reported separately. (1) Original registration, at the reviewed code `9c8e043`: **PASS**, all five registered runs matched 45 of 45 fixtures and gave the same report digest. (2) Amended suite (PREREG Amendments 1 to 3, registered after round 1 review), at the fixed code `b147791`: **PASS** against the amended acceptance. In each of five runs F46 to F135 matched 90 of 90 and F01 to F36 still match their original registration. F37 to F45 are changed registrations: they no longer match their original expectation (36 of the original 45 match at the fixed code) and give the outcome registered in Amendment 2 (9 of 9). Measured, unreplicated. Deterministic, so there is no spread to report.

What this is: an offline checker (`worksheet.py`, standard library, exact rationals) that takes one sampling policy worksheet and returns CONDITIONAL, INELIGIBLE or MISSING INPUTS, with the codes that decided it. At the reviewed code it did this correctly on the registered fixtures only: both round 1 reviews found worksheets outside them that received CONDITIONAL and should have been refused (see "Runs of the fixed checker" below). It is not a launch recommendation, it adds no formula, it estimates no cost, and it recommends no sampling rate. Every number in the fixtures is synthetic test input unless a main path is named next to it.

## Runs

This section and the next describe the original five runs at the reviewed code. They are unchanged evidence: the files under `runs/` are byte-identical to the reviewed head.

| run | matched | report sha256 | file |
|---|---|---|---|
| 1 | 45/45 | `0e08831366510def9ce75ba0670a487a139aed74c58831e15d10fb01a8319a39` | [runs/run-1.json](runs/run-1.json) |
| 2 | 45/45 | same | [runs/run-2.json](runs/run-2.json) |
| 3 | 45/45 | same | [runs/run-3.json](runs/run-3.json) |
| 4 | 45/45 | same | [runs/run-4.json](runs/run-4.json) |
| 5 | 45/45 | same | [runs/run-5.json](runs/run-5.json) |

Command per run: `taskset -c 4-5 prlimit --as=536870912 timeout 60 python3 experiments/20261117-211-sampling-worksheet/run_suite.py --run K --out experiments/20261117-211-sampling-worksheet/runs/run-K.json` (refuses to overwrite). Code was committed (`9c8e043`) before the first run; the PREREG (`3dc92dc`) before any code. No amendment existed when these five runs were made; Amendments 1 to 3 were added after round 1 review and apply only to the runs under `runs-r1/`. Before the registered runs only the debug fixtures DBG-01 to DBG-03 were run (`debug_fixtures.py`, outside the suite, as the PREREG allows). No time is reported.

## Every fixture and its verdict

All in `runs/run-1.json` (identical in runs 2 to 5). "match" means verdict, code set and the registered value(s) all equal the PREREG.

Formula fixtures (exact rationals; all inputs synthetic):

| id | check | expected | got |
|---|---|---|---|
| F01 | Bernoulli p=0, D=5 | 0 | 0, match |
| F02 | Bernoulli p=1, D=5 | 1 | 1, match |
| F03 | Bernoulli p=1/10, D=0 | 0 | 0, match |
| F04 | Bernoulli p=1/10, D=1 (single invalid) | 1/10 | 1/10, match |
| F05 | Bernoulli p=1/2, D=3 | 7/8 | 7/8, match |
| F06 | IID p=1/10, f=1/5, N=2 | 99/2500 | 99/2500, match |
| F07 | IID p=0 | 0 | 0, match |
| F08 | IID p=1, f=1 | 1 | 1, match |
| F09 | IID f=0 | 0 | 0, match |
| F10 | no-repl N=1000, m=10, D=1 | 1/100 (= m/N) | 1/100, match |
| F11 | no-repl D=0 | 0 | 0, match |
| F12 | no-repl D=N | 1 | 1, match |
| F13 | no-repl m=0 | 0 | 0, match |
| F14 | no-repl m=N | 1 | 1, match |
| F15 | no-repl N=12, m=3, D=3 | 34/55 | 34/55, match |
| F16 | no-repl N=12, m=3, D=6 | 10/11 | 10/11, match |
| F17 | explicit q: N=2, K=1, m=1, q=1/2 | 1/4 | 1/4, match |
| F18 | explicit q=0, K=N | 0 | 0, match |
| F19 | soundness: coverage 1/100, epsilon 1/50 | lower bound 0 | 0, match |

F15 and F16 reproduce the coverage values behind the #84 reviewer's concavity toy (61.82% at D=3, and D=6) quoted in `research/sampled-audit/README.md`; the 45.45% mix is the average of F16 and D=0.

#84 representative cells (exact value formatted as `research/sampled-audit/report.py:28,40` does, compared as strings with `research/sampled-audit/TABLES.md` on main):

| id | N, D, m | published | got |
|---|---|---|---|
| F20 | 1000, 100, 5 | 41.0168% | 41.0168%, match |
| F21 | 1000, 100, 10 | 65.3072% | 65.3072%, match |
| F22 | 1000, 10, 50 | 40.2689% | 40.2689%, match |
| F23 | 1000, 10, 100 | 65.3072% | 65.3072%, match |
| F24 | 64, 35, 1 | 54.6875% | 54.6875%, match |
| F25 | 64, 8, 4 | 42.1933% | 42.1933%, match |
| F26 | 256, 26, 16 | 82.9485% | 82.9485%, match |

Cost and unit fixtures (cost section only; inputs synthetic except F35):

| id | case | expected | got |
|---|---|---|---|
| F27 | I=1, C=1/100, A=F=0, P=100, p=1/100, one unit | cost 201/100, normalized 201/100, synthetic flagged | match |
| F28 | same via incremental R=100 | normalized 201/100 | match |
| F29 | same via total audited-path R=101, p(R-1) | normalized 201/100 | match |
| F30 | GPU seconds plus dollars | MISSING INPUTS, UNIT_MISMATCH, no number | match |
| F31 | GPU seconds plus wall seconds | MISSING INPUTS, UNIT_MISMATCH | match |
| F32 | Qwen proof cost P unknown | MISSING INPUTS, UNKNOWN_COST, P listed | match |
| F33 | receipt cost C unknown | MISSING INPUTS, UNKNOWN_COST, C listed | match |
| F34 | number with no source | MISSING INPUTS, NO_PROVENANCE | match |
| F35 | batch-1 decode ratio 0.46 (`experiments/20261112-7-plain-inference-baseline/RESULTS.md:84`, stream wall seconds) offered as GPU-cost R | MISSING INPUTS, DECODE_RATIO_NOT_GPU_COST | match |
| F36 | p given as a token fraction | MISSING INPUTS, TOKEN_FRACTION_NOT_REQUEST_FRACTION | match |

Policy fixtures (full worksheets; all synthetic):

| id | class | case | expected | got |
|---|---|---|---|---|
| F37 | fleet monitoring | p=1/2, D=3, target miss 1/4 | CONDITIONAL, coverage 7/8, miss 1/8 | match |
| F38 | fleet monitoring | target miss 1/10 | INELIGIBLE, MISS_ABOVE_TARGET | match |
| F39 | fleet monitoring | outcome-adaptive schedule, lifetime formula asked | INELIGIBLE, ADAPTIVE_NOT_IID, no coverage | match |
| F40 | vendor-independent proof | p=1, verify before action | CONDITIONAL, coverage 1, "only under the selected relation" | match |
| F41 | vendor-independent proof | p=99/100 | INELIGIBLE, SUBSAMPLE_NOT_PROOF | match |
| F42 | vendor-independent proof | p=1, verify after action | INELIGIBLE, VERIFY_AFTER_ACTION | match |
| F43 | hardware-trusting | m=100 of 1000, individual guarantee claimed | INELIGIBLE, SUBSAMPLE_NOT_PROOF | match |
| F44 | hardware-trusting | q inferred from changed-weight count | MISSING INPUTS, Q_INFERRED_FROM_WEIGHTS | match |
| F45 | hardware-trusting | timeout counted as a wrong answer | MISSING INPUTS, TIMEOUT_NOT_PROOF | match |

F37 also records deterrence as asked: synthetic P_detect 7/8 times loss 8 = 7 > gain 5, condition holds, under the stated synthetic behavioral assumption. It is a recorded field, not a verdict input and not a fact.

The three negative tests the issue names are F35 (batch-1 decode ratio as GPU-cost R), F39 (adaptive schedule as IID) and F41/F43 (p<1 sold as proof for a specific answer). All refuse.

## Templates and the decision sheet

`templates.json` has one blank template per class; [runs/templates.json](runs/templates.json) shows each evaluates to MISSING INPUTS (codes NO_RELATION, MISSING_INPUT, UNKNOWN_COST with `costs.P` and `costs.C` listed as unknown; the hardware-trusting one also NO_HW_TRUST_ASSUMPTION). [DECISION-SHEET.md](DECISION-SHEET.md) is empty on purpose: penalties, risk tolerance, desired miss probability, relation, retention and enforceability are not filled in. At the fixed code the same three templates are again MISSING INPUTS ([runs-r1/templates.json](runs-r1/templates.json)).

## Numbers quoted from main (not inputs, not re-derived)

- `guide/performance.md:27`: proving 93.0 times slower per GPU than stock prefill at the highest load, 71.4 times than prefill of 24 at once, one pass 20.1 times slower than decoding at 512 streams; calculated, best case, "not the cost of proving a generated reply".
- `docs/figures.tsv:54-55`: rows `overhead-prefill-24` and `overhead-prefill-max`, the same figures.
- `experiments/20261112-7-plain-inference-baseline/RESULTS.md:84`: 240 times prefill and 0.46 times decode at batch 1, conditional, route wall seconds, "not a cost claim, not a bound, not a measured proving overhead". F35 uses the 0.46 only to show it is refused as a GPU-cost R.
- `experiments/20261112-7-cost-model/model-output.json` `model.gpu_s_per_1k` central 42.52: extrapolated, no Qwen proof exists. Not used as an input.

These evidence files are byte-identical between the issue's snapshot `83299f19` and the base `415fb13a` (empty `git diff --stat`).

## What is NOT established

- No feasibility of any real policy: every real template is MISSING INPUTS, because the Qwen full-request proof cost P and the receipt cost C are unknown on main, and the policy values are Shadow's.
- No measured cost, overhead multiplier, dollar figure or sampling rate. Synthetic costs (I=1, P=100 and so on) are test inputs only.
- Coverage numbers are conditional calculations on a fixed invalid count or IID rate with perfect rejection (or an explicit q); they are not measured model-substitution detection and not a per-request guarantee.
- The checker does not check that the selection randomness was unpredictable, that the population was independently enumerated, or that the relation is sound; it states these as assumptions.
- No lifetime analysis for an outcome-adaptive adversary; such a request is refused, not answered.
- Queue/batch effects and all-traffic trace cost are not modelled.
- The cost-only fixtures F27 to F36 exercise the cost section alone; their "CONDITIONAL" means "numbers well formed", not a policy verdict.
- Unreplicated. Round 1 review (two reviewers) requested changes on the checker code. The fixed code has not been reviewed.

## Runs of the fixed checker (after round 1 review)

Both round 1 reviews requested changes on the checker code: [opus](https://github.com/wakesync/flashprove/pull/220#issuecomment-6961891535) and [astra](https://github.com/wakesync/flashprove/pull/220#issuecomment-6962089424). Their finding, as reviewers' descriptive findings: outside the registered fixtures the reviewed checker returned CONDITIONAL on incomplete or out-of-domain worksheets, and raised on some malformed ones. The registered evidence above was not in question.

Order in history: Amendment 1 (`e6c95a8`, new fixtures F46 to F135 and their expected verdicts), Amendment 2 (`c3b589e`, changed registration for F37 to F45), Amendment 3 (`74be4ac`, one rule found by the debug inputs), then the code (`b147791`), then the runs (`8d095b7`). No expectation was edited after it was registered. Before run 1 the new code was run only on `debug_fixtures_r1.py` (DBG-04 to DBG-17 and 960 generated malformed inputs on a separate base), twice; no fixture F01 to F135 was run on the new code before run 1.

| run | F01 to F45 against their original registration | F37 to F45 against Amendment 2 | F46 to F135 | report sha256 | file |
|---|---|---|---|---|---|
| 1 | 36/45 (F01 to F36 match; F37 to F45 do not) | 9/9 | 90/90 | `11664c01000b93b5982eff3e579ca48fb20575905deafc5832955925484e3ce6` | [runs-r1/run-1.json](runs-r1/run-1.json) |
| 2 | 36/45 | 9/9 | 90/90 | same | [runs-r1/run-2.json](runs-r1/run-2.json) |
| 3 | 36/45 | 9/9 | 90/90 | same | [runs-r1/run-3.json](runs-r1/run-3.json) |
| 4 | 36/45 | 9/9 | 90/90 | same | [runs-r1/run-4.json](runs-r1/run-4.json) |
| 5 | 36/45 | 9/9 | 90/90 | same | [runs-r1/run-5.json](runs-r1/run-5.json) |

Command per run: `taskset -c 4-5 prlimit --as=536870912 timeout 60 python3 -B experiments/20261117-211-sampling-worksheet/run_suite_r1.py --run K --out experiments/20261117-211-sampling-worksheet/runs-r1/run-K.json` (refuses to overwrite). Of the 90 new fixtures, 14 are registered CONDITIONAL, 11 INELIGIBLE and 65 MISSING INPUTS. Every MISSING INPUTS result carries no number. No time is reported.

### Changed registration: F37 to F45

The nine original policy fixtures are incomplete worksheets under the schema the reviews asked for (no declared deterrence state; F40 to F42 also no deadline policy). The fixed checker refuses them as MISSING INPUTS. This is a change of registered outcome, named in Amendment 2 before the code, not a pass of the original expectations: at the fixed code 36 of the original 45 fixtures match their original registration, not 45. `fixtures.py` is unchanged, and the original outcome at the reviewed code stays on record in `runs/`. The same nine cases are registered again on completed worksheets as F47 to F55, with the original verdicts and codes, and match.

### What each must-fix changed, and the fixtures that cover it

| must-fix | change in `worksheet.py` | fixtures |
|---|---|---|
| 1. Required schema and unknowns fail closed | required text, sections and booleans checked; `kind=unknown` on any required input is `UNKNOWN_REQUIRED`; deterrence needs a declared state; a refusal counted as a wrong answer is refused; unsupported formula and input combinations refused | F56 to F78 |
| 2. Numeric domains before arithmetic | `num()` checks value form, integer counts and ranges before any formula; counts are never truncated; `evaluate()` does not raise | F79 to F104 |
| 3. An explicit q is never dropped | q is used by the one registered q formula (fixed-size, with K equal to D) or refused as `Q_UNSUPPORTED`; no fallback to perfect rejection | F105 to F114 |
| 4. Soundness bound reaches the verdict | the target is compared with `1 - max(0, coverage - epsilon)`; epsilon range-checked | F115 to F121 (and F93, F94) |
| 5. No CONDITIONAL without a coverage | an outcome-adaptive schedule is always `ADAPTIVE_NOT_IID`; IID f under the fixed-size scheme is `UNSUPPORTED_COMBINATION`; a CONDITIONAL needs a computed coverage and cost | F122, F123, F67 (and F49) |
| 6. Cost scope and loss basis | F is an epoch total in a per-epoch unit, divided by N once; nonzero F tested in the plain and both R conventions; loss and gain need one concrete unit; all-wall-seconds costs refused | F46, F124 to F135 |

Controls: the 14 fixtures registered CONDITIONAL (F46, F47, F50, F66, F68, F76, F103, F104, F110, F116, F117, F120, F125, F126) are complete worksheets with registered values, so the suite also goes red if the checker refuses everything.

### Limits of the fixed checker and of this evidence

- The new fixtures and their expected verdicts were written by the same lane that wrote the fix, after reading both reviews. They were registered before the code, but they are not an independent test. The fixed code has not been reviewed.
- All 90 new fixtures matched on the first registered run. That shows the code does what was registered; it does not show the registration is complete. The reviews found the first registration incomplete in the same way.
- The rule of Amendment 3 (a `source` that is not text is `NO_PROVENANCE`) is covered only by debug inputs DBG-16 and DBG-17, not by a registered fixture.
- `NO_COVERAGE`, `NO_COST` and `CHECKER_ERROR` are backstops with no registered fixture; no input is known that reaches them.
- The 960 generated malformed inputs are debug inputs on one base, not a registered suite and not a proof that no malformed worksheet is accepted.
- A required text field is satisfied by any non-empty text. The checker cannot tell whether a relation, a population definition, a deadline policy or a behavioral assumption means anything.
- The loss basis is the declared unit of loss and gain. The checker cannot check that the two amounts are really in that unit.
- One stated exception to the cost scope rule: an F that is exactly zero is accepted in a per-request unit, which keeps F27 to F36 valid as registered.
- `templates.json` is unchanged from the reviewed head. The blank templates therefore do not show the fields the fixed checker now requires (`deterrence.state`, a per-epoch unit for F, `sampling.schedule`, and so on). They still evaluate to MISSING INPUTS, but a person filling one in has to read PREREG Amendment 1 for the full schema. Updating the templates is not done here.
- The reviewers' own failing inputs are not committed here as files. Each is re-registered as a fixture on a completed base worksheet (F56 to F135), because the reviewers' base worksheets are themselves incomplete under the new schema and would be refused for that reason alone.
- Design choices made where the reviews left one (refuse a q the registered formula cannot use; one miss target compared with the supported bound; wall seconds refused as a cost unit) are choices of this lane, stated in Amendment 1.
- Queue and batch effects and all-traffic trace cost are listed in every result under `not_modelled`. They are not input fields and nothing is computed from them.
- Everything under "What is NOT established" above still holds. No real policy is feasible or infeasible by this work, no cost, overhead, dollar figure or sampling rate is measured, and the decision sheet is empty.

## Corrections after review

Dated 2026-11-17, after the round 1 reviews. Each replaced sentence is quoted.

1. Replaced, at the top: "Verdict against the registered threshold: **PASS**. Measured, unreplicated. Deterministic: all five registered runs matched 45 of 45 fixtures and gave the same report digest, so there is no spread to report." Reason: it was true of the registered suite and is kept as result (1), but it read as the result for the checker, and both reviews show the checker accepted worksheets it should refuse. Asked for by [opus](https://github.com/wakesync/flashprove/pull/220#issuecomment-6961891535) and [astra](https://github.com/wakesync/flashprove/pull/220#issuecomment-6962089424) ("Report the original 5 runs and the new runs separately").
2. Replaced, under Runs: "No amendment." Reason: three amendments now exist; the sentence stays true only for the original five runs and says so. Same two comments.
3. Replaced, under What is NOT established: "- Unreplicated; no independent review yet." Reason: round 1 review happened and requested changes. Same two comments.
4. Added after "with the codes that decided it.": the sentence saying the reviewed code did this correctly on the registered fixtures only. Same two comments.
5. Results ledger row, generated README and CLAIMS rows, and the PR body said "All fixture numbers are synthetic." That is wrong for F35, whose 0.46 is a conditional calculation quoted from `experiments/20261112-7-plain-inference-baseline/RESULTS.md:84` on main. Corrected to "synthetic except F35". Asked for by [opus](https://github.com/wakesync/flashprove/pull/220#issuecomment-6961891535) (nonblocking). The fixture tables above already said this.
6. The PREREG header says "Date (UTC): 2026-11-17 21:20" but its commit is 21:14:31Z and the code commit is 21:19:29Z. Not edited; disclosed in PREREG Amendment 1. Asked for by both comments (nonblocking).
7. The sentence "Code was committed (`9c8e043`) before the first run; the PREREG (`3dc92dc`) before any code." is unchanged and still true of the original runs.
