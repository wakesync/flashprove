# BF16 / FP8 reference divergence harness (#8)

What this is: a CPU harness that compares the committed integer operator relations of `research/operators/qwen_ops` (PR #67) with two separately defined float references, BF16 and FP8 (OCP E4M3), operator by operator, on real-valued inputs frozen by hash.

What it is not: no proof is built or checked, nothing is about real weights or a model, no token or reply agreement. The verifier is not involved; "integer" here means the exact integer arithmetic the proof relations specify, re-implemented in Python (`refs.py`) and checked word for word against the C++ fixture program (`xcheck.py`, 150 / 150 cases).

Files:
- `PREREG.md`: hypothesis, reference definitions, conversion, splits, rule (registered first).
- `splits.py`, `splits/`: seeded input splits and their SHA-256 manifest (`--check` regenerates and compares).
- `refs.py`: BF16 / E4M3 rounding, float semantics per op, integer lowerings that read the committed tables.
- `test_formats.py`: rounding self-test (independent bit-level BF16, enumerated E4M3).
- `harness.py`: `calibrate`, `run heldout`, `run stress`, `debug`.
- `summarise.py`, `context_table.py`: aggregates and the verdict.
- `env.py` -> `ENV.json`; `add_results_row.py` -> the `ref-divergence-ops` row in `research/results.yaml`.
- `RESULTS.md`: numbers, verdict, and what the verdict does and does not mean.

Reproduce: the command list in `RESULTS.md` section 6. Every split runs in about 1 s of CPU.
