# RESULTS: 20261112-136-deltanet-decay

**Verdict: FAIL vs the pre-registered bar for all four table designs (T0, T1, T2, T3). H (T2 passes, T0 and T1 fail) is false. Measured, unreplicated, CPU, one deterministic run, no proof.** This is a decay-only proxy: no proof, no constraint build, no table digest change, and no end-to-end token check with the tables.

## Plain-language summary

The DeltaNet layers of Qwen3.8-27B forget their memory a little at every token. The forgetting factor a = exp(-A softplus(ar + dt_bias)) is one number per token and head. A proof would compute it with lookup tables (DESIGN M3 section 5.3). We recorded the real inputs to that computation in all 48 DeltaNet layers, 48 heads each, over 10 frozen prompts (1,461 tokens) on the abliterated checkpoint, and checked four table designs against the exact float64 value.
- The softplus input leaves the v1 table domain [-8, 8) on 8.1% of all values, on 939 of the 2,304 (layer, head) pairs. It is mostly below -8 (94% of the out-of-domain values), not above. One head (layer 0, head 8, dt_bias 19.25) is above 8 on every token.
- The decay exponent g is below one v1 exp-table row (1/256) on 39% of all values. For 965 of 2,304 heads that is the typical case.
- No design keeps every head within the bar. v1 as published (T0) rejects at least one token on 939 heads. With clamping (T1) it fails 2,291 heads. Adding the fine exp table (T2) brings that to 1,642, adding a softplus passthrough above 8 (T3) to 1,513.
- What is left is about precision, not domain: the fine table's 2^-12 step on g, one cA exponent per layer (heads with small A next to a large-A head get only 1 to 15 integer levels), and the softplus row step of 1/256. A finer internal scale alone (F' up to 18 with the v1 softplus row grid) does not close it.

## 1. Run record

- PREREG `PREREG.md`: first commit `38927cf`, alone. No amendments.
- Code at the run: `513ab974b603003e9a613cac99e37773d7b9b189` (`record.py`, `decay_tables.py`, `run_record.sh`). `summarise.py` added in `231b7dc`, before the run produced output; `report.py`, `check_manifests.py`, `env.py`, `scrub_time_path.py`, `add_results_row.py` after the run (descriptive and bookkeeping only; no threshold).
- Debug before the run, only on the fixture "The capital of Italy is" (stock layers 0 to 3, not a suite prompt) and on synthetic heads (`runs/debug-fixture/`): the driver's residual is bit-equal to plain `q1_forward.layer_step`, a rerun is bit-equal, `ar`, `A = exp(A_log)` and `dt_bias` are as stored; the generated coarse exp rows and the regenerated softplus rows equal float64 RNE at every row, and the regenerated F = 14 softplus grid equals the pinned `softplus-f14` table.
- Run (`runs/progress.log.jsonl`): heavy slot granted 2026-11-12T21:20:06Z (host bigmem lock, then `fp-heavy.sh`, `taskset -c 6-11`), MemAvailable 17 GB, registered set S10 (all 10 prompts), finished 21:44:19Z, exit 0, well before the 23:05Z forward stop. `runs/run.time`: 24:12 wall, max RSS 7.43 GB. S7 was not needed.
- Forward sanity (registered): REF top-1 after p01 = " Tokyo" (25358), `runs/sanity.json`.
- Weights (`runs/manifest-check.json`): all 226 stock and 624 abliterated tensors and 319 embedding rows fetched here have the same sha256 as PR #124's committed manifests, same revisions.
- Table evaluation: `decay_tables.py eval` (54 s), `summarise.py` (verdicts), `report.py` (descriptive tables). The pinned v1 softplus table's sha256 is checked against its manifest before use (`runs/eval/eval-meta.json`).

## 2. Registered verdicts

Bar, on every (layer, head, prompt) cell: no rejected lookup; e_tok = max over tokens of |a_table - a| <= 2^-9; e_cum = max over tokens of |prod_{s<=t} a_table - prod_{s<=t} a| <= 0.01. Cells: 48 layers x 48 heads x 10 prompts = 23,040. Source `runs/eval/summary.json`, table `runs/eval/summary.md`, raw per-cell values `runs/eval/cells.csv.gz`.

| arm | verdict | failing cells / 23,040 | by reason: reject, e_tok, e_cum | failing (layer, head) / 2,304 | e_tok max per cell: median (max) | e_cum max per cell: median (max) |
|---|---|---|---|---|---|---|
| T0 (v1, reject) | **FAIL** | 22,562 | 4,136, 18,271, 12,848 | 2,300 | 0.00379 (0.0384), n = 18,904 cells without reject | 0.0144 (1.0) |
| T1 (v1, clamp) | **FAIL** | 22,283 | 0, 22,030, 12,552 | 2,291 | 0.00378 (0.392) | 0.0129 (0.806) |
| T2 (T1 + fine exp on g < 1 at 2^-12) | **FAIL** | 6,964 | 0, 4,443, 3,542 | 1,642 | 0.000867 (0.390) | 0.00190 (0.390) |
| T3 (T2 + softplus passthrough at x >= 8) | **FAIL** | 6,391 | 0, 3,854, 3,253 | 1,513 | 0.000838 (0.0396) | 0.00182 (0.290) |

A cell can fail for more than one reason. For T0 a rejected token counts as a failure of its cell, and e_tok is reported only over cells without a reject (T0's e_cum treats a rejected token as a = 0, so its e_cum is not meaningful beyond "failed").

H: T2 PASS and T0, T1 FAIL. **False** (T2 fails).

Per prompt (failing cells of 2,304; `runs/eval/report.md`): T3 fails 301 (p01, 13 tokens) to 1,093 (p03, 512 repeated words); the longer the prompt, the more cells fail, as expected for an accumulated error. T0 and T1 fail almost every cell on every prompt.

## 3. Domain and step on real activations (issue item 2)

All values over 48 layers x 48 heads x 1,461 tokens = 3,366,144 (source `runs/eval/summary.json` `domain`; per head `runs/eval/domain.json.gz`, with n, min / median / max of x, g and a, and the shares).

- x = ar + dt_bias outside [-8, 8): **273,008 (8.11%)**: 256,478 below -8, 16,530 at or above 8. Heads with at least one: 939 of 2,304; with every token outside: 1 (layer 0 head 8, dt_bias 19.25, x in [16.99, 26.02]). Per-head share: median 0, max 1.0. Overall x range: -15.11 to 26.02.
- g = A softplus(x) below 1/256: **1,311,822 (38.97%)**. Per-head share: median 0.28, max 1.0; 965 heads have it on more than half of their tokens. Per-head median g: median 0.0081, min 1.7e-6, max 11.8.
- By layer (`domain.per_layer`): layer 0 has the most out-of-domain values (16,442 of 70,128, on 46 of 48 heads), then 52, 42, 26, 62, 48, 44, 53 (10k to 13k each). g below the step: 8,922 (layer 2) to 39,098 (layer 52) of 70,128.
- A spans 0.0038 to 139.4 across the model (layer 12 has the largest, 139.4), dt_bias -8.94 to 19.25.

DESIGN 8.2 said the domain problem was "not measured" and expected it from dt_bias 19.3 (above the domain). Measured: it is real but mostly on the other side, below -8, where softplus is tiny (< 3.4e-4) and a clamp sets it to softplus(-8). That is harmless for small A and not for large A (for A = 139, the clamp error in g is up to 0.047). DESIGN 5.3's inference that "at least half" of the exponents fall in the first exp row is of the right order: 39% of values, a majority on 965 of 2,304 heads.

## 4. Where T3 still fails (descriptive, no threshold; `runs/eval/report.md`, `report.json`)

T3 failing heads per layer (of 48): 16 (layer 58) to 45 (layer 12); every DeltaNet layer has failing heads.

**Error split by source** (`runs/eval/split-T3.csv.gz`): each source applied alone with everything else float64, over the 23,040 cells.

| source | cells e_tok > 2^-9 | cells e_cum > 0.01 | e_tok max: median (max) | e_cum max: median (max) |
|---|---|---|---|---|
| cA = RNE(2^(e_A) A), one e_A per layer | 2,263 | 564 | 0.000219 (0.0398) | 0.000386 (0.066) |
| softplus table (v1 row step 1/256, clamp below -8, passthrough above 8) | 409 | 240 | 0.000345 (0.00845) | 0.000479 (0.306) |
| g floor at 2^-12 + exp tables (fine and coarse) | 0 | 2,654 | 0.000303 (0.00148) | 0.000835 (0.115) |
| output rounding of a at 2^-12 | 0 | 270 | 0.000121 (0.000122) | 0.000143 (0.0571) |

- **Accumulated decay (e_cum):** the g floor at 2^-12 is the main source. For a slow head, g is around 1e-4 to 1e-3, so floor(2^12 g) loses up to 100% of g per token and the error compounds over the prompt. 923 of the 1,513 failing T3 heads have a median g below 1/256.
- **Per-token decay (e_tok):** the per-layer cA exponent is the main source. DESIGN 5.0's honest conversion picks one exponent per layer from the largest A; in layers 12, 28 and 44 (max A 82 to 139, e_A 4 or 5) 28 to 33 heads end up with cA between 1 and 15, i.e. 1 to 4 bits for A. 170 heads model-wide have cA below 16 (none at 0); 166 of them fail under T3.
- **Attribution per failing T3 head** (which single source already fails that head alone): g floor and exp alone 516; g floor with output rounding 156; cA alone 137; cA with g floor 136; softplus alone 70; other combinations 180; no single source alone (only the combination) 318.
- **Finer internal scale** (`runs/eval/sweep-T3-F.csv.gz`; T3 with sp, g, the fine key and a at 2^F', the softplus rows still at the v1 grid 1/256 and cA as above): F' = 14 / 16 / 18 leave 3,528 / 3,517 / 3,509 cells over the e_tok bar and 1,093 / 925 / 949 over the e_cum bar. The e_tok count barely moves because cA and the softplus row grid do not change with F'.

**15 worst T3 heads by e_cum** (full list with A, cA, dt_bias in `report.md`; the top 3 are on p03): layer 42 head 12 (A 9.64, e_cum 0.29 on p03), layer 26 head 14 (0.27), layer 48 head 31 (0.19), layer 42 head 35, layer 13 heads 27 and 29, layer 29 head 29, layer 46 head 40, layer 60 heads 18 and 20, layer 26 head 12, layer 0 heads 24 and 40, layer 32 head 31, layer 10 head 38 (0.105). 13 of the 15 have dt_bias between -5.3 and -7.6 (the two layer-0 heads -1.8 and -2.5, with A 0.004 and 0.017), and all 15 have a median g below 0.004: slow heads, whose small g the 2^-12 floor erases.

## 5. What a passing design would need (input for #35, inferred from section 4, not measured as an arm)

- **Per-head cA exponent** (or a fixed 12-bit mantissa per head), not one per layer. That removes the 1-to-15-level heads.
- **g at a finer scale than 2^-12 for slow heads**, or a decay table keyed on x (or on sp) per head, so that g around 1e-4 is not floored to 0. The sweep shows that a finer scale with the same cA and softplus grid is not enough on its own.
- **Softplus below -8:** clamp is acceptable only where A is small; for large-A heads either a wider domain (down to about -16 on these prompts) or exp(x) passthrough (softplus(x) is about exp(x) there).
- None of these was registered here, so none has a verdict. The next lane should register them as arms with the same bar and the same raw data (the ar arrays are reproducible from the code and the pinned checkpoints in 25 minutes).

## 6. Deviations from the PREREG and disclosures

- No amendment. All four arms, the metric, the bar and the prompt set are as registered. S10 ran in full.
- `report.py` (section 4) was written after the verdicts. It is descriptive and has no threshold.
- e_tok for T0 is reported over the cells without a reject (stated in section 2).
- The PREREG said "raw per-token x is kept in scratch, not committed if over budget". The per-token arrays are not committed (about 27 MB as float64, fully reproducible); per-cell and per-head tables are committed (`runs/eval/`, 6.3 MB total).
- Host shared and loaded during the run; it does not affect deterministic float64 results.

## 7. What is not established

- No proof, constraint count, soundness or table digest. Table semantics here are integer emulations of the designs, not proved relations.
- No end-to-end token agreement with any of these tables. A decay error of 0.29 in the accumulated decay of one head on a 512-token prompt may or may not change a token; PR #124's harness would answer that.
- Stock checkpoint not measured (out of scope); layers 0 to 16 are shared, layers 17 to 63 are abliterated only.
- Prompts: 10 frozen prompts, at most 512 tokens. Longer contexts accumulate more decay error; not measured.
- The bar is a choice fixed in the PREREG (half a BF16 ulp per token, 0.01 accumulated). A looser bar would change the counts, not the ranking of the arms or the sources.

## 8. Raw data

- `runs/eval/cells.csv.gz`: per arm, layer, head, prompt: T, rejects, e_tok max / median, e_cum max, max |ln P_arm - ln P|.
- `runs/eval/domain.json.gz`: per layer and head: n, A, dt_bias, e_A, cA, shares and counts of x outside the domain and g below the step, min / median / max of x, g, a.
- `runs/eval/split-T3.csv.gz`, `runs/eval/sweep-T3-F.csv.gz`: descriptive.
- `runs/eval/summary.json`, `summary.md`, `report.json`, `report.md`, `eval-meta.json`.
- `runs/progress.log.jsonl`, `runs/run.time`, `runs/sanity.json`, `runs/manifest-{stock,abl}.json`, `runs/manifest-check.json`, `runs/debug-fixture/`.
