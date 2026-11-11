# RESULTS: 20261111-35-qk-rmsnorm

Issue #35, lane qknorm35. Verdict vs PREREG: **PASS, measured, unreplicated.** Research prototype on synthetic inputs, CPU only. Not Qwen support, not a model claim, not a headline.

Code: `research/operators/qwen_qk_norm/` (README there has the relation, the no-wrap argument, what is and is not bound). Raw data: `runs/`.

## Plain-language summary

Per-head q/k RMSNorm (as in Qwen full attention: normalise each head's q or k vector by its root-mean-square plus epsilon, then multiply by a learned per-channel weight) is now written as constraints on the bounded CPU proof of PR #67, with exact integer square root and division checked by range-checked residuals instead of a lookup table. At head dim 16 and 256, every honest proof verified, every one of 420 registered hostile sub-cases per build was rejected (240 of them complete malicious proofs), in a release and a UBSan build, and the fixed-point output is within 2e-3 relative L2 error of a float64 RMSNorm on every head tested. **The proof says the norm was computed correctly from the inputs and gains in the statement; it says nothing about where those inputs and gains came from.**

## Verdict per registered criterion

| criterion (PREREG) | result | source |
|---|---|---|
| (a) honest accept, 5 distributions x 10 seeds x 2 arms | 100/100 release, 100/100 UBSan | `runs/summary.json` `honest_accepted` |
| (b) hostile reject, every sub-case, every seed, both builds | 420/420 release, 420/420 UBSan (21 sub-cases x 10 seeds x 2 arms) | `runs/summary.json` `hostile_rejected` |
| (b) complete malicious proofs among them | 240/240 rejected per build (12 complete sub-cases x 10 x 2) | `runs/summary.json` `complete_rejected` |
| (b) UBSan reports | 0 stderr bytes over all 20 UBSan processes | `runs/summary.json` `suite-ubsan.stderr_bytes` |
| (b) harness bug guard (complete case with no violated relation) | never triggered (every complete case violated >= 1 relation, see below) | `runs/suite.jsonl` `violations` |
| (c) fidelity, max per-head rel L2 <= 1e-2 | max 1.97e-3 (D16 unit-spike) | `runs/fidelity.json` |
| (c) median of seed medians <= 1e-3 (uniform, outlier, low), <= 5e-3 (unit-spike) | max 4.33e-4 (D16 low), unit-spike 1.25e-3 | `runs/fidelity.json` |
| (c) zero heads exactly 0 | 30/30 per arm | `runs/fidelity.json` |

## Hostile cases (each: 10 seeds x {D16, D256}, all rejected in both builds)

`complete` = complete malicious proof (all product gates hold, the prover's affine targets replaced by locally true values, the unchanged verifier keeps its own); `violations` = relations the witness violates, from `runs/suite.jsonl`.

| case | kind | violations D16 / D256 | what it shows |
|---|---|---|---|
| wrong-scale | complete | 1 / 1 | the gain is a coefficient of the y floor equation; a one-quantum change of gq[j*] (step 1 in all 20 runs) breaks it |
| wrong-scale | statement | n/a | statement gains are bound into the relation list and the transcript |
| gain-swap | complete | 32 / 511-512 | q heads cannot use the k gains |
| gain-over-bound | statement | n/a | refused by admission (`admit`), outside the proof |
| isqrt-plus-one, isqrt-minus-one | complete | 1 / 1 | the two isqrt residual ranges pin sigma |
| div-rem-over, div-rem-under | complete | 1 / 1 | rr in [0, sigma) pins R = floor(2^K / sigma) |
| floor-rem-over | complete | 1 / 1 | the Z floor remainder range |
| swapped-head | statement | n/a | outputs of head 0 and 1 swapped |
| swapped-head | complete | 32 / 512 | input pins: head h's cells must equal head h's public x |
| wrong-vector | complete | 16 / 256 | q head 0 normalising the k vector is caught by the input pins |
| shared-coefficient | complete | 2 / 2 | head 0 reusing head 1's sigma and R breaks head 0's isqrt residuals |
| zero-no-eps | complete | 3 / 4 | sigma = 0 on a zero head (epsilon dropped) |
| spike-no-eps | complete | 2 / 3 | sigma without epsilon on the unit-spike head |
| wrong-output, byte-flip, truncated, trailing | statement | n/a | standard mutations |
| dim-replay | statement | n/a | a D16 proof against a D256 statement and vice versa |
| scale-replay | statement | n/a | F = 14 statement; refused by admission (F = 12 only) |

Which mechanism rejects the statement cases (admission vs the proof's transcript check) is not recorded per case, except gain-over-bound and scale-replay, which fail admission by construction. The complete cases are rejected by an equation check with a large margin, not a low-probability query round: they show each constraint exists and reads the right cell, not that the protocol reaches its security target.

## Fixed-point error vs float64 (registered fixtures, 10 seeds, 3 heads per seed)

Per head: ||y/2^F - y_ref|| / ||y_ref||, y_ref = g x / sqrt(mean(x^2) + 1e-6) on the dequantized same integers. Per seed the median and max over the 3 heads; then across the 10 seeds. SD = sample SD (n - 1) over seeds.

| arm / dist | median of seed medians | SD | min / max seed median | max over all heads | max abs element error |
|---|---|---|---|---|---|
| D16 uniform | 2.29e-4 | 2.1e-5 | 1.89e-4 / 2.56e-4 | 3.26e-4 | 6.6e-4 |
| D16 outlier | 2.99e-4 | 5.2e-5 | 2.09e-4 / 3.48e-4 | 5.45e-4 | 7.3e-4 |
| D16 low | 4.33e-4 | 5.8e-5 | 3.86e-4 / 5.83e-4 | 6.41e-4 | 8.4e-4 |
| D16 unit-spike | 3.85e-4 | 4.3e-4 | 1.48e-4 / 1.43e-3 | 1.97e-3 | 2.7e-4 |
| D256 uniform | 2.31e-4 | 2.7e-6 | 2.26e-4 / 2.34e-4 | 2.51e-4 | 7.0e-4 |
| D256 outlier | 2.06e-4 | 1.0e-4 | 1.73e-4 / 4.79e-4 | 4.99e-4 | 7.0e-4 |
| D256 low | 4.06e-4 | 1.6e-5 | 3.90e-4 / 4.48e-4 | 4.91e-4 | 7.6e-4 |
| D256 unit-spike | 1.25e-3 | 1.7e-4 | 1.05e-3 / 1.51e-3 | 1.65e-3 | 6.3e-4 |
| D16 / D256 zero | exact 0 on 30/30 heads per arm | | | | |

The error floor (~2e-4) is the output quantum at F = 12 (2^-12 / typical |y| ~ 1). No input quantization error is included (the reference gets the same integers), and these are synthetic distributions, not real activations or BF16 fidelity.

## Descriptive sizes and times (not a performance claim)

`honest/uniform` proof, n = 10 per arm, release build, 4 pinned cores through the shared heavy-job gate on a loaded host (`runs/summary.json`, `suite.sizes`).

| arm | columns | relations | proof bytes median (min-max) | prove s median (SD, min-max) | verify s median (SD, min-max) |
|---|---|---|---|---|---|
| D16 (3 heads) | 3192 | 6333 | 67968 (67728-68272) | 0.0440 (0.0020, 0.0420-0.0487) | 0.0261 (0.0020, 0.0244-0.0308) |
| D256 (3 heads) | 43521 | 86262 | 815088 (814864-815376) | 0.711 (0.017, 0.683-0.739) | 0.170 (0.009, 0.158-0.184) |

Prove time starts after relation building, sizing and table assembly (not end-to-end). The dominant cost is bit decomposition: about 57 columns per channel at D256 (43521 / 768), almost all range bits of Z, rz and ry. For comparison only, PR #67's one-head D256 table norm has 15753 columns and 31137 relations (results.yaml `qwen-bounded-operators-1109`, `rms_columns`, `rms_relations`); this relation is about 0.92x of that per head (43521 / 3 = 14507) while adding epsilon, gain and an unbounded-below domain, but it is a different relation and the counts are not a like-for-like benchmark.

## What is NOT established

- **Provenance.** Inputs and gains are public statement fields. Nothing ties them to a q/k projection of a hidden state, to model weights, or to `q_norm.weight` / `k_norm.weight` (inventory OP-R18, gap G-08). This is the M3 / model-input provenance work of #35 and #34.
- **Model shape.** Hq = 2, Hk = 1, F = 12 only. Not Qwen's real head counts or F = 14/16. Composition with the projection, rotary (`qwen_ops` rotary) and the 1/sqrt(d) attention scale is not built.
- **Security.** Research target 10 bits per round including 6 bits proof-of-work, toy deterministic coins, no whole-proof soundness figure, no grinding attempt. Hostile cases are sampled classes, not exhaustive.
- **Fidelity.** Synthetic integer inputs; no BF16 or real-activation fidelity.
- **Replication.** None yet. Needs an independent review/replication lane before any public statement.

## Deviations and notes

- PREREG.md was first committed alone (669cf39), then edited three times (a3dd128, ba4694d, b4f9c36) before any code existed (code first appears in 831541e): output admission bound, unit-spike threshold 5e-3, hostile-case fixture and channel definitions, pre-scaled epsilon epsN. No PREREG edit after code; Amendments is empty.
- Debug used only seeds 901..903 (under ignored `work/`), as registered. One single D16 debug process at seed 901 ran before `run.py debug`; same seed set, not evidence.
- Cores: 12-15 via taskset inside the heavy-job gate (registered "<= 6 cores").
- The UBSan suite also wrote its own fixture files (`fixtures-*-ubsan.jsonl`); fidelity reads the release fixtures only. The two sets are generated by the same deterministic code from the same seeds.
- Main's `check_inventory.py` is red independently of this PR (`research/operators/qwen_conv_history` uncited; PR #105 fixes it). This PR adds rows for its own directory only.

## Reproduce

See `research/operators/qwen_qk_norm/README.md`, section Reproduce. ENV: `ENV.json`.
