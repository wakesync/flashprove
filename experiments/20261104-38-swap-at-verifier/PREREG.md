# PREREG: 20261104-38-swap-at-verifier
Issue: #38. Lane: GPU rental 2, workload 3. Date (UTC): 2026-11-04 15:00. Base commit: ff68a98b (origin/main).

Follows experiments/20261103-6-clipped-gap-rejection (PR #45, merged), whose rates are Python scores.
This run asks the real prover and verifier on one H100. Synthetic weights only.

## Hypothesis
On target_small_f2_gap, for attacked replies built by the #45 harness, the count of replies that the
honest cp_prove proves and cp_verify accepts under the shipped limits equals the count that #45's
Python scorer marks as meeting those limits (agreement on every request), so #45's score rates are the
verifier's rates for these classes: in particular one swap then greedy continuation (`fp2nd-1-redecode`,
`rand-1-redecode`) is accepted by cp_verify at roughly #45's 91-95 % median.

## Metric
Per (class, policy): accepted = cp_prove wrote `<name>.proof` and a whole cp_verify call against the
fresh commitment's ID with `-policy <policy>` exits 0 with last line `WITHIN LIMITS: ...`; refused =
cp_prove wrote `<name>.failed`; rejected = a proof exists and cp_verify exits non-zero. Rate =
accepted / requests in the class. Compared request by request with the Python score
(integrations/vllm/integer_model rule, as #45 analyze.py) under the same limits.

Policies, each a separate fresh commitment (the limits are lines of policy.txt, fixed at cp_commit):
- shipped: target_small_f2_gap as is (C=9244130 theta=323343 cap=1).
- fit: the same configuration with C/theta/cap replaced by #45's fit_limits.py rule on seed 2026
  (C=5178975 theta=203143 cap=1, numbers.json per_seed[0].fit_limits_rule).

Requests come from #45's committed raw files (research/acceptance/clipped-gap/raw/, seed 2026 held-out
half, no new decoding): classes `fp2nd-1-redecode`, `rand-1-redecode` (1 swap then continue), `fp2nd-4`,
`rand-4`, `int2nd-4` (4 swaps), `rand-1` (random token, no continuation), `rand-reply`, plus `honest`
(held-out control). A random 16 of each class's 64 replies (random.Random(2026001), drawn now, before
any proof), so 8 x 16 = 128 requests per policy. Prompt 16 tokens, reply up to 32, zeros to T=64,
r = 15, e = 15 + len(reply), as cp_verify_spot.py's request().

## Acceptance threshold
Fixed now.
- Agreement: PASS if Python score and prover+verifier decision agree on all 256 requests. Each
  disagreement is listed with its costs.
- Redecode at the verifier: reported as accepted / 16 per class per policy, with the #45 scored rate
  for the same 16 replies beside it. No pass bar on the rate itself (it is the measurement).
- Honest control: >= 15/16 accepted under shipped (matches #45's held-out FRR band).
- Any acceptance by cp_verify of a reply whose score fails the limits is a soundness finding and is
  reported first.

## Kill criterion
Caps from the brief: $60 all-in rental, 6 GPU-hours, hard deadline 17:18 UTC. Stop this workload at
30 GPU-minutes on its box. cp_commit or build failure: report and stop. No prover/verifier source
changes, no limit tuning after outcomes.

## Runs
One seed (2026) of #45's five, 16 replies per class, 8 classes, 2 policies = 256 requests. One
commitment per policy. Requests in cp_prove batches of at most 64. Deterministic cp_verify calls are not
independent trials. Rates per class: n = 16; no claim from overlapping intervals. Only seed 2026 because
the fit point is that seed's.

## Prior art
#45 (scores, stored-proof binding spot checks); DiFR / Token-DiFR (https://arxiv.org/abs/2511.20621);
TOPLOC (https://arxiv.org/abs/2501.16007) for tolerance-based inference checks. New here: real
cp_verify rejection counts under the clipped-gap limits for these attack classes.

## Amendments
(empty at registration)
