# PREREG: 20261113-182-reader-parity

Issue: #182. Lane: reader182. Date (UTC): 2026-11-13.
Base commit: 59bff9a4608e0cc720d58d7c30823a8838fa43e4.

## Hypothesis
Replacing only the host reader's experts-only table-line admission rule with the verifier's dense zero-sigmoid rule removes the valid dense digest mismatch without admitting malformed groups or changing experts-present outcomes.

## Metric
Record separately CPU parse refusal, CPU limit refusal (not run after parse failure), process exit, and the unchanged cp_verify planning/standard-form result for each fixture. Record exact rejection text, file/source/binary SHA-256, compiler flags and commands. These are deterministic functional outcomes, not timing measurements or proof verification.

## Acceptance threshold
All registered cases must match their expected categories in release and UBSan reader builds, with no sanitizer diagnostic. The pre-change reader must parse the valid dense own-digest file but reject it with policy-tables; the patched reader must admit it and the unmodified verifier must match its three tables and report standard form met. No digest lines must remain parseable/admissible but fail the verifier's table-digests standard-form condition. In both readers a partial group, reordered word, duplicate word and invalid encoding must fail parse. Dense nonzero sigmoid words (each of the eight positions tested separately) must fail admission with policy-tables. Changed SiLU, rotary and softmax words must be syntactically admitted by the patched reader but refused by cp_verify with table-digest-silu, table-digest-rope and table-digest-exp respectively. Dense rcl/gcl and absent-class/absent-kind controls must still be refused. Experts-present controls (valid digests, no digests, changed digest for each table including sigmoid, partial/reordered/duplicate/invalid word, clamps) must have identical before/after reader outcomes. No verifier source, arithmetic/shape rule, digest algorithm or historical result may change.

## Kill criterion
Stop on a required change outside the reader's table-line rules, a malformed group newly admitted, a sanitizer finding, or an unexplained experts-present change. Publish FAIL or PARTIAL with the blocker. Hard stop 2026-11-13T21:40:00Z. CPU cores 10-11 only, at most two workers, 4 GiB hard address-space cap for builds/runs, expected below 2 GiB RSS. Each individual build/test command is bounded below two minutes CPU; any job expected to exceed that requires the shared heavy wrapper, and no model/prover/GPU job is permitted. Overall build/test budget 25 elapsed minutes from first build (including any gate wait). No weights, forward pass, cp_commit/cp_prove, key/proof production, external service or spend.

## Runs
Five repetitions per reader arm and build mode, and five planning calls per fixture with the release unmodified verifier. Alternate before/after reader ordering per repetition; run fixtures in stable lexical order. No warmup and no excluded completed run. Also run the existing parameter_file_one_bits and parameter_file_one_place CPU tests once per reader arm in release and UBSan. UBSan exercises the reader and malformed suite, not a claim of full-verifier sanitizer coverage. Summarize count of expectation mismatches per repetition using median, population SD and min/max. Seeds: none (deterministic byte mutations).

Fixtures derive from committed small kits: the dense own-digest and no-digest policy/layout files in experiments/20261113-156-dense-table-digests/runs/served/dense-files, and prover/examples/target_small_f2 or verifier's committed small kit for experts-present controls. Preserve full fixture bytes, hashes and derivation. If a kit hits an unrelated producer-only shape limit, retain that result and construct a compatible synthetic fixture using existing admitted values before the registered run; never loosen the rule. Compile a host-only parse/admission probe through prover/tests/unit.sh, plus the same source with UBSan flags. Build the baseline using the pinned original header, not a hand-recreated old predicate. New regression coverage follows the existing host-only parameter_file tests. No registered fixture may be used for debug execution before the registered suite; compile-only checks are allowed. Unexpected outcomes remain in receipts; any later rerun is separately labelled and cannot erase the first run.

## Prior art
This is rule parity, not a new proof system or digest. The contract is already on main in verifier/docs/parameter-file.md and verifier/src/cp_verify.cpp (polLayout zero-sigmoid check), established by merged PR #158. Its experiment identifies the unchanged CPU reader as a producer boundary mismatch. The existing prover/tests/parameter_file_one_bits_test.cpp and parameter_file_one_place_test.cpp provide host-only testing without CUDA. The reader intentionally does not compute public tables: cp_verify owns those comparisons and standard-form checks. Lookup-based systems such as zkLLM, EZKL, Jolt and Expander motivate table binding but provide no new evidence for this narrow parser patch; no TEE claim is involved.

## Amendments
