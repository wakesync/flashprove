# DeltaNet decay tables, round 2: per-head exponent, 2^-20 scale, wider softplus, and one per-head table keyed on x (CPU, no proof)

Issue #155 (part of #35, follows #136 / PR #146, informs #8). PREREG: [PREREG.md](PREREG.md) (first commit `ef9bac0`, alone; four dated amendments after the run). Results: [RESULTS.md](RESULTS.md).

## What this is, in plain language

Every DeltaNet head of Qwen3.8-27B forgets a little of its memory at every token. The forgetting factor is a = exp(-A softplus(ar + dt_bias)). A proof would compute it with lookup tables. PR #146 recorded the real inputs of that computation (48 layers, 48 heads, 10 prompts, 1,461 tokens, abliterated checkpoint) and found that none of four table designs kept every head within its error bar. This directory takes the same recorded inputs and the same bar and tries four more designs, registered before any of them was evaluated:

- U1: PR #146's best design (T3) with one rounding exponent per head for the constant A instead of one per layer.
- U2: U1 with the intermediate values at a 256 times finer scale (2^-20 instead of 2^-12).
- U3: U2 with the softplus table extended from [-8, 8) down to -16.
- U4: a different shape: one table per head that maps the input x straight to the decay a, one lookup, no product.

**Nothing here is proved.** There is no proof, no constraint, no table digest and no format change. The designs are emulated in integers and compared with the float64 value.

- **What is computed in float64:** the reference decay (PR #146's `float_decay`, unchanged), and the rows of U4's per-head tables (by registration).
- **What is emulated in integers:** the decay step only. ar floored at 2^12, dt_bias rounded at 2^12, then the arm's tables and, for U1 to U3, the product with cA and its floor.
- **What a verifier would recompute:** not applicable.
- **Not covered:** a proof or its cost beyond counted table rows; end-to-end tokens with these tables; the stock checkpoint beyond layer 16; contexts over 512 tokens; a new recording of the inputs (PR #146's recorded arrays are reused).

No forward pass is run here and no weight is fetched.

## Files

| file | what it does |
|---|---|
| `PREREG.md` | registration (arms, bar, input rule, sha256 of the 48 input files) and amendments A1 to A4 |
| `design_inputs.py` | the tabulation of PR #146's committed per-head table that fixed the design constants (run before the PREREG; committed afterwards for the record) |
| `decay_r2.py` | integer emulation of U1 to U4; `fine20` builds the 2^20-row fine exp table; `eval` is the registered evaluation; `split` the descriptive split by source. Refuses an input that is not the registered files |
| `provenance.py` | the input rule: sha256 of every input file, and PR #146's unchanged evaluation on them compared with PR #146's committed output -> `runs/provenance.json` |
| `run_eval.py` | runs `decay_r2.py eval` with a start / end log -> `runs/progress.log.jsonl` |
| `summarise_r2.py` | verdicts against the registered bar -> `runs/eval/summary.{json,md}`; refuses (exit 2) a per-cell file that is not the complete registered cell set, has a negative or non-finite error (or median above max) on a cell without a rejected lookup, or is unreadable |
| `determinism.py` | compares the two runs of the registered evaluation -> `runs/determinism.json` |
| `posthoc.py` | POST HOC (Amendment A3): per-token error by band of g for U1 to U3 -> `runs/descriptive/gband.csv.gz` |
| `report_r2.py` | descriptive tables -> `runs/descriptive/report.{json,md}` |
| `test_r2.py` | offline tests on synthetic heads only: U1 with PR #146's per-layer exponent equals T3 bit for bit, U2 against a big-integer recomputation, U3 equals U2 inside [-8, 8), U4 against a brute-force row and its error bound, input refusal, and the summary's completeness checks |
| `input_digest.py` | content digest of the input arrays that does not depend on the .npz container bytes -> `runs/input-content.json` |
| `receipts.py` | receipts for the fine table and the test run -> `runs/fine20.json`, `runs/test_r2.json` |
| `env_r2.py`, `add_results_row.py` | ENV.json, the `research/results.yaml` row |

## Reproduce

From this directory, with Python 3.12 and numpy 2.x, a scratch directory `$X` outside the repo, and `$AR` = the directory of the 48 recorded files `ar-L*.npz`. PR #146 did not commit them; they come from its registered `record.py` run (see `../20261112-136-deltanet-decay/README.md`, about 25 minutes on 6 cores through the heavy gate, network access to the checkpoints).

```
python3 decay_r2.py fine20 $X/fine20.npy                    # about 5 s on 6 cores
R2_FINE20=$X/fine20.npy python3 test_r2.py                  # offline, synthetic heads, about 10 s
python3 input_digest.py $AR --compare                       # are these the arrays used here (content, not container)
python3 provenance.py $AR $X/prov-eval                      # about 1 min; rewrites runs/provenance.json
python3 run_eval.py $AR $X/eval $X/fine20.npy $X/progress.log.jsonl rerun      # about 15 s
python3 summarise_r2.py $X/eval
python3 determinism.py $X/eval                              # compares with the committed runs/eval
python3 decay_r2.py split $AR $X/descriptive $X/fine20.npy U4
python3 decay_r2.py split $AR $X/descriptive $X/fine20.npy U3
python3 posthoc.py $AR $X/descriptive $X/fine20.npy
python3 report_r2.py                                        # reads the committed runs/ files
```

`decay_r2.py eval`, `split` and `posthoc.py` refuse any input whose file bytes differ from the sha256 list in the PREREG, and need a passed `runs/provenance.json`. Whether a new recording gives the same file bytes was not tested here. If it does not, `input_digest.py --compare` says whether the array contents are equal; lifting the byte check is then a decision for the replicating lane to register, not something this code does silently.
