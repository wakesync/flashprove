# RESULTS: 20261111-36-keyfile-tensor-binding

**PASS against the selected small-key registration. Measured, unreplicated.**

A complete CPU key proof now binds each of four named row tensors to a verifier-held checkpoint and conversion manifest. The three complete substituted-table proofs are rejected by the native linear-claim check, not an outside hash of the witness. This is the existing small-key research fixture, not production cp_verify, a Qwen proof, or a soundness result.

The initial product-toy registration was replaced following a duplicate-session collision; the dated PREREG amendment discloses the entire sequence. The result is against that explicitly selected small-key plan, not an assertion that the original product-toy experiment ran.

## Provenance and threshold

- Initial PREREG-only commit: `82fae6f`. Duplicate-session rewrite: `12c4f3e`. Reconciliation/selection amendment: `7e42379`, before small-key adapter implementation.
- Implementation: `ba7fa76`; registered run code/CI commit: `d230a025019c59becc9adf073a7981b841a79b9c`. Release raw evidence committed in `c16632cffc2d7213d37a1e12617d8e123e6ec570`.
- Ten seeds, 1001..1010; no warmup or outlier exclusions. Gate granted at the UTC timestamp in `runs/ENV.json`, on cores 10-12 of a shared, loaded AMD EPYC-Rome CPU host. CPU only, no download or spend.
- Threshold: all honest controls accept; each of five named negatives refuses in all ten runs. All five thresholds met. Every negative attempted and failed the native proof check.
- `runs/seed-*/results.json` holds every timing/verdict; the adjacent `.key` files retain complete honest and malicious keys. `runs/summary.json` holds full-precision aggregate statistics.
- `replay.json`: all 150 saved-file decisions reproduce in fresh verifier processes. This is same-lane replay, not independent replication.
- Honest controls paired with the three swaps reuse the seed's original bound key. They are repeated verifications, not additional independently generated honest proofs.

## Named negatives and mechanism

| arm | accepts / trials | rejection mechanism |
|---|---:|---|
| one-tensor-swapped | 0 / 10 | second chain: a proximity test: BASE: the masked message in the proof does not satisfy the linear claim |
| two-tensors-swapped | 0 / 10 | second chain: a proximity test: BASE: the masked message in the proof does not satisfy the linear claim |
| tensor-order-permuted | 0 / 10 | second chain: a proximity test: BASE: the masked message in the proof does not satisfy the linear claim |
| manifest-root-other-checkpoint | 0 / 10 | one-time chain: the ranges: an opening does not lead to its root |
| conversion-id-mismatch | 0 / 10 | one-time chain: the ranges: an opening does not lead to its root |

For the first three arms the prover commits an in-range substituted matrix, binds the ORIGINAL held manifest, and uses truthful evaluations of its substituted matrix as its own pending targets. This lets it emit a complete WF/BATT/LIN key. The verifier independently derives the original expected targets and fails at `BASE: the masked message in the proof does not satisfy the linear claim`. The counterpart unbound legacy keys accept. One tensor replacement changes one element of row 0, the two-tensor case additionally changes an element of row 2, and permutation exchanges whole rows 0 and 1 under unchanged named addresses.

The checkpoint and conversion negatives replay an honest key under another self-consistent trusted statement. They fail inside the one-time native proof (range-chain opening), before the wrapper compares untrusted header IDs. Honest alternate-checkpoint and alternate-conversion keys accept. This is transcript binding, distinct from the false-evaluation mechanism of the first three arms.

## Cost and every timing arm

Units below are milliseconds for complete in-memory verification, including manifest consistency hashing and expected-MLE recomputation. File I/O, compilation, proving and caller-side fixture/world construction are not timed. The native KeyUnder copy/validation inside verification is included. SD is sample SD. All arms have n=10.

| arm | accepts | median ms | SD ms | min ms | max ms | key bytes (constant) |
|---|---:|---:|---:|---:|---:|---:|
| bound-honest | 10/10 | 1.402216 | 0.263356 | 1.260837 | 1.991122 | 63944 |
| conversion-id-honest-control | 10/10 | 1.494349 | 0.212408 | 1.334374 | 1.996573 | 63944 |
| conversion-id-mismatch | 0/10 | 0.437858 | 0.058010 | 0.372336 | 0.566950 | 63944 |
| legacy-honest | 10/10 | 1.338692 | 0.275164 | 1.120664 | 1.903108 | 63872 |
| manifest-root-other-checkpoint | 0/10 | 0.426076 | 0.083576 | 0.369651 | 0.611263 | 63944 |
| one-tensor-swapped | 0/10 | 1.475433 | 0.194928 | 1.330977 | 1.972547 | 63944 |
| one-tensor-swapped-honest-control | 10/10 | 1.501331 | 0.129582 | 1.345977 | 1.809271 | 63944 |
| one-tensor-swapped-legacy-control | 10/10 | 1.380291 | 0.291722 | 1.189072 | 1.986323 | 63872 |
| other-checkpoint-honest-control | 10/10 | 1.553669 | 0.239101 | 1.344632 | 2.059679 | 63944 |
| tensor-order-permuted | 0/10 | 1.478765 | 0.250013 | 1.282557 | 2.012121 | 63944 |
| tensor-order-permuted-honest-control | 10/10 | 1.303567 | 0.244934 | 1.239847 | 2.038731 | 63944 |
| tensor-order-permuted-legacy-control | 10/10 | 1.341944 | 0.165834 | 1.181588 | 1.740153 | 63872 |
| two-tensors-swapped | 0/10 | 1.459748 | 0.195346 | 1.294250 | 1.954022 | 63944 |
| two-tensors-swapped-honest-control | 10/10 | 1.421162 | 0.174998 | 1.230149 | 1.734883 | 63944 |
| two-tensors-swapped-legacy-control | 10/10 | 1.304574 | 0.099647 | 1.227935 | 1.494322 | 63872 |

The bound key is 63,944 bytes, versus 63,872 bytes for the legacy key in this fixture: exactly the 72-byte extension envelope. Each size has SD=0 and min=max at that value across all ten seeds. The native key portion remains 63,872 bytes here: BATT still emits the same sized sumcheck after batching six rather than two pending claims. This is not a claim that arbitrary tensor counts have constant proof size.

Bound honest verification: median 1.402216 ms, SD 0.263356 ms, range 1.260837..1.991122 ms. Legacy: median 1.338692 ms, SD 0.275164 ms, range 1.120664..1.903108 ms. The ranges overlap. No speedup, statistically resolved overhead, or large-model timing claim is made.

## Counted scaling, not Qwen measurements

Source: `counted.json`, reproducible with `research/weight-binding/keyfile/count.py`. Shapes come from merged #68 receipts; the effective-block count reuses merged #100. Nothing below is a new Qwen proof or integer conversion.

- All 1,199 source-tensor hashes occupy 38,368 bytes before names/shapes; their Merkle tree has 1,198 internal hashes and one 32-byte held checkpoint ID.
- A hypothetical one-effective-block-per-source extension would add 1,199 linear claims and hold 28,776 bytes of evaluation targets internally. Its flat-padding evaluation would have 39,699,843,584 entries, 39,699,842,385 fold multiplications, 21,084 extension-field point coordinates and 63,252 first-attempt SHA-256 point hashes. This is NOT the real Qwen conversion inventory.
- The actual text design instead has 722 effective blocks: 26,895,337,984 integers, 38,414,602,240 padded entries, 38,414,601,518 fold multiplications, 14,110 point coordinates, 42,330 first-attempt point hashes, 722 claims and 17,328 internal target bytes. Folded norms have no separate effective block; visual/MTP are outside that design.
- This adapter recomputes targets, so response serialization is zero bytes; the two root IDs and version/tag occupy a fixed 72-byte envelope. That is NOT an estimate of the full Qwen key size. Full native proof size, plan feasibility, table-side work and verification runtime require implementation and resizing, and remain uncounted/unmeasured. Point-hash counts omit rare rejection retries.

## Descriptive Qwen dry run

**NOT DONE.** `cache-probe.json` records a read-only search of local project and standard cache directories, plus two absent legacy/model directories. No safetensors files were present in those searched locations for stock pin `37561816` or huihui pin `739e3c5b`. Neither per-tensor root was recomputed from local weights. No weights were downloaded and old #68/#87 hash receipts were not relabelled a fresh rehash.

## Supplementary checks

- `runs/manifest-cross-check.json`: independent Python hashlib / merged wb_manifest computation agrees with the C++ checkpoint ID for every registered seed.
- `debug-ubsan/`: separate seed 9001, different tensor values and names; all fifteen arms pass with undefined-behavior sanitizer enabled. It additionally checks direct-sum versus folded MLE, row address coefficients, SHA-256 empty known answer, wrong version, truncation, trailing bytes, stale held IDs, noncanonical name order, a false header ID and corrupted native bytes. This is supplemental debugging, not another registered timing sample or independent replication.
- CI workflow rebuilds, runs the separate debug fixture, runs all ten seeds, and replays saved keys. The wrapper never returns a production TestedTable.

## Deviations and limits

1. Duplicate-session preregistration collision: two sessions addressed the same clone. The duplicate changed the PREREG to the small-key fixture and then stopped. The active session first attempted the originally registered product-toy debug fixture (length 8, seed 101); three attempts refused their plan before producing a proof. The discarded uncommitted product sources were moved out of the repository. Amendment `7e42379` openly selects the stronger small-key fixture before its implementation. No registered-suite fixture was run before its code commit, and no thresholds or observed results were silently changed. History is preserved.
2. The complete raw key files are retained, including the complete dishonest proofs. A later runner-only change records sanitizer flags correctly; it does not change the registered release protocol or its immutable receipts.
3. This is a native small-key research format and verifier, not a production cp_verify extension. The fixture uses test-only hand plans; no error-accounting, hiding, Fiat-Shamir/grinding or soundness theorem is established. No Qwen proof exists here and nothing demonstrates abliteration detection under proof.
4. Only four length-four public tensors with signed identity conversion and fixed row placement are implemented. Arbitrary tensor layouts, hidden-weight signed evaluations, Qwen conversion/placement, request/reply linkage and layers 17..51 remain outside the result.
5. Independent adversarial review and replication remain required. The bounded negative suite does not exhaust malicious strategies.

## Reproduce

Exact build, suite, replay, sanitizer, count and single-file verification commands are in [the code README](../../../research/weight-binding/keyfile/README.md). Use fresh output paths; never overwrite committed receipts.
