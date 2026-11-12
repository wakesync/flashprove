# RESULTS: Q3 cost model from merged numbers (desk, Part of #7)

**Desk result, extrapolated, not measured.** No proof run, no GPU, no provider call. No results.yaml row: nothing here is a measurement.
Full note: [research/cost/Q3-COST-MODEL-1112.md](../../research/cost/Q3-COST-MODEL-1112.md). Output of the script: [model-output.json](model-output.json)
(`python3 research/cost/q3_cost_model_1112.py --json experiments/20261112-7-cost-model/model-output.json`, deterministic).

## Against the registration

- Method as registered: every input is read from a file on main and labelled. Prose sources are parsed by pattern, and the script fails
  if the text has changed. Unmerged PR #123 appears only in the gap list.
- No threshold was registered. Deliverables as registered: script, table, ranked gap list, per-use-case statement.
- Deviation: the PREREG named model-r3.json's three time rates and four memory rates. The script also reads #44's two full-size
  Maverick rates as a cross-check (4.0x). It is not used in any headline. That is an addition, not a change of method.
- Deviation: the "estimator miss" factor (#73 measured / #66 estimated, 2.22x) is reported in the gap list but not multiplied into the
  envelope. It is CPU evidence about one estimator. The volume factor (2.56x) is multiplied in, as registered.

## Answer

- USD per 1,000 window tokens: low 0.026, central 0.035 (at the assumed 3.00/h), high 10.10. That is about 400x apart, and main cannot narrow it.
- Largest gaps: GPU-seconds per DeltaNet entry (60x), bytes per entry (14x), then price, built volume, window length and estimator miss (each 2.2 to 2.6x).
- One H200: fits a 1,024-token window at 23 B per entry (41 GB). It does not at 220 B per entry (393 GB; the largest window is 256 tokens, or 128 with weights resident). 81 segments against a cap of 64 at every rate.
- Multiple of plain inference: not established (no plain Qwen rate on main).
- U2 is the only use case whose cost can be made small at every rate on main. U1's viability is undecided on cost. U3 is blocked before cost (CC-On `cudaHostRegister`, free memory on the live H200).

## Next experiment

GPU calibration of the existing prover: memory and time against committed entries, over at least 3 dense configurations spanning at
least 2 orders of magnitude, plus stock vLLM Qwen3.8-27B BF16 prefill and decode rates on the same card. Decision rules are in the note.
