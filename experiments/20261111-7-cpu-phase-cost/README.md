# CPU phase-separated cost harness (issue #7)

Measures, phase by phase, what it costs to make a proof with one of this repository's two CPU-runnable proof programs and to check it in a separate process. Registration `PREREG.md`, numbers and verdicts `RESULTS.md`, frozen manifest `ENV.json`.

## What each harness proves, and what the verifier recomputes

- **`phase_a.cpp` (profile A):** the CPU reference protocol fixture of PR #40, unchanged in substance (`experiments/20261103-7-cpu-commit/reference.cpp`), split into `prove` (configure, commit, K batches of 3 requests) and `verify` (configure from the same public files, read key/entry/proof files, `check_key`, `check_entry`, `check_proof` per proof). It proves the reference protocol's commitment, its range and LINK proofs, and per-request toy segments that bind the request and reply. It does **not** prove model inference or that the replies are right. Its seed-0 artifacts are byte-identical to PR #40's.
- **`phase_b.cpp` (profile B):** includes `research/operators/qwen_deltanet_m2_build/stage1.cpp` unchanged (its `main` renamed) and splits it into `prove` (witness, `two_prove`, write statement words and proof) and `verify` (read the two files, `verify_stage1`). It proves one synthetic Qwen Gated DeltaNet head's recurrence and output for T = 4 positions (D = 128, F = 12) at research security; the verifier decodes all public words, derives every relation itself and runs the unchanged proof verifier. Not covered: projections, norms, MLP, other heads and layers, commitments to inputs or state, fidelity to the real model, zero knowledge.
- **`run.py`:** pins each child to `COST7_CORES` (default 6-11), times it with `time.monotonic()`, takes peak RSS from `os.wait4` (`ru_maxrss`, the kernel high-water mark; one value per process, not sampled) and writes one JSON line per process.
- **`analyze.py`:** the phase definitions of PREREG "Metric", statistics and the registered verdicts. **`hashes.py`:** artifact SHA-256s and the PR #40 byte-identity check. **`scrub.py`:** replaces the clone's absolute path in the raw log with ".". **`fixtures.py`:** profile B inputs by the unchanged reference recipe. **`build.py`:** compiles both with the flags of their original build scripts.

## Not covered

GPU (`cp_commit` / `cp_prove`), any whole model, Qwen3.8-27B, generated tokens/s, overhead vs plain inference (no baseline measured), money.

## Reproduce

From the repository root, CPU only:

```
python3 experiments/20261111-7-cpu-phase-cost/build.py scratch/bin
python3 experiments/20261111-7-cpu-phase-cost/fixtures.py registered scratch/fx
python3 experiments/20261111-7-cpu-phase-cost/run.py registered scratch/bin scratch/fx <new_out_dir>   # about 16 min; inside the host's heavy-job gate on a shared host
python3 experiments/20261111-7-cpu-phase-cost/analyze.py <new_out_dir>/runs.jsonl <new_out_dir>/summary.json
```

`analyze.py` with no arguments regenerates `runs/summary.json` from the committed `runs/runs.jsonl`. `hashes.py` needs the artifacts of a run under `runs/artifacts/` (not committed, 0.5 GB). Debug fixtures (`fixtures.py debug`, `build.py --debug`, `run.py debug`) are never part of a reported number.
