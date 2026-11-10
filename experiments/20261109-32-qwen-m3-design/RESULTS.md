# RESULTS: 20261109-32-qwen-m3-design

Issue: #32. PREREG: c9dc2c05, the first commit on the branch. Design: [DESIGN.md](DESIGN.md).
Code: `research/operators/qwen_m3/` (README there has the commands). Raw outputs: `runs/`.

**No proof was built and nothing was measured in this lane.** Every number below is one of:
- **counted**: a deterministic output of the count model or of the upstream planner (n = 1, no spread);
- **extrapolated**: a count times a rate from another model's runs, with the assumption named.

Counted and extrapolated numbers are in separate tables. Unreplicated, one host.

**r2 (2026-11-10), after two independent reviews of PR #70** (astra:
https://github.com/wakesync/flashprove/pull/70#issuecomment-6757513561, opus:
https://github.com/wakesync/flashprove/pull/70#issuecomment-6758415494). The counts were rerun with
the corrected count model and bound ledger into **new files** `runs/model-r2.json` and
`runs/bounds-r2.json`. `runs/model.json`, `runs/bounds.json` and `runs/model-first-run.json` are
the earlier runs and are unchanged. Tables below give r2 numbers, with r1 in brackets where they
differ. The section "r2: changed numbers" lists each one with its reason. The planner was not
rerun: the count model reads its committed output, and nothing in it changed.

## Verdicts against the registered thresholds

| | hypothesis | verdict |
|---|---|---|
| H1 | the model reproduces measured M1 and M1b | **PASS**, 10 of 10 quantities exact |
| H2 | M3 with its additions off equals the #66 M2 head | **PASS**, 5 of 5 exact |
| H3 | M3a-head at T = 16 fits a 2^22 table (arm B) | **PASS**: 2^21, 2,525,004 relations [r1: 2,505,232]; same verdict in r1 and r2 |
| H4 | the upstream planner accepts a dense proxy and is linear in f | **PASS**: error 0.0044% (threshold 1%) |
| H5 | the full text model fits one H200 in at least one named lowering | **First run, as registered: PASS, through the low-rank case only**; the per-token case with the DeltaNet mixer inside the 4-layer link did **not fit** (138 GB central against 127 GB). The later per-block and per-layer segments are post hoc and exploratory. **r2 reading: the low-rank case is not established (H5.6), so the registered PASS rests on a construction that is not specified or proved; whether the model fits one H200 is unknown.** The registered expectation held: it does not fit in the only DeltaNet lowering that exists |

Read H5 before quoting it. The short honest form: **nothing that has been built fits. Whether a
DeltaNet sub-proof that has not been written would fit one H200 is unknown: at the registered
rate some cases are under the limit, at this fork's own measured rate no case fits a 1,024-token
window. And the arithmetic it was counted for (F = 12, M2 lowering) FAILED the fidelity threshold
on layer 0 (PR #68: 10 prompts, F = 12, 14, 16); deeper layers are unmeasured.**

## H1: the count model against measured statements (counted vs measured)

| quantity | model | measured (#47, #63) |
|---|---|---|
| M1 columns, log-length, relations, terms | 2,338,816; 22; 4,761,088; 11,430,400 | the same |
| M1b laid columns, non-region columns, log-length | 1,310,720; 1,074,176; 21 | the same |
| M1b relations, terms, range cells | 2,231,808; 5,174,272; 67,072 | the same |

This guards against drift only. The recurrence emission is imported from #66's `count_model.py`,
so it is not an independent derivation.

## H2: M3 reduces to the M2 head (counted)

Arm B, T = 16, additions off: 1,056,800 gate columns, 272,384 range cells, 276,688 lookup keys,
2,402,432 relations, log-length 21. These are the #66 counts that its second reviewer reproduced
with independent closed forms.

## H3: M3a on the research harness (counted)

r2 (`runs/model-r2.json`); r1 in `runs/model.json`.

| statement | arm | T | gate columns | range cells | lookup keys | relations | laid columns | table | fits 2^22 |
|---|---|---|---|---|---|---|---|---|---|
| **M3a-head** | B | 16 | 1,111,897 | 296,112 | 358,118 | 2,525,004 | 1,783,641 | 2^21 | **yes** |
| M3a-head | A (bits, one-hot tables, sums split at 256 terms) | 16 | 39,163,811 | 296,112 | 0 | 78,239,934 | 39,475,107 | 2^26 | no |
| M3a-head | A | 1 | 2,469,611 | 19,587 | 0 | 4,947,534 | 2,502,379 | 2^22 | yes |
| M3a-MLP | B | 16 | 835,584 | 835,584 | 2,752,512 | 2,031,616 | 4,423,680 | 2^23 | **no** [r1: yes, 2^22] |
| one layer as one statement | B | 16 | 54,206,640 | 15,048,960 | 19,942,176 | 123,231,808 | 89,219,248 | 2^27 | no |
| one layer as one statement | B | 1 | 3,463,200 | 992,400 | 1,471,296 | 8,589,568 | 5,937,184 | 2^23 | no |

- Largest T that fits: M3a-head 37 (arm B) [r1: 38], 1 (arm A); M3a-MLP 15 (arm B) [r1: 20], none
  (arm A).
- M3 adds 169,785 laid columns to the M2 head, 11% [r1: 137,010, 8%].
- Every relation has at most 256 terms (the harness's cap), checked by the model
  (`max_terms_per_relation`). r1's arm A emitted 4,097-term relations, which the harness refuses.
- **M3a-MLP no longer fits at T = 16.** r1's lowering fed the unrounded s x u into the down
  projection, which can wrap the field against a cheating prover (`runs/bounds-r2.json`, control
  row). r2 rounds it to h with an exact remainder. M3a-MLP then needs T <= 15 or a split.
- A full layer in M3a is 48 head statements and one MLP statement: 90.0M product columns and 123M
  relations in total [r1: 87.3M, 121M]. At #66's interpolated 39 s per 2^21 statement that is on the order of half an
  hour of single-core proving per 16 tokens. **That time is an estimate from an interpolation, not a
  measurement.**
- Term counts are in `runs/model.json` as `terms_PROVISIONAL` and are used for nothing.
- The M3 additions (conv, lookups, q/k norm, gates, two-floor gated norm) have no builder to check
  them against. They are design counts.

**What these counts leave out.** "Fits 2^21" is about the trace table only, the product oracle that
holds the request's cells. Not counted, and found on self-review after the counts were made:
- the head's 3,288,706 committed weights [r1: 3,288,578, without the 128 gains]. They sit in a
  table of their own, with its own range proof and its own opening. No Qwen layout of that range
  proof (WF) exists; it exists for upstream's Maverick layout only. That table, and the composition
  of a weight table with this harness, has never been built here. It is M3a's main risk and none of
  its cost is in the table above (the trace side of the weight-cell tie, DESIGN 6.2, is);
- the two matmuls' own rounds: in_proj is 514 claims per token on the weight table (8,224 at
  T = 16) and out_proj 5,120 per token (81,920), each batched into one. The model counts their
  output cells and remainders and no relation for them;
- the multiplicity planes of the function-table lookups (about 14 planes of 4,096 places per table;
  small against the 2^21 row, and not sized by the layout routine).
The first of these is the reason the M3a prove time is not estimated from the table size alone.

Not registered, counted after the fact: arm A with a two-level 64 x 64 selector fits up to T = 9
(2^23 at T = 16).

## H4: the upstream planner as an anchor for the dense family (counted)

`cp_verify -plan arrays` on proxy configurations made from `prover/examples/target_full_f2`:

| proxy | links | entries per 1,024-token request | layer link | attention link | head link |
|---|---|---|---|---|---|
| Maverick (stored configuration) | 25 | 10,573,982,429 | 604,696,530 | 231,801,624 | 527,265,781 |
| dense, f 8,192 | 25 | 8,862,579,713 | 462,079,637 | 231,801,624 | 527,265,781 |
| dense, f 16,384 | 25 | 9,936,288,713 | 551,555,387 | 231,801,624 | 527,265,781 |
| dense, f 17,408 | 25 | 10,070,797,313 | 562,764,437 | 231,801,624 | 527,265,781 |
| dense, f 17,408, V 248,320 | 25 | 10,165,530,241 | 562,764,437 | 231,801,624 | 621,998,709 |
| **dense, f 17,408, V 248,320, L 64** | 33 | **13,343,794,485** | 562,764,437 | 231,801,624 | 621,998,709 |

Linearity in f: predicted 562,739,856 at f = 17,408 from the two other points, planner 562,764,437.

The first attempt was refused (`NO: policy-gcl`): a file with `NE 0` must also drop the clamp
lines, the digest lines, the expert weight kinds and the router's lookup segments. The second
attempt follows the repository's own recipe (`verifier/tests/served_form_test.py`, `no_experts()`).
The refused attempt is kept in `runs/planner-proxy-attempt1-refused.json`.

A proxy is not a Qwen configuration. It has Maverick's attention (40 heads of 128) and no DeltaNet.

## H5: the full text model on one H200

### H5.1 Committed weights (counted from the published shapes)

26,895,337,984 integers [r1: 26,895,323,648; r2 adds the 14,336 retained norm gains], 56.3 GB as
16-bit weights with a 32-bit embedding. That is 6.7% of the Maverick shape and is smaller than one
H200's memory.

### H5.2 Committed values per request (counted)

Per window token, all 64 layers and the output head:

| lowering | DeltaNet state | entries per token | of which DeltaNet mixer | built? |
|---|---|---|---|---|
| wide product oracle (M1, M1b, M2 design) | every token | 254,322,288 product columns = 763M field elements [r1: 249,758,496] | all | the head only, on CPU |
| packed byte limbs (**plan of record**: full state handed on at chunk boundaries) | every token | 95,057,841 | 88% | **no** |
| packed, remainder not committed (a lookup key) | every token | 63,107,880 | 82% | no |
| packed, low-rank inside chunks of 64: **NOT ESTABLISHED** (H5.6) | chunk boundaries | (16,493,386) | (31%) | no; no specified or proved construction |
| packed, low-rank inside chunks of 16: **NOT ESTABLISHED** | chunk boundaries | (20,190,721) | (44%) | no |
| dense family only (planner, proxy) | none | 13,031,049 | 0 | upstream, for Maverick's shape |

How the packed DeltaNet count is made: byte limbs per V head per token (state 3 limbs and its floor
remainder 2 limbs for each of 16,384 cells, then 3,328 limbs of vectors, 597 for the shared q/k
path, 16 scalars: 85,861 in all), three limbs to a committed entry, times 1.27 for the sumcheck and
lookup arrays that come with committed cells (that factor is the planner's ratio for a Maverick
layer link). The dense part of a layer is the planner's count, plus 1.84 entries per extra
projection output for Qwen's wider in_proj (a slope from one more planner call).

### H5.3 Does it fit: extrapolated

Every number in this table is **extrapolated, not measured**. Assumptions follow the table.
VRAM is for the largest segment at one request per pass with weights streamed: low / central / high.
Prove time is per window: central / high / small-example rate. "High" and the small-example
column (r1 called it "upper bound") are **labels of a registered range, not proved upper bounds**.
The packed rows are unchanged in r2 (the packed count did not change); the wide-oracle volume is
r2's. The column "own rate" (r2) is the same largest segment at this fork's own measured
220 bytes per entry; it is equally an extrapolation, from a small synthetic example of another
model.

| case | window | committed entries | largest segment | VRAM, GB | own rate, GB | prove, s | proof | registered rule |
|---|---|---|---|---|---|---|---|---|
| wide oracle, per-token state | 1,024 | 7.8e11 elements | not segmented here | 6,250 raw [r1: 6,138]: **aggregate trace volume over all layers and the window, not peak memory** | | not estimated | not estimated | does not fit as one segment; not compared with a card |
| packed, per-token state, DeltaNet inside the 4-layer link (**first run, registered**) | 1,024 | 9.66e10 | 6.00e9 | 96 / 138 / 276 | | 43 / 88 / 2,600 | 172 MB | **does not fit** (138 > 127) |
| packed, per-token state, one DeltaNet segment per block (**post hoc, exploratory**) | 1,024 | 9.73e10 | 5.36e9 | 86 / 123 / 246 | 1,178 | 44 / 88 / 2,620 | 173 MB | central under 127, high over |
| packed, per-token state, one DeltaNet segment per layer (**post hoc, exploratory**; 81 segments, over cp_verify's 64) | 1,024 | 9.73e10 | 1.79e9 | 29 / 41 / 82 | **393** | 44 / 88 / 2,620 | 173 MB | central and high under 127; own rate over |
| same | 512 | | 8.93e8 | | 196 | | | own rate over |
| same | 256 | 2.43e10 | 4.47e8 | 7 / 10 / 21 | 98 | 14 / 25 / 655 | 43 MB | under 127 at every rate shown |
| same | 64 | 6.08e9 | 1.12e8 | 2 / 3 / 5 | 25 | 6 / 9 / 164 | 11 MB | under 127 at every rate shown |
| packed, low-rank, chunk 64 (**NOT ESTABLISHED**, H5.6) | 1,024 | 1.69e10 | 6.29e8 (the dense layer link) | 10 / 14 / 29 | **138** | 11 / 18 / 455 | 30 MB | depends on an unspecified construction |
| same (not established) | 512 | | 3.14e8 | | 69 | | | |
| same (not established) | 256 | 4.22e9 | 1.57e8 | 3 / 4 / 7 | 35 | 5 / 7 / 114 | 8 MB | |
| same (not established) | 64 | 1.06e9 | 3.93e7 | 1 / 1 / 2 | 9 | 4 / 5 / 28 | 2 MB | |

The r1 table's verdict words "fits" are replaced by what the numbers say against the 127 GB rule
at each rate. None of these rows is a measurement, and no row establishes a fit (H5.4).

Per window token at T = 1,024 (extrapolated): per-token state 0.042 GPU-seconds central (0.086
high, 2.6 at the small-example rate); low-rank, not established, 0.010 (0.018, 0.44). At an **assumed** 3 USD per GPU-hour the
central figures are 0.035 and 0.009 USD per 1,000 window tokens. The window holds the prompt as
well as the reply, so the cost per reply token is the window's cost divided by the reply's length.
Committing the weights: about 2.6 minutes, extrapolated linearly from upstream's "about 39 minutes"
for Maverick, fixed costs ignored.

**Assumptions behind the extrapolation, and how much each can be trusted:**
1. *A packed DeltaNet sub-proof exists and costs what a dense-family cell costs per committed
   entry.* It does not exist. A state cell takes part in about four product gates per token; a
   dense-family cell does not. This could be off in either direction and nothing here bounds it.
2. *Prove time* = 18.16 s x 3 passes x 0.067 (weights) + 4.33 s per 10.57e9 entries. Both rates
   come from a fit to upstream's four published Maverick rates on one H100 (it predicts the two
   held-out batch sizes within 4%). Those records are not in this repository and this fork has not
   reproduced them. The "high" column charges all of upstream's 9.2 s per request to entries. The
   third column uses this fork's own measured small example (2.35 s for 87M entries), which is
   mostly start-up. The three differ by a factor of 60, and none is a proved bound. The forward pass itself has 1.59 times
   Maverick's multiply-adds per token and is not modelled separately.
3. *VRAM* = 22.97 bytes per entry of the largest segment, from one upstream point (80,629 MiB with
   six requests in a pass). Low is 16 bytes, high is twice central. **This fork's only own reading
   of GPU memory while proving** (5,293 MiB on the small example) would give 220 bytes per entry,
   ten times central. Upstream's full-size point contradicts that for the dense family (it would
   mean 809 GB where 85 GB was reported), so r1 read it as fixed cost. But the fork cannot confirm
   that itself, and a DeltaNet segment is not a dense-family segment. **r2 gives this case the same
   prominence as the central one** (the "own rate" column above): at 220 bytes per entry the
   per-layer case needs 393 GB at T = 1,024 and the low-rank form 138 GB, both over 127 GB; the
   largest windows under 127 GB are 256 tokens (per-token state) and 512 (low-rank, not
   established). Recorded in `runs/model-r2.json`, `H5_r2.own_small_example_rate`; not registered.
4. *H200 speed = H100 speed.* Not measured.
5. *Small windows scale linearly in T.* The planner pads lookups to minimum sizes, so the T = 64
   rows are on the low side.
6. *Qwen's attention layers cost what a quarter of a Maverick attention link costs.* Head dimension
   256, partial rotary and the q/k norm are not admitted by the planner and are not modelled.
7. *F = 12 and the M2 norm lowering.* Known not to be final (below).

### H5.4 The plain answer

- **Does a full abliterated 27B proof fit one H200?** **Unknown.** Nothing that exists can prove
  it, and no Qwen segment has been measured. The only DeltaNet lowering that has been built commits
  about 6,250 GB of raw trace over all layers of a 1,024-token window; that is aggregate volume, not
  the memory one card holds at once. For a DeltaNet sub-proof of the GPU prover, which has not been
  written, the answer depends on a rate nobody has measured for it. At the registered central rate
  (23 bytes per entry, from one upstream Maverick point) the per-token case with one DeltaNet
  segment per layer needs about 41 GB at T = 1,024. At this fork's own measured rate (about 220
  bytes per entry, from a small synthetic example of a different model) the same case needs about
  393 GB, and nothing fits a 1,024-token window; the largest window that fits is then 256 tokens.
  Both are extrapolations. The per-layer cut also needs 81 segments, and `cp_verify` refuses more
  than 64 today. The low-rank form is not established and is not the plan.
- **Registered verdicts:** the first run's per-token case (DeltaNet inside the 4-layer link) did
  not fit, 138 GB against 127 GB. The first run's H5 passed only through the low-rank case, which
  r2 marks as not established. The per-block and per-layer cuts were chosen after the first run
  was seen and are exploratory.
- **Binding constraint:** the DeltaNet state trace. It is 88% of everything a request commits when
  every state is committed, and it decides GPU memory. The weights are not the constraint: they are
  6.7% of Maverick's and smaller than one card's memory.
- **Cost per token:** about 0.04 GPU-seconds per window token on the central extrapolation for
  per-token state (0.01 for the low-rank form, not established), 2.6 at the small-example rate.
  Neither end is a bound. Read it as "somewhere between a tenth of a second and a few seconds per
  reply token for short replies", not as a price.
- **Smallest end-to-end milestone that proves a real abliterated reply:** all 64 layers, the
  abliterated weights committed with a per-tensor manifest, one 64-token window, reply generated by
  the integer model and proved under exact match (DESIGN.md section 10). Extrapolated, with every state
  committed and one DeltaNet segment per layer: 6 s (central) to 164 s (small-example rate) of
  proving, and 2 to 5 GB of GPU memory on the registered range, 25 GB at this fork's own
  small-example rate. A block of layers 0 to 3 cannot stand in for it:
  those layers are identical in the stock and the abliterated checkpoint.

### H5.5 What the open norm scaling does to these numbers (counted; requested during the lane)

PR #68 (merged) measured layer 0 only, 10 prompts, F = 12, 14 and 16 with the M2 lowering: at
F = 12 the ranges hold, and the integer head output FAILED its fidelity threshold at all three F.
So F = 12 with the M2 lowering is a candidate, not the final arithmetic; F and the lowering are
open parameters.

| if the fix is | M3a-head, T = 16 (harness, r2) | full model, per token (packed) |
|---|---|---|
| none | 1,783,641 columns, 2^21, largest T 37 [r1: 1,750,866, 38] | 95.1M per-token |
| o, t, y carry 4 to 8 more bits | 1,800,025 (+0.9%), 2^21, largest T 37 [r1: 1,767,250, 38] | unchanged on layer-0 maxima; +0.4% if a fourth limb is needed |
| the recurrence is widened too | 2,586,457 (+45%), 2^22, largest T 25 [r1: 2,570,066, +47%, 26] | 111.2M (+17%) per-token |

The M3a-head verdict does not change in any row. The last row is a lower bound, not a design.
Low-rank figures are omitted: not established.

### H5.6 The low-rank form is not established (r2)

The independent review of PR #71
(https://github.com/wakesync/flashprove/pull/71#issuecomment-6758363867) found that the chunked
low-rank state form is costed with remainder widths that are too narrow, that edge inputs inside
its range contract give 65 to 67 bit intermediates, and that its only passing variant is
unregistered and has no proof. This lane's low-rank count also omits a second QK Gram, the staged G
table, the P0/Q0 outputs and the M/o remainders. So every low-rank figure in this file (10 / 14 /
29 GB, 5.15M mixer entries, 16.5M per token) depends on a construction that is not specified or
proved. It is kept in the tables as r1 counted it, labelled, and it is not the plan. **The plan of
record is the boundary handoff with the full per-token cost** (the per-token rows).

## Deviations from the PREREG

1. **H5 segmentation changed after seeing the first result.** The first run (`runs/model-first-run.json`)
   put the DeltaNet mixer inside upstream's 4-layer layer link. Its verdict for per-token state at
   T = 1,024 was "does not fit" (138 GB central against 127). After seeing that, the DeltaNet
   sub-proof was made a segment of its own, per block or per layer, and those cases fit. Separate
   segments are a natural design (attention already has its own), but the choice was made with the
   result in view, so both are in the table and the first-run verdict stands as reported. H5 passed
   in the first run as well, through the low-rank case (which r2 marks as not established, H5.6).
   Recorded retrospectively in PREREG.md amendment A1 (2026-11-10).
2. The first run also had a "2-layer links" case (89 GB central). It is dropped: upstream allows at
   most 28 blocks of layers and 64 layers in blocks of 2 is 32.
3. **Gated norm changed after the first run**, in response to the second review of #66: the derived
   coefficient cg was replaced by a table cell, two floors and a committed gain. M3a-head moved from
   1,732,306 laid columns and 2,499,088 relations to 1,750,866 and 2,505,232. The H3 verdict is the
   same in both.
4. The packed DeltaNet count was registered as "2 cells per state cell per token". It is counted in
   byte limbs: 3 for the state and 2 for the remainder, so 5 limbs or 1.67 committed entries before
   overhead.
5. Not registered, added during the lane: the wider-in_proj slope (one more planner call), the
   in_proj outputs moved from the DeltaNet count to the dense part, the two-level fallback count,
   `bounds.py`, the sensitivity table (H5.5) and the descriptive VRAM calibration.
6. The first planner calls used a `cp_verify` binary built earlier from the same sources in another
   checkout. All calls were rerun with a binary built from this branch; the outputs are identical.
   Only the rerun is in `runs/`.
7. H4 needed two attempts (see H4). Within the registered 20 minutes.
8. Verify time was not modelled. With 49 to 81 segments and a proof of 30 to 173 MB against
   Maverick's 25 segments and 18.78 MB, expect minutes on one thread. That is a guess.
9. r1 made no amendment to PREREG.md. r2 adds dated retrospective amendments A1 to A4 for what
   changed after the first run (segmentation, gated norm, the r2 corrections, exploratory
   additions). Registered questions, thresholds and first-run verdicts are unchanged.
10. (r2) The count model and the bound ledger were changed after two reviews; the changes are in
    DESIGN section 12 and below. Their outputs are new files; no committed run file was changed.

Brief item 6 of r1 (two wording fixes left over from the #66 reviews) was not done in r1. #66 has
since merged at bd50893 and this branch includes it; this design was checked against #66's final
rule (step 3a, checked or 128-bit arithmetic, DESIGN 6.3).

## r2: changed numbers (old r1 value, new r2 value, reason)

All counted, deterministic, n = 1. Source: `runs/model.json` (r1) and `runs/model-r2.json` (r2);
bounds `runs/bounds.json` and `runs/bounds-r2.json`.

| quantity | r1 | r2 | reason |
|---|---|---|---|
| M3a-head weights | 3,288,578 | 3,288,706 | 128 retained gains (astra 3) |
| text model weights | 26,895,323,648 | 26,895,337,984 | 14,336 retained norm gains (48 x 128 + 16 x 512) |
| M3a-head arm B T16 gate columns | 1,111,890 | 1,111,897 | weight-cell tie split into 256-term sums (7 partial cells) |
| lookup keys | 326,432 | 358,118 | exact 2^s remainder classes (+2 keys per floor at a public shift), 36-bit q remainder, weight-cell class (3 keys x 1,666) |
| relations | 2,505,232 | 2,525,004 | the same, plus the tie |
| laid columns | 1,750,866 | 1,783,641 | the same |
| added over the M2 head (laid columns) | 137,010 | 169,785 | the same |
| largest T, arm B | 38 | 37 | the same |
| arm A T16 laid columns | 38,910,130 | 39,475,107 | 4,097-term sums split at 256 terms (astra 4), plus the above |
| arm A T1 laid columns | 2,446,757 | 2,502,379 | the same; still 2^22 |
| M3a-MLP T16 laid columns / table | 3,227,648 / 2^22 | 4,423,680 / 2^23 | r1's down projection could wrap; h rounded with an exact remainder (found in r2) |
| M3a-MLP largest T | 20 | 15 | the same |
| one layer, one statement, T16 laid columns | 86,499,168 | 89,219,248 | sum of the above |
| M3a layer as 49 statements, product columns | 87,269,216 | 90,038,448 | sum of the above |
| wide-oracle product columns per token (48 layers) | 249,758,496 | 254,322,288 | per-head change times 48 x 48 |
| wide-oracle raw volume, T = 1,024 | 6,138 GB | 6,250 GB | the same; now labelled aggregate volume, not peak memory |
| H5.5 output-path row | 1,767,250 | 1,800,025 | base moved |
| H5.5 recurrence row | 2,570,066 (+47%), largest T 26 | 2,586,457 (+45%), largest T 25 | base moved |
| commit-time extrapolation | 2.6176 min | 2.6176 min | gains, negligible |
| bounds: worst row | 2^61 (Rc sigma, log + 1) | 2^60.27 (q floor, 362 Rc x) | exact sums; q now carries 362 |
| bounds: q/k square row | 2^38 | 2^48.0007 | sigma^2 and e1 side added (astra 2) |
| bounds: k x delta | 2^53 (stated) | 2^53.000005 | low limb added |
| bounds: SiLU image | 4,095 | 32,741 | pinned table (astra 2) |
| bounds: rows | 21 + 1 control | 33 + 2 controls | full S5 to S8 of both norms, classes, keys, MLP rows; second control is r1's MLP down projection (2^64.09) |
| packed entries per token, VRAM, prove time | unchanged | unchanged | the packed count did not change |
| largest windows under 127 GB at the own rate | not stated | 256 (per-token), 512 (low-rank, not established) | made prominent (astra 5, opus M2) |
| segments per window, per-layer cut | 81 | 81 | now compared with cp_verify's cap of 64 |

## Open risks

See DESIGN.md section 11. The ones that bear on these numbers:
- No GPU DeltaNet sub-proof exists. Every row under the 127 GB rule is about a design, and fit on
  one H200 is unknown until a measured Qwen segment exists.
- The rates are another model's, unreproduced here. The VRAM constant rests on one point; the
  fork's own rate is ten times higher.
- F = 12 with the M2 lowering FAILED the fidelity threshold on layer 0 (PR #68: 10 prompts,
  F = 12, 14, 16). Ranges were measured on layer 0 only, with the memory read at 77% of its bound.
  Deeper layers and every abliterated layer (17 to 51) are unmeasured.
- The r2 changes to the count model are unreviewed and have no builder.
- Lookups are a precondition for M3a. PR #67 has standalone arm-A pieces with unbound inputs; the
  efficient lookup keyed on the statement's committed cells exists nowhere yet.
- No Qwen layout of the weight table's range proof exists; the weight-cell tie is designed and
  counted, not built.

## Proposed claims (PR body only, not in claims.json)

- Counted, not built: the first Qwen statement with committed weights (one V head, in_proj to
  out_proj, T = 16) fits the CPU research harness at the M2 head's table size, 2^21, if remainders
  and tables are lookups; without lookups it fits only at T = 1. The count is the request's trace
  table only: the separate table of the head's committed weights and the matmuls' rounds are not
  in it.
- Counted: the upstream planner accepts a dense 64-layer proxy of Qwen's dense family and plans
  13.3 billion committed entries per 1,024-token request.
- No claim about fitting one H200 should be made publicly from this lane. It is an extrapolation
  about an unbuilt sub-proof.

## Kill criterion

Not triggered. Lane start 00:08Z, counts complete 01:33Z, no prototype run, free disk above 40 GB.
