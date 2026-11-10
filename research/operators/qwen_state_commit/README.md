# Qwen DeltaNet recurrent-state commitment, chunk statements (issue #34, research only)

Experiment, pre-registration and verdict: [experiments/20261109-34-qwen-state-commit/](../../../experiments/20261109-34-qwen-state-commit/). Strategy comparison and recommendation: that directory's RESULTS.md. Research security settings only (#19: Goldilocks, target 10 bits, 6 work bits, deterministic toy coins). Nothing here is a serving protocol.

## What is in this directory

| file | what it is | measured or counted |
|---|---|---|
| `chunk.cpp` | One chunk statement of strategy SA (state committed at chunk boundaries only). The M1b relation and RNG/LKP composition (`../qwen_deltanet_lookup/`, PR #63), copied unchanged, plus a chunk header bound into the transcript under its own label. Modes `prove`, `verify`, `hostile-skip`. | proofs are measured |
| `window.py` | Builds a window of T tokens at D = 32, splits it into chunks of C, writes each chunk's public words, header and conv-history words, and holds the **chain verifier** (`chain_check`). | |
| `record.py` | Runs the honest windows (C = 1, 16, 64; seeds 1..5) and the boundary-targeted hostile suite. Writes `runs/`. | measured |
| `sb_ref.py`, `sb_summary.py` | Integer reference of strategy SB (chunked low-rank / UT form) at the real head shape D = 128 over 1,024 steps; range and drift study. No proof. | measured (reference arithmetic) |
| `count.py` | Volume formulas for every strategy at Qwen3.8-27B shapes. | **counted, not measured** |

## What is proved (SA chunk statement)

For one head of size D x D and a chunk of C tokens, given public S_in, the per-token a, beta, k, v, q, the outputs o and S_out: the prover knows intra-chunk states S_1..S_{C-1}, memory reads M, deltas and floor remainders such that the M1 staged-floor recurrence holds at every token and the last state equals S_out. This is the M1b statement with T = C; the intra-chunk states are committed witness cells of the chunk's product oracle.

The chunk header (request id, layer, chunk index, token start, C, D, the handle of (S_in, H_in) and the handle of (S_out, H_out)) is a statement item of the chunk's transcript (label `0x46505343`), so a chunk proof does not verify under another header.

## What the verifier recomputes

- Chunk verifier (`chunk.bin verify`): decodes the chunk's public words, derives every relation from them, runs the unchanged M1b verifier under the chunk label with the header bound.
- Chain verifier (`window.chain_check`): for every chunk in order, recomputes the boundary handles from the words (S, conv history H, request, layer, boundary index, token position), checks them against the header, checks that chunk c's input handle equals chunk c-1's output handle (chunk 0: the registered initial handle), that indices run 0..n-1, starts are contiguous and lengths sum to T, and that every chunk proof verifies.

## What is NOT covered

- **The handle is a stand-in.** Here S_in, S_out and H are public words and the handle is SHA-256 of them, recomputed by the chain verifier. In M3 the state is not public: the carried value must be a commitment that the next chunk's proof opens inside its own oracle (a kept row read by the next segment, as in `blocks/toy/segments.h`). This experiment tests the chain bookkeeping and the boundary attacks against it, not that in-proof handoff.
- **Conv history is bound, not proved.** H is a block of 3 taps x 3D synthetic words per boundary. Its relation (the four-tap conv) is the operators lane's gadget (draft PR #67, unreviewed), which per that lane does not tie its history to the previous chunk. Here only the binding of H across the boundary is tested.
- D = 32, not 128 (so that C = 64 fits a 2^21 table). Per-cell counts are compared to M1b's D = 128 statement.
- SB (low-rank in-chunk form), SC (checkpoint and recompute) and SD (sumcheck over time) are not proved. SB has an integer reference and range study; SC and SD are analysis only.
- No gates, conv, norms or projections; synthetic inputs; no GPU; no production security.

## Reproduce

All from the repository root, CPU only. The proof runs need about 4.6 GB RAM and use one core.

```
# SB reference and range study (about 5 min each, no proof)
python3 research/operators/qwen_state_commit/sb_ref.py
python3 research/operators/qwen_state_commit/sb_summary.py
python3 research/operators/qwen_state_commit/sb_ref.py --gb 24 --out experiments/20261109-34-qwen-state-commit/runs/sb-ranges-gb24.json
python3 research/operators/qwen_state_commit/sb_summary.py sb-ranges-gb24
# counted volumes (instant)
python3 research/operators/qwen_state_commit/count.py
# SA proofs: build, honest windows at C = 64, 16, 1, then the hostile suite (about 1 h)
taskset -c 0-5 python3 research/operators/qwen_state_commit/record.py build honest 64 16 1 hostile 64 16 1
```
