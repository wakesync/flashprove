# RESULTS: 20261104-38-swap-at-verifier

Part of #38. Measured on one rented H100 (synthetic weights only), unreplicated. Every decision is a real
`cp_prove` outcome on a fresh commitment and, where a proof was written, a whole `cp_verify` call with
`-policy`. `numbers.json` holds every request. `h100/<shipped45|fit45>/` holds the prover logs, `results.tsv`,
`result-v1.txt`, the commitment ID and proof digests (no proof files). The replies are #45's committed raw
replies (seed 2026, held-out half), 16 per class drawn with random.Random(2026001), with no new decoding.

## Verdict vs PREREG

| clause | threshold | result | verdict |
|---|---|---|---|
| agreement | Python score = prover+verifier decision on all 256 requests | 256 of 256 agree | **PASS** |
| honest control | >= 15/16 accepted under shipped | 16/16 | **PASS** |
| soundness flag | any cp_verify acceptance of a score-failing reply | 0 | none found |

## Counts (n = 16 per class; accepted / refused by the prover; no proof was rejected by cp_verify)

| class | shipped (C 9,244,130, theta 323,343, cap 1) | fit (C 5,178,975, theta 203,143, cap 1) | #45 score, same 16, shipped |
|---|---|---|---|
| honest (held-out) | 16 / 0 | 15 / 1 | 16 |
| fp2nd-1-redecode (1 swap, then continue) | **15** / 1 | **15** / 1 | 15 |
| rand-1-redecode (1 random swap, then continue) | **13** / 3 | **13** / 3 | 13 |
| rand-1 (1 random token, no continuation) | 1 / 15 | 1 / 15 | 1 |
| fp2nd-4, rand-4, int2nd-4 (4 swaps) | 0 / 16 each | 0 / 16 each | 0 each |
| rand-reply | 0 / 16 | 0 / 16 | 0 |

So at the real prover and verifier, one swap followed by greedy continuation passes the shipped limits
15/16 and 13/16 times on this sample, and the fit_limits.py point does no better. #45's
91 to 95 % scored median for this class is consistent (16-reply samples, one seed, no claim from overlap).
Four or more swaps and whole random replies get no proof at all.

## What this does and does not show

- The Python scorer predicted the real system exactly on these 256 requests. For these classes #45's score
  rates can be read as prover+verifier rates on this fixture.
- Every reply outside the limits was **refused by the honest prover** (`.failed`). None reached cp_verify, so
  the verifier's limit check was never exercised on an out-of-limits proof. A cheating prover that forges such
  a proof is not tested here, and that is the case the limits are meant to catch at the verifier.
- One synthetic small model, one seed, 16 replies per class. Not replicated.
- The fit commitment uses a copy of target_small_f2_gap/policy.txt with three lines changed (`fit-policy.txt`).
  Its KL.bin and layout.txt are the kit's.

## Reproduce

`python experiments/20261104-38-swap-at-verifier/gen_requests.py OUT` (CPU, no packages beyond the standard
library) writes the 128 requests and the fit policy. On one H100: `run_small.sh` (this folder) for each
policy, then `python analyze.py OUT/requests.json shipped/results.tsv fit/results.tsv numbers.json`.
