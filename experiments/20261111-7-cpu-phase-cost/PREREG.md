# PREREG: 20261111-7-cpu-phase-cost
Issue: #7. Lane: cost7. Date (UTC): 2026-11-11T04:22Z. Base commit: 8d5793374ece39954b48b8a86f54e6bde1d193e5.

## Hypothesis
On this repository's two committed CPU-runnable proof profiles, with a frozen benchmark manifest, a phase-separated measurement shows one phase dominating verified-before-release latency:
- **Profile B (Qwen DeltaNet head, two lookups, stage 1 of `research/operators/qwen_deltanet_m2_build/`):** proving dominates. Cold, the prove phase is at least 60% of the median end-to-end verified-before-release latency, and independent verification is the second largest phase.
- **Profile A (CPU reference protocol fixture of PR #40, `seam_file(4)` / `toy_model(3)`, 100-row matrix):** cold, the commit phase (two tables + key file + entry file) and the three-request proof batch are the two largest phases, and amortized over K batches on one commitment the per-batch cost falls to the batch proof plus its share of verification, so the amortized per-batch verified latency is below 50% of the cold end-to-end latency.

## Metric
All times are wall seconds from `std::chrono::steady_clock` inside the binaries, plus process wall from the Python runner's `time.monotonic()` around each child process. Phases:
- **startup/setup:** process wall minus the sum of in-process phases (exec, loader, static init, exit), plus, for A, `configure` (parse and size the public files), and for B, nothing beyond that (its shape is compiled in).
- **commit (A only):** `IndexCpu` x2 (encode + salted Merkle tables), `make_key` (range/one-time proof), `make_entry` (LINK proof). Reported separately and as a sum. Profile B has no commitment step: every input of the stage 1 statement is public (README of that directory); reported as "none, not applicable", not as zero cost of a commitment.
- **witness generation:** A: the toy matrix and its table rows (`toy_matrix_in_range`, `lin_table_rows`). The per-request witness vectors inside the library's `prove_batch` are drawn inside that call and are not separable without changing it; they are counted in prove and this is stated. B: `build()` of the witness, the C++ vs reference check, the witness-free derivation check, sizing and the table (the existing `build_s`).
- **prove:** A: `prove_batch` for 3 requests (request bytes {1,2,3,4}, {5,6,7}, {8,9}; replies 1001..1003). B: `two_prove` (existing `prove_s`).
- **independent verification:** a separate verifier process that reads only the public files and proof bytes written by the prover process. A: `configure`, `check_key`, `check_entry`, then `check_proof` per proof. B: `verify_stage1(words, proof)` (decode + derive + proof verifier).
- **end-to-end verified-before-release latency:** prover process wall + verifier process wall, run back to back, files on local disk.
- **amortized:** A: one prover process makes the commitment once and then proves K batches of 3 requests (K = 10, or fewer if the table's column budget refuses earlier; the refusal is recorded and K is stated), one verifier process checks key and entry once and then every proof. Amortized per-batch cost = (prove of batches 2..K) median and (check_proof of those batches' 3 proofs) median. B: one prover process proves 4 statements (seeds), one verifier process checks the 4; per-statement cost from statements 2..4.
- **proof bytes** (file sizes), **peak RSS** per process: the kernel's high-water mark `ru_maxrss` returned by `os.wait4` for the child (one value per process, not sampled over time); also the in-process `getrusage` value where the binary already prints it.
- **positions/s:** B: T = 4 head positions per statement, every position has a proved output o_t, so prompt positions/s and proved output positions/s are both T / prove seconds and T / end-to-end seconds; there is no prefill/decode split in this statement and no generation. A: not defined (toy requests are byte strings, not model positions); reported as "not applicable".
- **failures:** every nonzero exit, refusal or rejection is retained in the raw files and counted.
No generated-tokens/s and no overhead-vs-inference ratio are reported: no matched plain-inference baseline is measured in this run.

## Acceptance threshold
Fixed now, per profile, on the cold cell (n = 10):
- B PASS if prove median / end-to-end median >= 0.60 AND the prove min..max range does not overlap the next largest phase's min..max range AND verification is the second largest phase by median.
- A PASS if (i) commit-sum and prove are the two largest phases by median, each range non-overlapping with every smaller phase's range, AND (ii) the amortized per-batch verified latency median (prove + check_proof x3 of one batch) is below 50% of the cold end-to-end median, with non-overlapping ranges (amortized max < cold min).
- Otherwise FAIL for that profile, published as is. The phase table is the deliverable either way.

## Kill criterion
Hard stop for the lane: 2026-11-11T06:30Z wall clock (including any time queued in `fp-heavy.sh`). Registered run budget: 45 minutes elapsed from the moment `fp-heavy.sh` grants the slot (the runner logs it). If the slot is not granted by 05:50Z, or the budget ends, publish what finished as partial (KILLED for missing cells). CPU only, no GPU, no spend, no downloads.

## Runs
- n = 10 cold runs per profile (one prover process + one verifier process each), and n = 10 amortized processes per profile (A: K batches each; B: 4 statements each). Seeds: A uses seeds 0..9 (amortized batches use coin seed + 62 + 1000 k); B uses fixtures seeds 1..10 from `research/operators/qwen_deltanet/reference.py` (amortized process i proves seeds i, i+1, i+2, i+3 modulo 10, starting at 1).
- Ordering: interleaved by repetition (A cold i, B cold i, then after all cold, A amortized i, B amortized i). No warmup runs are excluded; there are none. No run is excluded; failures are retained.
- All runs through `fp-heavy.sh` with `taskset -c 6-11` (6 cores). The binaries are single-threaded; the pin bounds placement, not parallelism. Host shared and loaded; load average logged at each run.
- Toolchain: g++ 13.3.0, flags of the existing build scripts (`-O2 -fno-ipa-modref -std=c++17 -pthread -DBLK_FIELD=2`; profile B adds `-DBLK_HASH=1 -Wall -Wextra` as its `record.py`). The harness sources are new files under this directory; library and stage 1 sources unchanged.
- Debug before the registered run uses only fixtures the registered suite does not use: A with seeds 900..902, B with the `-DSTAGE1_D=16` debug build and seed 99. No number from a debug run is reported.

## Prior art
- **EZKL** (zkonduit): publishes per-model benchmarks split into setup (key generation), witness generation, prove and verify times plus proof size and memory, on stated hardware; Halo2/KZG, so setup is a large separate phase. Monetary figures are not part of the core benchmarks.
- **zkLLM** (Sun, Li, Zhang, CCS 2024): reports commitment, prove and verify time and proof size per LLaMA-2 size on GPU (A100), for one forward pass over a fixed prompt length; no separate "verified before release" latency.
- **Jolt** (a16z): reports prover time and proof size per RISC-V cycle count and separates preprocessing from proving; CPU benchmarks on stated machines.
- **Expander / Polyhedra**: reports GKR prover throughput (circuits/s, time per layer) on CPU and GPU, with verifier time; preprocessing separate.
- **In this repository:** PR #40 (`cpu-commit-profile`, `experiments/20261103-7-cpu-commit/`) measured profile A's stages in one process (configure 0.119 s, two tables 0.037 s, make_key 0.411 s, make_entry 0.113 s, prove_batch 0.800 s; medians, n = 10, CPU 13) as the baseline arm of a hashing A/B, verification in the same process and untimed. `experiments/20261109-32-qwen-deltanet-lookup-build/` measured profile B's build/prove/verify (prove median 13.667 s, verify 2.990 s, n = 10) with verification in the prover process. Q3 desk study (PR #85) found no phase-separated cost breakdown on main.
- **What is new here:** a frozen manifest; independent verifier processes reading only files; process startup and end-to-end verified-before-release latency; cold vs amortized cells with the amortization count; per-process peak RSS from the kernel; positions/s with its denominator; one table per profile. It does not re-test the hashing candidate of PR #40 and says nothing about the GPU path or Qwen3.8-27B.

## Amendments
(empty at registration)

### 2026-11-11 (after the registered run, in response to the two reviews of PR #106)
Nothing in this file above this heading changes. The registered run, its raw files under `runs/`, the thresholds and both verdicts (A FAIL, B PASS) stay as they are. No new registered run is made.

1. **Replay path.** `run.py registered` stops at the wall-clock hard stop 2026-11-11T06:30Z above, so after that moment the registered command runs no child process. That stays: the `registered` mode keeps this cutoff and its behaviour unchanged. A separate, explicitly labelled `run.py replay` mode is added for anyone reproducing the experiment later. It runs the same suite in the same order, ignores the registered wall-clock stop, and has a finite budget relative to its own start (`--budget-min`, default 45, the registered budget). It can be limited to the first N repetitions per cell (`--reps`, default 10). It refuses to write into this directory's `runs/` and needs a fresh output dir. A replay is a replication attempt, never part of the registered result. A test with the clock set after the cutoff (`test_replay.py`) shows `registered` still stops and `replay` runs its child processes; its receipt is a new file `runs/replay-check.json`, no committed run file is touched.
2. **Disclosure of two wordings of the A amortized metric.** "Metric" says the amortized per-batch cost is the median of prove over batches 2..K and the median of check_proof over those batches (two separate medians, summed). "Acceptance threshold" says "the amortized per-batch verified latency median (prove + check_proof x3 of one batch)" (median of per-batch sums). `analyze.py`, committed after the run (f70ff0c, not in the harness commit 499694a), implements the threshold wording. It is kept: it is the sentence that defines PASS/FAIL, it reads "of one batch", and it is the more conservative of the two here. RESULTS.md reports both numbers (0.500203 FAIL under the analyzer's reading; 0.499870 under the literal Metric wording, which would pass). The verdict stays FAIL.
