# RESULTS: 20261112-132-int-mlp-e2e (PARTIAL: not finished)

Issue #132, PR #138. PREREG `PREREG.md` (first commit c6311ec, alone; amendment A-1 6732850, format only). Code at the run: 1960ec5. Raw runs: commit 2b186b3 (which also edits `summarise_mlp.py` for partial-run reporting, see section 5). Post-review aggregate receipt: `aggregate_review.py` -> `runs/aggregate-review.json` (reads the committed raw runs only).

**Layer 30 is post-cutoff.** The registered compute hard stop was 18:25:00Z; layer 30 was saved at 18:25:14Z and the watchdog killed the job at 18:25:18Z. Layers 0 to 29 are inside the registered run. Layer 30 is kept as descriptive post-cutoff evidence and is marked so wherever it is used (section 5). Without it every finding below stands: m over class on 23,255,770 of 224,409,600 entries (10.36%), max 142,651 at layer 26 on p03; every other maximum and the 6 SiLU exits are unchanged.

**Verdict vs prereg: NOT FINISHED on the token bar (no PASS or FAIL); range verdict on the layers done: OUT-OF-BOUND.**

## Plain-language summary
- The run put the M3 design's integer MLP into every layer of the abliterated Qwen model, with the XS18 integer DeltaNet heads, and pushed the 10 frozen prompts through. Layer 29 of 63 was the last one finished before the registered stop time; layer 30 finished 14 s after it, before the watchdog's kill, and is used only as labelled post-cutoff evidence. So there are no next-token numbers yet and no answer on the token-agreement bar.
- What it does show: the MLP's input, written as an integer at 2^12 as the design says, is far bigger than the class the design gives it (2,047). From layer 27 on, about a quarter of the MLP inputs in a layer are over that class (peak 25.5% at layer 27). The largest inside the cutoff is 142,651 (layer 26); the post-cutoff layer 30 has 148,536. That happens in every layer, roughly increasing with depth (0.27% at layer 0). A statement written as specified would refuse those inputs.
- The other MLP values (gate, up, product, down-projection sum, output) stay inside their bounds. The down-projection wrap that the design's r2 fixed does not come back on real activations: the sum stays under 2^29 against a ledger bound of 2^55. Six hidden units in layers 21 to 26 leave the SiLU table's domain; the table rejects those inputs, so here they were saturated and counted.
- How far the integer model drifts from float64: after layer 29 (the last layer inside the cutoff) the residual stream differs by about 0.6% (median over prompts; 0.61%, and 0.60% after the post-cutoff layer 30). On the repeated-word prompt the drift jumps from 1% to 5.8% between layers 24 and 29, and to 8.8% at the post-cutoff layer 30. The float-heads control (FM: integer MLP, float heads) drifts by a similar amount at layer 30: its distance to float64 is 93% to 100% of XM18's on every prompt, and the largest gap is 0.20 percentage points (repeated-word prompt). At earlier layers that is not so: on the repeated-word prompt FM is about half of XM18 at layers 16 to 24 (gap up to 0.51 points at layer 19), and every layer from 0 to 25 has at least one prompt where FM is under 80% of XM18. These are distances of two arms to float64, not a split of XM18's error into a head part and an MLP part (no XS18-only arm was run here).
- No proof, no soundness claim. in_proj, out_proj, attention, every norm (including the MLP's own pre-norm) and lm_head stay float64.

## 1. Run record
- Registered run through `flock bigmem.lock` + `fp-heavy.sh` + `taskset -c 6-11`. `runs/progress.log`: first grant 16:51:58Z (so the full 10-prompt set, PREREG rule), MemAvailable 14.1 GB.
- The first process died at about 17:00:32Z, after layer 2 was saved. It was not killed by the run: a restart of the agent host's session service took its child processes down with it. It was resumed at 17:08:56Z from the per-layer checkpoint under a separate service unit, with the same command, the same code and the same first-grant time (`runs/progress.log.jsonl` has one `start` and one `resume` at `next_layer` 3; no layer was recomputed). About 9 minutes lost.
- Registered compute hard stop 18:25:00Z. Layer 30 was saved at 18:25:14Z, 14 s after the hard stop, and the watchdog killed the job by pid at 18:25:18Z (`end rc=143`): it checks the clock every 20 s, so it fired 18 s late. Layer 30 is therefore post-cutoff and is reported below only as descriptive evidence, labelled as such (section 5).
- No process-resource record exists for either process start. `runs/run.time` holds only two Python resource-tracker warnings (one per process), no `time -v` block, and every `time_v` field in ENV.json is null. A likely cause: `/usr/bin/time` is the process the watchdog and the service restart signal (`$!` in `run_mlp.sh`), so it dies before it prints. So peak RSS, user time and CPU share of the run are not recorded, and the PREREG memory rule (RSS over 14 GB: stop) cannot be audited from the committed files. Only the MemAvailable reading at each start (`runs/progress.log`: 14.1 GB and 22.2 GB) is recorded.
- Per-layer time 120.0 to 194.2 s, median 163.7 s over 31 layers (layer 25 fastest, layer 16 slowest; `runs/progress.log.jsonl`, aggregated in `runs/aggregate-review.json`), against 48 to 67 s for PR #124 and a PREREG estimate of 40 to 65 s. The host was shared and loaded. That the main process got only about 2 cores is an observation from a process monitor during the run, written in the lane's notes; it is not in any committed file and is not a measurement. The integer MLP adds 3 dense products per integer path. The estimate was wrong by a factor of about 2.5 and the PREREG budget did not hold. This is the reason the run did not finish.
- Not touched, as registered: the stock leg (conditional, not started), the final norm and lm_head, so no logits, no top-1, no KL, and no sanity check.
- Weights (`runs/manifest-check.json`): all 226 stock and 198 abl tensors fetched have the sha256 of PR #124's committed manifests and of PR #68's `diff.json`; 319 embedding rows match.
- Determinism: XM18#2 (p01, p04, p09) bit-identical to XM18 after every one of the 31 layers (`runs/summary.json` `det_bit_equal_every_layer`). No guard error (no `errors-abl.jsonl`): every integer product stayed exact in float64.
- Debug before the run on the fixture only (`runs/debug-fixture/fixture.json`): integer MLP on synthetic arrays equal to a Python-int reference of the same formulas; the exactness guard raises when it should; save/load and duplicate path bit-equal.

## 2. Ranges (registered, descriptive, no threshold). Abl leg, layers 0 to 30, XM18, all 10 prompts
Source: `runs/ranges-abl.jsonl`, `runs/summary.md`, `runs/summary.json` `ranges`. The table pools layers 0 to 30, so it includes the post-cutoff layer 30 (descriptive, see the note at the top). Inside the cutoff (layers 0 to 29, `runs/aggregate-review.json` `m_class.XM18_excluding_last_layer`): m over class on 23,255,770 of 224,409,600 entries (10.36%), max 142,651 at layer 26 on p03. No other row changes: none of the other maxima or SiLU exits is at layer 30.

| quantity | largest \|x\| | log2 | where | bound (source) | outside the bound |
|---|---|---|---|---|---|
| m = RNE(2^12 x norm out) | 148,536 | 17.18 | layer 30, p03 | \|m\| <= 2,047 (DESIGN 3.2, `bounds.py` A_PUB) | **25,123,072 of 231,889,920 entries (10.8%), every layer** |
| gw | 38,091 | 15.22 | layer 26, p03 | honest 2^18, rng 2^23 | 0 |
| gw vs SiLU domain [-2^15, 2^15) | | | | v1 table domain [-8, 8) (DESIGN 5.2, 8.2) | **6 of 788,425,728** (2 below, layer 22; 4 above, layers 21, 24, 26); saturated here, a reject under v1 |
| u | 37,178 | 15.18 | layer 22, p08 | honest 2^18, rng 2^23 | 0 |
| s | 32,741 | 15.0 | layer 21, p06a | table image 32,741 | 0 (the max is the saturated top row) |
| h = floor(s u / 2^12) | 145,770 | 17.15 | layer 22, p05 | honest 2^18, rng 2^23 | 0 |
| down accumulator h . Wd | 5.06e8 | 28.92 | layer 26, p11 | ledger 2^55.02 (`bounds-r3.json` row "M3a-MLP down (r2)") | 0 |
| out | 123,590 | 16.92 | layer 26, p11 | \|out\| < 2^31 (DESIGN 3.2, OUT_PUB) | 0 |
| weight exponents e_g, e_u, e_d | 11 to 15 | | | 1..24 (DESIGN 5.0) | 0; every \|W_int\| <= 4,095 |

The m count by layer (per-layer counts in `runs/ranges-abl.jsonl`, per-layer maxima in `runs/summary.json` `ranges.abl.XM18.per_layer_max`): 0.27% of entries at layer 0, 4.1% at layer 10, 17.8% at layer 20, a peak of 25.5% at layer 27, then 24.5%, 24.4% and 25.0% at layers 28 to 30 (layer 30 post-cutoff). The share roughly increases with depth but is not monotone (layer 1 0.42% > layer 2 0.41%; layer 27 above 28 to 30). The maximum grows from 14,147 to 148,536. The FM path gives the same picture (25,060,897 entries; max 148,534; both pooled over layers 0 to 30).

What this means for the design: the M3a-MLP statement takes m as a public word in class \|m\| <= 2,047 (DESIGN 3.2). That class comes from upstream's Maverick norm, which clamps its output to 12 bits (docs/model.md 5). Qwen's RMSNorm has a learned gain (1 + w), and at the design's scale 2^12 its output does not fit 12 bits. Either the class or the scale has to change, or the norm has to clamp. Each of these is a change to the arithmetic, and this lane did not make one.

## 3. Drift against float64 (descriptive)
Residual relative L2 vs REF after layer 30 (`runs/summary.md`, `runs/divergence-abl.jsonl`). Layer 30 finished after the registered hard stop, so this table is descriptive post-cutoff evidence. After layer 29, the last layer inside the cutoff: median XM18 0.00614, FM 0.00597; sample SD (n - 1) 0.01642 / 0.01536; max (p03) 0.0581 / 0.0545 (`runs/aggregate-review.json` `resid_rel_layer_before_last`).

| prompt | XM18 | FM (float heads, integer MLP) |
|---|---|---|
| p01 | 0.0059 | 0.0059 |
| p07 | 0.0052 | 0.0050 |
| p08 | 0.0060 | 0.0058 |
| p09 | 0.0060 | 0.0056 |
| p02 | 0.0075 | 0.0070 |
| p04 | 0.0052 | 0.0052 |
| p05 | 0.0072 | 0.0069 |
| p03 (repeated word) | 0.0878 | 0.0858 |
| p06a | 0.0084 | 0.0081 |
| p11 | 0.0060 | 0.0059 |

Median over prompts after layer 30: XM18 0.0060, FM 0.0059. Sample SD over the 10 prompts (n - 1, one deterministic execution, not repeated runs): XM18 0.025767, FM 0.025205; min 0.00515 / 0.00496, max 0.0878 / 0.0858 (`runs/aggregate-review.json`, written by `aggregate_review.py` from the committed `runs/divergence-abl.jsonl` after the round-1 review). The SD is large because one prompt (p03) is an outlier. For context, PR #124's committed XS18-only path ended the whole 64-layer forward with at most 1.5% drift on every prompt except p03 (6.1 to 6.5%) (PR #124 RESULTS section 3). That number is after 64 layers and this one after 31, so they are not directly comparable. On p03 the XM18 drift is 1.0% to 1.25% at layers 19 to 25 and then rises to 2.9%, 3.5%, 4.1%, 5.8% at layers 26 to 29, and 8.8% at the post-cutoff layer 30. FM ends at 8.6% on p03, close to XM18's 8.8% (gap 0.20 percentage points). Per layer on p03 (`runs/aggregate-review.json` `p03_by_layer`):

| layers | XM18 | FM | FM / XM18 |
|---|---|---|---|
| 2 to 15 | 0.0054 to 0.0084 | 0.0036 to 0.0051 | 0.58 to 0.71 |
| 16 to 24 | 0.0077 to 0.0101 | 0.0042 to 0.0055 | 0.49 to 0.56 |
| 25 | 0.0125 | 0.0088 | 0.70 |
| 26 to 30 | 0.0286 to 0.0878 | 0.0245 to 0.0858 | 0.86 to 0.98 |

The largest XM18 minus FM gap on any prompt and layer is 0.51 percentage points (p03, layer 19: 0.01015 vs 0.00501). At layers 0 and 1, FM / XM18 is under 0.8 (0.72 to 0.80) on five prompts each. So the control says only this: an arm with the integer MLP and float heads reaches a similar distance to float64 as XM18 after layers 29 and 30 (FM / XM18 0.93 to 1.00 on every prompt at layer 30), and on p03 the jump at layers 25 to 30 happens with float heads too. Before layer 26, FM sits clearly below XM18 on p03 and on several prompts at the first layers. These are two distances to REF. They do not measure the distance between XM18 and FM, and they do not split XM18's error into a head part and an MLP part, since errors can interact and no XS18-only arm was run in this experiment. The largest m (layer 30, post-cutoff; inside the cutoff layer 26) and the largest gw (layer 26) are also on p03. The FM path has 7 SiLU domain exits against 6 for XM18 (one more above the domain, layer 22).

## 4. What this establishes, and what it does not
Established (on the layers done inside the registered cutoff, abl layers 0 to 29, 10 prompts; layer 30 agrees and is descriptive post-cutoff evidence):
- The M3 design's MLP input class \|m\| <= 2,047 does not hold for Qwen's real activations at the design's scale 2^12. It is exceeded in every one of layers 0 to 29 (and in the post-cutoff layer 30), on up to a quarter of entries per layer (peak 25.5% at layer 27).
- Gate, up, h, the down-projection accumulator and out stay inside the design's bounds; the r2 down-projection fix holds on real activations with about 26 bits of headroom.
- A handful of SiLU inputs (6 of 7.9e8) leave the v1 table domain, which v1 rejects.

Not established:
- **Any token-agreement number, and the bar's PASS or FAIL**, for any checkpoint. The logits were not reached.
- Layers 31 to 63 (including abliterated layers 31 to 51 and the last 12 layers); layer 30 only as post-cutoff evidence. The stock checkpoint as a run. (Layers 0 to 16 of the abl leg use stock weights, byte-identical per PR #68, on the same prompts, so by inference their range and drift rows are what a stock leg would give for those layers. That is an inference, not a stock run.)
- Whether a lowering that keeps m in class (clamp, a different scale or a wider class) keeps the tokens.
- Anything about proofs, soundness or constraint counts. in_proj, out_proj, attention, norms and lm_head stay float64.
- Replication by an independent lane.

## 5. Deviations
- The run did not finish by the registered hard stop. The prompt set was not shrunk (registered: the reduced set depends only on the grant time, which was before 17:25Z).
- **Watchdog overshoot (added after the round-1 review).** The PREREG says the watchdog kills the job by pid at 18:25Z. It polls every 20 s, so it killed the job at 18:25:18Z, 18 s late; layer 30 was saved at 18:25:14Z, inside that overshoot. Classification: a deviation in the stop mechanism, not a moved cutoff. The cutoff stays 18:25:00Z. Layer 30 is reported only as descriptive post-cutoff evidence, labelled wherever it is used; every registered finding is stated on layers 0 to 29 and does not change without layer 30 (`runs/aggregate-review.json`). The first write-up presented layer 30 as reached by the hard stop; that was wrong.
- The raw-runs commit 2b186b3 also edits `summarise_mlp.py` after the run (17 lines: partial-run reporting of layers done, per-layer divergence and the determinism flag; no metric logic). Code at the run is 1960ec5.
- Added after the round-1 review: `aggregate_review.py` and its output `runs/aggregate-review.json` (new files; the committed run files are not modified).
- One process restart from the per-layer checkpoint (section 1), cause outside the run; same code, no layer recomputed.
- `run.time` has no `time -v` block for either process start (corrected after review: the first write-up said only the first process lacked one). Peak RSS and CPU share are not recorded; the PREREG's RSS stop rule cannot be audited (section 1).
- PREREG amendment A-1 (format only: a "Hypothesis" heading restated verbatim).
- PREREG said m outside 2,047 would be checked "per (leg, layer, prompt)": done, and reported here pooled and per layer.
- The budget in the PREREG (40 to 65 s per layer) was wrong by about 2.5 times; see section 1.

## 6. Next registered arm (proposal, not run)
Resume the same run from the saved state (`ckpt.npz`, layer 30) with the same code and the same bar, on a quieter host or with a longer budget, to get the abl logits (about 33 layers at about 150 s plus about 2 min of logits: about 85 min). Separately, a design change for m (for example clamp to 2,047 as upstream's norm does, or m at a smaller scale) needs its own PREREG, because it changes the arithmetic.

## 7. Raw data
`runs/progress.log`, `runs/progress.log.jsonl`, `runs/run.log`, `runs/run.time`, `runs/ranges-abl.jsonl`, `runs/divergence-abl.jsonl`, `runs/heads-abl.jsonl`, `runs/manifest-{stock,abl}.json`, `runs/manifest-check.json`, `runs/summary.{json,md}`, `runs/debug-fixture/`. Reproduce: `summarise_mlp.py runs`, `check_manifests.py`, `env.py <code commit>`; the run itself: `run_mlp.sh <scratch>` under the gate (README of the e2e harness: `experiments/20261111-8-qwen-e2e-agreement/README.md`).
