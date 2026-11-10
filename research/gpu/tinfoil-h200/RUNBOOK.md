# RUNBOOK: the FlashProve small example on a Tinfoil H200 (phase 2, not yet run)

Nothing in this file has been run against Tinfoil. Every write step below needs a human yes first, and which steps run depends on the choices in README.md, "What has to be decided". Placeholders: `<OWNER>/<REPO>` is the public config repo, `<TAG>` a release tag, `<LIVE>` the instance that holds the GPU today, `<LIVE_REPO>@<LIVE_TAG>` its pinned config, `<PROVER>` the prover instance name, `<DOMAIN>` its domain. The operator substitutes them from their own notes. They are never written into this repository.

Auth for every `tinfoil` command: `export TINFOIL_ADMIN_KEY=$(cat <path to the org admin key>)`. Never echo it, never put it on a command line, never commit it.

Protocol: experiments/20261110-43-h200-bringup/PREREG.md. Control arm: research/gpu/ and research/gpu/replication-1/ (H100 80 GB).

## 0. Before anything (read-only, any time)

```sh
tinfoil whoami
tinfoil container hosts -o json          # expect one host, available_gpu_values [1]
tinfoil container list                   # expect <LIVE> Running
tinfoil container get <LIVE> -o json > live-before.json      # keep: config, tag, mark_latest_release
tinfoil container metrics <LIVE> -o json > live-metrics-before.json
```

Write down, from `live-before.json`: the current tag, `mark_latest_release`, `update_strategy`, the secrets list. Record which GitHub release of `<LIVE_REPO>` is marked latest (`gh release view -R <LIVE_REPO> --json tagName`), because some clients of the live service verify against "latest", not a pinned tag.

Smoke-test the live service now so that "serving again" has a baseline to compare with (an attested request through the CLI, or the service's own probe):

```sh
tinfoil http get https://<LIVE_DOMAIN>/healthz --enclave <LIVE_DOMAIN> --repo <LIVE_REPO>@<LIVE_TAG>
```

## 1. Build and publish the image (needs a yes: it creates a public package)

The image must be public (or the org needs registry credentials). It holds only public code and NVIDIA's toolkit wheels, no secrets.

```sh
cd research/gpu/tinfoil-h200
docker build -t ghcr.io/<OWNER>/flashprove-h200-prover:phase2 .        # about 35 to 45 min on 16 cores
docker push ghcr.io/<OWNER>/flashprove-h200-prover:phase2
docker inspect --format='{{index .RepoDigests 0}}' ghcr.io/<OWNER>/flashprove-h200-prover:phase2
```

Before pushing, check the image locally without a GPU:

```sh
docker run --rm --entrypoint cat ghcr.io/<OWNER>/flashprove-h200-prover:phase2 /opt/env/nvcc.txt /opt/env/flashprove-commit.txt /opt/env/programs.sha256
docker run --rm --entrypoint /opt/flashprove/bin/cp_verify ghcr.io/<OWNER>/flashprove-h200-prover:phase2 2>&1 | head -3
```

`nvcc.txt` must end `V13.2.86`, `flashprove-commit.txt` must be `9e2bdd8f...`, and `cp_verify` from the image should hash to the H100 runs' `7f9efc1e...04394` (research/gpu/logs/binaries.sha256). If it does not, record it as a deviation; it does not block the run.

## 2. Put the config in a release (needs a yes: new tag on a public repo)

Copy `tinfoil-config.draft.yml` to the root of `<OWNER>/<REPO>` as `tinfoil-config.yml`, replace the image placeholder with the digest from step 1, commit, then:

```sh
gh workflow run tinfoil-release.yml -R <OWNER>/<REPO> -f version=<TAG>
gh run list -R <OWNER>/<REPO> --workflow tinfoil-release.yml --limit 1
gh run list -R <OWNER>/<REPO> --workflow tinfoil-release-publish.yml --limit 1   # both must succeed
gh release view <TAG> -R <OWNER>/<REPO>
```

A release seconds old can fail to fetch ("failed to fetch repository configuration"); retry after a minute.

Read-only check of the release against the org's limits, which creates nothing:

```sh
curl -s -X POST https://api.tinfoil.sh/api/containers/validate -H "Authorization: Bearer $TINFOIL_ADMIN_KEY" \
  -H 'Content-Type: application/json' -d '{"repo":"<OWNER>/<REPO>","tag":"<TAG>","instance_name":"<PROVER>"}'
```

## 3. Free the GPU (choice A only; this is the downtime)

The host has one GPU and the live instance holds it. A second instance cannot boot while it runs: Tinfoil gives each instance its own confidential VM with whole GPUs, and a single-GPU blue/green update already needs a second free GPU on the host (`HOST_GPU_BUSY` otherwise). So under choice A the live instance is stopped:

```sh
date -u +%FT%TZ                      # downtime starts
tinfoil container stop <LIVE>
tinfoil container get <LIVE>         # wait for Stopped
```

Stop removes its DNS records; its saved config, secrets bindings and tag remain. In-memory state (tmpfs data) is lost, which for the live service means its seeded demo data must be seeded again after restore.

## 4. Create the prover instance

```sh
tinfoil container create <PROVER> --repo <OWNER>/<REPO> --tag <TAG> --mark-latest=false --secret=""
tinfoil container get <PROVER>       # Deploying -> Starting -> Running
```

`--mark-latest=false` is required: the default moves the repository's latest GitHub release, which once broke verification for a running service whose clients follow "latest". `--secret=""`: the prover needs none. No `--host` (one host; explicit host choice was not enabled for the org). No `--debug`: a debug instance does not attest and still takes the GPU.

If create returns `HOST_CAPACITY` or `HOST_GPU_BUSY`, the GPU is not free yet: wait, do not retry in a loop, and if the live instance was stopped, go to step 7 when the window ends.

## 5. Follow the job and fetch the results (attested)

```sh
tinfoil http get https://<DOMAIN>/status --enclave <DOMAIN> --repo <OWNER>/<REPO>@<TAG>
```

`state` goes from `running` to `done` or `failed`; `stages` shows the last lines of the job's stage log. Expected timing, from the H100 receipts: with `FP_ONBOX_BUILD=1`, about 20 min for the quickstart (most of it the second build), then 10 repeats of about 25 s each, about 25 min in all after boot. With `FP_ONBOX_BUILD=0`, about 5 min.

When `done` or `failed`:

```sh
tinfoil http get https://<DOMAIN>/results.tar.gz --enclave <DOMAIN> --repo <OWNER>/<REPO>@<TAG> > h200-results.tar.gz
tar -tzf h200-results.tar.gz | grep -c . ; tar -tzf h200-results.tar.gz | grep -c isk     # second number must be 0
tar -xzf h200-results.tar.gz && (cd results && sha256sum -c --quiet SHA256SUMS)
```

If `tinfoil http get` writes a body other than raw bytes on this CLI version, use the verified proxy instead: `tinfoil container connect <PROVER> -p 3301` in one shell and `curl -s http://127.0.0.1:3301/results.tar.gz -o h200-results.tar.gz` in another (the proxy verifies attestation; plain `curl` against the domain does not).

## 6. Off the box: independent verification (CPU)

Same as research/gpu/local-verify: build `cp_verify` from a clean checkout at the pinned commit on a CPU machine, then for every run directory in `results/` that has a bundle:

```sh
ID=$(sed -n 's/^commitment ID: //p' results/<run>/cp_commit.log | tr -d ' ')
(cd results/<run>/bundle && <cp_verify> config ivk in/example.req out/example.y out/example.proof -id "$ID"; echo "exit $?")
```

Plus the five mutation cases of research/gpu/local-verify on each bundle (proof bit flip, answer bit flip, request bit flip, proof truncated, wrong ID): each must exit 1 with `NO`.

## 7. Teardown and restore (ends the downtime)

```sh
tinfoil container stop <PROVER>                     # frees the GPU
tinfoil container get <PROVER>                      # wait for Stopped
tinfoil container deploy <LIVE> --tag <LIVE_TAG> --mark-latest=false
tinfoil container get <LIVE>                        # Deploying -> Starting -> Running
```

Keep `<PROVER>` stopped, not deleted, until the results are verified (a stopped instance holds no GPU); delete it afterwards with `tinfoil container delete <PROVER>` (irreversible, asks for confirmation).

`--mark-latest=false` on deploy so the latest release of `<LIVE_REPO>` stays what it was in step 0 (check with `gh release view -R <LIVE_REPO> --json tagName`; if it moved, put it back with `gh release edit <LIVE_TAG> -R <LIVE_REPO> --latest`).

The live instance's cold boot loads two 27B engines one after the other; its healthchecks allow up to 30 and 60 min. Expect it to be Running 15 to 60 min after deploy (not measured on this host; the earlier held candidates of this service were healthy about 10 to 25 min after release).

## 8. Verify that the live service serves again

```sh
tinfoil container get <LIVE>                         # Status Running, all boot stages ok, tag <LIVE_TAG>
tinfoil http get https://<LIVE_DOMAIN>/healthz --enclave <LIVE_DOMAIN> --repo <LIVE_REPO>@<LIVE_TAG>
date -u +%FT%TZ                                      # downtime ends
```

Then the live service's own end-to-end check: one attested request to each model it serves, the same probe as in step 0, and the local bridge that depends on it reporting healthy. Re-seed its demo data if it had any (step 3). Record the downtime window (step 3 to here) in the RESULT.

## 9. Write-up

`experiments/20261110-43-h200-bringup/`: ENV.json (from gpu-env.txt, host-env.txt, cc_probe.json, nvcc/gcc, binaries.sha256), RESULTS.md against the PREREG thresholds, raw runs under `runs/`, research/results.yaml rows with hardware key `gpu-h200-tinfoil-a` (to be added), and a comparison table in the form of research/gpu/replication-1/README.md. Redact the domain, instance IDs and org identifiers before committing (run scripts/check-no-host-paths.sh and grep for the org's names).

## Choice B (the prover inside the live instance) and choice C (another host)

B: no stop/deploy of a separate instance. Add a `prover` container to the live config, release a new tag of `<LIVE_REPO>`, and `tinfoil container update <LIVE> --tag <NEW> --hold=true --mark-latest=false`. Blue/green would need a second free GPU on the host, so expect `HOST_GPU_BUSY`; the update then needs a stop and deploy with downtime anyway (step 3, then `tinfoil container deploy <LIVE> --tag <NEW> --mark-latest=false`). It also needs the engines' `--gpu-memory-utilization` lowered so that about 27 GB stay free for `cp_commit` (README.md, "What fits"), and it changes the measured config that the live service's clients verify. Restore = deploy `<LIVE_TAG>` again (same downtime).

C: a second GPU host for the org (ask Tinfoil). Then step 3 and step 7's restore are skipped; create the prover on that host with `--host <HOST2>` (explicit host selection must be enabled for the org first).
