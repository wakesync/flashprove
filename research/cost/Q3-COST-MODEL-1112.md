# Q3: what a Qwen3.8-27B proof costs, modelled from merged numbers (2026-11-12)

Desk note, Part of #7. Registration: [experiments/20261112-7-cost-model/PREREG.md](../../experiments/20261112-7-cost-model/PREREG.md).
Script: [q3_cost_model_1112.py](q3_cost_model_1112.py) (`python3 research/cost/q3_cost_model_1112.py`). Its printed output is the
source of every number here; the same values are in [model-output.json](../../experiments/20261112-7-cost-model/model-output.json).
It extends [Q3-COST-QWEN-1110.md](Q3-COST-QWEN-1110.md) (#85) with results merged since.

**Nothing here is a measurement of a Qwen proof.** No Qwen work has run on a GPU, and the DeltaNet sub-proof of the GPU prover has not
been written. Every Qwen figure is a count from main multiplied by a rate taken from another model or another program.

## The answer in five lines

1. **The selected conditional scenarios span $0.0255 to $10.0982 of variable proving cost per 1,000 window tokens (prompt plus
   reply).** These are not bounds on what a Qwen proof actually costs: the DeltaNet GPU sub-proof does not exist, the fidelity format
   and H200-versus-H100 speed are open, and fixed costs (commit, start-up) are left out. The low scenario is PR #70's central rate on a
   1,024-token window at the cheapest invoice on main. The high scenario multiplies the worst time rate, the built M2 volume and the
   dearest quote on main. The two are about 400 times apart, and main cannot narrow that.
2. **Two unknowns make up almost all of that spread.** How many GPU-seconds a DeltaNet entry takes (60 times between the rates on main),
   and how many bytes of GPU memory it takes (14 times). Neither is settled by desk work. A dense-family GPU calibration would not
   settle them either: it measures dense entries, and a DeltaNet entry needs the DeltaNet GPU sub-proof and its own calibration. The
   14 times is a memory spread, not a USD spread: in this model memory changes cost only by forcing a shorter window.
3. **Memory on one H200 depends on both the bytes per entry and the volume.** At plan volume and 23 bytes per entry, a 1,024-token
   window's largest segment is about 41 GB. At plan volume and the fork's own 220 bytes per entry it is about 393 GB, and the largest
   window that fits is 256 tokens (128 with weights resident). With the built M2 volume that the high scenario uses, it is 64 tokens
   at 220 bytes per entry (272.6 GB at T = 256), streamed or resident.
4. **"How many times plain inference": still not established.** Main has no plain Qwen3.8-27B speed on any card, so there is nothing to divide by.
5. **Use cases:** U2 (sampled audit) is the only one whose variable cost can be made small in every selected scenario, by choosing
   f. U1 (prove every token) is affordable only if the central rate holds. U3 (proof plus TEE) costs U1's or U2's proving plus a TEE
   serving overhead that is not on main (unknown, additive), and it is blocked first on running the prover under CC-On at all.

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

Prices: 2.16/h is an invoice (replication-1), 2.41/h and 5.54/h are quotes (saved marketplace offers, #44), 3.00/h is assumed (PR #70).

Selected conditional scenarios (variable proving cost per 1,000 window tokens, prompt plus reply; not bounds on actual cost, fixed
costs omitted): low 0.0255 (central rate, plan volume, T = 1,024, cheapest invoice). High 10.0982: small-example rate, times the
2.56 built-volume factor, at the H200 quote, at T = 64. T = 64 is the largest power-of-two window that fits at the fork's own memory
rate **with the built volume** the high scenario assumes (T_max 119 streamed, 66 with weights resident). The first version of this
note used the plan-volume window (256) here, which mixed two volume scenarios. The USD figure is the same either way, because the
small-example rate is flat per token in T (it scales linearly in entries; the script checks max/min over T = 1.000000000). The window
label was what was wrong. Ratio about 400 times.

GPU memory of the largest segment (one DeltaNet layer) and the largest power-of-two window under PR #70's 127 GB one-H200 rule,
at **plan volume** (1,744,122 planned entries per token):

| bytes per entry | T = 64 | T = 256 | T = 1,024 | largest window, weights streamed | weights resident (56.3 GB) |
|---|---|---|---|---|---|
| 16 (low) | 1.8 | 7.1 | 28.6 | 4,096 | 2,048 |
| 23 (central) | 2.6 | 10.3 | 41.0 | 2,048 | 1,024 |
| 46 (high) | 5.1 | 20.5 | 82.0 | 1,024 | 512 |
| 220 (own rate) | 24.5 | 98.2 | 392.8 | 256 | 128 |

The same at **built volume** (4,841,568 CPU-harness laid columns per token for one DeltaNet layer, read as entries, the transfer the
high scenario's time factor already makes):

| bytes per entry | T = 64 | T = 128 | T = 256 | T = 1,024 | largest window, weights streamed | weights resident |
|---|---|---|---|---|---|---|
| 16 (low) | 4.96 | 9.92 | 19.83 | 79.32 | 1,024 | 512 |
| 23 (central) | 7.12 | 14.24 | 28.47 | 113.88 | 1,024 | 512 |
| 46 (high) | 14.24 | 28.47 | 56.94 | 227.77 | 512 | 256 |
| 220 (own rate) | 68.15 | 136.29 | 272.59 | 1,090.36 | 64 | 64 |

The per-layer cut needs 81 segments per window; `cp_verify` takes 64. That holds at every rate.

Cross-check against the only measured full-size rate on main: the central Qwen figure is **4.0 times** Maverick's measured GPU-seconds
per token on the H100 (#44, a host 14% below upstream). Qwen commits **9.2 times** Maverick's entries per 1,024-token window (counted).
The time ratio is below the entries ratio because PR #70's fit charges most of Maverick's time to weight passes, and Qwen's weights are
6.7% of Maverick's. The central rate therefore depends on that split between weight passes and per-entry work. Nothing on main tests
the split, and nothing at all tests it for a DeltaNet entry.

## What closing each gap could move (one factor at a time, the others central)

The spreads are of one factor each, in that factor's own units. The 13.8x memory spread is not a 13.8x USD spread. G-price (2.5650x)
and G-volume (2.5641x) tie to two decimals, so their order is not meaningful.

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

PR #123 (hidden-root window handoff) was open when this model's registration was written against main cc4fe82. It merged at
253d9c12 after that (see the PREREG amendment for the timing). By registration it stays out of every number above. Its figures, cited from main: 14,493 core columns per token at D8/C2 (results.yaml
`qwen-hidden-root-handoff`, built and matched), and a hash share of columns of 0.887 there and 0.146 at D128/C64 (counted, not built;
`experiments/20261111-93-hidden-root-handoff/RESULTS.md`, counted-only table). They are column counts, not bytes, memory or time. Whether the D128 per-token cost of an in-proof handoff joins the volume
factor is left to a later amendment or lane.

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

- **U1, substitution check, every token proved.** At the central rate and plan volume this costs about 3 to 7 cents per 1,000 window
  tokens and fits a 1,024-token window on one H200. At the fork's own rates it costs about 1.5 to 10 dollars per 1,000. There windows
  are capped at 256 tokens at plan volume, and at 64 tokens with the built volume (the 10.10 scenario).
  Before cost matters at all, U1 is blocked on fidelity (#68, #88: no passing integer format), on the unbuilt DeltaNet GPU sub-proof,
  and on the 64-segment cap. Viability is **undecided**, and cost could decide it either way.
- **U2, sampled audit, a fraction f of windows proved.** Variable cost scales with f. At f = 0.01, over the same selected scenarios as
  U1, it is 0.43 to 65.6 GPU-seconds per 1,000 served tokens (about $0.00026 to $0.101), 100 times less than U1 in the same scenario.
  The high end carries the built volume and the 64-token window of the U1 high scenario. At plan volume only, at T = 1,024, the range
  is 0.4 to 26 GPU-seconds (script section 7a). Sampling does not make an oversized single proof fit: each sampled window still needs
  its own segment to fit. How that compares with serving is not established
  (no plain rate on main). The fixed cost may decide it instead. Upstream's start-up
  (68 to 79 s) is 1.6 to 1.8 times a central 1,024-token window proof, so U2 pays off only with a warm prover. U2 is the **only use case
  whose cost can be made small at every rate on main, by choosing f**. Its value depends on Q4 (#84: coverage per sample) and on the same blockers as U1.
- **U3, proof plus TEE.** Cost is U1's or U2's proving cost plus a TEE serving overhead that is not on main (unknown, additive). It is blocked first, not on
  cost: the unmodified prover calls `cudaHostRegister`, which is not allowed under CC-On (H200 bring-up, source reading, untested), and
  the live Tinfoil H200 leaves too little free memory for even the small example (#43 bring-up, phase 1).

## The next experiment to register

**GPU calibration of entries to time and bytes, plus the plain-inference denominator, in one rental.** On one H200 (or H100 if that is
what is available, labelled):

1. With the existing prover, prove at least 3 dense-family configurations spanning at least 2 orders of magnitude of committed entries:
   the small synthetic example, a planner proxy, and a mid-size proxy. Record peak GPU memory (sampled at 100 ms or finer, plus
   `cudaMemGetInfo` from the program if it can be added) and `cp_prove` wall time.
2. Fit memory = a + b x entries and time = c + d x entries, and report the fitted a, b, c, d with their spread. Decision rules proposed
   now, for the **dense family only**: if b is within 2x of 23 B per entry, the central memory rate is supported for dense segments;
   if within 2x of 220, the own rate is. If d puts the central time rate within 2x, the central rate is supported for dense entries.
   None of these makes the Qwen memory or USD columns stand, and none assigns U1 a window: the largest Qwen segment is a DeltaNet
   layer, and a window fit needs the intercept a and the actual coefficients, not a slope tolerance.
3. Same session, same card: stock vLLM on Qwen3.8-27B BF16, prefill tok/s and decode tok/s at 1, 8, 32 and 128 concurrent requests.
   That is the denominator for the multiple.

This does not measure a DeltaNet entry: no DeltaNet GPU sub-proof exists. It calibrates the dense family and fills the
plain-inference denominator, which is currently missing outright. Qwen fit and cost still need the DeltaNet GPU sub-proof and a
calibration of it. This is a proposal to register, not an authorization to spend.
