# RESULTS: 20261121-228-inkling-layer0-fidelity

**FAIL on both registered bars.** We computed the routed-expert MLP block of Inkling 2 Mini's layer 0 with our prover's integer rules, on real weights, and compared it with our own float64 version of the same block. The integer block's output is about 2% off (bar: 1% median). It also picks a different set of 8 experts on 3.75% of tokens (bar: at most 1%). Every value stayed inside its integer range, and two runs gave identical results. Most of the 2% comes from the changed expert choices: if the integer block is given the float block's expert choices, its error drops to 0.79%.

Measured, unreplicated, one layer, open loop, CPU. This is not a proof. The float reference is our reading of an open transformers pull request and has not been checked against the publisher's runtime.

## 1 Numbers against the bars

Data: `runs/result-A.json` (registered run), `runs/result-B.json` (second process, used for the determinism check), `runs/summary.json`. 10 prompts, 2,426 tokens.

| bar (PREREG) | measured | verdict |
|---|---|---|
| B1: per-prompt rel_y, median <= 1e-2 and max <= 5e-2 | median **0.02181**, max 0.03042, min 0.01373 (n = 10 prompts) | **FAIL** (median) |
| B2: share of tokens whose top-8 set differs <= 1% | **91 / 2,426 = 3.75%** | **FAIL** |
| B3: range verdict (not part of PASS) | 0 events at every site (below) | IN-BOUND |
| Determinism (A vs B, separate processes) | every integer-array sha256 and every metric equal | holds |

Per prompt (rel_y; tokens whose set differs out of n):

| prompt | n | rel_y | set differs | rel_y on tokens whose sets agree | rel_y with the float set and weights (attribution) |
|---|---|---|---|---|---|
| p01-ordinary-short | 13 | 0.02236 | 1 | 0.00859 | 0.00855 |
| p02-ordinary-paragraph | 109 | 0.02127 | 4 | 0.00943 | 0.00928 |
| p03-repeat-word | 512 | 0.01373 | 2 | 0.00703 | 0.00680 |
| p04-repeat-punct | 64 | 0.02719 | 2 | 0.00913 | 0.00905 |
| p05-code | 183 | 0.02773 | 8 | 0.00838 | 0.00824 |
| p06-digits | 239 | 0.01691 | 8 | 0.00931 | 0.00920 |
| p07-chat-ordinary | 43 | 0.01713 | 1 | 0.00773 | 0.00760 |
| p08-chat-refusal | 63 | 0.02267 | 2 | 0.00678 | 0.00669 |
| p09-multilingual | 28 | 0.01889 | 1 | 0.00705 | 0.00692 |
| p10-long-mixed | 1,172 | 0.03042 | 62 | 0.00945 | 0.00932 |

Pooled over all tokens: rel_y 0.02095. Per-token rel (descriptive): medians 0.0070 to 0.0108 per prompt, the largest single token 0.419 (p10).

Reviewer's descriptive finding, not this PR's measurement (added after review, https://github.com/wakesync/flashprove/pull/230#issuecomment-7058731735, section 6): that largest token, 0.419, is a routing flip (a token whose integer set of 8 differs from the float set), and all 90 tokens with a per-token error above 0.05 are flips; the largest error on a token without a flip is 0.0171. This file does not recompute those numbers.

## 2 Where the error comes from (descriptive, no bar)

- **Expert choice.** On each of the 91 tokens where the sets differ, exactly one of the 8 experts is different. On those tokens, the float scores of the 8th and 9th experts (s + b) differ by a median of 3.0e-4 (90th percentile 1.0e-3, largest 1.5e-3). The integer router reads the sigmoid table with logits at 2^-8 and outputs scores at 2^-16 steps of 16 (`docs/model.md` section 4 table 4, so a step of 2.4e-4). That step is about as large as these gaps. This is an observation about sizes. No arm with a finer router was registered or run, so it is not a tested cause.
- **Expert arithmetic with the routing fixed.** When the integer expert outputs are combined with the float set and float weights, pooled rel_y is **0.00789**, and per prompt it ranges from 0.0067 to 0.0093. All 10 prompts fall under 0.01, but not by much. This attribution arm was registered as descriptive, so it does not change the verdict.
- **Input scale.** The fitted exponent of m is Em = 6, because the largest |u| (unit-RMS input to the norm gain) is 23.9 over all tokens. A typical entry of size about 1 is then stored as about 64, roughly 6 to 7 significant bits. This is the 12-bit cell rule of `scales/README.md` applied as registered. Whether it is the main source of the 0.7 to 0.9% expert error was not tested.

## 3 Ranges and weights

From `runs/result-A.json` `ranges` and `weights`:
- m: 0 of 5,589,504 entries clamped at 2,047 (Em = 6, mx_u = 23.91).
- Router: ly clamp 0, condition 5 0, Sig read out of -16,384..16,383: 0 (of 310,528 logits).
- Expert hidden units (2,426 tokens x 8 experts x 1,152 = 22,358,016 integer-arm units): gate gh clamp at 127: 0; condition 6: 0; TA key out of domain: 0; up uh clamp: 0; TB key out of domain: 0; condition 7 on uw: 0.
- Largest down accumulator 1,831,128,802 (< 2^31). Largest expert output y 13,970 at 2^12.
- Weight exponents (gain folded, all 128 experts together): router 14, gate 13, up 13, down 13. Shifts kr 12, kg 11, ku 11, kd 17. Outside 13 bits: 0 everywhere (by construction). Non-zero decoded weights that round to 0: gate 285,406 of 316,316,398 (0.090%), up 285,211 of 316,332,517 (0.090%), down 0 of 316,541,401, router 625 of 294,912 (0.21%).
- Down: no non-zero decoded weight rounds to 0 at 2^13 (the smallest non-zero NVFP4 magnitude times the scales stays above 2^-14). Whether the down integers equal the decoded values times 2^13 exactly (no rounding at all) was not checked.

## 4 Decode checks (PREREG D1 to D4, before the run)

`runs/decode-check.json`: PASS. Shapes and block counts match. No NaN or negative block scale in 128 experts. For every expert, max |decoded| / amax = 1.000 (min 0.99999999999999990, max 1.0000000000000002) for both w13 and w2. outer_scale_denominator = 2,688 for both. The `amax` tensors behave like per-expert absolute maxima under our reading of the decode. This defends the decode's scale, not the gate/up row order: the even/odd split of w13 follows the PR's `Interleave` + `chunk`. A swapped gate/up would change the float and integer arms the same way, so it would not show up as integer error here. It would matter for any claim about the model's actual function.

## 5 What this establishes, and what it does not

Establishes (measured, unreplicated, one deterministic CPU run plus an identical second run): with this lowering (12-bit cells, in-sample input scale, 13-bit per-tensor weights, main's router and sigmoid table, two new 2^-8-step tables for the soft caps, a rounded-division routing weight at 2^13), the layer-0 routed MLP block of Inkling 2 Mini misses the Qwen-derived block bar (2.2% median vs 1%) and changes the expert set on 3.75% of tokens. No integer range was exceeded.

Does not establish:
- Anything about the other 23 layers, the loop, attention or logits. This is one block, open loop, with an exact float64 input.
- Agreement with the model as served. The float reference is our float64 reading of the open PR 51050 (`6173a2f6`), with no BF16 casts, and was not compared with any runtime of the publisher. Gate/up order rests on that PR.
- That Inkling is worse or better than Qwen. Qwen has no router, so B2 has no Qwen counterpart. Qwen's MLP was measured end to end on tokens (PR #173), not per block on rel_y. The B1 bar comes from Qwen's per-head DeltaNet and attention numbers, so this is a different unit (prompt instead of (prompt, head)).
- That a finer router (logit or score resolution) or a wider input cell would pass. Neither was registered or run.
- That the sliding-window mask's edge rule (a key counts when 0 <= i - j < 1,024, `run.py` CFG `window=1024`, `inkcore.py` `layer0_mlp_input`) matches its source. From the review (https://github.com/wakesync/flashprove/pull/230#issuecomment-7058731735, "Skipped"): the reviewer did not check it, because the source file that defines it was not among the fetched files. It affects only the tokens of p10 past position 1,024 (148 tokens, the reviewer's count) and sits on the float input path that both arms share.
- Soundness, proof size or prover cost of any of the new relations (top-8, routing-weight division, TA/TB tables).

## 6 Deviations from the PREREG

- The PREREG's guard bounds note gives "down 2^45" as a bound. The code asserts the actual bound max|a| x max|w| x n < 2^53 before every product, which is what the PREREG requires. The prose figure is not used by the code. No guard fired.
- The PREREG says rel_y per token is reported as "median, p99, max". These are reported per prompt (`tok_rel_*`), not as one pooled distribution.
- `summarise.py` was written after run A's numbers were visible. It only reads the result files and applies the registered bars. It adds no metric.
- The weighted-sum bound is asserted after the int64 accumulation (`run.py` lines 197-198: `if np.abs(out_acc).max() >= 2 ** 53: raise ic.Guard("weighted sum")`), not before each product as the PREREG's wording ("before each product") suggests. The m-products and the down product are checked before the product, in `inkcore.py` `imatmul`. The accumulation is int64, so checking after it is harmless at these sizes; the guard did not fire. Raised by the review.
- PREREG header time (added after review): the PREREG header says 2026-11-21T05:58Z, but the commit that carries it, `bbc3c742`, has commit time 2026-11-21T05:54:33Z. The commit time is the record; the header was not edited. See PREREG Amendment 1.
- ENV.json tensor count (added after review): ENV.json's `tensors_fetched` says 29 tensors; `runs/manifest-tensors.json` lists 28. 28 is right. See ENV.json `corrections_after_review`.
- Venv contents (added after review): the venv also holds packages pulled in by `tokenizers` that the experiment does not import (the reviewer names huggingface_hub, httpx, PyYAML and others). The five code files (`inkcore.py`, `run.py`, `decode_check.py`, `prompts.py`, `summarise.py`) import only numpy, tokenizers (in `prompts.py`), `inkcore` and the Python standard library (math, hashlib, json, os, sys, time).
- Nothing else. The registered run started at 06:01Z, before the 07:40Z limit, and took 54 s. 630 MB of weights were fetched against a 4 GB budget. Peak RSS was 1.5 GB against a 6 GB limit.

## 7 Reproduce

From a checkout of this branch, with numpy 2.3.5 and tokenizers 0.22.1 in a venv (no torch, no transformers):
1. Fetch the tensors listed in `runs/manifest-tensors.json` (byte ranges of `model-00001-of-00001.safetensors` at the pinned revision) into a directory `T`, one file `<tensor name>.bin` each, and check each sha256. Fetch the embedding rows listed in `runs/embed_rows.json` into `T/embed_rows.bin` (rows in sorted id order, BF16) with that json beside it. The fetch scripts used are lane tooling outside the repository. Their requests are in `runs/requests.jsonl`.
2. `python prompts.py ../20261109-8-qwen-real-weights/prompts.json <tokenizer.json> prompts-inkling.json` (must reproduce the committed file).
3. `python decode_check.py T runs/decode-check.json`
4. `python run.py run T prompts-inkling.json runs A` and again with `B`. Then `python summarise.py runs`.
5. `python run.py selftest runs/selftest.json` (synthetic fixture only).

## 8 Compared with Qwen (added after review)

The issue's registered outcomes are stated against Qwen, so each Inkling number is set here next to the merged Qwen number it was modelled on. Every Qwen number is quoted from the file on main named beside it. Which Qwen numbers to put side by side was chosen by the fix lane; a reader should check that choice.

| this experiment (Inkling 2 Mini, layer-0 routed MLP block) | merged Qwen number it is modelled on | Qwen source on main |
|---|---|---|
| B1: per-prompt rel_y median 0.0218, max 0.0304, n = 10 prompts, against median <= 0.01, max <= 0.05: FAIL | A2 bar "median rel_y <= 1e-2, max rel_y <= 5e-2" over 480 (prompt, head) pairs of layer 0's DeltaNet heads (gated-norm output y); no F passes: median rel_y 0.659 / 0.177 / 0.0494 at F = 12 / 14 / 16 (max 141 / 54.4 / 19.4): FAIL | `experiments/20261109-8-qwen-real-weights/RESULTS.md` (verdict table) |
| B1 bar applied per layer | the same bar per attention layer, 240 (prompt, head) pairs each, integer attention at in-sample scales: C2047 13 of 16 layers pass, C1665 11 of 16; pooled over 3,840 cells C2047 median 0.00700, max 0.0335; every failure on the median: FAIL | `experiments/20261113-176-qwen-int-attn/RESULTS.md` (sections 1 and 2) |
| B2: top-8 set differs on 91 of 2,426 tokens (3.75%), against <= 1%: FAIL | integer MLP end to end (XM18, abliterated): top-1 agreement 1,423 of 1,461 positions (97.40%) against >= 99%: FAIL | `experiments/20261112-132-int-mlp-e2e/RESULTS.md` (line "H (numerical) on abl: FAIL"), cited as PR #173 in `docs/qwen-port.md` |
| table step 2^-8 (the sigmoid table of the router, and TA and TB) | replacing only the SiLU table lookup (step 2^-8, index clipped to [-8, 8)) by exact SiLU moves the late-layer KL median from 1.466e-3 to 1.83e-6 (H-S holds); replacing only the 13-bit weights leaves it at 1.454e-3 (H-W does not hold) | `experiments/20261114-201-mlp-stage/RESULTS.md` ("Answer") |

What this comparison can support:
- Both models' first integer measurements against these bars are FAILs, and the bars here were carried over from those Qwen experiments (PREREG "Acceptance threshold").
- As the issue registered, PASS meant "the MLP block meets bars Qwen's MLP did not". The block did not meet its bars, so the condition under which Inkling would move ahead of Qwen is not met.
- The Qwen stage result (`20261114-201`) shows that on Qwen a 2^-8-step table carried most of the MLP's token error. Inkling's router reads a table of the same step, and section 2 observes that this step is about as large as the 8th/9th score gaps. That is a similarity of format, not a tested cause here: no exact-table arm was registered or run on Inkling.

What it cannot support:
- Different units. B1 is one rel_y per prompt (10 values) on the MLP block output; Qwen's A2 numbers are per (prompt, head) pair on DeltaNet or attention head outputs (480 or 240 per layer). Qwen's MLP number is end-to-end token agreement over 64 layers, not a per-block error.
- Qwen has no router, so B2 has no Qwen counterpart; the 99% figure is a discrete-choice bar carried over, not a like-for-like number.
- One Inkling layer, open loop, from an exact float64 input; the Qwen MLP result is closed loop through every layer.
- The Inkling float reference is our reading of unreleased code (the open transformers PR 51050), not the publisher's runtime.
- So the comparison does not show that Inkling is harder or easier to run under these integer rules than Qwen, and this file does not say which model should be worked on next.
