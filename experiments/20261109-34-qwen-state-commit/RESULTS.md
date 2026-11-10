# RESULTS: 20261109-34-qwen-state-commit

Issue: #34 (tracking #32). PREREG: 0c0556e, the first commit on the branch. Base: origin/main 4f7a8761.
All numbers are **measured and unreplicated** unless they are marked **counted**. They come from one shared, loaded host and one run set, and nobody has reviewed them independently. Research security settings throughout (#19: target 10 bits, 6 work bits, deterministic toy coins). These are relation-soundness arguments, not production security.

Strategy analysis (what each strategy commits, what the verifier checks, what a cheating prover could try, and the volume formulas): [STRATEGIES.md](STRATEGIES.md). Code and reproduce commands: [research/operators/qwen_state_commit/](../../research/operators/qwen_state_commit/README.md).

## Verdict against the registered thresholds

| hypothesis | threshold | result | verdict |
|---|---|---|---|
| H1 SA honest | every chunk and chain accepted, 5/5 windows per C | C=1: 320/320 chunks, 5/5 chains; C=16: 20/20, 5/5; C=64: 5/5, 5/5 | **PASS** |
| H2 SA boundary hostile | 100% per class at C=16 and C=64 (C=1 where it applies) | C=1: 9/9, C=16: 10/10, C=64: 10/10 rejected; honest controls accepted | **PASS** |
| H3 SA volume | committed columns per token at C=16, 64 within 10% of C=1; carried = (D^2 + 9D)/C | 19,104 at all three C (0% difference); carried 1,312 / 82 / 20.5 = (1,024 + 288)/C | **PASS** (confirms H-A: SA cuts carried values only, not committed volume) |
| H4 SB reference (registered GB = F = 12) | (a) C=1 equals M1 20/20; (b) contracts 20/20 at C=16, 64; (c) drift <= 0.064 20/20; (d) numerator < 2^62 | (a) 20/20; (b) 20/20 and 20/20; (c) **19/20** at C=16 (max 0.0663) and **19/20** at C=64 (max 0.0942), both misses are R3 seed 3; (d) 53 bits | **FAIL** (c) |

By the pre-registered recommendation rule, H4 failing means the registered recommendation is **SA at C = 64**, with SB's failure reported. The registered rule is followed. The section "Recommendation" below explains why that is not the end of the story. An unregistered SB arm that changes only the precision of the decay table passes all four H4 conditions. It is reported as unregistered, and it is what this lane proposes for M3, subject to a registered re-run.

## Deviations from the PREREG

1. **D = 32 for the SA proofs**, as registered: C = 64 at D = 128 would need a 2^23 table. The per-cell count is 18.66 product columns per state cell per token at D = 32, against M1b's 17.41 at D = 128. The difference comes from the per-column sites (M, delta, o) amortised over 32 instead of 128 rows.
2. **The hostile window at C = 64 is 128 tokens (2 chunks)**, not 64. With T = 64 there is no boundary between two chunks to attack. C = 1 and C = 16 use the registered 64-token window, attacked at boundary 1.
3. **Unregistered SB arms GB = 18 and GB = 24** (the decay table G held at scale 2^GB instead of 2^F). They were added after the registered GB = 12 arm failed H4(c). They are labelled unregistered everywhere. No threshold was changed.
4. **Conv history** enters as a synthetic block of 3 taps x 3D words per head per boundary, bound in the handle. It is not proved by a conv relation. This was added after registration by the coordinator note of 2026-11-09 20:00 EST. The PREREG already listed the b5 conv-history class.
5. Perf is n = 5 windows (n = 320, 20 and 5 chunk proofs). That is below the >= 10 perf rule, as the PREREG said. No perf claim is made.

## H1 and H3: SA honest windows (D = 32, T = 64, F = 12, seeds 1..5)

Each chunk is one process, run sequentially through fp-heavy.sh and pinned to cores 0-5. The prover is single-threaded.

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

Readings. These are measured, and they carry no perf claim.
- Committed volume per token is the same at every C (19,104 core columns, 18.66 per state cell). SA moves the state from "carried" to "witness". It does not remove it. **H3: PASS.**
- Per-window prove time drops about 3.8x from C = 1 to C = 16, then stays flat. Proof bytes drop about 4.4x. That is a fixed per-proof overhead (the proximity test and the RNG digits message) being amortised, not less work. Spreads do not overlap between C = 1 and C = 16. C = 16 and C = 64 overlap in prove time.
- Peak RSS grows linearly with C (one chunk's witness). C = 64 at D = 128 would be about 16x the D = 32 table (2^25). That does not fit this harness's 2^22 limit, and it is the reason SA alone does not scale to the real head.

## H2: SA boundary-targeted hostile suite (seed 1)

| class | attack (boundary 1 unless noted) | C=1 | C=16 | C=64 | caught by |
|---|---|---|---|---|---|
| b1-wrong-state | S_in(chunk 1)[0,0] += 1, chunk proved honestly from it (and later chunks re-proved) | rejected | rejected | rejected | boundary 1: carried handle mismatch |
| b1-wrong-state | chunk 1: honest words and header, proof made from S_in[0,0] + 1 | rejected | rejected | rejected | chunk 1 proof rejected |
| b2-other-chunk-state | S_in(chunk 1) := S_in(chunk 0), proved honestly | rejected | rejected | rejected | boundary 1: carried handle mismatch |
| b2-other-chunk-state | chunk 0 replayed verbatim in slot 1 | rejected | rejected | rejected | header fields at chunk 1 |
| b3-skipped-step | chunk 1 dropped from the chain | rejected | rejected | rejected | header fields at chunk 1; token ranges do not cover T |
| b4-replayed-boundary | proof of chunk 0 presented with chunk 1's words and header | rejected | rejected | rejected | chunk 1 proof rejected |
| b4-replayed-boundary | every chunk proof of request 1 replayed under request 2 (headers and handles recomputed) | rejected | rejected | rejected | chunk 0 proof rejected |
| b5-conv-history | H_in(chunk 1)[0,0] += 1, header and proof unchanged | rejected | rejected | rejected | header handles do not match words at chunk 1 |
| b5-conv-history | H_in(chunk 1)[0,0] += 1, header recomputed and chunk re-proved honestly | rejected | rejected | rejected | boundary 1: carried handle mismatch |
| b3-skipped-step | chunk 1: witness skips token C/2 (decay 1, beta 0), complete hostile proof | n/a | rejected | rejected | chunk verifier (1268 violated relations); chunk verifier (2181 violated relations) |

**Totals:** C=1: 9/9 (window 64 tokens, 64 chunks, honest control chain accepted: True) C=16: 10/10 (window 64 tokens, 4 chunks, honest control chain accepted: True) C=64: 10/10 (window 128 tokens, 2 chunks, honest control chain accepted: True). **H2: PASS.**

Notes:
- The skipped-step attack inside a chunk does not apply at C = 1 (one token per chunk); across chunks it is the dropped-chunk attack, which runs at every C.
- Requests are distinguished only because the request id is in the header, and the header is a statement item of the chunk transcript (a proof for request 1 fails under request 2 even with recomputed handles). The same holds for layer, index and token position.
- These are sampled classes on one seed, not exhaustive. They test the chain bookkeeping and the chunk transcript binding, not an in-proof handoff (see open risks).

## H4: SB reference (D = 128, real head shape, 1,024 steps, R1..R4 x seeds 1..5, no proof)

`sb_ref.py` evaluates the chunked relation with exact integers (Python ints) and compares it to the M1 per-token integer reference and to the float64 recurrence. Drift is the maximum over the run of |S / 2^F - S_float64| (state units), and then the maximum over runs.

| arm | C | fits contracts (S, M < 2^18, delta two-limb) | equals M1 at C=1 | drift max | drift median | drift <= 0.064 | max numerator bits | max abs S |
|---|---|---|---|---|---|---|---|---|
| GB=12 (registered) | 1 | 20/20 | 20/20 | 0.0321 | 0.0080 | 20/20 | 53 | 125,548 |
| GB=12 (registered) | 16 | 20/20 | n/a | **0.0663** | 0.0042 | **19/20** | 53 | 70,474 |
| GB=12 (registered) | 64 | 20/20 | n/a | **0.0942** | 0.0034 | **19/20** | 53 | 48,279 |
| GB=18 (unregistered) | 16 | 20/20 | n/a | 0.0206 | 0.0018 | 20/20 | 59 | |
| GB=18 (unregistered) | 64 | 20/20 | n/a | 0.0130 | 0.0014 | 20/20 | 59 | 48,608 |
| GB=24 (unregistered) | 16 | 20/20 | n/a | 0.0204 | 0.0018 | 20/20 | **65** | |
| GB=24 (unregistered) | 64 | 20/20 | n/a | 0.0120 | 0.0014 | 20/20 | **65** | 48,613 |

At C = 1, GB does not matter (G = 2^GB on the diagonal only): every arm equals M1.

What failed and why. The registered arm keeps the decay products G[t][s] at 2^F = 2^12, and the product of up to 64 decays is floored at every step. For fast-decaying heads (R3 seed 3), G[t][0] underflows to a few ulps, and the relative error of the chunk-start term grows with C. GB = 18 removes this. Its drift is lower than per-token M1 rounding: chunked rounding floors once per chunk instead of once per token. GB = 24 adds nothing over 18 and breaks the no-wrap bound (65 > 62 bits). **GB = 18 is the proposed SB arm**: 59-bit numerators leave 3 bits of slack under 2^62. That slack must be re-argued with RNG's 32x approximate bound on M and delta (2^5 more on the delta terms). That is the main open risk of SB.

SB versus M1 integer values. SB is a different integer model from M1 (it rounds once per chunk). At C = 64 its state differs from M1's integer state by at most 343 ulps (registered arm) or 80 ulps (GB = 18), both closer to float64 than M1 is. **The chunk size C is therefore part of the model definition and must be fixed in the commitment.** It is not a prover choice.

## Counted volumes (full Qwen3.8-27B, 48 DeltaNet layers x 48 V heads, D = 128; counted, not measured)

From `count.py` (`runs/count.json`). The formulas are in STRATEGIES.md.

| strategy | C | committed values per token | carried values per token (state + conv) | per 1,024-token window committed |
|---|---|---|---|---|
| S0 / SA / SC, #66 arm B (6.1 per cell) | any | 230.3M | 39.2M / C | 235.8B |
| S0 / SA / SC, M1b (17.41 per cell) | any | 657.2M | 39.2M / C | 673.0B |
| SB, sumcheck-matmul backend | 16 | 11.0M | 2.45M | 11.3B |
| SB, sumcheck-matmul backend | **64** | **5.97M** | **0.61M** | **6.12B** |
| SB, sumcheck-matmul backend | 128 | 5.46M | 0.31M | 5.59B |
| SB on the research product oracle (every multiply a gate) | 64 | 138.1M | 0.61M | 141.4B |
| SD sumcheck over time | T = 1,024 | 9.84M | 0.04M | 10.1B |

Conv history: 30,720 words per layer per boundary, 1.47M for the model, 3.9% of the 37.75M state values per boundary.

## Recommendation

1. **Boundary interface (all strategies): commit (S, conv history) per DeltaNet layer at chunk boundaries only.** Bind them in one handle with request id, layer, boundary index and token position. Make the chunk header a transcript statement item of the chunk proof. This handles every boundary attack class run here (H2). The handoff must commit **both** S (48 x 128 x 128 per layer) and the 3-token conv history (3 x 10,240 per layer). History alone is not tied by the conv gadget (#67, unreviewed draft).
2. **Registered recommendation (rule followed): SA at C = 64.** It is measured and passes H1 to H3. It reduces carried values to 0.61M per token. It does **not** reduce committed volume (230M per token at arm B).
3. **Proposed for M3, unregistered evidence: SB with GB = 18 at C = 64.** It gives 5.97M committed values per token (counted, sumcheck-matmul backend), 39x below #66's 231M, with 0.61M carried. It passes all four H4 conditions in the unregistered arm. C = 64 is the Transformers chunk size (modeling_qwen3_5.py chunked path) and is near the formula's optimum (C ~ 140 gives 5.4M). C = 128 saves only 9% more and doubles the per-chunk C^2 terms and the chunk witness. Condition: a registered re-run of H4 at GB = 18, and an SB chunk proof (M3a), before this is adopted.
4. SC (checkpoint and recompute) is the prover's memory schedule for either strategy, not a separate commitment. SD is not recommended: its forward-substitution soundness is open and its T^2 term grows with the request.

## Interface for the M3 design lane

A chunk statement for one DeltaNet layer, chunk c of request r, tokens [64c, 64c + 64):

- **In, carried by commitment from chunk c-1:** S_in (48 heads x 128 x 128, |x| < 2^18, scale 2^12) and H_in (3 x 10,240 conv inputs, the last 3 tokens before 64c). At c = 0 these are zero, or the previous request's handle.
- **In, this chunk:** the layer inputs of the 64 tokens (committed, from the previous segment) and the committed weights.
- **Out:** the layer outputs of the 64 tokens (committed, to the next segment), and S_out and H_out (the last 3 tokens' pre-conv inputs), committed and carried.
- **Header in the transcript:** (r, layer, c, 64c, C = 64, handle_in, handle_out).
- **Verifier, per boundary:** handle_out(c) = handle_in(c+1). Indices 0..n-1. Token ranges contiguous, covering T. A final chunk of fewer than 64 tokens needs C as a header field (it is one already).
- **Inside (SB):** P0 = S_in^T K, Q0 = S_in^T Q, Gram K K^T and Q K^T, the decay table G at 2^18, per-token M, delta (two limbs), o with exact remainder keys, S_out accumulation. Matrix products by sumcheck in the main prover.

## Open risks

- **The handle is a stand-in.** Here S and H are public words and the handle is SHA-256 recomputed by the chain verifier. M3 needs the in-proof version: the next chunk's proof reads chunk c's S_out cells from the same commitment (kept row or shared oracle). The boundary attacks were run against the bookkeeping, not against that handoff.
- **SB has no proof yet.** Its soundness sketch (STRATEGIES.md) assumes exact remainder checks and a no-wrap bound. With RNG's approximate 2^23 bound on M and delta, the 59-bit honest numerators may exceed 2^62. That needs a bound argument or a narrower GB.
- **SB's gain needs a sumcheck-matmul backend** for P0, Q0 and the S_out accumulation. On this repo's research product oracle, SB costs 138M per token, no better than arm B.
- **SB defines a different integer model** (chunked rounding). Fidelity (#8) must be evaluated on that model with C fixed at 64. A different C gives different outputs.
- The GB = 12 failure is driven by one heavy-tailed run (R3 seed 3). The synthetic decay distribution is Mamba2-style init, not measured Qwen gates. Real abliterated-weight gate statistics may be harsher.
- The conv-history relation itself is not proved here. #67 is an unreviewed draft.
- One host, shared and loaded. Unreplicated. Hostile classes are sampled, not exhaustive.

## Raw data

- `runs/honest-C{1,16,64}.jsonl`, `runs/chain-C{1,16,64}.json` (H1, H3)
- `runs/hostile-C{1,16,64}.jsonl` (H2)
- `runs/sb-ranges.json`, `runs/sb-summary.json` (H4 registered), `runs/sb-ranges-gb{18,24}.json` and summaries (unregistered)
- `runs/count.json` (counted), `runs/build.json` (compiler, source hashes)
