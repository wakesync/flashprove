# The prover on a Tinfoil H200: phase 1 (inventory and a ready package, nothing run)

**Status: nothing has been run on the H200.** This directory has a container image recipe, a draft Tinfoil config, a job runner, a read-only results server and a runbook for running the upstream small synthetic example on one H200 in a Tinfoil enclave, with the same protocol as the H100 receipts (`research/gpu/`). Phase 1 read the platform's docs and the org's own state with read-only calls and built the first stages of the image. It created, changed and stopped nothing on Tinfoil. Phase 2, the run itself, waits for the decisions below. The protocol for phase 2 is registered in advance in `experiments/20261110-43-h200-bringup/PREREG.md`.

Part of #43 (item 4: H100 control vs a larger-memory GPU) and #7 (cost).

## What is proved, what the verifier recomputes, what is not covered

Same as `research/gpu/`: the example commits to synthetic ("made-up") weights of the small configuration `target_small_f2_roomy`, proves one request (`own_choices.req`) and checks the proof. `cp_verify` recomputes, from public files alone (the configuration, the key file and leaf entry, the request, the answer and the proof) and the commitment ID, that the answer is the committed model's output on that request at the covered positions. Not covered here: real weights, the full-size configuration, Qwen, batching, serving, and anything about the enclave itself. A Tinfoil attestation would say which image and config ran; it does not replace the proof, and the proof does not depend on it.

## The answers phase 1 found

**Can two containers share the one GPU?** Not as two instances. Each Tinfoil instance is its own confidential VM (AMD SEV-SNP with the GPU attached), and NVIDIA's confidential-computing model assigns a whole GPU to one VM (no MIG, no MPS in CC mode). The platform's own docs say a blue/green update of a single-GPU instance needs a second free GPU on the same host, else it is refused with `HOST_GPU_BUSY`. The org's one host reports one GPU. So while the live instance runs, no second instance with a GPU can boot, in production or debug mode. Containers inside one instance can share its GPU (the live instance already runs two model servers on it), so the options are: (A) stop the live instance for a proving window, (B) add the prover as one more container inside the live instance's config, which changes the measured config of a live service, or (C) a second host.

**What fits beside the live service?** Nothing, without changing the prover. The live instance leaves about 6 to 8 GB of the 141 GB free (the platform's metrics show 94 % GPU memory in use, flat for seven days). `cp_commit` and `cp_prove` in the default build refuse to start when more than 2 GiB of the GPU are already in use (`prover/common/common.h`, `GPU_IN_USE_AT_THE_START`), because they assume the GPU is theirs alone. Even in a test build, which only warns, `cp_commit` keeps 2 GiB plus 24 GiB for its engine free beside its main buffer (`prover/hash_commitment/hf_commit_once.cuh`, `HF_ONCE_ENGINE_ROOM`), so it needs at least about 27 GiB free at the small size. On the H100 it took 74 GB only because it sizes its buffer to what is free; the prove step peaked at about 5.3 GB. So the small example does not fit in what the live service leaves, and the prove step alone would, but it needs a commitment made first.

**Confidential-computing mode is a second blocker, predicted from the sources.** Both programs page-lock host memory with `cudaHostRegister` and treat a failure as fatal (`hf_commit_weights.cuh`, `hf_open_side.cuh`, `hf_keeper.cu`, `weight_stream.cuh`). NVIDIA's Trusted Computing release notes (r580, "Limitations in the SPT CC and PPCIe Modes") list `cudaHostRegister` as not allowed in CC mode, and a public vLLM report measured error 801 on an H200 in CC-On while `cudaHostAlloc` worked. The live instance runs with confidential computing on (`disable_cc_mode: false`). The CLI offers `--disable-cc-mode` only as "EXPERIMENTAL ... benchmarks only; requires org entitlement", and whether this org has that entitlement is not visible from read-only calls. So in a normal (CC-On) Tinfoil enclave the unmodified prover is expected to stop at its first `cudaHostRegister`. The image includes `cc_probe` to check this in the first second of the run. A fix in the prover (allocate with `cudaHostAlloc` instead of registering) is a code change, outside this lane. This is the decision that matters most.

**Cost of CC mode.** NVIDIA's numbers: GPU compute and HBM bandwidth at par; CPU-GPU transfers go through encrypted bounce buffers, about 4 GB/s (NVIDIA developer blog, 2023), about 4.9 GiB/s measured for `cudaHostAlloc` copies in the vLLM report. At the small size the weights are tiny, so the effect should be small. At full size the prover streams weights from host memory every pass, so the effect could be large. Not measured.

**Getting a job in and results out.** Production instances have no SSH. Debug instances do (`tinfoil container create --debug --ssh-key`, then `ssh -p <port> root@debug.tinfoil.sh` into a toolbox with `tindbg`), but they do not attest and still take the GPU. Direct admin SSH needs `cvm_admin: true`, which grants control of the whole enclave. The package here uses neither: the job runs once at boot, and a read-only HTTP server behind the attested shim offers `/status`, `/files` and `/results.tar.gz`, fetched with `tinfoil http get` or `tinfoil container connect`. No request can start or change a job. `isk/` (the commitment's secret side) never leaves the work directory, which is a tmpfs inside the enclave and is gone when the instance stops.

**Where the config lives.** Tinfoil reads `tinfoil-config.yml` from the root of a public GitHub repo that has the two Tinfoil release workflows, and releases are tags of that repo. `wakesync/flashprove` is public, but putting the config at its root and adding release workflows that create tags would mix research tags with enclave releases in the main research repo. Recommended: a small separate public repo made from `tinfoilsh/tinfoil-containers-template`, holding only `tinfoil-config.yml`, the image build and the release workflows, with the image built from a pinned `wakesync/flashprove` commit. That needs a new repo, so it is a decision, not something this lane did. The alternative (config at the root of `wakesync/flashprove` plus the two workflows) works and needs no new repo, but every enclave release would then be a tag here.

## What has to be decided (smallest set)

1. Which window: (A) stop the live instance for a proving window, (B) put the prover inside the live instance, or (C) ask for a second host. Recommended: A for this first baseline.
2. CC mode: ask Tinfoil whether `--disable-cc-mode` is enabled for the org (benchmark only, not attested as confidential), or accept that phase 2 may first only measure the predicted CC-On refusal and then wait for a prover change that avoids `cudaHostRegister`.
3. Where the config lives: a new public config repo (recommended) or the root of this repo.
4. Publishing the image: a public package (GHCR), since the enclave pulls it.

Downtime and exact commands for each: RUNBOOK.md.

## What the prover needs on the box

From the H100 receipts and the build docs (all measured on H100 80 GB unless marked):

| item | small synthetic example | full synthetic example (`target_full_f2`) | first Qwen GPU block |
|---|---|---|---|
| GPU | sm_90a (H100 or H200), whole GPU; refuses > 2 GiB already in use | same | not built yet |
| GPU memory | 74 GB sampled peak during `cp_commit` (it takes what is free), 5.3 GB during `cp_prove`; needs at least about 27 GiB free to start `cp_commit` (from the sources, not measured) | "nearly all the memory of an H100 with 80 GB" (docs/quickstart.md) | not known; Qwen3.8-27B integer weights about 56 GB (estimate, research/ports/qwen3.8-27b/FEASIBILITY.md) |
| host memory | 7.6 GB cgroup peak, builds included; `cp_commit`/`cp_prove` about 0.86 GB RSS each | 280 GB available required by the script; up to 268 to 278 GB seen | per-token state witness about 92 to 155 GB at batch 1 (estimate, FEASIBILITY.md) |
| disk / scratch | about 2 GB in TMPDIR, 1 GB in the checkout, plus about 3 GB of toolkit | a few GB under TMPDIR | not known |
| time | quickstart 18 to 20 min (build); commit 13 to 21 s; prove 2.2 to 2.5 s | about 42 min run | not known |
| toolkit | CUDA 13.2 Update 2, nvcc 13.2.86 (pip wheels, sha256-pinned here), cuBLAS 13.4.1.3, gcc/g++ 13, python3, SHA extensions on the CPU | same | same |
| driver | runs seen under 580, 595.91.07 and 615.71.09; the H200's driver is whatever the enclave image ships (recorded by the job) | same | same |

The tinfoil-config draft asks for 16 CPUs and 64 GB, which is enough for the small example and too little for the full one (a full-size run needs a 262144 or 524288 MB shape and the GPU to itself).

A first Qwen GPU block does not exist in the prover yet (the Qwen port is CPU-only so far: `experiments/20261104-11-qwen-deltanet-m1/`, `20261105-32-qwen-deltanet-m1b-lookup/`). Its sizes above are estimates from the feasibility study, not measurements.

## Files

- `Dockerfile`: Ubuntu 24.04 (digest-pinned), the toolkit wheels (sha256-pinned, `requirements-cuda.txt`), NVIDIA's link stub for `libcuda.so` (sha256-pinned), the pinned upstream commit `9e2bdd8f`, `cp_verify`, the default prover build, `compiler_sample`, `cc_probe`, the job runner. Stages `toolkit`, `source` and `verifier` were built locally in phase 1 (see experiments/20261110-43-h200-bringup/RESULTS.md); the `prover` and `final` stages were not built (about half an hour of compiling on a shared host) and are validated by review only.
- `tinfoil-config.draft.yml`: the draft config, not released. Image digest is a placeholder.
- `run_job.sh`: the job (environment record, GPU compiler check, cold quickstart, 10 warm repeats under `/usr/bin/time`, public-bundle export, GPU sampler). Checked with `bash -n` and shellcheck, not run.
- `serve.py`: the read-only results server; `serve_test.py` tests it on CPU (7 of 7 checks pass, including that nothing under `isk/` is listed or served).
- `cc_probe.cu`: one call each to `cudaHostRegister` and `cudaHostAlloc`, and three 1 GiB copies, printed as JSON. Compiled in the image, not run.
- `requirements-cuda.txt`: the hash-pinned toolkit wheels.
- `RUNBOOK.md`: bring-up, the baseline run, result retrieval, teardown, restoring the live instance and checking that it serves again.

## Reproduce what phase 1 did

```sh
cd research/gpu/tinfoil-h200
python3 serve_test.py                                         # 7 PASS lines, exit 0
bash -n run_job.sh && docker run --rm -v "$PWD:/m:ro" koalaman/shellcheck:stable /m/run_job.sh
docker build --target verifier -t fp-h200-verifier .          # toolkit + pinned checkout + cp_verify
docker run --rm --entrypoint cat fp-h200-verifier /opt/env/nvcc.txt /opt/env/cp_verify.sha256
```
