# PREREG: 20261117-212-moe-at-layer-ne
Issue: #212. Lane: moe212. Date (UTC): 2026-11-17 09:08. Base commit: 5583d7f82b549454cdb6374d2fd347dfd9781976 (main).

Disclosure: before writing this file the lane read source on main (no code written, nothing built or run). That read is why the "not reachable" outcome is registered with specific places to check. What it found is listed under "Expected from the source read" and is a reading, not a result. The registered test below decides.

## Hypothesis
H1 (the issue's premise): on main, `moe_at_layer(prof, l)` (`prover/prover/layout.h`) returns true for a dense model (NE 0) on odd layers when `prof >= 3`, so the forward pass would run `ffn_moe()` where the committer, the hiding stage and the verifier treat the layer as dense.

H1 has two parts and each is tested on its own:
- H1a (the function alone): `moe_at_layer(prof, l)` disagrees with the reference rule `prof >= 3 && (l & 1) && NE > 0` for NE 0, odd l, prof >= 3.
- H1b (reachability): some caller on main passes `prof >= 3` while the parameter file has NE 0, so the disagreement is reached in the prover.

## Metric
1. Enumeration (host only, g++, no CUDA): for prof in {1, 2, 3, 20}, layer l in 0..7, NE in {0, 1, 16} (96 cases), count the cases where each arm disagrees with the reference rule `prof >= 3 && (l & 1) && NE > 0`:
   - Arm A, the function alone: `moe_at_layer(prof, l)` from main's unmodified `prover/prover/layout.h`, included as a header.
   - Arm B, the path as the prover composes it: `moe_at_layer(P(NE), l)` where P(NE) is the value main assigns to `LayerShape::prof` before either caller runs. The source read must name every assignment of `LayerShape::prof` with file and line; the arm uses exactly that expression. If a caller can see more than one value, every one is tested.
   - Arm C (risk check on the prior-art change, not a fix we propose): the fork-style rule `prof >= 3 && (l & 1) && NE > 0` evaluated with the `LayerShape` that main's `layer_words_fit()` caller builds (`prover/prover/inputs.cuh`), for MoE models (NE in {1, 16}). This checks whether passing `s.NE` at that call site would drop the router-shift check for MoE models, because that `LayerShape` may never have its NE set.
2. Source read with line numbers on main: every caller of `moe_at_layer`, every assignment of `LayerShape::prof` and `LayerShape::NE`, and every other place that decides "expert layer" from a profile and the layer number alone (prover, committer, hiding stage, verifier). Table in RESULTS.md.

Unit: count of disagreeing cases out of 96 (arm A, B) or out of 64 (arm C: NE in {1, 16}, all prof, all l; disagreement counted only where the reference is true).

## Acceptance threshold
Fixed now. Exactly one outcome is recorded.
- "reachable, fixed": arm B has at least one disagreement (necessarily NE 0, odd l). Then the lane makes the one-line change (NE > 0 in the rule, each caller passing an NE that is set on its shape) and a host-only test; PASS needs: the new test fails on unmodified main for every NE 0, odd l, prof >= 3 case and passes after the change in all 96 cases; and every existing host unit test under `prover/tests/unit.sh` that needs no GPU has the same outcome before and after the change.
- "not reachable on main": arm B has 0 disagreements of 96. Then the lane changes no prover, verifier or committer code, records where the gate is (file and line), and the issue's premise H1b is FALSE on main. H1a is reported separately (expected true: 16 cases, prof in {3, 20}, NE 0, l in {1, 3, 5, 7}).
- Arm C is reported as a count with no pass threshold: it is a risk note on the prior art. Any nonzero count is written into RESULTS and the PR body as a reason not to port that call-site change as is.

## Kill criterion
Hard stop 2026-11-17T11:30:00Z (lane deadline). If main's `layout.h` cannot be compiled on the host by g++ without CUDA headers, the enumeration falls back to a copy of the two-line function body, disclosed as such, and that weakens arm A to a text comparison; say so. If the source read finds an assignment of `LayerShape::prof` whose value cannot be decided from the source, record "undetermined" for arm B and stop with a partial result.

## Runs
Deterministic enumeration: no seeds, no timing, no randomness. The registered program is compiled once and run twice in a row on cores 2-3; both runs must print byte-identical output (checked by SHA-256 of the output files). Identical output stands in for a spread. Before the registered runs the program is only compiled (compile errors may be fixed); it is not executed before the registered run. Any execution before the registered run is listed as a deviation. If the "reachable, fixed" outcome applies, the existing no-GPU host unit tests run twice before and twice after the change, with identical outcomes required.

## Prior art
- marcellobardus/FlashProve-TinyLlama1.1B, commit 26dd68f962d0f227a7c450b6d486dc9b7e5a0f3a (public fork, read through the GitHub API only; no code copied, nothing cloned, built or run). Its message reports that a dense prove on an H100 stopped with UNFIT and that `moe_at_layer()` taking NE fixed it, with a CPU test. Read here as data only. Its parent commit's `prover/prover/layout.h` and `prover/prover/forward.cuh`, and its own `prover/prover/inputs.cuh` and `prover/prover/layer_setup.cuh`, have the same git blob ids as main at the base commit, so the call paths compared are the same text.
- In-repo: `experiments/20261113-156-dense-table-digests` (PR #158, dense parameter files admitted by the verifier) and #182 (CPU reader alignment). `docs/qwen-port.md` states no dense proof has been made on main.
- Outside FlashProve (zkML provers: zkLLM, EZKL, Jolt, Expander) there is no counterpart: this is a dispatch-predicate consistency check inside one codebase, not a new proving technique.

## Expected from the source read (not a result)
`LayerShape::prof` is documented as "not the prof of the parameter file" (`prover/prover/layout.h` lines 27-28). It is assigned `mo ? 3 : 2` with `mo = NE > 0` at `prover/prover/layer_setup.cuh` line 70 (feeds `forward()` via `make_layer_layout`) and `prover/prover/inputs.cuh` line 293 (feeds `layer_words_fit()`), and the parameter file's own prof (must be 20) never reaches `moe_at_layer`. If that holds, arm B is 0 and the outcome is "not reachable on main". Arm C is expected nonzero, since the `LayerShape s` at `inputs.cuh` line 292 sets prof, xl and digit forms but not NE.

## Amendments
- 2026-11-17 09:14 UTC, before any run, committed with the code: `enumerate.cpp` prints four extra counts besides the registered ones. They decide nothing; they only split the registered counts so the report can say where any disagreement sits. (1) `armB_disagree_ne0` and `armB_disagree_prof20`: arm B restricted to NE 0 and to prof 20. (2) `armB_own_prof_disagree`: the prover's call `moe_at_layer(P(NE), l)` against `ref(P(NE), l, NE)`, i.e. against the reference at the prof the prover actually runs with (24 cases). (3) `armC_main_prof_missed_moe`: arm C with prof = P(NE) as main assigns it, besides the registered arm C with the enumerated prof. Compile flags: `g++ -O2 -std=c++17 -Wall -Wextra -I prover` (13.3.0); the build compiled without warnings and was not executed before this amendment.
- 2026-11-17 09:16 UTC, before any run: a flaw in the registered metric, found by reading `enumerate.cpp` back, not by running it. Arm B feeds `moe_at_layer` the prof main assigns, P(NE) = (NE > 0 ? 3 : 2), but compares with the reference at the enumerated prof. For enumerated prof 1 or 2 with NE > 0 on odd layers, the reference is false and P(NE) = 3 gives true, so `armB_disagree` counts 16 cases (prof {1, 2} x l {1, 3, 5, 7} x NE {1, 16}) that are not the issue's question (dense NE 0) and not reachable as stated (a parameter file must have prof 20: `prover/common/parameter_file.h` line 176). The PREREG's own text said a reachable disagreement is "necessarily NE 0, odd l". Change: the outcome is decided by `armB_disagree_ne0` (arm B restricted to NE 0, 32 cases): 0 means "not reachable on main", above 0 means "reachable". `armB_disagree` is still printed and reported with this explanation. Expected value of `armB_disagree` from reading the code: 16, all with NE > 0 and prof < 3. If it has any case with NE 0, that alone means "reachable".
