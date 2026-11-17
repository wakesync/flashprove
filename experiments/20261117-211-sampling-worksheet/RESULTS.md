# RESULTS: 20261117-211-sampling-worksheet

Issue #211 (part of #7). Verdict against the registered threshold: **PASS**. Measured, unreplicated. Deterministic: all five registered runs matched 45 of 45 fixtures and gave the same report digest, so there is no spread to report.

What this is: an offline checker (`worksheet.py`, standard library, exact rationals) that takes one sampling policy worksheet and returns CONDITIONAL, INELIGIBLE or MISSING INPUTS, with the codes that decided it. It is not a launch recommendation, it adds no formula, it estimates no cost, and it recommends no sampling rate. Every number in the fixtures is synthetic test input unless a main path is named next to it.

## Runs

| run | matched | report sha256 | file |
|---|---|---|---|
| 1 | 45/45 | `0e08831366510def9ce75ba0670a487a139aed74c58831e15d10fb01a8319a39` | [runs/run-1.json](runs/run-1.json) |
| 2 | 45/45 | same | [runs/run-2.json](runs/run-2.json) |
| 3 | 45/45 | same | [runs/run-3.json](runs/run-3.json) |
| 4 | 45/45 | same | [runs/run-4.json](runs/run-4.json) |
| 5 | 45/45 | same | [runs/run-5.json](runs/run-5.json) |

Command per run: `taskset -c 4-5 prlimit --as=536870912 timeout 60 python3 experiments/20261117-211-sampling-worksheet/run_suite.py --run K --out experiments/20261117-211-sampling-worksheet/runs/run-K.json` (refuses to overwrite). Code was committed (`9c8e043`) before the first run; the PREREG (`3dc92dc`) before any code. No amendment. Before the registered runs only the debug fixtures DBG-01 to DBG-03 were run (`debug_fixtures.py`, outside the suite, as the PREREG allows). No time is reported.

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

`templates.json` has one blank template per class; [runs/templates.json](runs/templates.json) shows each evaluates to MISSING INPUTS (codes NO_RELATION, MISSING_INPUT, UNKNOWN_COST with `costs.P` and `costs.C` listed as unknown; the hardware-trusting one also NO_HW_TRUST_ASSUMPTION). [DECISION-SHEET.md](DECISION-SHEET.md) is empty on purpose: penalties, risk tolerance, desired miss probability, relation, retention and enforceability are not filled in.

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
- Unreplicated; no independent review yet.
