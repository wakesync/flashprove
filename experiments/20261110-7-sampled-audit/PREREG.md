# PREREG: 20261110-7-sampled-audit
Issue: #7 (threat-model cross-reference #6). Lane: Q4 sampled-audit. Date (UTC): 2026-11-10. Base commit: 14bc10e395b248583509ae33da3e1ae65293bb6f.

Use case: U2. This desk study measures sampling coverage, not proof soundness, inference fidelity, GPU speed, or production attack success.

## Hypothesis
With a fixed pre-challenge set of invalid units and a uniform fixed-size sample without replacement, simulated detection agrees with the hypergeometric formula, while fully leaked challenges allow a selective cheater to evade all audits below full coverage.

## Metric
Probability of at least one invalid unit sampled per audit window. Exact reference: 1 - choose(N-K,m)/choose(N,m). Report sampled fraction m/N, and five-seed median, sample SD and min/max of simulated rates. Cost fractions are analytic equal-cost-unit accounting, not wall-time measurements. Detection assumes a sound proof bound to the committed invalid statement, with conditional rejection probability one. It is NOT assumed that a changed model or weight necessarily violates that statement.

## Acceptance threshold
Every per-seed empirical probability must differ from its exact reference by at most 6*sqrt(p*(1-p)/10000) + 1/10000. Deterministic zero/one cases must match exactly. An independent combinatorial check on a small fixture must agree within 1e-12. Passing validates the sampler only, not a deployable audit protocol.

## Kill criterion
Single-threaded standard-library Python only, affinity cores 12-15, below 512 MiB RSS. Stop a simulation after 180 seconds elapsed using timeout. No GPU, model weights, provider requests, proof build or paid APIs. Hard lane stop: 2026-11-10 23:00 UTC. Publish partial or negative results if limits or assertions fail. No heavy job is planned; any unplanned heavy work requires a new registration and the shared heavy-job gate.

## Runs
Five independent committed simulation seeds: 11100401, 11100402, 11100403, 11100404, 11100405. 10000 independent windows per seed per scenario and sample size. No warmup and no exclusions; not a performance experiment. Fixed ordered arms, separate deterministically derived RNG streams per scenario/size/seed.

Request window N=1000, m in {1,5,10,50,100}: swap all K=1000, swap 10% K=100, swap 1% K=10, targeted single request K=1, layers-17-through-51 substitution on all requests K=1000, quantization on all requests K=1000, blind predicted-unsampled cheating on a precommitted 10% K=100, and leaked-challenge evasion K chosen only outside the sample (zero detection). Add full-coverage endpoint m=1000. The layer/quantization request arms assume every affected request contains a provable violation.

Layer window N=64, m in {1,2,4,8,16,32,64}: planted violations at all 64 layers, layers 17..51 inclusive (35 layers, zero-based indexing), eight quantized layers (0..7), or one layer. These are conditional structural coverage examples, not measurements on a model.

Token window N=256, m in {1,4,16,64,256}: planted violations at all tokens, 26 tokens (first 26), or one token. No inference about how errors propagate across tokens is made.

Debugging is allowed only on a disjoint N=7, K=3, m=2 fixture and algebraic endpoints, never on any registered suite arm before the registered run. Unit tests may enumerate the disjoint fixture. Raw run JSON is immutable once committed. Reproduction writes a new output path.

## Prior art
This uses elementary finite-population auditing (hypergeometric sampling), commit-before-challenge, Merkle authentication and verifier-owned statements, not a new cryptographic construction. Repository evidence only: research/security/threat-model/THREAT-MODEL.md; experiments/20261109-34-qwen-state-commit/RESULTS.md; research/ports/qwen3.8-27b/FEASIBILITY.md, all at the base main commit. No external benchmark or unmerged lane result is evidence. The contribution is a concrete U2 protocol and explicit separation between sample coverage, relation rejection, and execution provenance.

## Amendments
