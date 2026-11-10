# RESULTS: Q4 sampled audit (U2)

Sampled whole-request auditing is a credible direction for detecting repeated invalid outputs, not proof of physical model execution.
The outer challenge must be unpredictable until every eligible response is immutably committed in an independently complete log.
A 1% request sample is a 1% chance to catch one invalid request, not 99% confidence in every request.
Layer/token sampling additionally needs authenticated weights, trace boundaries and state dependencies, and has non-negligible all-traffic commitment cost.
The simulation passed its registered sampler checks; no production protocol, Qwen proof or GPU cost was measured.

## U2: verdict and provenance

**PASS, simulation only, unreplicated.** All 91 scenario/sample-size cells, each with five seeds and 10000 windows per seed, passed the registered per-seed threshold `6*sqrt(p*(1-p)/10000)+1/10000`; exact zero/one cases agreed exactly. This is 455 seeded cell-runs and 4,550,000 simulated windows, including deterministic endpoints. The disjoint N=7/K=3/m=2 exhaustive fixture also passed (21 subsets). The simulator uses random subset selection and intersection, independently of the combinatorial reference formula. Full-population selection has only one possible subset.

PREREG first commit: `237351c`. Simulator committed before running: `88084423fb5ca03c3666f52e43100ae0f3b34838`. Main evidence base: `14bc10e395b248583509ae33da3e1ae65293bb6f`. One registered suite run, no excluded observations, no warmups, no model or cryptographic proof calls. Script returned exit 0 within its 180-second timeout. Wall time and RSS were not measured as experiment outcomes. Hardware/toolchain/seeds/hash receipts: [ENV.json](ENV.json). Immutable raw counts, all seeds, exact probabilities and thresholds: [runs/registered.json](runs/registered.json).

## U2: representative outcomes

All probabilities below condition on a fixed invalid statement being rejected with probability one. Changed weights or a different serving engine do not establish that condition.

| Population / attack | Fraction audited | Exact coverage | Simulation median (five seeds) | SD | Min / max |
|---|---|---|---|---|---|
| 1000 requests, 100 invalid | 1% (10) | 65.3072% | 65.46% | 0.1927 percentage points | 65.07% / 65.56% |
| 1000 requests, 10 invalid | 1% (10) | 9.6032% | 9.66% | 0.4190 percentage points | 9.52% / 10.55% |
| 1000 requests, one invalid | 1% (10) | 1% | 0.98% | 0.1635 percentage points | 0.71% / 1.12% |
| Adaptive leaked challenge, cheats only off sample | any registered fraction below 100% | 0% | 0% | 0 | 0% / 0% |

At full coverage the leaked-challenge adversary has no unsampled request to attack; its zero detections are vacuous, not a successful full-coverage attack. See [TABLES.md](../../research/sampled-audit/TABLES.md) for all 91 cells, including whole-model, ablated-layer, quantization, blind predictor, layers 17..51, and token strategies. These are simulated planted violation patterns, not experiments on those models. Exact finite-population calculations and equal-unit variable-work fractions are labeled as calculations, not measurements. No cost/performance number is imported from another lane.

## U2: what this changes, and what it does not

The experiment validates a concrete coverage calculator against simulation. It makes visible the weak detection of rare targeted failures and the complete failure under leaked selection. It establishes neither semantic distinguishability of changed weights nor the soundness/security of FlashProve programs. The [design](../../research/sampled-audit/README.md) distinguishes cheap whole-response receipts from potentially expensive precommitted traces, and lists the verifier-held inputs and current-main capabilities.

Production prerequisites: a useful full-model proof relation with established fidelity, trusted weight/config binding, complete client/ingress receipts, external challenge generation, proof-to-receipt checking, retention/recomputation and timeout policy, hardened security settings, and measured costs. Independent per-layer proofs further require Q2 weight binding and Q6 state/dependency linkage. Current main's [M3 design results](../20261109-32-qwen-m3-design/RESULTS.md) explicitly count/extrapolate rather than build the full proof.

## U2: deviations and next registration

No deviations from registered arms, seeds, trial counts or thresholds. The report renderer was added after the run; it only reads immutable raw data. Endpoint selection uses the unique full-population subset without an unnecessary random permutation. No resource-limit kill and no approval holds occurred. The design and cost equations are desk analysis, not newly measured numbers.

Next experiment: preregister an actual small whole-request audit with a client-owned log and supported proof relation, including honest controls, post-challenge rewrite, omission, replay, range reduction, selective timeout and leaked-selection attacks. Include a cheaper engine's output that satisfies the pinned relation as an expected accept. Measure receipt overhead, retention/recomputation and batch costs separately; do not infer them from sample fractions.
