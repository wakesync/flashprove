# RESULTS: independent aggregation of PR #124

## Plain-language result
The independent reader recovers all four published XS18/XS20 decisions from the committed per-position measurements.
Every registered cell has exactly 10 prompts and 1,461 positions, and all three original inclusive bars pass.
All flip identities and margins, pooled/per-prompt KL statistics and recorded guard/sanity/determinism predicates agree with the frozen comparison targets.
Two fail-closed attempts exposed our own schema/physical-file mapping mistakes, which were corrected with prereg amendments before any aggregate output or target comparison; their logs are retained.
This is aggregation-only corroboration, not independent model execution, blind review, a proof or whole-experiment replication.

## Verdict and provenance
**MATCH after the two disclosed reader corrections**, with **494 comparison checks and zero mismatches**. No denominator, flip or decision discrepancy with the historical result was found. Do not label PR #124 broadly replicated.

- Frozen source main: `59bff9a4608e0cc720d58d7c30823a8838fa43e4`.
- First commit `ac0eef6` contains `PREREG.md` alone, before reader/test code.
- Reader at successful execution: `4b71fa3`; exact full SHA, Python and CPU provenance are in `ENV-r3.json`. `ENV.json` and `ENV-r2.json` are retained records of earlier rejected attempts, not the successful-run environment.
- Independent outputs `runs/independent-r3-{1,2,3,4,5}.json` were committed at `650b9fb` before the original summary, results table or ledger were read as comparison targets.
- All five outputs have SHA-256 `f34fd142041421f91fa6b55ba57684210b80b29e4e4402ae20c2ff3df3f0a897`. Five identical deterministic aggregations are repeatability checks on the same measurements, not five independent experiments. Every aggregate has repeat SD zero and identical min/median/max across executions. Position-level SD below is sample SD (n-1), not run-to-run variation.
- `runs/comparison.json` retains every comparison, tolerance, source-target hash and the empty mismatch list. Comparison targets come from the frozen source commit, not the branch's later ledger. Full-precision tolerance is 1e-12 + 1e-10*max(abs(a),abs(b)); rounded numbers are checked at half a unit of their last printed digit. No tolerance is added to any original acceptance threshold.

## Four recovered cells
KL values in nats, n = 1,461 positions and 10 prompts in every row. p99 is nearest rank, sample SD uses n-1. All per-prompt counterparts are retained in each independent JSON receipt.

| Cell | Agree / n | KL median | KL max | KL sample SD | KL nearest-rank p99 | KL min | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| stock/XS18 | 1460 / 1461 | 3.160271585755936e-06 | 0.002788924868109888 | 0.0001485821038828617 | 0.000426228028278075 | 0 | PASS |
| stock/XS20 | 1461 / 1461 | 1.989792639989219e-06 | 0.002403451414664914 | 0.0001166905015458787 | 0.0001360524256490692 | -7.105427357601002e-15 | PASS |
| abl/XS18 | 1460 / 1461 | 2.947839011113729e-06 | 0.005657224845904807 | 0.0002150136142250639 | 0.0003468823209082927 | 7.105427357601002e-15 | PASS |
| abl/XS20 | 1460 / 1461 | 1.948722005096215e-06 | 0.002944549084737957 | 0.0001388942879175477 | 0.0001527007920714141 | 0 | PASS |

Each cell passes agreement >=99%, KL median <=1e-4 and KL max <=0.1, plus recorded guard/sanity/determinism prerequisites. Thus the original H1 and H2 conjunctions are both recovered. Agreement counts are calculated from token IDs, not by summing the stored flags; every stored flag is then checked against the IDs.

## Complete flip list
Positions are zero-based. No flips are omitted. XS20 stock has none.

| Checkpoint / arm | Prompt | Position | REF ID | Path ID | REF top-1 margin |
|---|---|---:|---:|---:|---:|
| abl/XS18 | p06a-digits-256 | 81 | 16 | 18 | 0.0018144960764985285 |
| abl/XS20 | p06a-digits-256 | 81 | 16 | 18 | 0.0018144960764985285 |
| stock/XS18 | p06a-digits-256 | 109 | 19 | 17 | 0.0088245581388193273 |

## Negative KL, not silently clamped
- abl/XS18: 0 negative values.
- abl/XS20: 0 negative values.
- stock/XS18: 0 negative values.
- stock/XS20: 1 negative values. `p11-chat-long` position 279: -7.1054273576010019e-15 nats.
All retained negatives satisfy the preregistered [-1e-12,0) roundoff interval. This is not a derivation of nonnegative KL from full logits, which are not present in the aggregation inputs.

## Guard, sanity and determinism
- Source hashes match the prereg manifest, including the required absence of the two error logs. Complete finite prompt/path arrays and layer/head coverage were admitted. This validates the recorded absence of errors; it does not rerun overflow guards or establish that the original program was correct.
- REF last-token sanity on p01 is 25358 on both checkpoints and agrees with saved fields.
- Physical divergence coverage is 64 rows in the abl file and 47 in stock. The shared stock-weight prefix 0..16 is in the abl file, then each checkpoint has its own 17..63 rows. Effective coverage is 64 layers for each checkpoint, not 128 independent layer records. Requiring a second copy of the prefix would be wrong.
- Every physical layer has exactly six boolean duplicate-path flags, 666 flags total. All are true. REF#2 residual differences are zero; XS18#2 differences match XS18. Duplicate logit token/metric arrays agree (REF#2 maxdiff zero, REF#2 KL within 1e-12, XS18#2 arrays exact). No new forward was run.
- abl: 1104 complete local-error rows, 48 head values each; 64 physical layer rows and 384 recorded bit-equality flags.
- stock: 805 complete local-error rows, 48 head values each; 47 physical layer rows and 282 recorded bit-equality flags.
- BF16H's five-prompt, 608-position subset is validated as context only. No BF16H verdict is introduced; its numeric summary is outside this audit.

## Synthetic tests and fail-closed behavior
`runs/synthetic-tests-r3.txt` records 15 reader test methods; `runs/comparator-tests.txt` records 3 comparator methods, all 18 pass. Methods include many subcases, not 18 independent measurements. Fixtures are constructed afresh with synthetic tokens/short arrays, never copied from historical records.

Coverage includes missing/extra/duplicate prompts and layers, missing/extra/duplicate head rows, truncated/extended per-position and head arrays, inconsistent T, token/flag disagreement, invalid token domains/types, NaN/Inf and overflowed JSON numbers, duplicate JSON keys, missing or false determinism data, injected guard errors, hash changes, unexpected error-log presence, sanity inconsistencies, nullable metadata, negative-KL tolerance and exact/adjacent threshold edges. Comparator mutations cover count, flip identity/margin, missing flip, bar/verdict, median/SD, sanity and determinism discrepancies. Malformed inputs produce a nonzero CLI exit without creating an output receipt; valid data with failed predicates produces a NEGATIVE receipt, marks affected cells FAIL, and exits nonzero. Existing output paths are refused to avoid mistaking an older receipt for a new result.

## Deviations and independence
1. Initial attempt at `1053350` rejected p06a's `text: null` as invalid metadata. The token-ID denominator and hashes were intact. The documented amendment allows nullable text, which is not used in computation. `runs/reader-1.txt` and `runs/repeatability.json` retain the rejection.
2. Second attempt at `1d407f6` rejected missing stock layers because this lane had reversed the physical filenames of the shared prefix in its prereg and implementation. The producer's pinned `e2e.py` makes the naming clear: the first leg is called abl but uses stock weights through layer 16. The amendment corrects file assignment while preserving exact effective layer coverage. `runs/reader-r2-1.txt` and `runs/repeatability-r2.json` retain the rejection. Neither failed attempt reached aggregation or comparison-target inspection. This is not presented as a clean first-pass success under the unamended registration.
3. The lane uses the Astra model family, which previously reviewed PR #124. Local prior-review state was inspected to establish that involvement; its first six lines exposed a prose statement that prior aggregation matched. No previous review code or numeric output was reused. This lane did not produce PR #124, but this is neither blind nor cross-model-family replication. The new reader was implemented independently, with standard-library arithmetic, and never reads/imports/executes the original `summarise.py`.

## What is not established
No independent measurement, model forward, weight authentication, reference correctness, KL-from-full-logits reconstruction, free-running generation, whole-model integer lowering, proof generation, soundness, verifier acceptance or deployment fidelity. This audit recomputes supplied per-position KL values and validates recorded determinism rather than rerunning it. Descriptive local-head outlier aggregation and max-logit-diff summaries are not recomputed. No historical record or original ledger replication label is changed. This lane's analysis is measured, unreplicated; do not promote it to a public headline.
