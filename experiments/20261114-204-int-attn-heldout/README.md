# 20261114-204-int-attn-heldout

Issue #204. Held-out check of PR #178's integer attention on Qwen3.8-27B abliterated. CPU only. Nothing is proved.

## What this measures, in plain language
PR #178 lowered the core of each full-attention layer (from rotated q, k, v to the head output o) to upstream's exact
integer arithmetic and fitted one power-of-two scale per layer for q, k and v, on the same 1,461 tokens it then measured.
Here those scales are frozen (copied from PR #178's `runs/layers.jsonl`) and the same arithmetic runs on eight new prompts
that nothing was fitted on. Two questions per arm (clamp 2,047 and clamp 1,665):
- **Range transfer (H_R):** does any q, k or v entry exceed the clamp at the frozen scale (it would be clamped), or does any
  arithmetic guard fail?
- **Fidelity (H_F):** does every layer still meet PR #88's per-head bar (median rel_y <= 0.01 and max <= 0.05 over
  8 prompts x 24 heads)?

Open loop: every arm sees the float64 reference stream's own input at each attention layer; nothing compounds. This is not
token agreement and says nothing about logits. Projections, input norm, q/k RMSNorm, partial rotary, gate and o_proj stay
float64. No verifier recomputes anything here; no proof is made.

## Files
- `PREREG.md`: registration (first commit, alone).
- `make_prompts.py`, `prompts-heldout.json`, `runs/prompt-check.json`: the frozen eight-prompt manifest, tokenizer pin,
  split hash, exact-match and near-duplicate check against PR #124's calibration prompts (second commit).
- `heldout.py`: frozen-scale evaluator and REF driver. Imports PR #178's `int_attn.py` unchanged (sha256-checked) and reads
  the scale table (sha256-checked, refuses missing / duplicate / extra rows or a wrong clamp).
- `test_heldout.py`: 32 unit tests on synthetic data (bit equality with `int_attn.arm_prompt` at in-run fitted scales; an
  evaluation outlier cannot change a frozen scale and is clamped and counted; table and summariser refusals).
  Output `runs/debug/unit-tests.json` (receipt of the reviewed head 27b057dd, kept unchanged). Since PREREG Amendment A1
  (2026-11-14) the file has 59 tests: the 32, plus 21 synthetic fail-closed tests and 6 on a temporary copy of the
  committed run records; that version wrote `runs/debug/unit-tests-a1.json` (kept unchanged). Since PREREG Amendment A2
  (2026-11-14) the file has 83 tests: the 59, plus 11 guarded-null tests, 6 synthetic descriptive-field tests and 7 on a
  temporary copy of the committed run records; it writes `runs/debug/unit-tests-a2.json`.
- `summarise_heldout.py`: validates every record (since Amendment A1 also strict types, finite non-negative values, T and
  denominators against the manifest, per-head count reconciliation; since Amendment A2 the evaluator's guarded nulls are
  admitted only where it writes them, descriptive fields are checked and reconciled, per-head counts are bounded by
  T x 256), then writes `runs/summary.json` and `runs/summary.md`.
- `watchdog.py`, `run_heldout.sh`, `run_fixture.sh`: stop rules (memory in decimal GB, kB x 1,024 / 10^9).
- `check_manifests.py`, `env.py`, `add_results_row.py`: tensor sha256 comparison with PR #124, ENV.json, the results.yaml entry.

## Reproduce
From the repository root, CPU, about 30 GB RAM host:
```
python3 experiments/20261114-204-int-attn-heldout/test_heldout.py
<venv with tokenizers 0.23.3>/bin/python experiments/20261114-204-int-attn-heldout/make_prompts.py <tokenizer.json sha256 0997f410...>
bash experiments/20261114-204-int-attn-heldout/run_fixture.sh <scratch>      # debug, fixture only
bash experiments/20261114-204-int-attn-heldout/run_heldout.sh <scratch>      # registered run, streams weights over HTTP
python3 experiments/20261114-204-int-attn-heldout/summarise_heldout.py
python3 experiments/20261114-204-int-attn-heldout/check_manifests.py
```
The registered run was launched as `flock <bigmem lock> fp-heavy.sh taskset -c 8-13 /usr/bin/time -v bash run_heldout.sh <scratch>`.
