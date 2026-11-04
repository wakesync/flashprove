# PREREG: 20261103-11-qwen38-27b-feasibility
Issue: #11. Lane: qwen3.8-27b port feasibility (desk, CPU only). Date (UTC): 2026-11-03T23:12Z. Base commit: ae70e447b57f0f466c5012c88c9e41bf5a9d5712.

Registered before any script or the feasibility write-up. At registration the only inputs read were the
publisher model listing and config for `Qwen/Qwen3.8-27B` (to confirm the model exists and is a
dense hybrid, not MoE) and this repository's docs. Nothing below has been computed yet.

## Hypothesis
Qwen3.8-27B's text decoder needs strictly fewer new proof-relation operator families than
GLM-5.3-Flash (as inventoried in the prior port-feasibility research), and its committed integer
text weights are at most 0.25x the committed weight count of the Maverick shape FlashProve already
proves, so that a first port is bounded by operator work, not by commitment size.

## Metric
1. Parameter count: exact element count of every tensor in the 18 publisher safetensors shards at a
   pinned revision, read from shard headers only (HTTP range requests of the 8-byte length plus the
   JSON header, no tensor data). Reported split into text matrices, embedding, head, MTP, vision.
2. Committed integer weight count: text decoder matrices + embedding + output head, the set that
   `docs/model.md` section 3 commits for Maverick, computed for both shapes from their config
   numbers; ratio Qwen / Maverick.
3. New operator families: count of distinct operator families in the Qwen text forward pass (from the
   pinned Transformers reference) that have no counterpart in `docs/model.md` sections 5-8, each
   cited to a source line. Same count for GLM-5.3-Flash and DeepSeek-V4.1-Flash, taken from the prior
   feasibility notes and their pinned sources, not re-derived from memory.

## Acceptance threshold
PASS if both hold: (a) new-family count Qwen < new-family count GLM-5.3-Flash; (b) committed
integer weight ratio Qwen / Maverick <= 0.25. Otherwise FAIL, reported with the same rigor.
Prove-cost figures are estimates by linear scaling of per-token matrix work from the Maverick timed
runs in `guide/performance.md`; they are labelled estimates and are not part of the threshold.

## Kill criterion
Stop and publish a negative if: the pinned config shows routed experts (then it is not the dense
model this lane was scoped for), or the pinned reference implementation is unavailable so that op
semantics cannot be cited, or the desk budget (about 2 hours, no GPU, no download of any file over
5 GB) is exceeded.

## Runs
The parameter count is deterministic. The header-reading script is run 5 times against the pinned
revision; all 5 outputs must be byte-identical (SHA-256 compared), otherwise the count is reported as
unstable and the threshold is not evaluated. No seeds (no randomness). No warmup. Nothing excluded.
No performance measurement is made in this lane, so the >=10-run perf rule does not apply.

## Prior art
- In this repository: `docs/model.md` (the integer Maverick relation), `research/operators/glm_kda_slice/`
  and `research/operators/glm_kda_fixedpoint/` (toy proofs of a delta-rule recurrence, the GLM KDA
  variant), and the prior GLM/DeepSeek port-feasibility research (not on main; its conclusions are
  restated with their pinned source URLs).
- zkML for transformers: zkLLM (Sun et al., CCS 2024; tlookup + zkAttn for softmax attention),
  EZKL (Halo2 circuits for ONNX graphs, small models), Jolt (lookup-based zkVM; general programs,
  not specialised to LLMs), Expander/Polyhedra (GKR-based data-parallel circuits). None of these
  reports a proved gated-delta-rule / linear-attention recurrence at checkpoint scale; that is the new
  part here, and this lane only scopes it.
- TEE alternatives (H100 confidential computing, TDX/SEV-SNP; Phala, Atoma, Nillion) are out of scope
  for this lane: they attest execution, they do not prove an integer relation.

## Amendments
(empty at registration)

Amendments are recorded after the fact, in response to the independent review of PR #28. Nothing
above this section has been edited; the registered text stands as committed in `d0dab1d8`.

- **A1 (2026-11-04T08:55Z). Family-counting rule for threshold (a) was written after registration.** The
  registered Metric 3 says only "distinct operator families ... that have no counterpart". The
  operational rule used for the tally ("one family = one new kind of constraint or table in the
  integer relation; a new size of an existing gadget is not a family") first appears in
  `research/ports/qwen3.8-27b/FEASIBILITY.md` section 4, in the results commit `b02890af`
  (2026-11-03T23:31Z), after the counting script `a6a6b811`. The earlier wording "fixed before
  tallying" in FEASIBILITY.md and RESULTS.md was therefore not a pre-registration claim and has been
  corrected. Consequence: threshold (a) was judged under a rule chosen after registration, by the
  same author who did the tally. That weakens (a); it is reported as **(a): holds, judged under a
  post-registration counting rule (not a pre-registered test)**. Threshold (b) is unaffected: its
  metric (Metric 2) is fully specified above and was computed as registered.
- **A2 (2026-11-04T08:55Z). Evidence path for the GLM / DeepSeek counts.** Metric 3 says the GLM-5.3-Flash and
  DeepSeek-V4.1-Flash counts are "taken from the prior feasibility notes and their pinned sources".
  The two pinned configs are now committed in `sources/` (SHA-256 identical to ENV.json, re-fetched
  at the pinned revisions). The prior feasibility notes themselves are not on main, so the family
  lists (11, 12) remain a judgement against unmerged notes; (a) is labelled accordingly and is not a
  claim for `claims.json` until that evidence is merged.
- **A3 (2026-11-04T08:55Z). Per-token MAC figure renamed, not part of either threshold.** `count_params.py` now
  reports `per_token_matrix_macs_text` as 2-D text matrices + head only (25,621,954,560); the earlier
  figure, which also counted norm gains, A_log/dt_bias and conv1d taps (25,624,600,064), is kept as
  `per_token_macs_text_incl_gains_and_conv_taps`. The 5 runs were re-run (byte-identical, new output
  SHA-256 in ENV.json). Parameter counts and the (b) ratio are unchanged.
