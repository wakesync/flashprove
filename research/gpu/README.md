# One H100 small synthetic proof run, upstream quickstart, independent CPU verification

**Status: evidence only. One cold run of the upstream small example; no source change.** Nothing outside `research/gpu/` is modified. Upstream source was the pinned commit `9e2bdd8ff5bf9c62f18263d7dac189b0400b260c`, unchanged (`logs/git-status-before.txt` and `logs/git-status-after.txt` are empty).

## What was run

- `examples/quickstart-gpu.sh`, unmodified, on one rented H100 80GB (Vast.ai marketplace, on-demand). It builds the verifier and the default (serving) prover programs, then runs `prover/examples/run_target_example.sh target_small_f2_roomy`: synthetic ("made-up") weights, one commitment (`-M 1`), one request (`own_choices.req`), one proof, one verifier call.
- No model weights were downloaded. No test seeds, no test build, no full-size config.
- Toolkit: the pip recipe from `prover/docs/build.md`, line by line, into a fresh user directory. Resolved: cuda-toolkit 13.2.2, nvcc **V13.2.86**, cuBLAS 13.4.1.3 (`logs/pip.log`, `logs/nvcc.txt`). The image also shipped a CUDA under `/usr/local/cuda`; the recipe's nvcc was first on PATH and every `Compiled by` line names it (3/3).
- Everything ran as an unprivileged account. Compiler gcc/g++ 13.3.0.

## Machine

| item | value |
|---|---|
| GPU | NVIDIA H100 80GB HBM3, compute capability 9.0, MIG disabled, 0 MiB used before start |
| driver | 615.71.09 (upstream tested 580; this is a newer driver, not the tested one) |
| CPU | Xeon Platinum 8480+, SHA-NI present; container cgroup cpu.max ≈ 26.9 cores |
| host memory | container memory limit ≈ 684 GiB |
| disk | 40 GB container overlay |
| host | one GPU of an 8-GPU marketplace host; the host was **unverified** in the provider's listing (no provider attestation of the machine was relied on) |
| cost | $1.026 all-in from the provider's invoice: 0.426 GPU-hours at $2.40/h plus $0.003 storage, $0 transfer (instance lifetime about 25.5 min, including the build) |

## Results

| measurement | value | how measured |
|---|---|---|
| toolkit install | 11 s | stage timestamps (`logs/stages.log`) |
| verifier build | about 1 min | quickstart step log |
| prover default build | about 18.6 min (21:24:35 to 21:43:12 UTC) | quickstart step log, `THE PROGRAMS ARE BUILT` |
| whole quickstart | 20 min 04.6 s wall, 1611.8 s user CPU | `/usr/bin/time -v` (`logs/whole-run.time`) |
| cp_commit (made-up weights, M=1) | about 13 s | file timestamps (config copied 21:43:12, request copied after commit 21:43:25); phases in `logs/cp_commit.log`, key-file 8.1 s largest |
| cp_prove (one request) | about 3 s (±1 s) | request copy 21:43:25 to proof write 21:43:28, 1 s file-time resolution; not directly timed by upstream |
| peak GPU memory, whole run | 74,165 MiB sampled | nvidia-smi at 500 ms (`logs/gpu-samples.csv`); reached during **cp_commit**, not cp_prove |
| peak GPU memory, prove window | 5,293 MiB sampled | same samples, 21:43:26 to 21:43:30 |
| peak GPU power | 436 W sampled | same samples |
| peak host memory | 7.54 GB cgroup `memory.peak` (whole container, incl. builds); 4.6 GB max single-process RSS | cgroup v2 / GNU time |
| proof size | 4,149,564 bytes | `bundle/out/example.proof` |
| key / leaf entry | 1,095,152 / 536,928 bytes | `bundle/ivk/` |
| answer | token 284 | `bundle/out/example.y` |
| commitment ID | `5259d3dffde81fcf7b08634bfaca2bb217aa12286ef2aacd321648572660968c` | cp_commit output |
| verifier on GPU box | exit 0, `YES` | `logs/cp_verify.log` |

Sampled GPU numbers are maxima of 500 ms samples, not true peaks. Commit/prove times come from second-resolution file timestamps around steps that the upstream script does not time individually, so treat them as ±1 s. n = 1, cold run; no repeat runs.

Coverage line from the verifier (exact-match policy): `r=15 e=64 T=64 ... positions=15..63 tokens=16..63 y=yes next-token=no`. Accounting line: 126.21 bits with proof of work counted, 96.23 without; the verifier itself states that no figure there is a security level.

## Independent CPU verification

The public bundle (`config/`, `ivk/`, `in/example.req`, `out/example.y`, `out/example.proof`) was copied off the GPU box before it was destroyed. A separate `cp_verify` was built on a different (CPU-only) machine from a separate clean checkout of the same pinned commit, with gcc 13.3.0. Its source digest matches the GPU box's verifier build (`build=93afdaf5...`), and the two binaries are byte-identical (sha256 `7f9efc1e...04394`, see `logs/binaries.sha256` and `local-verify/result.json`).

| case | exit | last line |
|---|---|---|
| honest bundle, correct ID | **0** | **YES** (1.53 s on CPU) |
| one bit of the proof flipped | 1 | NO: proof-refused |
| one bit of the answer (`example.y`) flipped | 1 | NO: reply-differs |
| one bit of the request (last byte) flipped | 1 | NO: statement-range |
| last byte of the proof cut off | 1 | NO: proof-refused |
| wrong commitment ID (last bit flipped) | 1 | NO: model-statement |

The originals were never modified; each negative case ran on its own copy. Five rejections of single, crafted mutations are a check that the verifier is wired up, not soundness testing.

## Independent review replication

A reviewer who did not run the GPU job rebuilt `cp_verify` from a fresh clone at the pinned commit (`verifier/build.sh`, gcc 13.3.0, 16-vCPU AMD EPYC-Rome VM, no GPU). Its sha256 is again `7f9efc1e86a848a3715c6cc870e465ac2a1c5e8fd1eac09e4809023de7604394`, byte-identical to both binaries above. `review/replicate.sh <cp_verify> <scratch dir>` reruns everything below; its output is `review/result.txt`.

- Honest bundle, correct ID: exit 0, `YES` on 7 of 7 runs. Wall time per run, including process start: median 1.580 s, mean 1.587 s, SD 0.026 s, range 1.549 to 1.620 s (n = 7). A second batch of 7 earlier the same hour gave median 1.545 s, SD 0.039 s.
- Eleven corruptions, none of them one of the five above, each on its own copy: all exit 1 with `NO`.

| case | last line |
|---|---|
| proof, bit 3 of byte 1,000,003 flipped | NO: proof-refused |
| proof, bit 0 of the byte 17 before the end flipped | NO: proof-refused |
| proof header, bit 7 of byte 9 flipped | NO: cp-entry-missing |
| proof with one zero byte appended | NO: proof-refused |
| request with one byte appended | NO: statement-required |
| request and answer files swapped | NO: statement-range |
| proof's first 32 bytes zeroed | NO: cp-proof-head |
| proof's 8-byte magic zeroed | NO: cp-proof-head |
| key, bit 4 of byte 500,000 flipped | NO: key-refused |
| leaf entry, bit 1 of byte 1,234 flipped | NO: entry-refused |
| answer replaced by token 285 (honest answer 284) | NO: reply-differs |

The originals matched `SHA256SUMS` before and after. As above, this checks that a verifier built independently accepts this one proof and rejects simple tampering. It is not soundness testing.

## What this does not show

- Not the upstream headline numbers. This is a new run of the same small example, not a reproduction of full-size results.
- Not the full-size config, real weights, batching, or serving.
- The driver (615.71.09) is newer than the one upstream tested. The run passed, but that says nothing about driver compatibility in general.
- One run, so there is no variance estimate.
- The host was an unverified marketplace listing. Nothing here says anything about the host's integrity or about erasure of the rental's storage; the data was synthetic and the secret side is retired.
- The commitment's secret side (`isk/`) stayed on the rental and was destroyed with it. It is not published. The commitment is retired and must not be reused.

## Files

- `bundle/`: the public files a client needs, enough to rerun `cp_verify config ivk in/example.req out/example.y out/example.proof -id <ID>`.
- `logs/`: quickstart transcript, build logs and records, program logs, GPU samples, timing. Host-specific paths, the GPU UUID and the PCI bus id have been replaced with placeholders (`<REPO>`, `<TOP>`, `<CUDA>`, `<HOME>`, `<pci-bus>`).
- `local-verify/`: the independent verifier's log for each case, plus `result.json`.
- `review/`: the review replication script and its output.
- `SHA256SUMS`: covers every file here except itself.
