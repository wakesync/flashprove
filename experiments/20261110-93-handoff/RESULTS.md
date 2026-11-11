# Results: two-chunk joint handoff

**PASS against the bounded PREREG, measured and unreplicated.** This is a joint proof for two fixed-size chunks, not a separately resumable/private-root handoff protocol. Issue #93 remains broader than this milestone.

## Plain-language result

The first chunk's final state and the second chunk's starting state are linked by constraints inside one proof, rather than by Python comparing public boundary hashes. The proof also enforces the history shift register from verifier-pinned pre-conv inputs. The standalone verifier reads only its own statement file and a proof. It does not read the prover's manifest or witness files.

The initial root still has a **public opening checked by SHA-256 outside the proof**. Synthetic model/weights identifiers are bound labels, not proof of checkpoint execution. There is no convolution, projection, real-weight fidelity, privacy or production-security claim.

## Registered outcomes

- H1: 5/5 honest windows accepted, five independent synthetic seeds, D8/F12, two chunks of two tokens.
- H2: 65 complete-hostile proofs and five unchanged-proof statement replays were tested. 70/70 rejected by the proof verifier. All complete-hostile proofs preserve every product gate and emit the full protocol; the reported affine violations are diagnostics, not a verifier precheck.
- H3: the independent counting script matched core/aligned columns, affine relations and range cells of every honest built relation.
- No runs excluded. No timing or speedup hypothesis. Outcomes below are Boolean observations, not estimates of cryptographic soundness.

Raw evidence: `runs/suite.jsonl`, `runs/summary.json`, `runs/counts.json`; environment and source revision: `ENV.json`; binary/source hashes: `runs/build.json`. Deterministic proof and statement hashes are in every raw row. Proofs and witness files are reproducible under ignored `work/`, not committed as large binary artifacts.

| Case | Acceptances / n | Acceptance median; SD; min..max | Violated relations median; SD; min..max |
|---|---:|---|---|
| `honest` | 5/5 | 1; 0; 1..1 | 0; 0; 0..0 |
| `mixed_F12_F13` | 0/5 | 0; 0; 0..0 | 176; 1.92354; 172..177 |
| `split_chunk` | 0/5 | 0; 0; 0..0 | 5; 0; 5..5 |
| `replaced_token_inputs` | 0/5 | 0; 0; 0..0 | 592; 0.894427; 590..592 |
| `two_sided_history_shift` | 0/5 | 0; 0; 0..0 | 96; 0; 96..96 |
| `changed_last_chunk_history` | 0/5 | 0; 0; 0..0 | 1; 0; 1..1 |
| `other_layer` | 0/5 | 0; 0; 0..0 | 2; 0; 2..2 |
| `other_first_state` | 0/5 | 0; 0; 0..0 | 71; 3.28634; 67..76 |
| `dropped_chunk` | 0/5 | 0; 0; 0..0 | 197; 0; 197..197 |
| `truncated_window` | 0/5 | 0; 0; 0..0 | 91; 0.447214; 90..91 |
| `prefix_only_window` | 0/5 | 0; 0; 0..0 | 181; 0; 181..181 |
| `other_model_weights` | 0/5 | 0; 0; 0..0 | 4; 0; 4..4 |
| `other_request` | 0/5 | 0; 0; 0..0 | 2; 0; 2..2 |
| `changed_intermediate_state` | 0/5 | 0; 0; 0..0 | 67; 1.64317; 64..68 |
| `statement_replay_other_layer` | 0/5 | 0; 0; 0..0 | not applicable: transcript replay |

## Structure, not a performance study

All built structural observations below have n=5 (one per honest seed). These are this lowering's product columns and affine relations, not model-wide values or device memory. Three product field rows live behind each column. The aligned-column count still excludes the larger oracle padding, lookup planes, masks and proximity machinery.

| Quantity per window | Median | SD | Min | Max |
|---|---:|---:|---:|---:|
| core_columns | 6582 | 0 | 6582 | 6582 |
| aligned_columns | 7168 | 0 | 7168 | 7168 |
| relations | 12278 | 0 | 12278 | 12278 |
| relation_terms | 28398 | 0 | 28398 | 28398 |
| range_cells | 352 | 0 | 352 | 352 |
| proof_bytes | 1805704 | 195.436 | 1805480 | 1805928 |

The exact formula at T=2C is:

- Extra descriptor/history/input columns and relations: `E = 150 + 36D + 3TD`.
- Core columns: `T((F+5)D^2 + (4F+5)D) + E`.
- Affine relations: `T((2F+9)D^2 + (8F+7)D) + E`.
- Range cells: `T(D^2 + 3D)`.
- The core relation includes D^2 inter-chunk state equalities. The removal of the second initial pin and addition of the equality cancel in the formula. Both chunks' final public state pins are removed. History uses 27D equalities and 9D initial public pins.

`count.py` inventories these independently and the registered runner compares the built fields. The following larger shapes are **counted, not built/proved**; D128 is outside the executable's admitted verifier domain. These are not fit estimates.

| D | C | Core columns/token | Affine relations/token | Evidence kind |
|---:|---:|---:|---:|---|
| 8 | 2 | 1645.5 | 3069.5 | counted and checked against built relation |
| 32 | 2 | 19525.5 | 37509.5 | counted-not-built |
| 128 | 2 | 286885.5 | 555429.5 | counted-not-built |
| 128 | 64 | 285733.171875 | 554277.171875 | counted-not-built |

## What the negatives do and do not establish

Mixed F12/F13 supplies second-chunk reference states computed with F13 while the verifier derives an F12 relation. Replaced token inputs are actually changed and the suffix recomputed. Initial/intermediate-state changes re-prove the altered recurrence. Two-sided history shifts change both copies of the handoff, and still violate the input-to-history relation. Other layer/request/model/weights proposals change descriptor cells while keeping the verifier statement fixed.

The split/drop/truncation/prefix cases use the two fixed circuit slots: proposed counts/ranges/lengths differ, with identity padding for absent computation. Their rejection is in-proof, but they are **not a variable-size chain of independently accepted chunk proofs**. A private implementation may internally split an otherwise identical computation and then provide the correct fixed-slot witness; that does not change the proved statement. The experiment does not claim to detect that invisible scheduling.

The replay case changes the verifier's layer and retains the honest proof. It tests transcript/statement binding separately from the complete-hostile affine-relation cases.

## Deviations and debugging

Append-only PREREG A1 makes the fixed-slot encoding explicit. A2 records the tiny-head RNG sample-pad collision found only on disjoint debug seed909/D4/C1, before the registered run. Sizing now reserves sample-pad space without dropping any check. `runs/build-debug-1.json` preserves the failed debug binary's hashes; `runs/build.json` is the successful registered binary. Missing local OpenSSL development headers were avoided with a small SHA-256 implementation for the public opening, independently checked against Python hashlib in statement generation. No registered threshold or seed changed; no registered run file was edited.

## Remaining work

- A kept-oracle/segment-frame construction for independently resumable chunks and an authenticated continuation root.
- Hidden initial-state commitment opening, if that is required by the application; the public opening here does not provide it.
- Actual weight/projection commitments and upstream input provenance. Synthetic identifiers alone do not prove model identity.
- The convolution and its connection to post-conv recurrence inputs; only history shift-register provenance is proved here.
- Higher security settings, non-deterministic prover coins, independent replication and hostile-witness review.
- Model-scale counting including all operators, and hardware measurement only in an authorized later lane. No device-fit claim is made here.

Reproduction commands and detailed trust boundary are in `research/operators/qwen_handoff/README.md`.
