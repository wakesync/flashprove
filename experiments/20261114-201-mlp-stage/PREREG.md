# PREREG: 20261114-201-mlp-stage

Issue: #201 (part of #132 and #8). Lane: mlpstage201. Date (UTC): 2026-11-14T04:40Z (lane clock; the commit time is the record). Base commit: main `cdde96296e658fe803711dbb1b4699a225cc544a` (PR #200 merged). The files the issue cites at `47db5971` (`experiments/20261112-132-int-mlp-e2e/mlp_e2e.py`, `summarise_mlp.py`, `runs-resume150b/`, `experiments/20261111-8-qwen-e2e-agreement/e2e.py`, `experiments/20261112-148-norm-class/PREREG.md`) have no commit between `47db5971` and this base.

A new, separately registered diagnostic. It does not rerun, resume or amend PR #138 / PR #173, and it chooses no fix and no design.

## Question
PR #173's integer MLP fails PR #124's token bar (XM18 1,423 of 1,461 top-1, KL median 1.59e-3, max 1.92; FM, float heads with the integer MLP, fails the same way). Which numerical stage of the M3 MLP lowering carries that error in the late layers (31 to 63), where the SiLU saturations (181,964) and the h >= 2^18 entries (622) occur: the SiLU table (input step 2^-8, index clipped outside [-8, 8)) or the 13-bit per-tensor weight conversion?

## Setup (fixed now)
Start state: PR #167's layer-30 state, `ckpt.npz`, sha256 `22dff8b92107511838e50e4b26d6e91a2b55d09064711c638042c4c18fb80009` (recorded on main in `experiments/20261112-132-int-mlp-e2e/runs-resume164/` and `runs-resume150b/`). The lane re-hashes the file before use and records the hash; a missing file or a different hash means BLOCKED, reported, and nothing else runs. Layers 0 to 30 are never regenerated. Only the REF (float64) entries of the state are used: every path below starts from the REF residual entering layer 31. The state file is read-only; the lane works on a hashed copy in its own scratch.

Layers 31 to 63 of the abliterated checkpoint (`huihui-ai/Huihui-Qwen3.8-27B-abliterated` at PR #124's pinned revision), streamed per layer, no weight cache, then the abliterated final norm and lm_head. Prompts: PR #124's 10 frozen prompts (`experiments/20261111-8-qwen-e2e-agreement/prompts-e2e.json`, 1,461 positions), teacher-forced. In every path the DeltaNet heads, in_proj, out_proj, full attention, every RMSNorm (including the MLP pre-norm), final norm and lm_head are float64, as in PR #173's FM.

Paths:
- **REF**: float64 MLP (`q1_forward.mlp`, PR #88, unchanged).
- **M31 (control)**: PR #138's `mlp_int` (`experiments/20261112-132-int-mlp-e2e/mlp_e2e.py`, imported unchanged), with PR #138's in-place 13-bit weight conversion `to_int_inplace` (unchanged).
- **M31-S (exact SiLU)**: as M31, except s = RNE(2^12 * silu(gw / 2^12)) computed in float64 (silu(g) = g / (1 + exp(-g)), RNE = numpy rint, ties to even): no table step, no index clip. m, the integer weights, gw, u, h = floor(s u / 2^12) and out are computed by the same code as M31.
- **M31-W (float weights)**: as M31, except gate, up and down use the float64 weights instead of the 13-bit integers: acc = m . (2^e W_float), with e the same per-tensor exponent M31 uses (scaling by 2^e is exact), then the same floors gw = floor(acc_g / 2^e_g), u = floor(acc_u / 2^e_u), out = floor(acc_d / 2^e_d), the same SiLU table with the same clipped index and the same h floor. The 2^53 exactness guard does not apply to this path (its products are not integer); its magnitudes are logged.
- **M31#2**: a second, independent computation of M31 on p01-ordinary-short and p09-multilingual (determinism check).

Unit checks before the registered run, on synthetic arrays only, committed with their output before the run:
1. M31-S equals `mlp_int` bit for bit when every gw is a multiple of 2^4 and inside the table domain [-2^15, 2^15). (The table entry at index i is RNE(2^12 silu((i - 2048) / 256)) by its manifest; if float64 silu and the table's Q256 values disagree on some entry, the check reports which entries, and that disagreement is a finding, not a fix.)
2. M31-W equals `mlp_int` bit for bit when the float weights are already exact at their exponent (W_float = k / 2^e with integer |k| <= 4095).
Debug runs use only PR #88's fixture prompt ("The capital of Italy is", token ids 760 6511 314 14898 369, not in the suite) and synthetic arrays. No registered prompt is run, at any size, before the registered run.

## Hypothesis
- **H-S**: KL median of M31-S <= 0.5 x KL median of M31.
- **H-W**: KL median of M31-W <= 0.5 x KL median of M31.
(KL medians over all registered positions, each path vs REF.)

## Metric
PR #124's `logits_metrics` (`experiments/20261111-8-qwen-e2e-agreement/e2e.py`, unchanged), per path vs REF: top-1 agreement (count and fraction), KL(REF || path) in nats per position, median and max (also p99 and SD), and every top-1 flip with REF's top-1 margin (logit units) and its KL. Range counters per path and layer, as PR #173 counts them: SiLU domain exits (index below 0 or above 4095; saturated in M31 and M31-W, counted but not saturated in M31-S), h >= 2^18, h >= 2^23, m > 2,047, gw and u >= 2^18 and >= 2^23, max |acc_down|, max |out|. Per-layer residual relative L2 vs REF per path and prompt. Per-layer seconds, peak RSS (`/usr/bin/time -v`).

## Acceptance threshold
- H-S HOLDS if KLmed(M31-S) / KLmed(M31) <= 0.5, else DOES NOT HOLD. Same for H-W with M31-W.
- Each path is also reported against PR #124's bar (top-1 >= 99%, KL median <= 1e-4 nats, KL max <= 0.1 nats), descriptively, no verdict.
- Validity gates (a failure means "comparison invalid", not a scientific FAIL):
  - G1: REF top-1 list equals PR #173's committed `experiments/20261112-132-int-mlp-e2e/runs-resume150b/runs/e2e-abl.json` `ref_top1` on every prompt run.
  - G2: M31#2 equals M31 bit for bit: residual after every layer and the logit metrics on p01 and p09.
  - G3: no GuardError in M31 or M31-S (a path with a guard error on a prompt is reported dead on that prompt, and the hypotheses that use it are not evaluated).
- Descriptive only: M31 vs PR #173's whole-model FM (layers 0 to 63). If M31's KL median is far below FM's, most of the error comes from layers 0 to 30.

## Kill criterion
- Compute cap: 100 minutes from the moment the heavy gate grants the slot (logged), including the timing probe below. Hard stop for the job: 2026-11-14T06:45:00Z. Lane deadline 2026-11-14T07:00:00Z.
- RSS stop: process-tree RSS over 14 GB. Disk stop: free space under 21 GB. A watchdog polls every 2 s and signals only the lane's own Python pid (and its children).
- On any stop before the logits: the result is PARTIAL. Per-layer residual divergence of the layers done is reported, H-S and H-W are "not tested".
- Time rule (fixed now, applied by code in the same job, before the registered run): a timing probe runs every path once on a synthetic residual (512 tokens, numpy default_rng(0), not a registered prompt) through stock layer 0 (linear attention) and stock layer 3 (full attention), giving t_lin and t_full. projected_s(n_tok) = (n_tok / 512) x (24 x t_lin + 9 x t_full) + 150 (layers 31 to 63 have 24 linear and 9 full-attention layers; 150 s for logits and saving). available_s = min(6,000 - seconds since the grant, seconds to the hard stop). If projected_s(1,461) > available_s, the registered fallback runs instead: the six-prompt subset of issue #148 / PR #152 (`experiments/20261112-148-norm-class/PREREG.md`: p01-ordinary-short, p07-chat-ordinary, p08-chat-refusal, p09-multilingual, p04-repeat-punct, p03-repeat-word; 672 tokens), every path, M31#2 still on p01 and p09. Nothing else may change. If even projected_s(672) > available_s, the six-prompt run starts anyway and stops under the cap (PARTIAL). The probe's inputs, outputs and choice are logged in `runs/progress.log`.
- The heavy-slot wait counts against the lane deadline, not against the compute cap. If the slot is not granted in time to finish, the lane ships an honest partial.

## Runs
One registered run. The arithmetic is deterministic (float64 and integer-valued float64, fixed BLAS thread count, PR #124 and PR #173 showed bit-identical reruns); M31#2 is the determinism check. The registered spread is over prompts (n = 10, or 6 under the fallback) and positions (n = 1,461 or 672): median, SD, min, max, p99 per path. No seeds except the synthetic probe and unit-check inputs (default_rng(0)). Nothing is excluded. CPU only, cores 8-13 through `fp-heavy.sh` and `bigmem.lock`, OMP/OpenBLAS threads 6, head pool of 6 spawned workers with 1 BLAS thread (PR #124's `make_pool`). No GPU, no serving route, no spend.

## Prior art
- In-repo: PR #138 / PR #173 (integer MLP + XS18 end to end, FAIL; m class failure, saturations and h overflows counted, attribution "not separated"), PR #148 / PR #152 (norm class arms; arm W shows an open-loop MLP-part error of 0.00493 to 0.0217), PR #70 / M3 design (the lowering), PR #67 (pinned SiLU table), PR #124 (bar and harness).
- Quantization error attribution: per-operator and per-layer sensitivity analysis is standard in post-training quantization (e.g. HAWQ's Hessian-based sensitivity, ZeroQuant, LLM.int8()'s outlier-feature analysis, SmoothQuant's migration of activation outliers, which are concentrated in MLP inputs of large models). These swap one operator at a time to measure its contribution, as here.
- zkML: lookup-table non-linearities with bounded domains are the norm (zkLLM's tlookup, EZKL lookup tables, Jolt's lookup-centric design); out-of-domain handling (clamp vs range check) is a known source of error and of soundness obligations.
- New here: the swap-one-stage attribution on a real 27B hybrid model's late layers, under the exact M3 lowering and PR #124's token metric, from a hashed intermediate state.

## Out of scope
A clamp, scale or class change for m; layers 0 to 30; XS18 heads, integer attention or norms; the stock leg; any new SiLU table format or domain; any proof; any serving request; choosing a design.

## Amendments
(empty at registration)
