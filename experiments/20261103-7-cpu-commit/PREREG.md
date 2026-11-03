# PREREG: 20261103-7-cpu-commit
Issue: #7. Lane: cpu-commit-profile. Date (UTC): 2026-11-03. Base commit: 29907e5fbe648b9ec246cebf9d757511a751fca2.

## Hypothesis
An output-preserving change to the largest actionable CPU hotspot in commit/prover work reduces the median CPU-reachable workload time by at least 5%, with non-overlapping observed ranges.

## Metric
Elapsed wall seconds (steady clock) for a fixed CPU-reachable commit/prover workload, one pinned CPU thread. Also report process CPU seconds and stage times. First establish reachability by source inspection, profile unmodified code using gprof or unprivileged sampling and stage timers, then freeze exactly one candidate and the primary workload in a dated amendment before changing production code. Distinguish actual small-example host configuration from the library's smaller synthetic reference-prover fixture. No CPU reference timing will be called an end-to-end cp_commit or cp_prove measurement. Rank hotspots with counts/time and state unmeasured GPU regions explicitly.

## Acceptance threshold
PASS only if candidate maximum wall time is strictly less than baseline minimum AND median reduction is at least 5%, on at least 10 timed runs per arm. Every deterministic serialized proof/commitment artifact reached by the experiment must be byte-identical (SHA-256 plus byte comparison) across arms. Checks must still accept honest outputs and reject tested mutations. GPU output equivalence is not claimed without a GPU run. If only CPU-only code changes, state that and do not claim GPU benefit.

## Kill criterion
No GPU or paid API use. Stop after 90 minutes of CPU experiment work or if a useful reachable candidate cannot be isolated. Stop expensive reference fixtures if one call exceeds 120 seconds or 4 GiB RSS; report the reachability limit rather than reduce security parameters silently. A failed performance threshold is FAIL; inability to run a preregistered comparison or correctness failure is KILLED. No second candidate after looking at A/B outcomes.

## Runs
At least 10 measured runs per arm, two untimed warmups per arm. Pairs alternate AB, BA, AB, BA, continuing through ten pairs (20 measured calls). Fixed deterministic test fixture and seeds. No outlier removal; include all completed planned calls. Exclude warmups and profiling-instrumented binaries from primary measurements. Keep failed/incomplete calls separately and report any invalid comparison. No compilation concurrently with timings. Record affinity, flags, toolchain, hardware, load, source revisions and seeds in ENV.json and raw results. Report median, sample SD, min/max for each arm. Additional seeds and sanitizers are correctness-only.

## Prior art
This repository already provides a CPU reference engine and shared protocol routines in blocks/, while cp_commit/cp_prove are CUDA programs. Its frame tests generate and verify synthetic key, entry and request files. PR #27 optimized exact arithmetic shared by configuration; its profiling method and prior negative accounting-reuse trial motivate measurement rather than assuming hashing dominates. Existing GPU receipts in research/gpu identify approximately 18.8 s commitment and 2.35 s proving for one small synthetic run, not CPU attribution. Relevant implementation references are blocks/README.md, blocks/engine/engine_cpu.h, blocks/frame/check_key.h, prover/hash_commitment/hf_commit.cu and hf_commit_once.cuh. This experiment is implementation engineering, not a new proof system or cryptographic claim.

## Amendments
