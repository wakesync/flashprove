# Replication 1: one H100 small synthetic proof, rerun independently

**Verdict: agree.** A second lane that did not produce `research/gpu/` reran the same upstream small example from the merged README and runbook only. The run built, committed, proved and verified the same way, the proof was accepted by the CPU verifier on our side, and every number that should be stable came out within run-to-run noise of the original. Proof bytes differ from the original and between runs. That is expected (see "Why the proof bytes differ").

Nothing outside `research/gpu/replication-1/` changes except one line linking here from `research/gpu/README.md`. Upstream source was the pinned commit `9e2bdd8ff5bf9c62f18263d7dac189b0400b260c`, and the tree was clean before and after (`logs/git-status-*.txt` are empty).

## Independence

- New rental, new run-scoped SSH key and new instance label. No remote state, key, instance or artifact from the first run was reused. The only shared inputs are the merged docs and the operator scripts, which were copied and adapted, not edited in place.
- The toolkit came from the same pip recipe in `prover/docs/build.md`, run fresh, and resolved to the same wheels (cuda-toolkit 13.2.2, nvcc **V13.2.86**, cuBLAS 13.4.1.3). All 3 `Compiled by` lines name V13.2.86.
- The upstream script was the same, unmodified: `examples/quickstart-gpu.sh`, which runs `run_target_example.sh target_small_f2_roomy` (made-up weights, `-M 1`, `own_choices.req`). No weights were downloaded and no test seeds were used.
- Added on top of the original procedure: once the quickstart finished, three more runs of `prover/examples/run_target_example.sh target_small_f2_roomy`, each in a fresh work directory with a fresh commitment. These used the script's own `GPU_RUN` prefix to put `/usr/bin/time` around `cp_commit` and `cp_prove`, so this lane has direct per-program wall times. The original had only file timestamps.
- The host verifier was built from a separate clean worktree at the pinned commit on a CPU-only machine. Its sha256 is `7f9efc1e…04394`, byte-identical to the GPU box's verifier and to both earlier builds.

## Machine, and how it differs from the original

| item | original (`research/gpu/`) | replication 1 |
|---|---|---|
| GPU | H100 80GB HBM3, cc 9.0, MIG off, 0 MiB used at start | same |
| driver | 615.71.09 | 595.91.07 (upstream tested 580; neither run used the tested driver) |
| GPU power limit | not recorded | 500 W current (700 W default) |
| host listing | **unverified**, 1 GPU of an 8-GPU host | **verified**, whole-machine 1-GPU listing |
| CPU quota | Xeon 8480+, cgroup ≈ 26.9 cores | 24 threads, cgroup ≈ 23.0 cores, SHA-NI |
| container memory limit | ≈ 684 GiB | ≈ 118 GiB |
| image, disk, OS, gcc | `vastai/base-image:cuda-13.2-mini-py312-2026-10-23`, 40 GB, Ubuntu 24.04.5, gcc 13.3.0 | same |

Provider, instance, offer, region and GPU identifiers are left out on purpose. Full environment details are in `env-manifest.json`.

## Comparison

| measurement | original (n = 1) | replication 1 | agree? |
|---|---|---|---|
| toolkit install | 11 s | 16 s | yes (network) |
| quickstart start to programs built | 19.8 min (21:23:25 to 21:43:12) | 18.1 min (22:20:39 to 22:38:46) | yes |
| whole quickstart wall (`/usr/bin/time`) | 20:04.6, 1611.8 s user CPU | 18:25.3, 1478.1 s user CPU | yes |
| `cp_commit` wall | about 13 s (file times) | quickstart 14.5 s (file times). Repeats under `/usr/bin/time`: 18.0, 21.3, 17.2 s, mean 18.8 s, SD 2.2 s | **slower by ~40%** on repeats, same order (see note) |
| `cp_commit` key-file phase (its own log) | 8.1 s | 10.6, 11.8, 13.4, 11.5 s | same as above |
| `cp_prove` wall | about 3 s ±1 (file times) | quickstart 2.0 s (file times). Repeats under `/usr/bin/time`: 2.37, 2.46, 2.21 s, mean 2.35 s, SD 0.13 s | yes |
| proof size | 4,149,564 B | 4,149,084 / 4,160,516 / 4,153,388 / 4,161,860 B (mean 4,156,212, SD 6,033) | yes; the size varies by commitment (see below) |
| key / leaf entry | 1,095,152 / 536,928 B | 1,093,008 to 1,095,544 / 536,440 to 539,040 B | yes, same kind of variation |
| answer | token 284 | token 284 on all 4 runs | **identical** |
| request | `own_choices.req` sha256 `55655047…` | same bytes on all 4 runs | identical |
| config (`KL.bin`, `layout.txt`, `policy.txt`) | | same bytes | identical |
| peak GPU memory (500 ms samples) | 74,165 MiB, during `cp_commit` | 74,123 MiB, during `cp_commit`, on all 4 runs | yes (−42 MiB, −0.06%) |
| peak GPU memory, prove window | 5,293 MiB | 5,227 to 5,291 MiB | yes |
| peak GPU power (sampled) | 436 W | 519 W | differs (host power limit and sampling; not a claim) |
| cgroup `memory.peak` (incl. builds) | 7.54 GB | 7.64 GB | yes |
| max single-process RSS (whole quickstart) | 4.6 GB | 4.6 GB (4,615,596 kB) | yes |
| `cp_commit` / `cp_prove` max RSS | not measured | about 855 MB / about 880 MB | new |
| verifier on GPU box | exit 0, `YES` | exit 0, `YES`, 4 of 4 | yes |
| coverage line | `positions=15..63 tokens=16..63 y=yes next-token=no`, exact-match | identical on 4 of 4 | identical |
| accounting line | 126.21 bits (96.23 without PoW) | identical on 4 of 4 | identical |
| **host verifier** | YES; 5 of 5 mutations rejected | **YES on 4 of 4 proofs**; 20 of 20 mutations rejected (5 per proof) | yes |

**Note on commit time.** On this box `cp_commit` took about 17 to 21 s per run, against about 13 s in the original. All of the extra time is in one phase, `key-file`: 10.6 to 13.4 s here against 8.1 s there. Every other phase matches to 0.1 s. Inside that phase both sub-steps vary: "the ranges and the rows' vectors" took 2.5 to 5.7 s (original 2.8 s) and "the test on the table" took 5.7 to 8.5 s (original 5.3 s). The extra time is not all in one sub-step. This box had about 15% fewer CPU cores in its cgroup, a 500 W GPU power cap, and a different driver. The data can't say which of those matters. The order of magnitude and the phase that dominates are the same, so this counts as agreement on the claim ("commit takes on the order of 10 to 20 s; prove takes a few seconds"), not on the exact 13 s figure.

Original timing came from file timestamps, one run (±1 s). The replication timings with n = 3 come from `/usr/bin/time` and are the better numbers. Every replication run was warm (built programs, a GPU already in use), and only the quickstart run was cold.

## Why the proof bytes differ

Each proof's sha256 is different (`numbers.json`), and so are its length and the length of the key and leaf files. This is expected and doesn't count as disagreement:

- `cp_commit` draws its own random seed on each run. `run_target_example.sh` says so ("cp_commit draws its own seed, so the commitment, its ID and the proof differ from run to run"), and the runbook says the same. So every run has a new commitment ID (all four are in `numbers.json`), new masks and a new key.
- Proof, key and leaf sizes vary by about 0.3% between commitments. That fits variable-length encoding of randomized, masked data. The spread across the four replication proofs (12,776 B) is wider than the gap between the original and the nearest replication proof (480 B).
- Everything that should be deterministic matched byte for byte: config files, the request, the answer (token 284), the coverage line and the accounting line.
- Binaries: the verifier is byte-identical across all builds (`7f9efc1e…`). The `cp_commit` and `cp_prove` binaries have different sha256 from the original's, even though their build records list the same `sources` digest (`b57a72d3…`), the same flags and the same toolkit wheels. Only the `sha256` line in the `.build` records differs (diff the two `logs/cp_*.build` files). This lane didn't look into why the GPU programs aren't bit-reproducible across machines. The verifier, which is the trust anchor, is.

## Cost and safety

- Spend from the provider's invoice: **$0.92** all in. That is 0.423 GPU-hours at $2.16/h ($0.913), plus $0.005 storage and $0.002 transfer. The instance ran about 26 min, including the build, three repeat runs and export.
- One earlier create, on a different verified listing, never started: the host couldn't inject the GPU into the container (OCI CDI error). It was destroyed after about 1.5 min. Its invoice is $0.001 of storage and $0 GPU. One instance existed at a time. Cap was $5.
- The hard stop followed the runbook's timer-drift finding: a systemd user timer at an absolute UTC time (`--on-calendar`, `AccuracySec=1s`), plus a separate non-systemd watchdog that polls the wall clock. Both were checked right after create. Teardown was confirmed through the API (complete instance listing: 0; volumes: 0), and then both stops were disarmed.
- The commitments' secret side (`isk/`, seeds) never left the rental and went with it. All four commitments are retired and must not be reused.

## What this does not show

- It is not the upstream headline result. Both runs are the same small example, with no full-size config, real weights, batching or serving.
- It says nothing about driver compatibility in general. Two drivers passed, and upstream tested neither of them.
- n = 3 timed repeats on one machine. That gives some variance inside one host, not across hosts.
- Mutation rejection is a wiring check, not soundness testing.
- The provider's "verified" label is the provider's own claim. This lane relied on no attestation of the host.

## Files

- `bundle/`: public files of the quickstart run (`config/`, `ivk/`, `in/example.req`, `out/example.{y,proof}`). Commitment ID `b797f937404e1cd49f1cb6f2f1ac5bceb14fa969ff28db361ee9ad016a7bde76`.
- `rep{1,2,3}/bundle/`, `rep{1,2,3}/logs/`: the same for each repeat, plus that repeat's program logs and file times.
- `logs/`: quickstart transcript, build logs and records, toolkit install, GPU samples (500 ms), cgroup memory samples (2 s), `/usr/bin/time` for the whole quickstart and per program for each repeat (`rep*.time`), stage times. Host paths are replaced with `<HOME>`, `<REPO>`, `<CUDA>`, `<TOP>`, `<TOP-repN>`, and the GPU UUID and PCI bus id are removed.
- `local-verify/`: host verifier result and log for each proof (`main`, `rep1` to `rep3`): the honest case plus five mutations each.
- `numbers.json`: every figure in the table above, computed from the logs by the lane's analysis script.
- `env-manifest.json`: machine, toolkit and binary hashes.
- `SHA256SUMS`: covers every file here except itself.

To recheck a proof: `cp_verify config ivk in/example.req out/example.y out/example.proof -id <ID>`, run from inside a `bundle/`. The ID is in `numbers.json` or in that run's `cp_commit.log`.
