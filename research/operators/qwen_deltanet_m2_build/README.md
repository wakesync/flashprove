# Qwen Gated DeltaNet head on two lookups (research only)

Experiment, registration and verdicts: `experiments/20261109-32-qwen-deltanet-lookup-build/` (PREREG.md, RESULTS.md). Issue #32. This directory builds "arm B" of the M2 design (PR #66): floor remainders checked by a second lookup instead of by exact bits.

**Read this first.**
- Everything here runs on **synthetic inputs and synthetic head constants** with the **PR #66 lowering**. On real layer-0 weights that lowering did not meet the fidelity threshold (PR #68, unreviewed at the time of writing). Nothing here says the head matches the real model.
- Research security settings only (target 10 bits, N = 10 combinations, toy coins), as M1b (#63). No production soundness claim.
- As PR #66 section 0 says, every input of the M2 head statement is public, so a verifier could recompute the whole thing. Stage 2 is a rehearsal of the machinery for M3, not a useful proof.
- Not a serving protocol. Unreplicated. Hostile cases are sampled, not exhaustive.

## What is built

| file | what it is |
|---|---|
| `two_lookup.h` | The composition: sizing, plan, first-query binding and the verifier. The M1b run (wide affine product oracle + RNG with its digit lookup) plus a second LKP instance, the **remainder lookup**: unshifted, one function, keys in parts, table {0 .. 2^12 - 1}. Its keys are never sent: they are cells of row a of the product oracle (message 0), in public aligned key regions. The verifier calls the library's `rng_verify` and `lkp_verify` unchanged. |
| `two_lookup_prove.h` | The prover. Honest: library `lkp_prove`. Hostile: research copies on the prover side only (an RNG prover that can wrap a combination or move a digit, and an LKP prover side whose sumchecks do not stop on a false claim), so that complete proofs of false statements can be written and handed to the unchanged verifier. |
| `head.h` | One builder for both stages: gates, range cells, key cells, relations, layout. `build(.., relonly = true)` is the verifier's derivation and computes no witness. All i64 arithmetic is checked. The scale F, the norm constants and the norm lowering are in one place (`HeadParams`, `NormParams`, and the block marked "gated RMSNorm"). |
| `stage1.cpp` | Stage 1: the M1b statement (D = 128, T = 4, F = 12, public o) with lookup remainders. Entry `verify_stage1(words, proof)`. |
| `public_stage.h`, `m2.cpp` | Stage 2: the M2 head (T = 16). Entry `verify_m2(head_constants, words, proof)`. |
| `tables/`, `tables.py` | The pinned integer tables (below). |
| `reference_m2.py` | Integer reference of the M2 head in Python, independent of the C++ lowering; `m2.cpp` checks agreement value by value. |
| `record.py` | Builds fixtures, compiles, runs every step, writes `evidence.json` and the experiment's `runs/`. |

## What is proved

**Stage 1.** For public S0, a, beta, k, v, q, o, S_T: there are states S_1 .. S_4 with S_4 = S_T that follow the staged-floor recurrence of `research/operators/qwen_deltanet/README.md`, and o is the head output. As in M1b, RNG proves |x| < 2^23 for S', M and the two delta limbs. New: every floor remainder is one 12-bit key cell (two for the 24-bit M remainder), and the remainder lookup proves each key cell is in [0, 2^12). That is an exact range, so the floors are unique as in M1b.

**Stage 2.** For public S0, H, xq, xk, xv, ar, br, z, y, S_T and the verifier's head constants: the same recurrence with k, q, v, a, beta as the verifier recomputes them, the head output o as a witness range cell, and y = the gated RMSNorm of o (PR #66 section 4.4: sigma = isqrt(sum o^2 + eps), Rc = floor(2^36 / sigma), w = floor(o Rc / 2^24), y = floor(cg w / 2^F)), with every exact quantity (sigma, the two isqrt residuals, Rc, its remainder, the gap, the floor remainders) as 12-bit key cells.

## What the verifier recomputes (stage 2)

From decoded public integers and its own head constants, with integer arithmetic and pinned tables only (`public_stage.h`): the causal conv (kernel 4, history H in place of padding), SiLU, the q/k L2 norm with the q scale, the decay and beta gates, and the norm coefficient cg. Before any relation is derived and before any integer becomes a field element it checks: a, beta in [0, 2^F]; |k|, |q| <= 2^F; |v| < 2^31; **|cg| < 2^24**. A table input outside [-8, 8) is rejected, never clamped. Each of these is a returned verdict ("admit"). The cg bound is what makes the norm's last floor an integer equation (a hostile w is only known to be below 2^23, so |cg w| < 2^47); the fourth review of PR #66 showed modular aliases without it.

A consequence worth knowing: the conv output is floor(acc / 2^12) and a table key is floor(x / 16), so a small change of a public input can leave every recomputed value unchanged. The derived statement is then the same statement and the proof still verifies. "A changed H is rejected" holds for changes that alter a recomputed value.

## The two lookups: what separates them, and what was tested

The library gives every use of a block the same round names, and a plan's per-use label is not hashed. This directory does not change the library. The separation is:
1. Each instance's public inputs are bound into the first query under its own item name (`range check: digit lookup`, `remainder lookup`), together with the key regions' places and the first place of the remainder multiplicities.
2. Order: message 0 (product oracle, holds the remainder keys), then RNG's Theta, then messages 2 (digits) and 3 (both instances' multiplicities, in two disjoint fixed place ranges), then the digit lookup, then the remainder lookup. So every message that holds keys or multiplicities of either instance is sent and sampled before either lookup's first challenge, and the remainder lookup's alpha is drawn from a chain value that depends on the whole digit-lookup transcript.
3. The run has its own chain label.

The tests (stage 1 hostile suite, classes `h1-*`) are sanity checks, not a soundness proof. What each one is:
- **relabel control:** the honest proof under a verifier that binds the same two values under exchanged item names. Only the names differ, so its rejection shows the item names are part of the first query. This is the one `h1` case that tests a property directly.
- **alpha replay:** a prover that builds the remainder lookup's product trees under the digit lookup's alpha. The verifier rejects it. This does not show that a verifier with a shared-alpha bug would have accepted it: the research prover still uses the channel's own alpha in the leaf summand and the key claim, so its transcript is inconsistent under either alpha. No buggy verifier was built to test against.
- **moved or missing multiplicities:** the remainder planes committed one block after the bound place, or not at all. Rejected. No verifier that reads the other place was built, so there is no matching acceptance control.
- **splices:** byte ranges of the two lookups' transcripts overwritten or exchanged in an honest proof. Rejected, as any change to proof bytes is expected to be.

The argument that the composition is sound is the sequential-composition argument above (all key and multiplicity messages fixed before either lookup's first challenge, one hash chain), on paper, not refereed. "The two alphas differ" is reported because it was registered; two draws from a hash chain differ with overwhelming probability whatever the design, so it is weak evidence. In the stage 1 suite, every complete hostile proof (26 of them) was rejected at the same final check (the proximity test's base case), so the rejection reason does not say which claim was false. Where a tamper violates no affine relation and keeps every product, the false claim can only be one of RNG's or the lookups'; that attribution is by construction, not from the verifier's output.

## Pinned tables

`tables/silu-f12.i64le`, `sigmoid-f12.i64le`, `decay-one-f12.i64le` are the operators lane's files (PR #67, format `flashprove-qwen-integer-tables-v1`), copied byte for byte: 4,096 signed 64-bit little-endian rows, row = floor(X / 16) + 2048, domain [-8, 8), output at 2^12. Their SHA-256 values are in `tables.py`, which checks them and checks that `tables/pinned_f12.h` (what the C++ compiles in) equals the files. The format is not forked, and this directory does not regenerate the tables; that test is the operators lane's. If PR #67 changes a table, these copies must be updated with it.

Choices this forced, all departures from the real model: decay uses A = 1 with a public integer dt_bias added to the table key (the pinned tables carry no learned A); cg = floor(G silu(z) / 2^12) with a public per-channel constant G; the q/k L2 norm and the gated norm use exact integer isqrt as PR #66 pins it, not the operators lane's bounded `l2-128` table.

## Not covered

- in_proj, out_proj, the pre-norm, residual and MLP; the link between layers; any commitment to state or inputs (M3, issue #34).
- conv, SiLU, the q/k norm and the gates as in-relation gadgets (they are recomputed here; the operators lane builds them).
- Fidelity to the real model (see the top of this file).
- Zero knowledge. The run uses the library's masks, but nothing here was tested or argued for hiding.
- Production parameters. At N >= 128 combinations the RNG digits grow about 12.8 times.
- `rng_verify`'s and `lkp_verify`'s own soundness, which is the library's (argued on paper in `blocks/iop/`).

## Reproduce

CPU, g++ with C++17, Python 3 with numpy. From the repository root. On a shared host run the heavy steps through its job gate; cores come from `M2_CORES` (default 0-5).

```
python3 research/operators/qwen_deltanet_m2_build/tables.py check
python3 research/operators/qwen_deltanet_m2_build/record.py build1 honest1 hostile1 ubsan1
python3 research/operators/qwen_deltanet_m2_build/record.py build2 honest2 hostile2 ubsan2
python3 research/operators/qwen_deltanet_m2_build/record.py counts
```

`honestN` proves and verifies seeds 1..10 (one process each) and gives every timing, size and count in RESULTS.md. `hostileN` runs the hostile suite on seed 1. `ubsanN` runs it again under `-fsanitize=undefined -fno-sanitize-recover=undefined`. `counts` compares the builder's counts with `research/operators/qwen_deltanet_m2/count_model.py` arm B. `m2.bin <fixture> check` builds the stage 2 witness and relations and proves nothing (about 2 s).

`-DSTAGE1_D=16` gives a small debug build of stage 1. No reported number comes from it.
