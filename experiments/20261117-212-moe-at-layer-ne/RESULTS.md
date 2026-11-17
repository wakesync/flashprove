# RESULTS: 20261117-212-moe-at-layer-ne

Issue #212. Base: main `5583d7f82b549454cdb6374d2fd347dfd9781976`. Measured, unreplicated. Host only (g++, no CUDA, no GPU).

## Outcome: "not reachable on main" (as registered)

- H1a (the function alone) is TRUE: `moe_at_layer(prof, l)` (`prover/prover/layout.h` lines 173-175) has no NE term and disagrees with the reference rule `prof >= 3 && (l & 1) && NE > 0` in 8 of 96 enumerated cases, all of them NE 0, odd l, prof in {3, 20}.
- H1b (reachability) is FALSE on main: the prover never passes the parameter file's prof to `moe_at_layer`. Both callers read `LayerShape::prof`, and main sets that to `mo ? 3 : 2` with `mo = NE > 0`. A dense file (NE 0) therefore gives prof 2, and `moe_at_layer(2, l)` is false on every layer. Decision metric `armB_disagree_ne0` = 0 of 32.
- The gate: `mo = NE > 0` at `prover/prover/inputs.cuh` line 237, turned into the shape's prof at `prover/prover/layer_setup.cuh` line 70 (forward pass) and `prover/prover/inputs.cuh` line 293 (scale check). `prover/prover/layout.h` lines 27-28 already say `LayerShape::prof` is "not the prof of the parameter file".
- No prover, verifier or committer code was changed. No unit test was added (the registered "not reachable" branch changes no code).

## Numbers (`runs/enumerate-run1.txt`, last lines; run 2 is byte-identical)

| count | value | what it says |
|---|---|---|
| `armA_disagree` | 8 of 96 | main's `moe_at_layer(prof, l)` with the enumerated prof, vs the reference |
| `armA_disagree_ne0_odd_prof_ge3` | 8 | all 8 are NE 0, odd l, prof 3 or 20 (the issue's premise about the function) |
| `armB_disagree` | 16 of 96 | main's call with the prof main assigns, P(NE) = NE > 0 ? 3 : 2, vs the reference at the enumerated prof |
| `armB_disagree_ne0` (decides) | 0 of 32 | the same restricted to NE 0: no dense case takes the expert path |
| `armB_disagree_prof20` | 0 of 24 | the same restricted to prof 20, the only prof a parameter file may have (`prover/common/parameter_file.h` line 176) |
| `armB_own_prof_disagree` | 0 of 24 | the prover's call against the reference at the prof it runs with |
| `armC_missed_moe` | 16 of 64 | risk note, see below |
| `armC_main_prof_missed_moe` | 16 of 64 | risk note, with prof as main assigns it |

The 16 cases of `armB_disagree` are all prof 1 or 2 with NE 1 or 16 on odd layers (listed by row in `runs/enumerate-run1.txt`). They come from comparing against the reference at an enumerated prof that the prover does not use; PREREG Amendment 2 (before any run) explains why they do not answer the question. None has NE 0.

Determinism: the registered program ran twice in a row on cores 2-3. Both output files have SHA-256 `246a29ac37a139e75f6eeb4d58ea1399a87c18e8e841575c6fde59dd42def2cc`. Identical output stands in for a spread; there is no randomness or timing.

## Risk note on the prior art (arm C)

The public fork commit (marcellobardus/FlashProve-TinyLlama1.1B `26dd68f962d0`, read through the GitHub API only) changes both callers to pass the shape's NE. At `prover/prover/forward.cuh` line 108 (`layer_words_fit()`), the shape comes from `prover/prover/inputs.cuh` lines 292-295, which sets `prof`, `xl` and the digit forms but never `NE`, so NE keeps its default 0 (`prover/prover/layout.h` line 21). Evaluated on that shape, the fork-style rule is false on every layer, and for MoE models (NE 1 or 16) it misses all 16 odd-layer expert cases at prof >= 3 (`armC_missed_moe` 16 of 64; the 64 include the 48 cases where the reference is false). Effect if ported as is: the start-of-run range check of the router shifts kr, kgR and kuR for MoE models would be skipped. This is a reading of main's source plus the enumeration; nothing from the fork was built or run. On the fork itself the same files (`inputs.cuh`, `layer_setup.cuh`) have the same git blob ids as main, so the reading should carry over; that is not checked further.

The fork's report of an UNFIT stop on a dense H100 prove is not reproduced or explained here. If it happened, it was not through `moe_at_layer` with prof 20 on this code, since `LayerShape::prof` is 2 for NE 0. Something else in that run (a different build, a different `LayerShape`, or another check) would have to account for it.

## Source read on main (`5583d7f8`)

Every place that decides "expert layer" from a profile or flag and the layer number:

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
| `prover/tests/weights_blocks/make_model.cpp:523` (test tool) | `routed = experts > 0 && (l & 1)` | its own argument | false |

Assignments of `LayerShape::prof` on main: `prover/prover/layer_setup.cuh:70` and `prover/prover/inputs.cuh:293`, both `mo ? 3 : 2`; the default 3 (`layout.h:31`) is overwritten in both. No other `LayerShape` is built in `prover/` or `verifier/` (grep for `LayerShape` on main). Assignments of `LayerShape::NE`: `layer_setup.cuh:64` (`mo ? NE : 0`); not at `inputs.cuh:292`.

## What is NOT established

- The GPU prover was not built or run, and no dense proof was made on main or anywhere else by this lane. "Not reachable" is a statement about main's source and the host enumeration of the same predicate and assignment expressions; it is not a prove run.
- That a dense prove on main gets past the forward pass: other dense-path faults (if any) are untested. The issue's motivating UNFIT stop is not reproduced and not explained.
- Arm B models the two assignments by the expression `mo ? 3 : 2` copied into `enumerate.cpp`, not by calling `g_setup_layout()` or `read_inputs()` (both need CUDA and a full kit). A future edit to either line would not be caught by this program.
- Arm C is a reading plus an enumeration of a rule; the fork's code was not compiled or run, and no MoE kit was run with it.

## Deviations
- Before writing the PREREG the lane read source on main (disclosed at the top of PREREG.md).
- Amendment 2 (before any run) moved the decision from `armB_disagree` to `armB_disagree_ne0` after a flaw in the registered comparison was found by reading the program.
- The times of Amendments 1 and 2 were estimated and wrong; a third entry corrects them (commit order is the record).
- No unit test file was added and `prover/tests/unit.sh` is untouched, because the registered branch for "not reachable" changes no code. So the "before and after" unit-suite comparison of the other branch was not run.

## Reproduce
From the repository root, on a host with g++ (13.3.0 used):
```
g++ -O2 -std=c++17 -Wall -Wextra -I prover -o enumerate experiments/20261117-212-moe-at-layer-ne/enumerate.cpp
./enumerate out.txt
sha256sum out.txt   # 246a29ac37a139e75f6eeb4d58ea1399a87c18e8e841575c6fde59dd42def2cc
```
