# PREREG: 20261110-43-h200-bringup
Issue: #43 (efficiency levers, item 4: H100 control vs larger-memory GPU), part of #7 (cost). Lane: h200-bringup, phase 1. Date (UTC): 2026-11-10T01:10Z. Base commit: 4f7a876151c309f0159e88b18c8e286d4e1909c9.

Phase 1 (this PR) runs nothing on a GPU. It registers the protocol of the phase 2 run now, before any H200 code exists, so that phase 2 cannot pick its thresholds after seeing numbers. Phase 2 starts only after a human decision (see research/gpu/tinfoil-h200/README.md, "What has to be decided").

## Hypothesis
The upstream small synthetic example (`examples/quickstart-gpu.sh`, then `prover/examples/run_target_example.sh target_small_f2_roomy`), built from the pinned upstream commit with the same toolkit as the H100 receipts, runs to `YES` on one H200 inside a Tinfoil enclave, and its answer token, coverage line and accounting line are identical to the H100 receipts (`research/gpu/`, `research/gpu/replication-1/`).

## Metric
Per run (one cold quickstart run, then n warm repeats, each in a fresh work directory with a fresh commitment):
- exit status of each program and the verifier's last line (`YES` / `NO: ...`);
- answer token (`out/example.y`), the `covered:` line and the `accounting:` line of `cp_verify.log`;
- `cp_commit` and `cp_prove` wall time, user CPU and max RSS from `/usr/bin/time -v` (the script's `GPU_RUN` prefix), the same way as replication-1;
- proof, key-file and leaf-entry sizes in bytes;
- GPU memory and power, sampled by `nvidia-smi` every 500 ms (maxima of samples, not true peaks), split into commit and prove windows by file times;
- cgroup `memory.peak` of the prover container;
- host CPU verifier (built off the box, CPU-only, from the pinned commit): exit status on each exported public bundle, plus the 5 mutation cases of `research/gpu/local-verify`;
- environment: GPU name, driver, CUDA version reported by the driver, confidential-computing state (`nvidia-smi conf-compute`), CPU model and SHA extension, cgroup CPU quota, nvcc version, gcc version, and the result of a one-call probe of `cudaHostRegister` and `cudaHostAlloc`.

## Acceptance threshold
PASS only if all hold:
1. the cold quickstart run exits 0 with `YES`;
2. at least 9 of 10 warm repeats end with `YES` from the box's verifier, and every exported bundle is accepted by the host CPU verifier (exit 0, `YES`) and all mutation cases are rejected (exit 1, `NO`);
3. answer token 284, the coverage line and the accounting line are byte-identical to the H100 receipts on every accepted run.
Timing and memory are descriptive. A statement "H200 is faster or slower than H100" at commit or prove is allowed only if the min/max ranges of the 10 warm repeats and the 3 replication-1 H100 repeats do not overlap AND the median differs by at least 10 %. Otherwise the result is "no difference shown". Any comparison must also state the confidential-computing mode of the H200 run, since the H100 runs were not in such a mode.

FAIL: any of 1 to 3 fails. A run that fails in a way predicted below (confidential-computing mode refusing host memory registration) is a FAIL with a known cause, written up as a negative result.

## Kill criterion
Stop and publish what exists if: the prover enclave is not serving its results endpoint 60 minutes after create or deploy; or the build fails twice; or the whole window exceeds the downtime that was approved for it (if a live service had to be paused, its restore starts at that point regardless of the prover's state); or any step would need a write outside what was approved.

## Runs
1 cold run (the quickstart, which builds), then 10 warm repeats, sequential, one process at a time, no other GPU work in the enclave. No warmup exclusion: the cold run is reported separately, warm repeats as n = 10 with median, SD, min, max. Fresh commitment per run (each `cp_commit` draws its own seed; no test seeds). Exclusions only for an infrastructure fault outside the prover (enclave restart, lost GPU); such runs are reported and rerun, never silently dropped.

## Prior art
- This repository: the H100 small-example receipts (`research/gpu/`, n = 1, rental A; `research/gpu/replication-1/`, n = 3 timed repeats, rental B) are the control arm. Upstream `prover/docs/build.md` pins nvcc 13.2.86 and the pip toolkit recipe used by both.
- TEE GPU: NVIDIA Hopper confidential computing (CC-On, single-GPU passthrough to one CVM; bounce-buffer copies, CPU-GPU bandwidth limited by CPU encryption; NVIDIA, "Confidential Computing on H100 GPUs for Secure and Trustworthy AI", developer blog 2023). NVIDIA Trusted Computing Solutions release notes r580, "Limitations in the SPT CC and PPCIe Modes": `cudaHostRegister` / `cudaHostUnregister` are not allowed in CC mode. A public vLLM bug report (vllm-project/vllm issue 55428) reports `cudaHostRegister` returning error 801 on an H200 in CC-On mode, while `cudaHostAlloc` works.
- Tinfoil containers (SEV-SNP CVM with an attested H200, measured `tinfoil-config.yml`, docs.tinfoil.sh). zkML provers in TEEs (Phala, Atoma, Nillion) run inference in a TEE; none that we found runs a GPU proof system inside a GPU TEE and reports its cost against a non-TEE control. What is new here is only that comparison, at the smallest size.
- Prediction registered now, from reading the sources: the default build's `cp_commit` and `cp_prove` call `cudaHostRegister` on host memory (prover/hash_commitment/hf_commit_weights.cuh, hf_open_side.cuh, hf_keeper.cu; prover/prover/weight_stream.cuh) and treat a failure as fatal. Under CC-On they are therefore expected to stop at the first such call. If the run is CC-On and they do not, that prediction is wrong and is reported as such.

## Amendments
(empty at registration)

### Amendment 1 (2026-11-10, after the independent review of PR #69, before any H200 code has run)
No hypothesis, metric, threshold, run count or comparison rule changes. Implementation of rules already registered above:
- The kill criterion's limits become runner timeouts: the whole job under `FP_JOB_TIMEOUT` (set from the approved window so that the job ends before the restore cut-off, RUNBOOK.md "Window sheet"), each step under its own timeout. A run stopped by a timeout counts as not `YES`; a job stopped by `FP_JOB_TIMEOUT` is finalised as `FAILED` and its results are published like any other negative result.
- "Restore starts when the approved downtime expires" is replaced by a restore cut-off inside the window (window end minus the restore estimate), so that the total outage stays within the approval.
- The cgroup `memory.peak` metric is read at finalisation (`cgroup-final.txt`); per-step exit status, duration and timeout are in `steps.tsv`.
- The host's GPU count is not established (README.md); whether the window needs the live service stopped at all is decided before phase 2, not assumed.

### Amendment 2 (2026-11-10, after the second pair of re-reviews of PR #69, before any H200 code has run)
No hypothesis, metric, threshold, run count or comparison rule changes. Implementation of rules already registered above:
- Duty 6 for exported evidence: a run's response (`out/`) and its `cp_verify.log` are exported only for runs that `cp_verify` on the box accepted (exit 0, `YES`). For other runs they are withheld and listed in `<run>/withheld.txt`; the run still counts as not `YES` and its verdict line is kept. Threshold 2's host CPU verification therefore applies to the exported bundles of accepted runs, which is every bundle that has an `out/`.
- The kill criterion's "restore starts at that point regardless of the prover's state" now also bounds result retrieval: fetching has a budget that ends at the restore cut-off, the prover stop has its own deadline and escalation branch, and an unfinished fetch never delays the restore (RUNBOOK.md, "Window sheet", steps 5 and 6). Results not fetched by the cut-off are lost and reported as such.
- A job whose finalisation fails (an export, the marker, the checksums) is a `FAILED` job, reported like any other negative result.

### Amendment 3 (2026-11-10, after the third review of PR #69, before any H200 code has run)
No hypothesis, metric, threshold, run count or comparison rule changes. Implementation of a rule already registered above (Amendment 2, "fetching has a budget that ends at the restore cut-off"):
- Both result-fetch paths of RUNBOOK.md step 5 run through one helper, `research/gpu/tinfoil-h200/fetch_bounded.sh`. It reads the clock once, takes the kill grace and a launch margin out of the fetch budget, and starts the fetch under `timeout -k <grace> <budget>` only if the remaining budget is strictly positive; otherwise the fetch is not started and the restore begins. A fetch that ignores TERM is therefore over before the restore cut-off, and a zero duration (no timeout at all for GNU `timeout`) is never used. The earlier command, which read the clock twice and could pass `timeout 0`, is replaced.

### Amendment 4 (2026-11-10, after the fourth review of PR #69, before any H200 code has run)
No hypothesis, metric, threshold, run count or comparison rule changes. Hardening of the fetch helper of Amendment 3:
- `fetch_bounded.sh` validates its inputs before any arithmetic and refuses a violation with exit 2, nothing started: grace and margin are canonical decimal integers from 1 to 3600 (no sign, no leading zero, no whitespace); the cut-off and the single clock reading are canonical 10-digit epoch seconds between 1000000000 (2001-09-09) and 4102444800 (2100-01-01); the cut-off is at most 6 h after the clock reading. With these bounds no intermediate value can wrap in 64-bit arithmetic and no value is read as octal.
- The window sheet gains an NTP check of the operator's clock before step 3. The bound is stated as holding against that clock, with launch delay within the margin and a fetch that stays in its process group; it is not a hard real-time guarantee.
