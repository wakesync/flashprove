# FlashProve port feasibility: Qwen3.8-27B

Status: **desk feasibility only**. No build, no proof, no GPU, no weights downloaded (config, index,
model card and the JSON headers of the 18 shards only). Pre-registration, runs and env manifest:
[experiments/20261103-11-qwen38-27b-feasibility/](../../../experiments/20261103-11-qwen38-27b-feasibility/)
(PREREG committed before any script). Issue #11. Base: `ae70e447b57f0f466c5012c88c9e41bf5a9d5712`.

**Verdict.** Qwen3.8-27B is the best *first* real-model port of the three candidates (Qwen3.8-27B,
GLM-5.3-Flash, DeepSeek-V4.1-Flash): it is dense (no routing), its committed integer weights are 6.7 %
of the Maverick shape FlashProve already proves, and it needs 7 new operator families against 11 for
GLM and 12 for DeepSeek. It is **not** a loader patch. Three quarters of its layers are Gated DeltaNet
linear attention, a recurrent state that FlashProve has no relation for; that one family is the
whole risk, and it is the same core risk as GLM's Kimi Delta Attention (Qwen's is the simpler,
scalar-decay case). Pre-registered threshold: **PASS**
([RESULTS.md](../../../experiments/20261103-11-qwen38-27b-feasibility/RESULTS.md)).

## 1. Exact architecture (from the publisher config)

Sources, all pinned:

- Model repo `Qwen/Qwen3.8-27B`, revision `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`
  (ungated, Apache-2.0, last modified 2026-08-14).
- Config: <https://huggingface.co/Qwen/Qwen3.8-27B/blob/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/config.json>
  (SHA-256 `191e0af2…0be550e`, copy in `experiments/…/sources/`).
- Model card: <https://huggingface.co/Qwen/Qwen3.8-27B/blob/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/README.md>
  ("Model Overview", lines 30-53).
- Reference implementation: Transformers `src/transformers/models/qwen3_5/modeling_qwen3_5.py` at
  commit `e540ae4528889920ce36955d1527036cca9b4ca5` (SHA-256 `41a55adc…c00dc6d8`). The config's
  `model_type` is `qwen3_5` / `Qwen3_5ForConditionalGeneration`: Qwen3.8 reuses the Qwen3.5 code path.
  Line numbers below refer to this file. It is the reference, not the publisher's serving kernels
  (FLA / causal-conv1d); their equivalence is not checked here.

| property | value | source |
|---|---|---|
| dense or MoE | **dense**. Every layer has one SwiGLU MLP; no router, no experts in config or tensors | config `text_config`; tensor names (`mlp.{gate,up,down}_proj` only) |
| layers | 64 | `num_hidden_layers` |
| layer pattern | 16 x (3 Gated DeltaNet + 1 full attention); full attention at l mod 4 = 3 | `layer_types`, `full_attention_interval: 4`; card "Hidden Layout" |
| hidden size d | 5,120 | `hidden_size` |
| vocab | 248,320 (padded); embedding and head **untied** | `vocab_size`, `tie_word_embeddings: false` |
| context | 262,144 native; up to 1M with YaRN override (not in the config) | `max_position_embeddings`; card lines 53, 514-558 |
| **full attention (16 layers)** | GQA, 24 query heads, 4 KV heads (ratio 6), head dim 256, so dq = 6,144 != d | `num_attention_heads`, `num_key_value_heads`, `head_dim` |
| QK-norm | yes: per-head RMSNorm on q and k (dim 256), zero-centred gain `1 + w` | L760-761, L828-845 |
| output gate | yes: q_proj emits 2 x 6,144; second half is a gate, `out * sigmoid(gate)` before o_proj | `attn_output_gate: true`; L774-777, L805 |
| RoPE | partial: 64 of 256 dims (`partial_rotary_factor 0.25`), theta 10,000,000, `rotate_half` layout, interleaved M-RoPE sections [11,11,10]. For text-only input the three position streams are equal, so it reduces to 1-D RoPE | `rope_parameters`; L135-201, L661-697, L1240-1260 |
| sliding window | **none** (no `sliding_window` key; full causal) | config |
| **Gated DeltaNet (48 layers)** | 16 QK heads, 48 V heads (q/k repeated x3), head dims 128/128; state per V head 128 x 128 | `linear_*` keys; L490-525, L599-611 |
| DeltaNet input path | `in_proj_qkv` (10,240) -> causal depthwise conv1d, kernel 4, no bias -> SiLU -> split q,k,v | L555-597, L256-276 |
| DeltaNet gates | `beta = sigmoid(in_proj_b x)`; `g = -exp(A_log) * softplus(in_proj_a x + dt_bias)`, scalar per head per token; state decays by `exp(g)` | L605-607 |
| DeltaNet q/k | L2-normalised per head (`use_qk_l2norm_in_kernel=True`), q scaled by 1/sqrt(128) | L280-283, L329-334, L449-455 |
| DeltaNet recurrence | `S <- S * exp(g_t)`; `delta = beta_t (v_t - S^T k_t)`; `S <- S + k_t delta^T`; `o_t = S^T q_t` (FP32 state) | L466-478 (recurrent), L287-421 (chunked, chunk 64, triangular solve) |
| DeltaNet output | gated RMSNorm per head (dim 128): `RMSNorm(o) * w * SiLU(z)`, `z = in_proj_z x` (6,144), then out_proj 6,144 -> 5,120 | L204-220, L641-645 |
| MLP | SwiGLU, intermediate 17,408, SiLU | `intermediate_size`, `hidden_act`; L811-825 |
| norm | pre-norm RMSNorm, eps 1e-6, zero-centred gain `x * (1 + w)` | L828-845, L848-900 |
| extras outside a text port | 1 MTP layer (424.7M params); 27-layer ViT (460.7M params) | config; tensor names |
| weights dtype | BF16, all 1,199 tensors | shard headers |

## 2. Op-by-op diff against what FlashProve proves (Llama 4 Maverick integer model)

Reference for "already proved": [docs/model.md](../../../docs/model.md) sections 5-8 and the
standard parameter form in [verifier/docs/parameter-file.md](../../../verifier/docs/parameter-file.md).

| Qwen3.8-27B op | FlashProve today | class |
|---|---|---|
| token embedding, untied output head, final RMSNorm, greedy argmax / logit gap | same (section 8; Emb and Wh are separate) | **supported** (V = 248,320 passes `prover-only-V`: 6 one-bits) |
| pre-norm RMSNorm with gain `1 + w` | section 5 norm without gains; gains folded into the next matrix (section 11.3). `1 + w` folds the same way | **supported** |
| SwiGLU MLP, f = 17,408 | dense layer of section 7 (SiLU table Ts, s*u, down projection) | **supported** (17,408 = 2 one-bits, < 2^16) |
| no MoE in any layer (NE = 0) | model.md defines NE = 0, but the standard form requires `routed-experts` (NE > 0) and the Lean model fixes Maverick's dense/MoE alternation | **parameter / policy change** |
| GQA full causal softmax attention, ratio 6 | section 6 step 4 (EX table, rounded division) | **supported op**; shape needs `H*dh = d` relaxed (24 x 256 = 6,144 != 5,120) and `dh <= 128` relaxed to 256 in the standard form |
| attention scale 1/sqrt(256) | folded into Wq (section 6) | **changes**: q_norm sits between Wq and the scores, so the scale must go into the q_norm gain or the shift |
| partial RoPE, 64/256 dims, theta 1e7, rotate_half layout | per-layer `rp` all-or-nothing, pairs (2i, 2i+1), theta in {1e4, 5e5}, tie analysis only for those | **new constraint (light)**: per-channel rotary mask; layout is a fixed permutation of Wq/Wk columns; new rotary table + rerun `scales/tests/table_ties.py` at theta 1e7, dh 256 |
| q/k per-head RMSNorm with gain (full attn); q/k per-head L2 norm (DeltaNet) | the only norm is over the d-wide stream, gainless | **new constraint**: per-head isqrt norm (same isqrt / rounding machinery, new placement), with a per-channel gain that cannot be folded (RoPE follows) |
| sigmoid output gate on attention; SiLU(z) gated RMSNorm on DeltaNet output | Sig table exists (router only); s*u product exists (FFN only) | **new constraint (moderate)**: activation x activation product on a mixer output, lookups at new places |
| causal depthwise conv1d, kernel 4, + SiLU on q,k,v | no cross-position op except attention | **new constraint**: per-channel 4-tap filter over positions t-3..t with zero left padding |
| decay gate `exp(-exp(A_log) softplus(a + dt_bias))`, beta `sigmoid(b)` | no softplus / exp-of-softplus table; Sig exists | **new table**: per-head constant `exp(A_log)` folds into a scale; needs a fixed-point table for `exp(-c * softplus(x))` (or two tables) |
| Gated DeltaNet recurrence, 48 heads x 128 x 128 state, carried over all T positions | **nothing**: FlashProve's relation is stateless between positions except attention's causal sums | **hard (the big one)**: integer recurrence semantics, state commitment, per-step rounding, range of state cells, continuity, initial state = 0 |
| hybrid schedule: 3 DeltaNet layers then 1 attention layer; two mixer types | every layer has the same attention; layers grouped in blocks of 2^ll with one attention sub-proof per block | **structural change**: block layout, `KL.bin` per-layer fields, verifier plan, Lean model |
| MTP layer, vision encoder | absent | **excluded** from a first port; a text-only request must be rejected if it carries image/video tokens |

### Why the recurrence is the hard part

- **Semantics.** The reference has two FP32 forms: per-token recurrence (L466-478) and a chunked
  form with a unit-triangular solve (L287-421). They are equal in exact arithmetic, not under
  rounding. An integer relation must pick one; the per-token form is the only one without division
  by data. The chunked form can still be a prover-side schedule only if it reproduces the per-token
  integer values exactly, which with per-step rounding it will not; so the prover is constrained to
  the sequential form or to a relation designed around chunks from the start.
- **Witness size.** If every per-token state is committed: 48 layers x 48 heads x 128 x 128 =
  37.7M cells per token, 38.7B per 1,024-token window. That is larger than Qwen's own committed
  weights (26.9B) and roughly 10x a Maverick window's intermediate values (**estimate**: about 70K
  values per layer per token from the section 6-7 shapes, so ~3.4B per window; not counted from the
  prover's actual layout). Committing only chunk-boundary states (chunk 64) cuts this to 0.60B cells, but then
  intra-chunk state must be re-derived inside the proof.
- **Range.** Every committed cell must pass the smallness test (below 2^18 in absolute value,
  `docs/format/11-1-machinery.md`). A state that sums decayed rank-1 updates over 1,024 steps needs a
  fixed-point format with explicit per-step rounding and a bound argument; the existing repository
  bounds (`scales/worst-case-bounds.md`) say nothing about recurrences.
- **Existing work.** `research/operators/glm_kda_slice/` (two linked steps, dim 2) and
  `research/operators/glm_kda_fixedpoint/` (one step, dim 1, staged floor) already prove the
  delta-rule algebra on the product oracle for GLM's KDA, whose decay is per key channel. Qwen's
  Gated DeltaNet decay is one scalar per head: the same algebra with `decay[i]` constant, so those
  slices cover Qwen's update as a special case. Nothing at 128 x 128, no gate generation, no
  convolution, no link to the GPU prover.

## 3. Size and resources

Counted from the shard headers (5 identical runs, `runs/SHA256SUMS`):

| quantity | Qwen3.8-27B | Maverick (docs/model.md shape) |
|---|---|---|
| total parameters | 27.78B (incl. 0.46B vision, 0.42B MTP) | ~400.7B committed set |
| committed set (decoder + embedding + head) | **26.90B** | 400.71B |
| ratio | **0.067** | 1 |
| per-token matrix MACs (decoder + head) | 25.6B (all dense) | 16.1B (top-1 routed + shared) |
| ratio | **1.59** | 1 |

Integer footprint under FlashProve's format: every committed entry outside Emb is in
-4,096 .. 4,095 (13 bits, held as 16-bit), Emb entries 4 signed bytes. Qwen: 25.6B x 2 B + 1.27B x
4 B ≈ **56 GB** of integer weights, against ~800 GB for the Maverick shape. Commitment-side files
scale with weights: the provider keeps 2.15 GB per Maverick commitment (guide/performance.md), so
roughly 0.15 GB for Qwen (**estimate**, linear in weight count).

Does commit + prove fit one H100 80 GB + host RAM? **Estimate, not measured:**

- *Host RAM.* Maverick committing peaked at 299.6 GB, serving at 269.7 GB. Scaling the
  weight-proportional part by 0.067 suggests committing well under 64 GB and serving under 64 GB of
  host memory for the weights, *before* the DeltaNet state witness. With per-token state committed
  (38.7B cells per window, at least 2 B each), one request adds ~80 GB of witness: still a
  single-host job (the GPU run in research/gpu had a ~684 GiB container), but the state, not the
  weights, decides the host size.
- *GPU.* 56 GB of integer weights alone would fit in 80 GB, but the Maverick prover does not keep
  weights resident (it cannot at 800 GB), so the existing streaming design applies; the GPU peak in
  the small synthetic run was reached during commit (74 GB sampled, research/gpu). No reason to
  expect Qwen not to fit one H100; not shown.
- *Prove cost (estimate, scaled from the timed runs: 111.23 ± 0.92 tok/s steady at 24 per batch on
  one H100).* If cost scales with per-token matrix work, Qwen is 1.59 times the work: about **70
  tok/s** at 24 per batch. That is a lower bound on time. The DeltaNet witness is the unknown: if
  per-token state cells are committed and cost scales with committed cells, the witness per window
  is ~10x Maverick's intermediate values (estimate above) and the rate could fall to **single-digit tok/s**. Chunk-boundary
  commitment plus intra-chunk recomputation would sit in between. The range spans an order of
  magnitude; the first milestones exist to narrow it.
- *Verify.* Proof size and `cp_verify` time scale with the number of sub-proofs and lookups, not
  weights; extra layer types and a recurrence sub-proof add to both. No estimate given.

## 4. Comparison with GLM-5.3-Flash and DeepSeek-V4.1-Flash

GLM and DeepSeek facts are from the prior port-feasibility research (pinned revisions
`46a050bec13002ad29ee795c16e61cf4fa3c4a9c` and `314113f8a7dadb388215396ba5fbee2c610a04d6`) and their
configs (SHA-256 in ENV.json), not re-derived. Counting rule, fixed before tallying: one family = one
new kind of constraint or table in the integer relation; a new size of an existing gadget is not a
family. GLM and DeepSeek counts are lower bounds.

| | Qwen3.8-27B | GLM-5.3-Flash | DeepSeek-V4.1-Flash |
|---|---|---|---|
| type | dense, hybrid linear/full attention | MoE 288 experts top-8 + shared, hybrid KDA / DeepSeek sparse attention | MoE 384 top-6 + shared, causal encoder-decoder, CSA2, Engram |
| total params | 27.8B | 320B (18B active) | 552B backbone (+196B Engram per card) |
| published tensor bytes | 55.6 GB (BF16) | 328 GB (FP8 + exclusions) | 510 GB (FP8/FP4) |
| committed vs Maverick | 0.067x | ~0.8x (estimate from total) | ~1.4x+ (estimate) |
| layers / width / vocab | 64 / 5,120 / 248,320 | 45 / 4,096 / 154,880 | 40 (20 enc + 20 dec) / 5,120 / 129,280 |
| routing | none | top-8, sigmoid + correction bias, normalized, scale 2.5 | top-6, sqrtsoftplus + bias, normalized, scale 1.5 |
| recurrent / linear attention | Gated DeltaNet, scalar decay, 48 of 64 layers | KDA, per-channel decay, 34 of 45 layers | none (but cross-layer KV/index reuse, encoder state) |
| residual | plain | mHC, 4 streams, 20 Sinkhorn iterations | mHC, 4 streams, 20 Sinkhorn iterations |
| **new op families** | **7**: DeltaNet recurrence; decay/beta gate table; causal conv1d; per-head q/k norm; mixer output gates; partial RoPE; hybrid schedule (incl. NE = 0, dq != d) | **11**: KDA recurrence; low-rank forget gate + tables; conv1d; per-head q/k norm; gated output norm; MLA latent attention (NoPE + separately roped indexer); DSA indexer top-2048 + pooling + tail; top-8 routing + aggregation; mHC Sinkhorn; clipped SwiGLU; hybrid dense/MoE + linear/sparse schedule | **12**: CSA2 sliding window + KV compression; hierarchical top-512 candidate selection; cross-layer KV/index reuse; CED encoder->decoder global KV; partial RoPE + YaRN; low-rank Q / grouped O; sqrtsoftplus top-6 routing; mHC Sinkhorn; Engram n-gram hash lookup into committed tables; Engram gating/mixing; FP4/FP8 multi-domain quantization incl. FP4 KV; heterogeneous schedule incl. prediction layers |
| hard items | 1 (recurrence) | 3+ (KDA recurrence, sparse top-k selection, mHC) | 5+ (CSA2 selection, CED, Engram, mHC, FP4 KV) |
| BF16 reference fits one host for calibration | yes (55.6 GB) | only via separate BF16 artifact, ~640 GB | no (multi-node) |
| expected effort to first full-model proof (judgement) | **medium-large**: one research gadget + ~6 engineering extensions | large: recurrence + sparse selection + routing + mHC | very large; not a first target |

## 5. Recommendation

**Yes: Qwen3.8-27B should be the first real-model port**, ahead of GLM-5.3-Flash (the prior
recommendation). Reasons, in order:

1. It isolates the one genuinely new research problem (proving a gated delta-rule recurrence) from
   routing, sparse selection and multi-stream residuals. GLM needs the same recurrence plus all of
   those. Whatever is built for Qwen's scalar-decay DeltaNet carries to GLM's per-channel KDA, and
   the existing KDA slices already cover Qwen's algebra.
2. Everything else is an extension of operators FlashProve already proves (norm, softmax attention,
   SwiGLU, rotary, lookups), not a new construction.
3. It is small: 6.7 % of Maverick's committed weights, BF16 release that fits one machine, so
   fidelity calibration (issue #8) can run on a single host without multi-node infrastructure.
4. Ungated, Apache-2.0, single precision artifact (BF16): no FP8/FP4 format to reconcile first.

What would change the recommendation: if milestone M1 below shows the recurrence state cannot be
held in a fixed-point format that passes the 2^18 smallness bound with tolerable error over 1,024
steps, the DeltaNet path is blocked for Qwen *and* GLM alike, and the first port should fall back to
a dense, full-attention-only model (none of the three candidates is one).

### Smallest milestones (each a separate pre-registered experiment)

- **M0, spec (CPU, desk).** Write the integer semantics of one Gated DeltaNet layer as an addendum to
  docs/model.md: fixed-point format of q, k, v, beta, decay and state; per-step rounding; tables for
  `exp(-c softplus(x))`; the conv1d and gated-norm placement; range conditions. Python reference in
  exact integers. Exit: reference agrees with the FP32 Transformers recurrence within a stated
  tolerance on random inputs of the exact shape (no weights).
- **M1, smallest proof (CPU).** One DeltaNet head at the real state size 128 x 128, T = 4 tokens,
  synthetic inputs, proved on the product-oracle harness used by `research/operators/glm_kda_*`, with
  hostile provers (state continuity, delta operand, rounding remainder) rejected. Report proof size,
  CPU prove/verify time (>= 10 runs), and the measured state range over T = 1,024 from the M0
  reference. This is the go/no-go for the recurrence.
- **M2, one layer of exact shape (CPU).** One full Qwen DeltaNet layer (d 5,120; 16/48 heads;
  conv1d; gates; gated norm; out_proj; SwiGLU 17,408) on synthetic weights of exactly the published
  shapes, small T (16), proved end to end on the harness. Gives the first measured
  per-layer witness size and the basis for a real prove-cost estimate.
- **M3, prover integration (GPU, needs spend approval).** A 4-layer block (3 DeltaNet + 1 full
  attention) in the CUDA prover at T = 1,024, synthetic weights, with `cp_verify` changes and
  negatives. Only after M1 and M2 pass.

Real weights, Lean extension, full 64-layer model and fidelity numbers come after M3 and are not
scoped here.

## Not claimed

No part of Qwen3.8-27B is supported by FlashProve today. No proof, timing or memory figure for Qwen
was measured; every cost in section 3 is an estimate labelled as such. The integer model's fidelity
to the BF16 model is unknown. The Transformers reference is not checked against the publisher's
serving kernels. Multimodal input, MTP and contexts above 1,024 tokens are out of scope.
