# RUNBOOK: the FlashProve small example on a Tinfoil H200 (phase 2, not yet run)

Nothing in this file has been run against Tinfoil. It is a draft for an untested package. **Every write step below needs its own human yes first**, recorded in the window sheet: publishing the image, the config release tag, the live stop, the prover create, the prover stop, the live deploy, deleting the prover, reseeding, the latest-release repair.

**Order of precedence, whatever happens: restoring the live service wins over collecting results.** At the restore cut-off the prover is stopped and the live service redeployed, whether the job has finished, the results have been fetched or not. Results that could not be fetched in time are lost (the prover's `/work` is a tmpfs) unless a copy was already fetched; the owner accepts that on the window sheet before step 3. Which steps run depends on the choices in README.md, "What has to be decided". Placeholders: `<OWNER>/<REPO>` is the public config repo, `<TAG>` a release tag, `<LIVE>` the instance that holds the GPU today, `<LIVE_REPO>@<LIVE_TAG>` its pinned config, `<PREV_LATEST>` the tag that was marked latest on `<LIVE_REPO>` before anything started, `<PROVER>` the prover instance name, `<DOMAIN>` its domain, `<LIVE_DOMAIN>` the live service's. The operator substitutes them from their own notes. They are never written into this repository.

Protocol: experiments/20261110-43-h200-bringup/PREREG.md. Control arm: research/gpu/ and research/gpu/replication-1/ (H100 80 GB).

## Credentials: never in a process's argument list

The org admin key must not appear on any command line, in shell history, in a log or in a file outside a mode-600 file of the operator's own. Anything in a command's arguments can be read by other processes on the machine (`ps`, `/proc/<pid>/cmdline`), so `curl -H "Authorization: Bearer $KEY"` is wrong even when `$KEY` came from a file: the shell expands it into curl's argv.

Start the operator shell like this (shell tracing off, so `set -x` cannot print the key). The key is **not** exported into the shell: an exported variable would reach every child of the operator shell (`gh`, `docker`, `curl`, `tar`, an editor), not only `tinfoil`. Instead a small function gives it to one `tinfoil` process at a time:

```sh
set +x
umask 077
KEYFILE=<path to the org admin key>           # a mode-600 file of the operator's own
tf() { TINFOIL_ADMIN_KEY="$(cat "$KEYFILE")" tinfoil "$@"; }
# The assignment prefix puts the key into the environment of that one tinfoil process only; it is
# not in any argv, not in the shell's own variables, and not in history (history holds the text
# `tf ...`, never the key). The key is read from the file each time, without echo.
```

Every `tinfoil` command below is written `tf ...`. The `tinfoil` CLI reads `TINFOIL_ADMIN_KEY` from its environment (its documented highest-priority credential), so no command takes the key as an argument. A process's environment is readable only by its own user and root, unlike its argv.

For a raw API call with `curl`, put the header in a mode-600 file and let curl read it (`-H @file`, curl 7.55 or newer); the key then never reaches an argv:

```sh
HDR=$(mktemp)                                             # mode 600 under umask 077
{ printf 'Authorization: Bearer '; cat "$KEYFILE"; } >"$HDR"   # printf gets a literal, cat a path
curl -s -H @"$HDR" ...                                    # see step 2
rm -f "$HDR"
```

Do not use `tinfoil login --api-key <key>` (the key would be in argv), `export TINFOIL_ADMIN_KEY=...` (every child of the shell would get it), `echo` of the key, or `curl -u`. When the window is over: `unset -f tf`.

## Window sheet (the owner fills this in BEFORE step 3; no step that stops the live service runs without it)

Copy this into the operator's own notes (not this repository) and fill every field. A field left empty means "no": the step it governs does not run.

| field | value |
|---|---|
| host capacity answer (step 0): GPUs on the host, free for the org | `<n installed / n free, source>` or "not established" |
| choice (README.md: A, B or C) | |
| approved outage window, start and end (UTC) | |
| restore cut-off (UTC): the moment the job is abandoned and restore starts, whatever the state | at the latest: window end minus the restore reserve below |
| restore reserve: prover stop deadline + live deploy deadline + one deploy retry + the end-to-end check | the sum of the deadlines below; never shortened to make room for fetching |
| fetch start (UTC) and fetch budget (minutes) for the results archive | fetch start = restore cut-off minus the fetch budget, e.g. 10 min; the fetch is stopped at the cut-off |
| if the fetch has not finished by the cut-off | owner's choice, one of: "restore now, results lost if no copy was fetched" or "restore now; keep any partial copy, do not refetch". There is no option to delay the restore |
| deadline for the prover to reach Stopped (step 6), and what then | e.g. 5 min; then escalation (below) while the live deploy is attempted anyway |
| deadline for the live stop to reach Stopped | e.g. 10 min after the stop |
| deadline for the prover to reach Running and serve `/healthz` | at most the PREREG's 60 min after create |
| deadline for the job (sets `FP_JOB_TIMEOUT` in the config; it must end before the restore cut-off) | |
| deadline for the live deploy to reach Running | from the live config's healthcheck limits, see below |
| who to contact if restore fails | the live service's owner (role); the provider's support/escalation channel (role); never names or identifiers here |
| notice to the live service's consumers: sent when, acknowledged by whom (role) | |
| acceptance of data loss: the live service's in-memory (tmpfs) data is lost on stop; reseed after restore yes/no, who approves | |
| spend: cap, or provider quote, or "cost unknown" accepted explicitly by the owner | |
| approvals, each yes or no: image publication (step 1) / config release tag (step 2) / live stop (step 3) / prover create (step 4) / prover stop (step 6) / live deploy (step 6) / prover delete (after step 8) / reseed (step 7) / latest-release repair (step 6) | |

**Total estimated outage** (choice A), to be filled before approval; the unmeasured parts must stay marked unmeasured:

| part | estimate | basis |
|---|---|---|
| live stop to Stopped | unmeasured | no stop of this instance has been observed |
| prover image pull and enclave boot | unmeasured | no instance with this image has booted |
| fetching the results | at most the fetch budget (enforced by `timeout`, step 5) | the window sheet |
| the job | about 25 min with `FP_ONBOX_BUILD=1` (quickstart about 20 min, 18 to 20 min on the H100, plus 10 repeats of about 25 s); about 5 min with `FP_ONBOX_BUILD=0` | H100 receipts, research/gpu/; not measured on the H200 or under CC-On |
| prover stop | unmeasured; bounded by the prover stop deadline | |
| live deploy to Running | unmeasured; its own healthchecks allow up to 30 and 60 min (`start_period`) for its two model engines, so plan for up to about 60 min | the live config's healthcheck limits only |
| end-to-end check of the live service | unmeasured; a few minutes of requests | |
| **total** | **unmeasured; job about 5 to 25 min plus at least four unmeasured parts, one of which may take up to about 60 min** | |

## 0. Before anything (read-only, any time)

```sh
tf whoami
tf container hosts -o json               # hosts surfaced to the org; available_gpu_values are permitted
                                         # instance shapes, NOT a count of installed or free GPUs
tf container list                        # expect <LIVE> Running
tf container get <LIVE> -o json > live-before.json           # keep: config, tag, mark_latest_release
tf container metrics <LIVE> -o json > live-metrics-before.json
gh release view -R <LIVE_REPO> --json tagName > live-latest-before.json   # = <PREV_LATEST>
```

Write down, from `live-before.json`: the current tag (`<LIVE_TAG>`), `mark_latest_release`, `update_strategy`, the secrets list. Write down `<PREV_LATEST>` from `live-latest-before.json`: some clients of the live service verify against "latest", not a pinned tag, and `<PREV_LATEST>` can differ from `<LIVE_TAG>`.

**Ask the host capacity question now** (owner to the provider): how many GPUs does the host have, and how many are free for the org? If a second GPU is free and the org may use it, the prover can run as its own instance with no downtime for the live service: skip step 3 and the restore part of step 6, and the window sheet's outage fields do not apply. Only if the answer is "no free second GPU" (or the owner chooses A without an answer, recorded as such) does the rest of this runbook's choice A apply.

Smoke-test the live service now so that "serving again" has a baseline to compare with: one attested request through the CLI, and the same request through a client that follows "latest", if the service has such clients:

```sh
tf http get https://<LIVE_DOMAIN>/healthz --enclave <LIVE_DOMAIN> --repo <LIVE_REPO>@<LIVE_TAG>
tf http get https://<LIVE_DOMAIN>/healthz --enclave <LIVE_DOMAIN> --repo <LIVE_REPO>   # latest-following, if supported by the CLI version
```

## 1. Build, check, then publish the image (the publication needs a yes)

The image holds only public code and NVIDIA's toolkit wheels, no secrets. It can be a public GHCR package (simplest, recommended) or a private one with registry credentials configured for the org (README.md, decision 4). Build and check locally first; push only if every check passes.

```sh
cd research/gpu/tinfoil-h200
python3 serve_test.py && python3 run_job_test.py                        # both must end "N of N checks passed"
docker build -t ghcr.io/<OWNER>/flashprove-h200-prover:phase2 .        # unmeasured; the prover stage has not been built yet
docker run --rm --entrypoint cat ghcr.io/<OWNER>/flashprove-h200-prover:phase2 /opt/env/nvcc.txt /opt/env/flashprove-commit.txt /opt/env/programs.sha256
docker run --rm --entrypoint sha256sum ghcr.io/<OWNER>/flashprove-h200-prover:phase2 /opt/flashprove/bin/cp_verify
```

`nvcc.txt` must end `V13.2.86`, `flashprove-commit.txt` must be `9e2bdd8f...`, and `cp_verify` from the image should hash to the H100 runs' `7f9efc1e...04394` (research/gpu/logs/binaries.sha256). If it does not, record it as a deviation; it does not block the run. Then, with the yes:

```sh
docker push ghcr.io/<OWNER>/flashprove-h200-prover:phase2
docker inspect --format='{{index .RepoDigests 0}}' ghcr.io/<OWNER>/flashprove-h200-prover:phase2
```

## 2. Put the config in a release (needs a yes: new tag on a public repo)

Copy `tinfoil-config.draft.yml` to the root of `<OWNER>/<REPO>` as `tinfoil-config.yml`, replace the image placeholder with the digest from step 1, set `FP_JOB_TIMEOUT` (and, if wanted, the per-step timeouts) from the window sheet, commit, then:

```sh
gh workflow run tinfoil-release.yml -R <OWNER>/<REPO> -f version=<TAG>
gh run list -R <OWNER>/<REPO> --workflow tinfoil-release.yml --limit 1
gh run list -R <OWNER>/<REPO> --workflow tinfoil-release-publish.yml --limit 1   # both must succeed
gh release view <TAG> -R <OWNER>/<REPO>
```

A release seconds old can fail to fetch ("failed to fetch repository configuration"); retry after a minute.

Read-only check of the release against the org's limits, which creates nothing (header from a file, see "Credentials"):

```sh
HDR=$(mktemp); { printf 'Authorization: Bearer '; cat "$KEYFILE"; } >"$HDR"
curl -s -X POST https://api.tinfoil.sh/api/containers/validate -H @"$HDR" \
  -H 'Content-Type: application/json' -d '{"repo":"<OWNER>/<REPO>","tag":"<TAG>","instance_name":"<PROVER>"}'
rm -f "$HDR"
```

A validation passing says the config is acceptable; it does not reserve a GPU or say one is free.

## 3. Free the GPU (choice A only, only with a filled window sheet; this is the downtime)

Applies only if step 0 found no free second GPU (or the owner chose A without an answer). Under that assumption a second instance with a GPU cannot boot while the live one runs: each instance is its own confidential VM with whole GPUs, and a single-GPU blue/green update needs a second free GPU on the host (`HOST_GPU_BUSY` otherwise). So the live instance is stopped:

```sh
date -u +%FT%TZ                      # downtime starts; check it is inside the approved window
tf container stop <LIVE>
tf container get <LIVE>              # wait for Stopped, at most the window sheet's stop deadline
```

If it is not Stopped by the deadline: do not go on to step 4; contact the escalation roles in the window sheet. Stop removes its DNS records; its saved config, secrets bindings and tag remain. In-memory state (tmpfs data) is lost, which for the live service means its data must be reseeded after restore, if the window sheet approved that.

## 4. Create the prover instance

```sh
tf container create <PROVER> --repo <OWNER>/<REPO> --tag <TAG> --mark-latest=false --secret=""
tf container get <PROVER>            # Deploying -> Starting -> Running, at most the boot deadline
```

`--mark-latest=false` is required: the default moves the repository's latest GitHub release, which once broke verification for a running service whose clients follow "latest". `--secret=""`: the prover needs none. No `--host` (explicit host choice was not enabled for the org). No `--debug`: a debug instance does not attest and still takes a GPU.

If create returns `HOST_CAPACITY` or `HOST_GPU_BUSY`, the GPU is not free: do not retry in a loop. If create fails, or the prover is not Running and serving `/healthz` by the boot deadline (the PREREG's 60 min at most): stop it if it exists (`tf container stop <PROVER>`), record what it showed (`tf container get <PROVER> -o json`), and go to step 6 at once. That is a published negative result, not a retry.

## 5. Follow the job and fetch the results (attested)

```sh
tf http get https://<DOMAIN>/status --enclave <DOMAIN> --repo <OWNER>/<REPO>@<TAG>
```

`state` goes from `running` to `finalising` to `done` or `failed`; `stages` shows the last lines of the job's stage log. A failed job (for example the predicted CC-On refusal) is finalised and served like a successful one: fetch it the same way. Expected timing, from the H100 receipts (not measured here): with `FP_ONBOX_BUILD=1`, about 20 min for the quickstart (most of it the second build), then 10 repeats of about 25 s each, about 25 min in all after boot. With `FP_ONBOX_BUILD=0`, about 5 min. The job stops itself at `FP_JOB_TIMEOUT` and is then finalised as failed.

**Fetching is bounded, and it never runs into the restore reserve.** Fetch as soon as the state is `done` or `failed`, and in any case start no later than the window sheet's fetch start (restore cut-off minus the fetch budget). Every fetch runs under `timeout` with the time left until the restore cut-off, so it is stopped at the cut-off whatever it is doing; the archive checks below are local and run after step 6, not inside the window. At the restore cut-off, go to step 6 **at once**, whatever the state of the job or the fetch, and do what the window sheet chose for an unfinished fetch (keep a partial copy, or accept the loss). Never delay the restore to finish or retry a fetch.

```sh
CUTOFF=<restore cut-off as UTC, e.g. 2026-12-01T14:30:00Z>
left() { echo $(( $(date -u -d "$CUTOFF" +%s) - $(date -u +%s) )); }   # seconds until the cut-off
[ "$(left)" -gt 0 ] && timeout -k 5 "$(left)" \
  bash -c 'TINFOIL_ADMIN_KEY="$(cat "$1")" tinfoil http get https://<DOMAIN>/results.tar.gz --enclave <DOMAIN> --repo <OWNER>/<REPO>@<TAG>' _ "$KEYFILE" \
  > h200-results.tar.gz
echo "fetch exit $? at $(date -u +%FT%TZ)"   # 124: stopped at the cut-off; the copy is partial
```

(The `bash -c` form passes the key file's path, not the key, as an argument; the key is read inside, as in `tf`.) Then go to step 6. Only after the live service is restored (step 7), off the window:

```sh
tar -tzf h200-results.tar.gz | grep -c . ; tar -tzf h200-results.tar.gz | grep -c isk     # second number must be 0
tar -xzf h200-results.tar.gz && (cd results && sha256sum -c --quiet SHA256SUMS)          # only if the state was done or failed
```

A partial or failed fetch is recorded in the RESULT as it is; no fetch is retried after the cut-off (the prover is stopped by then, its tmpfs gone). If `tinfoil http get` writes a body other than raw bytes on this CLI version, use the verified proxy instead, under the same `timeout`: `tf container connect <PROVER> -p 3301` in one shell and `timeout -k 5 "$(left)" curl -s http://127.0.0.1:3301/results.tar.gz -o h200-results.tar.gz` in another (the proxy verifies attestation; plain `curl` against the domain does not). The server allows two archive downloads at a time and answers 503 to a third; retry only while time is left before the fetch budget ends.

## 6. Teardown and restore (ends the downtime; before any lengthy off-box work)

Restore the live service first; verify the results off the box afterwards (step 8). Starts at the restore cut-off at the latest, or as soon as the fetch has ended, whichever is first. Any fetch still running is stopped first (its `timeout` ends it at the cut-off anyway).

```sh
date -u +%FT%TZ                                # restore starts
tf container stop <PROVER>                     # frees the GPU
tf container get <PROVER>                      # wait for Stopped, at most the window sheet's prover stop deadline
tf container deploy <LIVE> --tag <LIVE_TAG> --mark-latest=false
tf container get <LIVE>                        # Deploying -> Starting -> Running, at most the deploy deadline
```

**If the prover is not Stopped by its deadline:** send the stop once more and check `tf container list`; if it still holds the GPU, contact the escalation roles in the window sheet at once (the provider can free it), and meanwhile try the live deploy anyway (it will be refused with `HOST_GPU_BUSY` or `HOST_CAPACITY` while the GPU is held; that refusal is recorded, not looped on). Do not wait for results, do not delete the live instance's config, do not try other configs. The restore failure branch below then applies, inside the same reserve.

If `<PROVER>` was never created or is already gone, skip its stop. Keep `<PROVER>` stopped, not deleted, until the results are verified (a stopped instance holds no GPU); delete it afterwards only with its own yes: `tf container delete <PROVER>` (irreversible, asks for confirmation).

`--mark-latest=false` on deploy so that the latest release of `<LIVE_REPO>` stays `<PREV_LATEST>` from step 0. Check with `gh release view -R <LIVE_REPO> --json tagName`; if it moved, and only with the window sheet's yes for the latest-release repair, put it back to the recorded value (not to `<LIVE_TAG>`, which can differ): `gh release edit <PREV_LATEST> -R <LIVE_REPO> --latest`.

The live instance's cold boot loads two model engines one after the other; its healthchecks allow up to 30 and 60 min. Its boot time on this host has not been observed.

**If restore fails** (deploy refused, `HOST_CAPACITY` or `HOST_GPU_BUSY` while the prover is stopped, boot stages failing, or not Running by the deploy deadline): do not delete anything and do not try other configs. Check that `<PROVER>` is Stopped and holds no GPU (`tf container list`); try the same deploy once more, only if the reserve still holds one deploy deadline before the window end; then, or at once if it does not, contact the escalation roles in the window sheet (the live service's owner, then the provider), with `tf container get <LIVE> -o json` and the times of every step. Record it in the RESULT.

## 7. Verify that the live service serves again

```sh
tf container get <LIVE>                              # Status Running, all boot stages ok, tag <LIVE_TAG>
tf http get https://<LIVE_DOMAIN>/healthz --enclave <LIVE_DOMAIN> --repo <LIVE_REPO>@<LIVE_TAG>
tf http get https://<LIVE_DOMAIN>/healthz --enclave <LIVE_DOMAIN> --repo <LIVE_REPO>   # latest-following, as in step 0
gh release view -R <LIVE_REPO> --json tagName        # must equal <PREV_LATEST>
date -u +%FT%TZ                                      # downtime ends
```

Then the live service's own end-to-end check: one attested request to each model it serves, the same probes as in step 0 through both a pinned and a latest-following client, and any local component that depends on it reporting healthy. Reseed its data if the window sheet approved that (step 3). Record the downtime window (step 3 to here) and each part of it against the window sheet's estimates in the RESULT.

## 8. Off the box: independent verification (CPU, after restore)

Same as research/gpu/local-verify: build `cp_verify` from a clean checkout at the pinned commit on a CPU machine, then for every run directory in `results/` that has a bundle:

```sh
ID=$(sed -n 's/^commitment ID: //p' results/<run>/cp_commit.log | tr -d ' ')
(cd results/<run>/bundle && <cp_verify> config ivk in/example.req out/example.y out/example.proof -id "$ID"; echo "exit $?")
```

Plus the five mutation cases of research/gpu/local-verify on each bundle (proof bit flip, answer bit flip, request bit flip, proof truncated, wrong ID): each must exit 1 with `NO`.

## 9. Write-up

`experiments/20261110-43-h200-bringup/`: ENV.json (from gpu-env.txt, host-env.txt, cc_probe.json, cgroup-final.txt, steps.tsv, nvcc/gcc, binaries.sha256), RESULTS.md against the PREREG thresholds, raw runs under `runs/`, research/results.yaml rows with hardware key `gpu-h200-tinfoil-a` (to be added), and a comparison table in the form of research/gpu/replication-1/README.md. Redact the domain, instance IDs and org identifiers before committing (run scripts/check-no-host-paths.sh and grep for the org's names).

## Choice B (the prover inside the live instance) and choice C (a second GPU)

B is **not runnable as this package stands**. It would mean: add a `prover` container to the live config, release a new tag of `<LIVE_REPO>`, and `tf container update <LIVE> --tag <NEW> --hold=true --mark-latest=false`. If the host has no second free GPU, blue/green is refused (`HOST_GPU_BUSY`) and the update needs a stop and deploy with downtime anyway (step 3, then `tf container deploy <LIVE> --tag <NEW> --mark-latest=false`). It needs the engines' `--gpu-memory-utilization` lowered so that about 27 GiB stay free for `cp_commit` (README.md, "What fits"); and even then the default prover programs refuse to start when more than 2 GiB of the GPU are in use, so B also needs a prover change or a test build that only warns, which is outside this lane and would be a registered deviation from the PREREG. It also changes the measured config that the live service's clients verify. Restore = deploy `<LIVE_TAG>` again (same downtime).

C: a second free GPU, on this host (if step 0 finds one) or on a second host for the org (ask the provider). Then step 3 and the restore in step 6 are skipped; on a second host, create the prover with `--host <HOST2>` (explicit host selection must be enabled for the org first).
