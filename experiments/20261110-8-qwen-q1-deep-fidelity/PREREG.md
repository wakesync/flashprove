# PREREG: 20261110-8-qwen-q1-deep-fidelity
Issue: #8 (fidelity), part of #32 (Qwen tracking). Agenda question Q1, use case U1 (model substitution) first. Lane: q1-fidelity (CPU only; integer reference arithmetic against a float64 reference; no proof is built). Date (UTC): 2026-11-10T21:30Z (clock estimate; the commit time is the record). Base commit: 14bc10e395b248583509ae33da3e1ae65293bb6f (main).

This file is the first commit on the branch, before any code of this experiment and before any measurement. What was looked at before writing it: main at the base commit, in particular PR #68 (`experiments/20261109-8-qwen-real-weights/`, layer 0 negative) and PR #74 (`experiments/20261110-8-qwen-norm-scaling/`, norm scaling, exploratory, every candidate fails; X3 post hoc), their code, RESULTS and committed run files; the pinned `config.json` and `modeling_qwen3_5.py` (sha256 41a55adc..., the file PR #68 pins) of Qwen/Qwen3.8-27B@37561816; the tokenizer's vocabulary for the debug fixture below. No tensor of any layer other than 0 has been fetched or used in this lane, and no arithmetic on weights has been run in this lane.

## Why (use case)
U1 (model substitution) needs a proof that recomputes the model's integer lowering and a verifier that accepts only if the result is the claimed model's output. That only makes sense if an honest integer lowering stays close to the real model **past layer 0 and end to end**: if honest error is as large as the difference between two checkpoints, the proof cannot tell them apart in output terms. The stock and abliterated checkpoints differ only in layers 17 to 51 (PR #68, on main), so this lane measures one layer inside that range on both checkpoints. U2 and U3 depend on the same fidelity gate; this lane moves them only through that.

## Hypothesis
H1: arm X3 (PR #74's post-hoc arm: state at 2^18 with two-limb S' and M, q_hat at 2^20, cg at 2^16, per-token shift on o, bundle P, registered rounding) meets the acceptance bar below at **each** of the three targets T16 (stock layer 16), T20s (stock layer 20) and T20a (abliterated layer 20). Falsified if it misses the bar on any one target.

Secondary question, decided by the rule in "Acceptance threshold": the smallest state scale FS in {12, 14, 16, 18, 20} at which the slow-decay heads (defined below) meet the bar.

## Setup (fixed now)
- Checkpoints: Qwen/Qwen3.8-27B@37561816e66b5b9153b1b64c10968c18c1e6f4a0 (stock) and huihui-ai/Huihui-Qwen3.8-27B-abliterated@739e3c5b89849f6c238ce1e5b70008612ae42cdd (abl). Tensors are read by HTTP range request into memory (as PR #68's `fetch.py`), one layer at a time, sha256 of every fetched tensor recorded in a manifest; nothing is written to disk but small caches (prep files, hidden states) in a scratch dir outside the repo; no token.
- Prompts: PR #68's 10 frozen prompts (`experiments/20261109-8-qwen-real-weights/prompts.json`, 2,396 tokens), sequence start.
- Float reference forward: float64 numpy, Transformers semantics of the pinned `modeling_qwen3_5.py`: embedding, 64 decoder layers (zero-centred RMSNorm with (1 + w); Gated DeltaNet as PR #68's `inproj` / `heads` / `run_float`, then `out_proj`; gated full attention every 4th layer (layers 3, 7, ..., 63): q_proj split per head into query and gate, q_norm / k_norm, partial rotary (first 64 of 256 dims, theta 1e7, text positions so the three mrope sections coincide), GQA 24 / 4, causal softmax at 1/16, output times sigmoid(gate), o_proj; SwiGLU MLP), final norm, lm_head. Float64 throughout, no BF16 casts except where stated.
- Targets (the layer whose DeltaNet heads are lowered; the head inputs are the float64 reference residual stream at that layer, so these are open-loop, per-layer measurements):
  - **T16**: stock layer 16 (linear attention). Layers 0 to 16 are byte-identical between the checkpoints (PR #68, on main), so T16 holds for abl too by construction; it is not re-run on abl.
  - **T20s**: stock layer 20 (linear attention, inside 17 to 51).
  - **T20a**: abl layer 20, abl residual stream (layers 17 to 19 abl weights).
- Engine: `experiments/20261110-8-qwen-norm-scaling/scaled_head.py` on main, unchanged, driven through its `prep` file format (`NS_PREP`) and `run` (6 single-thread worker processes). The layer-0 `out_proj` it loads for the residual measure is replaced by the target layer's `out_proj` (set in its `_WO` cache before the workers fork; no code edit).

## Arms (fixed now; file `arms-q1.json`, written by `make_arms_q1.py` from these definitions)
All arms set `ext_stats`. "Registered rounding" = rnd = ornd = vrnd = shift_ornd = rhu (PR #74 A-4 r2). C4 = {Fw 16, Fy 20, Fo 24, RC 56}. G = gates at 2^18 (Fg 18). R = registered rounding. U = public stage finer (Fx, TAP, Fc 16; Fab, Fz 14). XB (X-family base) = C4P-style public stage and gates (G + U + R) with per-token shift o (omode shift, RC 46, Fw 16, Fy 20), q_hat at 2^20 (Fq 20), cg at 2^16 (Fcg 16), k_hat at 2^12 (Fk 12).
1. **C0**: M2 baseline (floor everywhere, F = 12).
2. **C4P**: C4 + G + R + U (PR #74's best registered arm, registered rounding).
3. **P taken apart on C4**: **C4+R**, **C4+U**, **C4+G**, **C4+RU** (= C4P without G, PR #74's cheapest arm with P's accuracy at layer 0).
4. **X3 family (state precision)**: XB with FS = 12, 14, 16, 18, 20 and least shift smin = FS - 10 (o scale at most 2^30 as in X3): **XS12**, **XS14**, **XS16**, **XS18** (= PR #74's X3-r2), **XS20**.
5. **X3 variants**: **XS18-K16** (XS18 with k_hat at 2^16, Fk 16); **XS18-noG** (XS18 with gates at 2^12); **XS18-noU** (XS18 with the public stage at 2^12: Fx, TAP, Fc, Fab, Fz 12).
14 arms x 3 targets x 10 prompts.

Stated honest classes (for "pairs in classes", as PR #74's `summarise.bounds`, with this extension): X-family S' and M at FS: |x| < 2^(FS + 7) (two limbs); o in [-2^17, 2^17), shift at most 24 (XS12: at most 24 too). C4-type: |Sigma| < 2^28. All public classes as DESIGN section 2. This is the honest-class check only, **not** a soundness check (PR #74 RESULTS 8.2 applies to every arm here).

## Slow-decay heads (definition fixed now)
For each target and V head h: d_h = median over the 10 prompts of (median over the prompt's tokens of 1 - a_t,h), with a_t,h = exp(-A_h softplus(ar_t,h + dt_bias_h)) in float64 from the target's float in_proj outputs. **Slow** = d_h < 2^-9 (8 integer units at 2^12, the regime PR #74 named); **fast** = the rest. Reported per bucket and arm: number of heads, rel_y and rel_S median / max over the bucket's pairs.

## Metric
Per arm and target, over the 480 (prompt, head) pairs: rel_y = ||y_int / 2^Fy - y_f|| / ||y_f|| per head over the prompt's tokens; rel_S = final-state relative error; median, min, max; pairs with rel_y <= 0.05; layer-level rel_y (n = 10); the mixer-output error over the residual norm through the target layer's out_proj (scaled_head's `resid`, descriptive); per-pair BF16-emulation context (`bf16_rel_y`); guard errors; range maxima and pairs within the stated honest classes.

**End to end (descriptive, no threshold).** Subset E = {p01, p07, p08, p09} (96 tokens; the four shortest non-repeated prompts, chosen for CPU time). Three closed-loop paths through all 64 layers: REF (float64); INT (every DeltaNet layer's heads, conv through gated norm, replaced by arm XS18 = X3-r2; in_proj, out_proj, attention, MLP, norms and lm_head stay float64); BF16H (every DeltaNet layer's heads replaced by PR #68's BF16-emulation `run_float(emulate_bf16=True)`, as context). Per position (96): top-1 agreement with REF, KL(REF || path) in nats, max |logit difference| over the vocabulary divided by the std of REF's logits at that position. Reported: agreement count, KL median and max, per prompt and pooled. Stock first; abl second (stage E below). If XS18 raises an OverflowError in any layer of a prompt, that prompt's INT path is reported as failed; there is no fallback arm. Feasibility on CPU: the dense parts stream 55 GB of weights once per checkpoint; the 96-token subset keeps the integer engine inside the time box. Long-prompt and generation-level (greedy continuation) agreement are not measured.

**Forward sanity check (registered).** REF's top-1 next token after p01 ("The capital of France is Paris, and the capital of Japan is") must be " Tokyo" (id 25358). If it is not, the forward is treated as broken: no target or end-to-end number is reported as a result, only the failure.

## Acceptance threshold
Per arm and target, PR #68's A2 bar (as PR #74): median rel_y <= 0.01, max rel_y <= 0.05, median rel_S <= 0.01, max rel_S <= 0.05 over the 480 pairs, no guard error, and 480 / 480 pairs inside the stated honest classes.
- **H1** holds if XS18 passes on T16, T20s and T20a.
- **Q1 answer per target**: the arms that pass, or "none passes" with the best arm's numbers (lowest median rel_y among arms inside their classes).
- **State precision for slow-decay heads**: the smallest FS in the X family whose **slow-bucket** pairs meet median rel_y <= 0.01, max rel_y <= 0.05, median rel_S <= 0.01, max rel_S <= 0.05 on every target where the slow bucket is non-empty, with no guard error. If no FS up to 20 does, the answer is "more than 2^20, or the limit is not the state scale", and the bucket numbers are reported.
- U1 reading (descriptive, no threshold): for T20, the stock-vs-abl difference of the float reference mixer output at layer 20 (||W_o,abl y_abl - W_o,stock y_stock|| over the residual norm, per prompt) next to the honest integer error of the best arm; and the end-to-end numbers. This says whether honest lowering error is small against the checkpoint difference, not whether a proof detects it.

## Kill criterion
- Lane hard stop 23:20Z (3 h from the restart at about 20:20Z). Compute hard stop 23:00Z: anything still running then is killed by pid and reported as not run.
- Run budget from the heavy-gate grant (the grant time is logged first by `run_q1.sh`): stages in order A (stock forward layers 0 to 20, all prompts; E-subset paths carried), B (abl layers 17 to 20 from the shared layer-16 output), C (arms on T16, T20s, T20a), D (stock end to end, layers 21 to 63 and logits on E), E (abl end to end). No new stage starts later than grant + 75 minutes, and stage C's arm groups follow scaled_head's own cut-off at the same time; stages not started are listed. These times do not move after registration.
- Forward sanity check fails: stop after stage D's check, report.
- Free disk under 3 GB or scratch over 6 GB: stop writing, report. RAM: the forward holds one layer of float64 weights (about 3.5 GB) plus hidden states (under 1 GB); if RSS passes 12 GB the run is stopped and the scope shrunk (reported).
- Gated or 401/403: stop, no credential search.

## Runs
Deterministic float64 and integer arithmetic, no seeds; one run per arm and target (a rerun is bit-identical up to BLAS thread count, PR #74 section 1; recorded in ENV.json). n = 480 pairs per arm per target. Heavy work through `fp-heavy.sh`, `taskset -c 0-5`, BLAS threads 6 in the dense forward, 1 per arm worker. No exclusions; guard errors are reported as error rows.

**Debug before the registered run (disclosed now).** New code is debugged only on a fixture the registered suite does not use: the token sequence "The capital of Italy is" ([760, 6511, 314, 14898, 369]), forward through layers 0 to 3 only (covers DeltaNet and one full-attention layer), plus every arm configuration run once on that fixture's layer-0 head inputs (guards, shapes), plus a bit-for-bit check that this lane's layer-0 head inputs equal PR #68's `inproj` / `heads` on the fixture. No registered prompt, layer 16 or 20 tensor, or lm_head is touched before the registered run.

## Prior art
In this repo: PR #68 (layer 0, M2 contract fails fidelity, abliteration localised to layers 17 to 51 out_proj / o_proj and down_proj), PR #74 (layer 0 norm and state scaling; round half up does the accuracy; X3 post hoc at median 0.0070 / max 0.281 under registered rounding). Outside: integer-only transformer inference (I-BERT, Kim et al. 2021), per-token / per-channel scales on real checkpoints (LLM.int8(), SmoothQuant), microscaling formats (OCP MX); zkML end-to-end LLM proofs (zkLLM, Sun et al. CCS 2024) report fidelity as perplexity or output agreement on whole models with fixed-point scales chosen per tensor; linear-attention / state-space quantisation work (e.g. Quamba for Mamba, 2024) reports that recurrent state and its decay are the precision-sensitive part. What is new here: the same honest-lowering arms measured at a mid-depth layer of a 27B Gated DeltaNet hybrid, on both a stock and an abliterated checkpoint, with a decay-stratified answer for the state scale, and a closed-loop end-to-end check of one arm on CPU.

## Amendments
(empty at registration)
