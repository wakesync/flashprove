# RESULTS: 20261109-32-qwen-m3-design

Issue: #32. PREREG: c9dc2c05, the first commit on the branch. Design: [DESIGN.md](DESIGN.md).
Code: `research/operators/qwen_m3/` (README there has the commands). Raw outputs: `runs/`.

**No proof was built and nothing was measured in this lane.** Every number below is one of:
- **counted**: a deterministic output of the count model or of the upstream planner (n = 1, no spread);
- **extrapolated**: a count times a rate from another model's runs, with the assumption named.

Counted and extrapolated numbers are in separate tables. Unreplicated, one host.

## Verdicts against the registered thresholds

| | hypothesis | verdict |
|---|---|---|
| H1 | the model reproduces measured M1 and M1b | **PASS**, 10 of 10 quantities exact |
| H2 | M3 with its additions off equals the #66 M2 head | **PASS**, 5 of 5 exact |
| H3 | M3a-head at T = 16 fits a 2^22 table (arm B) | **PASS**: 2^21, 2,505,232 relations |
| H4 | the upstream planner accepts a dense proxy and is linear in f | **PASS**: error 0.0044% (threshold 1%) |
| H5 | the full text model fits one H200 in at least one named lowering | **PASS by the registered rule, with a disclosed post-hoc change, and only on paper.** See H5. The registered expectation held: it does not fit in the only DeltaNet lowering that exists |

Read H5 before quoting it. The short honest form: **nothing that has been built fits. A design that
has not been built fits on extrapolated numbers. And the arithmetic it was counted for (F = 12) is
known not to track the real model.**

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

| statement | arm | T | gate columns | range cells | lookup keys | relations | laid columns | table | fits 2^22 |
|---|---|---|---|---|---|---|---|---|---|
| **M3a-head** | B | 16 | 1,111,890 | 296,112 | 326,432 | 2,505,232 | 1,750,866 | 2^21 | **yes** |
| M3a-head | A (bits, one-hot tables) | 16 | 38,598,834 | 296,112 | 0 | 77,528,560 | 38,910,130 | 2^26 | no |
| M3a-head | A | 1 | 2,413,989 | 19,587 | 0 | 4,860,895 | 2,446,757 | 2^22 | yes |
| M3a-MLP | B | 16 | 835,584 | 557,056 | 1,835,008 | 1,114,112 | 3,227,648 | 2^22 | yes |
| one layer as one statement | B | 16 | 54,206,304 | 14,770,432 | 17,503,744 | 121,365,248 | 86,499,168 | 2^27 | no |
| one layer as one statement | B | 1 | 3,462,864 | 974,992 | 1,093,984 | 8,322,608 | 5,543,632 | 2^23 | no |

- Largest T that fits: M3a-head 38 (arm B), 1 (arm A); M3a-MLP 20 (arm B), none (arm A).
- M3 adds 137,010 laid columns to the M2 head, 8%.
- A full layer in M3a is 48 head statements and one MLP statement: 87.3M product columns and 121M
  relations in total. At #66's interpolated 39 s per 2^21 statement that is on the order of half an
  hour of single-core proving per 16 tokens. **That time is an estimate from an interpolation, not a
  measurement.**
- Term counts are in `runs/model.json` as `terms_PROVISIONAL` and are used for nothing.
- The M3 additions (conv, lookups, q/k norm, gates, two-floor gated norm) have no builder to check
  them against. They are design counts.

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

26,895,323,648 integers, 56.3 GB as 16-bit weights with a 32-bit embedding. That is 6.7% of the
Maverick shape and fits in H200 memory whole.

### H5.2 Committed values per request (counted)

Per window token, all 64 layers and the output head:

| lowering | DeltaNet state | entries per token | of which DeltaNet mixer | built? |
|---|---|---|---|---|
| wide product oracle (M1, M1b, M2 design) | every token | 249,758,496 product columns = 749M field elements | all | the head only, on CPU |
| packed byte limbs | every token | 95,057,841 | 88% | **no** |
| packed, remainder not committed (a lookup key) | every token | 63,107,880 | 82% | no |
| packed, low-rank inside chunks of 64 | chunk boundaries | 16,493,386 | 31% | no; changes the integer model |
| packed, low-rank inside chunks of 16 | chunk boundaries | 20,190,721 | 44% | no |
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
Prove time is per window: central / high / upper bound.

| case | window | committed entries | largest segment | VRAM, GB | prove, s | proof | registered rule |
|---|---|---|---|---|---|---|---|
| wide oracle, per-token state | 1,024 | 7.7e11 elements | all of it | 6,138 raw, before encoding | not estimated | not estimated | **does not fit** |
| packed, per-token state, DeltaNet inside the 4-layer link (**first run**) | 1,024 | 9.66e10 | 6.00e9 | 96 / 138 / 276 | 43 / 88 / 2,600 | 172 MB | **does not fit** (138 > 127) |
| packed, per-token state, one DeltaNet segment per block (post hoc) | 1,024 | 9.73e10 | 5.36e9 | 86 / 123 / 246 | 44 / 88 / 2,620 | 173 MB | fits on the central assumption, not robust |
| packed, per-token state, one DeltaNet segment per layer (post hoc) | 1,024 | 9.73e10 | 1.79e9 | 29 / 41 / 82 | 44 / 88 / 2,620 | 173 MB | fits, also on the high estimate |
| same | 256 | 2.43e10 | 4.47e8 | 7 / 10 / 21 | 14 / 25 / 655 | 43 MB | fits |
| same | 64 | 6.08e9 | 1.12e8 | 2 / 3 / 5 | 6 / 9 / 164 | 11 MB | fits |
| packed, low-rank, chunk 64 | 1,024 | 1.69e10 | 6.29e8 (the dense layer link) | 10 / 14 / 29 | 11 / 18 / 455 | 30 MB | fits, also on the high estimate |
| same | 256 | 4.22e9 | 1.57e8 | 3 / 4 / 7 | 5 / 7 / 114 | 8 MB | fits |
| same | 64 | 1.06e9 | 3.93e7 | 1 / 1 / 2 | 4 / 5 / 28 | 2 MB | fits |

Per window token at T = 1,024 (extrapolated): per-token state 0.042 GPU-seconds central (0.086
high, 2.6 upper bound); low-rank 0.010 (0.018, 0.44). At an **assumed** 3 USD per GPU-hour the
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
   "upper bound" uses this fork's own measured small example (2.35 s for 87M entries), which is
   mostly start-up. The three differ by a factor of 60. The forward pass itself has 1.59 times
   Maverick's multiply-adds per token and is not modelled separately.
3. *VRAM* = 22.97 bytes per entry of the largest segment, from one upstream point (80,629 MiB with
   six requests in a pass). Low is 16 bytes, high is twice central. **This fork's only own reading
   of GPU memory while proving** (5,293 MiB on the small example) would give 220 bytes per entry,
   ten times central. Upstream's full-size point contradicts that for the dense family (it would
   mean 809 GB where 85 GB was reported), so it is read as fixed cost. But the fork cannot confirm
   that itself, and at 220 bytes the per-layer case needs 393 GB at T = 1,024 and 98 GB at T = 256.
   Recorded in `runs/model.json`, `vram_calibration_descriptive`; not registered, not used for a
   verdict.
4. *H200 speed = H100 speed.* Not measured.
5. *Small windows scale linearly in T.* The planner pads lookups to minimum sizes, so the T = 64
   rows are on the low side.
6. *Qwen's attention layers cost what a quarter of a Maverick attention link costs.* Head dimension
   256, partial rotary and the q/k norm are not admitted by the planner and are not modelled.
7. *F = 12 and the M2 norm lowering.* Known not to be final (below).

### H5.4 The plain answer

- **Does a full abliterated 27B proof fit one H200?** Not with anything that exists. The only
  DeltaNet lowering that has been built needs about 6,100 GB for one 1,024-token window, before
  encoding, about 44 times the card. With a DeltaNet sub-proof for the GPU prover, which has not been written, the
  extrapolation says yes for windows up to 1,024 tokens, comfortably if the state is committed only
  at chunk boundaries, and with little margin if every state is committed and the segments are
  large. That "yes" has never been tested and rests on another model's rates.
- **Binding constraint:** the DeltaNet state trace. It is 88% of everything a request commits when
  every state is committed, and it decides GPU memory. The weights are not the constraint: they are
  6.7% of Maverick's and would fit in memory whole. With chunk-boundary state the largest segment
  becomes the dense layer link and the DeltaNet part stops binding.
- **Cost per token:** 0.01 to 0.04 GPU-seconds per window token on the central extrapolation, up
  to 2.6 on the upper bound. Read it as "somewhere between a tenth of a second and a few seconds
  per reply token for short replies", not as a price.
- **Smallest end-to-end milestone that proves a real abliterated reply:** all 64 layers, the
  abliterated weights committed with a per-tensor manifest, one 64-token window, reply generated by
  the integer model and proved under exact match (DESIGN.md section 10). Extrapolated, with every state
  committed and one DeltaNet segment per layer: 6 s (central) to 164 s (upper bound) of proving, and
  2 to 5 GB of GPU memory on the registered range, 25 GB at this fork's own small-example rate. A block of layers 0 to 3 cannot stand in for it:
  those layers are identical in the stock and the abliterated checkpoint.

### H5.5 What the open norm scaling does to these numbers (counted; requested during the lane)

The real-weights lane (PR #68, draft, unreviewed) found that at F = 12 the ranges hold on layer 0
but the head output misses its fidelity threshold at F = 12, 14 and 16. So F = 12 with the M2 norm
is a candidate, not the final arithmetic.

| if the fix is | M3a-head, T = 16 (harness) | full model, per token (packed) |
|---|---|---|
| none | 1,750,866 columns, 2^21, largest T 38 | 95.1M per-token; 16.5M low-rank |
| o, t, y carry 4 to 8 more bits | 1,767,250 (+0.9%), 2^21, largest T 38 | unchanged on layer-0 maxima; +0.4% / +2.3% if a fourth limb is needed |
| the recurrence is widened too | 2,570,066 (+47%), 2^22, largest T 26 | 111.2M (+17%) per-token; 16.9M (+2.3%) low-rank |

No verdict above changes in any row. The last row is a lower bound, not a design.

## Deviations from the PREREG

1. **H5 segmentation changed after seeing the first result.** The first run (`runs/model-first-run.json`)
   put the DeltaNet mixer inside upstream's 4-layer layer link. Its verdict for per-token state at
   T = 1,024 was "does not fit" (138 GB central against 127). After seeing that, the DeltaNet
   sub-proof was made a segment of its own, per block or per layer, and those cases fit. Separate
   segments are a natural design (attention already has its own), but the choice was made with the
   result in view, so both are in the table and the first-run verdict stands as reported. H5 passed
   in the first run as well, through the low-rank case.
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
9. No amendment was made to PREREG.md.

Brief item 6 (two wording fixes left over from the #66 reviews) is **not done**: #66 is not on main,
and another lane is changing the same files on that branch.

## Open risks

See DESIGN.md section 11. The ones that bear on these numbers:
- No GPU DeltaNet sub-proof exists. Every "fits" row is about a design.
- The rates are another model's, unreproduced here. The VRAM constant rests on one point.
- F = 12 with the M2 norm does not meet fidelity on real layer-0 weights (PR #68, draft). Ranges
  were measured on layer 0 only, with the memory read at 77% of its bound.
- The M3 additions to the count model are unreviewed and have no builder.
- Lookups are a precondition for M3a, and function-table lookups are in no lane's scope yet.

## Proposed claims (PR body only, not in claims.json)

- Counted, not built: the first Qwen statement with committed weights (one V head, in_proj to
  out_proj, T = 16) fits the CPU research harness at the M2 head's table size, 2^21, if remainders
  and tables are lookups; without lookups it fits only at T = 1.
- Counted: the upstream planner accepts a dense 64-layer proxy of Qwen's dense family and plans
  13.3 billion committed entries per 1,024-token request.
- No claim about fitting one H200 should be made publicly from this lane. It is an extrapolation
  about an unbuilt sub-proof.

## Kill criterion

Not triggered. Lane start 00:08Z, counts complete 01:33Z, no prototype run, free disk above 40 GB.
