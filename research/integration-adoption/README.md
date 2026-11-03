# Repaired integration adoption candidate

**HOLD. This candidate is not approved for merge.** PR4 must first receive an explicit disposition of its remaining coverage gates and independent exact-head review. No merge of this candidate or the original operator stack may bypass that decision.

## Ancestry and adoption

This isolated branch starts at PR4 `133da749937115883c95edfc4b6e372c16209449` and makes conflict-free local integration commits, in order, retaining the original commits as ancestors:

1. Top-k prerequisite `a425c6c6f53b8697a35e29258ac035a1a347a03f`.
2. PR14 `ba3c98459c2aae732fedeb9742db4deb5fcedfa8`, including public-binding predecessor `65ada28a`.
3. PR15 `0af3dde7bace5b5e583434cb64ec38670fd57641`.
4. PR16 `8fca2c4b9ffb5d5180df51095d5f52a33df4a207`.

Resulting implementation head: `baa774321db94e4afc957e33a78af31ee07f69a0`.
`research/operators` is byte-identical to PR16. SUITE.md, integrations, tools, verifier and blocks are byte-identical to PR4. Original owners' branches and PR bases were not rewritten or retargeted. This is an alternative consolidated adoption candidate, not permission to merge twice. The coordinator should choose this route or an explicitly reviewed restacking route, then reconcile original PR14/15/16. Current PR targets repaired PR4, not main. After PR4 is approved and lands, reconcile main's separately merged documentation and review the final exact head again. Keep synthetic top-k constraint satisfaction distinct from the shared product-oracle and KDA algebra milestones.

## Targeted PR4 gap closure

Executed against clean exact PR4 source before any adoption merge, as an ordinary account under tools/confine.py or the default confined suite runner:

- Clang 18.1.3: user-local Ubuntu packages downloaded with apt and extracted with dpkg-deb, no sudo/system installation. `clang_build_test.sh --field 2` compared a new Clang build against the retained original full-run GCC target build. Exit 0, zero compiler warnings, 33 identical planning calls, two made-up-file fixtures as expected. No generated GPU world supplied, matching the CPU row's scope.
- weight_sums: isolated CPython 3.12.3 environment with numpy 2.3.5 and gguf 0.19.0. Confined selection `--only '^weight_sums$' --jobs 1`: aggregate 0, one row passed, **zero skipped**, including all 13 formerly unavailable Python steps. No CUDA/Torch installation.
- integrations unit diagnostic rerun with `-rs`, non-root selection: **1961 passed, 3 skipped, 20 deselected**, exit 0. This is the bounded unit row, not a duplicate full CPU suite. Root collection alone identifies all 20 deselected node IDs in `root-collection.log`; they were not executed as root.

The three skips are now identified, not waived:

1. `test_false_modules_are_not_imported`, start `as a module`, flags `[-I]`: intentional incompatible invocation, because isolated Python does not find a module in the current directory.
2. `test_the_demos_model_directory[integer]`: missing `integer_model_vllm`.
3. `test_the_demos_model_directory[float]`: missing `integer_model_vllm.float_pair`.

The latter two require the local integer-model package (declares Python >=3.13, torch==2.13.0; float export also needs safetensors). They are model-directory generation tests, not evidence of model serving or GPU proofs. They remain unexecuted. No unsupported dependency-version substitution or expensive model-stack installation was used to force them green.

## Failed setup attempts, retained transparently

The first weight follow-up used uv's default CPython 3.13.12, which lacks `os.pidfd_open`. All former dependency skips ran, but edge.cpp/edge.py/refusals.cpp/refusals.py failed that prerequisite. Aggregate 1, not a product defect or pass. Correcting to the system CPython 3.12.3 environment yielded the successful row above; both receipts retained.

The first unit diagnostic used a newly made temporary parent with the account's group-writable default mode. The trust guard correctly stood aside (1964 skipped, exit 77). Only that newly created private test parent was changed to 0700, then a fresh basetemp used. No shared checkout ancestor or trust guard was changed. The successful diagnostic retained all original three skips.

## Remaining gates and limits

Original full CPU aggregate remains **77**, not retroactively relabeled zero. These are supplementary targeted receipts. Kernel ordinary-signal confinement and second-level kernel-answer-5 coverage remain unavailable. Real root mount/proc/account-file cases and the 20 root-only unit cases remain unexecuted. Source checkout still has a group-writable ancestor warning. The intentional isolated-import skip and the two model package skips need explicit scoped acceptance or further safe closure. The original 13 GPU-dependent CPU exclusions remain exclusions. No real Lean, hardware TEE, production-model E2E, cryptographic soundness theorem or speedup claim follows.

Independent review must cover the new integrated exact head, top-k prerequisite (not merely the already reviewed upper stack), source-equivalence assertions and targeted receipts. No hosted check/protection absence substitutes for this gate. No GitHub merges, original branch rewrites, confinement bypass or GPU spend occurred.

## Integrated-head checks

At implementation head `baa774321db94e4afc957e33a78af31ee07f69a0`, the confined follow-up completed all 17 commands with their expected status: five Python top-k tests, four C++ builds and four honest/adversarial test binaries, plus eight invalid-affine-constructor calls with expected SIGABRT (-6), with core files disabled. Public binding: 7776-byte proof and three hostile proofs rejected. Shared wires: 7936-byte proof and two hostile edge proofs rejected. Affine rows: 7744-byte proof and two affine-only hostile proofs rejected. KDA algebra: 8144-byte proof and three hostile proofs rejected. Detailed mutation/domain/truncation counts are retained in each log. This is execution evidence, not independent review or broader soundness approval.

During this work PR17's ledger correction landed on main (`4c0ea496`), and the separate real-model owner opened PR19 at `aeebf5ffeea8fbf0b048a156aad3c298ad2b02e1` on PR16. Neither is silently included in this bounded adoption candidate; PR19 needs its own review/adoption decision. Main documentation reconciliation remains a coordinator step after PR4's HOLD is resolved.

## Evidence format

Public evidence copies normalize local checkout/dependency paths to `<CHECKOUT>` / `<PLANNING>` and temporary prefixes to `<WORK_*>`; this is path redaction only, not verbatim raw bytes. Raw local receipts and original full-suite receipts remain retained separately. JSON commands record actual execution heads dynamically. The operator follow-up compiles/tests in a confined temporary folder without overwriting the original stack's committed evidence files. `SHA256SUMS` covers these published normalized files.
