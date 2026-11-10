# Qwen DeltaNet recurrent-state commitment, chunk statements (issue #34, research only)

Experiment, pre-registration and verdict: [experiments/20261109-34-qwen-state-commit/](../../../experiments/20261109-34-qwen-state-commit/). Strategy comparison and recommendation: that directory's RESULTS.md. Corrected on 2026-11-10 after two independent reviews of PR #71; the list of corrections is at the end of RESULTS.md. Research security settings only (#19: Goldilocks, target 10 bits, 6 work bits, deterministic toy coins). Nothing here is a serving protocol.

## What is in this directory

| file | what it is | measured or counted |
|---|---|---|
| `chunk.cpp` | One chunk statement of strategy SA (state committed at chunk boundaries only). The M1b relation and RNG/LKP composition (`../qwen_deltanet_lookup/`, PR #63), copied unchanged, plus a chunk header bound into the transcript under its own label. Modes `prove`, `verify`, `hostile-skip`. | proofs are measured |
| `window.py` | Builds a window of T tokens at D = 32, splits it into chunks of C, writes each chunk's public words, header and conv-history words. Holds the **chain verifier** `chain_check(outdir, statement, names, verify_chunk)`, the statement descriptor `statement()`, and `chain_check_unpinned`, the check of the registered runs, kept for comparison only. | |
| `record.py` | Runs the honest windows (C = 1, 16, 64; seeds 1..5) and the hostile suite: registered classes b1..b5, the constructions of the two reviews as named negative cases n1..n9, and the cases this harness cannot reject (open). Writes `runs/*-r2.*` only; the registered run files were written by this script at commit d39f598. | measured |
| `sb_ref.py`, `sb_summary.py` | Integer reference of strategy SB (chunked low-rank / UT form) at the real head shape D = 128 over 1,024 steps; range and drift study. No proof. | measured (reference arithmetic) |
| `count.py` | Volume formulas for every strategy at Qwen3.8-27B shapes, state mixer only. Its SB rows use the remainder widths of the registered 2^12 arm. Writes `runs/count.json` (registered). | **counted, not measured** |
| `count_r2.py` | The SB formulas with the remainder widths of each decay-table scale, and the costs still missing. Writes `runs/count-r2.json`. | **counted, not measured** |
| `sb_alias.py` | Second solutions of the SB floors in the field under an M1b-style range check, edge traces, interval bounds. Writes `runs/sb-alias-gb18.json`. | reference arithmetic |
| `sb_gates.py` | Gate statistics of the registered failure case (R3 seed 3). Writes `runs/sb-gates-r3s3.json`. | reference arithmetic |
| `mixed_f.py` | State and output differences of the mixed-precision chain of case n1. Writes `runs/mixed-f-states.json`. | reference arithmetic |

## What is proved (SA chunk statement)

For one head of size D x D and a chunk of C tokens, given public S_in, the per-token a, beta, k, v, q, the outputs o and S_out: the prover knows intra-chunk states S_1..S_{C-1}, memory reads M, deltas and floor remainders such that the M1 staged-floor recurrence holds at every token and the last state equals S_out. This is the M1b statement with T = C; the intra-chunk states are committed witness cells of the chunk's product oracle.

The chunk header (request id, layer, chunk index, token start, C, D, the handle of (S_in, H_in) and the handle of (S_out, H_out)) is a statement item of the chunk's transcript (label `0x46505343`), so a chunk proof does not verify under another header.

## What the verifier recomputes

- Chunk verifier (`chunk.bin verify`): decodes the chunk's public words, derives every relation from them, runs the unchanged M1b verifier under the chunk label with the header bound.
- Chain verifier (`window.chain_check`). It takes a **statement descriptor that the verifier holds** and an ordered list of chunk names. The descriptor (`window.statement()`) has: a model/arithmetic identifier slot (a placeholder here), request, layer, window length T, chunk size C, head size D, fixed-point bits F, the first-chunk handle, and the digest of the conv history at the end of the window. It is an argument; it is not read from the directory the prover writes (the manifest is not read at all). The verifier rejects unless: the number of chunks is ceil(T / C); every fixture says the statement's F and D; every chunk has exactly C tokens, except the last, which has T - (n - 1) C; every header says the statement's request and layer, index c, token start c C, that length and D; the handles recomputed from the words (S, conv history H, request, layer, boundary index, token position) equal the header's; chunk c's input handle equals chunk c-1's output handle (chunk 0: the statement's first handle); every chunk proof verifies; the last chunk's history out has the statement's digest.
- All of these comparisons except "every chunk proof verifies" are done in Python, outside the proofs, on public values. In this harness the statement is computed by the same script that plays the prover (from the registered seed, C, T, request and layer); the separation is by argument, not by process.

## What is NOT covered

- **Everything at a boundary is public.** S_in, S_out, every token input and every output are public words. Only the states inside a chunk are committed. The link between chunks is a comparison of SHA-256 hashes of public words outside the proofs. Nothing here tests a handoff where the state is hidden.
- **Token inputs are bound to nothing.** A chunk whose inputs were replaced by another window's, honestly proved, is accepted (`runs/hostile-C*-r2.jsonl`, `open-inputs-not-bound`).
- **A conv history changed consistently on both sides of a boundary is accepted** (`open-history-consistent-shift`). The registered b5 class covers inconsistent replacements only.
- **No model identity.** The statement's model identifier is a placeholder; the header and the handle do not carry one.
- **SB has no sound lowering here** at the 2^18 table that passes the sampled drift bound (`runs/sb-alias-gb18.json`), and its registered 2^12 arm failed that bound.

- **The handle is a stand-in.** Here S_in, S_out and H are public words and the handle is SHA-256 of them, recomputed by the chain verifier. In M3 the state is not public: the carried value must be a commitment that the next chunk's proof opens inside its own oracle (a kept row read by the next segment, as in `blocks/toy/segments.h`). This experiment tests the chain bookkeeping and the boundary attacks against it, not that in-proof handoff.
- **Conv history is bound, not proved.** H is a block of 3 taps x 3D synthetic words per boundary. Its relation (the four-tap conv) is the operators lane's gadget (draft PR #67, unreviewed), which per that lane does not tie its history to the previous chunk. Here only the binding of H across the boundary is tested.
- D = 32, not 128 (so that C = 64 fits a 2^21 table). Per-cell counts are compared to M1b's D = 128 statement.
- SB (low-rank in-chunk form), SC (checkpoint and recompute) and SD (sumcheck over time) are not proved, and the matmul-sumcheck backend that SB's counts assume does not exist in this repository. SB has an integer reference and range study; SC and SD are analysis only.
- No gates, conv, norms or projections; synthetic inputs; no GPU; no production security.

## Reproduce

All from the repository root, CPU only. The proof runs need about 4.6 GB RAM and use one core.

```
# SB reference and range study (about 6 to 7 min each, no proof). Registered arm (decay table 2^12):
python3 research/operators/qwen_state_commit/sb_ref.py
python3 research/operators/qwen_state_commit/sb_summary.py sb-ranges
#   sb_summary.py writes runs/<name>-summary.json. The committed registered summary is runs/sb-summary.json:
#   it was written under that name by an earlier default and has the same bytes as runs/sb-ranges-summary.json.
# Unregistered arms (decay table 2^18 and 2^24):
python3 research/operators/qwen_state_commit/sb_ref.py --gb 18 --out experiments/20261109-34-qwen-state-commit/runs/sb-ranges-gb18.json
python3 research/operators/qwen_state_commit/sb_summary.py sb-ranges-gb18
python3 research/operators/qwen_state_commit/sb_ref.py --gb 24 --out experiments/20261109-34-qwen-state-commit/runs/sb-ranges-gb24.json
python3 research/operators/qwen_state_commit/sb_summary.py sb-ranges-gb24
# SB second solutions, edge traces, gate statistics, mixed-precision differences (seconds each, no proof)
python3 research/operators/qwen_state_commit/sb_alias.py
python3 research/operators/qwen_state_commit/sb_gates.py
python3 research/operators/qwen_state_commit/mixed_f.py
# counted volumes (instant): registered count.json, then the recount count-r2.json
python3 research/operators/qwen_state_commit/count.py
python3 research/operators/qwen_state_commit/count_r2.py
# SA proofs, r2 files: build, honest windows at C = 64, 16, 1, then the hostile suite (about 1 h on one core)
python3 research/operators/qwen_state_commit/record.py build honest 64 16 1 hostile 64 16 1
```

`record.py` now writes `runs/*-r2.*` only. The registered files (`runs/honest-C*.jsonl`, `chain-C*.json`, `hostile-C*.jsonl`, `build.json`) were produced by `record.py` at commit d39f598 with the same command line; to regenerate them, check out that commit.
