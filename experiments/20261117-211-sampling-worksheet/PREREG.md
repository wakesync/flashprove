# PREREG: 20261117-211-sampling-worksheet

Issue: #211 (part of #7; agenda U2/Q3/Q4). Lane: sheet211. Date (UTC): 2026-11-17 21:20. Base commit: `415fb13aab9425d224e2ca88788497ce3677bd7f` (main when this branch was made).

Desk analysis plus a small deterministic arithmetic checker. No model, no weights, no GPU, no prover, no benchmark, no Monte Carlo, no new proving-cost or overhead estimate, no dollars, no recommended sampling rate.

## Evidence read (on the base commit)

The issue cites main `83299f194b80f62feca170a28650b390add3fbdc`. `git diff --stat 83299f19 415fb13a` over every evidence path the issue names is empty, so the files below are unchanged in substance (and byte for byte) at the base commit:

- `guide/performance.md:27` (Cost paragraph: proving at 24 per batch is 93.0 times slower than stock prefill at the highest load, 71.4 times than prefill of 24 at once, one pass 20.1 times slower than decoding at 512 streams; all per GPU, calculated, best case).
- `docs/figures.tsv:54-55` (rows `overhead-prefill-24`, `overhead-prefill-max`).
- `experiments/20261112-7-plain-inference-baseline/RESULTS.md:75-96` (#137: conditional multiple 240x prefill and 0.46x decode at batch 1; route wall seconds of one stream on a shared card, explicitly "not a cost claim, not a bound, not a measured proving overhead").
- `experiments/20261112-7-cost-model/RESULTS.md` and `model-output.json` (#126: `model.gpu_s_per_1k` central 42.52 GPU-s per 1,000 window tokens, extrapolated, no Qwen proof exists).
- `research/sampled-audit/README.md` and `TABLES.md` (#84: formulas, cost accounting `I + C + A + F/N + p*P`, plan tables rounded with `f'{v*100:.4f}%'`, `research/sampled-audit/report.py:28` and `:40`).

These numbers are only quoted, as data with their evidence kind; the checker never turns one into an input it did not have.

## Hypothesis

A standard-library Python checker using exact rational arithmetic (`fractions.Fraction`), with typed units and mandatory provenance on every numeric input, gives every fixture registered below its registered verdict, error codes and exact value, identically in five repeated runs.

## Metric

1. Per fixture: match (yes/no) of verdict, of the set of error codes, and of the exact rational value (or of the published rounded string for #84 cells). Count of matching fixtures over the registered total.
2. Run-to-run: SHA-256 of the canonical JSON report (sorted keys, Fractions as `"num/den"` strings) for each of five runs; all five must be equal.

## Acceptance threshold

PASS only if all registered fixtures (F01 to F45 below) match in all three parts, in each of the five runs, and the five report digests are identical. Any single mismatch is FAIL. The outcome is deterministic, so no spread is reported; "deterministic" stands in place of a spread.

## Kill criterion

Hard stop 2026-11-17T22:45:00Z (the issue's two-hour wall stop), whatever state the code is in. At the stop: commit, write RESULTS.md as PARTIAL (suite not run, or not all fixtures implemented) or FAIL (any registered fixture mismatches), never edit a fixture expectation or an assumption to make a fixture or a policy pass. CPU budget: one process, cores 4-5 (`taskset -c 4-5`), address-space cap 512 MiB (`prlimit --as=536870912`). A run that exceeds the cap or 60 seconds is a FAIL for that run.

## Runs

- The registered suite is run exactly five times, sequentially, as `taskset -c 4-5 prlimit --as=536870912 python3 experiments/20261117-211-sampling-worksheet/run_suite.py --run k --out experiments/20261117-211-sampling-worksheet/runs/run-k.json` for k = 1..5. No warmup, no exclusion, no seeds (nothing random). Each run file is written once and never modified.
- Debug rule: before the registered runs the code may be exercised only on debug fixtures DBG-01 to DBG-03, which are not part of the registered suite: DBG-01 Bernoulli p=1/3, D=2 (expected 5/9); DBG-02 no-replacement N=5, m=2, D=1 (expected 2/5); DBG-03 a cost input with unit `apples` (expected UNIT_UNKNOWN). Debug fixtures live in a separate file and are not in the five registered runs' totals.

## Worksheet schema (registered sections)

Each worksheet is one JSON object with these sections. A numeric input is `{"value": "a/b", "unit": U, "kind": K, "source": S}`; `kind` is one of `measured`, `calculated`, `extrapolated`, `conditional_calculation`, `policy_supplied`, `synthetic`, `unknown`; `source` is a path:line on main, `policy:<who>`, or `synthetic:test`. A numeric input with no `kind` or no `source` is error `NO_PROVENANCE`. `kind=unknown` means the value is unknown and must be `null`.

1. `policy_class`: one of `fleet_monitoring_after_release`, `vendor_independent_proof_irreversible`, `hardware_trusting_immediate_with_later_review`.
2. `population`: definition text, `N` (unit `request`, or `layer`/`token` with an explicit family), epoch rule.
3. `sampling`: `scheme` in `bernoulli_p`, `fixed_size_no_replacement_m`; `p` (unit `request_fraction`) or `m` (unit `request`); `schedule` in `fixed_in_advance`, `outcome_adaptive`.
4. `invalidity`: either fixed `D` (unit `request`) or IID `f` (unit `request_fraction`), not both.
5. `distinguishability`: optional `q` (dimensionless probability, with provenance), or `K` changed-model count; `q_source` must not be `changed_weight_count`.
6. `soundness_treatment`: text, and optional `epsilon` (probability); detection lower bound is `max(0, coverage - epsilon)`.
7. `relation`: the selected proof relation (text; required for every class).
8. `costs`: `I`, `P`, `C`, `A`, `F` with one declared cost unit shared by all five (e.g. `gpu_s_per_request`); or an `R` ratio with `R_convention` in `incremental` (R=P/I) or `total_audited_path` (R=(I+P)/I) and `R_unit_basis` naming the units of numerator and denominator.
9. `latency`: deadline policy, `verify_before_action` (bool), `timeout_policy` text.
10. `targets`: `desired_miss_probability` (policy_supplied).
11. `deterrence`: `enforceable_loss`, `cheating_gain` (same unit, policy_supplied), `behavioral_assumptions` text.
12. `claims`: `individual_guarantee` (bool), `hardware_trust_assumption` text (required for the third class).

Outputs: `verdict` in `CONDITIONAL`, `INELIGIBLE`, `MISSING INPUTS`; sorted `codes`; exact `coverage`, `miss`, `cost_per_request`, `normalized_cost`; `assumptions` text; `synthetic_inputs` list; `unknowns` list. Never a launch recommendation.

## Registered formulas

- Bernoulli, fixed D: `1-(1-p)^D`.
- IID invalidity, Bernoulli selection: `1-(1-p*f)^N`.
- Fixed-size no replacement: `1-C(N-D,m)/C(N,m)`.
- With explicit independent q and K changed requests, fixed-size: `1-sum_j C(K,j)C(N-K,m-j)/C(N,m)*(1-q)^j`.
- Cost: `I+C+A+F/N+p*P`; incremental normalized `1+(C+A+F/N)/I+p*R` with R=P/I; total audited-path R: `1+(C+A+F/N)/I+p*(R-1)`.
- Deterrence (recorded only, under the declared behavioral assumptions): `P_detect*enforceable_loss > cheating_gain`.

## Registered verdict rules

- Any required input absent, any `kind=unknown` required value, any `NO_PROVENANCE`, any unit error: `MISSING INPUTS` (unit errors and unknown costs block a numeric viability verdict; no numeric cost is output).
- `vendor_independent_proof_irreversible`: requires p=1 (or m=N) and `verify_before_action=true`, else `INELIGIBLE` (`SUBSAMPLE_NOT_PROOF` or `VERIFY_AFTER_ACTION`). Even then the verdict is CONDITIONAL "only under the selected relation".
- `hardware_trusting_immediate_with_later_review` and `fleet_monitoring_after_release`: `individual_guarantee=true` with p<1 is `INELIGIBLE` (`SUBSAMPLE_NOT_PROOF`). Third class requires a non-empty `hardware_trust_assumption` (else MISSING INPUTS, `NO_HW_TRUST_ASSUMPTION`).
- Coverage classes: CONDITIONAL if `miss <= desired_miss_probability`, else `INELIGIBLE` (`MISS_ABOVE_TARGET`).
- `schedule=outcome_adaptive` with a lifetime/IID or plug-in product request: `INELIGIBLE` (`ADAPTIVE_NOT_IID`).
- R whose `R_unit_basis` is wall seconds of a stream (or a decode ratio) used as GPU cost: refused, `DECODE_RATIO_NOT_GPU_COST`, MISSING INPUTS.
- Adding `gpu_s` to `wall_s`, or mixing cost units: `UNIT_MISMATCH`. Token fraction where request fraction is required: `TOKEN_FRACTION_NOT_REQUEST_FRACTION`.
- A timeout counted as proof of a wrong answer: `TIMEOUT_NOT_PROOF`, MISSING INPUTS for that observation.
- q supplied with `q_source=changed_weight_count`: `Q_INFERRED_FROM_WEIGHTS`, MISSING INPUTS.
- Values with `kind=synthetic` are listed in `synthetic_inputs` and the report carries `synthetic: true`; synthetic numbers are never reported as forecasts.

## Registered fixtures (exact rationals; all numeric inputs are synthetic unless a main path is named)

Formula fixtures (value checks):

| id | formula | inputs | expected |
|---|---|---|---|
| F01 | Bernoulli | p=0, D=5 | 0 |
| F02 | Bernoulli | p=1, D=5 | 1 |
| F03 | Bernoulli | p=1/10, D=0 | 0 |
| F04 | Bernoulli | p=1/10, D=1 (single invalid) | 1/10 |
| F05 | Bernoulli | p=1/2, D=3 | 7/8 |
| F06 | IID | p=1/10, f=1/5, N=2 | 99/2500 |
| F07 | IID | p=0, f=1/2, N=10 | 0 |
| F08 | IID | p=1, f=1, N=3 | 1 |
| F09 | IID | p=1/2, f=0, N=7 | 0 |
| F10 | no-repl | N=1000, m=10, D=1 (single invalid) | 1/100 |
| F11 | no-repl | N=1000, m=10, D=0 | 0 |
| F12 | no-repl | N=10, m=3, D=10 (D=N) | 1 |
| F13 | no-repl | N=10, m=0, D=4 (p=0) | 0 |
| F14 | no-repl | N=10, m=10, D=1 (p=1) | 1 |
| F15 | no-repl | N=12, m=3, D=3 | 34/55 |
| F16 | no-repl | N=12, m=3, D=6 | 10/11 |
| F17 | q-model | N=2, K=1, m=1, q=1/2 | 1/4 |
| F18 | q-model | N=10, K=10, m=3, q=0 | 0 |
| F19 | soundness | coverage 1/100, epsilon 1/50 | lower bound 0 |

#84 representative cells (computed exactly, then formatted `f'{v*100:.4f}%'` and compared as strings with `research/sampled-audit/TABLES.md` on main):

| id | inputs | published string |
|---|---|---|
| F20 | N=1000, D=100, m=5 | 41.0168% |
| F21 | N=1000, D=100, m=10 | 65.3072% |
| F22 | N=1000, D=10, m=50 | 40.2689% |
| F23 | N=1000, D=10, m=100 | 65.3072% |
| F24 | N=64, D=35, m=1 | 54.6875% |
| F25 | N=64, D=8, m=4 | 42.1933% |
| F26 | N=256, D=26, m=16 | 82.9485% |

Cost and unit fixtures:

| id | inputs | expected |
|---|---|---|
| F27 | I=1, C=1/100, A=0, F=0, N=1000, P=100, p=1/100, all `gpu_s_per_request`, synthetic | cost 201/100, normalized 201/100, synthetic flagged |
| F28 | same as F27 via incremental R=100 | normalized 201/100 (equals F27) |
| F29 | same via total audited-path R=101, `p*(R-1)` | normalized 201/100 (equals F27) |
| F30 | I in `gpu_s_per_request`, C in `usd_per_request` | MISSING INPUTS, UNIT_MISMATCH, no numeric cost |
| F31 | I in `gpu_s_per_request`, C in `wall_s_per_request` | MISSING INPUTS, UNIT_MISMATCH |
| F32 | P `kind=unknown` (Qwen proof cost), rest known | MISSING INPUTS, UNKNOWN_COST, P in unknowns |
| F33 | C (receipt cost) `kind=unknown` | MISSING INPUTS, UNKNOWN_COST |
| F34 | numeric I with no source | MISSING INPUTS, NO_PROVENANCE |
| F35 | R=23/50 (0.46, #137 decode at batch 1, `R_unit_basis=wall_s_stream`) used as GPU-cost R | MISSING INPUTS, DECODE_RATIO_NOT_GPU_COST |
| F36 | p given in unit `token_fraction` | MISSING INPUTS, TOKEN_FRACTION_NOT_REQUEST_FRACTION |

Policy fixtures (full worksheets; all numbers synthetic except where noted):

| id | class | key inputs | expected |
|---|---|---|---|
| F37 | fleet monitoring | Bernoulli p=1/2, D=3, desired miss 1/4, costs known synthetic | CONDITIONAL, coverage 7/8, miss 1/8 |
| F38 | fleet monitoring | same, desired miss 1/10 | INELIGIBLE, MISS_ABOVE_TARGET |
| F39 | fleet monitoring | `schedule=outcome_adaptive`, lifetime IID formula requested | INELIGIBLE, ADAPTIVE_NOT_IID |
| F40 | vendor-independent proof | p=1, verify_before_action=true, relation stated, costs known synthetic | CONDITIONAL, coverage 1, assumption text includes "only under the selected relation" |
| F41 | vendor-independent proof | p=99/100, verify_before_action=true | INELIGIBLE, SUBSAMPLE_NOT_PROOF |
| F42 | vendor-independent proof | p=1, verify_before_action=false | INELIGIBLE, VERIFY_AFTER_ACTION |
| F43 | hardware-trusting | no-repl N=1000, m=100, D=10, desired miss 1/2, hw trust assumption stated, `individual_guarantee=true` | INELIGIBLE, SUBSAMPLE_NOT_PROOF |
| F44 | hardware-trusting | same with `individual_guarantee=false`, q `q_source=changed_weight_count` | MISSING INPUTS, Q_INFERRED_FROM_WEIGHTS |
| F45 | hardware-trusting | same as F43 with `individual_guarantee=false`, no q, timeout observation counted as wrong answer | MISSING INPUTS, TIMEOUT_NOT_PROOF |

Deterrence is recorded as a field in F37 (P_detect=7/8, loss 8, gain 5, synthetic: condition `7 > 5` true, recorded with the behavioral-assumption text) and does not change any verdict.

Real-world templates: three policy decision templates (one per class) and an empty decision sheet for Shadow are produced alongside. Their penalties, risk tolerance, desired miss probability, relation, retention and enforceability are left blank; the Qwen proof cost P and receipt cost C are `kind=unknown`. They are not registered fixtures and are expected to evaluate to MISSING INPUTS.

## Prior art

- In repo: #84 `research/sampled-audit/` (formulas, protocol, coverage simulation); #126 cost model; #137 plain-inference baseline; `guide/performance.md` cost paragraph. This lane adds no new formula or number; new is the typed eligibility decision, unit/provenance guard and policy templates the issue asks for.
- Outside: probabilistic auditing and spot-checking (risk-limiting audits in election auditing; hypergeometric acceptance sampling, e.g. ANSI/ASQ Z1.4-style attribute sampling); proof-of-retrievability and probabilistic storage audits (PDP, Ateniese et al. 2007) which use the same `1-C(N-D,m)/C(N,m)` coverage; verifiable-ML systems (zkLLM, EZKL, Jolt) that prove each inference in full; TEE-based inference (H100 confidential computing, TDX/SEV-SNP; Phala, Atoma, Nillion) which corresponds to the hardware-trusting class. Units-of-measure checking in software (e.g. dimension-typed libraries like Pint) is the model for the unit guard. Not claimed to be new: the formulas. Not surveyed exhaustively.

## Amendments

(empty at registration)

### Amendment 1 (2026-11-17T22:46:17Z): adversarial fixtures F46 to F135 registered after round 1 review, before any code change

Written after the round 1 review of head `455420464a7d4abb9cb76a09600b4377853eab54`, and after the original code and the original five runs. Both reviews ask for changes to the checker code, not to the registered evidence: https://github.com/wakesync/flashprove/pull/220#issuecomment-6961891535 and https://github.com/wakesync/flashprove/pull/220#issuecomment-6962089424. This entry is committed alone, before any change to `worksheet.py`. It registers new fixtures with their inputs and expected verdicts. It does not change F01 to F45: `fixtures.py`, `run_suite.py` and the six files under `runs/` stay byte-identical.

What was run before this entry was written: each failing input reported in the two reviews was rebuilt and run against a private copy of the reviewed code (outside the repository, same core, memory and time limits; 56 inputs). All of them behave as the reviews report: a CONDITIONAL verdict on the listed incomplete or out-of-domain worksheets, and an uncaught exception on N=0, I=0, m>N, m<0, D>N under the no-replacement scheme, and a non-rational value. The two reviews do not contradict each other on any input. No new code existed when this entry was written, so every expected verdict below is a registration, not an observation.

Disclosure asked for by both reviews: the header line of this file says "Date (UTC): 2026-11-17 21:20". The commit that added this file is `3dc92dc5`, committed 2026-11-17T21:14:31Z; the code commit `9c8e0433` is 21:19:29Z and the runs commit `07b25c66` is 21:20:18Z. The order in history (registration, then code, then runs) is the true one; the prose time in the header is wrong (later than its own commit and later than the code commit). The header line is left as it is and is corrected here.

Known in advance, stated now: the rules below make the fixed checker refuse the registered policy fixtures F37 to F45 as incomplete worksheets (none declares a deterrence state; F40 to F42 have no deadline policy; F37 uses the generic `loss_unit`). Their registered expectations are not edited. Amendment 2, committed separately and also before the code, names each of them with its old and new outcome. F47 to F55 below re-register the same nine cases on completed worksheets.

**Design choices where the reviews left one.**
- An explicit q is usable only by the one registered q formula (fixed-size sample without replacement, with K). Any other use of q is refused (`Q_UNSUPPORTED`). No new formula is added.
- Miss target: one target, compared with the supported bound. `supported_miss = 1 - max(0, coverage - epsilon)` when an epsilon is given, else `1 - coverage`. `MISS_ABOVE_TARGET` when `supported_miss > desired_miss_probability`. For the vendor-independent class without an epsilon no miss target is read (as before). With an epsilon its supported miss is epsilon, a desired miss probability is then required, and it is compared the same way.
- F is an epoch-total cost. It must carry an epoch unit (`gpu_s_per_epoch`, `cpu_s_per_epoch`, `usd_per_epoch`) and is divided by N exactly once. I, P, C, A carry per-request units. One exception, stated openly: an F whose value is exactly zero is accepted in a per-request unit too, because zero is the same quantity in both scopes. This keeps F27 to F36 valid as registered (they use F=0). A nonzero F in a per-request unit is refused (`COST_SCOPE`).
- Wall seconds are not a cost unit. If every cost is in `wall_s_per_request` the costs are refused (`WALL_TIME_NOT_COST`). Wall seconds mixed with another unit stay `UNIT_MISMATCH`, as registered in F31.
- Deterrence: the section is required for every class and must declare `state` as `modeled` or `not_modeled`. `modeled` needs `enforceable_loss`, `cheating_gain` and a non-empty `behavioral_assumptions` text. Loss and gain must share one concrete unit out of `usd`, `gpu_s`, `cpu_s`. The generic `loss_unit` is refused (`LOSS_BASIS_NOT_CONCRETE`); two different units are `UNIT_MISMATCH`. The checker cannot read a free-text source, so the unit is the declared loss basis.
- A numeric `value` must be a string holding an integer, a fraction `a/b` or a plain decimal. A JSON number (integer or binary float) is refused (`BAD_VALUE`), so no binary float is taken as an exact rational.

**Rules added (each refusal is `MISSING INPUTS` unless marked INELIGIBLE).**

1. Sections: the worksheet and each section (`population`, `sampling`, `invalidity`, `distinguishability`, `soundness_treatment`, `costs`, `latency`, `targets`, `deterrence`, `claims`) must be JSON objects and `observations` a list of objects, else `BAD_SECTION` and nothing else is evaluated. Any exception inside the checker is caught and returned as `CHECKER_ERROR`, `MISSING INPUTS`: the checker does not raise on a worksheet.
2. Required text: `relation`, `population.definition`, `latency.deadline_policy`, `soundness_treatment.text`, and `sampling.schedule` (no default), else `MISSING_INPUT`.
3. Required numeric inputs: `population.N`, `sampling.p` or `sampling.m`, `invalidity.D` or `invalidity.f` (not for the vendor-independent class), `targets.desired_miss_probability` (for the vendor-independent class only when an epsilon is given), and, when their key is present, `invalidity.D`, `invalidity.f`, `distinguishability.q`, `distinguishability.K`, `soundness_treatment.epsilon`, `deterrence.enforceable_loss`, `deterrence.cheating_gain`. A key present with a null value is `MISSING_INPUT`. `kind=unknown` on any of them is `UNKNOWN_REQUIRED`. Costs keep `UNKNOWN_COST`.
4. Values: not a string, not a rational, or a zero denominator: `BAD_VALUE`.
5. Domains, checked before any arithmetic: N an integer >= 1; D, m, K integers in [0, N]; p, f, q, desired miss probability and epsilon in [0, 1]; I, P, C, A, F >= 0 and I > 0; R >= 0 for `incremental`, R >= 1 for `total_audited_path`. A count that is not an integer is `NOT_INTEGER`; anything outside its range is `OUT_OF_RANGE`. Counts are never truncated.
6. Booleans: `latency.verify_before_action` and `claims.individual_guarantee` must be JSON booleans, else `NOT_BOOLEAN` (absent: `MISSING_INPUT`). The vendor-independent class needs `verify_before_action` true.
7. Observations: `type` in `timeout`, `refusal`, `proof_rejected`; `counted_as` in `wrong_answer`, `audit_failure`; anything else `BAD_OBSERVATION`. A `timeout` or a `refusal` counted as `wrong_answer` is `TIMEOUT_NOT_PROOF`.
8. q: `q_source=changed_weight_count` stays `Q_INFERRED_FROM_WEIGHTS`. Otherwise a q is accepted only with the fixed-size scheme and a K; if `invalidity.D` is also given it must equal K. Any other q (Bernoulli scheme, no K, K different from D, q together with f) is `Q_UNSUPPORTED`. A K without q is `MISSING_INPUT`. The checker never falls back to the perfect-rejection formula once a q key is present.
9. Formula selection: fixed D with Bernoulli, fixed D with fixed-size, IID f with Bernoulli, q with K and fixed-size. IID f with the fixed-size scheme is `UNSUPPORTED_COMBINATION`.
10. Schedule: `outcome_adaptive` is always `ADAPTIVE_NOT_IID` (INELIGIBLE), with or without the lifetime flag, and no coverage is output.
11. Costs: scope and wall-time rules as in the design choices; an R together with a P is `R_AND_P_BOTH`.
12. Order and output: all refusals above are collected first. `MISS_ABOVE_TARGET` is only evaluated when there is no `MISSING INPUTS` code. A `MISSING INPUTS` result carries no number at all (coverage, miss, supported miss, lower bound, costs and deterrence are null). A coverage class can only be CONDITIONAL with a computed coverage and a computed normalized cost; if either is absent the result is `NO_COVERAGE` or `NO_COST`, `MISSING INPUTS`. No emitted probability is outside [0, 1].
13. Every result lists `not_modelled`: queue and batch effects, and all-traffic trace cost. They are separate unknowns and are not scaled by p.

New codes: `BAD_SECTION`, `CHECKER_ERROR`, `UNKNOWN_REQUIRED`, `BAD_VALUE`, `NOT_INTEGER`, `NOT_BOOLEAN`, `BAD_OBSERVATION`, `Q_UNSUPPORTED`, `UNSUPPORTED_COMBINATION`, `COST_SCOPE`, `WALL_TIME_NOT_COST`, `R_AND_P_BOTH`, `LOSS_BASIS_NOT_CONCRETE`, `NO_COVERAGE`, `NO_COST`. All are `MISSING INPUTS` codes. New output fields: `supported_miss`, `not_modelled`.

**Bases (all numbers synthetic test input, never a forecast).**
- B (fleet monitoring): relation, population definition and epoch rule stated; N=12; Bernoulli p=1/3, `fixed_in_advance`; D=2; soundness text "perfect rejection"; I=2, P=9, C=1/4, A=1/8 in `gpu_s_per_request`, F=6 in `gpu_s_per_epoch`; deadline policy and timeout policy stated, `verify_before_action=false`; desired miss 1/2; deterrence `modeled`, loss 10 and gain 1 in `usd`, assumptions stated; `individual_guarantee=false`.
- V: B with class vendor-independent, p=1, `verify_before_action=true`, no invalidity and no targets section.
- T37 to T45: the registered input of F37 to F45 from `fixtures.py`, unchanged, plus only what the completed schema needs: a deterrence section (`not_modeled`, or for T37 `modeled` with loss 8 and gain 5 in `usd`) and, for T40 to T42, a deadline policy text.

Epoch rule and timeout policy text stay optional. Loss and gain must be >= 0. For the vendor-independent class any q is `Q_UNSUPPORTED` (its coverage statement does not use q). When a q is used, `invalidity.D` is still required and must equal K.

**New registered fixtures.** "MI" is `MISSING INPUTS`. The code set must match exactly. Each row changes only what it names from its base. Expected values were computed from the registered formulas in a separate exact-rational script that does not import the checker, and the small ones were checked by hand; none comes from running the checker.

Controls and completed twins of F37 to F45:

| id | input | expected |
|---|---|---|
| F46 | B unchanged | CONDITIONAL, no code, coverage 5/9, miss 4/9, supported miss 4/9, cost 47/8, normalized 47/16, deterrence product 50/9 |
| F47 | T37 | CONDITIONAL, coverage 7/8, miss 1/8, deterrence product 7 |
| F48 | T38 | INELIGIBLE, MISS_ABOVE_TARGET, coverage 7/8 |
| F49 | T39 | INELIGIBLE, ADAPTIVE_NOT_IID, coverage null |
| F50 | T40 | CONDITIONAL, coverage 1, assumption text includes "only under the selected relation" |
| F51 | T41 | INELIGIBLE, SUBSAMPLE_NOT_PROOF |
| F52 | T42 | INELIGIBLE, VERIFY_AFTER_ACTION |
| F53 | T43 | INELIGIBLE, SUBSAMPLE_NOT_PROOF |
| F54 | T44 | MI, Q_INFERRED_FROM_WEIGHTS |
| F55 | T45 | MI, TIMEOUT_NOT_PROOF |

Must-fix 1, required schema and unknowns (opus 5, 6; astra 1):

| id | input | expected |
|---|---|---|
| F56 | B, p `kind=unknown`, value null | MI, UNKNOWN_REQUIRED |
| F57 | B, desired miss probability `kind=unknown` | MI, UNKNOWN_REQUIRED |
| F58 | B, D `kind=unknown` | MI, UNKNOWN_REQUIRED |
| F59 | B, `invalidity.D` present and null | MI, MISSING_INPUT |
| F60 | B, N `kind=unknown` | MI, UNKNOWN_REQUIRED |
| F61 | B, no `population.definition` | MI, MISSING_INPUT |
| F62 | B, no `latency.deadline_policy` | MI, MISSING_INPUT |
| F63 | B, no `deterrence` section | MI, MISSING_INPUT |
| F64 | B, deterrence `modeled` without `behavioral_assumptions` | MI, MISSING_INPUT |
| F65 | B, deterrence without `state` | MI, MISSING_INPUT |
| F66 | B, deterrence `state=not_modeled` only | CONDITIONAL, coverage 5/9, deterrence null |
| F67 | B, fixed-size m=3 with IID f=1/4 (no D) | MI, UNSUPPORTED_COMBINATION |
| F68 | V unchanged | CONDITIONAL, coverage 1, normalized 95/16 |
| F69 | V, `verify_before_action` null | MI, NOT_BOOLEAN |
| F70 | V, `verify_before_action` the string "false" | MI, NOT_BOOLEAN |
| F71 | B, `verify_before_action` the string "false" | MI, NOT_BOOLEAN |
| F72 | B, `individual_guarantee` the string "yes" | MI, NOT_BOOLEAN |
| F73 | B, observation `refusal` counted as `wrong_answer` | MI, TIMEOUT_NOT_PROOF |
| F74 | B, observation type `outage` counted as `audit_failure` | MI, BAD_OBSERVATION |
| F75 | B, no `sampling.schedule` | MI, MISSING_INPUT |
| F76 | B, observation `timeout` counted as `audit_failure` | CONDITIONAL, coverage 5/9 |
| F77 | B, epsilon `kind=unknown` | MI, UNKNOWN_REQUIRED |
| F78 | B, `sampling` is a list | MI, BAD_SECTION |

Must-fix 2, numeric domains (opus 1; astra 2; the crashes in the nonblocking lists):

| id | input | expected |
|---|---|---|
| F79 | B, D=13 (N=12) | MI, OUT_OF_RANGE |
| F80 | B, D=5/2 | MI, NOT_INTEGER |
| F81 | B, D=-1 | MI, OUT_OF_RANGE |
| F82 | B, N=0 | MI, OUT_OF_RANGE |
| F83 | B, N=-2 | MI, OUT_OF_RANGE |
| F84 | B, N=25/2 | MI, NOT_INTEGER |
| F85 | B, fixed-size m=13 | MI, OUT_OF_RANGE |
| F86 | B, fixed-size m=-1 | MI, OUT_OF_RANGE |
| F87 | B, fixed-size m=7/2 | MI, NOT_INTEGER |
| F88 | B, fixed-size m=3, D=13 | MI, OUT_OF_RANGE |
| F89 | B, p=-1/2 | MI, OUT_OF_RANGE |
| F90 | B, p=3/2 | MI, OUT_OF_RANGE |
| F91 | B, IID f=2 (no D) | MI, OUT_OF_RANGE |
| F92 | B, desired miss probability 2 | MI, OUT_OF_RANGE |
| F93 | B, epsilon=-1 | MI, OUT_OF_RANGE |
| F94 | B, epsilon=2 | MI, OUT_OF_RANGE |
| F95 | B, P=-9 | MI, OUT_OF_RANGE |
| F96 | B, I=0 | MI, OUT_OF_RANGE |
| F97 | B, P value the string "garbage" | MI, BAD_VALUE |
| F98 | B, P value the string "1/0" | MI, BAD_VALUE |
| F99 | B, p value the JSON float 0.1 | MI, BAD_VALUE |
| F100 | B, N value the JSON integer 12 | MI, BAD_VALUE |
| F101 | B with incremental R=-1 (no P), basis `gpu_s/gpu_s` | MI, OUT_OF_RANGE |
| F102 | B with total audited-path R=1/2 (no P) | MI, OUT_OF_RANGE |
| F103 | B, IID f=1/4 (no D) | CONDITIONAL, coverage 5777672071535/8916100448256 |
| F104 | B, fixed-size m=4, D=2 | CONDITIONAL, coverage 19/33, miss 14/33, normalized 47/16 |

Must-fix 3, an explicit q is never dropped (opus 2; astra 3). "q-fixed" is B with fixed-size m=4, D=2:

| id | input | expected |
|---|---|---|
| F105 | B (Bernoulli), q=0, K=2 | MI, Q_UNSUPPORTED |
| F106 | q-fixed, q `kind=unknown`, K=2 | MI, UNKNOWN_REQUIRED |
| F107 | q-fixed, q=0, no K | MI, Q_UNSUPPORTED |
| F108 | B (Bernoulli), q=1/100, no K | MI, Q_UNSUPPORTED |
| F109 | q-fixed, q=0, K=2 | INELIGIBLE, MISS_ABOVE_TARGET, coverage 0, miss 1 |
| F110 | q-fixed, q=1/2, K=2, desired miss 3/4 | CONDITIONAL, coverage 41/132, miss 91/132 |
| F111 | q-fixed, q=1/2, K=3 (D=2) | MI, Q_UNSUPPORTED |
| F112 | q-fixed, K=2, no q | MI, MISSING_INPUT |
| F113 | V, q=1/2, K=2 | MI, Q_UNSUPPORTED |
| F114 | q-fixed, q=3/2, K=2 | MI, OUT_OF_RANGE |

Must-fix 4, the soundness bound reaches the verdict (opus 3; astra 4):

| id | input | expected |
|---|---|---|
| F115 | B, epsilon=1/2 | INELIGIBLE, MISS_ABOVE_TARGET, coverage 5/9, lower bound 1/18, supported miss 17/18 |
| F116 | B, epsilon=1/100 | CONDITIONAL, lower bound 491/900, supported miss 409/900, deterrence product 491/90 |
| F117 | B, epsilon=1/18 (boundary) | CONDITIONAL, lower bound 1/2, supported miss 1/2 |
| F118 | T37, epsilon=9/10 | INELIGIBLE, MISS_ABOVE_TARGET, coverage 7/8, lower bound 0, supported miss 1 |
| F119 | V, epsilon=1/100, no targets section | MI, MISSING_INPUT |
| F120 | V, epsilon=1/100, desired miss 1/2 | CONDITIONAL, coverage 1, lower bound 99/100, supported miss 1/100 |
| F121 | V, epsilon=1/2, desired miss 1/4 | INELIGIBLE, MISS_ABOVE_TARGET, lower bound 1/2, supported miss 1/2 |

Must-fix 5, no CONDITIONAL without a computed coverage (opus 4; astra 1). F67 above is the IID f under the fixed-size scheme:

| id | input | expected |
|---|---|---|
| F122 | B, `schedule=outcome_adaptive`, no lifetime flag | INELIGIBLE, ADAPTIVE_NOT_IID, coverage null |
| F123 | B, `schedule=outcome_adaptive`, IID f=1/4 (no D), no lifetime flag | INELIGIBLE, ADAPTIVE_NOT_IID, coverage null |

Must-fix 6, cost scope and loss basis (astra 5; opus nonblocking on wall seconds). F46 is the nonzero epoch-total F in the plain convention:

| id | input | expected |
|---|---|---|
| F124 | B, F=6 in `gpu_s_per_request` | MI, COST_SCOPE |
| F125 | B via incremental R=9/2 (no P), basis `gpu_s/gpu_s`, F=6 per epoch | CONDITIONAL, coverage 5/9, normalized 47/16 |
| F126 | B via total audited-path R=11/2 (no P), F=6 per epoch | CONDITIONAL, coverage 5/9, normalized 47/16 |
| F127 | B, F=6 in `usd_per_epoch` | MI, UNIT_MISMATCH |
| F128 | B, I=2 in `gpu_s_per_epoch` | MI, COST_SCOPE |
| F129 | B, I, P, C, A and F=0 all in `wall_s_per_request` | MI, WALL_TIME_NOT_COST |
| F130 | B, incremental R=9/2 given together with P | MI, R_AND_P_BOTH |
| F131 | B, loss and gain in `loss_unit` | MI, LOSS_BASIS_NOT_CONCRETE |
| F132 | B, loss in `usd`, gain in `gpu_s` | MI, UNIT_MISMATCH |
| F133 | B, loss `kind=unknown` | MI, UNKNOWN_REQUIRED |
| F134 | B, loss=-1 | MI, OUT_OF_RANGE |
| F135 | B via incremental R=9/2, F=6 in `gpu_s_per_request` | MI, COST_SCOPE |

`NO_COVERAGE`, `NO_COST` and `CHECKER_ERROR` are backstops. No input is known that reaches them once the rules above hold, so no fixture is registered for them.

**Runs.** F01 to F45 are evaluated from the unchanged `fixtures.py`; F46 to F135 from a new file `fixtures_r1.py`; both by a new runner `run_suite_r1.py`. Five runs, same limits as before (`taskset -c 4-5`, `prlimit --as=536870912`, `timeout 60`), into new files `runs-r1/run-1.json` to `run-5.json`, each written once. The three blank templates (`templates.json`, unchanged) are evaluated again into `runs-r1/templates.json`; expected `MISSING INPUTS` for each. The original files under `runs/` are not touched and remain the evidence of the reviewed head. Debug rule: no fixture F01 to F135 is run against the new code before run 1. Before these runs the new code may be exercised only on debug inputs that are not F01 to F135: DBG-04 onward, in `debug_fixtures_r1.py`, on a different base (N=7, p=1/5, D=3, other costs), which repeat the same kinds of change as the rows above with other numbers, plus malformed inputs generated from that debug base. Debug inputs are not in any registered total.

**Acceptance for the amended suite.** PASS only if, in each of the five runs, every one of F46 to F135 matches (verdict, exact code set, registered values), F01 to F36 match their original registration, F37 to F45 give exactly the outcome registered in Amendment 2, and the five report digests are equal. Anything else is FAIL. The original PASS (45 of 45 at the reviewed code) is reported separately and is not replaced. Hard stop for this amendment: 2026-11-18T00:05:00Z; at the stop, what is complete is published as PARTIAL or FAIL without editing an expectation.

Still not established, and not changed by this amendment: feasibility of any real policy, any cost, any rate, any guarantee. The decision sheet stays empty.


### Amendment 2 (2026-11-17T22:53:44Z): changed registration for F37 to F45, stated before the code that causes it

Written after Amendment 1 and before any change to `worksheet.py`. The rules registered in Amendment 1 change what the checker returns for nine of the original fixtures. Their original expectations in `fixtures.py` and in the table above are not edited, and the original run files keep showing the original outcome at the reviewed code. This entry names each fixture, its old registered outcome, the outcome registered for the fixed checker, and the reason.

Reason, common to all nine: the original policy worksheets are incomplete under the schema the reviews ask the checker to enforce. F38 to F45 have no `deterrence` section, F37 has one without a declared `state`, and F40 to F42 have no `latency.deadline_policy`. A missing deterrence section or deadline policy must now be refused (must-fix 1), so the fixed checker returns `MISSING INPUTS` for all nine and outputs no number for them.

| id | old registered outcome (reviewed code) | outcome registered for the fixed checker | completed twin |
|---|---|---|---|
| F37 | CONDITIONAL, no code, coverage 7/8, miss 1/8 | MISSING INPUTS, MISSING_INPUT, no number | F47 |
| F38 | INELIGIBLE, MISS_ABOVE_TARGET, coverage 7/8 | MISSING INPUTS, MISSING_INPUT, no number | F48 |
| F39 | INELIGIBLE, ADAPTIVE_NOT_IID | MISSING INPUTS, ADAPTIVE_NOT_IID and MISSING_INPUT | F49 |
| F40 | CONDITIONAL, no code, coverage 1 | MISSING INPUTS, MISSING_INPUT, no number | F50 |
| F41 | INELIGIBLE, SUBSAMPLE_NOT_PROOF | MISSING INPUTS, MISSING_INPUT and SUBSAMPLE_NOT_PROOF | F51 |
| F42 | INELIGIBLE, VERIFY_AFTER_ACTION | MISSING INPUTS, MISSING_INPUT and VERIFY_AFTER_ACTION | F52 |
| F43 | INELIGIBLE, SUBSAMPLE_NOT_PROOF | MISSING INPUTS, MISSING_INPUT and SUBSAMPLE_NOT_PROOF | F53 |
| F44 | MISSING INPUTS, Q_INFERRED_FROM_WEIGHTS | MISSING INPUTS, MISSING_INPUT and Q_INFERRED_FROM_WEIGHTS | F54 |
| F45 | MISSING INPUTS, TIMEOUT_NOT_PROOF | MISSING INPUTS, MISSING_INPUT and TIMEOUT_NOT_PROOF | F55 |

Consequences, stated now. Against their original registration, F37 to F45 will not match at the fixed code: 36 of the original 45 fixtures (F01 to F36) are expected to still match, 9 are changed registrations. The amended suite counts F37 to F45 as matching only if they give exactly the outcome in the third column. The behaviour each of them was written to test (the coverage verdict, the miss target, the adaptive refusal, the proof class rules, the q and timeout refusals) is re-registered on completed worksheets as F47 to F55 in Amendment 1, with the original verdict and codes. RESULTS.md reports this as a changed registration, not as a pass of the original expectations. F01 to F36 are expected to be unaffected; if any of them changes, that is a FAIL of the amended suite, not a further amendment.


### Amendment 3 (2026-11-17T23:14:03Z): one rule found by the debug inputs, stated before the code is committed

Written after Amendments 1 and 2, after the new code was written and run on the debug inputs only (DBG-04 onward and the inputs generated from the debug base, as the debug rule of Amendment 1 allows), and before the code commit. No fixture F01 to F135 had been run against the new code.

The generated debug inputs showed one acceptance that neither review lists: a `source` that is not text (a number, a boolean or an object) was taken as provenance. Rule added: `source` must be a non-empty text, else `NO_PROVENANCE` (the code that the original registration already uses for a missing source). No registered fixture has a non-text source, so no expectation of F01 to F135 changes. No registered fixture is added for it: it is covered by debug inputs DBG-16 and DBG-17 only, which is weaker than a registered fixture and is said so in RESULTS.md.


### Amendment 4 (2026-11-18T01:39:53Z): a proof rejection counted as a wrong answer is refused; fixtures F136 to F141 registered after round 2 review, before any code change

Written after the round 2 review of head `c66c4b2e924d621be173d9979bd4a6aef3d07445`, and after the code and the runs of both earlier rounds (original code `9c8e0433` with runs `07b25c66`; fixed code `b1477914` with runs `8d095b7c`). Round 2 was split. One review approves with no must-fix: https://github.com/wakesync/flashprove/pull/220#issuecomment-6964830279. One requests a change with one must-fix: https://github.com/wakesync/flashprove/pull/220#issuecomment-6964807245. This entry is committed alone, before any change to `worksheet.py`. It does not change F01 to F135: `fixtures.py`, `fixtures_r1.py`, `run_suite.py`, `run_suite_r1.py` and every file under `runs/` and `runs-r1/` stay byte-identical.

The finding, as that reviewer's descriptive finding (second link above): rule 7 of Amendment 1 refuses a `timeout` or a `refusal` counted as `wrong_answer`, but accepts a `proof_rejected` counted as `wrong_answer`. A verifier rejecting a proof does not establish that the delivered answer was wrong: a correct answer with a malformed or corrupted proof is rejected too.

What was run before this entry was written: the reviewer's input was rebuilt from the comment (a complete fleet worksheet with N=17, Bernoulli p=2/5, D=4) and run against the reviewed checker, taken from commit `c66c4b2e` into a private temporary directory outside the repository (cores 4-5, same memory and time limits). It behaves as the review reports. With the single observation `proof_rejected` counted as `wrong_answer` the reviewed checker returns CONDITIONAL with no code. `timeout` and `refusal` counted as `wrong_answer` are `MISSING INPUTS` with `TIMEOUT_NOT_PROOF`. All three types counted as `audit_failure` are accepted. No new code existed when this entry was written, so the expected verdicts of F136 to F140 below are registrations, not observations. F141 is different and says so.

**Design choice.** Plain refusal. No "explicit basis" mechanism and no new input field: the worksheet has no input that could establish that the delivered answer violates the relation, and a free-text basis would only be checked for being non-empty. Code: a new code `PROOF_REJECTION_NOT_WRONG_ANSWER`, verdict `MISSING INPUTS`. Why `MISSING INPUTS` and not INELIGIBLE: it is the same kind of defect as `TIMEOUT_NOT_PROOF` in rule 7 (an observation classified without support, so the worksheet as written cannot be evaluated), and a `MISSING INPUTS` result carries no number at all, while an INELIGIBLE result keeps its coverage. Why a new code and not `TIMEOUT_NOT_PROOF`: a proof rejection is not a timeout, and the code is what a reader sees.

**Rule added (rule 7 of Amendment 1, extended).** A `proof_rejected` counted as `wrong_answer` is `PROOF_REJECTION_NOT_WRONG_ANSWER`, `MISSING INPUTS`. A `proof_rejected` counted as `audit_failure` stays accepted. Each observation is checked on its own: one refused observation is enough, and a worksheet with a refused timeout and a refused proof rejection carries both codes. The rule does not depend on the policy class. Nothing else changes: no other rule, formula or output field.

No fixture F01 to F135 contains a `proof_rejected` observation (they use `timeout`, `refusal` and the invalid type `outage`), so no registered expectation is expected to change. If any of them gives another outcome at the new code than the one registered for it, that is a FAIL of this amendment's suite, not a further amendment.

Not made, stated so that the registration is complete: the behaviour changes that the round 2 comments list as nonblocking (an allow-list for `q_source`, a size limit on N, ASCII-only digits in a value, a stricter rule for a zero F). The checker's behaviour on those inputs is unchanged by this amendment.

**New registered fixtures.** B and V are the bases of Amendment 1. "MI" is `MISSING INPUTS`. The code set must match exactly, and an MI result carries no number. Each row changes only what it names from its base.

| id | input | expected |
|---|---|---|
| F136 | B, one observation: `proof_rejected` counted as `wrong_answer` | MI, PROOF_REJECTION_NOT_WRONG_ANSWER |
| F137 | B, one observation: `proof_rejected` counted as `audit_failure` (positive control) | CONDITIONAL, no code, coverage 5/9, miss 4/9, normalized 47/16 |
| F138 | B, two observations: `proof_rejected` counted as `audit_failure`, then `proof_rejected` counted as `wrong_answer` | MI, PROOF_REJECTION_NOT_WRONG_ANSWER |
| F139 | B, two observations: `timeout` counted as `wrong_answer`, then `proof_rejected` counted as `wrong_answer` | MI, PROOF_REJECTION_NOT_WRONG_ANSWER and TIMEOUT_NOT_PROOF |
| F140 | V, one observation: `proof_rejected` counted as `wrong_answer` | MI, PROOF_REJECTION_NOT_WRONG_ANSWER |
| F141 | B, the `source` of `population.N` is the number 7 | MI, NO_PROVENANCE |

The values of F137 are those registered for B in F46 (an accepted observation changes no number). F141 covers the rule of Amendment 3 (a `source` that is not text), for which the approving round 2 comment asks for a registered fixture. F141 is not a prediction: the rule is already in the code at `b1477914`, and Amendment 3 records that the debug inputs DBG-16 and DBG-17 cover the same refusal on another base. It is registered so that the suite goes red if the rule is lost.

**Runs.** F136 to F141 live in a new file `fixtures_r2.py` and are run by a new runner `run_suite_r2.py`, together with F01 to F45 from the unchanged `fixtures.py` and F46 to F135 from the unchanged `fixtures_r1.py`. Five runs, same limits as before (`taskset -c 4-5`, `prlimit --as=536870912`, `timeout 60`), into new files `runs-r2/run-1.json` to `run-5.json`, each written once. The three blank templates (`templates.json`, unchanged) are evaluated again into `runs-r2/templates.json`; expected `MISSING INPUTS` for each. The files under `runs/` and `runs-r1/` are not touched and remain the evidence of the earlier heads. Debug rule: no fixture F01 to F141 is run against the new code before run 1. Before these runs the new code may be exercised only on debug inputs DBG-18 onward, in a new file `debug_fixtures_r2.py`, on a base that no registered fixture uses (N=9, p=1/4, D=2, other costs). Debug inputs are not in any registered total.

**Acceptance for this suite.** PASS only if, in each of the five runs, F136 to F141 match (verdict, exact code set, registered values), F46 to F135 match their registration, F01 to F36 match their original registration, F37 to F45 give exactly the outcome registered in Amendment 2, and the five report digests are equal. Anything else is FAIL. The earlier results (45 of 45 at the reviewed code; the amended suite at the round 1 fixed code) are reported separately and are not replaced. Hard stop for this amendment: 2026-11-18T02:45:00Z; at the stop, what is complete is published as PARTIAL or FAIL without editing an expectation.

Still not established, and not changed by this amendment: feasibility of any real policy, any cost, any rate, any guarantee. The decision sheet holds no policy value.
