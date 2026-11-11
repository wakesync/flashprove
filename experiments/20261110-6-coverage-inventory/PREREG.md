# PREREG: 20261110-6-coverage-inventory
Issue: #6. Lane: coverage6. Date (UTC): 2026-11-10T23:05Z. Base commit: ba1e3067f58b0142dd16a3df884626cfe6ccc585.

## Hypothesis
On main at the base commit, every admitted operator, range/rounding rule, committed input/state and output position of the shipped `cp_verify` relation (plus the fork's research operator relations) can be mapped to a named code or document site and classified as one of four enforcement kinds; and, for three rows that are "verifier-side application validation" rather than "proof constraint", a complete, honestly made proof that is valid for a different statement (other commitment, other policy, other coverage) is rejected by exactly that validation, while the same files are accepted when the caller states the statement the proof is really about.

## Metric
1. Inventory: number of rows, by category (operator, range/rounding, committed input/state, output position) and by enforcement kind (`proof_constraint`, `verifier_validation`, `prover_only`, `not_enforced`). Counted from `research/coverage/inventory.yaml` by `research/coverage/check_inventory.py`, which also checks that every cited site (file plus literal symbol or phrase) exists in the tree. Exit code of the checker on the PR head.
2. Negative tests (three cases, N1 to N3 below): for each case, the attack arm's exit code, last line, and the line that names the check (the verifier's `policy:` / `id:` line, or `check_proof:` reason); and the control arm's exit code and last line. Measured by `experiments/20261110-6-coverage-inventory/negative.py`, which writes `runs/negative-registered.json` with input SHA-256s and the trimmed outputs.
   - N1 commitment substitution: the stored clipped-gap example's complete files (its own key, leaf, config, request, proof) presented under the exact-match example's commitment ID. Intended check: the ID comparison in the key stage (`model-statement`, cp_verify.cpp). Control: the same files under their own ID with their own `-policy`.
   - N2 policy substitution: the stored clipped-gap example's complete files under its own ID, called (a) without `-policy` (a client that expects exact match) and (b) with `-policy exact-match` numbers. Intended check: `cpPolicyHeld` (`NO: policy` with the "no -policy" / "another kind of policy" reason). Control: the same call with the right `-policy`.
   - N3 coverage substitution: the stored exact-match example (range 60:64) given to `integrations/check_proof.py` by a client that expects a wider range (59:64). Intended check: the integration's range comparison (`Request.__init__`, "the request file's checked range is"). Control: the same call with `--range 60:64`. Also recorded: `cp_verify` alone on the same files ends `YES`, which is what makes this row application validation and not a proof constraint.
   A case counts as "rejected for the intended check" only if the attack arm's exit code is 1, its last line is the expected one, the named reason line is present, and the control arm accepts (exit 0, `YES` or `WITHIN LIMITS`).

## Acceptance threshold
Fixed now:
- Inventory PASS: at least 40 rows, every row has at least one cited site, every site resolves (checker exit 0), every row in categories operator / range / input-state / output has one of the four kinds, and the open-gaps list contains every `not_enforced` and `prover_only` row (checker verifies this).
- Negative tests PASS: N1, N2 (both sub-arms) and N3 each meet the "rejected for the intended check" rule in 5 of 5 repetitions, and every control accepts in 5 of 5.
- Any attack arm that is accepted is a FAIL and is reported as a finding, not retried.
This is descriptive. It does not establish soundness, and a pass says nothing about inputs other than the stored synthetic fixtures.

## Kill criterion
Hard stop for the lane 2026-11-11T01:10Z (wall clock, including any time queued in fp-heavy.sh). Registered negative run budget: 15 minutes elapsed from the moment the gate grants the slot (logged by negative.py). If the budget ends, publish what finished as partial. CPU only, no GPU, no spend, no downloads.

## Runs
- Inventory checker: deterministic; run once per commit, plus a mutation self-test (a copy of the inventory with one symbol changed must make the checker fail), recorded in `runs/checker-selftest.json`.
- Negative tests: 5 repetitions per arm (attack and control), order alternates by repetition (odd: control then attack; even: attack then control). Deterministic inputs, no seeds. `cp_verify -j 1`, pinned to CPUs 0-5, run under `fp-heavy.sh`. Shared, loaded host: times are diagnostic only. No run is excluded.
- Debug: before the registered run, negative.py is exercised only with `--dry-run` (builds commands and hashes inputs, invokes no verifier). The first verifier call on any registered case is the registered run. The verifier is built once from the base commit with `verifier/build.sh` before the run (a build is not a run of the suite).

## Prior art
- **EZKL** (zkonduit): compiles an ONNX graph to a Halo2 circuit; its notion of coverage is "every op in the graph is a constraint", with a visibility setting per input/output/param (public, private, hashed, fixed). Unsupported ops fail at compile time. There is no per-relation inventory separating circuit constraints from host-side checks: what the host checks (input hashing, visibility, calibration ranges) lives in settings, not in the proof.
- **zkLLM** (Sun, Li, Zhang, CCS 2024): proves full LLM inference with tlookup (non-arithmetic ops as lookups) and zkAttn (softmax). Coverage is stated per operator class; rounding/precision is argued in the paper; no machine-readable map from relations to code.
- **Jolt** (a16z): a zkVM where coverage is instruction-level (every RISC-V instruction is a lookup into a decomposable table); soundness obligations are tracked per instruction and in an audit/bug list, not as a typed inventory of host versus proof checks.
- **Expander / Polyhedra** (GKR-based): coverage is "the circuit"; the zkML front ends list supported layers. Host-side preprocessing (quantization, input commitment) is outside the proof and documented in prose.
- In this repository: upstream `docs/protocol.md` 6.4 (ten verifier check groups), `guide/what-is-proved.md`, `docs/model.md` section 9 (range conditions), `research/security/threat-model/` (bound/not-bound table), PR #41 (Fiat-Shamir binding probe) and `examples/rejected-proofs/` (altered copies of honest proofs).
- What is new here: one typed, machine-checked inventory of relation elements against their enforcement site with four kinds, a checker that fails when a cited site disappears (so the inventory cannot rot silently), and negative tests that feed complete honest proofs of a different statement (not bit flips) to the application-level checks.

## Amendments
(empty at registration)

### 2026-11-11T01:20Z, after review of PR #97 (lane fix97)

1. **Scripts were not committed before the registered run.** `negative.py`, `check_inventory.py`, `selftest_checker.py` and the inventory first appear in commit `81c93f46` (2026-11-10T23:27:14Z), together with the receipts; the registered negative run ran 23:24:54Z to 23:25:29Z. This PREREG was first and alone, but scripts-before-runs was not met. The original receipts (`runs/negative-registered.json`, `runs/inventory-check.json`, `runs/checker-selftest.json`) stay as they are and are not the evidence of record any more.
2. **Repair run, registered here before it runs.** With scripts already committed on this branch (`negative.py` unchanged since `81c93f46`; the checker and self-test as of the commit before this amendment):
   - `python3 experiments/20261110-6-coverage-inventory/negative.py --out runs/negative-repair-20261111.json`, under `fp-heavy.sh taskset -c 0-5`, the same 5 repetitions per arm, same order rule, same threshold and same "rejected for the intended check" rule as above. `bin/cp_verify` built with `verifier/build.sh` from this branch (verifier/ unchanged since the base; build digest must equal ENV.json's). No run of the suite between this amendment and the repair run.
   - `python3 research/coverage/check_inventory.py --json experiments/20261110-6-coverage-inventory/runs/inventory-check-20261111.json` and `python3 research/coverage/selftest_checker.py --json experiments/20261110-6-coverage-inventory/runs/checker-selftest-20261111.json`.
   - Budget 15 minutes elapsed from the gate granting the slot (negative.py logs it). Hard stop for the repair 2026-11-11T02:30Z wall clock, queueing included. If it is missed, the original receipts stay the only evidence and the result says so.
   - Evidence references (RESULTS.md, results.yaml) move to the repair receipts, with the original ones kept and named.
3. **"Every" in the hypothesis is not met.** Review found elements with no row (embedding lookup, stream links between segments, range conditions 1 to 6 and 8, tokens after e, GLM KDA prototypes, qwen_ops internal relations, the caller's y). They were added (64 to 84 rows). The inventory is now described as an inventory, not a complete map; research directories it does not cover are listed under `excluded`, which the checker enforces. The inventory threshold (at least 40 rows, sites resolve, four kinds, gap rows in gaps) is unchanged and is judged on the repair receipt.
4. **Checker changed after registration.** It now fixes the four kinds and categories itself (an inventory that declared a fifth kind used to pass), requires symbols of at least 12 characters, restricts plain gaps to prover_only / not_enforced rows and checks research directories against `excluded`. Its self-test gains cases M5 to M10 and runs M3 for every gap row.
