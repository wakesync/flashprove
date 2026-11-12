# RESULTS: Q3 cost model from merged numbers (desk, Part of #7)

**Desk result, extrapolated, not measured.** No proof run, no GPU, no provider call. No results.yaml row: nothing here is a measurement.
Full note: [research/cost/Q3-COST-MODEL-1112.md](../../research/cost/Q3-COST-MODEL-1112.md). Output of the script: [model-output.json](model-output.json)
(`python3 research/cost/q3_cost_model_1112.py --json experiments/20261112-7-cost-model/model-output.json`, deterministic).

## Against the registration

- Method as registered: every evidence input is read from a file on main and labelled. Prose sources are parsed by pattern, and the
  script fails if the text has changed. PR #123 was open when the registration was written against main cc4fe82, and merged at 253d9c12
  (01:27:30Z, eight seconds before the PREREG commit's timestamp). By registration it
  stays out of every computed number; the note cites its figures from main as context only.
- No threshold was registered. Deliverables as registered: script, table, ranked gap list, per-use-case statement.
- The template sections (Hypothesis, Metric, Acceptance threshold, Kill criterion, Runs, Prior art) were missing from the PREREG.
  They were added after code, by a dated `## Amendments` entry (round-1 review). The registration text of b84fc2d9 is unchanged.
- Deviation: the PREREG named model-r3.json's three time rates and four memory rates. The script also reads #44's two full-size
  Maverick rates as a cross-check (4.0x). It is not used in any headline. That is an addition, not a change of method.
- Deviation: the "estimator miss" factor (#73 measured / #66 estimated, 2.22x) is reported in the gap list but not multiplied into the
  high scenario. It is CPU evidence about one estimator. The volume factor (2.56x) is multiplied in, as registered.
- Deviation (round-1 review fix, after code): the built-volume scenario is now carried through memory and window selection, not
  only time. The first version took the high scenario's window (256) from the plan volume while multiplying its time by the built
  volume. Old vs new `model-output.json`:
  - `envelope_usd_per_1k.high`: 10.098217412657844, unchanged bit for bit. The small-example rate is flat per token in T (max/min
    over T = 1.000000000), so the window does not change it.
  - `envelope_usd_per_1k.high_window`: 256 -> 64 (built volume, own rate: T_max 119 streamed, 66 resident). Added
    `high_window_plan_volume_own_rate` = 256.
  - Added `fit_window_built`, `largest_segment_gb_built` (own rate at built volume: T = 64 68.15 GB, T = 128 136.29 GB, T = 256
    272.59 GB), `largest_segment_entries_per_token` (plan 1,744,122, built 4,841,568), `u2_scenarios`,
    `small_example_per_token_flat`, `built_mixer_columns_per_layer_token`. Added `t_max_resident` to `fit_window` rows.
  - Inputs: price labels changed from `measured` to `invoiced` (2.16/h) and `quoted` (2.41/h, 5.54/h); the two #44 USD per Mtok
    figures to `calculated`. New inputs read from main instead of hard-coded: `fit_rule_gb` (127), `m2_head_tokens` (16),
    `deltanet_layers` (48), `v_heads` (48), `maverick_tokens_per_batch` (24 x 1,024), `h100_box_gpus` (2), and the 3.00/h
    assumption's source text. Values unchanged.
  - Every number that was in the first version is unchanged.
- Deviation (same fix): U2 is now also reported for the same two selected scenarios as U1 (section 7b). The 0.4 to 26 GPU-s range at
  f = 0.01 is plan volume only (section 7a).

## Answer

- **The selected conditional variable-proving scenarios span $0.0255 to $10.0982 per 1,000 window tokens (prompt plus reply).**
  Central 0.0354 at the assumed 3.00/h. About 400x apart, and main cannot narrow it. These are not bounds on actual Qwen proof cost:
  the DeltaNet GPU sub-proof does not exist, fidelity format and H200 speed are open, and fixed costs are omitted.
- Largest gaps: GPU-seconds per DeltaNet entry (60x), bytes per entry (14x, a memory spread, not a USD spread), then price, built
  volume (these two tie, 2.5650x vs 2.5641x), window length and estimator miss (each 2.2 to 2.6x).
- One H200, plan volume: fits a 1,024-token window at 23 B per entry (41 GB). It does not at 220 B per entry (393 GB; the largest window
  is 256 tokens, or 128 with weights resident). With the built volume of the high scenario: 64 tokens at 220 B per entry (272.6 GB at
  T = 256), streamed or resident; 1,024 streamed / 512 resident at 23 B per entry. 81 segments against a cap of 64 at every rate.
- Multiple of plain inference: not established (no plain Qwen rate on main).
- U2 is the only use case whose variable cost can be made small in every selected scenario (f = 0.01: 0.43 to 65.6 GPU-s, about
  $0.00026 to $0.101 per 1,000 served tokens). U1's viability is undecided on cost. U3 costs U1 or U2 plus an unknown additive TEE
  overhead, and is blocked before cost (CC-On `cudaHostRegister`, free memory on the live H200).

## Next experiment (proposal, not authorization to spend)

GPU calibration of the existing prover: memory and time against committed entries, over at least 3 dense configurations spanning at
least 2 orders of magnitude, plus stock vLLM Qwen3.8-27B BF16 prefill and decode rates on the same card. This calibrates the dense
family and the plain-inference denominator only. Qwen fit and cost still need the DeltaNet GPU sub-proof and its calibration.
Decision rules are in the note.
