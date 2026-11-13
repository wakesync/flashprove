# The Qwen3.8-27B port: where it stands

This page tracks Qwen3.8-27B and its abliterated checkpoint under proof. Tracking issue:
[#32](https://github.com/wakesync/flashprove/issues/32).

**No end-to-end proof of the real Qwen3.8-27B model or an abliterated reply exists in this
snapshot.** There are synthetic CPU proofs of components, real-weight numerical measurements,
and designs and cost counts. A numerical forward through all layers is not a proof. [E1, E3, E5, E12]

Updated from main pinned once at `59bff9a4608e0cc720d58d7c30823a8838fa43e4` (2026-11-13).
“Built” below means the cited build evidence is in that tree, not that it proves the real model.
Historical verdicts stay as recorded. This is a documentation refresh, not an experiment: no
PREREG or results-ledger row is added. PRs #173, #174 and #180 merged after the pin and are
summarised only in the dated section below. PRs #178 and #179 were open at the pin and remain
open at the main revision checked below; neither is used. The
[evidence map](qwen-port-evidence.md) gives the source path, section and scope for every E-reference.

## Merged after the pin (not incorporated above)

2026-11-13 update, checked against main `4991f69acbc9db0c9cd0bc80b79ad658078e3737`.
Except for this dated section, the body remains the snapshot at the original pin and was not
re-derived; the pointers below do not replace its historical verdicts.

- **PR #173: FAIL** on the registered integer-MLP token-agreement bar for the abliterated XM18
  path (XS18 heads plus M3 integer MLP): top-1 agreement is 1,423 of 1,461 positions (97.40%
  against >= 99.0%), and both registered KL criteria also fail. This is measured, unreplicated
  numerical evidence, not a proof or a stock-leg result, and it does not move the original run's
  cutoff. [E19]
- **PR #174: KILLED** for XS18, XS18+U4 and XS18+U3 in the abliterated decay-table end-to-end
  run after 21 of 64 layers. No logits were produced, so the token-agreement hypothesis remains
  untested; the partial measurements are descriptive, unreplicated and not a proof. [E20]
- **PR #180: design only**, a desk note on head dimension 256 and partial rotary, not a
  registered experimental PASS/FAIL verdict. It supplies no implementation, measurement,
  soundness theorem or build green light. [E21]

## Why this is a port, not a loader change

Qwen's text model is dense, with 64 layers: 48 Gated DeltaNet layers and 16 full-attention layers.
Each DeltaNet layer has 48 value heads, each carrying a 128 x 128 state. Its full-attention shape
has query width 6,144 against stream width 5,120, head dimension 256 and partial rotary embedding.
These are architectural requirements, not evidence of prover support. [E2]

## Merged evidence at a glance

| work | status at the pin | what that status does not mean | source |
|---|---|---|---|
| M1 and M1b | Synthetic CPU head proofs built. M1 FAIL on its registered range test; M1b PASS on its own thresholds | No real weights or full layer proved | E3 |
| M2 two-lookup build | Built, including the 16-token head. Original H4 **NOT PASSED**; separately registered H4-r2 **PASS** | Not a retrospective H4 pass, production security or real-model fidelity | E4 |
| Whole-forward, head-only fidelity | XS18 and XS20 PASS on both checkpoints, teacher-forced, with only DeltaNet head arithmetic lowered | Not a fully integer model or a proof | E5 |
| Served-reply comparison | Registered bars PASS on the recorded abliterated replies | Reconstructed token ids, not observed server ids; no CPU free-running generation or proof | E6 |
| Integer MLP | **PARTIAL / NOT FINISHED** on token agreement; input class exceeded on the layers completed | No MLP token-agreement verdict; the state-regeneration follow-up adds no logits. For the later registered **FAIL**, see [Merged after the pin](#merged-after-the-pin-not-incorporated-above). | E7 |
| Norm classes | **PARTIAL**, no registered all-layer arm verdict; measured class/fidelity failures | No logits, no token agreement, no selected arithmetic | E8 |
| Decay round 2 | U1/U2/U3 FAIL; U4 PASS as decay-only emulation | U4 is not a built committed-table lookup or end-to-end test | E9 |
| Stock-vs-abliterated U1 margin | **FAIL (mixed)** on all 10 registered prompts | Not a detection algorithm or an impossibility theorem | E10 |
| Dense table-digest admission | Dense verifier planning accepts the required table digests | No dense proof or dense `YES`; producer reader still mismatches | E11 |
| Query-width design | Merged desk audit of `dq != d` | No gate opened; head dimension and partial rotary remain barriers | E11 |
| M3 | Merged design and counts for committed-weight proofs | M3a through full-model milestones are not established builds | E12 |

## What the proof machinery actually covers

The two-lookup build composes range checking and exact remainder checking. The smaller, four-token
statement accepted 10/10 honest proofs and rejected 95/95 hostile cases. For the full 16-token head,
the original H4 missed its stop rule and left its hostile suite incomplete. H4-r2 separately accepted
10/10 honest proofs and obtained all 129/129 expected hostile-suite verdicts, normally and under
UBSan. The suite includes acceptance controls, so 129/129 does **not** mean 129 rejections. [E4]

Those proofs use synthetic inputs and head constants, F = 12, a 10-bit research target and toy
coins. The verifier recomputes the public front end; this does not bind the head to a real
checkpoint or compose a model proof. The build remains unreplicated; its sampled hostile cases
and paper composition argument do not establish general soundness or production security. [E4]

M3's planned statement instead binds weights and intermediate values. Its efficient function lookup
keyed on committed statement cells, Qwen weight-table range proof and ties to that table remain
build obligations in the design. The completed M2 remainder lookup is not completion of those
obligations. M3a is the CPU head/layer plan; M3b is a GPU block plan; M3c/M3d extend to all layers,
then real stock and abliterated weights. [E12]

The state-commit study recommends full-state handoff at chunk boundaries (SA at C = 64), not the
cheaper low-rank SB construction. Its registered SB drift test failed; its descriptive higher-precision
arm is not a sound lowering in that study. Neither that study nor M3's low-rank count establishes a
full-model state proof. [E13]

## Real-weight fidelity: what improved and what is still missing

### Head-only teacher forcing

The whole-forward comparison covers 10 prompts and 1,461 positions on stock and abliterated
weights, with XS18 or XS20 in every DeltaNet layer. All four cells pass their registered bar:
top-1 matches are 1,460/1,461 except XS20 stock at 1,461/1,461. Projections, full attention, MLP,
norms and the output head remain float64. This is measured, unreplicated, deterministic CPU
numerics, not proof-ready relations. [E5]

Deeper-layer work is no longer unmeasured: the earlier deep-fidelity study tests layers 16 and 20,
and the whole-forward study logs head errors across all 48 DeltaNet layers. The deep study's
per-head failures remain failures; a pass on a different next-token metric does not overturn them.
The whole-forward study still finds head outliers, especially on repetition. [E5, E14]

### Recorded served replies

On 10 short abliterated replies, float64, XS18 and XS20 each match the reconstructed served token
at 287/291 reply positions; XS18 and XS20 match float64 at all 291/291. The four shared misses
are not causally attributed to serving precision. The route returned text and counts, not token ids;
a different same-count tokenisation earlier in a prefix remains possible. This is teacher-forced
comparison on recorded replies, not a free-running integer CPU generation or proof. [E6]

### Integer MLP and norm classes

The paragraph below is historical: the later integer-MLP token-agreement **FAIL** is summarised
in [Merged after the pin](#merged-after-the-pin-not-incorporated-above), not incorporated here.

The integer-MLP run completed layers 0 through 29 before its cutoff; layer 30 is descriptive
post-cutoff evidence. Within the cutoff, the MLP input exceeds the design's class of 2,047 in every
layer measured, with maximum 142,651. Six SiLU inputs leave the v1 domain; the numerical run
saturated them, whereas the v1 proof rule would reject them. No logits were reached. The later
state regeneration reproduces 374/374 rows through layer 30, excluding named timing fields, but
adds no token result and does not move the original cutoff. [E7]

The norm-class study measured both pre-norms on 52 layers and arms on 27 layers, with six prompts
and 672 tokens, open loop from the float64 stream. Both pre-norms exceed 2,047 in every measured
baseline layer. Clamp arm C has 0/27 layers meeting its fidelity bar; widened arm W has 12/27 and
2,108 out-of-class entries. The smaller-scale arm's selection rule needs the missing full baseline.
The run stopped on its registered disk floor and has **no registered arm verdict**, not an all-layer
FAIL or PASS. Every arm already has failing layers among those completed; the source explains
that no completion of this run could have given any arm a PASS, while an S scale below the measured
ladder remains unmeasured. Its measured failures do not choose a new norm format, and it computed
no logits. [E8]

### Decay and checkpoint separation

Decay round 2 evaluates 23,040 (layer, head, prompt) cells per arm on the abliterated checkpoint.
U1/U2/U3 fail, while U4's per-head direct table passes the registered decay-error bar. That is
emulation on recorded inputs, with domains chosen from those same prompts and float64-generated
U4 rows. U4 would require 28,311,552 weight-dependent rows, counted not built, plus a committed-table
lookup, a tie to the learned parameter and an integer row generator. No proof, table-format/digest
change or end-to-end token test of U4 is established. [E9]

Separately, the **U1 use-case margin** study is about stock-vs-abliterated outputs, not the decay
arm named U1. On the full 10-prompt set, its pooled shares with D > 10 E and D > 100 E are 0.676
and 0.439; all three registered criteria fail. Here D is stock-vs-abliterated float64 KL distance,
and E is head-only lowering error. This does not establish a verifier acceptance radius, a working
detector or that detection is impossible. [E10]

## Admission is not a dense proof

For dense parameter files (`NE 0`), verifier planning now requires all 32 table-digest lines: eight
sigmoid words must be zero, and the other 24 must match the verifier's SiLU, rotary and softmax
tables. The passing dense planning case still exits as a plan, not `YES`. No dense proof was made
or checked in that result. The producer's parameter reader still refuses digest lines without
experts; this mismatch is source-read evidence, not a measured producer run. [E11]

The merged `dq != d` note finds the audited verifier sizes already use the appropriate widths,
but calls for an explicit query-width bound and admission changes on both verifier and prover.
It changes no code. The equality gate, `dh = 256` no-wrap barrier and partial-rotary barrier remain
explicit dependencies; dense table admission does not resolve them or Qwen's other operators. [E11]

## Cost: three different kinds of evidence

- **Measured CPU component cost.** The separate-process four-token head profile (n = 10) reports
  median prove 13.4016 s (13.2702 to 13.6726), independent verification 3.2605 s (3.1442 to 3.3857),
  and end-to-end verified latency 16.9118 s (16.7979 to 17.3505). All inputs are public: a model
  commitment phase is not applicable, not free. This is one synthetic head, not model throughput.
  H4-r2's 16-token head reports median prove 88.453 s (86.344 to 94.687, n = 10), with shared-core
  timing caveats. [E15, E4]
- **Measured route-level plain inference.** The baseline fits 0.0931 s per reported generated token
  over 40 timed decode requests, and 0.000178 s per reported prompt token over 50 prefill requests.
  These are client wall times including transport and serving layers, not GPU timings or proof
  overhead. The prefill fit is sensitive to its range and should not be extrapolated to long
  contexts; reasoning-token accounting is not established from text and usage counts alone. [E16]
- **Conditional proving cost.** The desk model's selected variable-cost scenarios span $0.0255 to
  $10.0982 per 1,000 window tokens, not bounds on actual Qwen cost. They omit fixed costs and
  assume an unbuilt DeltaNet GPU sub-proof and borrowed rates. The later route comparison's
  approximately 240x prefill / 0.46x decode central ratios are conditional, with GPU-seconds in the
  numerator and shared-route wall seconds in the denominator, not measured proving overhead. [E17, E16]

**Full-model fit on one 141 GB GPU is still unknown.** The cost model changes its fitting window
with the assumed rate and planned versus built volume; its segment count is also over the verifier
cap. The dense GPU calibration directory at this pin contains registration, planner and CPU/image
preparation receipts, but no `RESULTS.md`. The preparation README labels it “prepared, not run”.
A completed GPU calibration is therefore **NOT ESTABLISHED by this snapshot**. No availability
promise or live-route action follows from this page. [E1, E17, E18]

M3's CPU trace-size counts are also not a build: its lookup-based 16-token head excludes the
separate committed weight table, that table's range proof and the matrix-product rounds. Its MLP
count fits at most 15 tokens. Do not turn those trace counts into a whole-proof memory claim. [E12]

## The endpoint remains a choice, not a result

M3 DESIGN section 10 keeps two distinct targets. This page selects neither: [E12]

- **Integer-served, exact match:** generate the reply with the committed integer model and prove
  that each reply token is its top choice. This alone says nothing about the float model.
- **Float-served, clipped gap:** take a reply from the float engine and prove that its tokens score
  within fitted limits under the integer model. The meaning depends on fidelity between the models.

The design's smallest full target covers all 64 layers, committed abliterated weights, a short prompt
and reply in a 64-token window, and a manifest naming the commitment ID. It requires per-tensor
identity: stock and abliterated differ in 70 of 1,199 tensors, in layers 17 through 51; early-layer
proofs alone cannot distinguish them. The design does not supply a Qwen Lean soundness theorem.
These remain target and coverage statements, not an achieved abliterated proof. [E12]

## Source disagreements and historical limits

Do not silently make older source text agree with newer results:

- M3 DESIGN sections 10 and 11 say fidelity/ranges beyond layer 0 are unmeasured. The later
  deep-fidelity, whole-forward and norm-class results contain deeper-layer measurements. Keep the
  design as a historical design; use the later results only for their measured arithmetic and scope.
  They do not establish a fully integer proof. [E12, E14, E5, E8]
- M3 RESULTS' “Proposed claims” says the no-lookup head fits only at T = 1; its H3 section and
  DESIGN 7.2 also describe an unregistered two-level selector count fitting through T = 9. That
  blanket T = 1 wording is not a safe general summary. Both are counts, not builds; neither is
  promoted here into a new verdict. [E12]
- The cost-model RESULTS says no plain Qwen rate is on main. The later plain-inference RESULTS
  supplies a route-level baseline and conditional ratios, not the missing GPU-level calibration.
  The original cost model is not rewritten or recalibrated here. [E17, E16]
- The lookup RESULTS preserves H4's incomplete-suite account alongside the explicit H4-r2
  follow-up. Read the two registrations separately: the later PASS never changes the original
  NOT PASSED. [E4]

## Glossary

- **Measured:** recorded execution within the stated scope, not an extrapolation to the full model.
- **Counted / extrapolated:** a layout count / a count combined with an assumed or borrowed rate.
- **Teacher forcing:** compare next-token choices under the recorded prefix, rather than let each
  path generate its own continuation. [E5, E6]
- **Committed:** bound to a commitment checked by the verifier; a numerical emulation is not by
  itself a committed proof. [E12]
- **Research security:** test parameters, not a production soundness target. [E4]
