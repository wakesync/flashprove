# U2: sampling coverage tables

Conditional on fixed, provably invalid committed units and perfect rejection. These are not measured model-substitution probabilities. Cost fraction is variable equal-cost unit work only, excluding receipts, traces, setup and dependencies. Displayed values are rounded: 100.0000% can be slightly below one; raw probabilities are retained in registered.json.

## U2: plain request table (N=1000, exact calculation)

Window detection probability in percent. "All" includes whole-model, ablated-layer and quantized-layer strategies ONLY if every request is invalid under the pinned relation. Blind predictor fixes 100 invalid requests before an independent draw. Leaked challenge chooses only unsampled requests; full coverage leaves none to cheat on.

| Fraction proven | All invalid | Swap 10% | Swap 1% | One request | Blind predictor 10% | Leaked challenge |
|---|---|---|---|---|---|---|
| 0.1% | 100.0000% | 10.0000% | 1.0000% | 0.1000% | 10.0000% | 0.0000% |
| 0.5% | 100.0000% | 41.0168% | 4.9106% | 0.5000% | 41.0168% | 0.0000% |
| 1% | 100.0000% | 65.3072% | 9.6032% | 1.0000% | 65.3072% | 0.0000% |
| 5% | 100.0000% | 99.5524% | 40.2689% | 5.0000% | 99.5524% | 0.0000% |
| 10% | 100.0000% | 99.9985% | 65.3072% | 10.0000% | 99.9985% | 0.0000% |
| 100% | 100.0000% | 100.0000% | 100.0000% | 100.0000% | 100.0000% | 0.0000% |

## U2: layer table (N=64, exact calculation)

One request; fixed planted local violations, not a claim that weight edits or engine swaps necessarily create this many violations.

| Units proven | Fraction | whole_model | ablated_17_51 | quantized_8 | one_layer |
|---|---|---|---|---|---|
| 1 | 1.5625% | 100.0000% | 54.6875% | 12.5000% | 1.5625% |
| 2 | 3.1250% | 100.0000% | 79.8611% | 23.6111% | 3.1250% |
| 4 | 6.2500% | 100.0000% | 96.2619% | 42.1933% | 6.2500% |
| 8 | 12.5000% | 100.0000% | 99.9030% | 67.9069% | 12.5000% |
| 16 | 25.0000% | 100.0000% | 100.0000% | 91.4746% | 25.0000% |
| 32 | 50.0000% | 100.0000% | 100.0000% | 99.7624% | 50.0000% |
| 64 | 100.0000% | 100.0000% | 100.0000% | 100.0000% | 100.0000% |

## U2: token table (N=256, exact calculation)

One request; fixed planted local violations, not a claim that weight edits or engine swaps necessarily create this many violations.

| Units proven | Fraction | all_tokens | 26_tokens | one_token |
|---|---|---|---|---|
| 1 | 0.3906% | 100.0000% | 10.1562% | 0.3906% |
| 4 | 1.5625% | 100.0000% | 35.0185% | 1.5625% |
| 16 | 6.2500% | 100.0000% | 82.9485% | 6.2500% |
| 64 | 25.0000% | 100.0000% | 99.9643% | 25.0000% |
| 256 | 100.0000% | 100.0000% | 100.0000% | 100.0000% |

## U2: all simulated cells

Five independent seeded runs, each 10000 windows per cell. All values below are probabilities, not percentages. SD is the sample SD across five rates. Registered checks apply to every seed separately. Full raw hit counts are in registered.json.

| Family | Strategy | m/N | Exact | Median | SD | Min | Max | Verdict |
|---|---|---|---|---|---|---|---|---|
| request | whole_model | 1/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | whole_model | 5/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | whole_model | 10/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | whole_model | 50/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | whole_model | 100/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | whole_model | 1000/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | swap_10pct | 1/1000 | 0.100000 | 0.100100 | 0.002139 | 0.097100 | 0.102600 | PASS |
| request | swap_10pct | 5/1000 | 0.410168 | 0.412000 | 0.002079 | 0.408000 | 0.412500 | PASS |
| request | swap_10pct | 10/1000 | 0.653072 | 0.654600 | 0.001927 | 0.650700 | 0.655600 | PASS |
| request | swap_10pct | 50/1000 | 0.995524 | 0.995900 | 0.000635 | 0.994800 | 0.996400 | PASS |
| request | swap_10pct | 100/1000 | 0.999985 | 1.000000 | 0.000055 | 0.999900 | 1.000000 | PASS |
| request | swap_10pct | 1000/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | swap_1pct | 1/1000 | 0.010000 | 0.009800 | 0.000630 | 0.009700 | 0.011200 | PASS |
| request | swap_1pct | 5/1000 | 0.049106 | 0.049500 | 0.001193 | 0.047800 | 0.050400 | PASS |
| request | swap_1pct | 10/1000 | 0.096032 | 0.096600 | 0.004190 | 0.095200 | 0.105500 | PASS |
| request | swap_1pct | 50/1000 | 0.402689 | 0.402200 | 0.005375 | 0.399300 | 0.410400 | PASS |
| request | swap_1pct | 100/1000 | 0.653072 | 0.653600 | 0.003095 | 0.650300 | 0.658400 | PASS |
| request | swap_1pct | 1000/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | single_request | 1/1000 | 0.001000 | 0.001200 | 0.000415 | 0.000400 | 0.001400 | PASS |
| request | single_request | 5/1000 | 0.005000 | 0.004900 | 0.000650 | 0.004100 | 0.005700 | PASS |
| request | single_request | 10/1000 | 0.010000 | 0.009800 | 0.001635 | 0.007100 | 0.011200 | PASS |
| request | single_request | 50/1000 | 0.050000 | 0.050500 | 0.002053 | 0.046900 | 0.052400 | PASS |
| request | single_request | 100/1000 | 0.100000 | 0.101300 | 0.003121 | 0.095400 | 0.103300 | PASS |
| request | single_request | 1000/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | ablated_all_requests | 1/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | ablated_all_requests | 5/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | ablated_all_requests | 10/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | ablated_all_requests | 50/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | ablated_all_requests | 100/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | ablated_all_requests | 1000/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | quantized_all_requests | 1/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | quantized_all_requests | 5/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | quantized_all_requests | 10/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | quantized_all_requests | 50/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | quantized_all_requests | 100/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | quantized_all_requests | 1000/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | blind_predictor_10pct | 1/1000 | 0.100000 | 0.102300 | 0.002942 | 0.097400 | 0.104400 | PASS |
| request | blind_predictor_10pct | 5/1000 | 0.410168 | 0.412800 | 0.003735 | 0.409000 | 0.419200 | PASS |
| request | blind_predictor_10pct | 10/1000 | 0.653072 | 0.653800 | 0.004141 | 0.648600 | 0.659800 | PASS |
| request | blind_predictor_10pct | 50/1000 | 0.995524 | 0.995900 | 0.000701 | 0.994600 | 0.996400 | PASS |
| request | blind_predictor_10pct | 100/1000 | 0.999985 | 1.000000 | 0.000045 | 0.999900 | 1.000000 | PASS |
| request | blind_predictor_10pct | 1000/1000 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| request | leaked_challenge | 1/1000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | PASS |
| request | leaked_challenge | 5/1000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | PASS |
| request | leaked_challenge | 10/1000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | PASS |
| request | leaked_challenge | 50/1000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | PASS |
| request | leaked_challenge | 100/1000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | PASS |
| request | leaked_challenge | 1000/1000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | PASS |
| layer | whole_model | 1/64 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| layer | whole_model | 2/64 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| layer | whole_model | 4/64 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| layer | whole_model | 8/64 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| layer | whole_model | 16/64 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| layer | whole_model | 32/64 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| layer | whole_model | 64/64 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| layer | ablated_17_51 | 1/64 | 0.546875 | 0.546000 | 0.002544 | 0.544200 | 0.550500 | PASS |
| layer | ablated_17_51 | 2/64 | 0.798611 | 0.801500 | 0.004044 | 0.795500 | 0.804600 | PASS |
| layer | ablated_17_51 | 4/64 | 0.962619 | 0.962700 | 0.001430 | 0.961200 | 0.964700 | PASS |
| layer | ablated_17_51 | 8/64 | 0.999030 | 0.999100 | 0.000251 | 0.998700 | 0.999400 | PASS |
| layer | ablated_17_51 | 16/64 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| layer | ablated_17_51 | 32/64 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| layer | ablated_17_51 | 64/64 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| layer | quantized_8 | 1/64 | 0.125000 | 0.128200 | 0.003694 | 0.122300 | 0.130400 | PASS |
| layer | quantized_8 | 2/64 | 0.236111 | 0.232200 | 0.002869 | 0.231600 | 0.238600 | PASS |
| layer | quantized_8 | 4/64 | 0.421933 | 0.428800 | 0.005473 | 0.417700 | 0.431900 | PASS |
| layer | quantized_8 | 8/64 | 0.679069 | 0.683800 | 0.004353 | 0.678500 | 0.689000 | PASS |
| layer | quantized_8 | 16/64 | 0.914746 | 0.915000 | 0.002060 | 0.912100 | 0.916700 | PASS |
| layer | quantized_8 | 32/64 | 0.997624 | 0.998200 | 0.000356 | 0.997700 | 0.998700 | PASS |
| layer | quantized_8 | 64/64 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| layer | one_layer | 1/64 | 0.015625 | 0.014800 | 0.001165 | 0.013500 | 0.016500 | PASS |
| layer | one_layer | 2/64 | 0.031250 | 0.032300 | 0.001292 | 0.030500 | 0.033300 | PASS |
| layer | one_layer | 4/64 | 0.062500 | 0.064600 | 0.003815 | 0.057700 | 0.067800 | PASS |
| layer | one_layer | 8/64 | 0.125000 | 0.124400 | 0.001994 | 0.120500 | 0.125300 | PASS |
| layer | one_layer | 16/64 | 0.250000 | 0.249200 | 0.006630 | 0.239400 | 0.255900 | PASS |
| layer | one_layer | 32/64 | 0.500000 | 0.504800 | 0.005427 | 0.495100 | 0.509500 | PASS |
| layer | one_layer | 64/64 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| token | all_tokens | 1/256 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| token | all_tokens | 4/256 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| token | all_tokens | 16/256 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| token | all_tokens | 64/256 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| token | all_tokens | 256/256 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| token | 26_tokens | 1/256 | 0.101562 | 0.102400 | 0.002823 | 0.099600 | 0.107400 | PASS |
| token | 26_tokens | 4/256 | 0.350185 | 0.347400 | 0.005855 | 0.340400 | 0.353100 | PASS |
| token | 26_tokens | 16/256 | 0.829485 | 0.830200 | 0.004164 | 0.822800 | 0.834100 | PASS |
| token | 26_tokens | 64/256 | 0.999643 | 0.999800 | 0.000200 | 0.999600 | 1.000000 | PASS |
| token | 26_tokens | 256/256 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
| token | one_token | 1/256 | 0.003906 | 0.004100 | 0.000472 | 0.003300 | 0.004500 | PASS |
| token | one_token | 4/256 | 0.015625 | 0.015000 | 0.001431 | 0.013900 | 0.017300 | PASS |
| token | one_token | 16/256 | 0.062500 | 0.062400 | 0.003548 | 0.059100 | 0.067700 | PASS |
| token | one_token | 64/256 | 0.250000 | 0.248900 | 0.002669 | 0.246600 | 0.253600 | PASS |
| token | one_token | 256/256 | 1.000000 | 1.000000 | 0.000000 | 1.000000 | 1.000000 | PASS |
