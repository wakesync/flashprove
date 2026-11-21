# RESULTS: 20261121-229-qwen-m3a1-weight-side

Issue #229. PREREG: [PREREG.md](PREREG.md) (first commit 9ce83190, alone; amendment A1 committed before any registered run). Code: [`research/operators/qwen_m3a1/`](../../research/operators/qwen_m3a1/README.md). Environment: [ENV.json](ENV.json).

**Verdict: PASS for the honest, hostile and completeness conditions of (a) and (b) as registered. The fourth registered condition (a C++ check that the trace cells equal the converted integers) was not tested by a separate check: no such check was written (deviation, amendment A2). Sub-step (c) was not started. The M3a-1 evidence gate is not met (see NOT established).** Every number below is measured, unreplicated, on one shared CPU host, at the harness's research setting. None of it is a security level.

## In plain words

The 3,288,706 integer weights of one Gated DeltaNet head of the real Qwen3.8-27B (layer 0, V head 0, pinned stock checkpoint) are in a committed table. The verifier holds only the table's root and record. A proof shows that the 1,666 weights the head's trace reads (conv taps, gains, cA, dt_bias) are integers in their design classes, and that they are the table's entries at their fixed addresses. Five honest proofs verified. Every registered hostile case was rejected and every completeness case was accepted. The other 3,287,040 weights (the in_proj and out_proj matrices) are committed but **not bounded**: no range proof on the table exists for a Qwen layout, and none was built.

## The statement (as built)

- **Public:** run configuration (codes, plans, setting), the 1,666 addresses and class widths, the layout of M (595 x 8,192), the table's key (root and record).
- **Committed:** the table (all 3,288,706 weights as field elements); the trace cells and their bits.
- **Proved:** (1) each of the 1,666 trace cells is in its class: [-4,096, 4,095] for taps, gains and cA, [-2^17, 2^17) for dt_bias (exact bits, b^2 = b); (2) sum_i eq(psi, i) w_i = v on the trace (psi drawn after the trace root and the table's name); (3) row 0 of the table at psi equals v (one LIN claim on the table under its one-time test). (2) and (3) together tie each cell to its table entry and force row 0 to be zero past address 1,665, except with probability at most 13 / |E| over psi. That 13 / |E| is the bound of the idealised argument with both vectors fixed before psi is drawn, not the error of the compiled proof at the research setting.
- **The verifier** builds every relation and the LIN claim itself, from public data and its own transcript. It reads no weight.

## Registered items

| item | registered | result | verdict |
|---|---|---|---|
| honest proof | accepted 5 of 5 (seeds 1..5) | 5 of 5 accepted | PASS |
| H1 other root (table with one tap +1) | rejected | rejected, trace chain: "a nonce does not give the proof of work that its round asks for" (`blocks/chain/rounds.h` line 516) | PASS |
| H1b other root (same weights, other randomness) | rejected | rejected, same reason and line | PASS |
| H2a tap +1 in trace, v from the trace | rejected | trace accepted; rejected by LIN: "LIN second part: a proximity test" (`qm3a1.cpp` line 249) | PASS |
| H2b tap +1 in trace, v from the table | rejected | rejected, trace chain: "BASE: the masked message in the proof does not satisfy the linear claim" (`blocks/iop/base_case.h` line 225) | PASS |
| H3 gain 2^50 in trace and table | rejected | rejected, trace chain, BASE (base_case.h line 225) | PASS |
| H4 gain +1 in trace, not the table's | rejected | trace accepted; rejected by LIN, second part proximity test (qm3a1.cpp line 249) | PASS |
| H5 dt_bias = 2^17 in trace and table | rejected | rejected, trace chain, BASE (base_case.h line 225) | PASS |
| H6 table row 0 non-zero past the cells | rejected | trace accepted; rejected by LIN, second part proximity test (qm3a1.cpp line 249) | PASS |
| C1 dt_int = 78,848 (real layer-0 max) | accepted | accepted | PASS |
| C2 dt_int = -23,424 (real layer-0 min) | accepted | accepted | PASS |
| C3 dt_int = 2^17 - 1 | accepted | accepted | PASS |
| trace cells equal the converted integers at their addresses | holds | no separate check was written; the program reads the 1,666 cells from row 0 of the same M.i32 that it commits (`qm3a1.cpp` line 323), and requires row 0 zero past them | DEVIATION: holds by construction, not tested (amendment A2) |

H1 and H1b are refused at the first check that reads the verifier's own first query: the trace chain binds the table's name, so a different key changes the transcript and the recorded proof-of-work nonce no longer fits. LIN is not reached. That is the intended binding (a proof is about one root), but the refusal line is a transcript check, not a check of the weights. Reviewer's finding (<https://github.com/wakesync/flashprove/pull/231#issuecomment-7059688619>): a proof honestly generated against the other table's key (tap 0 +1 in that table, trace cell honest) is rejected. With v from the trace, the trace is accepted and LIN refuses it ("LIN second part: a proximity test"); with v from that table and local targets, the trace refuses it ("BASE: ... does not satisfy the linear claim"). So that stronger case is refused by the weight checks, not the nonce; H1 and H1b as registered test transcript binding only. That case is not a registered case.

H2a, H4 and H6 are rejected where the design says they must be: the trace is consistent with itself and the class holds, but the table disagrees, and LIN refuses. H3 and H5 are rejected by the class relations (the honest decomposition of an out-of-class value gives bits of another value, so the class relation is false and a hostile prover that sets each target to its local value fails the proximity test). H2b is rejected by the tie row on the trace.

Raw outputs: `runs/honest-seed{1..5}.json`, `runs/case-*.json` (each written once), summary `runs/summary.json`. Weight inputs: `runs/weights-head0.json` (shapes, exponents, SHA-256 of every fetched tensor, each equal to the merged stream hash, and the SHA-256 of M; it also holds `ranges`: cA, dt_int, tap and gain minimum and maximum, and the matrix absolute maximum of head 0, see Deviations).

## Measured (unreplicated, shared host, single-threaded runs on cores 2-7)

| quantity | value |
|---|---|
| weights in the table | 3,288,706 (595 x 8,192 matrix, 2^7 table rows of 2^6 matrix columns each; code length 38,083 entries, 2^18 positions) |
| trace cells / product columns / log length / relations | 1,666 / 23,329 / 15 / 44,992 |
| commit of the table, s (n = 5) | median 3.160, sd 0.042, min 3.116, max 3.222 |
| prove (trace + LIN), s (n = 5) | median 0.908, sd 0.012, min 0.897, max 0.928 |
| verify (trace + LIN), s (n = 5) | median 0.098, sd 0.005, min 0.089, max 0.099 |
| peak RSS, kB (n = 5) | median 453,204, min 452,636, max 453,336; hostile runs up to 818,236 (H1: two tables) |
| trace proof bytes (n = 5) | median 420,984, min 420,632, max 421,240 |
| LIN proof bytes (n = 5) | median 224,312, min 224,056, max 224,760 |

What varies between the 5 honest runs: the prover's private randomness (seed 1..5): table tails and pads, so the root and record, the transcript's challenges, and the proof bytes. Verdicts did not vary. Weights converted (stock, layer 0, head 0): exponents conv 12, gain x sqrt(128) 8, cA 13, dt_bias 12 (F), in_proj_qkv 13, in_proj_z 14, in_proj_a 14, in_proj_b 16, out_proj 11; head 0's cells: taps -1,296..1,720, gains 2,274..2,693, cA 333, dt_int -14,208; matrix |w| <= 3,584 by the conversion (not by the proof).

## What bounds each kind of weight in this step (issue item 5)

- **The 1,666 trace-read weights** (taps, gains, cA, dt_bias): bounded **by the proof**, by the in-trace exact class (bits), and tied to the table by the tie. The class does not depend on any range proof of the table.
- **The 3,287,040 matrix weights** (in_proj and out_proj rows of the head): **not bounded by anything in this step.** They are committed (the root fixes them, up to the table's proximity test), but no range proof on table entries exists for a Qwen layout: WF (`blocks/iop/wf.h`, `blocks/frame/wf_units.h`) is for upstream's Maverick layout only, and no Qwen layout was built here. That their absolute values are at most 3,584 is a property of an honest conversion, checked by `prepare.py`, not proved. What this leaves open: any later claim that multiplies these weights (the in_proj and out_proj claims of M3a-1) has no proved bound on its weight factor until a Qwen WF layout, or an in-proof class on every matrix weight (which DESIGN 6.2 counts at 9,866,118 keys, beyond 2^23), exists.

## Sub-step (c) not started

The registration allowed (c) only after (a) and (b) were committed and with more than 50 minutes left; at 06:55 UTC there were 80. It was not started for a reason found in the source, not the clock alone: LIN's claim is `<g (x) eq(psi, .), M>`, columns weighted by an equality vector at a point. in_proj with public a needs columns weighted by a (y_r = sum_j a_j M[r][j]), which takes a sumcheck over the column index to reduce to a point, plus committed y cells and their tie, none of which is merged for a table in this harness. Building and reviewing that is not a 70-minute step. This is the smallest missing piece for (c).

## Deviations

- Draft PR opened 40 minutes after the lane started, 5 minutes over the brief's 35.
- The PREREG commit was first tried in the same step as `git add` and failed on the index lock; the branch was pushed once at the base commit before the PREREG commit was made and pushed. No history was rewritten.
- Amendment A1's header says 06:58 UTC; it was written and committed at about 06:51 UTC, before the registered runs started (06:52). The time in the header is wrong, the order is not.
- `summarise.py` was fixed once after it tried to read `runs/weights-head0.json` as a run file; no run file changed.
- PREREG (Weights) says "never values". A small number of values and ranges of this public checkpoint's head 0 are in `runs/weights-head0.json` (`ranges`) and in this file (Measured, last paragraph; the matrix maximum 3,584 also under "What bounds each kind of weight"). The run file is not rewritten.
- PREREG's acceptance threshold names a C++ check that the trace cells equal the converted integers at their addresses. That check was not written. The program reads the 1,666 cells from row 0 of the same M.i32 that it commits (`qm3a1.cpp` line 323), so the property holds by construction, together with the fetch-time SHA-256 check of the tensors (`prepare.py`). Amendment A2. Reviewer's finding (<https://github.com/wakesync/flashprove/pull/231#issuecomment-7059688619>): an independent conversion by the reviewer agrees with M.i32 for row 0's 1,666 cells.
- PREREG step 4 says LIN's first chain binds "the trace chain's seal". The code binds psi and v only (`qm3a1.cpp` line 181).

## NOT established

- Any computation of the head: no in_proj, conv, gates, q/k norm, recurrence, gated norm or out_proj product. T = 16 is not touched.
- The M3a-1 evidence gate of `experiments/20261109-32-qwen-m3-design/DESIGN.md` section 9 (honest 10 of 10 at T = 16, the hostile cases that need the head computation, UBSan clean) is NOT met by this step; this step is the weight side only.
- Any bound on the matrix weights (above).
- Any soundness level: the trace uses the research setting (target 10 bits), and LIN runs on the hand-made plan of `blocks/iop/tests/lin_world.h` (all rounds priced NOTHING, built with the test-only macros `BLK_PLANS_BY_HAND_FOR_A_TEST` and `BLK_TESTED_TABLE_FOR_A_TEST`). The hostile cases are one complete proof each.
- That the table is the advertised checkpoint (the proof binds a root; the fetch-time hash check is outside it). Only head 0 of layer 0 is converted; layer 0 is byte-identical in the abliterated checkpoint (PR #68), so this says nothing about abliteration.
- Hiding: v is sent unmasked.
- Any accuracy claim.
- Independent replication.

## Open risks

1. Composition argument for the tie is the lane's own (13 / |E| from a vector fixed before psi); it is not reviewed and not in Lean.
2. The cell-to-address check in the honest path is by construction in one program; a reviewer should check `prepare.py`'s address layout against DESIGN 6.2 and real_head.py's channel map (V head h reads QK head h // 3).
3. LIN with a single request and the request's mask entry at weight 0 is a use the upstream tests do not exercise.
