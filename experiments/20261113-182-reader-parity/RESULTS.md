# CPU reader dense table-line parity, issue #182

## Verdict: PARTIAL against the full PREREG

Release-only evidence supports the narrow reader change, but the registered milestone is **not PASS**. The unchanged unit harness provides no sanitizer-build option, so the registered UBSan arms and their controls were **not run**. The first release series also failed its runner expectations; a separately labelled supplementary series diagnoses and corrects runner mistakes without deleting or overwriting any first-series output. Neither series makes a proof.

The initial refusal remains byte-identical under `runs/build/`. The dated output-directory amendment was committed alone before the continuation builds. Seven release binaries were built successfully through the unchanged repository harnesses (six reader/control binaries via `prover/tests/unit.sh`, one unmodified verifier via `verifier/build.sh`) into a private output directory created by `mktemp -d`. No permissions, harness checks, compiler selection, digest algorithm or verifier source changed.

## Measured counts and variance

Both series contain **33 fixtures** (21 dense, 12 experts-present), five repetitions, and three observations per fixture: baseline reader, patched reader, and verifier planning. Each series therefore has **330 reader calls and 165 verifier calls, 495 total**. Readers alternate before/after ordering by repetition; cases are lexical. No completed execution is excluded.

- First series, `runs/continuation-matrix/`: **25 expectation mismatches**, five per repetition. Median 5, population SD 0, min/max 5/5 over n=5. The four existing-test invocations all fail usage because this lane omitted their required policy-file argument; no regression assertion executes in those four calls.
- Supplementary series, `runs/supplementary-matrix/`: **0 expectation mismatches**, zero per repetition. Median 0, population SD 0, min/max 0/0 over n=5. Four separately labelled corrected existing-test invocations pass (two tests by two reader arms).
- Combined execution accounting: **660 reader probes, 330 request-planning calls, eight existing-test invocations**, four failing usage and four passing. Two array-planning calls and two layout-packer calls are fixture construction, not additional matrix trials. There are no UBSan binaries or executions.
- Commands, exact rejection text and process exits are in per-call JSON; source and binary SHA-256 are in `runs/continuation-source-hashes.json` and `runs/continuation-build/hashes.json`. Fixture hashes are recorded separately for each series. No timing/performance claim is made.

See [MATRIX.md](MATRIX.md) for all 33 before/after/verifier rows. All five repetitions agree on category and exit within each series.

## Why the first series does not pass

Five mismatches recur in each repetition:

1. Dense valid and dense no-digests verifier calls return `plan-layout`, not the registered standard-form outcomes. The runner combined the layout packer's standard error with standard output. Its diagnostic text landed inside a layout line. This is a fixture-generation error, not verifier rejection of the digest contract.
2. Dense and experts invalid word encodings are rejected by the verifier as `policy-tables`, not the runner's expected `policy-line-form`. Both readers correctly reject them during parsing as `policy-line-form`. The PREREG requires parse failure, not identical reader/verifier error names.
3. The baseline absent-kind fixture with digest lines returns `policy-tables` before reaching the absent-kind limit. The patched reader and verifier return `header-absent-kind`. Both versions reject it; no malformed file becomes admissible.

The supplementary runner separates standard output/error, supplies the existing tests' documented argument, and corrects only those three expected diagnostic tags. It writes a new directory, including new full fixtures. The original inputs, expectations, output and summary remain unchanged. This is an explicitly labelled later rerun under the PREREG's rerun rule, not retroactive replacement of the registered first result or relaxation of the acceptance threshold.

## What the release observations establish

- All five baseline valid-dense probes parse but reject admission as `policy-tables`. All five patched probes parse and admit. In the supplementary series the unchanged verifier matches the dense public tables and reports standard form met (planning exit 4, not proof success).
- Dense no-digests parses and is admitted by both readers. Supplementary verifier planning reports only `table-digests` unmet. Parsing without digests is deliberately not globally banned.
- Partial, reordered, duplicate and out-of-range words fail parsing in both readers for dense and experts kits. Dense nonzero sigmoid is rejected at every one of its eight positions. Dense rcl/gcl and absent-class/absent-kind cases remain rejected.
- Changed dense SiLU, rotary and softmax words are syntactically admitted by the patched reader but rejected by the unchanged verifier as `table-digest-silu`, `table-digest-rope`, and `table-digest-exp`. This occurs in both series, before any layout acceptance.
- All 12 experts-present cases have identical before/after reader categories and exits in every repetition, including valid/no-digest, four malformed forms, four changed table digests and two invalid clamp values. Valid experts includes the existing valid clamps.

## Boundary and exclusions

The reader does syntax and limit admission only. It does **not recompute table hashes**. Actual table generation/hash comparison, quantization-scale and layout checks, and the complete standard-form decision remain in `cp_verify`. No cryptographic validation is attributed to the reader. None of these planning calls consumes a key or proof. No dense key, dense proof, Qwen forward, conversion, GPU build, `cp_commit`, `cp_prove`, model weights, serving or attestation call occurred. The full dense producer path remains unestablished; other producer-only limits are outside this patch.

## Deviations, limits and next step

- UBSan is not run: the unchanged harness has no supported interface for the registered sanitizer flags. The authorization explicitly forbids direct compilation or altering/bypassing that harness. No substitute sanitizer mode is claimed.
- The continuation uses cores 12-13 as explicitly directed, rather than the first lane's 10-11. Every build/test has a 4 GiB address-space cap and 115/120-second soft/hard CPU limit. Full build and matrix batches use the shared heavy-job gate. The continuation's last test completed 299.3883728981018 seconds after its first build, inside its 25-minute run budget and before the original 21:40Z hard stop. The separately authorized continuation starts a new run budget after the first lane's refused, zero-compilation attempt; this does not make the elapsed gap between lanes a compliant original run.
- First-series runner mistakes and their corrected supplementary rerun are disclosed above. The full PREREG is not declared satisfied.
- Measured, unreplicated. The draft needs a two-family review pair and a separately authorized plan for UBSan support before the milestone can be declared complete. No historical experiment receipt has been edited.
