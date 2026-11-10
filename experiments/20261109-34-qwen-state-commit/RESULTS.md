# RESULTS: 20261109-34-qwen-state-commit

Issue: #34 (tracking #32). PREREG: 0c0556e, the first commit on the branch. Base: origin/main 4f7a8761, main merged in later (merge commits, no rebase).

**This file was corrected on 2026-11-10 after two independent reviews of PR #71** ([astra](https://github.com/wakesync/flashprove/pull/71#issuecomment-6758363867), [opus](https://github.com/wakesync/flashprove/pull/71#issuecomment-6758460446)). Both reproduced every committed number and both asked for changes. The registered verdicts did not change: H1 to H3 PASS, H4 FAIL. What changed is listed in "Corrections after review" at the end. Run files of the registered run are untouched; new runs have the suffix `-r2` or a new name.

All numbers are **measured and unreplicated** unless they are marked **counted** or **reviewer's figure**. They come from one shared, loaded host. Research security settings throughout (#19: target 10 bits, 6 work bits, deterministic toy coins). These are relation-soundness arguments on a research harness, not production security.

Strategy analysis: [STRATEGIES.md](STRATEGIES.md). Code and reproduce commands: [research/operators/qwen_state_commit/](../../research/operators/qwen_state_commit/README.md).

## What this experiment does and does not show

- **SA** (commit the state at chunk boundaries, keep the states inside a chunk as witness): chunk proofs exist and verify, and the bookkeeping that links chunks works **once the verifier holds the statement** (request, layer, window length T, chunk size C, head size D, fixed-point bits F, first-chunk handle). In this harness the boundary state, every token input and every output are public words. The link between two chunks is a comparison of SHA-256 hashes of public words, done outside the proofs. Nothing here tests a handoff in which the state is hidden.
- **SA does not reduce committed volume.** 19,104 columns per token at every C. That is true by construction of this harness's per-token lowering. It is not a measured property of SA.
- **SB** (chunked low-rank form) **is not established.** It is integer reference arithmetic with no proof. Its registered arm failed the registered drift bound. The arm that passes is unregistered, was under-counted in the first version of this file, has no sound lowering here, and has no proof and no backend in this repository.

## Verdict against the registered thresholds

| hypothesis | threshold | result | verdict |
|---|---|---|---|
| H1 SA honest | every chunk and chain accepted, 5/5 windows per C | C=1: 320/320 chunks, 5/5 chains; C=16: 20/20, 5/5; C=64: 5/5, 5/5 | **PASS** |
| H2 SA boundary hostile | 100% per class at C=16 and C=64 (C=1 where it applies) | C=1: 9/9, C=16: 10/10, C=64: 10/10 rejected; honest controls accepted. See the scope statement under H2: 11 by a chunk proof, 18 by checks outside the proof, and cases outside the registered classes were accepted by the registered chain check | **PASS** as registered |
| H3 SA volume | committed columns per token at C=16, 64 within 10% of C=1; carried = (D^2 + 9D)/C | 19,104 at all three C (0% difference); carried 1,312 / 82 / 20.5 = (1,024 + 288)/C | **PASS** (true by construction of the lowering, see H1 and H3) |
| H4 SB reference (registered GB = F = 12) | (a) C=1 equals M1 20/20; (b) contracts 20/20 at C=16, 64; (c) drift <= 0.064 20/20; (d) numerator < 2^62 | (a) 20/20; (b) 20/20 and 20/20; (c) **19/20** at C=16 (max 0.0663) and **19/20** at C=64 (max 0.0942), both misses are R3 seed 3; (d) 53 bits | **FAIL** (c) |

By the pre-registered recommendation rule, H4 failing means the registered recommendation is **SA at C = 64**, with SB's failure reported. The rule is followed. No threshold was changed after the failure: the PREREG diff from its first commit to the head is amendment lines only, and both reviewers confirmed it.

## Deviations from the PREREG

1. **D = 32 for the SA proofs**, as registered. The registered reason was the table size at C = 64. The per-cell count is 18.66 product columns per state cell per token at D = 32, against M1b's 17.41 at D = 128. The difference comes from the per-column sites (M, delta, o) amortised over 32 instead of 128 rows.
2. **The hostile window at C = 64 is 128 tokens (2 chunks)**, not 64. With T = 64 there is no boundary between two chunks to attack. C = 1 and C = 16 use the registered 64-token window, attacked at boundary 1.
3. **Unregistered SB arms GB = 18 and GB = 24** (the decay table G held at scale 2^GB instead of 2^F). They were added after the registered GB = 12 arm failed H4(c). They are unregistered, descriptive, and change no verdict.
4. **Conv history** enters as a synthetic block of 3 taps x 3D words per head per boundary, hashed into the handle. It is not proved by a conv relation.
5. Perf is n = 5 windows (n = 320, 20 and 5 chunk proofs). That is below the >= 10 perf rule, as the PREREG said. No perf claim is made.
6. **Order of events (provenance).** The times written by hand in the PREREG header and in amendments A1 to A3 do not agree with the commit times and are not reliable. The order shown by the commits is: `0c0556e` (PREREG only, committed 01:08:29Z), then `d39f598` (code, 01:56:26Z; it already contains the 128-token hostile window that A1 describes and the `--gb` flag that A2 describes), then `733bfe5` (run files, RESULTS, and the text of A1 to A3, 02:23:48Z). Wall-clock times of the runs were not recorded. Commit order does not prove when a run happened.
7. **After review (PREREG A4 to A7):** the chain verifier was changed and every SA run was repeated as `-r2`; new negative cases, a recount and three reference-arithmetic scripts were added. None of this is registered. It changes no threshold and no verdict.

## H1 and H3: SA honest windows (D = 32, T = 64, F = 12, seeds 1..5)

Registered run (`runs/honest-C*.jsonl`, `runs/chain-C*.json`). Each chunk is one process, run sequentially through fp-heavy.sh and pinned to cores 0-5. The prover is single-threaded.

| C | chunks per window | chunk proofs accepted | chains accepted | table | per chunk prove s (median, min..max) | per chunk verify s | per chunk proof bytes | peak RSS (prove) |
|---|---|---|---|---|---|---|---|---|
| 1 | 64 | 320/320 | 5/5 | 2^17 | 2.381 (2.301..2.774), n=320 | 0.130 (0.120..0.177) | 1,807,304 | 0.22 GB |
| 16 | 4 | 20/20 | 5/5 | 2^19 | 9.779 (9.620..10.238), n=20 | 1.648 (1.563..1.789) | 6,532,528 | 1.18 GB |
| 64 | 1 | 5/5 | 5/5 | 2^21 | 40.335 (39.783..41.694), n=5 | 7.834 (7.698..8.235) | 25,411,680 | 4.55 GB |

Per 64-token window (sum over its chunks, n = 5 windows):

| C | prove s median (min..max) | verify s median (min..max) | proof bytes median | committed core columns per token | relations per token | carried handle values per token |
|---|---|---|---|---|---|---|
| 1 | 153.18 (152.00..153.62) | 8.438 (8.425..8.484) | 115,666,080 | 19,104 | 38,112 | 1,312 |
| 16 | 39.28 (38.80..39.99) | 6.659 (6.514..6.729) | 26,129,984 | 19,104 | 37,152 | 82 |
| 64 | 40.34 (39.78..41.69) | 7.834 (7.698..8.235) | 25,411,680 | 19,104 | 37,104 | 20.5 |

Readings.
- **Committed volume per token is the same at every C: 19,104 core columns, 18.66 per state cell. This is by construction, not a finding.** `chunk.cpp` emits the same columns for every token whatever the chunk length. From the code, per token: (4 + F + 1) D^2 + (2 + 4F + 3) D = 17 D^2 + 53 D at F = 12, which is 19,104 at D = 32. Only the relation count moves with C (38,112 / 37,152 / 37,104), because of the boundary pins. So H3 confirms that a per-token lowering keeps the states inside a chunk as committed witness. It does not show that every possible SA backend must cost this much.
- **Times are indicative only.** n = 5 windows on a shared loaded host is below the perf rule. In this run the per-window prove time and proof bytes are lower at C = 16 and C = 64 than at C = 1 (medians in the table). No speedup is claimed.
- Peak RSS grows with C (one chunk's witness). Extrapolated from the formula above, not run: C = 64 at D = 128 has 285,312 x 64 = 18,259,968 core columns, more than 2^24, so it would need a 2^25 table. This harness has been run up to 2^21. That is why SA alone does not scale to the real head here.

**Run r2 (after the chain-verifier fix, `runs/honest-C*-r2.jsonl`, `runs/chain-C*-r2.json`).** Every honest chunk proof was made again with the unchanged `chunk.cpp` (same source hash in `build.json` and `build-r2.json`) and the chains were checked by the fixed verifier with the statement held by the verifier: 320/320, 20/20 and 5/5 chunk proofs accepted, 5/5 chains at each C. Proof bytes, column, relation, range-cell and table-size fields are identical, chunk by chunk, to the registered run. The r2 run used four single-threaded workers at once on cores 12-15, so its times are not comparable and are not reported.

## H2: SA boundary-targeted hostile suite (seed 1)

### What the 29 rejections are

In this experiment S_in, S_out, every token input (a, beta, k, v, q) and every output o are **public words**. Only the states inside a chunk are committed witness. The chain verifier recomputes SHA-256 handles from public words and compares them. So:

- Of the 29 registered rejections, **11 come from a chunk proof failing** (C=1: 3, C=16: 4, C=64: 4) and **18 from comparisons outside the proof** (carried handle, header fields, handle against words, token coverage). Source: the `why` field of `runs/hostile-C*.jsonl` and the `check` field of `runs/hostile-C*-r2.jsonl`.
- The 29 are sampled classes on one seed. They test the bookkeeping and the binding of the header into the chunk transcript. They say nothing about a handoff in which the state is hidden, and they are not a property of "the handle" in such a setting.

Registered run (`runs/hostile-C*.jsonl`):

| class | attack (boundary 1 unless noted) | C=1 | C=16 | C=64 | caught by |
|---|---|---|---|---|---|
| b1-wrong-state | S_in(chunk 1)[0,0] += 1, chunk proved honestly from it (and later chunks re-proved) | rejected | rejected | rejected | boundary 1: carried handle mismatch (outside the proof) |
| b1-wrong-state | chunk 1: honest words and header, proof made from S_in[0,0] + 1 | rejected | rejected | rejected | chunk 1 proof rejected |
| b2-other-chunk-state | S_in(chunk 1) := S_in(chunk 0), proved honestly | rejected | rejected | rejected | boundary 1: carried handle mismatch (outside) |
| b2-other-chunk-state | chunk 0 replayed verbatim in slot 1 | rejected | rejected | rejected | header fields at chunk 1 (outside) |
| b3-skipped-step | chunk 1 dropped from the chain | rejected | rejected | rejected | header fields at chunk 1; token ranges do not cover T (outside) |
| b4-replayed-boundary | proof of chunk 0 presented with chunk 1's words and header | rejected | rejected | rejected | chunk 1 proof rejected |
| b4-replayed-boundary | every chunk proof of request 1 replayed under request 2 (headers and handles recomputed) | rejected | rejected | rejected | chunk 0 proof rejected |
| b5-conv-history | H_in(chunk 1)[0,0] += 1, header and proof unchanged (an inconsistent replacement) | rejected | rejected | rejected | header handles do not match words at chunk 1 (outside) |
| b5-conv-history | H_in(chunk 1)[0,0] += 1, header recomputed and chunk re-proved honestly (inconsistent with the previous chunk) | rejected | rejected | rejected | boundary 1: carried handle mismatch (outside) |
| b3-skipped-step | chunk 1: witness skips token C/2 (decay 1, beta 0), complete hostile proof | n/a | rejected | rejected | chunk verifier: 2,181 violated relations at C = 16, 1,268 at C = 64 |

**Totals, registered run:** C=1: 9/9, C=16: 10/10, C=64: 10/10. Honest control chains accepted. **H2: PASS as registered.**

### What the registered chain check accepted, and the fix

The chain check of the registered run (`chain_check` at commit d39f598, kept as `window.chain_check_unpinned`) read request, layer, T and the first handle from a manifest file that the prover writes. It compared a header's chunk size only with the length of that chunk's own fixture, and it decoded the fixture's F and dropped it. Both reviews built chains that it accepted and that should be refused. So the induction in STRATEGIES ("every chunk applies the same step") did **not** hold for the registered check: it holds only when the verifier pins those parameters.

**Fix (Python only, `chunk.cpp` and the proof transcript unchanged).** `window.chain_check(outdir, statement, names, verify_chunk)` now takes a **statement descriptor held by the verifier**: a model/arithmetic identifier slot (a placeholder in this experiment: there are no weights), request, layer, T, C, D, F, the first-chunk handle, and the digest of the conv history at the end of the window. It does not read the manifest. It rejects unless the number of chunks is ceil(T / C); every fixture says the statement's F and D; every chunk has exactly C tokens except the last, which has T - (n - 1) C; every header says the statement's request and layer, index c, start c C, that length and D; the recomputed handles equal the header's; each chunk's input handle equals the previous output handle (chunk 0: the statement's first handle); every chunk proof verifies; and the last chunk's history matches the statement.

In the harness the statement is computed by `window.statement()` from the registered constants (seed, C, T, request, layer), not from the directory the prover writes. Both the verifier and the prover run in one script here; the separation is by argument, not by process or by machine.

**Run r2 (`runs/hostile-C*-r2.jsonl`).** Every row records the check that decided and, for the reviewer constructions, what the old unpinned check says about the same chain. Every chunk proof inside these cases is an honest, complete proof of the chunk it is presented with.

| named case | construction | from | old unpinned check | fixed verifier, C=1 / 16 / 64 | check that rejects |
|---|---|---|---|---|---|
| n1-mixed-F | chunk 1 proved in the same relation at F = 13, later chunks re-proved at F = 12 from its output | astra item 1 | **accepted** | rejected / rejected / rejected | fixture F against the statement's F |
| n1-mixed-F (relabelled) | the F = 13 chunk with its fixture relabelled F = 12, proof unchanged | this lane | rejected | rejected / rejected / rejected | chunk proof (the relation is derived from the fixture's F) |
| n2-split-chunk | chunk 1 presented as two honest chunks of C/2, later chunks renumbered | opus R10 | **accepted** | n/a / rejected / rejected | chunk count |
| n2-split-chunk (uneven) | chunks 0 and 1 re-cut as 8 and 24 tokens, same number of chunks | this lane | **accepted** | n/a / rejected / n/a | chunk length |
| n3-foreign-layer | every chunk honestly proved under layer-1 headers; the verifier asked for layer 0 | opus R3c | **accepted** | rejected / rejected / rejected | header fields against the statement |
| n4-foreign-first-state | chunk 0 starts from another in-range state, chain re-proved, manifest handle updated | opus R5b, astra 7 | **accepted** | rejected / rejected / rejected | carried handle at boundary 0 (statement's first handle) |
| n5-dropped-chunk | chunk 1 removed, later chunks renumbered and re-proved, manifest T reduced | opus R8b | **accepted** | rejected / rejected / n/a | chunk count |
| n6-truncated-chunk | last chunk proved over its first C/2 tokens, manifest T reduced | opus R9b, astra 13 | **accepted** | n/a / rejected / rejected | chunk length |
| n6-truncated-chunk (short window) | an honest window of T - C/2 tokens presented for the statement T | this lane | not run | n/a / rejected / rejected | chunk length |
| n7-prefix-only | only the first n - 1 chunks presented, manifest T reduced | opus R15 | **accepted** | rejected / rejected / rejected | chunk count |
| n8-last-chunk-history | H_out of the last chunk changed, header recomputed, chunk re-proved | opus R18 | **accepted** | rejected / rejected / rejected | last-chunk history against the statement |
| n9-empty-chain | no chunk presented, manifest T = 0 | astra 19 | **accepted** | rejected / rejected / rejected | chunk count |

**Totals, r2:** registered classes 9/9, 10/10, 10/10 rejected, the same verdicts as the registered run (the dropped-chunk case is now caught earlier, by the chunk count). Named negative cases: 8/8, 12/12, 10/10 rejected, 30 of 30. Of the 28 that were also run against the old check, it accepted 25 (the three it rejected are the relabelled-fixture rows). Honest controls accepted, including a window whose declared last chunk is short (T = 56 at C = 16, T = 96 at C = 64).

How far the mixed-precision chain is from the honest one (`runs/mixed-f-states.json`, arithmetic only, seed 1): the output state of the F = 13 chunk differs from the honest one by up to 1,847 / 1,788 / 1,394 integer units at C = 1 / 16 / 64, and that chunk's outputs o by up to 82 / 406 / 377. The final state of the window differs by 1,394 at C = 64, where the F = 13 chunk is the last one, and by 0 at C = 1 and 16, where 62 and 32 more tokens follow it. So at C = 1 and 16 the accepted chain differs from the honest one in a boundary state and in public outputs, not in the final state. Reviewer's figure, on another window (seed 7, C = 2, T = 6): final state differs by 66 units ([astra](https://github.com/wakesync/flashprove/pull/71#issuecomment-6758363867)).

### Still accepted after the fix, by design of this harness (open)

These are in `runs/hostile-C*-r2.jsonl` with `expect: accept`. They are listed, not counted as rejections.

1. **Token inputs replaced with another window's** (`open-inputs-not-bound`, accepted at C = 1, 16, 64). The inputs a, beta, k, v, q are public words bound to nothing. The request id is only a label. Chunk 1's inputs were replaced by another seed's, the chunk was proved honestly, the later chunks re-proved, and the chain is accepted. In M3 the layer inputs must be tied to the previous segment's committed outputs.
2. **Conv history changed consistently on both sides of a boundary** (`open-history-consistent-shift`, accepted at C = 1, 16, 64). A matching hash on both sides does not prove that the history is the last three real inputs. No conv relation is proved here. The registered b5 class covers inconsistent replacements only. After the fix the last chunk's history is compared with the statement, but interior histories are not in the statement.
3. **The boundary state is public.** Nothing here tests a handoff where the state is hidden and the next chunk's proof opens a commitment made by the previous one.
4. The statement descriptor is produced by the harness itself, and its model identifier is a placeholder: nothing ties a chain to a set of weights.
5. Reported by the reviews and unchanged: intermediate witness records in a fixture file are ignored by the verifier (it recomputes them); a chunk verifier alone accepts a changed S_in when the statement happens to stay true (the chain catches it through the handle).

## H4: SB reference (D = 128, real head shape, 1,024 steps, R1..R4 x seeds 1..5, no proof)

`sb_ref.py` evaluates the chunked relation with exact integers (Python ints) and compares it to the M1 per-token integer reference and to the float64 recurrence. Drift is the maximum over the run of |S / 2^F - S_float64| (state units), and then the maximum over runs.

| arm | C | fits contracts (S, M < 2^18, delta two-limb) | equals M1 at C=1 | drift max | drift median | drift <= 0.064 | max numerator bits (honest runs) | max abs S |
|---|---|---|---|---|---|---|---|---|
| GB=12 (registered) | 1 | 20/20 | 20/20 | 0.0321 | 0.0080 | 20/20 | 53 | 125,548 |
| GB=12 (registered) | 16 | 20/20 | n/a | **0.0663** | 0.0042 | **19/20** | 53 | 70,474 |
| GB=12 (registered) | 64 | 20/20 | n/a | **0.0942** | 0.0034 | **19/20** | 53 | 48,279 |
| GB=18 (unregistered) | 16 | 20/20 | n/a | 0.0206 | 0.0018 | 20/20 | 59 | 70,474 |
| GB=18 (unregistered) | 64 | 20/20 | n/a | 0.0130 | 0.0014 | 20/20 | 59 | 48,608 |
| GB=24 (unregistered) | 16 | 20/20 | n/a | 0.0204 | 0.0018 | 20/20 | **65** | |
| GB=24 (unregistered) | 64 | 20/20 | n/a | 0.0120 | 0.0014 | 20/20 | **65** | 48,613 |

At C = 1, GB does not matter (G = 2^GB on the diagonal only): every arm equals M1 for M, delta and S. The output o is floored in a different order from M1's, so nothing is claimed about o.

**The registered failure, as observed.** The registered arm misses the drift bound on one run, R3 seed 3: 0.0663 at C = 16 and 0.0942 at C = 64, against 0.064. On the same run the per-token arm (C = 1, equal to M1) has 0.0321. So on this run the registered chunked arm is further from float64 than M1 is, by about 2x at C = 16 and 3x at C = 64. No cause is established. The first version of this file said that this run is a fast-decaying head whose decay products underflow; that was wrong and is withdrawn. Measured (`runs/sb-gates-r3s3.json`): the run's decay gate has median 0.993 (minimum 0.836), and the staged decay products at chunk start, at scale 4,096, are 2,996 to 3,723 at C = 16 and 1,727 to 2,472 at C = 64, with none equal to zero.

**The unregistered arms, as observed.** With the decay table at 2^18 the same 20 runs pass the sampled bounds, with drift at most 0.0206 (C = 16) and 0.0130 (C = 64). On these 20 synthetic runs that is below the per-token arm's worst (0.0321); medians are 0.0018 and 0.0014 against 0.0080. This is one unregistered run set on synthetic gates. GB = 24 changes little and its honest numerators reach 65 bits, above the registered 62-bit line.

**SB is a different integer model from M1.** It rounds once per chunk. At C = 64 its integer state differs from M1's by at most 343 units (registered arm) or 80 units (GB = 18). The chunk size C is therefore part of the model definition and must be fixed by the verifier. It is not a prover choice. (The fixed chain verifier pins C; see H2.)

### Negative result: the 2^18 arm has no sound lowering here

The honest-run maximum of 59 bits is not a bound for a hostile prover, and the problem is larger than "3 bits of slack". Reproduced by this lane in `runs/sb-alias-gb18.json` (`sb_alias.py`, reference arithmetic; there is no SB proof, so nothing here is a forged proof):

- **Second solutions.** Suppose the SB floors were lowered the way M1b lowers its floors: the quotient is a range cell, for which the range check proves only |x| < 2^23 (honest values are below 2^18), the remainder is exact, and the relation divisor x quotient + remainder = numerator is checked in the Goldilocks field. At GB = 18 the M and o floors divide by 2^42. Then quotient + 2^22 with remainder - (2^32 - 1) satisfies the same field relation, because 2^42 x 2^22 = 2^64 = 2^32 - 1 modulo p. On the first 64-token chunk of two real SB runs (R1 seed 1 and R3 seed 3, D = 128), a second valid pair exists for **8,192 of 8,192 M floors and 8,192 of 8,192 o floors**. At GB = 12 (divisor 2^36) and at GB = 15 (2^39) there is none, for 8,192 of 8,192, because the smallest shift is about 2^28 or 2^25 and falls outside the 2^23 window. The S_out floor (divisor 2^30 at GB = 18) has none either. A second M changes delta: in the recorded example delta moves from -459 to 3,094,069, which still fits its two-limb contract.
- **Edge inputs inside the stated contracts overflow the registered line.** Complete SB chunks on constant inputs that pass the public admission of `chunk.cpp`: with every S_in cell at 2^18 - 1, a one-hot k and all q entries at 2^F, the o numerator has **67 bits** at GB = 18 (61 at GB = 12) while M and S_out stay inside the 2^18 contract. With S_in at 2^16 - 1 and all k and q entries at 2^F, the M and o numerators have **65 bits** (59 at GB = 12) and M = 8,388,480 is inside the 2^23 that the range check proves. Same at C = 1, 16 and 64.
- **Interval bounds** with every admitted value at the edge of its range at once (bounds, not traces): 91 / 92 / 73 bits for the M / o / S_out numerators at GB = 18 with 18-bit limbs, 96 / 97 / 78 with 23-bit limbs; 85 / 86 / 67 at GB = 12.

Conclusion: **SB at decay-table scale 2^18 has no sound lowering in this repository.** A sound one needs a remainder and quotient class tied to the divisor (an exact range on M and o below 2^22, not the approximate 2^23), proved bounds on the operands (for example norms of k and q, which the current admission does not check), or multi-word relations. None of these is specified, costed or tested here. GB = 15 has no second solution in this test, but it has no drift run.

### Real gates

The drift bound 0.064 was registered as twice M1b's worst on **synthetic fast-decay gates** (A drawn from U(1, 16)). It does not carry over to real gates. The real-weight check now on main (experiments/20261109-8-qwen-real-weights, PR #68) reports A in [0.0038, 0.34] on layer 0, far slower decay than the synthetic heads. Reviewer's descriptive run, not in this repository ([opus](https://github.com/wakesync/flashprove/pull/71#issuecomment-6758460446)): with A drawn from U(0.004, 0.34) and everything else unchanged, the 2^18 arm passed 19 of 20 at C = 16 and at C = 64, the registered 2^12 arm 18 of 20, and the per-token M1 reference itself failed the 0.064 bound in 8 of 20. A registered re-run on real gate statistics, with a bound stated relative to M1 or to float on those gates, is future work.

## Counted volumes (counted, not measured)

Scope of every number in this section: **the DeltaNet state mixer only**, 48 layers x 48 V heads, D = 128, one count per committed value. No conv, gates, norms, projections, output path, attention layers or head. The SB rows are counts **for a proof that does not exist, on a matmul-sumcheck backend that this repository does not have**.

Per-token strategies and carried values, from `count.py` (`runs/count.json`, registered, unchanged):

| strategy | C | committed values per token | carried values per token (state + conv) |
|---|---|---|---|
| S0 / SA / SC at 6.1 per cell (the count of #66 arm B, research product oracle) | any | 230.3M | 39.2M / C |
| S0 / SA / SC at 17.41 per cell (M1b, measured statement count) | any | 657.2M | 39.2M / C |

SB, from `count_r2.py` (`runs/count-r2.json`; its GB = 12 column reproduces `count.json` exactly):

| SB arm | formula per head per token | C = 16 | C = 64 | C = 128 |
|---|---|---|---|---|
| GB = 12, **the registered arm, which FAILED H4** | 3 D^2/C + 13 D + 2.5 C + 0.5 | 11,005,056 | 5,973,120 | 5,457,024 |
| GB = 18, unregistered, remainder keys widened only | 4 D^2/C + 15 D + 2.5 C + 0.5 | 13,954,176 | 7,152,768 | 6,341,760 |
| GB = 18, plus the two listed extras | | 14,863,104 | 8,116,992 | 7,379,712 |
| same formula on this repository's product oracle (every multiply a gate), GB = 12 / GB = 18 | 3 D^2 + D C + SB | 129.0M / 131.9M | 138.1M / 139.3M | 156.5M / 157.3M |

- **What was wrong.** The first version of this file quoted 5.97M per token for the proposed 2^18 arm. `count.py` uses two 12-bit keys for a 24-bit S_out remainder and three for the 36-bit M and o remainders. Those are the widths of the 2^12 arm. At 2^18, `sb_ref.py` divides by 2^30 and 2^42, so the same layout needs three and four keys: 7,152,768 at C = 64. Both reviewers get the same three numbers by the same formula; that is one calculation, not three confirmations.
- **Still missing from every SB row.** The "two listed extras" row adds the remainder keys of the floors that define the decay table and the operands k, q, v, a, beta as committed values (they are public here; in a model they come from the previous segment). Not counted at all: range checks of the quotients, whatever a sound 2^18 lowering needs (see the negative result above), and every sumcheck, lookup or commitment overhead.
- **No ratio against 230M is given.** The first version said "about 39 times". That divided a value count on a hypothetical matmul-sumcheck backend by a column count on the research product oracle. They are different quantities.
- **On the same backend the stated formula is lower, not equal.** On the product oracle, SB's formula gives 138.1M per token at C = 64 against 230.3M: about 40% lower (139.3M with the 2^18 widths). The first version said "no better than arm B"; that was wrong. Both are counts on the stated formula; no SB proof is built on either backend.
- **Against PR #70** (the M3 counting model, an unmerged draft): its counts and these are different quantities. Here: state mixer only, 48 layers, one field element per value, hypothetical backend, per-head formulas. There: the whole model, entries packed from byte limbs, with a planner overhead factor, and its own low-rank construction. Neither is a complete count of an SB proof, and none of these numbers should be compared across the two.

Conv history: 30,720 words per layer per boundary, 1.47M for the model, 3.9% of the 37.75M state values per boundary.

## Recommendation

1. **Registered recommendation, rule followed: SA at C = 64.** What the evidence supports is narrower than the first version said. SA's bookkeeping works once the verifier pins the statement (request, layer, T, C, D, F, first-chunk handle), on a harness where the boundary state, the inputs and the outputs are public. SA does not reduce committed volume: 19,104 columns per token at every C, which is true by construction of this harness's lowering and is not a measured property of SA. It reduces carried values only (counted: 0.61M per token at C = 64 for the full model).
2. **SB is not established and is not recommended.** Its registered arm (decay table at 2^12) failed the drift bound. Its passing arm (2^18) is unregistered, was under-costed (7.15M counted values per token at C = 64, not 5.97M, with more costs uncounted), is not sound as lowered (a second solution for every M and o floor tested, and 65 to 67 bit numerators at admitted edge inputs), and has no proof and no backend in this repository. The proposal in the first version of this file, "SB with GB = 18 at C = 64 for M3", is withdrawn.
3. **Before SB is reconsidered** it needs, in this order: a registered re-run of the reference on real gate statistics with a bound that makes sense there; a specified sound lowering of the floors (exact quotient range tied to the divisor, proved operand bounds or multi-word relations) with its cost counted; and an SB chunk proof on a backend that exists.
4. **Boundary interface (any strategy):** the verifier holds the statement; the boundary carries the state and the conv history together; the header is a statement item of the chunk transcript. What is bound, checked outside or missing here is in the next section.
5. SC (checkpoint and recompute) is the prover's memory schedule, not a separate commitment. SD is not recommended: its forward-substitution soundness is open and its T^2 term grows with the request.

## Interface for the M3 design lane

What a real in-proof handoff must bind, and where each item stands in this experiment. "In the transcript" means a proof made for another value does not verify. "Outside" means a comparison done by the chain verifier in Python on public values.

| item the statement or boundary handle must bind | here |
|---|---|
| model / weights identity | **missing.** A placeholder slot in the statement descriptor. Not in the header, the handle or any transcript. |
| F and every scale (decay-table scale for SB) | F: the chunk's relations are derived from the fixture's F, so a proof is tied to it; that it equals the statement's F is **checked outside**. Not in the header or the handle. No other scale exists here. |
| C and the chunk policy (every chunk C tokens, declared short last chunk) | header C is **in the transcript**; that it follows the policy is **checked outside** against the statement. |
| window length T | **checked outside** (chunk count and lengths). Not in the header or the handle. |
| request and layer | **in the transcript** (header) and in the handle; equality with the statement **checked outside**. |
| chunk index and token start | **in the transcript** (header) and in the handle; order **checked outside**. |
| first-chunk state: zero, or a named continuation root | **checked outside** against the statement's first handle. Here it is a warmed-up public state, neither zero nor a proved continuation root. Who supplies a continuation root and how the verifier knows it is undefined. |
| a commitment to the layer's inputs | **missing.** Inputs are public words bound to nothing (open case 1). |
| the conv history as part of the committed boundary | hashed into the handle with the state, so an inconsistent change is caught **outside**; the last chunk's history is compared with the statement. No conv relation; a consistent change is accepted (open case 2). |
| the boundary state itself, hidden | **missing.** S_in and S_out are public relation targets of the chunk proof; the handle is a SHA-256 of public words. An in-proof opening of the previous chunk's commitment is not built. |
| the layer's outputs, committed for the next segment | **missing.** Outputs are public words. |

Shape of a chunk statement for one DeltaNet layer, chunk c of request r (unchanged from the first version, sizes for the real model): S_in and S_out are 48 heads x 128 x 128 at scale 2^12 with |x| < 2^18; the conv history is 3 x 10,240 pre-conv inputs; the header is (r, layer, c, token start, chunk length, handle_in, handle_out). The fields the table marks missing or outside-only must move into what the proof binds.

## Open risks

- **The handoff is not in the proof.** See "Still accepted" and the interface table. The boundary cases were run against bookkeeping on public values.
- **SB**: see the negative result. It also defines a different integer model (chunked rounding), so fidelity (#8) would have to be evaluated on that model with C fixed.
- The synthetic decay distribution is not the model's. See "Real gates".
- The conv-history relation is not proved here.
- One host, shared and loaded. Unreplicated in the ledger sense: both reviewers reran the registered SA and SB runs and report identical structural fields and rows (their PR comments, linked above), but their runs are not files in this repository. Hostile cases are sampled on one seed, not exhaustive.

## Corrections after review (2026-11-10)

| what the first version said | what is true | where |
|---|---|---|
| the chain verifier rejects 29 of 29 boundary attacks (unqualified) | 29 of 29 registered cases, 11 by a chunk proof and 18 by outside comparisons of public values; the registered chain check accepted chains outside those classes (mixed F, re-cut chunks, and with a prover-written manifest another layer, first state, dropped, truncated or missing chunks, a changed last history). Fixed; 30 of 30 named negative cases rejected in r2; two classes remain accepted by design | H2 |
| the fixed-step induction holds for an accepted chain | only with request, layer, T, C, D, F and the first handle pinned by the verifier | H2, STRATEGIES |
| SB at 2^18: 5.97M committed values per token at C = 64 | 5,973,120 is the count of the registered 2^12 arm, which failed H4. With the 2^18 widths: 7,152,768, and more costs are uncounted | Counted volumes |
| "39x below #66's 231M" | removed: different quantities on different backends | Counted volumes |
| SB on the product oracle is "no better than arm B" | 138.1M against 230.3M is about 40% lower on the stated formula | Counted volumes |
| 59-bit numerators leave 3 bits of slack to re-argue | honest runs only; second solutions for 8,192 of 8,192 M and o floors under an M1b-style range check, 65 to 67 bits at admitted edge inputs: no sound lowering here | H4 |
| R3 seed 3 fails because a fast-decaying head underflows | wrong, withdrawn: median decay 0.993, chunk-start products 1,727 to 2,472 of 4,096 at C = 64, none zero. No cause is established | H4 |
| both SB arms are closer to float64 than M1 | wrong for the registered arm: 0.0942 against M1's 0.0321 on the same run | H4 |
| the in-chunk skip violates 1,268 relations at C = 16 and 2,181 at C = 64 | the other way round: 2,181 at C = 16, 1,268 at C = 64 | H2 |
| C = 64 at D = 128 would need a 2^23 table (deviation 1) | 2^25, extrapolated from the column formula | H1 and H3 |
| prove time drops 3.8x and bytes 4.4x from C = 1 to C = 16 | n = 5 windows, indicative only; no speedup is claimed | H1 and H3 |
| proposed for M3: SB with GB = 18 at C = 64 | withdrawn | Recommendation |
| hand-entered times in the PREREG | order shown by commits; run wall-clock times were not recorded | Deviations 6 |

## Raw data

Registered run (commit 733bfe5, never modified):
- `runs/honest-C{1,16,64}.jsonl`, `runs/chain-C{1,16,64}.json` (H1, H3)
- `runs/hostile-C{1,16,64}.jsonl` (H2)
- `runs/sb-ranges.json`, `runs/sb-summary.json` (H4 registered), `runs/sb-ranges-gb{18,24}.json` and summaries (unregistered arms)
- `runs/count.json` (counted), `runs/build.json` (compiler, source hashes of seven files; `sb_ref.py` and `count.py` are not among them)

After review (unregistered, descriptive):
- `runs/honest-C{1,16,64}-r2.jsonl`, `runs/chain-C{1,16,64}-r2.json`: honest proofs made again, chains checked by the fixed verifier; each chain row holds the statement descriptor used
- `runs/hostile-C{1,16,64}-r2.jsonl`: registered classes, named negative cases, open cases; `check` is the comparison that decided, `legacy_accept` the verdict of the old check
- `runs/build-r2.json`: source hashes of ten files (now including `sb_ref.py`, `sb_summary.py`, `count.py`) and of the binary
- `runs/count-r2.json` (counted), `runs/sb-alias-gb18.json`, `runs/sb-gates-r3s3.json`, `runs/mixed-f-states.json` (reference arithmetic)
