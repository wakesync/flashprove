# Integer lowering of the Qwen head output and norm on real layer-0 weights (CPU, no proof)

Issue #8, part of #32. PREREG: [PREREG.md](PREREG.md) (first commit 694dcd2, amendments A-1 to A-3). Results and verdict: [RESULTS.md](RESULTS.md). Stacked on PR #68 (`experiments/20261109-8-qwen-real-weights/`), whose fetch code, prompts, pins and float reference are reused unchanged.

## What this is, in plain language

PR #68 measured the first layer of the real Qwen3.8-27B checkpoint against the integer arithmetic the M2 design specifies. The number ranges held, but the integer answer was far from the real model's answer. This directory asks whether a different way of writing the same computation in integers gets close to the real model while every number still fits a range a proof can check.

**Nothing here is proved.** No proof is built or verified. Every number is integer reference arithmetic compared with a float64 reference, on the CPU.

- **What the integer path computes:** `scaled_head.py`, a generalised version of the M2 head (`research/operators/qwen_deltanet_m2/head_reference.py`) in which every scale is a parameter and every rounding step can be switched to exact. In the M2 configuration it is checked bit for bit against PR #68's `IntHead` on the real inputs (`check`), and with every rounding switched off it is checked against PR #68's float64 reference.
- **What the float path computes:** PR #68's `run_float` (float64 Transformers semantics, sequence start), unchanged.
- **What a verifier would recompute:** not applicable, there is no proof. In the M2 design the conv, SiLU, q/k L2 norm and the gates are verifier-recomputed from public integers. Changing their scales changes verifier work and coefficient sizes, not the witness.
- **Not covered:** any layer but 0, the ablated layers 17 to 51, attention and MLP blocks, built lookup tables, any proof, FP8. Costs are counted by the repo's counting model, not built.

No weight data is in the repo.

## Files

| file | what it does |
|---|---|
| `PREREG.md` | registration and amendments |
| `prelook.py` | the read-only summary of PR #68's committed rows that was looked at before the PREREG |
| `fetch_all.sh` | PR #68's `fetch.py` for both checkpoints, plus layer-0 `out_proj` (for the residual-stream measure) |
| `repro_check.py`, `repro_diff.py` | step 1: fetch manifests and F = 12 rows against PR #68's committed files; per-field diagnosis of a mismatch |
| `repro_run.sh`, `run_lane.sh` | step 1, first attempt (my thread setting; did not match exactly, see RESULTS section 1) |
| `repro_run2.sh` | step 1, second attempt: PR #68's own command line; caches the in_proj outputs on a match |
| `blas_threads_test.sh`, `blas_threads_test.py`, `blas_threads_cmp.py` | shows that the in_proj float64 outputs depend on the BLAS thread count |
| `scaled_head.py` | the generalised integer head: `check`, `prep`, `run` |
| `make_arms.py`, `arms-cand.json`, `arms-local.json` | the arm definitions (candidates; localisation) |
| `unit_smoke.py` | code test of every arm configuration on synthetic inputs (no result number) |
| `pipeline.sh` | engine check, candidate arms, abliterated identity rerun, localisation arms, mechanism numbers |
| `summarise.py`, `pick_final.py`, `cmp_ckpt.py` | tables, the verdict arm by the registered rule, stock versus abliterated rows |
| `count_cost.py` | counted (not built) cost of each candidate against M2 arm B of `count_model.py` |
| `diag_mech.py` | mechanism numbers for the localisation (decay, q_hat, o sizes) |

## Reproduce

Requirements: Python 3.12, numpy 2.4.3, x86-64 (the engine uses 80-bit long double for exact integer products below 2^63). Network access to huggingface.co, no token. About 1.6 GB of scratch disk, about 2 GB of RAM per process.

```
cd experiments/20261110-8-qwen-norm-scaling
X=/path/to/scratch            # outside the repo; delete when done
C=$X/cache

./fetch_all.sh $C                                  # 224 MB per checkpoint
python3 repro_check.py fetch                       # every sha256 equal to PR #68's manifests

# step 1: PR #68's registered arm at F = 12, its own command line (6 cores, BLAS thread variables unset).
# On a match this continues into pipeline.sh.
./repro_run2.sh $C                                 # writes runs/repro.done or runs/STOP
./pipeline.sh $C $X                                # if run separately; needs runs/repro.done

python3 make_arms.py                               # regenerates arms-*.json (committed)
python3 unit_smoke.py                              # code test, no weights
python3 count_cost.py                              # runs/cost.json
```

`repro_run2.sh` must run with 6 cores and no `OPENBLAS_NUM_THREADS`: PR #68's float fields are bit-reproducible only at its BLAS thread count (RESULTS section 1).

## Not claimed

- No fidelity or range claim for any layer but 0, and none for inputs other than these 10 prompts from sequence start.
- No proof, timing or security claim. Costs are counted, not built.
- Post-registration arms (X1 to X3) are not passes even where they meet the thresholds; they need held-out prompts.
- Proposed claims are listed in the PR body. None is added to `loop/claims.json`.
