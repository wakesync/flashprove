# PREREG: 20261109-34-qwen-state-commit
Issue: #34. Lane: qwen-state-commit (Qwen recurrent-state commitment strategy). Date (UTC): 2026-11-10 01:20. Base commit: 4f7a876151c309f0159e88b18c8e286d4e1909c9 (origin/main). Read, not depended on: PR #66 DESIGN.md at 8ec7c799 (unmerged), PR #67 operators write-up (unmerged, unreviewed draft).

Inputs read before registration: issue #34, research/ports/qwen3.8-27b/FEASIBILITY.md, research/operators/qwen_deltanet (M1) and qwen_deltanet_lookup (M1b) code and RESULTS, #66 DESIGN.md sections 0 and 6, docs/protocol.md section on segments. No code for this experiment existed or ran before this file was committed.

Research security level throughout: the #19 research settings (Goldilocks, target 10 bits, 6 work bits on QUERY, deterministic toy coins). Relation soundness of a construction, not production security.

## Strategies compared

Notation: T tokens, chunk size C (T/C chunks), H = 48 V heads per layer, L = 48 DeltaNet layers, D = 128 (state D x D per head), F = 12. Conv history: 3 taps x 10,240 channels per layer (coordinator note 2026-11-09 20:00 EST, from unreviewed draft PR #67: the conv gadget does not tie its history to the previous chunk).

- **S0 per-token commit (baseline).** Every S_t is a committed cell set and a carried handle. Proof per token.
- **SA boundary commit, state as witness.** One statement per chunk of C tokens, in the M1b relation. Boundary states S_in, S_out (and the conv history) are the only carried values. Intra-chunk states are witness cells of the chunk's product oracle.
- **SB chunked low-rank (UT form).** One statement per chunk. Inside the chunk the state is never materialised: delta, M, o are computed from S_in, the chunk's k, q, v, the decay products gamma[t,s] and the Gram matrices K K^T, Q K^T, by one floor per value from an exact in-chunk integer accumulation. S_out = floor((G_C S_in 2^F + sum_s gamma[C,s] k_s delta_s^T) / 2^2F). At C = 1 this is exactly the M1 relation for M, delta and S.
- **SC checkpoint and recompute.** Analysis only: commit checkpoints every C, prover regenerates the intra-chunk trace when proving. Not tested.
- **SD sumcheck over time.** Analysis only: SB with C = T (decayed linear-attention form proved by sumcheck, no state materialised after S_0). Not tested.

For each: what the prover commits, what the verifier checks, what a cheating prover could try, the volume formula, and conv-history binding, written in RESULTS.md.

## Hypothesis
(H-A) Under SA in the M1b machinery, committed product cells per token do not fall with C (the intra-chunk state is still committed witness); only the carried handle volume falls, as D^2/C per head. (H-B) SB at the real head shape keeps every committed quotient inside the M1b range contracts at C = 16 and 64 and equals M1 at C = 1, so its committed volume per token is O(D^2/C + D + C) per head under a sumcheck-matmul backend.

## Metric
CPU experiment (SA), on the M1b statement shape (relation, lowering and RNG/LKP composition of research/operators/qwen_deltanet_lookup, unchanged) with the head shrunk to D = 32 so that C = 64 fits a 2^21 table (registered deviation from 128 x 128; the per-cell counts scale as D^2 and are checked against the M1b 128 count). Window of T = 64 tokens split into chunks of C in {1, 16, 64}. Per chunk proof: accept, relations, product columns used, range cells, log-length, proof bytes, prove s, verify s, peak RSS. Per window: sums of the above, committed product columns per token, carried handle values per token (S_out cells + conv history words).
Chain verifier (stand-in for the in-proof kept-row handoff, labelled as such): each chunk's public words include S_in, S_out, the conv history H_in, H_out, and a header (request id, layer, chunk index, token start, C). The handle of a boundary is SHA-256 over the canonical words of (request id, layer, boundary index, token position, S, H). The chain verifier accepts iff every chunk proof verifies against relations it derives from that chunk's words, handle(S_out, H_out of chunk c) == handle(S_in, H_in of chunk c+1), chunk 0 starts from the registered initial handle, indices are 0..n-1 and token ranges are contiguous and cover T.
Reference experiment (SB): numpy integer reference of SB at D = 128 (real head), M1 token generator (research/operators/qwen_deltanet/reference.py), R1..R4 x seeds 1..5, 1,024 steps, C in {1, 16, 64}: max |S|, |M|, |delta|, |o|, max bits of every in-chunk numerator, max divergence of S from the float64 recurrence, and bit equality of M, delta, S with M1 at C = 1.
Counted (not measured): committed values per token for the full model under S0, SA, SB (two backends: this harness's product oracle, and a sumcheck matmul backend that commits matrix outputs only), SC and SD; conv-history volume per boundary.

## Acceptance threshold
- H1 (SA honest): every chunk proof of every honest window accepted and the chain verifier accepts, 5/5 windows at each C.
- H2 (SA boundary hostile): 100% rejection per class, at C = 16 and C = 64 (and C = 1 where the class applies): b1 wrong carried state (S_in of chunk c+1 = honest + 1 in one cell, proved honestly from it; and the honest-handle variant where the words say S_out(c) but the proof was made from the tampered state); b2 state from another chunk (S_in(c+1) := S_out(c-1), or chunk 0's S_in at c = 0 of the 64-window); b3 skipped step (inside a chunk: one token's state set to the previous state in the witness, complete hostile proof with true local targets; across chunks: a chunk dropped, ranges not contiguous); b4 replayed boundary handle (a valid chunk proof and handle replayed at another chunk index, and from another request id); b5 replaced conv history (H_in(c+1) != H_out(c), chunk proof otherwise honest).
- H3 (SA volume): committed product columns per token at C = 16 and 64 within 10% of C = 1's; carried handle values per token equal (D^2 + 9D)/C exactly (S cells plus the 3-tap history of the head's q, k, v channels).
- H4 (SB reference): (a) C = 1 equals M1 for M, delta, S in 20/20 runs; (b) at C = 16 and 64, |S|, |M| < 2^18 and delta fits the M1b two-limb contract in 20/20 runs each; (c) max |S - S_float| over the run <= 0.064 (twice M1b's measured worst 0.032) in 20/20; (d) the max in-chunk numerator is below 2^62 (so honest relations fit Goldilocks without wrap; the RNG slack question is reported, not thresholded).
Recommendation rule (fixed now): if H4 passes, recommend SB with the C in {16, 64} that minimises counted committed values per token for the full model under the sumcheck backend at T = 1,024; if H4 fails, recommend SA at C = 64 and report SB's failure. SC and SD are compared on paper only.
Prove and verify times are descriptive (no threshold).

## Kill criterion
Shrink and say so if peak RSS of any chunk proof exceeds 8 GB, or the plan is refused at C = 64 (fall back to D = 16). If no honest SA chunk proof is accepted by 2026-11-10 02:45 UTC, publish the SB reference and the counts as the deliverable and mark SA KILLED. Lane time box ends 2026-11-10 04:08 UTC; whatever is unrun then is listed as not run.

## Runs
SA: 5 windows (seeds 1..5, R1, 64-token warm-up at D = 32) per C; C = 1 gives 320 chunk proofs, C = 16 gives 20, C = 64 gives 5. Sequential, one process per chunk, through fp-heavy.sh, taskset -c 0-5. Report n, median, SD, min, max per chunk and per window. First process included. Perf is descriptive (n = 5 windows, below the >= 10 perf rule; no perf claim is made). Hostile: window seed 1, one run per attack. SB: 20 runs per C, deterministic. Exclusions only for host faults, rerun and reported. Host is a shared loaded VM.

## Prior art
- This repository: M1 (#47) and M1b (#63) define the relation and machinery; FEASIBILITY.md section 2 gives the per-token and chunk-64 volume estimates (37.7M cells per token, 0.60B per 1,024-token window); #66 DESIGN.md section 6 counts 231M committed values per token for 48 layers (arm B) and lists committed state as M3's job; blocks/toy/segments.h is the kept-row handoff between segments that the stand-in handle models; docs/protocol.md (segments fold their commitments into a carried short commitment).
- Literature: the chunkwise parallel form of DeltaNet with the WY / UT representation (Yang, Wang, Zhang, Shen, Kim, NeurIPS 2024, "Parallelizing linear transformers with the delta rule over sequence length"; Gated DeltaNet, Yang, Kautz, Hatamizadeh, ICLR 2025), the Transformers reference chunked form (modeling_qwen3_5.py L287-421, chunk 64). Checkpoint and recompute: gradient checkpointing (Chen et al. 2016) and IVC / folding style accumulation (Nova, Kothapalli, Setty, Tzialla 2022). Sumcheck over time: matrix-product sumchecks (Thaler 2013), zkLLM's tlookup / zkAttn (CCS 2024) for attention. As far as we found, no zkML system proves a gated delta-rule state across chunks; zkLLM, EZKL, Jolt, Expander target stateless transformers.

## Amendments
(empty at registration)

- A1 (2026-11-10 02:00 UTC, after code). The hostile window at C = 64 is 128 tokens (2 chunks), because a 64-token window has no chunk-to-chunk boundary to attack. C = 1 and 16 keep the 64-token window. Thresholds unchanged.
- A2 (2026-11-10 01:50 UTC, after the registered SB arm failed H4(c)). Added unregistered SB arms with the decay table at 2^18 and 2^24 (`sb_ref.py --gb`). They are reported as unregistered and do not change the registered verdict or the recommendation rule.
- A3 (2026-11-10 02:30 UTC). Coordinator note 2026-11-09 20:00 EST: the carried conv history (3 x 10,240 per layer) is included in the volume formulas and in the handle. It was already in the b5 class and the H3 carried formula (9D per head = 3 taps x 3D channels). No threshold changed.
