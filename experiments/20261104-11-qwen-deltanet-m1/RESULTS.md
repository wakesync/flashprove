# RESULTS: 20261104-11-qwen-deltanet-m1

Verdict against the pre-registered threshold: **FAIL** (H1 PASS, H2 PASS, H3 FAIL).
M1 is therefore **NO-GO for M2 as registered** (F = 12, single signed 19-bit limb for state, memory read and delta).
The proof itself works at the real shape. The failure is range headroom: under the heavy-tailed value distribution (R3), delta (and in one seed the memory read) leaves the 2^18 bound at F = 12. The state matrix itself stayed inside 2^18 in every realistic run.

Code and receipt: [research/operators/qwen_deltanet/](../../research/operators/qwen_deltanet/) (`record.py` regenerates everything; `evidence.json` holds commands, exit codes, timings and SHA-256 of every source).
Raw data: `runs/honest.jsonl`, `runs/hostile-seed1.jsonl`, `runs/ranges.json`.

## Kill criterion

Not triggered. The T = 4, 128 x 128 proof was built on the host: product table 2^22 entries (2,338,816 used), peak RSS 6.73 GB (limit 12 GB), total compute about 50 minutes (limit 3 hours).

## H1: honest proofs (threshold 10/10 accepted)

One Gated DeltaNet head, key dim 128, value dim 128, state 128 x 128, T = 4 tokens, F = 12. Inputs: R1 distribution, after a 64-token integer warm-up from S = 0, so S0 is a nonzero realistic state (max |S0| 1,694 to 1,949 in the fixtures). Seeds 1..10, one process each, sequential.

| metric | n | median | SD | min | max |
|---|---|---|---|---|---|
| accepted | 10 | | | **10/10** | |
| prove (s, CPU wall) | 10 | 51.43 | 0.64 | 50.99 | 52.76 |
| prove without first run (s) | 9 | 51.42 | 0.55 | 50.99 | 52.57 |
| verify (s) | 10 | 11.63 | 0.12 | 11.42 | 11.79 |
| proof bytes | 10 | 50,365,792 | 157 | 50,365,456 | 50,365,968 |
| peak RSS (KB) | 10 | 6,728,278 | 68 | 6,728,212 | 6,728,348 |

Statement size, identical for every seed: 2,338,816 product gates (table 2^22), 4,761,088 linear relations, 11,430,400 relation terms. The C++ witness lowering agrees cell by cell with the numpy reference (M, delta, S, o for all 4 tokens) for all 10 seeds. Timings are on a shared, loaded VM (AMD EPYC-Rome, 16 vCPU): indicative only, not a performance claim. Security parameters are the #19 research test settings (target 10 bits, 6 work bits, deterministic toy coins).

**H1: PASS.**

## H2: hostile proofs (threshold 100% rejected per class)

Seed 1, real shape. Complete hostile proofs commit a tampered witness with every product gate preserved, and substitute the true local value of every linear row as its target (the #19 style). The verifier is unchanged.

| class | what | rejected |
|---|---|---|
| c1 state | private S_1[0,0] += 1; S_3[0,0] += 1 | 2/2 |
| c2 floor-preserving state | S_2[0,0] += 1, remainder -= 2^F (negative remainder), quotient range bits re-derived for the new value | 1/1 |
| c3 decay | decay operand of one gate += 1 (public a unchanged); public a_1 += 1 at every binding vs honest proof | 2/2 |
| c4 beta | beta operand of one gate += 1; public beta_1 += 1 at every binding | 2/2 |
| c5 rounding | memory read M[0] += 1 with remainder -= 2^2F; delta[0] += 1 with remainder -= 2^F (truncation-style quotient/remainder shift) | 2/2 |
| c6 range bit | S_1[0,0] range bit 3 flipped; remainder bit 0 flipped | 2/2 |
| c7 public | S0[0,0], k_1[0], v_1[0], q_1[0], o_4[0], S_4[0,0] each += 1 vs honest proof | 6/6 |
| c8 bytes | 12 single-bit flips, 9 truncations, 1 trailing byte, 1 wrong transcript label | 23/23 |
| **total** | | **40/40** |

**H2: PASS.** These are sampled attacks, not an exhaustive search or a formal soundness proof.

## H3: state range over 1,024 steps (threshold max |S|, |M|, |delta| < 2^18 at F = 12, all 4 realistic distributions x 5 seeds)

Integer reference only (no proof), D = 128, 1,024 steps from S = 0, seeds 1..5. "Bits" = signed bits needed for max |S|.

| dist | v law | max \|S\| median (min..max) | bits S | max \|M\|,\|delta\| | fits 2^18 |
|---|---|---|---|---|---|
| R1 | SiLU(N(0,1)) | 4,229 (3,615..4,730) | 14 | 14,591 | 5/5 |
| R2 | SiLU(N(0,4)) | 8,600 (7,398..10,350) | 15 | 29,618 | 5/5 |
| R3 | SiLU(2 t_3) heavy tails | 75,605 (70,488..125,548) | 18 | **422,167** | **0/5** |
| R4 | SiLU(AR(1), rho 0.9, sd 2) | 12,062 (8,547..19,015) | 16 | 32,332 | 5/5 |

R3 per seed: max |delta| 291,511 / 298,632 / 337,617 / 422,167 / 285,196, first leaving the bound at step 302 / 159 / 145 / 120 / 35. The state stays below 2^18 in every R3 run (max 125,548). What overflows is delta = beta (v - M), because the t_3 tails put single v entries near 100 in real units (409,600 at F = 12).

**H3: FAIL** (R3, 5/5 seeds).

Stress suite (a = 1, beta = 1; reported only): S1 14,696, S2 31,625, S4 44,491 max |S|, all fit; S3 (heavy tails) max |S| 459,648, does not fit.

F sweep (realistic suite, all 5 seeds, all four laws):

| F | worst max \|S\| | worst max \|M\|,\|delta\| | all 20 runs fit 2^18 | state divergence vs float64 (max abs, real units) |
|---|---|---|---|---|
| 8 | 7,861 | 26,439 | yes | 0.42 |
| 10 | 31,376 | 105,511 | **yes** | 0.091 |
| 12 | 125,548 | 422,167 | no (R3) | 0.032 |
| 14 | 502,337 | 1,688,792 | no (R3) | 0.0061 |
| 16 | 2,009,356 | 6,755,171 | no (R2, R3, R4) | 0.0016 |

Divergence is integer vs float64 of the same recurrence. It is not fidelity to Qwen's BF16/FP32 kernels; M0 owns that. Largest intermediate product a*P: 1.3e12 at F = 12, 5.4e15 at F = 16. Both are far below the Goldilocks prime, so these are committed product values, not limbs that need splitting.

## What this means for M2 (not part of the verdict)

- The recurrence is provable on this harness at the real 128 x 128 shape, and every tested hostile class is rejected. That half of the go/no-go holds.
- A single 2^18 limb at F = 12 is not enough if value inputs are heavy-tailed. Three options, none tested here under a registered threshold: (1) F = 10, where all 20 realistic runs fit with headroom (worst delta 105,511, about 2.5x below the bound), at about 3x the rounding error of F = 12; (2) two limbs for delta and M only, with the state single-limb (the state fit 2^18 everywhere at F = 12); (3) take the real v range from M0 calibration (Qwen's actual post-conv SiLU outputs) rather than a synthetic t_3 tail, which may be pessimistic or optimistic. Choosing among these is a new pre-registered experiment.
- Cost signal: this gadget uses explicit bit decomposition for every range check, about 36 product columns per state cell per token (19 range bits + 12 remainder bits + gates). One head over 4 tokens is 2.34M columns and 50 MB of proof on the toy harness. That does not extrapolate to the production prover, which has a lookup-based smallness test. But it shows that range checks, not the multiplications, dominate the witness. M2 should be designed around the lookup smallness test.

## Deviations from PREREG

- The #19 harness (`affine_rows/product.h`) caps relations at 64 and terms at 8. `research/operators/qwen_deltanet/product.h` adds a wide variant on the same product oracle and the same affine row lowering (relations up to 2^23, terms up to 256, own transcript label). Every relation is bound in the first query and counted in both GroupLoad and plan_iopp, the same as `affine_size`. Public values and wire reuse are expressed as 1-term and 2-term relations instead of separate coordinate and wire lists. Not reviewed independently yet.
- c8 adds a wrong-transcript-label check, beyond the registered counts. No registered item was dropped.
