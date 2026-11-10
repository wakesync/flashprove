# Recurrent-state commitment strategies for Qwen3.8-27B Gated DeltaNet (issue #34)

Analysis document for experiment 20261109-34-qwen-state-commit. What was measured is in RESULTS.md. Everything in this file that is not cited to a run is **analysis or a count, not a test**.

Corrected on 2026-11-10 after two independent reviews of PR #71 ([astra](https://github.com/wakesync/flashprove/pull/71#issuecomment-6758363867), [opus](https://github.com/wakesync/flashprove/pull/71#issuecomment-6758460446)). Summary of the corrections: the SA induction needs the statement pinned by the verifier; the SB counts were at the wrong widths for the 2^18 arm and are for a proof and a backend that do not exist; the 2^18 arm has no sound lowering here; no ratio against the per-token count is given. The list is at the end of RESULTS.md.

## Setting and notation

One Gated DeltaNet V head carries a state S in Z^{D x D}, D = 128, at scale 2^F, F = 12. Per token t (M1 relation, `research/operators/qwen_deltanet/README.md`):

```
P = S^T k,   M = floor(a P / 2^2F),   delta = floor((v - M) beta / 2^F)
S' = floor((a S + k delta^T) / 2^F),  o = floor(S'^T q / 2^F)
```

Qwen3.8-27B (FEASIBILITY.md section 1): L = 48 DeltaNet layers, H = 48 V heads per layer. T tokens per request, chunk size C. Besides S, every DeltaNet layer carries the **causal conv history**: the last 3 pre-conv in_proj_qkv outputs over 10,240 channels, so 30,720 words per layer per boundary (coordinator note 2026-11-09 20:00 EST; the operators lane's draft PR #67, unreviewed, reports that its conv gadget does not bind this history to the previous chunk). Per head that is 30,720 / 48 = 640 words, 3.9% of the head's 16,384 state cells.

"Committed" below means a value the prover places in a committed oracle (product oracle cell, range cell, lookup key, or matrix output). "Carried" means a value that must be bound across a chunk boundary from one chunk statement to the next.

w_cell is the per-token relation's committed cells per state cell per token: 18.66 measured in this experiment's SA chunks (D = 32), 17.41 measured for M1b at D = 128 (#63), 6.1 counted for #66 arm B (lookup-exact remainders). The difference between 18.66 and 17.41 is the per-column sites (M, delta, o and their remainder bits) amortised over D = 32 instead of 128.

## Comparison table

Committed and carried values per token, full model (48 x 48 heads). Formulas per head; full-model numbers from `runs/count.json` (counted, not measured). Conv history included in "carried".

| strategy | committed per token per head | carried per token per head | full model committed per token (C) | full model carried per token (C) | status |
|---|---|---|---|---|---|
| S0 per-token commit | w_cell D^2 | D^2 + 640 | 230M (arm B) / 657M (M1b) | 39.2M | measured shape (= SA at C = 1) |
| SA boundary commit, state as witness | w_cell D^2 (independent of C) | (D^2 + 640) / C | 230M / 657M at every C | 2.45M (16), 0.61M (64) | **measured** at D = 32, C = 1, 16, 64 |
| SB chunked low-rank, decay table at 2^12 (the registered arm, which FAILED H4), matmul-sumcheck backend | 3 D^2 / C + 13 D + 2.5 C + 0.5 | (D^2 + 640) / C | 11.0M (16), 5.97M (64), 5.46M (128) | 2.45M (16), 0.61M (64) | integer reference measured, registered arm failed; **no proof, and no such backend in this repository** |
| SB, decay table at 2^18 (unregistered), remainder keys widened only | 4 D^2 / C + 15 D + 2.5 C + 0.5 | (D^2 + 640) / C | 13.95M (16), 7.15M (64), 6.34M (128); more costs uncounted | same | unregistered reference run; **no sound lowering here, no proof, no backend** |
| SB on this repo's product-oracle backend (every product term a gate) | 3 D^2 + D C + SB | (D^2 + 640) / C | 129M (16), 138M (64) at 2^12; 132M, 139M at 2^18 | same | counted; no SB proof built |
| SC checkpoint and recompute | as SA | as SA | as SA | as SA | analysis only |
| SD sumcheck over time | SB with C = T | (D^2 + 640) / T | 9.84M at T = 1,024 | 38K | analysis only |

The number #66 asks M3 to beat is 231M committed values per token (arm B, 48 layers, on the research product oracle). SA does not beat it at any C, by construction of its per-token lowering. For SB no ratio is given: its 5.97M (2^12 arm) and 7.15M (2^18 arm) are value counts for a proof that does not exist, on a matmul-sumcheck backend this repository does not have, and they cover the state mixer only. Dividing them into a column count on the product oracle compares two different quantities. On the product oracle itself the stated SB formula gives 138M at C = 64, about 40% below 230M; that is also a count, not a built proof.

Every count in this file is for the DeltaNet state mixer only (48 layers x 48 V heads, one count per committed value). The M3 counting model of draft PR #70 counts a different quantity (the whole model, entries packed from byte limbs, with an overhead factor, and its own low-rank construction). Neither is a complete count of an SB proof and the two must not be compared number to number.

## S0: commit the state every token (baseline)

- **Prover commits:** every S_t (D^2 cells per head per token), plus the per-token witness (memory read, delta, remainders) in one oracle per token or per segment.
- **Verifier checks:** every per-token statement, and that the output state of token t is the input state of t+1 (a kept-row handoff, `blocks/toy/segments.h`, or the same oracle).
- **Cheating prover could try:** a state cell changed between tokens (continuity), a skipped token, a replayed token statement. All of these are the boundary attacks of SA at C = 1 (RESULTS.md H2, C = 1 arm).
- **Volume:** carried D^2 + 640 per head per token, 39.2M per token for the full model, 40.2B per 1,024-token window (37.7M state + 1.47M conv per token; FEASIBILITY.md's 38.7B is the state only).
- **Fit:** fits the existing machinery directly (M1b is exactly one S0 step at T = 1 per statement, or T tokens per statement). Too large for one host at T = 1,024 (FEASIBILITY.md section 3).

## SA: commit only at chunk boundaries, intra-chunk state as witness

- **Prover commits:** S_in and S_out of each chunk as carried values (handles), plus the C intra-chunk states as witness cells of the chunk's own oracle.
- **Verifier checks:** each chunk statement (the M1 relation at every one of the C steps, last state = S_out); handle(S_out, H_out of chunk c) = handle(S_in, H_in of chunk c+1); chunk 0 starts at the registered initial handle; indices and token ranges contiguous. **And, since the review fix, against a statement the verifier itself holds:** request, layer, window length T, chunk size C (every chunk exactly C tokens, a declared short last chunk), head size D, fixed-point bits F of every chunk, and the first-chunk handle.
- **Soundness sketch, and its condition.** Fix a chain of n accepted chunks. By chunk soundness (M1b relation soundness: unique floors, no wrap, RNG bound; `research/operators/qwen_deltanet_lookup/README.md`), each chunk's (S_in, S_out) satisfies S_out = Step_c(S_in; inputs), where Step_c is **the step of that chunk's own fixture**: its F, its D and its number of tokens. The chunk proof binds whatever relation is derived from each fixture; it does not make two chunks use the same integer model. By binding of the handle (collision resistance of SHA-256 in the stand-in; binding of the oracle commitment in M3), S_in(c+1) = S_out(c) and H_in(c+1) = H_out(c). The induction "S_out(n-1) = Step^T(S_0) for the one registered Step" therefore holds **only if the verifier pins F, D, the chunk policy C, the window length T, request, layer and the first handle**, from a statement that does not come from the prover. The chain check of the registered runs did not: it accepted a chain whose middle chunk was proved at F = 13, a chunk re-cut into smaller chunks, and, because it read the manifest the prover writes, another layer, another first state, and dropped, truncated or missing chunks (both reviews of PR #71; reproduced in `runs/hostile-C*-r2.jsonl` with the old check next to the fixed one). The fixed `window.chain_check` pins them and rejects all of these. The induction still says nothing about the token inputs (public words, bound to nothing) or about a state that is hidden. The handle includes request id, layer, boundary index and token position, so a handle from another request, layer or position is a different string; a proof replayed under another header fails because the header is a transcript statement item.
- **Cheating prover could try:** wrong carried state (b1), a state from another chunk (b2), a skipped step inside or across chunks (b3), a replayed boundary handle (b4), an inconsistently replaced conv history (b5). All five registered classes were run (RESULTS.md H2). Also, found by the reviews: another F for some chunks, another chunk split, a prover-chosen layer, first state or window length, a changed last-chunk history (rejected by the fixed verifier, r2), and replaced token inputs or a conv history changed consistently on both sides of a boundary (**still accepted**, by design of this harness).
- **Volume:** carried (D^2 + 640)/C per head per token. Committed volume is unchanged: the intra-chunk states are still committed cells, only not carried. In this harness: 19,104 core columns per token at C = 1, 16 and 64 (D = 32), because `chunk.cpp` emits the same columns for every token whatever the chunk length. That is a property of this lowering by construction, not a measured property of SA. So SA alone does not solve #34's volume problem; it solves the **host-memory** problem only if chunks are proved and dropped one at a time (streaming), and the carried handle volume.
- **Fit:** no new gadget. The chunk header is one transcript statement item. In M3 the handle becomes the chunk's S_out cells as a kept row read by the next chunk's segment.

## SB: chunked low-rank (WY / UT) form inside the chunk

- **Integer relation (this lane's research contract, `research/operators/qwen_state_commit/sb_ref.py`).** For a chunk with input state S_0 and tokens 1..C: staged decay products G[t][s] (G[t][t] = 2^GB, G[t][s] = floor(G[t-1][s] a_t / 2^F)); the chunk-start reads P0_t = S_0^T k_t and Q0_t = S_0^T q_t (exact matrix products); then one floor per value from an exact accumulation:
  - M_t = floor((2^F G[t][0] P0_t + sum_{s<t} G[t][s] (k_t . k_s) delta_s) / 2^(2F+GB))
  - delta_t = floor((v_t - M_t) beta_t / 2^F)
  - o_t = floor((2^F G[t][0] Q0_t + sum_{s<=t} G[t][s] (q_t . k_s) delta_s) / 2^(2F+GB))
  - S_out = floor((2^F G[C][0] S_0 + sum_s G[C][s] k_s delta_s^T) / 2^(F+GB))

  GB is the scale of the decay table: GB = F = 12 is the registered arm (it failed H4(c)); GB = 18 and 24 are unregistered arms.

  This is not the M1 per-token relation (it rounds once per chunk instead of once per token), so it defines a different integer model; at C = 1 it is bit-identical to M1 for M, delta and S (measured, 20/20). The intra-chunk delta recursion is a forward substitution through the strictly lower-triangular decayed Gram matrix (the UT transform), done with integer floors per token; there is no division by data.
- **Prover commits:** S_out (carried), per token P0, Q0, M, delta (two limbs), o and their remainder keys; per chunk the decay table G and the Gram matrices K K^T, Q K^T (C^2 each). The intra-chunk states S_1..S_{C-1} are never materialised.
- **Verifier checks:** the chunk statement (the products P0 = S_0^T K and Q0 = S_0^T Q and the S_out accumulation K^T diag(G) Delta are matrix products, proved by sumcheck against the committed S_0 and the committed K, Q, Delta; the floors by range-checked remainders), the boundary handle chain as in SA.
- **Soundness sketch, and where it fails.** Each floor has a unique (quotient, remainder) pair if the remainder is range-checked exactly, the quotient is confined to a window smaller than p divided by the divisor, and no relation wraps the field. The forward substitution means delta_t depends only on delta_{<t}, so given S_0 and the inputs every committed value would then be determined, by induction on t. **These conditions are not met by an M1b-style lowering of the unregistered 2^18 arm.** Its M and o floors divide by 2^42 while the range check proves only |quotient| < 2^23: quotient + 2^22 with a shifted remainder satisfies the same field relation, for 8,192 of 8,192 M floors and 8,192 of 8,192 o floors of two real SB chunks (`runs/sb-alias-gb18.json`). The registered 2^12 arm (divisor 2^36) and a 2^15 table (2^39) have no such second solution in that test. No-wrap is not established either: honest runs reach 53 bits (2^12 arm) and 59 bits (2^18 arm), but inputs that pass the public admission reach 65 to 67 bits at 2^18, and interval bounds over the admitted ranges are 85 to 97 bits (same file). A sound lowering needs an exact quotient range tied to the divisor, proved operand bounds (for example norms of k and q) or multi-word relations. None is specified here. The boundary argument is SA's, with SA's condition.
- **Cheating prover could try:** everything SA's prover could, plus: a wrong Gram entry (k_t . k_s) (caught if the Gram matrix is a proved product of the committed K), a wrong decay product G (G is a public function of the public a_t in M2-style statements, or a small proved table in M3), using the M1 per-token rounding on some tokens and the chunk rounding on others (rejected because the relation fixes one numerator per value), and choosing a chunk split that changes the integer outputs (the chunk boundaries must be part of the model definition, not a prover choice: **C is a model parameter**, fixed in the commitment).
- **Volume (counted, for a proof that does not exist):** at the registered 2^12 table, 3 D^2/C + 13 D + 2.5 C + 0.5 values per head per token under a matmul-sumcheck backend; the D^2/C term is S_out plus its two remainder keys. That is 5.97M per token for the 48 x 48 heads at C = 64, and it belongs to the arm that failed H4. At a 2^18 table the remainders are 30 and 42 bits, so the same 12-bit-key layout gives 4 D^2/C + 15 D + 2.5 C + 0.5: 7.15M at C = 64 (`runs/count-r2.json`). Not in either formula: the floors that define the decay table, the operands when they are committed, quotient range checks, whatever a sound 2^18 lowering needs, and all sumcheck, lookup and commitment overhead.
- **Fit:** needs a matrix-product sumcheck over committed operands, which FlashProve's main prover has (the matmul segments of docs/model.md sections 5-7), but **this repo's research product oracle does not**: on the product-oracle backend every multiply-add is a committed gate and the stated formula gives 129M to 138M per token (counted), about 40% below the 230M per-token count at C = 64 and nowhere near the matmul-sumcheck count. So any larger gain of SB depends on M3 lowering P0, Q0 and the S_out accumulation as matrix products in the main prover, which is not built for this relation.

## SC: checkpoint and recompute (analysis only, not tested)

- **What it is:** a prover-side schedule. The prover keeps only the boundary states in memory and regenerates the C intra-chunk states from the checkpoint when it proves that chunk.
- **Prover commits:** exactly what SA commits; the saving is prover memory (it holds one chunk's trace at a time), not committed volume or proof size.
- **Verifier checks / attacks:** identical to SA.
- **Volume:** SA's. Memory: one chunk's witness plus the checkpoints, (T/C) D^2 per head for checkpoints.
- **Fit:** compatible with SA and SB; it is how the GPU prover would stream either. Recommended as the prover schedule, not as a commitment strategy.

## SD: sumcheck over time (analysis only, not tested)

- **What it is:** SB with C = T. The whole request is one chunk; the output o_t is written in the decayed linear-attention form o = (Q K^T odot Gamma) Delta + diag(G[.,0]) Q S_0, and every product is reduced by sumcheck over the token axis and the head dimension. The state is never materialised except S_0 (zero at sequence start) and S_T (if carried to a next request).
- **Prover commits:** per token M, delta, o and remainder keys (13 D) plus the T x T decay and Gram matrices (2.5 T per token): the T^2 term dominates for long requests (at T = 1,024: 2,560 per head per token vs 1,664 for the D-terms).
- **Verifier checks:** one statement per layer and request. Delta is defined by a lower-triangular system, so its sumcheck must be a sequence of T dependent claims (delta_t needs delta_{<t}) or a proved triangular solve; a single batched sumcheck does not capture the forward substitution. **This is the open soundness question of SD.**
- **Cheating prover could try:** a delta vector that satisfies the batched (random-linear-combination) form but not the sequential floors; mitigated only if every delta_t floor is range-checked individually, which brings back the 13 D per token.
- **Volume:** 9.84M per token at T = 1,024 (counted); grows linearly with T because of the T x T matrices, so it is worse than SB at C = 64 to 128 beyond about T = 300 (counted, from the formula).
- **Fit:** no existing gadget; needs a triangular-solve argument. Not recommended for M3.

## The carried conv history

| strategy | conv words carried per boundary per layer | how it is bound |
|---|---|---|
| S0 | 30,720 every token (or none if conv is proved within one statement covering consecutive tokens) | same handle as S |
| SA / SB / SC | 30,720 per chunk boundary, i.e. 30,720 / C per token | in the boundary handle together with S: handle = H(request, layer, boundary index, token position, S, conv history). Tested here with the stand-in hash for inconsistent replacements only (b5); a history changed consistently on both sides of a boundary is accepted |
| SD | 30,720 per request boundary | same handle, per request |

The conv history volume is small (3.9% of S) and does not change the ranking. What matters is that it must be **in the same handle as S**, with the same index and position fields: the operators lane found that a chunk's conv gadget alone accepts a replaced history (draft PR #67, unreviewed). In this experiment an inconsistent history change is caught at the boundary (b5a: words changed, handle not; b5b: history changed and the chunk honestly re-proved with a recomputed header, which breaks the carried-handle equality with the previous chunk), and since the review fix the last chunk's history is compared with the statement. A matching hash on both sides does not prove that the history is the last three real inputs: with both sides changed together the chain is accepted (`runs/hostile-C*-r2.jsonl`, open case). That needs the conv relation and a commitment to the layer inputs.
