# RESULTS: 20261117-212-moe-at-layer-ne

Issue #212. Base: main `5583d7f82b549454cdb6374d2fd347dfd9781976`. Measured, unreplicated. Host only (g++, no CUDA, no GPU).

## Outcome: "not reachable on main" (as registered)

- H1a (the function alone) is TRUE: `moe_at_layer(prof, l)` (`prover/prover/layout.h` lines 173-175) has no NE term and disagrees with the reference rule `prof >= 3 && (l & 1) && NE > 0` in 8 of 96 enumerated cases, all of them NE 0, odd l, prof in {3, 20}.
- H1b (reachability) is FALSE on main: the prover never passes the parameter file's prof to `moe_at_layer`. Both callers read `LayerShape::prof`, and main sets that to `mo ? 3 : 2` with `mo = NE > 0`. A dense file (NE 0) therefore gives prof 2, and `moe_at_layer(2, l)` is false on every layer. Decision metric `armB_disagree_ne0` = 0 of 32. That count follows from the expression `mo ? 3 : 2` copied into `enumerate.cpp`; the evidence that carries this result is the source read below, which shows the prover uses that expression.
- The gate: `mo = NE > 0` at `prover/prover/inputs.cuh` line 237, turned into the shape's prof at `prover/prover/layer_setup.cuh` line 70 (forward pass) and `prover/prover/inputs.cuh` line 293 (scale check). `prover/prover/layout.h` lines 27-28 already say `LayerShape::prof` is "not the prof of the parameter file".
- No prover, verifier or committer code was changed. No unit test was added (the registered "not reachable" branch changes no code).

## Numbers (`runs/enumerate-run1.txt`, last lines; run 2 is byte-identical)

| count | value | what it says |
|---|---|---|
| `armA_disagree` | 8 of 96 | main's `moe_at_layer(prof, l)` with the enumerated prof, vs the reference |
| `armA_disagree_ne0_odd_prof_ge3` | 8 | all 8 are NE 0, odd l, prof 3 or 20 (the issue's premise about the function) |
| `armB_disagree` | 16 of 96 | main's call with the prof main assigns, P(NE) = NE > 0 ? 3 : 2, vs the reference at the enumerated prof |
| `armB_disagree_ne0` (decides) | 0 of 32 | the same restricted to NE 0: no dense case of the enumeration takes the expert path. Expected from the copied expression (with NE 0 the program calls `moe_at_layer(2, l)`); it shows the predicate's value on those inputs, not that the prover builds its shape that way (that is the source read) |
| `armB_disagree_prof20` | 0 of 24 | the same restricted to prof 20, the only prof a parameter file may have (`prover/common/parameter_file.h` line 176) |
| `armB_own_prof_disagree` | 0 of 24 | the prover's call against the reference at the prof it runs with |
| `armC_missed_moe` | 16 of 64 | risk note, see below |
| `armC_main_prof_missed_moe` | 16 of 64 | risk note. The tested shape gets the prof main assigns, P(NE), but the reference is still evaluated at the enumerated prof. Denominator: the 64 rows with NE 1 or 16; a row counts when that reference is true and the rule is false. See the label note below |

The 16 cases of `armB_disagree` are all prof 1 or 2 with NE 1 or 16 on odd layers (listed by row in `runs/enumerate-run1.txt`). They come from comparing against the reference at an enumerated prof that the prover does not use; PREREG Amendment 2 (before any run) explains why they do not answer the question. None has NE 0.

Label note on `armC_main_prof_missed_moe` (added after review). The program gives the tested shape the prof main assigns, P(NE) = 3 for NE 1 or 16, but keeps the reference at the enumerated prof (`disC_main += r && !cm` in `enumerate.cpp`, with `r = ref(prof, l, NE)`). So the 16 are the rows with enumerated prof 3 or 20, odd l, NE 1 or 16, out of the 64 rows with NE 1 or 16: the same rows as `armC_missed_moe`. It is not a count against a reference at the normalized prof, and it is not a second independent measurement of main's path. A reviewer's descriptive finding, not a registered metric and not in `research/results.yaml`: against a reference at the normalized prof the count over the same 64 rows would be 32 (https://github.com/wakesync/flashprove/pull/216#issuecomment-6945253629).

Determinism: the registered program ran twice in a row on cores 2-3. Both output files have SHA-256 `246a29ac37a139e75f6eeb4d58ea1399a87c18e8e841575c6fde59dd42def2cc`. Identical output stands in for a spread; there is no randomness or timing.

## Risk note on the prior art (arm C)

The public fork commit (marcellobardus/FlashProve-TinyLlama1.1B `26dd68f962d0`, read through the GitHub API only) changes both callers to pass the shape's NE. At `prover/prover/forward.cuh` line 108 (`layer_words_fit()`), the shape comes from `prover/prover/inputs.cuh` lines 292-295, which sets `prof`, `xl` and the digit forms but never `NE`, so NE keeps its default 0 (`prover/prover/layout.h` line 21). Evaluated on that shape, the fork-style rule is false on every layer, and for MoE models (NE 1 or 16) it misses all 16 odd-layer expert cases at prof >= 3 (`armC_missed_moe` 16 of 64; the 64 include the 48 cases where the reference is false). Effect if ported as is: the start-of-run range check of the router shifts kr, kgR and kuR for MoE models would be skipped. This is a reading of main's source plus the enumeration; nothing from the fork was built or run. The statement is about a hypothetical port of that call-site change to pinned main, where the scale-check shape leaves NE at zero. It is not a statement about the fork.

Prior-art facts, checked through the GitHub API by blob id only: at the fork commit, `prover/prover/inputs.cuh` and `prover/prover/layer_setup.cuh` have the same git blob ids as main `5583d7f8`; at its parent commit, `prover/prover/layout.h` and `prover/prover/forward.cuh` do too. These four equalities establish the text of those four files. They do not establish how the fork builds or changes a `LayerShape` elsewhere, what was built, or what ran.

The fork's own failure (its reported UNFIT stop on a dense H100 prove) is neither reproduced nor explained here, and this report draws no conclusion about its cause.

## Source read on main (`5583d7f8`)

Places that decide "expert layer" from a profile or flag and the layer number, as found by the text searches listed under "Search coverage" below. The table is as complete as those searches. It is not a proof that no other such expression exists. Rows marked (added after review) were missing at `808d0bc8`.

| file:line | expression | input to the flag | dense (NE 0) gives |
|---|---|---|---|
| `prover/prover/layout.h:173-175` | `moe_at_layer(prof, l) = prof >= 3 && (l & 1)` | caller's `LayerShape::prof` | depends on caller |
| `prover/prover/forward.cuh:108` (caller, `layer_words_fit`) | `!moe_at_layer(s.prof, l) \|\| shifts fit` | `s.prof = mo ? 3 : 2` at `prover/prover/inputs.cuh:293` | prof 2, no expert layer |
| `prover/prover/forward.cuh:1558` (caller, `forward`) | `mo = moe_at_layer(pf, l)`, `pf = L.s.prof` (line 1480) | `LayerShape S{..., mo ? 3 : 2, ...}` at `prover/prover/layer_setup.cuh:70`, via `make_layer_layout` (line 78, `L.s = s` at `layout.h:179`) | prof 2, `ffn_dense` on every layer |
| `prover/prover/forward.cuh:1099, 1116` | `L.s.prof >= 3 && wblocks` (scratch for routed blocks) | same `L.s.prof` | prof 2, no routed scratch |
| `prover/prover/layout.h:379, 439` | `sd->moe && pf < 3` (expert segments refused or skipped) | `s.prof` | prof 2: expert segments not allowed |
| `prover/prover/inputs.cuh:237` | `mo = NE > 0` | parameter file NE | 0 |
| `prover/prover/prover.h:451` | `is_moe_layer(l) = mo && (l & 1)` | `mo` | false |
| `prover/prover/layer_walk.cuh:238-239` | `gw_isM(lam) = mo && (lam & 1)` | `mo` | false |
| `prover/head/stack.cuh:380, 383, 773, 961, 1296` | `s.mo && (l & 1)` | `s8.mo = mo` at `prover/prover/layer_walk.cuh:725` | false |
| `prover/hash_commitment/hf_shape.cuh:61` (committer) | `moeMode = (p >= 3 && NE > 0)`, `p = prof & 15` | parameter file prof and NE | 0 |
| `prover/hash_commitment/hf_commit_weights.cuh:121` | `sh.moeMode && (u.l & 1)` | `moeMode` | false |
| `prover/weights_commitment/kernels.cuh:108` | `S.moe && (l & 1)` | `model.moe = sh.moeMode` at `hf_shape.cuh:110` | false |
| `prover/weights_commitment/worst_case.cuh:409, 534` | `S.moe && (l & 1)`, `sh.moeMode && moeW(l)` | `moeMode` | false |
| `prover/weights_commitment/fold_source.cuh:41, 55` | `experts && (layer & 1)` | `model.experts = sh.moeMode != 0` (line 202) | false |
| `prover/common/weight_layout.h:109` | `s.moeMode && moeW(l)` | `moeMode` (from `hf_shape.cuh` or `request_member.cuh:171`, `g.mo`) | false |
| `prover/weights_blocks/block_weights.h:97` | `has_experts(layer) = experts && (layer & 1)` | `experts = mo` at `prover/prover/inputs.cuh:491, 499` | false |
| `verifier/src/vf_weights_layout.h:39, 145` | `MOE && (l & 1)` | `wsSetMoe(..., NE > 0)`; comment line 28 | false |
| `verifier/src/cp_verify.cpp:1362, 1396` | `isMoeL(l) = p3 && l % 2 == 1`, `p3 = h.NE > 0` | parameter file NE | false |
| `verifier/src/vf_layers_check.inc:122-124` (added after review) | `isMoe(lam) = p3 && lam % 2 == 1`, the predicate of the layer sub-proof check; used at lines 406, 416, 426, 553, 879 | `p3 = h.NE > 0` at `verifier/src/cp_verify.cpp:1362`: the file is included inside `runStage` at `cp_verify.cpp:2190` and uses its local `p3` (the file's own lines 8-9 say so); `h.NE` is read at `cp_verify.cpp:361` (`parseHeader`) from the statement, which the verifier builds itself (comment at lines 326-327) from the parameter file's value lines, NE among them (lines 951-957) | false. Supports the outcome |
| `verifier/src/cp_verify.cpp:490` (added after review) | `p3 = h.NE > 0` in `layout()`, a second definition of the same flag; it guards the expert tensors and segments (for example lines 557, 676, 688, 699). Line 489 refuses a header prof other than 4 | `h.NE` | false. Supports the outcome |
| `verifier/src/cp_verify.cpp:143` (added after review) | `padding(lam, j) = !used[j] \|\| (used[j] == 2 && lam % 2 == 0)` | `used[j]` is 2 only for a segment declared with `moe` (line 178); those are declared under `p3` (lines 676-681, 688-692, 699) or with RCL (line 698), and RCL without `p3` is refused (line 599) | no column has 2, so the layer-parity term is never used. Supports the outcome |
| `prover/prover/weights_generated.cuh:134, 141` (added after review) | `q.mode = experts ? 1 : 0`, `if (experts)`: index modes of generated weights (`experts`: "every second layer has experts", line 104) | `w->experts = mo` at `prover/prover/inputs.cuh:491` | false. Supports the outcome |
| `prover/head/stack.cuh:343, 353, 367, 369, 563, 796` (added after review) | `s.mo ? ... : ...` offsets and counts, the same flag as the `stack.cuh` row above | `s8.mo = mo` at `prover/prover/layer_walk.cuh:725` | dense branch. Supports the outcome |
| `prover/tests/weights_blocks/make_model.cpp:523` (test tool) | `routed = experts > 0 && (l & 1)` | its own argument | false |

Search coverage (added after review). The table was checked against `git grep` at main `5583d7f8`. Over all of `prover/` and `verifier/`, tests included: `moe_at_layer` and `LayerShape`; `prof` or `pf` compared with a number; a layer-named variable (`l`, `lam`, `layer`, `lm`, `u.l`) combined with `& 1` or `% 2`; the names `p3`, `isMoe`, `isMoeL`, `is_moe_layer`, `gw_isM`, `has_experts`, `moeW`, `nMoe`, `moeMode =` and `wsSetMoe`. Over the source directories only (`verifier/src`, `prover/prover`, `prover/head`, `prover/common`, `prover/hash_commitment`, `prover/weights_commitment`, `prover/weights_blocks`; not every pattern over every one of them): any variable with `& 1` or `% 2`, `NE > 0`, `.moe`, `.experts` and `LamM`. The words moe, expert and routed in `prover/hiding`, `prover/attn`, `prover/engine`, `prover/longrow` and `prover/second_writing` (no predicate there). In the non-test code under `prover/` and `verifier/`, every hit that tests a layer's parity for experts is keyed on a flag derived from NE > 0 (`mo`, `p3`, `moeMode`, `MOE`, `experts`) or on `LayerShape::prof`. None is keyed on the parameter file's prof alone: the one predicate that reads it, the committer's `moeMode` at `hf_shape.cuh:61`, requires NE > 0 as well. (`verifier/tests/ws_build_fuzz.cpp:61` sets its flag at random; it is a fuzz test of the layout builder.) Limits of this search:
- Model-level uses of the same flags that do not test a layer number are not listed row by row. Examples read: `prover/prover/inputs.cuh:238` (`LamM = mo ? Lam / 2 : 0`), `prover/prover/layout.h:188` and `:215` (`s.prof >= 3` shape rule; `X.on = pf >= X.minprof`, with `pf = s.prof` at line 198 and minprof 3 on the tensors xr, lr, rl, sel, sc, ly, l3 and gh at lines 207-210), `verifier/src/cp_verify.cpp:369` and `:1372`, `prover/common/parameter_file.h:270`, `prover/weights_blocks/block_weights.cuh:171, 176`.
- Loops that walk expert layers by index (`2 * lm + 1` over `LamM`) instead of calling a predicate were not inventoried one by one. The ones read: `verifier/src/vf_layers_check.inc:701-720` is reached only after lines 699-700 (`else if (!p3)` / `continue;`), and the loop at `:877-879` takes its odd-layer branch only for the segment LR, which is declared only under `p3` (`cp_verify.cpp:678`), and calls `isMoe(lam)` at line 879.
- Outside `prover/` and `verifier/` the search was a single pattern (a layer variable with `& 1` or `% 2`) over `blocks`, `driver`, `tools`, `toy`, `tests`, `integrations`, `scales`, `weight_sums`, `scripts` and `examples`; `lean/` was not searched. Found and read: `integrations/vllm/integer_model/integer_model/parameters.py:172` and `:588` and `scales/words_to_policy.py:254`, all `NE > 0` and odd layer. Also found: two test-fixture writers that append the three expert scale words for every odd layer with no NE term, `integrations/vllm/integer_model/tests/chosen_model.py:67` and `integrations/vllm/integer_model/tests/lean_vectors/make_vectors.py:183` (and `:657`). They write `KL.bin` for the Python integer-model tests and are not prover, committer or verifier code. Whether they are ever given a dense base was not traced. They are outside the registered scope and are not counted for or against the outcome.

Assignments of `LayerShape::prof` on main: `prover/prover/layer_setup.cuh:70` and `prover/prover/inputs.cuh:293`, both `mo ? 3 : 2`; the default 3 (`layout.h:31`) is overwritten in both. No other `LayerShape` is built in `prover/` or `verifier/` (grep for `LayerShape` on main). Assignments of `LayerShape::NE`: `layer_setup.cuh:64` (`mo ? NE : 0`); not at `inputs.cuh:292`.

## What is NOT established

- The GPU prover was not built or run, and no dense proof was made on main or anywhere else by this lane. "Not reachable" is a statement about main's source and the host enumeration of the same predicate and assignment expressions; it is not a prove run.
- That a dense prove on main gets past the forward pass: other dense-path faults (if any) are untested. The issue's motivating UNFIT stop is not reproduced and not explained.
- Arm B models the two assignments by the expression `mo ? 3 : 2` copied into `enumerate.cpp`, not by calling `g_setup_layout()` or `read_inputs()` (both need CUDA and a full kit). A future edit to either line would not be caught by this program.
- Arm C is a reading plus an enumeration of a rule; the fork's code was not compiled or run, and no MoE kit was run with it.

## Deviations
- Before writing the PREREG the lane read source on main (disclosed at the top of PREREG.md).
- The PREREG's acceptance text expected H1a to be true in "16 cases, prof in {3, 20}, NE 0, l in {1, 3, 5, 7}". That set has 2 x 4 x 1 = 8 cases, not 16: the registered figure was an arithmetic slip. The measured value is 8 (`armA_disagree` 8 of 96, `armA_disagree_ne0_odd_prof_ge3` 8). The slip decides nothing: H1a had no numeric threshold. The registered line is left as written; a dated entry under PREREG `## Amendments` records the slip (added after review).
- Amendment 2 (before any run) moved the decision from `armB_disagree` to `armB_disagree_ne0` after a flaw in the registered comparison was found by reading the program.
- The times of Amendments 1 and 2 were estimated and wrong; a third entry corrects them (commit order is the record).
- No unit test file was added and `prover/tests/unit.sh` is untouched, because the registered branch for "not reachable" changes no code. So the "before and after" unit-suite comparison of the other branch was not run.

## Corrections after review
2026-11-17, written between two clock reads, 11:14:51 and 11:19:22 UTC. Text only: no rerun, no number changed, no change to `enumerate.cpp`, to either file under `runs/` or to any code. Reviews at `808d0bc85bb618ca374ec3d55550fdcf7787b394`: A = https://github.com/wakesync/flashprove/pull/216#issuecomment-6945253629 (request changes), B = https://github.com/wakesync/flashprove/pull/216#issuecomment-6945126944 (approve, nonblocking notes).

1. Source inventory (A must-fix 1, B nonblocking 2). Replaced heading sentence: "Every place that decides "expert layer" from a profile or flag and the layer number:". The table omitted the verifier's layer sub-proof predicate `verifier/src/vf_layers_check.inc:122-124` and the first definition of `p3` at `verifier/src/cp_verify.cpp:490`, which both reviews name. Those two rows are added with their NE provenance, plus three more found while re-searching, and a "Search coverage" paragraph says what was searched and what was not. The word "every" is withdrawn: the table is as complete as the listed searches. All added rows support the outcome.
2. Fork conclusion (A must-fix 2, B nonblocking 3). Removed: "On the fork itself the same files (`inputs.cuh`, `layer_setup.cuh`) have the same git blob ids as main, so the reading should carry over; that is not checked further." Removed: "If it happened, it was not through `moe_at_layer` with prof 20 on this code, since `LayerShape::prof` is 2 for NE 0. Something else in that run (a different build, a different `LayerShape`, or another check) would have to account for it." Replaced: "The fork's report of an UNFIT stop on a dense H100 prove is not reproduced or explained here." The risk note now keeps the four blob equalities as prior-art facts, bounds the statement to a hypothetical port to pinned main, and says the fork's own failure is neither reproduced nor explained.
3. `armC_main_prof_missed_moe` label (A nonblocking). Replaced table cell: "risk note, with prof as main assigns it". The cell and a label note now state the reference and the denominator. The value 16 of 64 is unchanged.
4. `armB_disagree_ne0` weight (B nonblocking 4). Replaced table cell: "the same restricted to NE 0: no dense case takes the expert path". The cell and one sentence added to the H1b bullet now say the count follows from the copied expression and that the source read carries the result. The value 0 of 32 is unchanged.
5. H1a expected count (A nonblocking, B nonblocking 1). Added under Deviations; nothing replaced.

## Reproduce
From the repository root, on a host with g++ (13.3.0 used):
```
g++ -O2 -std=c++17 -Wall -Wextra -I prover -o enumerate experiments/20261117-212-moe-at-layer-ne/enumerate.cpp
./enumerate out.txt
sha256sum out.txt   # 246a29ac37a139e75f6eeb4d58ea1399a87c18e8e841575c6fde59dd42def2cc
```
