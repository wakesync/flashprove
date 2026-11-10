# RESULTS: 20261110-43-h200-bringup, phase 1

**Verdict for phase 1: untested draft package, run blocked on decisions. The PREREG's thresholds are for phase 2 and are not evaluated here: no H200 run happened.** The runner and server control flow is tested on CPU with mocks only; the `prover` and `final` image stages are unbuilt; nothing has run on a GPU.

Phase 1 made only read-only calls to the platform (list, get, metrics, hosts, limits, a config validation and an update *plan*, which the API documents as read-only and which deploys nothing). No instance, release, model, secret, volume or SSH key was created or changed. The fix round after the review made no platform calls at all.

## What was measured locally (CPU host, no GPU)

These are local receipts, not ledger results: no rows are added to `research/results.yaml`, and there is no H200 row.

| check | result | receipt |
|---|---|---|
| image stages `toolkit` + `source` + `verifier` build | exit 0; image 1.63 GB; `cp_verify` compile 79 s (n = 1, shared loaded host) | `runs/build-stages.txt`, `runs/verifier-stage.log` |
| nvcc in the image | `V13.2.86`, the release both H100 runs used | `runs/image-env.txt` |
| `cp_verify` built in the image, sha256 | `7f9efc1e...04394`, byte-identical to the H100 rentals' and the independent CPU builds' (`research/gpu/logs/binaries.sha256`) | `runs/image-env.txt` |
| pinned source in the image | `9e2bdd8f...`, the commit of the H100 receipts | `runs/image-env.txt` |
| `cc_probe.cu` compiles with the image's nvcc for sm_90a | exit 0; on this GPU-less host it stops at its first call ("driver version is insufficient"), as expected without a driver | `runs/cc_probe-compile.txt` |
| `serve.py` on CPU, first version | 7 of 7 checks of the first test pass | `runs/serve_test.txt` |
| `run_job.sh`, first version | `bash -n` exit 0; shellcheck exit 0 | `runs/shellcheck.txt` |
| after review: `serve_test.py` (17 checks) | fixed server 17 of 17; the reviewed server 12 of 16 (the 17th check needs the archive cap and is not reached) | `runs/review-fix-serve_test-{after,before}.txt` |
| after review: `run_job_test.py` (47 checks, mocked GPU programs) | fixed runner 47 of 47; the reviewed runner 13 of 47 | `runs/review-fix-run_job_test-{after,before}.txt` |
| after review: shellcheck of the fixed `run_job.sh` | exit 0, no suppressions | `runs/review-fix-shellcheck.txt` |
| after the second re-reviews: `serve_test.py` (33 checks) | this fix 33 of 33; the server of `3e360778` 24 of 33 (fails the ancestor swap at all three depths, the swap during the walk, the 414, the connection bound and two sealing states) | `runs/review-fix2-serve_test-{after,before}.txt` |
| after the second re-reviews: `run_job_test.py` (87 checks) | this fix 87 of 87; the runner of `3e360778` 60 of 87 | `runs/review-fix2-run_job_test-{after,before}.txt` |
| after the second re-reviews: `bash -n`, shellcheck (the digest-pinned image, no network) | exit 0 and exit 0, no suppressions | `runs/review-fix2-shellcheck.txt` |
| after the third review: `fetch_bounded_test.py` (both runbook fetch paths with an inert program in place of the fetch, plus the helper) | this fix 25 of 25; the runbook of `99d16a77` 5 of 14 (2 static and 12 path checks; the 11 helper-only checks are not run against it, it has no helper). On the old runbook a clock moving from 1 s to 0 s left started the fetch on both paths, the proxy path ran a fetch to the end at 0 s left (`timeout 0`), and a TERM-ignoring fetch ended 5.4 to 5.7 s after the cut-off on both paths; on this fix none started with too little time and the TERM-ignoring fetch was over 4.6 to 4.8 s before the cut-off | `runs/review-fix3-fetch_bounded_test-{after,before}.txt` |
| after the third review: `bash -n` of `run_job.sh` and `fetch_bounded.sh` | exit 0 and exit 0; shellcheck of both in CI only (no local shellcheck on this host) | `runs/review-fix3-bash-n.txt` |

Not built: the `prover` and `final` stages (the default prover build, about half an hour of compiling) on a host shared with other lanes. `cc_probe`, `compiler_sample` and the job have not run on any GPU.

## What was found (from docs and read-only state; details in research/gpu/tinfoil-h200/README.md)

1. One GPU host surfaced to the org; the live instance on it is assigned one GPU. **The host's total and free GPU count is not established**: the hosts listing's `available_gpu_values: [1]` is a permitted instance shape (host capabilities intersected with org entitlement), not a count of cards. If there is no second free GPU, single-GPU blue/green updates are refused (`HOST_GPU_BUSY`) and no second GPU instance can boot beside the live one; that is an assumption to be confirmed with the provider, not a finding. A read-only update plan for the live instance reports `blue_green`, `downtime_required: false`, which describes the strategy, not whether a GPU is free.
2. GPU memory of the live instance, platform metrics (integer percent of a reported total of 140, unit not stated): the 24-hour response has 30 of 30 buckets at 94 %. The 7-day response has 30 buckets: 20 empty (total and utilisation 0), then 87 %, 93 % and 8 at 94 %, about 2.3 days of data. Nominally about 8.4 of the reported units free at 94 %; a derived figure, not a measured free amount.
3. Source reading: the default `cp_commit` and `cp_prove` refuse a GPU with more than 2 GiB in use, and `cp_commit` needs at least about 27 GiB free beside its buffer (a lower bound from the sources). The small example does not fit in what the live instance leaves.
4. Source reading plus NVIDIA's release notes: both programs call `cudaHostRegister` and stop if it fails; NVIDIA lists it as not allowed in CC mode. The live instance runs CC-On. The PREREG's prediction (the unmodified prover stops under CC-On) stands untested. The CLI flag wording for a CC-off benchmark mode and its entitlement, recorded in phase 1, are unverified.
5. Results out: no SSH in production; the package serves results read-only through the attested shim, and keeps serving them after a failed job.

## Changes after review

The independent review (PR #69, comment 6757587635) requested changes; all of them were made in new commits on top of the reviewed head:
- runner: a failed, timed-out or signalled job no longer ends the results server; the job is finalised (marker by rename, last stage line, then SHA256SUMS by rename) and served on every path; runs are classed before their work directory is removed; per-step timeouts, `steps.tsv`, cgroup `memory.peak` at finalisation;
- server: one no-symlink, inside-the-directory, `O_NOFOLLOW` rule on every route; `/status` reads only the tail; the archive is streamed and capped;
- docs: host capacity rewritten as not established; metrics stated as above; runbook window sheet with outage budget, cut-off, deadlines, escalation roles, consumer notice, data-loss and spend gates, restore failure path, restore before off-box verification, the previous-latest tag, the credential kept out of argv; B marked not runnable as packaged; the 524288 MB shape for a full-size run; public image presented as a choice; the CC-off flag marked unverified; units in MiB; apt packages stated as not reproducible; `pipefail` in the prover and final stages.

## Changes after the second re-reviews

Two re-reviews of `3e360778` (PR #69 comments 6759653963, request changes, and 6759737181, approve with should-fix items). Every change below has a test that fails on the code of `3e360778` and passes on this fix (counts in the table above; one test file per component, the older checks kept):
- server: every open is relative to a kept descriptor of the results directory, one component at a time, no link followed at any depth, `fstat` of each opened object; the walk for `/files` and the archive holds the descriptor of each directory it lists and serves each file from the descriptor it checked. Tests: an ancestor directory swapped for a link between check and open at each of three depths, a directory swapped during the walk, the by-name route with a linked ancestor at each depth, a FIFO;
- runner: every finalisation step is checked; an export failure, a marker that cannot be put in place, or a checksum failure (hashing or write) ends as `FAILED` (plus `SEAL-FAILED` when sealing failed), with a stage line naming the step, and a nonzero exit (3 when the job itself ended 0); `/status` reports `failed`, never `done` and never `finalising` forever. Tests: each of these injected failures, plus an unreadable file in `results/`;
- runner: the default quickstart is registered before it starts, so a whole-job timeout during it exports its partial evidence (test: a 3 s job limit during a quickstart that hangs);
- runner: one job per work directory, an exclusive `flock` lock for the whole job; a second `job` or `serve` refuses with a message and exit 2 and touches nothing (test);
- runner: the interrupted step gets its own `steps.tsv` row (`interrupted`) at finalisation; the sampler is waited for before the checksums; real warm-repeat cases (cold run `YES`, first repeat rejected or timed out) (tests);
- runner: duty 6: `out/` and `cp_verify.log` are exported only for runs that `cp_verify` accepted; for others they are listed in `withheld.txt` (tests on rejected, crashed, timed-out and interrupted runs);
- server: connections bounded before a handler thread is started; a 70 KB request line gets 414 instead of crashing the handler (tests);
- runbook: restoring the live service wins over collecting results; fetching has a budget on the window sheet, runs under `timeout` until the restore cut-off and is never retried after it; the prover stop has a deadline and an escalation branch; the restore retry happens only inside the reserve; the key reaches one `tinfoil` process at a time (`tf` function with an assignment prefix) instead of being exported to the operator shell; the approvals row lists image publication and the release tag;
- config: one sentence that it requests one GPU for the instance and says nothing about the host's count;
- docs: the tests have not run inside the Dockerfile's pinned base image (below and README.md); the Dockerfile's comment on the unchanged stages' pipelines corrected.

## Changes after the third review

One review of `99d16a77` (PR #69 comment 6760883534, request changes). Its blocking item and its should-fix and nit:
- runbook: both fetch paths of step 5 go through `fetch_bounded.sh`: one clock read, budget = cut-off minus now minus the kill grace minus a launch margin, the fetch started under `timeout -k <grace> <budget>` only if that is strictly positive, otherwise not started (exit 121) and the restore begins. The grace and margin are inside the fetch budget, so a fetch that ignores TERM is over before the cut-off, and `timeout 0` is never reached. Test: `fetch_bounded_test.py` takes both fetch commands out of the runbook and runs a clock that moves from 1 s to 0 s left between reads, a cut-off reached and one passed, less time left than the kill grace, a TERM-ignoring fetch, and a fetch with time enough; plus the helper's argument handling, the 1 s budget edge and a single clock read. It fails on the runbook of `99d16a77` and passes on this fix (table above). It runs in CI;
- runner and README: the lock's scope is stated: `flock` is advisory, assumes a private local work directory with working `flock` and cooperating writers; a writer that does not take the lock, or a replaced lock inode, is out of scope;
- CI: the push filter for main now includes the workflow file itself; the workflow also runs the new test and shellcheck of `fetch_bounded.sh`.

## Deviations from the PREREG

None for phase 1 (the PREREG governs phase 2). One choice recorded now for phase 2: `FP_ONBOX_BUILD=0` (prebuilt programs, no quickstart) would be a deviation from the PREREG's cold-run definition and must be written up as one if used. The runner now has explicit timeouts (`FP_JOB_TIMEOUT`, per step); see the PREREG's amendment.

## Open risks

- CC-On refusal of `cudaHostRegister` (item 4) could make phase 2 a negative result on the unmodified prover. The package now keeps and serves that negative result.
- The prover stages of the image are unbuilt; a build failure would be found only in phase 2. Apt packages are not pinned, so a rebuild may differ.
- The tests have **not run inside the Dockerfile's pinned base image**: the attempt stopped at `apt-get install` (HTTP 404 for superseded packages of the unpinned archive, `runs/review-fix-ubuntu-image.txt`). They ran on a CPU host and in CI on `ubuntu-24.04`; the image's own bash, coreutils, util-linux (`flock`) and python3 are untested with this code.
- The host's GPU count is not established; whether phase 2 needs downtime at all depends on it.
- The live instance's stop and cold boot times on this host are not measured; the outage total in RUNBOOK.md has four unmeasured parts.
