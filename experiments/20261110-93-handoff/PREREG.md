# PREREG: 20261110-93-handoff
Issue: #93. Lane: handoff. Date (UTC): 2026-11-10. Base commit: 38523f9c6474465edda37613ebe7135b3d4acc4b.

## Hypothesis
A joint product-oracle proof for two consecutive synthetic DeltaNet chunks, with explicit in-proof equalities between their boundary state/history cells and a verifier-owned statement, accepts honest windows and rejects each named #71 construction without relying on a Python chain comparison.

## Metric
Boolean complete-proof verification for honest and hostile windows, with the number of violated affine relations reported separately. Count core product columns, aligned columns, affine relations and range cells per token using a committed counting script and compare against the built relation. These are counts of this lowering, not memory/fit measurements. No speedup or production-security claim.

The verifier owns F, D, request, layer, model/weights identifier, chunk policy, window length, initial state/history root, public token inputs, public pre-conv inputs and public outputs. The initial SHA-256 root is an anchor to a public initial-state/history opening supplied by the verifier, not an in-circuit SHA gadget. The interior state/history handoff is witness-to-witness equality inside one joint proof, not two independently resumable proofs. No hidden initial state or private hash opening is claimed. Model/weights identity is transcript-bound synthetic provenance only; no weights are downloaded and no weight matmul is proved. History is proved to be the correct shift register of public pre-conv inputs, not their convolution or their link to the post-conv recurrence inputs.

## Acceptance threshold
H1: every honest proof accepted for five seeds, two chunks of two tokens, D=8, F=12.
H2: every named hostile construction rejected for each of those five seeds: mixed F12/F13, split chunk, replaced token inputs, two-sided history shift, changed last-chunk history, other layer, other first state, dropped chunk, truncated window, prefix-only window. Also test another model/weights identifier, another request, changed intermediate state, and unchanged-proof replay under a changed verifier statement. Complete hostile proofs use locally true prover linear targets against unchanged verifier relations; rejection must occur in the proof verifier. Public statement replay tests are separately labelled transcript binding. No target change is counted as a repair of the verifier.
H3: a committed script's exact counts match all honest built relations. Formula extrapolations at D=32/128 are labelled counted-not-built.
All H1-H3 are required for PASS; otherwise report FAIL or KILLED. No performance hypothesis.

## Kill criterion
Hard lane stop 2026-11-11T00:37Z, including queue time. Registered suite elapsed budget 45 minutes from fp-heavy slot acquisition; stop incomplete work and report KILLED. CPU only, no paid services, no downloads of model weights. Use cores 0-5 with at most one proof process at a time. If the inherited arithmetic cannot safely be adapted, publish the negative rather than substitute outside-proof rejection.

## Runs
Five independent synthetic seeds 101, 102, 103, 104, 105, ascending order; honest then named hostile cases per seed. No warm-up or timing comparison. Retain all cases, no exclusions. Report n, median, sample SD, min and max for counts and Boolean outcomes. Deterministic research proof coins and inherited low research security are explicit limitations. Debug fixtures use seed 909, D=4, two chunks of one token only, never any registered suite instance. Registered suite is not run before the registered run. Count-only larger shapes have no proof and are not performance runs.

## Prior art
Merged #71 provides the SA per-token M1b product/RNG lowering and public SHA-256 chain bookkeeping, with explicit missing in-proof linking and unbound token/history inputs. Its reviewer constructions motivate this suite. blocks/toy/segments.h demonstrates kept-oracle-row handoff in a segmented proof, but directly composing that frame with the lookup/RNG protocol is not assumed implemented here. This bounded milestone instead combines two chunks in one product oracle with equality relations, at full per-token cost. EZKL and zkLLM are broader zkML systems; this is not an end-to-end comparison or a new proof system. The novelty claimed is a tested DeltaNet-specific joint-boundary relation and verifier-owned statement, not a scalable continuation protocol.

## Amendments
- A1 (2026-11-10, after code, before the registered suite): the declared joint proof has two fixed-size witness slots. Split/drop/truncation/prefix constructions are encoded by claimed chunk count/ranges/lengths in those slots, with identity padding for missing computation. A split is not three independently valid proofs: separately resumable/variable-size proofs remain outside this milestone. This narrows how H2 must be described, not its required rejection outcomes.
- A2 (2026-11-10, after the first disjoint debug attempt, before the registered suite): the inherited #71 sizing can fill an RNG multiplicity row exactly on tiny heads and overlap its sample pad. Reserve `E_DEGREE * samples` places in addition to the larger digit/multiplicity extent. Keep all RNG checks. This changes proof padding only, not core column/relation counts or thresholds. The failed debug binary receipt is retained as `runs/build-debug-1.json`; no registered seed has been run at this point.
