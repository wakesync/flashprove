# Q1: does the integer Qwen DeltaNet lowering hold past layer 0? (CPU, no proof)

Issue #8, part of #32. Agenda question Q1 (fidelity), use case U1 (model substitution) first. PREREG: [PREREG.md](PREREG.md) (first commit 07a5417). Results: [RESULTS.md](RESULTS.md). Built on PR #68 and PR #74, both on main; their code is reused unchanged.

## What this is, in plain language

PR #68 and PR #74 measured the integer arithmetic of one Gated DeltaNet layer (layer 0) of Qwen3.8-27B against the real model. This directory asks the same question deeper in the network: at layer 16 (last layer shared by the stock and abliterated checkpoints) and layer 20 (inside the abliterated range 17 to 51, on both checkpoints), with the arm family that varies the state precision. It also runs the whole 64-layer model in float64 on four short prompts with every DeltaNet layer's heads replaced by one integer arm, and compares the next-token predictions with the float model.

**Nothing here is proved.** No proof is built or verified. Every number is integer reference arithmetic compared with a float64 reference, on the CPU. The arms are numerical lowerings, not sound, proof-ready ones (PR #74 RESULTS section 8.2 applies to every arm here).

- **What the integer path computes:** `scaled_head.py` from PR #74 (unchanged): conv, SiLU, q/k L2 norm, gates, the delta-rule state update, the head output and the gated RMS norm, for all 48 V heads of one layer, with the scales and roundings of each arm.
- **What the float path computes:** a float64 forward of the whole model (`q1_forward.py`): embedding, DeltaNet layers (PR #68's in_proj split and `run_float`), gated full attention every 4th layer, SwiGLU MLP, zero-centred RMSNorm, final norm, lm_head, following the pinned `modeling_qwen3_5.py`. Its residual stream at layers 16 and 20 gives the head inputs (per-layer, open-loop measurements). A sanity check (the float model must predict " Tokyo" after prompt p01) guards the forward.
- **What a verifier would recompute:** not applicable, there is no proof.
- **Not covered:** in_proj, out_proj, attention, MLP and lm_head in integers (they stay float64 in every path); any proof; long-prompt or generated-text agreement end to end; layers other than 16 and 20 per layer; BF16 inference numerics beyond the head-level emulation.

No weight data is in the repo. Weights are read by HTTP range request into memory, one layer at a time; every fetched tensor's sha256 is in `runs/manifest-*.json`.

## Outcome (see RESULTS.md)

Measured, unreplicated, negative against the bar. No arm passes at layer 16 or layer 20 on either checkpoint. Medians are well under the bar from FS = 16 up, but the max fails on a few pairs, mostly from the repeated-word prompt. End to end on the stock checkpoint, XS18 keeps top-1 on 96 of 96 positions (descriptive). The abliterated end-to-end stage stopped at layer 45 and is **not finished**.

## Files

| file | what it does |
|---|---|
| `PREREG.md` | registration and amendments |
| `make_arms_q1.py`, `arms-q1.json` | the 14 arms; `check_arms.py` confirms the arms that reuse PR #74 configurations equal PR #74's `arms-r2.json` |
| `q1_forward.py` | streaming float64 forward (stages A, B, D, E), prep files for the targets, end-to-end paths and logit metrics; `fixture` / `fixture2` are the debug runs on a sequence outside the suite |
| `q1_arms.py` | runs `scaled_head.run` (PR #74, unchanged) on one target's prep files, with the target layer's out_proj for the residual measure |
| `run_q1.sh` | the registered run, one heavy slot, stop rule |
| `run_fixture.sh`, `run_fixture2.sh` | the two debug runs (output in `runs/debug-fixture/`) |
| `summarise_q1.py` | per-target tables, decay buckets, the state-precision rule, H1, U1 reading, end-to-end tables -> `runs/summary.json`, `runs/summary.md` |
| `peek_e2e.py` | prints the end-to-end, U1 and bucket parts of `runs/summary.json` and the last divergence rows (reading aid) |
| `scrub_time_paths.py` | replaced the scratch prefix in the `time -v` headers by `<SCRATCH>` before the run files were committed (`runs/scrub-time-paths.json`) |

## Reproduce

From this directory, with a scratch directory `$X` outside the repo (about 3 GB free), cores 0 to 5, Python 3.12 and numpy 2.4.3 (no torch needed), network access to huggingface.co:

```
python3 make_arms_q1.py && python3 check_arms.py
./run_fixture.sh $X/fixture && ./run_fixture2.sh $X/fixture      # debug only
./run_q1.sh $X                                                  # about 75 minutes on 6 cores of a shared EPYC VM
python3 summarise_q1.py $X > runs/summary.md
```

`run_q1.sh` writes to `runs/` and has a wall-clock stop rule (PREREG); remove its time checks to rerun at another time of day. Float fields depend on the BLAS thread count in the last bits (PR #74 section 1); the dense forward uses 6 threads, the arm workers 1.
