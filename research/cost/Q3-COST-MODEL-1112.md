# Q3: what a Qwen3.8-27B proof costs, modelled from merged numbers (2026-11-12)

Desk note, Part of #7. Registration: [experiments/20261112-7-cost-model/PREREG.md](../../experiments/20261112-7-cost-model/PREREG.md).
Script: [q3_cost_model_1112.py](q3_cost_model_1112.py) (`python3 research/cost/q3_cost_model_1112.py`). Its printed output is the
source of every number here; the same values are in [model-output.json](../../experiments/20261112-7-cost-model/model-output.json).
It extends [Q3-COST-QWEN-1110.md](Q3-COST-QWEN-1110.md) (#85) with results merged since.

**Nothing here is a measurement of a Qwen proof.** No Qwen work has run on a GPU, and the DeltaNet sub-proof of the GPU prover has not
been written. Every Qwen figure is a count from main multiplied by a rate taken from another model or another program.

## The answer in five lines

1. **Cost per 1,000 tokens: somewhere between about 3 cents and about 10 dollars.** The low end is PR #70's central rate on a 1,024-token
   window at the cheapest invoice on main. The high end puts together the worst factors main actually shows. The two ends are about
   400 times apart. Main cannot narrow that.
2. **Two unknowns make up almost all of that spread.** How many GPU-seconds a DeltaNet entry takes (60 times between the rates on main),
   and how many bytes of GPU memory it takes (14 times). Both are settled by one GPU calibration run, not by more desk work.
3. **Memory on one H200: fits on the central rate, not on the fork's own rate.** At 23 bytes per entry a 1,024-token window's largest
   segment is about 41 GB. At the fork's own 220 bytes per entry it is about 393 GB, and the largest window that fits drops to 256 tokens
   (128 if the weights stay on the card).
4. **"How many times plain inference": still not established.** Main has no plain Qwen3.8-27B speed on any card, so there is nothing to divide by.
5. **Use cases:** U2 (sampled audit) is the only one whose cost holds up across the whole range. U1 (prove every token) is affordable only
   if the central rate holds. U3 (proof plus TEE) has the same cost as U1 or U2, and it is also blocked on running the prover under CC-On at all.

## What changed since #85

#85 used only PR #70's rates. Since then, results have merged that bear on cost. They don't change the central number, but they widen
the high end and say where it comes from:

| merged result | what it adds to the cost model | label |
|---|---|---|
| #73, built M2 DeltaNet head (D = 128, 16 tokens, CPU) | The only DeltaNet lowering built at the real head shape lays out 1,613,856 columns for 16 tokens. Over 2,304 head-layers that is 2.32e8 per token, **2.78 times** the 8.37e7 mixer entries the plan of record counts (2.56 times for the whole model). Proving took 86.7 s against #66's 39 s estimate: **2.22 times** what was estimated. | counted (volume), measured on CPU (time) |
| #44, H200 memory lever (Maverick shape, synthetic weights) | The only full-size proving rates on main: 93.85 tok/s (H100) and 146.06 tok/s (H200), one session each, on two hosts. 7.13 and 10.53 USD per Mtok at the rented quotes. Quotes: 2.41/h per H100 GPU, 5.54/h per H200. | measured |
| #106, CPU phase split | On the one DeltaNet head statement (stage 1), proving is 79% of verified latency and there is no setup to amortise. Context only: CPU, not a GPU rate. | measured (CPU) |
| #98, #114, #121, PR #70 sensitivity | Handoff, unique-floor and key-binding counts are small next to the per-token state. A wider recurrence (if F12 is replaced for fidelity) adds at least 17%. | counted |
| #68, #88, #74 | No integer format on main passes fidelity yet. The final format's size is open (the 17% above is a lower bound). | measured, negative |

The 2.78 times compares two different things: research-harness laid columns against GPU-prover committed entries. It is a volume
multiplier for the case where the M2 lowering is what gets ported, not a like-for-like count.

## The numbers (all extrapolated)

GPU-seconds per 1,000 window tokens, PR #70 rates (`runs/model-r3.json`, per-token state, one DeltaNet segment per layer):

| T | central | high | small-example rate |
|---|---|---|---|
| 64 | 96.1 | 139.9 | 2,559 |
| 256 | 53.2 | 97.0 | 2,559 |
| 1,024 | 42.5 | 86.3 | 2,559 |

USD per 1,000 window tokens at T = 1,024, at the four prices on main:

| rate | H100 invoice 2.16/h | H100 quote 2.41/h | assumed 3.00/h | H200 quote 5.54/h |
|---|---|---|---|---|
| central | 0.026 | 0.029 | 0.035 | 0.065 |
| high | 0.052 | 0.058 | 0.072 | 0.133 |
| small-example | 1.54 | 1.71 | 2.13 | 3.94 |

Envelope: low 0.026 (central rate, T = 1,024, cheapest invoice). High 10.10: small-example rate, times the 2.56 built-volume factor,
at the H200 quote, at T = 256, which is the largest window that fits at the fork's own memory rate. Ratio about 400 times.

GPU memory of the largest segment (GB) and the largest power-of-two window under PR #70's 127 GB one-H200 rule:

| bytes per entry | T = 64 | T = 256 | T = 1,024 | largest window, weights streamed | weights resident (56.3 GB) |
|---|---|---|---|---|---|
| 16 (low) | 1.8 | 7.1 | 28.6 | 4,096 | 2,048 |
| 23 (central) | 2.6 | 10.3 | 41.0 | 2,048 | 1,024 |
| 46 (high) | 5.1 | 20.5 | 82.0 | 1,024 | 512 |
| 220 (own rate) | 24.5 | 98.2 | 392.8 | 256 | 128 |

The per-layer cut needs 81 segments per window; `cp_verify` takes 64. That holds at every rate.

Cross-check against the only measured full-size rate on main: the central Qwen figure is **4.0 times** Maverick's measured GPU-seconds
per token on the H100 (#44, a host 14% below upstream). Qwen commits **9.2 times** Maverick's entries per 1,024-token window (counted).
The time ratio is below the entries ratio because PR #70's fit charges most of Maverick's time to weight passes, and Qwen's weights are
6.7% of Maverick's. The central rate therefore depends on that split between weight passes and per-entry work. Nothing on main tests
the split, and nothing at all tests it for a DeltaNet entry.

## What closing each gap could move (one factor at a time, the others central)

| spread | gap | moves |
|---|---|---|
| unbounded | plain Qwen3.8-27B inference rate | the multiple of plain inference only; not on main |
| 60.2x | GPU-seconds per DeltaNet entry (central vs small-example rate) | USD, GPU-s |
| 13.8x | GPU bytes per DeltaNet entry (16 vs 220) | memory; USD once it forces T down |
| 2.56x | USD per GPU-hour (H100 invoice vs H200 quote) | USD |
| 2.56x | volume of the lowering that gets built (plan vs built M2) | USD, GPU-s, memory (unit caveat above) |
| 2.26x | window length (T = 64 vs 1,024) | USD, GPU-s |
| 2.22x | estimator miss seen on main (#73) | USD, GPU-s (CPU evidence, transferred) |
| 1.17x+ | wider recurrence for fidelity | USD, GPU-s, memory |
| not quantified | H200 speed vs H100 (assumed equal) | USD, GPU-s |

Open PR #123 (hidden-root window handoff, unmerged) counts 14,493 columns per token at D8/C2, with a sponge that is 88.7% of them. At
D128/C64 the hash share is 14.6% of columns. Not established, not used above. If it merges, the D128 per-token cost of an in-proof
handoff would join the volume factor.

## The multiple of plain inference

multiple = proved GPU-seconds per token x plain tokens per GPU-second, on the same card and the same kind of token.

The second factor is not on main for Qwen3.8-27B. Evaluated only at **assumed** plain rates, at T = 1,024:

| assumed plain tok/s per GPU | central | high | small-example |
|---|---|---|---|
| 1,000 | 43x | 86x | 2,559x |
| 5,000 | 213x | 432x | 12,796x |
| 10,000 | 425x | 863x | 25,591x |

For context only: upstream's Maverick figures imply about 10,300 plain prefill tok/s per GPU (111.23 x 93.0, guide/performance.md).
That is a different model, run in FP8 on 8 H100s, and is not a Qwen baseline.

## By use case

- **U1, substitution check, every token proved.** At the central rate this costs about 3 to 7 cents per 1,000 window tokens and fits a
  1,024-token window on one H200. At the fork's own rates it costs about 1.5 to 10 dollars per 1,000 and windows are capped at 256 tokens.
  Before cost matters at all, U1 is blocked on fidelity (#68, #88: no passing integer format), on the unbuilt DeltaNet GPU sub-proof,
  and on the 64-segment cap. Viability is **undecided**, and cost could decide it either way.
- **U2, sampled audit, a fraction f of windows proved.** Variable cost scales with f. At f = 0.01 it is 0.4 to 26 GPU-seconds per 1,000
  served tokens across the whole range, 100 times less than U1 at the same rate. How that compares with serving is not established
  (no plain rate on main). The fixed cost may decide it instead. Upstream's start-up
  (68 to 79 s) is 1.6 to 1.8 times a central 1,024-token window proof, so U2 pays off only with a warm prover. U2 is the **only use case
  whose cost can be made small at every rate on main, by choosing f**. Its value depends on Q4 (#84: coverage per sample) and on the same blockers as U1.
- **U3, proof plus TEE.** Cost is U1's or U2's plus a TEE serving overhead, and that overhead is not on main. It is blocked first, not on
  cost: the unmodified prover calls `cudaHostRegister`, which is not allowed under CC-On (H200 bring-up, source reading, untested), and
  the live Tinfoil H200 leaves too little free memory for even the small example (#43 bring-up, phase 1).

## The next experiment to register

**GPU calibration of entries to time and bytes, plus the plain-inference denominator, in one rental.** On one H200 (or H100 if that is
what is available, labelled):

1. With the existing prover, prove at least 3 dense-family configurations spanning at least 2 orders of magnitude of committed entries:
   the small synthetic example, a planner proxy, and a mid-size proxy. Record peak GPU memory (sampled at 100 ms or finer, plus
   `cudaMemGetInfo` from the program if it can be added) and `cp_prove` wall time.
2. Fit memory = a + b x entries and time = c + d x entries. Decision rules fixed now: if b is within 2x of 23 B per entry, the central memory
   column stands. If b is within 2x of 220, the own-rate column stands and the U1 window is 256 tokens. If d puts the central time
   rate within 2x, the central USD column stands.
3. Same session, same card: stock vLLM on Qwen3.8-27B BF16, prefill tok/s and decode tok/s at 1, 8, 32 and 128 concurrent requests.
   That is the denominator for the multiple.

This does not measure a DeltaNet entry: no DeltaNet GPU sub-proof exists. It turns two of the three largest gaps from "which of two numbers"
into one measured slope for the dense family, and it fills the denominator, which is currently missing outright. A DeltaNet GPU
calibration needs the sub-proof first.
