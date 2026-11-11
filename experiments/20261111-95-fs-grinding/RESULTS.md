# RESULTS: 20261111-95-fs-grinding

Issue #95, lane grind95. Verdict against the PREREG threshold: **PASS** (measured, unreplicated). Research toy profile only. **No whole-proof soundness figure and no security level is established or claimed here.** This measures one attack (grinding) on one round of one research profile.

## In plain words

A cheating prover can retry the Fiat-Shamir hash until a challenge comes out in its favour. We took the round of the research convolution profile (PR #67) whose error is largest before proof of work, a round that draws 9 positions out of 512, and modelled a prover whose committed word agrees with a codeword on exactly the fraction of positions that the plan's bound allows. We then ground the repository's own hash chain at that round, half a million times per arm, re-randomising only what a prover controls (the nonce, or its own message before the draw). The prover's success rate per completed try came out at the uniform-draw figure, about 1 in 20 (2^-4.33), inside the plan's bound for that round (2^-4.30 before work). The 6 bits of proof of work raised the counted work-test cost per success by the expected factor of 64: about 1284 nonce tests (work-test calls) per lucky draw (2^10.33), against 20 without work. These counts are nonce tests only, not all hash calls: they leave out challenge expansion (2 extra chain calls per completed try at w = 6, 1 at w = 0) and hashing the message prefix, so the 64x applies to the counted work-test cost, not to the total hashing cost. Grinding gained nothing beyond paying for more tries. What a lucky draw at this round is worth for forging a whole proof was not measured.

## Selected round

From `runs/plan.jsonl` (the unmodified library's plan for `fixture("conv", 12, 1)` through `run_for()` of `research/operators/qwen_ops/proof.cpp`; target 10 bits, 6 bits of work on QUERY rounds; 27 rounds) and `runs/accounting.txt` (the library's `print_accounting` for the same plan):

- Round index 26 (chain round 27), `BASE (a, b, c, last stage)`, kind POSITIONS, error kind QUERY.
- Error bound without work e = 2^-4.300226 = 0.0507578; with work 2^-10.30. The accounting names this round as the largest round error without work (`work: 4.30 + 6 ... BASE (a, b, c, last stage)`).
- t = 9 positions, each in [0, 2^9), w = 6 work bits.
- Modelled attacker: agreement a = e^(1/9) = 0.718070, agreeing set A = floor(a x 512) = 367 positions, so p0 = (367/512)^9 = 0.0499534 (rounding A down makes p0 slightly below e).
- The two `CS` rounds (2^-4.30 and 2^-4.40 before work) are the same class of round; the stage-1 CS round (index 20) was used for debugging only (seed 99, 1000 tries), as the PREREG required.
- The rounds with the largest error with work counted are FOLD/BASE-lambda closeness rounds at 2^-10.00, which are algebraic challenges with no work; grinding them is a different attack (search for a bad field element) and was not run here.

## Numbers (5 runs per arm, 100000 completed tries per run)

Source: `runs/arm-A.jsonl`, `runs/arm-B.jsonl`, `runs/arm-C.jsonl` (raw), `runs/summary.json` (pooled, computed by `run.py report`).

| arm | what is ground | forges / tries | pooled rate | 99% Clopper-Pearson | per-run rate median [min, max], SD | nonce tests per forge |
|---|---|---|---|---|---|---|
| A | nonce only, fixed prefix | 24923 / 500000 | 0.049846 (2^-4.326) | [0.049057, 0.050644] | 0.04951 [0.04897, 0.05082], 0.00082 | 1284.07 |
| B | fresh prover message per try (1590 words, 12720 bytes; see Deviations), first nonce that passes | 24864 / 500000 | 0.049728 (2^-4.330) | [0.048939, 0.050525] | 0.04987 [0.04880, 0.05034], 0.00060 | 1285.41 |
| C (control) | arm B with no work (w = 0) | 24847 / 500000 | 0.049694 (2^-4.331) | [0.048906, 0.050491] | 0.04978 [0.04822, 0.05117], 0.00109 | 20.12 |

Reference values: p0 = 0.0499534, e = 0.0507578, e x 1.05 = 0.0532957; expected nonce tests per forge 2^6 / p0 = 1281.19 (arms A, B), 1 / p0 = 20.02 (arm C).

Nonces tested per completed try (each one work-test call): arm A median 64.004 [63.801, 64.264], arm B 63.983 [63.722, 64.091], arm C 1 by construction.

**What the cost column counts.** "Nonce tests per forge" (1284.07, 1285.41, 20.12) is the number of work-test calls in the nonce loop per successful draw, as counted by `nonces` in `grind.cpp`. It is not the total number of hash calls. Not counted: challenge expansion, where `draw_position` takes 2 further chain calls per completed try at w = 6 and 1 at w = 0 to produce the 9 positions; and hashing the message prefix (12720 bytes, once per run in arm A, on every try in arms B and C). Any "64x" comparison in this file is about the counted work-test cost only. Total hashing cost per success was not instrumented.

**Arm C is an independent control stream.** Its generator seed depends on the arm letter, so it does not see the same messages as arm B; it is not a paired run. It differs from arm B in w and in the random stream, not only in w.

**How fine the test is.** At 5 x 10^5 tries per arm the 99% interval is about +-1.6% of p0 wide. A per-try bias smaller than that would not show up here.

**Tie for the selected round.** Round index 24 (`CS`, stage 2) has the same bound before work as round 26 to 6 decimals (4.300226 bits), with the same t = 9, n = 512 and w = 6 (only its planned message length differs, 24 bytes against 12720; `runs/plan.jsonl` lines 25 and 27). The harness's `pick()` replaces its choice only when a round's bits are strictly smaller in double precision, and round 26's are, by less than 10^-6 bits, so it picked round 26; since the two rounds have the same t, n, w and bound, the choice between them makes no difference to the threshold or the expected rate p0.

**What this tests.** That the library's position draw comes out uniform under retries (nonce or message), and that the work test multiplies the counted nonce-test cost by the expected 2^w. It does not test whether the plan's agreement figure for the BASE round is right (see below).

## Against the threshold

- Arm A: interval contains p0 (yes), upper end 0.050644 <= e x 1.05 = 0.053296 (yes). PASS.
- Arm B: interval contains p0 (yes), upper end 0.050525 <= 0.053296 (yes). PASS.
- Reported check, not a gate: nonces per forge within 10% of 2^w / p0: A +0.22%, B +0.33%, C +0.52%. Yes for all three.
- Overall: **PASS** (gate arms A and B).

The upper ends also lie below e itself, so on this round no grinding strategy tried here beat the plan's per-round bound. The interval excludes nothing about strategies that were not tried (see below).

Wall time, for information only (shared loaded host, single thread): arm A median 1.553 s per 10^5 tries, arm B 5.048 s (absorbing the round's 1590-word message dominates), arm C 3.474 s.

## What is NOT established

- **No whole-proof figure.** A forge here is "the 9 drawn positions of one round all fall in the agreeing set". It is not an accepting proof. A false statement would also have to survive the other 26 rounds, and how the rounds compose under grinding (the compiled bound in `blocks/numbers/accounting.h`) was not measured. The repository's accounting itself says "no figure here is a security level".
- **Modelled, not constructed, cheating prover.** The agreeing set is derived from the plan's own bound (a = e^(1/t)); no false witness was committed and no codeword distance was measured. For this round the bound is priced as agree^t, so a equals the analysis' agreement. A real cheating word could agree on fewer positions (the attack would do worse) and, if the analysis' agreement were wrong, on more; this experiment cannot tell which.
- **Synthetic transcript prefix.** The chain is started from a first query with this profile's configuration digest, a seeded statement and salt, and then advanced by empty rounds to chain round 26; the prover's message at the round is random words of the planned length (1590 words), not real Merkle roots and answers. This tests the chain's query construction, work test and position draw as the library implements them, not the rest of the transcript.
- **Strategies not tried:** grinding earlier rounds to steer the BASE round's agreement (e.g. choosing fold challenges), grinding the 2^-10.00 algebraic closeness rounds, adaptive choice of the agreeing set after seeing the positions, attacks on the hash (BLAKE2b treated as the library uses it, no cryptanalysis). The round's positions may repeat (draws are with replacement, as in `PositionsDraw::positions`); that is part of the measured rate.
- **One profile, one seed of the fixture** (conv, F = 12, `fixture` seed 1). The other operators of PR #67 (nonlinear, L2, RMS, rotary) and the production setting (128-bit target) were not run.
- **Unreplicated.** One lane, one host.

## Deviations from the PREREG

- The registered runs took about 50 s of single-threaded CPU and were run pinned to cores 10-15 without the heavy-job gate (below its 2-minute threshold); the 8-minute build went through the gate. Recorded in ENV.json.
- **Message size in arms B and C (not pre-registered).** PREREG `Runs` registered a fresh 32-byte prover message per try for arm B (and arm C). The harness instead regenerates the round's full planned message, 1590 words (12720 bytes), on every B and C try. This was not recorded before the runs; an earlier version of this file said "None other". A dated, explicitly retrospective entry now records it under PREREG `## Amendments` (added after the registered runs). The threshold, metric, arms, seeds and try counts are unchanged and no run was repeated. Whether a 32-byte message gives a different rate was not measured.
- PREREG header time 09:35Z is 6 minutes after the commit time of 5b89ea5d (09:29:28Z); the commit time is the real one (noted in the same amendment, history not rewritten).
- Known format issue in raw receipts: `runs/plan.jsonl` lines 2 and 15 contain a bare `inf` (an infinite bit bound), which is not valid JSON. The raw file is left as committed; future receipts should write `null` or a documented string instead.
- The selected round is the one the PREREG's rule picks, and the threshold, arms, seeds and try counts are as registered.

## Reproduce

From the repository root, g++ with C++17 and Python 3 standard library (no downloads):

```
python3 experiments/20261111-95-fs-grinding/run.py build    # about 8 minutes: the pinned tables of qwen_ops
python3 experiments/20261111-95-fs-grinding/run.py plan
python3 experiments/20261111-95-fs-grinding/run.py runs
python3 experiments/20261111-95-fs-grinding/run.py report
python3 experiments/20261111-95-fs-grinding/env.py          # rewrites ENV.json with the current host
```

The counts are deterministic for a given binary and seed (seeded generators, no timing in the decision), so a rerun of `runs` should reproduce every forge and nonce count exactly; wall times will differ. `runs` and `report` overwrite the committed run files; to compare, write to another checkout.
