# PREREG: 20261103-model-identity
Issue: none (model-identity lane). Lane: C, CPU synthetic Stage 1. Date (UTC): 2026-11-04 (2026-11-03 lane date in Eastern time). Base commit: 29907e5fbe648b9ec246cebf9d757511a751fca2.

## Hypothesis
On the small synthetic integer model, nonzero one-neuron residual steering can change greedy replies while some changed replies still satisfy the repository's default clipped-gap policy; exact match accepts a steered reply if and only if its covered tokens are also stock greedy tokens.

## Metric
For five predeclared prompt seeds, measure changed-token count and acceptance of a four-token autoregressive reply at signed doses 0, +/-0.05, +/-0.1, +/-0.2, +/-0.5, +/-0.8, +/-1.0. Normalize the selected layer's down-projection column to unit Euclidean norm and multiply by signed dose times the median residual norm at that layer on the stock prompt. Round the intervention to integers at the residual boundary. Select layer 0, shared MLP neuron 0 without outcome-based selection. Use the small synthetic block weights and configuration of examples/accepted-proof, not a separately invented neural net.

Measure three parameter sets: stock; projection of coordinate direction e_0 out of every Wo, Wd and Wdr output and the embedding (synthetic analogue, not a refusal direction, exact integer projection); and doubling layer-0 Wd column 0, saturating to the allowed [-4096,4095] range if needed (a weight-steered surrogate, NOT mathematically identical to constant runtime residual injection). Report reproducible SHA-256 artifact fingerprints separately from FlashProve commitment IDs.

Primary requested proof measurements: three fresh cp_commit IDs, independently regenerated from public weights and a published commitment seed, own-ID acceptance and wrong-stock-ID rejection, and fresh proofs of runtime-steered replies checked by real cp_verify. If CPU-only execution cannot produce fresh commitments/proofs, mark these NOT MEASURED and the overall deliverable KILLED, rather than substitute SHA hashes or Python score decisions. Existing stored proofs may be used only as distinctly labeled verifier binding controls. Record exit codes, full last lines, covered ranges and result-v1.

## Acceptance threshold
Success requires all 15 fresh variant commitments (3 variants x 5 runs) to reproduce, all own-ID proofs to accept, all changed-ID proofs to reject, zero stock false rejections, and at least one changed runtime-steered reply accepted under clipped-gap but rejected under exact match through fresh real proofs. Otherwise FAIL or KILLED, with sub-results stated separately.

For scorer-only exploratory results use fixed repository stored clipped-gap defaults: C=9244130, theta=323343, cap=1, s=16, sh=8, sT=4, F=24. Strict defaults: C=256, theta=256, cap=0. No CLIPPED* result file exists in shared planning at registration. No threshold tuning after outcomes. A score-only curve is not a verifier dose-detection curve.

## Kill criterion
No GPU, paid API or real-weight download. Stop full proof experiment immediately if fresh cp_commit/cp_prove require CUDA/H100, or after 90 minutes CPU/wall execution. Publish the negative prerequisite result and any clearly separated CPU measurements. Stop scoring if interventions overflow or violate integer-model invariants, reporting each failure rather than excluding it. No proof-system source changes to force an outcome.

## Runs
Five independent prompt seeds: 1103, 1104, 1105, 1106, 1107. Fixed stock weight-generator seed 31, matching the stored small baseline. Prompt length 8; reply length 4; uniform vocabulary sampling with NumPy PCG64. These are prompt replicates, not five independently trained models. Zero dose first, then increasing magnitude, negative before positive, for each seed. No warmup exclusion or outcome exclusion. Report n, median, sample SD, minimum and maximum for scalar summaries. Repeated verifier controls are deterministic checks, not independent cryptographic trials. A fresh artifact reconstruction in a separate process is a reproducibility check, not independent-researcher replication.

## Prior art
- DiFR / Token-DiFR, https://arxiv.org/abs/2511.20621, is the source of the clipped-gap idea; its cited experiments concern quantization, caches, seeds and temperature, not evidence for this steering experiment.
- CommitLLM, https://github.com/lambdaclass/CommitLLM, provides adjacent open-weight commit-and-audit work with a different protocol.
- Tinfoil Modelwrap, https://tinfoil.sh/blog/2026-02-03-proving-model-identity, binds weights within a TEE-based system, not this proof path.
- Abliteration artifact audit, https://arxiv.org/abs/2607.01854, is statistical artifact-level auditing, not a cryptographic inference proof.
- Arditi et al., https://arxiv.org/abs/2406.11717, motivates direction projection; no refusal direction or behavior exists in this synthetic fixture.
- https://github.com/lyramakesmusic/neuron-explorer motivates a normalized down-column residual intervention, with doses expressed as fractions of median residual norm. This lane independently implements the algebra, not a real Qwen neuron/persona claim.

Framing is measured on FlashProve, never a first-in-literature claim. Qwen3.5-4B support and real-model claims are outside scope; its 24 linear DeltaNet plus 8 full-attention layers require architecture work.

## Amendments
(empty at registration)
