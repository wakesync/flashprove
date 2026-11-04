# Full confined CPU suite at PR #4 head: aggregate exit 77

**Status: evidence only.** This directory publishes the receipts of the single confined full CPU-suite run that [docs/research-evidence.md](../../docs/research-evidence.md) and the [PR #4 closeout comment](https://github.com/wakesync/flashprove/pull/4#issuecomment-6613832649) summarize. Until now those receipts were local only; the comment's SHA-256 anchors pointed at files that were not in the repository. They are committed here so that the "89 passed / 2 partial / 0 failed / 1 not run" claim has a public receipt. No suite was rerun to produce this directory.

## Standards

This run predates the 2026-11-03 21:31Z research standards (pre-registration, pinned environment, variance, as enforced by the project dev loop). It ran 2026-11-03 18:28:39Z to about 19:41:30Z; only the publication of its receipts came later.

- It was **not pre-registered**. There is no PREREG, and none has been written after the fact.
- **n = 1.** One run, no variance data.
- It is the **grandfathered** claim `cpu-aggregate-77` (gaps: pre-registration, variance). It is **not a headline**.
- The 4370.89 s duration is wall time of one run on a shared host. It is **not a performance number** and should not be cited as one.

The machine-readable environment manifest is [`ENV.json`](ENV.json). Values the run did not record (RAM, provider, OS point release) are marked unknown there.

## What ran

- Tested source: PR #4 head `133da749937115883c95edfc4b6e372c16209449` (merged to main as `eff9bda3`).
- Command (from `run_full.py`, the as-executed driver): `python3 -u run_suite.py cpu <WORK> --jobs 4`, upstream's own confined runner, CPU mode.
- Host: AMD EPYC-Rome KVM VM, 16 logical CPUs, Ubuntu 24.04, Linux 6.8.0-100-generic, g++ 13.3.0, Python 3.12.3. Shared host.
- Duration 4370.89 s (`full-result.json`). One run (n = 1).
- Head binding: the `head` field in `full-result.json` is a string literal in `run_full.py`. The driver did not run `git rev-parse` or check for a dirty tree, so it is not a recorded checkout state. The binding to `133da749` rests on the driver and on the independent bounded rerun at `133da749` in the PR #31 review, which reproduced the row classifications.

## Result

`full.exit` is **77**, not 0. The last line of `full.log`:

> 89 rows passed, 2 passed in part (status 77 ...), 0 failed, 1 not run ..., 13 left out in mode cpu because they need nvcc or a GPU ...; 0 ended with status 3; 0 lines to look at; 4371 s; ... the call chose 92 of the table's 173 rows

| class | rows | which |
|---|---:|---|
| passed | 89 | `full-rows.json` |
| passed in part (77) | 2 | `tools.confine` (29 checks as expected; signal and second-level kernel cases not run), `weight_sums` (13 Python substeps skipped: numpy / gguf-py 0.19.0 missing) |
| not run (77) | 1 | `verifier.clang_build` (no clang++ on the host) |
| failed | 0 | |
| left out, GPU-dependent | 13 | CPU mode excludes them by design |

Rows that touch the PR #4 repair: `tools.lean_verify.script` 346 calls as expected (fake Lean, not real Lean), `integrations.cp_verify` 68 passed, `integrations.unit` 1961 passed, 3 skipped, 20 deselected.

Later targeted receipts (in [`../integration-adoption/`](../integration-adoption/README.md)) closed the clang row (clang 18.1.3, exit 0) and the weight_sums skips (0 skipped) at the same source. They do not relabel this aggregate: the full-suite aggregate stays 77.

## Files

- `full.log`, `full.exit`, `full-result.json`: runner stdout, aggregate exit, argv/head/duration.
- `full-rows.json`, `full-rows.txt`: per-row classification derived from `full.log`.
- `full-screens/`: all 92 per-row screens copied from the runner's work directory.
- `run_full.py`: the driver that launched the run (as executed, paths redacted).
- `independent-closeout-review.md`, `closeout-static-review.json`: the separate source review of the four repaired files (not merge approval by itself). `closeout-static-review.json` is that review's raw command log (argv, exit, output of `git diff --check`, `bash -n`, `git rev-parse`, `git status`, `sha256sum -c` run against the PR #4 tree); its `git diff --check` exit 2 is trailing whitespace in `research/integration-v2/evidence/adapter.log`, not in this directory.
- `ENV.json`: commits, toolchain, hardware and seeds for this run, derived from the receipts above.
- `ORIGINAL-SHA256SUMS`: the manifest of the **unredacted** local receipts (sha256 `744928a2fdba3afeebb2d4af59da2d1d249e140f5ff6b3cb13cf03343ecb7252`, the anchor quoted in the PR #4 comment). It will not verify against these files, because local paths were replaced.
- `SHA256SUMS`: the manifest of the files as published here. Check with `cd research/cpu-full-suite && sha256sum -c SHA256SUMS`.

## Redaction

Only path prefixes were changed: the checkout to `<REPO>`, its workspace parent to `<WORKSPACE>`, the work directory to `<WORK>`. No number, status or other text was edited. Files whose bytes changed therefore differ from `ORIGINAL-SHA256SUMS`; files with no local path still match it, which `sha256sum -c ORIGINAL-SHA256SUMS` shows (path-bearing files report FAILED, path-free ones OK).

## Limits

One run on one shared host. Not a GPU, real-Lean, TEE or production-model result. The checkout ancestor was group-writable (the runner warns about it in `full.log`), so this is not a secured build attestation. The kernel cannot confine ordinary signals.
