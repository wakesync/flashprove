# PREREG: 20261104-36-steering-real-proofs
Issue: #36. Lane: GPU rental 2, workload 2. Date (UTC): 2026-11-04 14:58. Base commit: ff68a98b (origin/main).

Follows experiments/20261103-model-identity (PR #46, merged), whose proof part was KILLED on CPU. This
run makes the fresh commitments and proofs on one H100. Synthetic weights only.

## Hypothesis
On the small synthetic model, runtime-steered replies (one-neuron residual injection, the #46 recipe)
that change at least one covered token are refused by the honest prover or rejected by cp_verify
against the STOCK commitment under exact match, while under the shipped clipped-gap policy some
changed steered replies can get a proof that cp_verify accepts (WITHIN LIMITS). Direction: the
smallest dose at which every changed reply is refused is the same for strict and lenient on 4-token
replies (as #46's scores said) and lower for strict than lenient on 16-token replies.

## Metric
Per (policy, signed dose, prompt seed, reply length): the honest prover's outcome on the request
(`.proof` or `.failed`), and for each proof the exit code and last line of a whole `cp_verify` call
against the stock commitment ID, stock ivk, the request built from the steered reply, and the policy
named with `-policy`. Counted as accepted only if cp_verify exits 0 (`YES` or `WITHIN LIMITS`).
Also the Python integer-model score of the same reply (run.py's rule), to count agreement between
score and the real prover/verifier.

Commitments, both fresh on the H100 with `cp_commit -weights made-up-blocks -M 1`:
- S: configuration prover/examples/target_small_f2_roomy (exact match, C=256 theta=256 cap=0).
- G: configuration prover/examples/target_small_f2_gap (clipped-gap C=9244130 theta=323343 cap=1).
Each steered reply is generated on the CPU by the integer model of that same configuration (same
weights, that configuration's KL.bin), so a lenient reply is scored and proved under one set of scales.

Steering: experiments/20261103-model-identity/run.py RuntimeSteered unchanged in algebra (layer 0,
shared down column 0, coefficient dose x median stock residual norm / column norm, rounded at the
residual boundary). Signed doses 0, +/-0.05, +/-0.2, +/-1.0 (the brief's minimum grid).

Requests: prompt of 8 tokens (NumPy PCG64 seeds 1103..1107, as #46), reply of 4 tokens (primary,
as #46) and 16 tokens (secondary), zeros to T=64, r = len(prompt) - 1, e = len(prompt) + len(reply) - 1,
so the proof covers the reply tokens.

## Acceptance threshold
Fixed now.
- Strict (S): PASS if 0 changed steered replies are accepted by cp_verify and every unchanged reply
  (dose 0 and any dose that did not change a token) gets a proof that cp_verify accepts.
- Lenient (G): reported as counts of changed replies accepted / proved / refused per dose; the
  hypothesis' lenient half holds if at least one changed steered reply is accepted WITHIN LIMITS
  (it may hold at 16 tokens only). If none is accepted, that is a valid negative and is reported.
- Score agreement: the Python score's accept/reject equals the prover+verifier decision on every
  request, else each disagreement is listed (a disagreement is a finding, not excluded).
- Stock false rejections: dose-0 replies must be proved and accepted 5/5 per policy and length.

## Kill criterion
Caps from the brief: $60 all-in rental, 6 GPU-hours, hard deadline 17:18 UTC today. Stop this
workload at 30 GPU-minutes on its box. If cp_commit or the build fails, report and stop. No proof-system
source changes, no threshold tuning.

## Runs
5 prompt seeds x 7 signed doses x 2 reply lengths x 2 policies = 140 requests, plus dose-0 repeats as
the controls. Prompt replicates, not independent models. No warmup exclusion. Requests go to cp_prove in
batches of at most 64 (`slots 64`). Each cp_verify call is deterministic, not an independent trial.
Report per dose n, counts, and for changed-token counts median, SD, min, max.

## Prior art
experiments/20261103-model-identity (PR #46: CPU scores, stored-proof binding controls only);
DiFR / Token-DiFR (https://arxiv.org/abs/2511.20621) for clipped-gap acceptance; CommitLLM
(https://github.com/lambdaclass/CommitLLM); neuron-explorer relative-dose steering
(https://github.com/lyramakesmusic/neuron-explorer). What is new: real cp_commit / cp_prove / cp_verify
decisions on steered replies of this fork's synthetic model. No first-in-literature claim.

## Amendments
(empty at registration)
