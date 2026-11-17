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
