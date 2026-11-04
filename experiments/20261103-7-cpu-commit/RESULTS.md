# CPU commit/prover profile: FAIL, no adopted optimization

## Verdict

**FAIL against the preregistered wall-time threshold.** Ten alternating AB/BA pairs, two warmups per arm, fixed seed 0, CPU 13. The candidate reduced the observed median of the CPU reference workload by 6.51%, but the wall-time ranges overlap substantially. That is not a demonstrated speedup under this experiment's rule. No observations were removed and no second candidate or rescue timing run was tried.

The candidate was implemented and tested at `9be0e419`, then removed from production source. `candidate.patch` preserves the exact experimental change for reproduction. This PR is a profile and negative-result receipt, not a proposal to ship the optimization. No GPU, paid API or model-download spend occurred.

## What was actually reachable

There is **no CPU executable that proves a model's reply**. `cp_commit` and `cp_prove` require CUDA. `blocks/` supplies a CPU reference engine for the shared protocol routines, not the model inference/sub-proof implementation.

1. **Exact small-example CPU host setup:** the real `cp_with_configured()` entry point linked from `cp_verify.cpp` with the same symbol isolation used by `prover/build.sh:verifier_unit`. This is the function both production GPU programs call to parse, size, configure and check the public files. Inputs are `prover/examples/target_small_f2_roomy/{policy.txt,layout.txt,KL.bin}`, byte-identical to the stored accepted-proof configuration and the prior GPU receipt's configuration. Ten gprof-instrumented calls: median **0.477662 s**, SD **0.104150**, range **0.436565..0.755029**. These are profiling times, not an uninstrumented production latency estimate.
2. **Smaller CPU reference commitment and prover:** unchanged existing test fixtures `seam_file(4)`, `toy_model(3,{})`, 100 matrix rows of 64 field cells. `IndexCpu` encodes and builds two salted Merkle tables; `make_key` runs the range/one-time proof; `make_entry` runs the LINK proof; `prove_batch` creates three reference request files. The fixture retains its `sec 128` target and existing test proof-of-work settings. The request segments multiply toy vectors and bind replies; they **do not prove model inference or the correctness of the supplied replies**. The test-only fixture macros are not serving-build interfaces.
3. **Not reached:** GPU weight loading/checking and pinned-memory orchestration, worst-case checks on actual weights, streamed GPU weight-table encoding/Merkle generation, GPU range/linear kernels, GPU model forward pass and sub-proofs, full `cp_commit`/`cp_prove` execution, or deterministic production GPU artifact comparison. No timings are assigned to these regions.

The actual small example's table is 256 rows x 8,388,608 symbols. Merely materializing its base-field codewords in `IndexCpu` costs **16 GiB per table**, before other storage. This exceeds the registered 4 GiB limit, so a full CPU reference execution of that configuration was not attempted. The smaller reference fixture is explicitly a fallback, not a relabeling of the GPU workload.

## Hotspots and selected candidate

Generation-only gprof profile, ten independent processes, 1,395 self-time samples at nominal 10 ms/sample. `moncontrol(0)` stops profiling before validation and artifact writes. Percentages are **self samples in instrumented code**, not percentages of uninstrumented elapsed time. Inlining and instrumentation overhead limit precision.

| Rank | Function/region | Self seconds, ten calls | Self share | Calls, ten runs |
|---|---|---:|---:|---:|
| 1 | BLAKE2b compression `Blake2bF::F` | 4.45 | 31.90% | 23,218,520 |
| 2 | CPU oracle encoding `EngineCpu::encode_rows` | 3.59 | 25.73% | 1,730 |
| 3 | Hash byte feeding `HasherT::push` | 1.02 | 7.31% | 145,296,350 |
| 4 | Two-digest hash construction | 0.78 | 5.59% | 8,109,750 |
| 5 | Synthetic `TestCoins::bytes` | 0.43 | 3.08% | 1,060 |
| 6 | Exact integer division `Big::divmod` | 0.29 | 2.08% | 2,363,950 |

The actual-example host configuration has a different profile: `Big::divmod` 23.00% (0.49 s), limb copies 11.74% (0.25 s), shifts right 9.39% (0.20 s), Big multiplication 7.98% (0.17 s), limb release 7.04% (0.15 s), shifts left 5.63% (0.12 s). Those are ten-run aggregate self times out of 2.13 sampled seconds. This confirms setup remains arithmetic-heavy after PR #27; it does not establish the CPU share of the prior 18.8 s GPU commitment.

**Selected single candidate:** direct little-endian `push_u64` stores when eight bytes fit in the hash buffer. Finished-state and maximum-length checks remain; crossing/full-block appends retain the old generic path, including delayed last-block compression. The CUDA device branch is unchanged. Compression is already explicitly round-unrolled, while CPU encoding uses a different implementation from GPU encoding. The word-feed change was selected as the small, low-risk host hashing opportunity, not as a claim that byte feeding exceeds compression in cost. No arithmetic, randomness schedule, transcript order, checks, policy, compiler optimization level or thread count changed.

## Registered A/B results

Seconds; SD is the sample standard deviation. A is baseline, B is candidate. Primary is complete reference generation from configuration through the three proof files, excluding validation and file writes. Every row has **n=10 per arm**. Raw measurements, load averages and artifact hashes are in `results/raw.json`; full precision in `results/summary.json`.

| Metric | A median | A SD | A min..max | B median | B SD | B min..max | Median reduction |
|---|---:|---:|---:|---:|---:|---:|---:|
| **All generation, primary wall** | **1.489418** | **0.184686** | **1.452337..1.942321** | **1.392443** | **0.178384** | **1.347229..1.951097** | **6.51%** |
| Commit portion, wall | 0.685878 | 0.053446 | 0.658267..0.847377 | 0.659604 | 0.022961 | 0.620891..0.704670 | 3.83% |
| Three-request proof batch, wall | 0.799992 | 0.147457 | 0.772286..1.220104 | 0.738717 | 0.168243 | 0.721649..1.268536 | 7.66% |
| All generation, process CPU | 1.486127 | 0.041442 | 1.452313..1.601287 | 1.383506 | 0.035398 | 1.324587..1.437140 | 6.91% |

The secondary process-CPU ranges do not overlap. **That does not rescue the registered wall-time FAIL** and is not promoted to a performance headline. The shared KVM host's one-minute load was 12.45..14.59 during the experiment; no exclusive CPU was available. Some wall times greatly exceed process CPU time, consistent with scheduling interference, but this is not a license to delete them or change the endpoint. No experiment build ran during primary timing.

Baseline uninstrumented stage medians, n=10: configure 0.119037 s, two tables 0.036811 s, make_key 0.411353 s, make_entry 0.112951 s, prove_batch 0.799992 s. Component medians need not sum to the median total. In the reference commit portion, the range/one-time proof is the largest stage; the initial two Merkle commitments are much smaller.

## Byte identity and correctness

The harness compares actual bytes, not hashes alone, for every run. Both arms produced identical anchor and leaf roots, key file, entry file and three request proof files in all 24 warmup/measured calls, and in correctness-only runs for seeds 1..5. Every call verifies honest key/entry/proofs and rejects one last-byte bit flip in each of the five files. This establishes equality of the **reached reference artifacts** for six seeds, not a proof of equivalence for all inputs or for the unexecuted GPU path.

Seed 0 SHA-256 values, identical in both arms:

```text
167600d501043e54b851165bbfff3ba460d45d3282597b5ef354972476bab9e9  anchor.root
ef3ba5636e40e5c94ea92333fb6778894947c3e026f281d4249f0d6946d6a01e  leaf.root
23259689257229aadaa3145de2d0f3eb6fd202f2dd76d1c0f7870de5c2b3563a  key.bin
4ece3cc9253ea5a26716c867dd3eaaa3e9fd811124cb6827f4e2c57ec642ac23  entry.bin
2cbc0d1ceb9d9de928e6661b27af749e70af8b26bcb218f530360be1fc410ff5  proof0.bin
cd5823c9577dd94f8b3c5064fcead3a738b0dbca62db8951ee3eeaf29b4a63c3  proof1.bin
373ad052246c0cc83adcdf5da59ba144e96f04bdb84bded6ae67b3835302eee1  proof2.bin
```

Additional seed hashes and file lengths: `results/correctness-hashes.json`. The new word-feed test checks 811,403 comparisons across all pending-buffer offsets, unaligned words, full/split blocks, suffix lengths, hash-chain prefix state and post-finish/post-prefix rejection. It passes against both the baseline and candidate. Existing targeted candidate tests pass: hash calls (181), compression known answers (14), hash modes (2,968), older modes (149), code (510 shapes), and tree tests. This was not the complete repository test suite.

ASan+UBSan candidate builds of the complete reference harness and the word-feed test both exited 0, with no diagnostics. The sanitized reference generated the same seven seed-0 artifacts as baseline, byte-for-byte. Logs and identity receipt are in `results/sanitizer-*`. The experimental word-feed test is kept under this experiment, not added to the production test tree after rejecting the candidate.

## GPU follow-up plan, not executed

**First recommendation: independently rerun this CPU trial on a quieter host before spending money.** The primary gate failed and the GPU's heavy encoding/hash kernels do not use this host fast path. There is no measured GPU benefit to justify adopting it.

If Shadow separately approves a GPU trial:

- One exclusive H100 80 GB, pin CUDA 13.2.86 and both source revisions, identical CPU quota, affinity, driver and power cap. Build both arms and run the existing small synthetic configuration. Profile host vs GPU phase contributions before interpreting the CPU-reference numbers as transferable.
- Two warmups and ten measured AB/BA pairs per arm, record full commit and prove wall times plus phase logs. Keep the same non-overlapping-ranges and >=5% median threshold. At roughly 18.8 s commit + 2.35 s prove per call, 24 calls require about **8.5 minutes of timed workload**, plus verification and orchestration. Allow **15..20 minutes on one H100 with binaries ready**, or **50..60 minutes including two cold builds** (prior cold builds took roughly 18..20 minutes each).
- For byte identity use only the repository's explicitly non-serving deterministic synthetic test mode (`-test-seed`, `-test-coins`), with fixed seed material and matching synthetic fixtures. Check repeatability in baseline first. Compare all generated public commitment/proof bytes and verify them with an independent stock verifier. Do not compare fresh randomized production runs and call expected randomness a regression. Do not use deterministic coins with secret real weights. If serving mode is separately timed with fresh randomness, label it as a different experiment and do not conflate its outputs with deterministic correctness runs.
- Illustrative estimate at **$2.40/H100-hour**: **$0.60..$0.80** ready-built, or **$2.00..$2.40** cold-build compute; allow **$3..$4 all-in** for setup, storage and billing overhead. This is not a live quote. Approval is required before any rental or GPU command. Actual spend in this lane: **$0**.

## Reproduction and audit trail

- First commit: `5467e232`, PREREG only. Discovery/candidate-freeze commit: `f2909c2c`. Candidate implementation: `9be0e419`. Environment, flags, seeds, binary hashes and fixture hashes: `ENV.json`.
- `bash experiments/20261103-7-cpu-commit/build.sh scratch/reproduce` builds A from archived baseline headers and B by applying `candidate.patch` to a separate copy. It also builds baseline profiling programs; no CUDA is invoked. The scratch path must be new, without spaces.
- `python3 experiments/20261103-7-cpu-commit/bench.py --a scratch/reproduce/reference-A --b scratch/reproduce/reference-B --out scratch/reproduction-results --cpu 13` reproduces the registered ordering and checks. The output path must not exist. Confirm the selected CPU is available on a different host.
- Compile `word_feed_test.cpp` with `-I scratch/reproduce/base/blocks` and then `-I scratch/reproduce/candidate/blocks`, using the reference build flags, and run both. Sanitizer builds add `-O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined`; run with `ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1`.
- The targeted test command at the candidate commit was `make -C blocks OUT=<new-private-output-directory> CXX=g++-13 -j2 TESTS='hash/tests/calls_test.cpp hash/tests/functions_test.cpp hash/tests/mode_test.cpp hash/tests/older_test.cpp hash/tests/word_feed_test.cpp code/tests/code_test.cpp tree/tests/tree_test.cpp' test`. On the final evidence-only tree, use the candidate header tree and the experimental word-feed source instead. The mode/tree tests intentionally abort child processes; setting `ulimit -c 0` avoids slow system core-dump handling.
- For gprof, run the generation profiler ten times with separate `GMON_OUT_PREFIX` names; aggregate **only numeric-suffixed gmon files**, not the similarly named `.log` files. Do the same for `configure-prof` on `prover/examples/target_small_f2_roomy`. Published profiles retain the top 75 symbols; the runner source regenerates all call graphs.
- Initial setup errors were corrected before timing: a missing `<iostream>` include in the new harness; a too-short source-digest macro rejected by the verifier's compile-time check (replaced by the build script's real digest); a glob accidentally passed `.log` files to gprof (aggregation rerun on numeric-suffixed profile files). No failed attempt or instrumented binary entered A/B timing.

No README, claim ledger, model support claim or public performance headline was changed. Independent replication and GPU compatibility remain open.
