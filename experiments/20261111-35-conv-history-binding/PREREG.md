# PREREG: 20261111-35-conv-history-binding
Issue: #35. Lane: conv35. Date (UTC): 2026-11-11 01:35. Base commit: 1ef75fd3cb759fd9dd83b5e25160b9557c568de9.

## Hypothesis
If the four-tap causal conv1d proof's three carried history words are pinned inside the proof to a public opening whose SHA-256 tail root must equal a root the verifier already holds (the previous segment's committed tail), and the segment's own outgoing tail (its last three inputs) is pinned to a public opening that becomes the verifier's next root, then the PR #67 replaced-history construction (same public outputs, consistently changed history and new inputs) is rejected, together with at least three further hostile history variants, while honest two-segment chains are still accepted.

## Metric
Counts of accepted/rejected verifier decisions, per arm, per seed (one run = one seed, one fresh fixture, one full set of proofs). Arms:
- `honest-chain`: genesis root R0 over a seeded initial history, segment 1 verified against R0 gives R1 from its outgoing opening, segment 2 verified against R1. Accept means both segments accept and the carried root matches.
- `c67-unbound` (named negative control, live check): the #67 `history-control` construction (`research/operators/qwen_ops/proof.cpp`, mode `history-control`: halve the seeded window, taps S/2, then x[0]++, x[1]--, x[4]++, x[5]--) proved and verified on this lane's copy of the unbound conv profile. Expected: BOTH proofs accepted for the same public outputs (the gap is reproduced, so the control is not vacuous). This arm is not a hostile case and does not count toward rejection.
- `c67-bound`: the same construction against the bound profile with the verifier holding the original history's root. Two sub-cases, both must reject: (a) the replacement's honest proof with its own (replacement) history opening; (b) a complete malicious proof of the replacement witness under the original opening.
- New hostile variants, each with the statement-level and, where feasible, a complete malicious proof sub-case: `tail-splice` (segment 2 proved from a different history, zero history, than segment 1's tail), `out-tail-lie` (segment 1 publishes an outgoing opening that is not its last three committed inputs), `history-reorder` (segment 2's witness uses the carried tail in reversed order), `cross-scale-root` (root computed for F14 over the same words presented to the F12 verifier), `proof-transplant` (segment 1's proof bytes presented with segment 2's statement), `segment-replay` (segment 1's statement and proof presented again when the verifier holds R1).
Complete malicious proofs use the existing technique of PR #67 (`prove(...,hostile=true)`: every product equation holds, the prover's affine targets are replaced by locally true values, the unchanged verifier keeps its own targets). Also measured descriptively: columns, relations, proof bytes, prove and verify seconds of the bound vs unbound conv profile (median, sample SD, min, max), on a shared loaded CPU host. Not a performance claim.

## Acceptance threshold
PASS iff all of: honest-chain accepted 10/10 seeds; c67-unbound accepts both proofs in every seed (control live); c67-bound (a) and (b) rejected in every seed; each of the >= 3 new hostile variants (all sub-cases) rejected in every seed; any `hostile did not violate relation` or witness self-check failure is a harness bug and counts as FAIL, not as a rejection. A single acceptance of any hostile sub-case in any seed is FAIL.

## Kill criterion
KILLED if the binding cannot be built without editing the committed PR #67 files (`research/operators/qwen_ops/*`) or PR #98's files, or if the implementation is not running by 2026-11-11T03:20Z (lane deadline 03:55Z). Stop and publish FAIL on the first registered run that accepts a hostile sub-case; do not tune and rerun. Free disk below 3 GB: stop.

## Runs
Registered suite: seeds 1..10 for every arm (n=10 per arm, >= 5 required), one process per seed, fixed toy coins derived from the seed, no warmup exclusion, no seed excluded. The suite is run once. A UBSan build repeats the full registered suite once (same seeds). Debug before the registered run uses ONLY seeds 101..103, disjoint from the registered seeds, and is kept under ignored `work/`, not committed as evidence. CPU only, pinned to <= 2 cores, shared loaded host, through the heavy-job gate if a run exceeds two minutes of CPU.

## Prior art
- PR #67 (this issue): bounded local conv1d relation; history, kernel and inputs prover-chosen; registered the negative control this lane targets.
- PR #98 / issue #93 (DeltaNet two-chunk handoff, draft at registration): verifier-owned initial root, SHA-256 of a domain string plus little-endian words, checked outside the arithmetic proof, words pinned inside the proof, statement bound into the transcript. This lane reuses that pattern for the conv tail; it does not edit #98 files.
- #34 / PR #71 (state commitment): chained state commitments across chunks for DeltaNet state, not the conv tail.
- Inference engines carry a per-layer `conv_state` of width-1 = 3 tokens between decode steps for causal-conv1d layers (Mamba / Gated DeltaNet implementations); this is exactly the object bound here.
- zkML: EZKL offers "hashed" input/output visibility (Poseidon commitment to public inputs) but has no carried recurrent state across proofs; zkLLM and Jolt-based zkML prove single forward passes. IVC/folding (Valiant 2008; Nova 2022) carries a state commitment between steps inside the proof.
What is new here: nothing cryptographically. A plain public-opening tail root, hash checked by the verifier outside the proof, no in-circuit hash, no hiding of the tail words. The contribution is closing the specific registered #67 gap on the toy profile and measuring it with hostile proofs. Kernel identity, model-input provenance, norm/decay/admission items of #35 are out of scope.

## Amendments
