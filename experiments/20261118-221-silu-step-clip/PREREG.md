# PREREG: 20261118-221-silu-step-clip

Issue: #221. Lane: silu221. Written 2026-11-18, about 01:36Z by the lane clock. The commit time of this file is the record. Base commit: main `bb2bee6f172fb92805c3e89e5230f78b6914c166` (PR #223 merged).

This is a new diagnostic, registered on its own. It does not rerun, resume or amend PR #202, PR #138 or PR #173. It does not choose a repair, an operator or a design. The two arms are diagnostics, not candidate operators.

## Question
PR #202 (issue #201, `experiments/20261114-201-mlp-stage/`) found that swapping the SiLU table lookup for exact SiLU (arm M31-S) in abliterated layers 31 to 63 brings the KL median from 1.466e-3 to 1.83e-6 nats. That swap removed two things at once:
- the table's input step: gw is floored to the 2^4 grid before the lookup, so the table's input step is 2^-8;
- the index clip: gw outside [-2^15, 2^15), which is SiLU input outside [-8, 8), takes the table's end rows.

Its RESULTS.md says "The run does not separate the step from the clip". This run makes one change at a time, on the same layers, prompts and start state. Which of the two carries the token error?

## Setup (fixed now)
Checked from main at the base commit by the lane before writing this file:
- `experiments/20261114-201-mlp-stage/mlp_stage.py` (PR #202). Its harness, every non-MLP stage and `silu_exact` are reused unchanged.
- `experiments/20261112-132-int-mlp-e2e/mlp_e2e.py` (PR #138), `mlp_int` lines 108 to 131. Its integer stages are used unchanged. The lookup is `raw = floor(gw / 2^(FB-8)) + 2048` and `s = TS[clip(raw, 0, 4095)]`, with FB = 12. `TS` is the pinned table `research/operators/qwen_ops/tables/silu-f12.i64le` (PR #67).
- M31's committed KL median: `experiments/20261114-201-mlp-stage/runs/summary.json`, `cells.M31.kl.median` = 0.001465834035915492. RESULTS.md in the same directory gives it as 1.466e-3.

Start state: PR #167's layer-30 state `ckpt.npz`, sha256 `22dff8b92107511838e50e4b26d6e91a2b55d09064711c638042c4c18fb80009`. The lane checked it before writing this file: the hash matches, and the meta reads `{"leg": "abl", "next_layer": 31, "legs_done": [], "prompt_set": "full"}`. The job re-hashes the file and re-reads `next_layer` in process before the run starts. Missing, a different hash or `next_layer` other than 31 means BLOCKED, and nothing runs. Layers 0 to 30 are never regenerated. Only the REF entries of the state are used. The state file is read-only, and the job reads a hashed copy in the lane's own scratch.

Model and data: layers 31 to 63 of the abliterated checkpoint at PR #124's pinned revision, streamed per layer with no weight cache, then the abliterated final norm and lm_head. The prompts are PR #124's 10 frozen prompts (`experiments/20261111-8-qwen-e2e-agreement/prompts-e2e.json`, 1,461 positions), teacher-forced. In every path the DeltaNet heads, in_proj, out_proj, full attention, every RMSNorm, the final norm and lm_head are float64, exactly as in PR #202.

### Arms, exact integer definitions
In every integer arm, every line is identical to M31 (PR #138 `mlp_int` with the 13-bit weights from `to_int_inplace`) except the line that computes s from gw. Here gw is the integer-valued gate output, FB = 12, `D = [-2^15, 2^15)` is the table domain (the index `floor(gw / 16) + 2048` lies in [0, 4095] exactly when gw is in D), and `silu_exact(v) = rint(2^12 * silu(v / 2^12))` in float64 (numpy rint, ties to even; silu(g) = g / (1 + exp(-g))). This is PR #202's `silu_exact`, unchanged.

- **REF**: float64 MLP (PR #88 `q1_forward.mlp`), unchanged.
- **M31-C (clip only removed)**: for gw in D, `s = TS[floor(gw / 16) + 2048]`, exactly as M31. For gw outside D, `s = silu_exact(gw)` instead of the table's end rows.
- **M31-T (step only removed)**: `g' = clip(gw, -2^15, 2^15 - 1)`, then `s = silu_exact(g')`. Inside D this is exact SiLU with no 2^4 floor. Outside D it is held at the domain edge.
- **M31-C#2**: M31-C computed a second time, independently, on p01-ordinary-short and p09-multilingual. This is the determinism check.

M31 and M31-S are not rerun. They are the committed PR #202 values. The domain-exit counters are those of M31: n_lo = #(floor(gw/16) + 2048 < 0) and n_hi = #(> 4095). They are counted in every arm and are never used to change a value.

Notes, fixed now:
1. Because the table's rows equal `silu_exact` at their grid points (PR #202 unit check 1a: 4,096 of 4,096 rows), M31-T inside D differs from M31 only by the step.
2. Outside D on the high side, M31-T uses silu_exact(2^15 - 1), while M31 uses TS[4095] = silu_exact(2^15 - 16). On the low side both use silu_exact(-2^15). So M31-T's high edge value can differ from M31's end row by the last partial step. This follows the issue's definition and is not changed.

### Unit checks (issue milestone step 3), run and committed with their output before the registered run
On synthetic integer gw arrays only (numpy default_rng(0), covering inside D, both edges and outside D on both sides):
- U1: M31-C's s equals M31's s bit for bit for every gw in D, and equals M31-S's s bit for bit for every gw outside D.
- U2: M31-T's s equals M31-S's s bit for bit for every gw in D. For gw outside D it equals M31-S's s evaluated at clip(gw), so it differs from M31-S only through the clip.
- U3: U1 and U2 hold element by element on the real gw arrays that the arm functions see on PR #88's fixture prompt ("The capital of Italy is", token ids 760 6511 314 14898 369, not in the suite), with stock layers 0 and 3 and the stock lm_head, through a fixture command. The fixture runs REF, M31, M31-S, M31-C, M31-T and M31-C#2, and M31-C#2 must be bit-equal to M31-C there. The fixture's KL values are debug output only.
Debug runs use only that fixture prompt and synthetic arrays. No registered prompt is run, at any size, before the registered run. The summariser is committed before the heavy slot is requested.

## Hypothesis
- **H-C**: KLmed(M31-C) / 0.001465834035915492 <= 0.5. Removing only the clip at least halves M31's KL median.
- **H-T**: KLmed(M31-T) / 0.001465834035915492 <= 0.5. Removing only the step at least halves M31's KL median.

The denominator is M31's committed KL median from `experiments/20261114-201-mlp-stage/runs/summary.json`. KL medians are taken over all registered positions, each arm vs REF.

Registered readings of the four outcomes:
- H-C holds, H-T does not: the clip carries the token error. The step alone does not halve it.
- H-T holds, H-C does not: the step carries it. The clip alone does not halve it.
- Both hold: each change alone at least halves it. Neither one is the sole carrier at this threshold.
- Neither holds: neither change alone halves it. The step and the clip matter together along the trajectory, and a combined change would have to be tested directly. This interaction is itself the finding.

## Metric
PR #124's `logits_metrics` (`experiments/20261111-8-qwen-e2e-agreement/e2e.py`, unchanged), per arm vs REF:
- top-1 agreement (count and fraction);
- KL(REF || arm) in nats per position: median, max, p99 and SD;
- every top-1 flip, with REF's top-1 margin in logit units and its KL.

Also reported:
- range counters per arm and layer, as in PR #202: domain exits low and high, h >= 2^18, h >= 2^23, m > 2,047, gw and u >= 2^18 and >= 2^23, max |acc_down|, max |out|;
- per-layer residual relative L2 vs REF per arm and prompt;
- per-layer seconds and peak RSS (`/usr/bin/time -v`).

## Acceptance threshold
- H-C HOLDS if the ratio is <= 0.5, else DOES NOT HOLD. The same rule applies to H-T.
- Each arm is also compared with PR #124's bar (top-1 >= 99%, KL median <= 1e-4, KL max <= 0.1). This is descriptive only, with no verdict.
- Validity gates. A failure means "comparison invalid", not a FAIL.
  - G1: REF's top-1 list equals the committed `ref_top1` in `experiments/20261112-132-int-mlp-e2e/runs-resume150b/runs/e2e-abl.json` (PR #173) on every prompt run.
  - G2: M31-C#2 equals M31-C bit for bit: the residual after every layer, and the logit metrics on p01 and p09.
  - G3: no GuardError in M31-C or M31-T. A path with a guard error on a prompt is reported dead on that prompt, and its hypothesis is not evaluated.

## Kill criterion
- Compute cap: 100 minutes from the moment the heavy gate grants the slot. The grant time is logged by the job itself. The cap is computed from the grant, not from a wall-clock time fixed in advance, and it includes the timing probe.
- Hard stop for the job: 2026-11-18T03:30:00Z. Lane deadline: 2026-11-18T03:50:00Z.
- RSS stop: process-tree RSS over 14 GB. Disk stop: free space under 21 GB. A watchdog polls every 2 s and signals only the lane's own Python pid and its children.
- Any stop before the logits gives PARTIAL. The per-layer residual divergence of the layers done is reported, and H-C and H-T are "not tested".
- Time rule, applied by code in the same job before the registered run (the same rule as PR #202, with this run's paths):
  - A timing probe runs every path once on a synthetic residual (512 tokens, default_rng(0)) through stock layer 0 and stock layer 3, giving t_lin and t_full.
  - projected_s(n) = (n / 512) x (24 t_lin + 9 t_full) + 150.
  - available_s = min(6,000 - seconds since the grant, seconds to the hard stop).
  - If projected_s(1,461) > available_s, the registered six-prompt subset runs instead: p01, p07, p08, p09, p04 and p03 (672 positions), with every path. M31-C#2 still runs on p01 and p09.
  - If even projected_s(672) > available_s, the six-prompt run starts anyway and stops under the cap (PARTIAL).
- Heavy-slot wait counts against the lane deadline, not the compute cap. If the slot cannot be had in time, the lane ships an honest partial.
- Provider refusal or a flag on any step: the lane records it and stops.

## Runs
- One registered run. The arithmetic is deterministic: float64 and integer-valued float64, with fixed thread counts. M31-C#2 is the determinism check, so it stands in place of a spread over reruns. The spread reported is over prompts (n = 10) and positions (n = 1,461): median, SD, min, max and p99 per arm.
- Seeds: only the synthetic probe and unit-check inputs (default_rng(0)). Nothing is excluded.
- Hardware: CPU only, cores 8-13 through `fp-heavy.sh` and `bigmem.lock`. Run as in PR #202: OMP/OpenBLAS threads 6, with PR #124's head pool.
- No GPU, no Tinfoil or H200, no serving route, no attestation request, no spend.

## Prior art
- In-repo: PR #202 (exact SiLU at the M31 stage halves the KL median many times over; step and clip not separated), PR #138 / PR #173 (integer MLP end to end; domain exits counted), PR #67 (pinned SiLU table), PR #124 (bar and harness).
- Lookup non-linearities in zkML use bounded domains with a fixed input step: zkLLM's tlookup, EZKL's lookup tables, Jolt's lookup-centric design. Input resolution and out-of-domain handling (clamp, range check, a separate branch) are separate design axes with different proof costs.
- Quantization studies separate rounding error from clipping error, for example clipping-range calibration in PTQ (ACIQ, and percentile versus max calibration).
- New here: the step and the clip separated one at a time on a real 27B hybrid model's late layers, under the exact M3 lowering and PR #124's token metric, from a hashed intermediate state.

## Out of scope
Any admissible operator or proof; the m class (m is not clamped, as in PR #138); layers 0 to 30; the stock leg; XS18 heads; attention or decay changes; choosing a repair.

## Amendments
(empty at registration)
