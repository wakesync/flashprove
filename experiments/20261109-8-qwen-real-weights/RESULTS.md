# RESULTS: 20261109-8-qwen-real-weights

Issue #8 (fidelity), part of #32 (Qwen tracking) and #36 (model identity). PREREG: [PREREG.md](PREREG.md) (first commit a02fc72). Code and reproduce commands: [README.md](README.md). Raw data: `runs/`.

**Verdict against the pre-registration: FAIL.** The hypothesis had three parts. Two hold and one does not:

| item | registered threshold | result | verdict |
|---|---|---|---|
| A1 ranges at F = 12 | 480 / 480 (prompt, head) pairs per checkpoint: every M2 RNG class < 2^18, every exact limb in its interval, every public word in its class | **480 / 480** stock, **480 / 480** abliterated | **PASS** |
| A2 fidelity | some F in {12, 14, 16} with median rel_y <= 1e-2, max rel_y <= 5e-2, median rel_S <= 1e-2, max rel_S <= 5e-2 over 480 pairs | no F passes. Median rel_y 0.659 / 0.177 / 0.0494 at F = 12 / 14 / 16 (max 141 / 54.4 / 19.4) | **FAIL** |
| A3 abliteration at layer 0 | every layer-0 tensor and the embedding byte-identical | 9 / 9 layer-0 DeltaNet-path tensors, all 14 layer-0 tensors and the embedding identical; all 3,360 result rows identical across checkpoints | **PASS** |

In one sentence: on real layer-0 weights the M2 range bounds hold at F = 12, with less margin than the synthetic study showed. But the integer head output is far from the float model at every F that the 2^18 bounds allow. The state is close; the gated-norm output is not. None of the tested F = 12, 14, 16 meets both the range bounds and the fidelity threshold with the M2 lowering, on layer 0, on these 10 prompts (section 4). Other F values and other lowerings were not tested.

*Text revised after review (two independent reviews at 9b366632, linked in section 6, A-8). No number, script or run file changed.*

All numbers are measured, n as stated, unreplicated. Shared, loaded CPU host. Nothing here is a proof run.

## 1 Pinned inputs and coverage

- stock `Qwen/Qwen3.8-27B` at `37561816e66b5b9153b1b64c10968c18c1e6f4a0`. Its 18 shards have the same LFS sha256 as revision `1d4bf0f2`, the one the feasibility lane (#28) used.
- abliterated `huihui-ai/Huihui-Qwen3.8-27B-abliterated` at `739e3c5b89849f6c238ce1e5b70008612ae42cdd`.
- Neither checkpoint is gated. No token was used. Both are apache-2.0, and the LICENSE files are byte-identical. The tokenizer.json files are byte-identical too (sha256 0997f410...).
- Model card of the abliterated checkpoint: base_model Qwen/Qwen3.8-27B; "Only layers 18 to 51 have been ablated ... MTP and visual has not been modified". Method: abliteration, after Sumandora/remove-refusals-with-transformers.
- Data read:
  - both checkpoints streamed in full once for hashing, 55.56 GB each, nothing stored;
  - range-fetched to a scratch directory outside the repo: 170,987,968 bytes per checkpoint (9 layer-0 tensors and 209 embedding rows);
  - for Q5: 3 more matrices per checkpoint, 304,087,040 bytes each, held in memory only.
- Peak weight data on disk: 342 MB, the two layer-0 caches (budget 3 GB). Deleted at the end. Every range and sha256 is in `runs/fetch-*.json`.

## 2 Layout (Q1, from headers only), `runs/layout.json`

- 1,199 tensors, all BF16, 18 shards.
- **Both checkpoints have identical tensor names, dtypes, shapes, shard assignment and data offsets.**
- The abliterated headers are 24 to 32 bytes shorter: they have no `__metadata__: {"format": "pt"}`. So **all 18 shard files differ in sha256, including the shards whose tensors are all unchanged.** A shard file hash identifies that serialized file. It does not tell you whether two files hold the same weights, because header metadata changes the hash of files whose tensors are identical, and it does not show which tensors changed.
- 64 decoder layers:
  - **Gated DeltaNet**: every layer with i mod 4 != 3, 48 layers (0, 1, 2, 4, ..., 62);
  - **full attention**: 3, 7, 11, ..., 63, 16 layers.
- **Layer 0 is a DeltaNet layer.** The first DeltaNet layer reads the token embedding directly, so this lane needed no approximation of the layer input.
- Embedding: `model.language_model.embed_tokens.weight` [248320, 5120] BF16, shard 3, data offsets [0, 2542796800]. The untied `lm_head.weight` has the same shape (shard 18).
- Layer 0 (shard 1, `model.language_model.layers.0.`):

| tensor | shape | data offsets |
|---|---|---|
| input_layernorm.weight | [5120] | 0 - 10240 |
| linear_attn.A_log | [48] | 10240 - 10336 |
| linear_attn.conv1d.weight | [10240, 1, 4] | 10336 - 92256 |
| linear_attn.dt_bias | [48] | 92256 - 92352 |
| linear_attn.in_proj_a.weight | [48, 5120] | 92352 - 583872 |
| linear_attn.in_proj_b.weight | [48, 5120] | 583872 - 1075392 |
| linear_attn.in_proj_qkv.weight | [10240, 5120] | 1075392 - 105932992 |
| linear_attn.in_proj_z.weight | [6144, 5120] | 105932992 - 168847552 |
| linear_attn.norm.weight | [128] | 168847552 - 168847808 |
| linear_attn.out_proj.weight | [5120, 6144] | 168847808 - 231762368 |
| mlp.down_proj / gate_proj / up_proj | [5120, 17408] / [17408, 5120] / [17408, 5120] | 231762368 - 766536128 |
| post_attention_layernorm.weight | [5120] | 766536128 - 766546368 |

- **Shape check against M1 / M1b / M2: no mismatch.** All 12 per-layer shapes that DESIGN D1 and the references assume are what every layer has. These are D = 128, 48 V heads over 16 K heads, conv kernel 4 over 10,240 channels, in_proj_qkv 10,240 x 5,120, in_proj_z 6,144 x 5,120, in_proj_a/b 48 x 5,120, out_proj 5,120 x 6,144, and MLP 17,408.
- Channel layout used for a V head h: q channels (h div 3) x 128 + [0, 128), k channels 2048 + the same, v channels 4096 + h x 128 + [0, 128). V head h reads K head h div 3 (`repeat_interleave(3)`, modeling_qwen3_5.py L631-633). The conv taps run oldest to newest (`F.conv1d` with padding 3, then truncation).
- **What differs from the synthetic assumptions** is the values, not the shapes (`runs/weight-stats.json`, layer 0):
  - A = exp(A_log) is in [0.0038, 0.34]. The synthetic init was U(1, 16).
  - dt_bias is in [-5.7, 19.25]. The synthetic range was about [-6.9, -2.25].
  - As a result, the decay at in_proj_a = 0 has median 0.998. Real layer-0 heads remember far longer than the synthetic heads did.
  - Conv taps: |w| <= 0.512. 2.2% of them round to 0 at 2^12, and the relative tap rounding error is 0.21% at 2^12.
  - Gated-norm gain is in [0.785, 0.930] (synthetic: 1).
  - Embedding rows: max |x| 0.547, RMS 0.0147.

## 3 Stock versus abliterated, by tensor (Q2, Q5)

**Coverage: full.** All 1,199 tensors of both checkpoints were hashed per tensor while streaming, and no data was kept.
- Time: 290.0 s (stock) and 273.1 s (abliterated), n = 1 each, on a shared host and network.
- The whole-file sha256 computed in the same pass matched the Hub's LFS sha256 for 36 / 36 shards.
- The 18 tensors that were also range-fetched for Q3 hashed identically in both reads (18 / 18, two independent fetches).
- Raw data: `runs/stream-*.json`, `runs/diff.json`.

| | tensors | bytes |
|---|---|---|
| identical | **1,129** | 47,121,819,104 |
| different | **70** | 8,441,036,800 bytes in the 70 changed tensors (4,220,518,400 parameters, 15.2% of the checkpoint). This is the size of the changed tensors, not a count of unequal byte positions |

- **The 70 differing tensors are exactly 2 per layer, in the 35 layers 17 to 51 (0-indexed).** In each such layer:
  - `mlp.down_proj.weight`, plus
  - the mixer's output projection: `linear_attn.out_proj.weight` in the 26 DeltaNet layers, `self_attn.o_proj.weight` in the 9 attention layers.
- These are the matrices that write into the residual stream. No other family changed.
- Byte-identical: the embedding, lm_head, final norm, every tensor of layers 0 to 16 and 52 to 63, every norm, every DeltaNet gate, conv and in_proj tensor, MTP and the vision tower.
- The model card says "layers 18 to 51". The tensors say 0-indexed 17 to 51, which is 35 layers. One reading is that 18 is 1-indexed and 51 is 0-indexed. We report what the bytes say.

**What the change is, on a sample of 3 of the 70 changed tensors** (`runs/lowrank.json`). Three differing matrices were fetched from both checkpoints: layer 17 down_proj, layer 17 out_proj and layer 19 o_proj, the first of each family. Nothing below was measured on the other 67. For each of the 3, Delta = W_abl - W_stock:
- ||Delta|| / ||W|| = 1.9% to 2.1%. 77% to 78% of the entries changed.
- **Delta is close to rank-1: the top singular value carries 99.36% to 99.45% of its energy.** sigma_1 = 2.00, 1.88 and 1.78; sigma_2 is about 0.02. It is not exactly rank-1.
- **The top left singular vector r is the same direction in all three matrices: |cos| >= 0.9999985.** The vector lives in the 5,120-dim residual space.
- **The fit is W_abl ~= W_stock - alpha r r^T W_stock with alpha = 1.2995, 1.2999 and 1.2995**, not the plain projection alpha = 1.
  - Plain projection leaves 24% of ||Delta|| unexplained.
  - The scaled fit leaves 7.4% to 8.1%, which is the BF16 rounding level of W_abl (a half-ulp estimate gives 5.3% to 5.8%).
  - Rounded to BF16, the scaled fit reproduces 92.1% to 92.6% of the published entries exactly.
- So, on the 3 tensors checked, this abliteration is a scaled, close-to-rank-1 directional ablation of residual-writing matrices, with one direction r shared across them. It is not a fine-tune. The other 67 changed tensors were hashed, not analysed; that they have the same structure is an inference, not a measurement of this PR.
- Reviewers' numbers, not this PR's evidence: the two reviewers checked 5 more changed tensors with their own code and found the same structure, top-1 energy 99.2% to 99.5%, alpha about 1.299, shared direction. astra (n = 2: L18 out_proj 0.9943, L50 down_proj 0.9927, <https://github.com/wakesync/flashprove/pull/68#issuecomment-6756503458>) and opus (n = 3: L34 out_proj 0.9946, L51 o_proj 0.9924, L40 down_proj 0.9926, <https://github.com/wakesync/flashprove/pull/68#issuecomment-6757172391>). That makes 8 of 70 looked at by anyone. It is still a sample.

**Layer-0 behaviour (A3).** Layer 0 and the embedding are byte-identical, so the integer and float layer-0 computations must be identical across checkpoints. They were computed independently for both checkpoints and compared: **0 of 1,440 (registered), 0 of 960 (taps at 2^F) and 0 of 960 (q unscaled) result rows differ.** Every layer-0 number below therefore holds for both checkpoints. It says nothing about layers 17 to 51.

## 4 Fidelity and ranges on real layer-0 weights (Q3, Q4)

What was run, for each checkpoint, each of the 10 frozen prompts (2,396 tokens) and all 48 V heads of layer 0:
- the real embedding rows, the real zero-centred input RMSNorm and the real in_proj matrices, in float64;
- then the head, by the integer M2 contract and by a float64 twin, from sequence start.

The float64 twin was checked against the Transformers source itself (`runs/xcheck-torch.json`). `l2norm`, `causal_conv1d_fn`, `torch_recurrent_gated_delta_rule` and both RMSNorm forwards were taken verbatim from modeling_qwen3_5.py (e540ae45, sha256 verified) and run in torch float64. The two agree to rel_y <= 1e-6 on all 10 prompts.

The integer path is checked against the repo's reference (`runs/selfcheck-f12.json`). At F = 12, the lane's batched integer path (`real_head.py`) is **bit-identical to `head_reference.py` + `reference.step` on 20 / 20 synthetic runs** (20,480 tokens, every S, o and y).

Metrics (PREREG):
- rel_S: the relative Frobenius error of the final state;
- rel_o and rel_y: the relative error over all tokens of the head output o and of the gated-norm output y;
- "typical" is the median over the 48 heads, "worst" is the max over heads;
- n = 480 (prompt, head) pairs per F per checkpoint.

### 4.1 Summary over 480 pairs (identical for both checkpoints)

| F | rel_S median (min / max) | rel_o median (max) | rel_y median (min / max) | o-rounded + integer norm rel_y median (see 4.4 point 2) | pairs with every M2 class in contract |
|---|---|---|---|---|---|
| 12 | 0.0098 (0.0015 / 0.406) | 0.014 (9.69) | **0.659** (0.033 / 141) | 0.171 | **480 / 480** |
| 14 | 0.0042 (0.0006 / 0.104) | 0.0047 (2.44) | **0.177** (0.0086 / 54.4) | 0.046 | 198 / 480 (S, M over 2^18) |
| 16 | 0.0033 (0.0002 / 0.030) | 0.0028 (0.63) | **0.049** (0.0023 / 19.4) | 0.012 | 19 / 480 (S, M, o over 2^18; public ar and z over 2^20) |

Layer level: all 48 heads together, pooled into one relative error over the 6,144-wide y that out_proj reads (and, for rel_o, over the 6,144-wide o). out_proj reads y, not o. The gated norm rescales every head's o to unit RMS before the gain and the SiLU(z) gate, so a head with small o does not have small y and is not down-weighted in this pooled number or by out_proj. n = 10 prompts, median (min / max):

| F | rel_y | rel_o | o-rounded + integer norm rel_y |
|---|---|---|---|
| 12 | 1.12 (0.55 / 2.18) | 0.0056 (0.0037 / 0.042) | 0.093 |
| 14 | 0.295 (0.18 / 0.64) | 0.0026 | 0.058 |
| 16 | 0.068 (0.060 / 0.17) | 0.0021 | 0.024 |

Context, the publisher's own precision on the same path:
- BF16 eager, through the verbatim Transformers functions run in torch (`runs/xcheck-torch.json`), against float64: layer-level rel_y median 0.0030 (0.0025 / 0.0055), n = 10. Per head: median 0.0052, worst head 0.026.
- The lane's BF16-cast emulation in numpy (`runs/summary.json`, field `bf16_rel_y`) gives the same layer-level median (0.0030, min 0.0025, max 0.0054). The ledger value in `research/results.yaml` is this emulation number, not the torch run; it is named `bf16_emulation_layer_rel_y` there.
- The integer contract's error is about 23x (F = 16) to 370x (F = 12) the BF16 model's own error at layer level.

### 4.2 Per prompt (F = 12; tables for F = 14 and 16 in section 7)

| prompt | T | rel_S typ / worst | rel_y typ / worst | max S | max M | max delta | max o |
|---|---|---|---|---|---|---|---|
| p01 ordinary short | 13 | 0.0061 / 0.014 | 0.47 / 60.5 | 109,198 | 146,543 | 131,264 | 13,568 |
| p02 ordinary paragraph | 107 | 0.021 / 0.069 | 0.38 / 29.1 | 128,239 | 202,297 | 140,202 | 18,091 |
| p03 " the" x 512 | 512 | 0.0090 / 0.072 | 0.77 / 105 | 103,012 | 167,442 | 105,030 | 10,861 |
| p04 "!" x 512 | 64 | 0.024 / 0.111 | 0.41 / 141 | 27,265 | 42,972 | 32,278 | 2,502 |
| p05 code | 144 | 0.022 / 0.068 | 0.56 / 25.9 | 153,822 | 186,457 | 154,991 | 17,909 |
| p06 digits | 465 | 0.125 / 0.406 | 4.71 / 113 | 122,945 | 156,185 | 159,069 | 12,618 |
| p07 chat ordinary | 23 | 0.0078 / 0.018 | 0.62 / 23.6 | 123,835 | 150,940 | 134,325 | 13,111 |
| p08 chat refusal-style | 39 | 0.011 / 0.025 | 0.65 / 22.2 | 151,396 | 174,377 | 154,355 | 17,704 |
| p09 multilingual | 21 | 0.0084 / 0.018 | 0.30 / 12.1 | 120,266 | 113,415 | 107,394 | 10,385 |
| p10 long mixed | 1,008 | 0.048 / 0.287 | 1.19 / 29.7 | 175,232 | 202,297 | 154,991 | 23,630 |

The refusal-style prompt behaves like the other chat prompt. At layer 0 that is expected: the layer is identical in both checkpoints, and abliteration acts later.

### 4.3 Ranges (Q4) against the M2 contracts, all 480 pairs, F = 12

| class | contract | max on real weights | share of contract | synthetic H4 max (#66) |
|---|---|---|---|---|
| S' | < 2^18 | 175,232 | 0.67 | 150,189 |
| M | < 2^18 | **202,297** | **0.77** | 53,294 |
| delta (unsplit, M1 contract) | < 2^18 | 159,069 | 0.61 (fits unsplit; delta_hi max 1) | 282,387 |
| o | < 2^18 | 23,630 | 0.09 | 6,379 |
| w | <= 2^12 (provable) | 4,096 | 1.00 (at its provable bound, as designed) | 4,048 |
| xq, xk, xv (public) | < 2^31 | 277,776 | < 0.001 | 1,478,242 |
| ar / br (public) | < 2^20 | 94,041 / 31,661 | 0.09 / 0.03 | |
| z (public) | < 2^20 | 144,386 | 0.14 | |
| cg (public) | < 2^24 | 749,931 | 0.045 | 230,259 |
| y (public) | < 2^31 | 15,321 | | 101,976 |

- Exact limbs (e1, e2, rr, gap, and the w and y floor remainders): never negative, all inside their intervals, in 480 / 480 pairs at every F.
- Rc < 2^(3F) always.
- No int64 guard fired.

**Real M is 3.8x the synthetic maximum**, and has only 1.3x margin to 2^18. Real decays near 1 let the memory read grow.

Bits needed by F (signed, max over pairs):
- F = 12: M 19, S 19 (fits the 19-bit class);
- F = 14: M 21, S 21;
- F = 16: M 23, S 23, o 20.

At F = 16 the public in_proj outputs also exceed the DESIGN classes: ar reaches 1,504,655 and z reaches 2,310,181 against 2^20. **Each extra bit of F costs one bit of every range class**, and the 2^18 contract (16 x 2^18 = D = 2^22, RNG's completeness condition) holds only at F = 12.

### 4.4 Where the error comes from

1. **The head output o, and with it y, is small in absolute terms at layer 0.**
   - The float o RMS per token per head, in integer units at F = 12, has median 187 over the 480 pairs.
   - 134 of 480 pairs have a median o RMS below 16 integer units.
   - o is rounded to 2^-F before the norm. The gated norm then divides by o's RMS, so a fixed absolute resolution of 2^-F on o becomes a large relative error in y.
   - This does not make those heads unimportant. out_proj reads y, not o, and the norm has already rescaled y to ordinary size. Reviewer's number, not this PR's evidence (opus, n = 480 pairs at F = 12, <https://github.com/wakesync/flashprove/pull/68#issuecomment-6757172391>): 110 of 480 pairs have o RMS below 4 integer units, and their float y absmax still has median 0.167. Small-o heads enter out_proj at close to full weight.

   Median rel_y by the head's median o RMS in integer units (`runs/buckets.json`):

| o RMS (integer units) | F = 12: n, median rel_y | F = 16: n, median rel_y |
|---|---|---|
| < 16 | 134, 12.8 | 71, 1.20 |
| 16 to 128 | 80, 0.59 | 52, 0.61 |
| 128 to 1,024 | 245, 0.36 | 48, 0.093 |
| 1,024 to 8,192 | 21, 0.38 | 202, 0.028 |
| >= 8,192 | | 107, 0.022 |

2. **Rounding o to the grid, then the integer norm** (this arm was called "norm-only" in the first version of this file; the field in the run files is still `norm_only_rel_y`).
   - The arm takes the float64 o, rounds it to the 2^-F grid, applies the integer gated norm (DESIGN 4.4), and compares with the float y. So it measures the rounding of o plus the integer norm. It is not the norm alone, and it is not "a perfect o".
   - Its error is per-head median 0.171 / 0.046 / 0.012 (0.0120) at F = 12 / 14 / 16, a factor of 4 per 2 bits. **At F = 16 the median 0.0120 still fails the 0.01 threshold.**
   - Where the error comes from inside this arm. Reviewer's decomposition, not this PR's evidence (opus, own code, per-head median over n = 480 pairs, <https://github.com/wakesync/flashprove/pull/68#issuecomment-6757172391>): o rounded to the grid with an exact float norm gives 0.132 at F = 12 and 0.0087 at F = 16; the full integer norm gives 0.171 and 0.012. So most of this arm's error is the rounding of the small o, which the norm then scales back to full size. The floors on w and y add the rest.
   - Design implication: the accuracy is lost mainly when the small head output o is rounded to 2^-F before the norm. The next things to try are finer resolution or a per-head scale on o before the norm. Changing the norm lowering alone cannot recover that loss.
   - The registered localisation of this error is done by the `qwen-norm-scaling` lane. It is not part of this PR.
3. **Conv tap rounding (registered ablation) moves the state error but not y.**
   - At F = 16 with taps at 2^16 instead of 2^12, rel_S median falls 0.0033 to 0.00064, and rel_o falls 0.0028 to 0.00099.
   - rel_y stays at 0.048 (from 0.049), and the layer-level rel_y stays at 0.068.
   - At F = 12 the two arms are the same computation.
4. **The q 1/sqrt(128) scale (secondary, unregistered; head_reference's `q_unscaled` option).**
   - Dropping the scale makes o 11.3x larger in integer units.
   - Layer-level rel_y improves: 1.12 to 0.199 at F = 12, and 0.068 to 0.017 at F = 16.
   - Per-head median at F = 16 is 0.028, and the max stays at 23.6.
   - At F = 12 one pair puts o over 2^18 (267,312), so it does not fit the contract.
   - Still no A2 pass.

The worst pairs are heads with near-zero o on a prompt. For example, p04 head 36 has o RMS about 0.1 integer units at F = 12 and float y max 0.028. Rounding o to an absolute grid fails there. These heads are not negligible downstream: out_proj reads y, which the norm has rescaled, so they enter out_proj at close to full weight (point 1). The layer-level rows in 4.1 pool all heads over y, and they fail too, at every tested F (0.068 at F = 16 against 0.01).

## 5 Verdict

1. **Do the M2 range bounds hold on real weights?** At F = 12, **yes**: 480 / 480 pairs, both checkpoints, every RNG class, exact limb and public class (A1 PASS). The margin is thin for M (0.77 of 2^18) and was 4x larger in the synthetic study. At F = 14 and 16 they **do not** hold (198 / 480, 19 / 480).
2. **Which F is needed?** **None of 12, 14 or 16 meets the registered fidelity threshold** (A2 FAIL).
   - The state recurrence alone would pass the median at F = 12 and every rel_S criterion at F = 16 (max 0.030).
   - The gated-norm output fails at every tested F. Layer-0 o is small in absolute terms, it is rounded to 2^-F before the norm, and the norm scales that loss back up to full size (4.4).
   - Ranges hold at F = 12 only; F = 14 and F = 16 break them. Fidelity fails at F = 12, 14 and 16.
   - **What was tested: none of F = 12, 14, 16 meets both the range bounds and the fidelity threshold with the M2 lowering, on layer 0, on these 10 prompts.** No argument here covers other F values, other lowerings, other layers or wider cells.
   - Design input for M3: the accuracy is lost mainly when the small o is rounded to 2^-F before the norm (4.4 point 2). So the next things to try are finer resolution or a per-head (or per-token) scale on o before the norm. Changing the norm lowering alone cannot recover that loss. Wider range cells would cost a bigger RNG window.
   - Reviewer's descriptive number, not this PR's evidence (opus, n = 480 pairs and 10 prompts, <https://github.com/wakesync/flashprove/pull/68#issuecomment-6757172391>): a split scale, state at F = 12 and o plus the norm at 2^15, stayed inside every range (o max 189,042, 0.72 of 2^18) and reduced the error (layer-level rel_y 1.12 to 0.21, per-head median 0.31) without meeting the threshold.
3. **Does the abliterated checkpoint behave differently in a way that matters for the proof?**
   - At layer 0: no. It is byte-identical, and all outputs were identical (A3 PASS).
   - For the proof as a whole: **yes, in identity.** 70 tensors in layers 17 to 51 differ (full per-tensor hash coverage). On the 3 tensors checked, the change is close to rank-1 (top singular value 99.36% to 99.45% of the energy) and about 2% of the matrix's norm. A proof that commits to, or recomputes, only the layers this lane covered cannot tell the checkpoints apart.
   - Shard file hashes: a shard file hash identifies that serialized file. It does not tell you whether two files hold the same weights, because header metadata changes the hash of files whose tensors are identical (here every shard hash differs, even for shards whose tensors did not change), and it does not show which tensors changed.
   - Implication for #36: for weight identity that survives re-serialization, and for locating a change, commit per tensor (or per layer) over all 64 layers. On the sampled tensors the edit is cheap to describe (one 5,120-vector r and alpha), but a proof only sees it if it covers layers 17 to 51.
4. **Hypothesis**: false as registered (its fidelity half fails). The negative is the main deliverable.

## 6 Deviations from the pre-registration (Amendments)

- **A-1 (descriptive arms added after the first run, before any write-up).** Added: a norm-only arm (relabelled in A-8: it is o rounded to the grid, then the integer norm), the o-RMS buckets, layer-level aggregates, and the secondary `q_unscaled` arm (head_reference's own unregistered option). The full run was then repeated. All 6,720 per-head rows of the first run were reproduced exactly (`cmp_first.py`; the first-run copy was not kept). The registered metrics and thresholds did not change.
- **A-2 (cross-checks added).**
  - `xcheck_torch.py`: the verbatim Transformers functions in torch, float64 and BF16 eager.
  - `weight_stats.py`.
  - In `lowrank.py`: the scaled-projection fit (alpha). Q5 had only asked "low rank or not".
  - All descriptive.
- **A-3 (fetch method).**
  - The streaming diff used one whole-file GET per shard rather than range requests. It still stores nothing, and it also checks the LFS sha256.
  - Q5 range-fetched 3 extra matrices per checkpoint (0.61 GB in total, under budget).
- **A-4 (heavy-job rule).**
  - The registered runs (`run_all.sh`) went through `fp-heavy.sh`, pinned to 6 cores, with peak RSS 1.9 GB.
  - Run outside the gate: the streaming hash (single core, 47 MB RSS), `lowrank.py` and `xcheck_torch.py`. The last two ran on 4 cores (taskset 6-9) with several GB of RSS, at the edge of the heavy threshold.
  - The scratch venv with torch (CPU) was 1.1 GB, just over the 1 GB guideline. It is deleted.
- **A-5 (model card).** The card says "layers 18 to 51". The tensors say 17 to 51 (0-indexed). Reported as found.
- **A-6 (A2 evaluation).** A2 is evaluated on the registered per-head metric. Layer-level numbers are added for context and do not change the verdict.
- **A-7 (2026-11-10, code in the PREREG commit).** `prompts.py` was committed together with PREREG in `a02fc72`. It is the generator of the frozen prompt set: it reads the pinned tokenizer.json, reads no weights and computes no metric. `prompts.json` is in the same commit. No other code preceded or shared that commit. All measurement code first appears in `4a4db63`. This deviates from the letter of "PREREG before any code". `a02fc72` is not moved, split or rewritten. Raised by the opus review addendum, <https://github.com/wakesync/flashprove/pull/68#issuecomment-6757208533>.
- **A-8 (2026-11-10, text revised after review; disclosures).** Two independent reviews at `9b366632` (astra <https://github.com/wakesync/flashprove/pull/68#issuecomment-6756503458>, opus <https://github.com/wakesync/flashprove/pull/68#issuecomment-6757172391>) reproduced all 6,720 rows and found no bug, and asked for text changes only. This revision: corrects the out_proj explanation (it reads y, not o); relabels the "norm-only" arm as o rounded to the grid, then the integer norm, and changes the design advice drawn from it; scopes the global-F, rank-1 and file-hash statements to what was tested; renames the BF16 ledger metric to say it is an emulation. No number, script, metric, threshold, prompt or run file changed. Two process facts the reviews pointed out:
  - No fetch, stream or run record carries an absolute UTC timestamp (they record elapsed seconds). So "PREREG predates any fetch" rests on commit order alone (`a02fc72` 00:26:57Z, then `4a4db63` 01:16:54Z), not on the records.
  - The first-run copy used for the 6,720-row comparison in A-1 was not kept, so that comparison cannot be rerun (`cmp_first.py` reads the uncommitted `runs/first-run/`). Both reviewers' fresh reruns reproduced all 6,720 committed rows exactly. That does not retroactively prove the history of the first run.

## 7 Per-prompt tables at F = 14 and F = 16

F = 14 (pairs with an RNG class >= 2^18 out of 48):

| prompt | rel_S typ / worst | rel_y typ / worst | max S | max M | pairs over |
|---|---|---|---|---|---|
| p01 | 0.0032 / 0.0054 | 0.111 / 17.1 | 436,791 | 585,983 | 28 |
| p02 | 0.0068 / 0.018 | 0.091 / 7.2 | 512,758 | 809,362 | 36 |
| p03 | 0.0053 / 0.062 | 0.313 / 36.2 | 413,486 | 669,766 | 28 |
| p04 | 0.0097 / 0.038 | 0.143 / 36.5 | 109,091 | 171,896 | 0 |
| p05 | 0.0072 / 0.018 | 0.139 / 6.23 | 613,893 | 745,509 | 38 |
| p06 | 0.034 / 0.104 | 1.54 / 54.4 | 492,128 | 624,894 | 36 |
| p07 | 0.0037 / 0.0052 | 0.170 / 6.66 | 495,063 | 603,793 | 26 |
| p08 | 0.0042 / 0.0068 | 0.164 / 6.15 | 605,742 | 697,309 | 32 |
| p09 | 0.0036 / 0.0056 | 0.078 / 2.97 | 480,716 | 453,354 | 20 |
| p10 | 0.0135 / 0.073 | 0.300 / 6.74 | 698,396 | 809,362 | 38 |

F = 16:

| prompt | rel_S typ / worst | rel_y typ / worst | max S | max M | pairs over |
|---|---|---|---|---|---|
| p01 | 0.0026 / 0.0053 | 0.031 / 3.83 | 1,747,124 | 2,344,219 | 48 |
| p02 | 0.0038 / 0.0071 | 0.023 / 1.57 | 2,050,847 | 3,237,399 | 48 |
| p03 | 0.0036 / 0.024 | 0.108 / 15.7 | 1,655,009 | 2,679,123 | 48 |
| p04 | 0.0047 / 0.011 | 0.038 / 9.01 | 436,420 | 687,560 | 31 |
| p05 | 0.0037 / 0.0078 | 0.035 / 1.34 | 2,454,093 | 2,982,008 | 48 |
| p06 | 0.0097 / 0.030 | 0.415 / 19.4 | 1,968,861 | 2,499,600 | 48 |
| p07 | 0.0030 / 0.0048 | 0.040 / 1.55 | 1,979,965 | 2,415,465 | 48 |
| p08 | 0.0031 / 0.0055 | 0.042 / 1.47 | 2,423,024 | 2,789,012 | 48 |
| p09 | 0.0026 / 0.0052 | 0.020 / 0.741 | 1,922,685 | 1,813,554 | 46 |
| p10 | 0.0052 / 0.019 | 0.076 / 1.42 | 2,790,841 | 3,237,399 | 48 |

## 8 What this does not show

- **Layer 0 only.** Deeper DeltaNet layers read the residual stream after earlier layers, not raw embeddings. Their ranges and o magnitudes are unmeasured. Running them needs the earlier layers' weights, including the full-attention and MLP blocks.
- **The ablated layers (17 to 51) were not run.** Their behaviour under the integer contract is unmeasured.
- Sequence start only (S0 = 0, zero conv history). The longest prompt is 1,008 tokens.
- The gates, SiLU and L2 norm use float64 at the table points, as head_reference does. The tables that the build will use are not built.
- Fidelity is measured against float64, with a BF16 context arm. No FP8 reference.
- No proof run and no timing claim.
- The low-rank structure was checked on 3 of the 70 differing tensors by this PR (8 of 70 counting the reviewers' 5). The others are hashed only.
- Every abliterated layer (17 to 51) and every layer deeper than 0 is unmeasured for ranges and fidelity.
- The "o rounded to the grid, then integer norm" arm does not separate the rounding of o from the norm. Its decomposition here is the reviewer's, and the registered localisation belongs to the `qwen-norm-scaling` lane.

Raw files: `runs/layout.json`, `runs/diff.json`, `runs/stream-{stock,abl}.json`, `runs/fetch-{stock,abl}.json`, `runs/fetch-lowrank-{stock,abl}.json`, `runs/lowrank.json`, `runs/real-{stock,abl}{,-tapF,-qunscaled}.jsonl`, `runs/summary.json`, `runs/buckets.json`, `runs/selfcheck-f12.json`, `runs/xcheck-torch.json`, `runs/weight-stats.json`, `runs/*.time`.
