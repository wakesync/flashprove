# RESULTS: 20261110-43-h200-bringup, phase 1

**Verdict for phase 1: package ready, run blocked on decisions. The PREREG's thresholds are for phase 2 and are not evaluated here: no H200 run happened.**

Phase 1 made only read-only calls to the platform (list, get, metrics, hosts, limits, a config validation and an update *plan*, which the API documents as read-only and which deploys nothing). No instance, release, model, secret, volume or SSH key was created or changed.

## What was measured locally (CPU host, no GPU)

| check | result | receipt |
|---|---|---|
| image stages `toolkit` + `source` + `verifier` build | exit 0; image 1.63 GB; `cp_verify` compile 79 s (n = 1, shared loaded host) | `runs/build-stages.txt`, `runs/verifier-stage.log` |
| nvcc in the image | `V13.2.86`, the release both H100 runs used | `runs/image-env.txt` |
| `cp_verify` built in the image, sha256 | `7f9efc1e...04394`, byte-identical to the H100 rentals' and the independent CPU builds' (`research/gpu/logs/binaries.sha256`) | `runs/image-env.txt` |
| pinned source in the image | `9e2bdd8f...`, the commit of the H100 receipts | `runs/image-env.txt` |
| `cc_probe.cu` compiles with the image's nvcc for sm_90a | exit 0; on this GPU-less host it stops at its first call ("driver version is insufficient"), as expected without a driver | `runs/cc_probe-compile.txt` |
| `serve.py` on CPU | 7 of 7 checks pass, incl. that nothing under `isk/` is listed or in the tarball, unknown paths 404, POST refused | `runs/serve_test.txt` |
| `run_job.sh` | `bash -n` exit 0; shellcheck exit 0 (one SC2094 info suppressed with a reason) | `runs/shellcheck.txt` |

Not built: the `prover` and `final` stages (the default prover build, about half an hour of compiling) on a host shared with other lanes. They are validated by review only. `cc_probe`, `compiler_sample` and the job have not run on any GPU.

## What was found (from docs and read-only state; details in research/gpu/tinfoil-h200/README.md)

1. One GPU host, one GPU, held by one live instance at 94 % GPU memory (platform metrics, flat for 7 days). Single-GPU blue/green updates need a second free GPU on the host (`HOST_GPU_BUSY`), so no second GPU instance can boot beside it. A read-only update plan for the live instance reports `blue_green`, `downtime_required: false`, which describes the strategy, not whether a GPU is free.
2. Source reading: the default `cp_commit` and `cp_prove` refuse a GPU with more than 2 GiB in use, and `cp_commit` needs about 27 GiB free beside its buffer. The small example does not fit in the 6 to 8 GB the live instance leaves.
3. Source reading plus NVIDIA's release notes: both programs call `cudaHostRegister` and stop if it fails; NVIDIA lists it as not allowed in CC mode. The live instance runs CC-On. The PREREG's prediction (the unmodified prover stops under CC-On) stands untested.
4. Results out: no SSH in production; the package serves results read-only through the attested shim.

## Deviations from the PREREG

None for phase 1 (the PREREG governs phase 2). One choice recorded now for phase 2: `FP_ONBOX_BUILD=0` (prebuilt programs, no quickstart) would be a deviation from the PREREG's cold-run definition and must be written up as one if used.

## Open risks

- CC-On refusal of `cudaHostRegister` (item 3) could make phase 2 a negative result on the unmodified prover.
- The prover stages of the image are unbuilt; a build failure would be found only in phase 2.
- The live instance's cold boot time on this host is not measured; the downtime estimate (15 to 60 min for restore) rests on its healthcheck limits and earlier held-candidate boots.
