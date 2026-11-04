# RESULTS: 20261104-38-swap-at-verifier

Part of #38. **Honest-prover path only**: every decision below comes from the honest `cp_prove` (which refuses
to prove a reply outside the limits) followed, where a proof was written, by `cp_verify`. A cheating prover
that submits a forged out-of-limits proof is not tested here. Measured on one rented H100 (synthetic weights
only), unreplicated.

Every decision is a real `cp_prove` outcome on a fresh commitment and, where a proof was written, a whole
`cp_verify` call with `-policy`. `numbers.json` holds every request. `intervals.json` (written by
`intervals.py` from `numbers.json` and `requests.json`, CPU, standard library) holds the 95% intervals, the
decision breakdown and the score margins quoted below. `h100/<shipped45|fit45>/` holds the prover logs,
`results.tsv`, `result-v1.txt`, the commitment ID and proof digests (no proof files). The replies are #45's
committed raw replies (seed 2026, held-out half), 16 per class drawn with random.Random(2026001), with no new
decoding. In #45's raw data the 4-swap classes (fp2nd-4, rand-4, int2nd-4) have 63 scored replies, not 64;
the other classes have 64. The 16 are drawn from whatever is there.

## Verdict vs PREREG

| clause | threshold | result | verdict |
|---|---|---|---|
| agreement | Python score = prover+verifier decision on all 256 requests | 256 of 256 agree. Breakdown: **89 cp_verify accepts** (45 shipped, 44 fit) + **167 refusals by the honest cp_prove** (`.failed`, 83 shipped, 84 fit) + **0 cp_verify rejections** | **PASS** (honest-prover path) |
| honest control | >= 15/16 accepted under shipped | 16/16, 95% CI [0.79, 1.00] | **PASS** |
| soundness flag | any cp_verify acceptance of a score-failing reply | 0, but **vacuous for a cheating prover**: all 167 score-failing replies were refused by the honest prover, so cp_verify never saw a score-failing proof | not exercised |

The agreement result therefore says two things: the honest prover's limit check refused exactly the replies
the Python score fails (167 of 167), and cp_verify accepted exactly the proofs the score passes (89 of 89).
It does not show that cp_verify's own limit check rejects an out-of-limits proof. That needs a prover built to
skip its check, or a crafted proof with an over-limit cost vector (follow-up under #38).

## Counts (n = 16 per class; accepted / refused by the honest prover; cp_verify rejected none)

95% intervals are exact (Clopper-Pearson) two-sided intervals of accepted / 16, from `intervals.json`.
One seed, one draw of 16 per class.

| class | shipped (C 9,244,130, theta 323,343, cap 1) | fit (C 5,178,975, theta 203,143, cap 1) | #45 score, same 16, shipped |
|---|---|---|---|
| honest (held-out) | 16 / 0, [0.79, 1.00] | 15 / 1, [0.70, 1.00] | 16 |
| fp2nd-1-redecode (1 swap, then continue) | **15** / 1, [0.70, 1.00] | **15** / 1, [0.70, 1.00] | 15 |
| rand-1-redecode (1 random swap, then continue) | **13** / 3, [0.54, 0.96] | **13** / 3, [0.54, 0.96] | 13 |
| rand-1 (1 random token, no continuation) | 1 / 15, [0.00, 0.30] | 1 / 15, [0.00, 0.30] | 1 |
| fp2nd-4, rand-4, int2nd-4 (4 swaps) | 0 / 16 each, [0.00, 0.21] | 0 / 16 each, [0.00, 0.21] | 0 each |
| rand-reply | 0 / 16, [0.00, 0.21] | 0 / 16, [0.00, 0.21] | 0 |

The last column is the Python score on the same 16 replies. It agrees with the middle columns by
construction (that is the agreement result above), so it is not an independent check of #45.

So on the honest-prover path, one swap followed by greedy continuation was proved and accepted 15/16 and 13/16
times under the shipped limits on this sample. Against #45's scored medians for these classes over 5 seeds
(fp2nd-1-redecode 95 %, rand-1-redecode 91 %, shipped limits): 15/16 = 94 % sits inside its interval of
[0.70, 1.00]; 13/16 = 81 % is below #45's 91 % median, and its interval [0.54, 0.96] neither confirms nor
rules out #45's band. Under the fit point the counts are identical to shipped for both redecode classes;
with n = 16 per cell this sample cannot separate the two policies, so no comparison between them is
claimed. Four or more swaps and whole random replies got no proof at all (0/16 each, upper bound 0.21).

## Margins (from `intervals.json`, #45's committed cost vectors)

- **honest_75 is the single row that differs between the two policies**, and so the whole 16/16 vs 15/16
  honest difference. Under shipped its clipped mean sits 5.0 % under theta with 0 positions over C (its
  largest cost, 5,693,380, is under shipped C). Under fit that cost is over fit C (1 position, allowed by
  cap = 1) and the clipped mean is 43 % over fit theta, so the prover refuses it on theta.
- **cap = 1 carries the redecode class.** Every accepted rand-1-redecode reply (13 of 13, both policies) has
  exactly 1 position over C, and sits 7.6 to 10.6 % under theta (shipped) or 15.4 to 20.2 % (fit). Under
  cap = 0 the score would refuse all 13. For fp2nd-1-redecode, 3 of 15 (shipped) and 5 of 15 (fit) accepted
  replies use the one allowed position over C; the rest are under C everywhere. rand-1's one accept also
  uses it.
- The `above-clip=1` that cp_verify prints on every accepted line is the policy-derived upper bound on such
  positions (cp_verify.cpp, `aboveClip`), not a count measured on the reply. The counts above come from the
  cost vectors.

## What this does and does not show

- On the honest-prover path the Python scorer predicted the real system exactly on these 256 requests. For
  these classes #45's score rates can be read as honest-prover+verifier rates on this fixture, within the
  n = 16 intervals above.
- Every reply outside the limits was **refused by the honest prover** (`.failed`). None reached cp_verify,
  so the verifier's limit check was never exercised on an out-of-limits proof. A cheating prover that forges
  such a proof is not tested here, and that is the case the limits are meant to catch at the verifier.
- One synthetic small model, one seed, 16 replies per class. Not replicated.
- The fit commitment uses a copy of target_small_f2_gap/policy.txt with two lines changed (`C`, `theta`; `cap`
  is 1 in both) (`fit-policy.txt`). Its KL.bin and layout.txt are the kit's.

## Reproduce

`python experiments/20261104-38-swap-at-verifier/gen_requests.py OUT` (CPU, no packages beyond the standard
library) writes the 128 requests and the fit policy. On one H100: `run_small.sh` (this folder) for each
policy, then `python analyze.py OUT/requests.json shipped/results.tsv fit/results.tsv numbers.json`, then
`python intervals.py numbers.json requests.json intervals.json` (CPU).
