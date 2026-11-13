# RESULTS: 20261113-155-deltanet-decay-r2

**Verdict vs the pre-registered bar: U1 FAIL, U2 FAIL, U3 FAIL, U4 PASS. H (U3 passes, U1 and U2 fail) is false, because U3 fails. Measured, unreplicated, CPU, one deterministic evaluation, no proof.** This is a decay-only emulation of table semantics on PR #146's recorded inputs: no proof, no constraint build, no table digest or format change, and no end-to-end token check with any of these tables.

## Plain-language summary

PR #146 found that none of four lookup-table designs kept the DeltaNet decay a = exp(-A softplus(ar + dt_bias)) of every head of Qwen3.8-27B abliterated within its bar, and named three changes that were not tested. This experiment registered those changes as arms and evaluated them on the same recorded inputs (48 layers x 48 heads x 10 prompts, 1,461 tokens) against the same bar.

- The three changes help but do not close it. The designs that keep PR #146's shape (softplus lookup, product with a rounded constant, exp lookup) still fail: with a per-head exponent 1,336 of 2,304 heads fail (PR #146's best: 1,513); adding a 256 times finer scale, 504; adding softplus rows down to -16, 294.
- What is left in that last design (U3) is one thing: on tokens where the exponent g is at least 1, it still reads the exp table of format v1, whose rows are 1/256 apart, after a softplus row that is also 1/256 wide. The two roundings push the same way and together reach 0.0028 per token against a bar of 0.00195. Its accumulated error is fine on every cell.
- A different shape passes: one table per head that maps the input x directly to the decay (12,288 rows per head, one lookup, no product). It meets the bar on all 23,040 cells; largest per-token error 0.00071, largest accumulated error 0.00070 (bar 0.01).
- The passing design has a cost that is counted here, not built: 28.3 million table rows for the model that depend on a weight, so they would be committed with the model, and a lookup into a committed table, which no design on main specifies.
- Limits: the table domains were fixed from the ranges seen on these same 10 prompts; one checkpoint; prompts of at most 512 tokens; nothing is proved.

## 1. Run record

- PREREG `PREREG.md`: first commit `ef9bac0769b089673a72a2e012db4cec447ff64d`, alone, before any code. Amendments A1 to A3 (commit `fa595731`), all after the registered run: a correction of the header time, a record of the input branch taken, and two post hoc descriptive computations declared before they were run.
- Arm code: `decay_r2.py`, `summarise_r2.py`, `provenance.py`, `test_r2.py` in `4c25604e`. The registered run was made at `cba5725b` (`runs/progress.log.jsonl`, `arm_code_modified: false`); `decay_r2.py`, `summarise_r2.py` and `provenance.py` have not changed since `4c25604e`.
- Debug before the run, as registered: synthetic heads only (`test_r2.py`, numpy seed 155; receipt of a later run `runs/test_r2.json`) and PR #146's debug fixture, "The capital of Italy is", stock layers 0 to 2, 5 tokens, not a suite prompt (`runs/debug-fixture/`). The fixture output was seen before the registered run: U1, U2 and U3 missed the per-token bar on 15, 10 and 10 of 144 fixture cells, U4 on none.
- Input (`runs/provenance.json`): the 48 array files of PR #146's registered recording were still in that lane's scratch output. Every file's sha256 equals the list written in the PREREG before use, and PR #146's unchanged `decay_tables.py eval` on them reproduces PR #146's committed `runs/eval/cells.csv.gz` and `domain.json.gz` (equal decompressed bytes). So the arrays were used and `record.py` was not rerun. A container-independent digest of the array contents is in `runs/input-content.json`.
- Tables (`runs/eval/eval-meta.json`, `runs/fine20.json`): every table of U1 to U3 comes from the pinned integer generator, including all 1,048,576 rows of the fine exp table (0 rows differ from float64 round-to-nearest; the float fallback of the PREREG was not needed). U4's per-head rows are float64 by registration.
- Registered run (`runs/progress.log.jsonl`): 2026-11-13T01:47:25Z to 01:47:39Z, exit 0, 13.6 s wall, 151 MiB peak RSS, cores 0 to 5, one process. Run twice as registered (second run 01:47:43Z to 01:47:56Z): per-cell outputs equal (`runs/determinism.json`).
- Completeness (`runs/eval/summary.json` `coverage`): COMPLETE, 23,040 cells per arm, checked against PR #146's `suite.py`.

## 2. Registered verdicts

Bar, unchanged from PR #146, on every (layer, head, prompt) cell: no rejected lookup; e_tok = max over tokens of |a_table - a| <= 2^-9 = 0.001953; e_cum = max over tokens of |prod_{s<=t} a_table - prod_{s<=t} a| <= 0.01. Cells: 48 layers x 48 heads x 10 prompts = 23,040. Source `runs/eval/summary.json`, table `runs/eval/summary.md`, raw per-cell values `runs/eval/cells.csv.gz`. The T3 row is PR #146's committed result, for comparison.

| arm | verdict | failing cells / 23,040 | by reason: reject, e_tok, e_cum | failing (layer, head) / 2,304 | e_tok max per cell: median (max) | e_cum max per cell: median (max) |
|---|---|---|---|---|---|---|
| T3 (PR #146) | FAIL | 6,391 | 0, 3,854, 3,253 | 1,513 | 0.000838 (0.0396) | 0.00182 (0.290) |
| U1 (T3 + per-head cA exponent) | **FAIL** | 3,942 | 0, 1,175, 2,772 | 1,336 | 0.000520 (0.00854) | 0.00137 (0.290) |
| U2 (U1 + scale 2^-20) | **FAIL** | 1,210 | 0, 850, 378 | 504 | 0.000348 (0.00991) | 0.000519 (0.400) |
| U3 (U2 + softplus rows down to -16) | **FAIL** | 815 | 0, 815, 0 | 294 | 0.000338 (0.00282) | 0.000497 (0.00260) |
| U4 (per-head table keyed on x) | **PASS** | 0 | 0, 0, 0 | 0 | 0.000161 (0.000712) | 0.000120 (0.000697) |

A cell can fail for more than one reason. n = 23,040 cells for every median; SD, minimum and median of the per-token error are in `summary.json`. No arm rejected a lookup (only U4 can; the largest x on these prompts is 26.02, its table ends at 32).

H: U3 PASS and U1, U2 FAIL. **False** (U3 fails).

Two things in the table that are easy to misread:
- U2's worst cells are worse than U1's (largest e_cum 0.400 against 0.290, largest e_tok 0.00991 against 0.00854) although U2 fails far fewer cells. All 208 heads that fail e_cum under U2 have x below -8 on some token (section 4). A possible reading, not tested: in U1 the floor of g and the softplus clamp below -8 err in opposite directions and partly cancel, and the finer scale removes one of them.
- U4's per-token pass is close to arithmetic: with one key at the middle of a 1/256 row, the error is at most (8.5 / 4096) / e + 2^-21 = 0.000764 for any A, under the bar of 0.001953. What the run adds for U4 is the accumulated error (that argument only bounds it by the sum of the per-token errors, about 0.39 over 512 tokens, far above the bar of 0.01) and that no x on these prompts left the table.

Expectation written in the PREREG before the run, against the result: "U1 to U3 may fail the per-token bar on tokens with g >= 1 (two floors together can reach about 0.0029)": U3's largest per-token error is 0.00282 and every one of its failing cells has its worst token at g >= 1 (section 4). "U2 is expected to fail on large-A heads whose x goes below -8": U2's accumulated failures are all on heads with x below -8, but their A is 0.082 to 17.2 with median 0.47, so "large-A" was wrong. "U4 is expected to pass": it passed.

## 3. Where the arms fail (descriptive, no threshold; `runs/descriptive/report.md`, `report.json`)

- **Per layer** (failing heads of 48): U1 15 (layer 38) to 44 (layer 4), every DeltaNet layer; U2 0 (layers 0 and 54) to 29 (layer 2); U3 0 (10 layers: 0, 20, 50, 54, 56, 57, 58, 60, 61, 62) to 29 (layer 2).
- **Per prompt** (failing cells of 2,304): U1 63 (p01, 13 tokens) to 985 (p03, 512 repeated words); U2 34 to 247; U3 20 (p04) to 193 (p11). U3's count does not grow with prompt length the way U1's does, as expected when nothing accumulates.
- **Per-head exponent** (`runs/eval/heads.json.gz`): e_h runs from 4 to 20 and every cA_h is between 2,051 and 4,091, so every head keeps 12 bits of A. Under PR #146's per-layer rule 170 heads had cA below 16. A layer has 3 to 10 distinct exponents (median 8).
- **U1's accumulated failures**: 1,023 heads fail e_cum; 914 of them have a median g below 1/256 (median g from PR #146's committed table). The per-head exponent does not touch the floor of g at 2^-12, which PR #146 named as the main source of accumulated error.
- **15 worst U3 heads** by per-token error: layer 1 heads 44, 36, 45, 46; layer 14 head 12; layer 28 head 27; layer 8 head 8; layer 13 heads 33, 24, 30; layer 4 head 6; layer 24 head 42; layer 45 head 35; layer 9 head 42; layer 2 head 44 (e_tok 0.00261 to 0.00282; A 2.8 to 63.8; table with cA, dt_bias and g in `report.md`). All 294 failing U3 heads have g >= 1 on some token; 961 heads in the model do.

## 4. Sources of the remaining error

**Registered: split of the best arm, U4** (`runs/descriptive/split-U4.csv.gz`; each source alone, the rest float64, 23,040 cells).

| source | cells e_tok > 2^-9 | cells e_cum > 0.01 | e_tok max per cell: median (max) | e_cum max per cell: median (max) |
|---|---|---|---|---|
| row step (key = middle of a 1/256 row of x) | 0 | 0 | 0.000161 (0.000712) | 0.000119 (0.000697) |
| output rounding of a at 2^-20 | 0 | 0 | 4.73e-07 (4.77e-07) | 5.54e-07 (0.000212) |

U4's error is its row step. The output scale contributes nothing visible per token.

**Post hoc (PREREG Amendment A3, declared after the verdicts and before running; no threshold, no verdict).** The registered split covers only the best arm, and the best arm passes, so two computations were added to say where U1 to U3 fail.

Split of U3 by source (`runs/descriptive/split-U3.csv.gz`, by the split code committed before the run):

| source alone | cells e_tok > 2^-9 | cells e_cum > 0.01 | e_tok max per cell: median (max) | e_cum max per cell: median (max) |
|---|---|---|---|---|
| cA = RNE(2^(e_h) A_h), one exponent per head | 0 | 0 | 1.5e-05 (8.69e-05) | 2.34e-05 (8.69e-05) |
| softplus table (rows 1/256 apart, down to -16, passthrough above 8) | 0 | 0 | 0.000325 (0.00143) | 0.00044 (0.00139) |
| g floor at 2^-20 and exp tables (fine below 1, v1 rows above) | 0 | 0 | 1.3e-06 (0.00143) | 9.65e-06 (0.00139) |
| output rounding of a at 2^-20 | 0 | 0 | 4.73e-07 (4.77e-07) | 5.54e-07 (0.000212) |

No single source fails any cell on its own. All 294 failing U3 heads fail only through the combination. The two sources that reach 0.00143 are the softplus row step and the exp tables. Both are just under (1/256) / e = 0.00144, which is the most a step of 1/256 in a key can move a (derived arithmetic, not a measurement).

Per-token error by band of the float64 exponent g (`runs/descriptive/gband.csv.gz`, `posthoc.py`):

| arm | cells over the e_tok bar | of these, worst token has g >= 1 | cells whose g < 1 tokens alone exceed the bar | largest error on g < 1 tokens | largest error on g >= 1 tokens |
|---|---|---|---|---|---|
| U1 | 1,175 | 829 | 441 | 0.00854 | 0.00482 |
| U2 | 850 | 814 | 36 | 0.00991 | 0.00282 |
| U3 | 815 | 815 | 0 | 0.00147 | 0.00282 |

207,656 of the 3,366,144 (token, head) values (6.17%) have g >= 1. For U3 the worst token of every failing cell has g between 1.006 and 1.54 (median 1.08), and on tokens with g below 1 its largest error anywhere is 0.00147, under the bar. So every U3 failure is on a token whose float64 g is at least 1, the region where U3 reads the v1 exp rows instead of the fine table.

U2's accumulated failures: 208 heads fail e_cum and all 208 have x below -8 on some token (9% to 99.9% of their tokens, median 47%); with the softplus rows extended to -16 (U3) no cell fails e_cum.

## 5. Cost of each design (counted from the registered table shapes and DESIGN M3 sections 5.0, 5.2, 5.3, 6 and 7; **counted, not built, and not a measurement**)

DESIGN 5.3 counts for the decay, per head per token: one softplus lookup, one product with the committed cell cA and its floor with a remainder, one exp lookup. It says the fine exp table of PR #146's T2 / T3 "costs one more lookup per head per token" and that its own counts do not include it. Table rows below are in `runs/descriptive/report.json` (`counted_not_built`).

| arm | function lookups per head per token | committed cells per head for the decay | public table rows | rows of tables that depend on a weight | other |
|---|---|---|---|---|---|
| DESIGN 5.3 as counted | 2 (softplus, exp) | cA, dt_bias | 8,192 | 0 | one exponent per layer |
| T3 (PR #146) | 3 (softplus, coarse exp, fine exp) | cA, dt_bias | 12,288 | 0 | plus a branch on x >= 8, not counted in DESIGN |
| U1 | 3 | cA, dt_bias (unchanged) | 12,288 | 0 | 48 public exponents per layer instead of 1 (2,304 in the model). 1,412 heads get a shift above 12 against 192 under the per-layer rule; DESIGN 7 already counts the two-limb remainder for every shift, so its count does not change |
| U2 | 3 | cA, dt_bias | 1,056,768 (fine exp 1,048,576) | 0 | as U1; sp and g at 2^-20 |
| U3 | 3 | cA, dt_bias | 1,058,816 (2,048 more softplus rows) | 0 | as U2 |
| U4 | 1 | dt_bias only (no cA cell, no product, no floor remainder) | 0 | 12,288 per head, 589,824 per layer, 28,311,552 for the 48 layers | the table replaces cA; no exponent |

Not counted, and each one is a real obligation for a build:
- **U2, U3: the 2^20-row fine table.** For scale only: DESIGN 7.2 lays the whole M3a-head statement out in a table of 2^21, and the fine table alone has 2^20 rows. How such a table would be laid out or looked up is not counted here. Splitting the key into digits with a small table per digit (zkLLM's tlookup, PREREG "Prior art") avoids the big table at the price of a product and a rounding per digit; that variant was not emulated, so its error is not known.
- **U2, U3: cell width.** g at 2^-20 reaches about 2^25.5 on these prompts (largest g 43.9, PR #146's `domain.json.gz`) and the passthrough softplus value about 2^24.7 (largest x 26.02); DESIGN 6's range class for ordinary cells is |x| < 2^23. Derived arithmetic, not checked against `bounds.py`.
- **U4: a lookup into a committed table.** DESIGN 5.2 and 8.3 have function lookups into public tables whose digest is in the configuration. U4's rows depend on A_h, so the table is model data: it would be committed with the weights (28,311,552 rows next to the 26,895,337,984 committed integers of DESIGN 7.1, about 0.1% more; derived arithmetic) and looked up as a committed table. No design on main specifies that lookup, its soundness, or how the table is tied to A_log. This is the main open cost of the one arm that passes.
- **U4: row generation.** The rows were computed in float64 (as registered). DESIGN 5.2 requires tables "generated without floating point"; an integer generator for these rows was not written, and a row that sits near a rounding tie could differ between float libraries.
- **U4: output scale.** a comes out at 2^-20 while the stream is at 2^-12; the state update that multiplies by a would have a wider product. Not counted. Whether U4 still passes with a at 2^-12 was not registered and not measured.
- **U4: rows actually reached.** On these 10 prompts the per-head x ranges span 5,494,684 of the 28,311,552 rows (median 2,242 rows per head, largest 7,622). Descriptive, from PR #146's committed per-head minimum and maximum; it is not a bound and says nothing about other prompts.

## 6. What this means for #35 and the next lane (inferred from sections 2 to 5, not measured as arms)

- The issue asked whether "a table-based decay cannot meet a half-BF16-ulp bar ... at an affordable table size". Measured: the three registered designs of the softplus, product, exp shape do not meet it; a per-head table keyed on x does, at 12,288 rows per head. Whether that is affordable depends on the committed-table lookup, which is not designed.
- U3's remaining failures all sit on tokens with g between 1 and 1.54, where it uses the v1 exp rows after a v1-width softplus row. A fine exp table that reaches further than g = 1, or keys taken at the middle of a row instead of its lower edge, are the obvious next arms for that shape. Neither was registered here, so neither has a verdict.
- The per-head exponent and the wider softplus domain each removed a named failure class (the 1-to-15-level heads; the accumulated error of heads with x below -8) at almost no table cost. The finer scale is what costs: 2^20 rows, or a digit split with unmeasured error.
- Before U4 is taken as the design, it needs an arm with integer-generated rows and the output at the stream scale, prompts that were not used to choose its domain, and the end-to-end check below.

## 7. Deviations from the PREREG and disclosures

- Arms, table constants, metric, bar and prompt set are as registered. No arm was evaluated on a registered array before the registered run.
- **Amendment A1.** The PREREG header says its date was "read from the host clock". The clock was read at 01:34:40Z and "01:36Z" was typed as an estimate of when the commit would land (it landed at 01:36:07Z); the commit time is the record.
- **Amendment A3, post hoc.** The U3 split and the g-band table of section 4 were added after the verdicts were seen. They are descriptive, have no threshold and change no verdict. The amendment and `posthoc.py` were committed before either was run.
- The design constants (G = 20, the -16 softplus bound, U4's [-16, 32) domain) were fixed from PR #146's committed per-head minimum, median and maximum of x and g, which come from the same 10 prompts the arms are then evaluated on. The bar and the metric were not tuned, but the domains are in-sample: on other prompts x could fall below -16 (clamped, error at most A softplus(-16)) or reach 32 (U4 rejects).
- `design_inputs.py`, the script that produced that tabulation, was run from outside the repo before the PREREG and committed afterwards (docstring changed, code not).
- Code written after the registered run: `posthoc.py`, `determinism.py`, `report_r2.py`, `env_r2.py`, `input_digest.py`, `receipts.py`, `add_results_row.py`. In `test_r2.py` one test method was renamed and one comment added after the run; no assertion changed.
- The heavy-CPU gate was not used. The longest step was PR #146's evaluation for the input check (52 s, one process); the registered evaluation took 13.6 s and peaked at 151 MiB; the fine table was generated with 6 processes in 5 s. Peak memory of the other steps was not measured.
- The input arrays are not committed (27 MB; PR #146 did not commit them either). A reader without them has to re-record with PR #146's `record.py`. Whether a re-recording gives the same file bytes as the PREREG list was not tested (`input_digest.py` compares contents instead).
- Host shared and loaded during the run; it does not affect deterministic results.

## 8. What is not established

- No proof, constraint count, soundness or table digest. These are integer emulations of table semantics, not proved relations.
- That U4 can be built: the committed-table lookup, an integer row generator, and the output scale are open (section 5).
- No end-to-end token agreement with any of these tables. Whether U3's per-token misses of up to 0.0028, or U4's of up to 0.0007, change a token is not known; PR #124's harness would answer that.
- Other prompts and longer contexts. 10 frozen prompts of at most 512 tokens, the same ones the domains were chosen on. Accumulated error grows with length; U4's largest was 0.0007 at 512 tokens and is not bounded by an argument here.
- The stock checkpoint (layers 0 to 16 are shared, layers 17 to 63 are abliterated only).
- Replication. One lane, one deterministic evaluation run twice on one host, on arrays recorded by one earlier run.
- The variants named in section 6. None was registered or measured.
- The bar is PR #146's choice (half a BF16 ulp per token, 0.01 accumulated). A different bar would move the counts.

## 9. Raw data

- `runs/eval/cells.csv.gz`: per arm, layer, head, prompt: T, rejects, e_tok max / median, e_cum max, max |ln P_arm - ln P|.
- `runs/eval/heads.json.gz`: per layer and head: A, dt_bias, e_h, cA_h. `runs/eval/eval-meta.json`: table sha256, G, table shapes, bar, input list digest.
- `runs/eval/summary.json`, `summary.md`: verdicts, failing heads per layer, failing cells per prompt, worst cells.
- `runs/descriptive/split-U4.csv.gz` (registered), `split-U3.csv.gz` and `gband.csv.gz` (post hoc), `report.json`, `report.md`.
- `runs/provenance.json`, `runs/input-content.json`, `runs/progress.log.jsonl`, `runs/determinism.json`, `runs/fine20.json`, `runs/test_r2.json`, `runs/debug-fixture/`.
- PR #146's committed files used for comparison: `../20261112-136-deltanet-decay/runs/eval/summary.json`, `domain.json.gz`.
