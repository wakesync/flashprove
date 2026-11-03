# Matched CPU verification baseline: no measured improvement

Issue #7. This is an executed measurement of **complete CPU verification of a stored synthetic-model proof**, including key, leaf and request checks. It is not a matrix microbenchmark, but neither is it inference, proof generation, real-model validation or verified-response serving latency. No implementation optimization is claimed or shipped by this change.

## Pinned inputs and environment

- Upstream: `9e2bdd8ff5bf9c62f18263d7dac189b0400b260c`.
- Fork: PR #4 head `133da749937115883c95edfc4b6e372c16209449`. This evidence branch adds only research files.
- Both verifier/blocks source trees are unchanged between those commits. Fresh independent builds produce **identical binaries**, SHA-256 `7f9efc1e86a848a3715c6cc870e465ac2a1c5e8fd1eac09e4809023de7604394`. Thus differences here are measurement noise, not a fork speedup.
- AMD EPYC-Rome KVM VM, 16 logical CPUs, about 30 GiB host RAM. Each invocation and its descendants pinned to logical CPU 15; explicit `-j 1` in both arms. Three stage processes compete on that single CPU. This is an allocation choice, not a claim to saturate the machine.
- Ubuntu g++ 13.3.0, stock `verifier/build.sh`: `-O2`, `-fno-ipa-modref`, all original hardening/assertion flags, DW=8, field=2. No native-architecture tuning, weakened checks or security parameters.
- Stored `examples/accepted-proof`, 64 prompt positions, covered `r=60 e=64`, exact-match policy. Synthetic weights, not an external checkpoint. One shared fixture directory for both binaries; hashes of every fixture file in `evidence/results.json`.
- Request proof **4,145,300 bytes**; key proof 1,096,408 bytes; leaf proof 536,952 bytes. These are different objects, not a single reported proof size silently including setup.
- Commitment ID: `79a5a2bc7a469b40df73dedf40abeb740671e8ae8077738bd3743897aeb22183` (from the stored example, permissible for this example only).

## Repeated measurements

One untimed-for-summary warmup per binary, then five repetitions each, alternating AB/BA ordering. GNU time measures each full verifier invocation; no cache flushing or amortization. Compiler processes had finished before measurement. All values below are seconds unless specified.

| Arm | All five wall times | Median | Min/max | Sample standard deviation |
| --- | --- | --- | --- | --- |
| Upstream | 2.67, 2.72, 2.59, 2.70, 2.66 | 2.67 | 2.59 / 2.72 | 0.0497 |
| Fork | 2.68, 2.87, 2.64, 2.71, 2.62 | 2.68 | 2.62 / 2.87 | 0.0991 |

Max-process RSS in KiB:
- Upstream: 157908, 157872, 157616, 157780, 157872.
- Fork: 157872, 157868, 157780, 157872, 157776.

**Memory limitation:** GNU time reports the maximum RSS of a process, not the simultaneous peak of the whole forked process tree. No cgroup-total or GPU memory claim. All ten measured runs had zero major faults. The initial exploratory pilot had cold faults and is excluded from this warm comparison.

The predeclared stop screen is `(max-min)/median > 10%`, checked after each paired repetition beginning with the third. Neither arm exceeded it (4.87% upstream, 9.33% fork). This is only a gross-instability screen, not statistical confidence or proof of exclusive resources. Shared-host services remain, there is no exclusive physical-core reservation, and the fork range is too broad for small performance claims. CPU PSI rises during the runs because three verifier children intentionally compete on one pinned CPU; it cannot by itself identify unrelated contention. Memory pressure stays negligible. Raw per-run CPU time, switches, page faults and pressure snapshots are retained.

**Conclusion: no performance improvement.** In particular, do not promote a median ratio between identical binaries to an optimization result.

## Verification and negative checks

- Both warmups and all ten measured honest verifications: exit **0**, entire final line **`YES`**.
- One full-length altered proof per binary, flipping the middle byte's low bit while holding all other inputs and the ID fixed: exit **1**, entire final line **`NO: proof-refused`** in both arms.
- Every honest receipt includes `covered: r=60 e=64 T=64`, `commitment:`, `proof of work:` and the complete `result-v1` line. See the `.stdout` files, not just this summary.
- Commitment lines explicitly retain **49 closeness rounds relying on an assumed coding theorem**. Proof-of-work lines retain **up to 32 work bits counted in 38 rounds**, least round **128.00** with work and **96.23** without it. These numbers are not an established security level.
- One mutation is a targeted regression check, not comprehensive adversarial coverage or soundness certification.

## Phase profile and why no speculative optimization

The existing verifier's internal timers provide a coarse phase profile without modifying the binary. Representative third upstream repetition:

- Request-stage wall duration: 2.582 s.
- Before reading request proof (scan, planning, configuration, request form, accounting): 1.544 s.
- Links plus last proximity test: 0.938 s.
- Remaining chains/table work: 0.083 s.

The request's pre-proof phase is approximately 60% of its elapsed duration under this allocation. **That does not identify a function consuming 60% of CPU:** key and leaf stages run concurrently and compete on the pinned CPU; phase and stage times must not be added. This identifies the next profiling region, not a justified patch. Source inspection also finds configuration work is intentionally repeated in isolated stage processes, with process-global parsing state. Sharing or caching it without preserving input binding, all validation paths and failure isolation is not a trivial correctness-preserving edit.

Function-level sampling is unavailable through the currently installed `perf` path (`perf` not installed; `kernel.perf_event_paranoid=4`). No privilege/config change or package installation was attempted. An unprivileged instrumented build is a possible follow-up, but was not executed and must not be described as a completed profile. No optimization was selected from intuition alone.

**Remaining blocker for the requested outcome:** a specific hot function and a bounded change with unchanged transcript/acceptance semantics have not been established. For proving/real-model E2E improvement, this CPU-only host and stored synthetic proof cannot supply the requested GPU witness/prove baseline; that belongs to the existing exclusive GPU lane. This PR establishes a measured no-improvement baseline, not fulfillment of the broader performance objective.

## Reproduce

Use separate worktrees at the two SHAs above. In each run `bash verifier/build.sh`, serially, and wait for both to finish. Do not run a suite/build concurrently with timings. Then:

```sh
python3 research/performance/compare_cpu.py \
  /path/to/upstream /path/to/fork /path/to/new-output-directory \
  --cpu 15 --repetitions 5
```

Choose an allowed CPU consistently on another machine. Requires Linux, Python 3, `taskset` and GNU `/usr/bin/time`. Output directory must not exist. The runner persists raw receipts and results after every call, refuses unexpected verifier results, and stops timing on its dispersion screen. It does not provision hardware, alter host settings or run the full suite. The altered proof is reconstructible from the pinned fixture and is not committed. Evidence paths replace the local workspace prefix with `<workspace>`; numeric results and verifier stdout are otherwise unchanged. The runner's post-run validation uses explicit checks rather than Python `assert` so `python -O` cannot disable them; measurements were collected with the equivalent assertions enabled.

Both build logs warn that a group-writable workspace ancestor could let another account modify sources/builds. No permissions were changed. This is a local reproducibility receipt, not a hostile multi-user build attestation.

PR #4 remains **HOLD** at its existing coverage gate. No full-suite rerun, missing-coverage waiver, merge or GPU spend is authorized by this benchmark.
