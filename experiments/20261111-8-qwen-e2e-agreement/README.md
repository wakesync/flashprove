# End-to-end token agreement of the XS18 / XS20 DeltaNet lowering, stock and abliterated (CPU, no proof)

Issue #8, part of #32. PREREG: [PREREG.md](PREREG.md) (first commit 436280e, alone). Results: [RESULTS.md](RESULTS.md). Builds on PR #68, PR #74 and PR #88 (all on main); their code is imported unchanged.

## What this is, in plain language

PR #88 found that the integer lowering of Qwen3.8-27B's Gated DeltaNet heads (arms XS18 and XS20) misses a strict per-head error bar at layers 16 and 20, on a few heads of the repeated-word prompt. Per-head error is a proxy. What matters for "a reply under proof" is whether the whole model, with the integer heads in every DeltaNet layer, still predicts the same tokens. This directory measures that, against a bar fixed in advance, on both the stock and the abliterated checkpoint, on 10 frozen prompts (1,461 positions).

**Nothing here is proved.** No proof is built or verified. The integer arms are numerical lowerings, not sound proof-ready relations (PR #74 RESULTS 8.2). Every number compares integer reference arithmetic with a float64 reference, on the CPU.

- **What is lowered:** only the DeltaNet head computation, in all 48 DeltaNet layers: conv, SiLU, q/k L2 norms, gates, the delta-rule state update, the head output and the gated RMS norm (`scaled_head.py`, PR #74, unchanged; arms `XS18` and `XS20` from PR #88's `arms-q1.json`).
- **What stays float64 in every path:** in_proj, out_proj, the 16 full-attention layers, every MLP, every RMSNorm, the final norm and lm_head.
- **What is compared:** teacher-forced next-token logits at every prompt position against the float64 reference forward (REF): top-1 agreement, KL(REF || arm) over the full 248,320-token vocabulary, max logit difference over REF's logit SD. A BF16-emulation path of the heads (BF16H, 5 prompts) is reported as a yardstick, without a bar.
- **What a verifier would recompute:** not applicable, there is no proof.
- **Not covered:** integer in_proj / out_proj / attention / MLP / lm_head; generated (free-running) text; prompts beyond the 10 frozen ones; long contexts beyond 512 tokens; any soundness or proof property.

No weight data is in the repo. Weights are read by HTTP range request into memory, one layer at a time; every fetched tensor's sha256 is in `runs/manifest-*.json` and is checked against PR #88's and PR #68's committed hashes (`runs/manifest-check.json`).

## Files

| file | what it does |
|---|---|
| `PREREG.md` | registration and amendments |
| `make_prompts_e2e.py`, `prompts-e2e.json` | the frozen prompt set (9 from PR #68 by id, one new chat prompt p11 tokenised with the pinned tokenizer) |
| `e2e.py` | the run: all paths through all 64 layers, per-layer checkpoint and resume, streaming lm_head metrics; `fixture` = the debug run on a sequence outside the suite |
| `run_e2e.sh` | the registered run under its hard stop (run through `fp-heavy.sh`) |
| `summarise.py` | the bar, per-prompt tables, flips, the closed-loop per-head error log -> `runs/summary.json`, `runs/summary.md` |
| `check_manifests.py` | sha256 cross-check of the fetched tensors -> `runs/manifest-check.json` |
| `env.py` | writes `ENV.json` |
| `add_results_row.py` | inserts the `research/results.yaml` row |

## Reproduce

From this directory, with a scratch directory `$X` outside the repo (about 1 GB free), cores 0 to 5, Python 3.12 and numpy 2.4.3 (no torch), network access to huggingface.co:

```
python3 make_prompts_e2e.py <tokenizer.json> prompts-e2e.json   # needs `tokenizers`; asserts the registered ids sha256
python3 e2e.py fixture $X/fixture $X/fixture.json                # debug only, not a suite prompt
fp-heavy.sh bash run_e2e.sh $X                                   # about 2 h on 6 cores of a shared EPYC VM; resumes from $X/ckpt.npz
python3 summarise.py
python3 check_manifests.py
```

`run_e2e.sh` has a registered wall-clock stop (PREREG); edit its cap to rerun at another time. Float fields depend on the BLAS thread count in the last bits (PR #74 section 1); the dense forward uses 6 threads, the head workers 1.
