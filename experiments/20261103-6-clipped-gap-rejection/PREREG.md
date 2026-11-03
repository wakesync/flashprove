# PREREG: 20261103-6-clipped-gap-rejection
Issue: #6. Lane: clipped-gap rejection study (CPU only, no GPU). Date (UTC): 2026-11-03T23:45Z. Base commit: 29907e5f.

Weak point attacked: guide/known-limits.md says no run shows the clipped-gap policy's own limits
rejecting anything at a verifier, and the project recommends no limits.

## Hypothesis
On the small synthetic clipped-gap example (prover/examples/target_small_f2_gap, `small_float_pair`),
scored by the integer-model package (not proved), some point of the pre-registered (C, theta, cap) grid
accepts 0 % of the replies in each "gross" attack class (k >= 4 tokens swapped, random tokens,
whole random reply, reply after another prompt) while falsely rejecting at most 5 % of held-out honest
replies; and no grid point accepts 0 % of 1-token second-choice swaps at a false-reject rate of at most
5 %.

## Metric
Per (seed, grid point, class): acceptance rate = replies that meet the limits / replies in the class
whose window passes the integer model's range conditions (a window that fails them gets no proof from
the honest prover and is counted separately as `no_proof`, never as accepted or rejected). False-reject
rate (FRR) = 1 - acceptance rate on held-out honest replies. "Meets" is the rule of
integrations/vllm/integer_model/examples/try_limits.py `meets()`: window = prompt + reply + zeros to T;
costs = logit gap + 2^sh at the reply's positions; sum(min(cost, C)) <= theta * n and #(cost > C) <= cap.
Tool: integer_model package at this commit, CPU, PyTorch 2.9.1 (CPU wheel), transformers 4.57.6.

Honest replies: greedy decode, 32 tokens, of the float32 checkpoint written by `small_float_pair`, run in
bfloat16 on the CPU (as try_limits.py), to 16 random prompt ids; 128 prompts per seed, first 64 = fit
half, last 64 = held-out half. Attack classes, each built from every held-out honest reply:
- `fp2nd-k`: k positions (k = 1, 2, 4, 8, 16) replaced by the float model's second choice at that
  position (no re-decode after the swap; as try_limits.py).
- `int2nd-k`: k positions replaced by the integer model's second choice (the cheapest single-token
  deviation an adversary that knows the weights can make).
- `rand-k`: k positions replaced by a uniformly random other id (end token excluded).
- `rand-reply`: whole reply replaced by uniformly random ids (same length).
- `other-prompt`: the reply after the next held-out reply's prompt.
- `trunc-half`, `trunc-1`: the honest reply cut to its first half / with its last token dropped
  (expected to pass: the policy cannot see truncation; reported as a control, not an attack the policy
  is meant to stop).
Positions and random ids from random.Random(seed * 1000 + class index).

Grid (fixed now): C in {256 (exact), p99, p99.5, p99.9, max} of all fit-half costs, plus 9244130 (shipped);
theta in {256, and the 50/75/90/95/99/100th percentile of fit-half clipped means at that C}, plus 323343;
cap in {0, 1, 2, 4}. Points with theta > C are dropped; theta == C with cap > 0 kept but flagged (the
verifier treats it as no bound on the mean). The shipped point (9244130, 323343, 1) and exact match
(256, 256, 0) always included.

cp_verify (released sources at base commit, built by verifier/build.sh): no GPU, so no new proof can be
made. For each class, one attacked request is built from the stored example's reply.json and checked
with the stored proof of examples/accepted-proof-clipped-gap (label: "binding spot check", which tests
that the proof is bound to its reply, not the policy), and the stored honest set is checked with
`-policy` set to each of three tighter grid points (label: "policy-named", the verifier refuses a policy
that the commitment did not fix). These are recorded as what cp_verify can and cannot say on CPU, not as
policy rejections.

## Acceptance threshold
PASS for the first clause if some grid point has median (over seeds) acceptance 0 % in every gross class
and median FRR <= 5 %. The second clause holds if no grid point has median `fp2nd-1` acceptance 0 % at
median FRR <= 5 %. Both are reported as they come, each with min/max over seeds.

## Kill criterion
Stop and publish the negative if: (a) the float pair cannot be built or the stored reply's four costs
differ from prover/examples/target_small_f2_gap/README.md (446,700, 438,154, 56,748, 470,490), or (b) the
seed-2026 fit (same prompts as try_limits.py) gives limits far from the shipped ones without an
explanation, or (c) wall time exceeds 3 h on this CPU host. No GPU spend under any outcome.

## Runs
5 prompt seeds: 2026 (try_limits.py's own draw), 2027, 2028, 2029, 2030; n = 128 prompts per seed.
Scoring is deterministic given replies, so the spread is over prompt draws. Report median, SD, min, max
over the 5 seeds per (grid point, class). Grid percentiles are refit per seed on that seed's fit half.
Exclusions: replies too short for k swaps are skipped for that k (counted); windows failing range
conditions counted as `no_proof`. No warmup (no timing claim).

## Prior art
Token-DiFR (Karvonen et al., arXiv:2511.20621), which this policy follows: thresholds from an honest
calibration split, reported detection of model/quantization substitution. TOPLOC (arXiv:2501.16007):
locality-sensitive hashes of activations, tolerances set on honest runs. zkML systems (EZKL, zkLLM,
DeepProve, zkAgent) prove exact computation, no tolerance policy. The repository's own try_limits.py
counts (one seed, one fit, 1/4/16 swaps). New here: a (C, theta, cap) sweep with FRR, an
integer-model-second-choice adversary, k = 2/8, truncation and whole-random classes, 5 seeds, and a
record of what cp_verify can and cannot check on CPU.

## Amendments
