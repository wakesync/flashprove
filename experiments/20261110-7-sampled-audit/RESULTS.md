# RESULTS: Q4 sampled audit (U2)

Sampled whole-request auditing is a credible direction for detecting repeated invalid outputs, not proof of physical model execution.
The outer challenge must be unpredictable until every eligible response is immutably committed in an independently complete log.
A 1% request sample is a 1% chance to catch one invalid request, not 99% confidence in every request.
Layer/token sampling additionally needs authenticated weights, trace boundaries and state dependencies, plus an all-traffic trace commitment whose cost does not shrink with the sample fraction (its size was not measured or bounded).
The simulation passed its registered sampler checks; no production protocol, Qwen proof or GPU cost was measured.

## U2: verdict and provenance

**PASS, simulation only, unreplicated.** All 91 scenario/sample-size cells, each with five seeds and 10000 windows per seed, passed the registered per-seed threshold `6*sqrt(p*(1-p)/10000)+1/10000`; exact zero/one cases agreed exactly. This is 455 seeded cell-runs and 4,550,000 simulated windows, including deterministic endpoints. Only **45 cells are random-simulated** (exact probability strictly between 0 and 1, 225 seed-runs within the bound); these are the cells that test the sampler. The other **46 are deterministic**: 40 have exact probability 1 and the 6 leaked-challenge cells are 0 by construction. The disjoint N=7/K=3/m=2 exhaustive fixture also passed (21 subsets). The simulator uses random subset selection and intersection, independently of the combinatorial reference formula. Full-population selection has only one possible subset.

PREREG first commit: `237351c`. Simulator committed before running: `88084423fb5ca03c3666f52e43100ae0f3b34838`. Main evidence base: `14bc10e395b248583509ae33da3e1ae65293bb6f`. One registered suite run, no excluded observations, no warmups, no model or cryptographic proof calls. Script returned exit 0 within its 180-second timeout. Wall time and RSS were not measured as experiment outcomes. Hardware/toolchain/seeds/hash receipts: [ENV.json](ENV.json). Immutable raw counts, all seeds, exact probabilities and thresholds: [runs/registered.json](runs/registered.json).

## U2: representative outcomes

All probabilities below condition on a fixed invalid statement being rejected with probability one. Changed weights or a different serving engine do not establish that condition.

| Population / attack | Fraction audited | Exact coverage | Simulation median (five seeds) | SD | Min / max |
|---|---|---|---|---|---|
| 1000 requests, 100 invalid | 1% (10) | 65.3072% | 65.46% | 0.1927 percentage points | 65.07% / 65.56% |
| 1000 requests, 10 invalid | 1% (10) | 9.6032% | 9.66% | 0.4190 percentage points | 9.52% / 10.55% |
| 1000 requests, one invalid | 1% (10) | 1% | 0.98% | 0.1635 percentage points | 0.71% / 1.12% |
| Adaptive leaked challenge, cheats only off sample (0 by construction, negative control) | any registered fraction below 100% | 0% | 0% (identity) | 0 | 0% / 0% |

The leaked-challenge row is **zero by construction**, not simulated detection: the simulator sets the cheated set to the complement of the selected set, so no selected request can be invalid. It is a negative control that shows what leakage does, not evidence about a sampler. At full coverage the leaked-challenge adversary has no unsampled request to attack; its zero detections are vacuous, not a successful full-coverage attack. See [TABLES.md](../../research/sampled-audit/TABLES.md) for all 91 cells, including whole-model, ablated-layer, quantization, blind predictor, layers 17..51, and token strategies. These are simulated planted violation patterns, not experiments on those models. Exact finite-population calculations and equal-unit variable-work fractions are labeled as calculations, not measurements. No cost/performance number is imported from another lane.

## U2: what this changes, and what it does not

The experiment validates a concrete coverage calculator against simulation. It makes visible the weak detection of rare targeted failures and the complete failure under leaked selection. It establishes neither semantic distinguishability of changed weights nor the soundness/security of FlashProve programs. Coverage is per epoch, conditional on that epoch's invalid count fixed before its challenge. Multiplying per-epoch survival probabilities, each with its own epoch's count, gives lifetime coverage only for a count schedule fixed independently of audit outcomes; an average count never goes into the formula. For a cheater that adapts its count to earlier audit outcomes, only the per-epoch statement conditional on the history before each challenge holds, and lifetime coverage needs an analysis of the adaptive policy (see the design's detection section). On main, 0 of 96 stored honest replies from a stock floating-point engine met exact match ([docs/protocol.md:45](https://github.com/wakesync/flashprove/blob/14bc10e395b248583509ae33da3e1ae65293bb6f/docs/protocol.md#L45)), so a whole-request audit under exact match as written would flag honest float-served traffic. Using it needs integer-model serving or a declared tolerance relation with a measured honest-pass rate; neither is established here. The [design](../../research/sampled-audit/README.md) distinguishes cheap whole-response receipts from potentially expensive precommitted traces, and lists the verifier-held inputs and current-main capabilities.

Production prerequisites: a useful full-model proof relation with established fidelity, trusted weight/config binding, complete client/ingress receipts (audit population = every reply that delivered tokens, whatever its status or finish reason; epochs assigned by ingress sequence index, not completion time), external challenge generation, proof-to-receipt checking, retention/recomputation and timeout policy, hardened security settings, and measured costs. Independent per-layer proofs further require Q2 weight binding and Q6 state/dependency linkage. Current main's [M3 design results](../20261109-32-qwen-m3-design/RESULTS.md) explicitly count/extrapolate rather than build the full proof.

## U2: deviations and next registration

No deviations from registered arms, seeds, trial counts or thresholds. The report renderer was added after the run; it only reads immutable raw data. Endpoint selection uses the unique full-population subset without an unnecessary random permutation. No resource-limit kill and no approval holds occurred. The registered kill criterion names 512 MiB RSS, but the registered run did not measure RSS (ENV `peak_rss_measured: false`); a reviewer's rerun at the registered seeds peaked at 18.5 MiB ([review comment](https://github.com/wakesync/flashprove/pull/84#issuecomment-6778822702), a reviewer's descriptive number, not a result of this PR). The design and cost equations are desk analysis, not newly measured numbers.

Next experiment: preregister an actual small whole-request audit with a client-owned log and supported proof relation, including honest controls, post-challenge rewrite, omission, replay, range reduction, selective timeout, a delivered reply mislabelled as error or cancelled, a late answer moved across an epoch boundary, and leaked-selection attacks. Include a cheaper engine's output that satisfies the pinned relation as an expected accept. Measure receipt overhead, retention/recomputation and batch costs separately; do not infer them from sample fractions.
