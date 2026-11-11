# RESULTS: 20261111-35-conv-history-binding

Issue #35, lane conv35. Verdict against the PREREG threshold: **PASS** (measured, unreplicated). Research toy profile only.

## Summary in plain language

PR #67's conv1d proof let a prover swap in a different carried history (and adjusted inputs) and still prove the same public outputs. This experiment adds a verifier-held tail root: the incoming three history words must open that root, and the segment's last three inputs are published as the next segment's root. With that, the #67 swap is rejected in all 10 seeds, and so are six further hostile variants (12 sub-cases), while honest two-segment chains are accepted 10/10. The kernel and inputs are still free; only carried history continuity is bound.

## Numbers (registered suite, seeds 1..10, one process per seed)

Raw: `runs/suite.jsonl` (release, 200 rows), `runs/suite-ubsan.jsonl` (UBSan, 200 rows, all `stderr_bytes` 0), aggregated in `runs/summary.json`. Builds: `runs/build.json`, `runs/build-ubsan.json` (source commit feaf5c4, clean tree).

| arm / sub-case | expected | release accepted | UBSan accepted | rejected by |
|---|---|---|---|---|
| honest-chain / two-segment | accept | 10/10 | 10/10 | n/a (R0 -> R1 -> R2 handoff matches) |
| honest-unbound / segment-1 | accept | 10/10 | 10/10 | n/a (#67 statement, descriptive) |
| c67-unbound / original | accept (control) | 10/10 | 10/10 | n/a |
| c67-unbound / replacement | accept (control) | 10/10 | 10/10 | n/a: the #67 gap reproduced |
| c67-bound / original-accepted | accept | 10/10 | 10/10 | n/a |
| c67-bound / a: replacement, own opening | reject | 0/10 | 0/10 | outside root check |
| c67-bound / b: replacement witness, original opening, complete malicious proof | reject | 0/10 | 0/10 | in-proof pins (4 violated relations) |
| tail-splice / zero-history statement | reject | 0/10 | 0/10 | outside root check |
| tail-splice / malicious under true opening | reject | 0/10 | 0/10 | in-proof history pins (3) |
| out-tail-lie / honest proof, lying out-opening | reject | 0/10 | 0/10 | proof (out-root in digest + tail pin target) |
| out-tail-lie / malicious, lying out-opening | reject | 0/10 | 0/10 | in-proof tail pin (1) |
| history-reorder / reordered opening | reject | 0/10 | 0/10 | outside root check |
| history-reorder / malicious under true opening | reject | 0/10 | 0/10 | in-proof history pins (2) |
| cross-scale-root / F14 root, F12 statement | reject | 0/10 | 0/10 | outside root check |
| cross-scale-root / F12 proof, F14 statement + F14 root | reject | 0/10 | 0/10 | proof (F-specific circuit and digest) |
| proof-transplant / p1 with s2 | reject | 0/10 | 0/10 | proof (root passes) |
| proof-transplant / p2 with s1 | reject | 0/10 | 0/10 | proof (root passes) |
| segment-replay / s1 again, verifier holds R1 | reject | 0/10 | 0/10 | outside root check |
| segment-replay / s1 relabelled index, matching root supplied | reject | 0/10 | 0/10 | proof (segment index in digest) |

Hostile sub-cases: 14 per seed, 140 per build, 280 total, 0 accepted. Complete malicious proofs: 4 per seed (40 per build), each with every product gate holding and at least one verifier-owned affine target violated; violation counts constant across seeds (`violations` field). No `hostile did not violate relation` or witness self-check failure occurred (every seed exited 0, `not_as_registered` 0). The c67-unbound control accepted both proofs in every seed, so the control is live, not vacuous. `history-reorder` had no palindromic (not-applicable) seed.

Descriptive size/time (release, n=10, shared loaded host, 2 cores; not a performance claim):

| profile | columns | relations | proof bytes median (SD, min-max) | prove s median (SD, min-max) | verify s median (SD, min-max) |
|---|---|---|---|---|---|
| bound, segment 1 | 294 | 579 | 22300 (199, 21904-22496) | 0.00543 (0.00015, 0.00531-0.00567) | 0.0210 (0.0012, 0.0208-0.0246) |
| unbound (#67 statement) | 294 | 573 | 22224 (168, 21960-22464) | 0.00524 (0.00043, 0.00491-0.00636) | 0.0216 (0.0007, 0.0206-0.0229) |

Prove/verify ranges overlap, so no cost difference is claimed. The 6 added relations are the 3 history pins and 3 tail pins. The unbound copy's 294/573 matches #67's committed `experiments/20261109-35-qwen-operators/runs/conv-summary.json`.

## Against the threshold

- honest >= 10/10: 10/10 (release and UBSan).
- c67 construction rejected every run: (a) 0/10 and (b) 0/10 accepted, both builds.
- >= 3 new hostile variants rejected every run: 6 variants (tail-splice, out-tail-lie, history-reorder, cross-scale-root, proof-transplant, segment-replay), 12 sub-cases, 0 accepted.
- c67-unbound control live: 10/10 both proofs accepted.
- No harness failure. **PASS.**

## What is NOT established

- Kernel/tap identity: still prover-chosen; the #67 reviewer's arbitrary-output construction (taps (0,0,0,-S)) is not stopped by this binding.
- Model-input provenance: X[0..3] are free except that X[1..3] become the next segment's history.
- Hiding: history and tail are public openings; no in-circuit hash, no hidden commitment.
- Genesis correctness: the first root is trusted as given.
- Five of the 14 hostile sub-cases are rejected by the verifier's outside SHA-256 comparison, not by the arithmetic proof (table column "rejected by"). That is the design (as in PR #98), but those cases test the statement check, not proof soundness.
- Sampled hostile classes, not exhaustive; rejections are by equation checks with large margin, not by low-probability query rounds; no grinding attempted. Research security 10 bits per round, toy coins, no whole-proof soundness figure.
- One channel, T=4, F=12 only. No multi-channel batch, no integration with #67 binary, PR #98 or `cp_verify`.

## Deviations from PREREG

- PREREG said heavy runs go through the gate if a run exceeds two minutes of CPU; each registered suite took about one minute on 2 cores (`taskset -c 10-11`), so the gate was not used. Recorded in ENV.json.
- `cross-scale-root` gained a second sub-case (F12 proof under an F14 statement and root) and `segment-replay` a second sub-case (relabelled segment index with a matching root supplied). Both were in the code before the registered run and are additional rejections, not substitutes. `proof-transplant` and `cross-scale-root` have no complete-malicious-proof sub-case (they reuse honest proofs under the wrong statement); PREREG said "where feasible".
- Debug (seeds 101..103) ran once before the registered suite, output kept in ignored `work/` and not committed, as registered.
