# Integer attention on Qwen3.8-27B's 16 full-attention layers, clamps 2,047 and 1,665, open loop (CPU, no proof)

Issue #176 (part of #8, informs #35 and #32). PREREG: [PREREG.md](PREREG.md) (first commit cc31ae3, alone). Results: [RESULTS.md](RESULTS.md). Builds on PR #68, #74, #88 and #124 (all on main); their code is imported unchanged.

## What this is, in plain language

Every Qwen fidelity number on main so far kept the 16 full-attention layers in float64. This directory runs upstream's integer attention arithmetic (`docs/model.md` section 6) on those layers of the abliterated checkpoint, on real activations from PR #124's 10 frozen prompts (1,461 tokens), and compares each head's output with float64. Two clamps: 2,047 (upstream's, which the attention sub-proof's no-wrap check N4 refuses at Qwen's head size 256) and 1,665 (the largest that N4 admits at every admitted C; the arithmetic is in PREREG).

**Nothing here is proved.** No proof is built or verified, no verifier is changed. Every number compares integer reference arithmetic with a float64 reference, on the CPU.

- **What is lowered:** from the rotated q (with 1/sqrt(256) = 1/16 folded in), k and v to the head output o: power-of-two scales fitted per layer, round half to even, clamp, integer scores, max-subtracted shift by sh, the softmax table EX (expS 12, rx 8), Z, acc and o by floor division (`docs/model.md` 6 steps 2 clamp only, 3, 4).
- **What stays float64:** input RMSNorm, q/k/v projections, q/k RMSNorm, partial rotary, the sigmoid output gate, o_proj, every DeltaNet layer, every MLP.
- **Open loop:** a float64 reference stream (REF) runs all layers; each attention layer's arms start from REF's input to that layer, so no arm's error carries into a later layer.
- **What is compared:** per (prompt, layer, head), rel_y = ||o_arm - o_float|| / ||o_float|| over the prompt's tokens x 256 dims. Bar (PR #88's A2, rel_y part): per layer median <= 0.01 and max <= 0.05 over 240 (prompt, head) pairs, on all 16 layers.
- **What a verifier would recompute:** not applicable, there is no proof.
- **Not covered:** closed loop, tokens or logits; the stock checkpoint beyond layers 0 to 16 (byte-identical); integer projections, q/k norm, rotary, gate, o_proj; any verifier change (passing N4 is not admission: dq != d, partial rotary, theta0 and dh > 128 still stand); scales fitted out of sample (the scales here are fitted on the same data they are measured on).

No weight data is in the repo. Weights are read by HTTP range request into memory, one layer at a time; every fetched tensor's sha256 is in `runs/manifest-*.json` and is checked against PR #124's committed manifests (`runs/manifest-check.json`).

## Files

| file | what it does |
|---|---|
| `PREREG.md` | registration and amendments |
| `int_attn.py` | the run (`run`), the debug fixture (`fixture`), the synthetic checks (`synth`) |
| `watchdog.py` | stop rules: logs the slot grant, kills the job by pid at the RSS limit, the elapsed budget or the hard stop |
| `run_fixture.sh`, `run_attn.sh` | the debug fixture and the registered run under the watchdog |
| `summarise.py` | the bar -> `runs/summary.json`, `runs/summary.md` |
| `check_manifests.py` | sha256 cross-check -> `runs/manifest-check.json` |
| `scrub_paths.py` | replaces host paths in run logs with placeholders before commit |
| `env.py` | writes `ENV.json` |
| `add_results_row.py` | inserts the `research/results.yaml` row |
| `runs/` | raw output: `cells.jsonl` (one row per arm, layer, prompt, head), `prompt-rows.jsonl`, `layers.jsonl`, `attn-timing.jsonl`, `progress.log`, `run.time`, manifests; `debug-fixture/` and `debug/` hold debug outputs, not results |

## Reproduce

From the repo root, with a scratch directory `$X` outside the repo (about 1.2 GB free), Python 3.12, numpy 2.4.3 (no torch), network access to huggingface.co:

```
python3 experiments/20261113-176-qwen-int-attn/int_attn.py synth $X/synthetic.json      # no weights; integer core vs a Python-int reference
bash experiments/20261113-176-qwen-int-attn/run_fixture.sh $X                            # debug fixture, about 1 min
bash experiments/20261113-176-qwen-int-attn/run_attn.sh $X                               # registered run, about 30 min on 6 cores of a shared EPYC VM
python3 experiments/20261113-176-qwen-int-attn/summarise.py
python3 experiments/20261113-176-qwen-int-attn/check_manifests.py
```

On the host used, both shell scripts were run under the host's big-memory lock and two-slot heavy gate, pinned with `taskset -c 10-15`, inside `/usr/bin/time -v`. The arithmetic is deterministic: a rerun gives the same numbers (checked once per layer by computing arm C2047 twice on p01 and p09).
