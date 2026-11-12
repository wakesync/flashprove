# DeltaNet decay on real activations: softplus table domain, exp table step, four table designs (CPU, no proof)

Issue #136 (part of #35, informs #8). PREREG: [PREREG.md](PREREG.md) (first commit 38927cf, alone). Results: [RESULTS.md](RESULTS.md).

## What this is, in plain language

DESIGN M3 (section 5.3) computes the DeltaNet decay a = exp(-A softplus(ar + dt_bias)) with table lookups. This directory records the real inputs of that computation (ar per token and V head, A = exp(A_log), dt_bias) in all 48 DeltaNet layers of the abliterated Qwen3.8-27B over PR #124's 10 frozen prompts, then emulates four table designs in integers and compares their decay with float64.

**Nothing here is proved.** No proof, no constraint, no table digest. The designs are integer emulations of table semantics.

- **What is computed in float64:** the whole forward (PR #88 `q1_forward.py`, unchanged) and the reference decay.
- **What is emulated in integers:** the decay step only: ar floor at 2^12, dt_bias RNE at 2^12, the pinned v1 softplus table, cA = RNE(2^e_A A) with one e_A per layer, g floor, the exp tables (v1 layout, and the fine table on g at 2^-12), output at 2^12.
- **What a verifier would recompute:** not applicable.
- **Not covered:** a proof; end-to-end tokens with the tables; the stock checkpoint beyond layer 16; contexts over 512 tokens.

The only addition to the forward is `record.py`, which calls `q1_forward.layer_step(i, L, x, "REF", None, keep)` (the existing `keep` argument) and saves `keep["hd"]`'s `ar`, `A` and `dt_bias`. The residual was bit-equal to a plain `layer_step`, as recorded on the fixture run (`runs/debug-fixture/fixture.json`; rerunning it needs the checkpoint, there is no offline test of it).

## Files

| file | what it does |
|---|---|
| `PREREG.md` | registration |
| `record.py` | the forward with the logging hook; `fixture` = debug on a non-suite prompt |
| `run_record.sh` | the registered run with its stop time (through the heavy gate) |
| `decay_tables.py` | integer emulation of T0..T3, the error split and the F' sweep; `selftest` = synthetic checks |
| `summarise.py` | verdicts vs the registered bar -> `runs/eval/summary.{json,md}`; refuses (exit 2) an input that is not the complete registered cell set |
| `suite.py` | the registered suite (DeltaNet layers, heads, prompts and token counts) and the completeness checks used by `summarise.py` and `decay_tables.py eval` (added after the run, RESULTS section 6) |
| `test_completeness.py` | offline negative tests: dropped layers / heads / prompts / cells, one row per arm, a tiny fake input, inconsistent metadata, NaN; plus an intact control and a byte-for-byte rerun of the committed summary |
| `report.py` | descriptive tables -> `runs/eval/report.{json,md}` |
| `check_manifests.py` | sha256 of every fetched tensor vs PR #124's manifests |
| `env.py`, `scrub_time_path.py`, `add_results_row.py` | ENV.json, path scrub of run.time, results.yaml row |

## Reproduce

From this directory, with a scratch directory `$X` outside the repo (about 0.5 GB free), Python 3.12, numpy 2.x, network access to huggingface.co:

```
python3 decay_tables.py selftest $X/selftest.json
python3 test_completeness.py                                # offline, no model data, about 20 s
python3 record.py fixture $X/fx $X/fixture.json             # debug only, not a suite prompt
fp-heavy.sh taskset -c 6-11 bash run_record.sh $X/run S10   # about 25 min on 6 cores; resumes from $X/run/state.npz
python3 decay_tables.py eval $X/run/ar runs/eval            # about 1 min
python3 summarise.py runs/eval
python3 report.py
python3 check_manifests.py
```

`run_record.sh` has a registered wall-clock stop (2026-11-12T23:05Z); edit it to rerun at another time.

`decay_tables.py eval` and `summarise.py` take the full registered suite S10 by default and refuse anything else. A run stopped at the PREREG hard stop is evaluated with `--partial-layers N` (the first N DeltaNet layers, labelled PARTIAL), the reduced set with `--set S7`, the debug fixture with `--fixture`.
