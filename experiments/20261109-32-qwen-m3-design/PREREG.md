# PREREG: 20261109-32-qwen-m3-design

Issue: #32 (touches #34, #35, #7, #8). Lane: qwen-m3-design. Date (UTC): 2026-11-10T00:50Z.
Base commit: 8ec7c79969ca4ca6044dc4c8b79fe4385910fe8c, the head of PR #66 (the M2 design). #66 is open
and not on main; this lane reads its files, so it branches from that head. main was
4f7a876151c309f0159e88b18c8e286d4e1909c9.

This is a design and counting lane. No proof is built. No GPU, no weights, no paid API. Every number
this lane produces is either a count from a model (deterministic, n = 1) or an extrapolation. None
is a measurement of a Qwen proof, and none may be reported as one.

## What was looked at before this file was committed (disclosure)

- Read: DESIGN.md and RESULTS.md of #66, FEASIBILITY.md, issues #32, #34, #35, #8,
  docs/architecture.md, docs/model.md, docs/protocol.md sections 1 to 6, guide/performance.md,
  research/results.yaml, the head comments of blocks/iop/{req,lin,foldeq,link,member,rng,lkp,psc,
  relation,laid}.h, prover/README.md, and the sibling lanes' briefs and STATE files.
- Ran the upstream planner (`cp_verify -plan arrays` and `-plan accounting`) on the stored
  configuration `prover/examples/target_full_f2`, and summed the planner's array sizes with a
  short script: 10,573,982,429 committed entries for one 1,024-token request (12 layer links of
  about 6.05e8, 12 attention links of 2.32e8, one head link of 5.27e8).
- Fitted "seconds per batch = p x passes + q x requests" to upstream's four published rates
  (guide/performance.md: batch 1, 8, 24, 64), solving on batch 1 and 8 with 2 opening passes per
  batch: p = 18.16 s per pass, q = 4.33 s per request; it predicts batch 24 and 64 within -3.6%
  and -3.4%. Because this was seen before registration it is registered as descriptive (D1), not
  as a hypothesis.
- Nothing was counted for Qwen. The planner was not run at any other shape. No M3 counting code
  existed. A first draft of this file was written before the fit above was run and was replaced by
  this one before any commit.

## Hypothesis

A first Qwen statement in which the proof does real work (weights committed, so the verifier
cannot recompute it) can be specified on machinery that exists in this repository plus the three
interfaces other lanes are building (state commitment #34, operator gadgets #35, the lookup
composition), such that its smallest instance fits the CPU research harness; and a counting model
anchored on measured statements and on the upstream planner says whether the full text model fits
one H200 (141 GB).

Sub-hypotheses, each falsifiable:

- **H1 (the model still reproduces what was measured).** The M3 counting model, at the M1 and M1b
  statement shapes, reproduces the measured M1 (#47) and M1b (#63) statements on the ten quantities
  that #66 checked (columns, relations, terms, range cells, log-length).
- **H2 (M3 reduces to M2).** With every M3 addition switched off, the M3 model gives the #66 M2
  head counts for arm B at T = 16: 1,056,800 gate columns, 272,384 range cells, 276,688 lookup
  keys, 2,402,432 relations, table log-length 21.
- **H3 (the smallest M3 statement fits the CPU harness).** M3a-head, defined here before counting:
  one V head of one DeltaNet layer, from the layer's normed input a (public, T x 5,120) to that
  head's out_proj contribution (public), with the head's in_proj and out_proj rows as proved
  matmuls against committed weights (a product argument, no gate per multiply), and with conv,
  SiLU, the q/k L2 norm, the decay and beta gates, the recurrence and the gated norm all in
  relation on committed cells, T = 16, F = 12, remainders and nonlinear tables by lookup (arm B).
  Claim: it fits a product table of log-length <= 22 with at most 2^23 relations (the harness's
  own guard).
- **H4 (the upstream planner is a usable anchor for the dense family).** The planner accepts a
  proxy shape for Qwen's dense parts (no experts, d = 5,120, f = 17,408, V = 248,320, 64 layers),
  and its layer-link entry count is linear in f: the count at f = 17,408, predicted from the
  planner's counts at f = 8,192 and f = 16,384, is within 1% of the planner's own count.
- **H5 (full model, one H200).** Under the decision rule below, a 1,024-token window of the full
  text model (48 DeltaNet layers, 16 attention layers, 64 MLPs, norms, embedding, head; vision and
  MTP excluded) fits one H200 in at least one lowering this design names concretely. Registered
  expectation: it does NOT fit in the only DeltaNet lowering that has been built (the wide product
  oracle, every state in the table), and the binding constraint is the DeltaNet state trace, not
  the weights.

## Metric

Counts, deterministic, from `research/operators/qwen_m3/count_m3.py` (written after this file):

- **Research-harness lowering** (wide product oracle, RNG, LKP): gate columns, RNG range cells,
  lookup keys, relations, relation terms, laid table log-length. Same counting rules as
  `research/operators/qwen_deltanet_m2/count_model.py`; its `head()` and `layout()` are the
  reference for H1 and H2.
- **Packed lowering** (the upstream prover's form: committed arrays of cells, three cells to an
  entry (`LANES`, docs/format/11-1-machinery.md), sumchecks, lookups, the smallness test):
  committed entries (field elements) per token and per window. Dense family: from the upstream
  planner at a proxy shape. DeltaNet: a design count, cells listed one by one in the code, 2 cells
  per state cell per token (the new state and one floor remainder), times an overhead factor
  taken from the planner (the non-cell arrays of a Maverick layer link over its cell arrays).
- **Weights**: committed integers and bytes, from the shapes in FEASIBILITY.md.

Extrapolations. Each is labelled "extrapolated" with its assumption and is never put in a table
with measurements:

- **Prove time** per window = p x passes x (Qwen committed weights / Maverick committed weights)
  + q_e x committed entries, with p = 18.16 s and q_e = 4.33 s / 10,573,982,429 entries (D1), 3
  passes at one request per batch. Source of p and q: upstream's published rates for Llama 4
  Maverick on one H100, whose records are not in this repository and which this fork has not
  reproduced. H200 speed is taken equal to H100. A second calibration from this fork's own measured
  small synthetic example (cp_prove 2.35 s, PR #26) over that example's planner entry count is
  reported as an upper bound only, since it is dominated by start-up.
- **Commit time**: linear in committed weights from upstream's "about 39 minutes" for Maverick.
- **VRAM**: b x (entries of the largest segment in flight, one request per pass), plus weights if
  held resident. b central = 80,629 MiB / (6 x entries of the largest Maverick segment), from the
  one published point (64 per batch, six requests per pass). That point is the card's ceiling, so
  b central is an upper estimate of need. b low = 16 bytes (one 8-byte element under a rate-1/2
  code and nothing else). b high = 2 x b central.
- **Proof size**: linear in committed entries from the planner's 18.78 MB for Maverick.
- **Cost**: GPU-seconds per token. USD only at a stated hourly rate, which is an assumption.

## Acceptance threshold

- H1: exact equality on all ten quantities. Any mismatch is FAIL.
- H2: exact equality on the five quantities. Any mismatch is FAIL.
- H3: PASS if log-length <= 22 and relations <= 2^23 at T = 16 under arm B. Reported without a
  threshold: the same statement under arm A (exact bits, the lookup build's fallback), the largest
  T that fits under each arm, and one full DeltaNet layer as a single harness statement (48 V
  heads; expected not to fit).
- H4: PASS if the planner returns arrays for the proxy shape and the linearity error at
  f = 17,408 is <= 1%. If the planner refuses the proxy shape after 20 minutes of trying, H4 is
  KILLED and the dense family is scaled from the Maverick planner counts instead, with that
  stated.
- H5 decision rule, fixed now. "Fits one H200" for a window means both:
  (a) central VRAM estimate <= 127 GB (90% of 141 GB) at one request per pass, weights streamed;
  (b) central prove-time estimate <= 3,600 s per window.
  The verdict is given for each named lowering and state strategy. If the central estimate fits
  and the high estimate does not, the verdict reads "fits on the central assumption, not robust".
  The binding constraint is the term that is largest in the first lowering that fails, or, if all
  fit, the term with the least headroom.
- D1 (descriptive, seen before registration): the two-parameter fit of upstream's rates.

## Kill criterion

- Time box 3 hours from 2026-11-10T00:08Z. At 2h30 the lane stops counting and writes up what it
  has, including any hypothesis not reached, as "not run".
- Any prototype over 10 minutes of CPU is not run. None is planned: the counts take seconds.
- If H1 or H2 fails, the M3 counts are not reported as anchored: fix the model or report FAIL.
- Under 3 GB free disk: stop writing and report.

## Runs

Counts are deterministic functions of the shape: n = 1, no seeds, no spread. The planner calls are
deterministic too; each is run once and its output stored under `runs/`. No timing is measured in
this lane. No run is excluded.

## Prior art

- In this repository: M1 (#47), M1b (#63) and the M2 design (#66) for the DeltaNet head; the
  feasibility study (#28); upstream's proved dense family (docs/model.md) and its published
  Maverick rates (guide/performance.md).
- zkML systems that prove transformer inference: zkLLM (tlookup, attention-specific arguments),
  EZKL (Halo2 circuits), Jolt and Expander style sumcheck or GKR provers, and GKR-based LLM
  provers that report GPT-2 scale. None is known to this lane to prove a gated delta-rule
  recurrence with a carried matrix state, or a 27B-parameter model end to end on one GPU.
- Recurrent state across steps: incrementally verifiable computation and folding (Nova family)
  are the usual tools; this project uses a hash-based IOP with carried commitments instead, and
  #34 owns that comparison.
- TEE-only alternatives (H100/H200 confidential computing, TDX, SEV-SNP; Tinfoil, Phala) attest the
  software, not the arithmetic.
- No literature search beyond these lists was done in this lane. What is new here is a statement
  design and a cost model for one specific model on one specific GPU, not a new argument.

## Amendments

(empty at registration)
