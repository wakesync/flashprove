# MoE top-k routing: bias-corrected stable top-k, normalized weights, weighted aggregation (research gadget; not checkpoint support)

Shared GLM-5.3-Flash / DeepSeek-V4.1-Flash router operator. Issue #11, cross-ref #35. Pre-registration, results and verdict: [experiments/20261105-11-moe-topk-routing/](../../../experiments/20261105-11-moe-topk-routing/). All numbers are measured, unreplicated, at research security settings (target 10 bits), on a shared CPU VM.

## Upstream semantics (pinned sources, no weights)

| | GLM-5.3-Flash | DeepSeek-V4.1-Flash |
|---|---|---|
| Source | Transformers `f90e93c4f83974f634860e246cdfd2c68666d605`, `models/glm5_next/modeling_glm5_next.py` L144-182 (`Glm5NextTextTopkRouter`); config at HF revision `46a050bec13002ad29ee795c16e61cf4fa3c4a9c` | publisher `inference/model.py` L794-829 (`Gate`) and `config.json`, HF revision `314113f8a7dadb388215396ba5fbee2c610a04d6` |
| Routed experts, k | 288, top-8 (+1 shared) | 384, top-6 (+1 shared); DSpark draft layers 128, top-3 (out of scope) |
| Score | `sigmoid(x W^T)` in FP32 | `sqrt(softplus(x W^T / gate_temp))` in FP32 (`scoring_func: sqrtsoftplus`) |
| Selection | `topk(s + e_score_correction_bias)` after a group stage (sum of top-2 per group, keep `topk_group` groups); config `n_group = topk_group = 1`, so no expert is filtered | `topk(s + bias)`; image-span tokens use a separate `bias_vl` |
| Weights | gathered ORIGINAL `s`; `/ (sum + 1e-20)` if `norm_topk_prob` (true); `* 2.5` | gathered ORIGINAL `s`; `/ (sum + 1e-20)` only if `norm_topk_prob` and k > 1; `* 1.5` |
| Weight applied | to the expert's `down_proj` OUTPUT (`F.linear(...) * w`) | to the SwiGLU activation BEFORE `w2` (`weights * x`, then `w2`) |
| Tie order | `torch.topk(..., sorted=False)`: unspecified | `torch.topk` default: unspecified; no stable semantic oracle in either |

Shared: correction bias steers selection only, weights come from unbiased scores, normalization over the selected k, then a routed scaling factor. Differences: score nonlinearity, k/E, scale, the group stage (GLM only, inactive in this config), the vision bias (DeepSeek only, text-only scope must reject image tokens first), and where the weight multiplies (linear, so equal over the reals, but different under integer rounding). `gate_temp` is not a key in the HF `config.json` and the `ModelArgs` default is 1.0. Review of #62 checked the publisher's `inference/config.json` at the same revision 314113f8 (sha256 `2e84f45cf1dac8c7fcbb200e96667d4b913275690668ed496f24c7747207a809`): it has no `gate_temp` key either, and `inference/generate.py` builds `ModelArgs(**json.load(f))` from it, so the reference inference path runs with `gate_temp = 1.0`. The same file sets `n_routed_experts = 384`, `n_activated_experts = 6`, `route_scale = 1.5`, `score_func = sqrtsoftplus` and leaves `norm_topk_prob` at its default (true), matching the HF config.

## Integer contract (NEW, chosen here, not publisher numerics)

Per token, E experts, k selected, h output lanes:

- Public: scores `s_i` unsigned 16-bit (score nonlinearity is upstream of this gadget and NOT proved), bias `b_i` signed 16-bit, expert outputs `X_i[d]` signed 16-bit, outputs `y[d]`. Shape (E, k, h, T, RS) fixed by the verifier.
- Key `K_i = E (s_i + b_i + 2^15) + (E - 1 - i)`: distinct; larger key = larger corrected score, ties to the LOWEST expert index.
- Selected ordered list `p_1..p_k`: the k largest keys, strictly descending.
- `D = sum_m s_{p_m}` (ORIGINAL scores). `D = 0` is inadmissible (fail closed, no epsilon).
- `w_m = floor(2^12 RSn s_{p_m} / (RSd D))`, RS = RSn/RSd (GLM 5/2, DeepSeek 3/2): normalization and routed scale in one floor. Weights need not sum exactly to 2^12 RS. k = 1 also normalizes (DeepSeek does not; a k = 1 DeepSeek layer would need a flag).
- `y[d] = floor(sum_m w_m X_{p_m}[d] / 2^12)` (GLM placement).

## Relation (lowering on the shared product oracle)

All cells are columns `[a, b, a*b]` of the committed product oracle; every constraint is a wide affine row (`product.h`, a copy of `qwen_deltanet/product.h` with 512 terms per row and its own transcript label).

1. `(s_i, b_i)` column, both 1-term public bindings; `s_i` 16-bit range.
2. One-hot `P[m,i]` (k x E): Boolean (`[x,x,x]`), each row sums to 1. Gather columns `(P[m,i], K_i)` with `K_i` tied linearly to the `(s_i, b_i)` cell, and `(P[m,i], s_i)` tied to `s_i`.
3. `sel_i = sum_m P[m,i]` is Boolean: no expert twice.
4. Carriers `(G_m, S_m)` = sums of the gather products: the selected key and ORIGINAL score in slot m.
5. `G_m - G_{m+1} - 1` in 26 bits: strictly descending.
6. `(G_k - K_i - 1) (1 - sel_i)` in 26 bits for every i: every unselected key is below the last selected key.
7. `(w_m, D)` with `D = sum_m S_m`; `RSd w_m D + r_m = 2^12 RSn S_m`; `r_m` and `RSd D - 1 - r_m` in 21 bits (same `r_m` bit cells); `w_m` 14 bits; `D - 1` 19 bits.
8. Aggregation: `(P[m,i], X_i[d])` gathers (each `X_i[d]` public-bound), `(w_m, XG_m[d])`, `sum_m w_m XG_m[d] + rem = 2^12 y[d]`, `rem` 12 bits.

Why the selection is unique: (2)+(3) give exactly k distinct experts in k slots; (5) orders them strictly by key; (6) puts every other key strictly below the k-th; keys are distinct, so the slots must be the k largest keys in descending order. Every range is at most 26 bits on values below 2^34 in magnitude, far under the Goldilocks prime, so no relation can be met by wraparound; a negative difference reduces near p and cannot fit its range. Floors are unique by the remainder ranges. Two inputs are bounded by statement-side admission (`admissible()` in `test.cpp`), not by a relation: the bias range `-2^15 <= b_i < 2^15` (which keeps `s_i + b_i + 2^15` in `[0, 2^17)`, so keys are distinct, below `2^26`, and in the right order) and the expert-output range `|X_i[d]| < 2^15`. Any integration must keep that admission check on the verifier side or add the ranges as relations. This is an argument, not a Lean theorem. H2b checks it by brute force at E = 16 (all 256 / 4,096 ordered k = 2 / k = 3 tuples, with exact ties): exactly one admits a satisfying witness, the reference.

## Cost (measured, T = 4, h = 16)

| | GLM 288/8 | DeepSeek 384/6 |
|---|---|---|
| Selection + normalization columns per token | 20,537 | 24,689 |
| Aggregation columns per token (h = 16) | 37,184 | 37,152 |
| Total columns (2^18 table) | 230,884 | 247,364 |
| Relations / terms | 465,416 / 1,024,624 | 499,496 / 1,106,496 |
| Prove, median of 10 (min/max) | 3.11 s (3.03/3.34) | 3.17 s (3.11/3.27) |
| Verify, median of 10 (min/max) | 0.77 s (0.75/0.80) | 0.87 s (0.83/0.90) |
| Proof size | 3.18 MB | 3.18 MB |

Selection costs about E (3k + 45) columns per token: per expert one score/bias cell, 16 score-range bits, 3k one-hot/gather cells, one sel cell, one threshold cell and 26 threshold-range bits; plus k carriers, 26 (k - 1) ordering bits, 57 k weight cells and 19 bits for D - 1. GLM: 288 x 69 + 665 = 20,537; DeepSeek: 384 x 63 + 497 = 24,689 (both exact). Aggregation is k h (E + 1) + 12 h: 37,184 and 37,152 at h = 16. Aggregation by one-hot gather costs about k E columns per output lane: at h = 4096 that is 9.52M (GLM) and 9.51M (DeepSeek, h = 4096 used for comparison; its residual width is 5120) columns per token, about 9x over the pre-registered 2^20 line, so dispatch at real width must not use the one-hot gather (pre-registered NO-GO rule). The obvious replacement is to gather by index from a committed expert-output table (lookup / memory argument), keyed by the already-proved `p_m`.

## Reproduce (CPU, about 4 min, < 1 GB RAM)

```
python3 research/operators/moe_topk/record.py           # all
python3 research/operators/moe_topk/record.py hostile   # subsets: build honest hostile enum
```

## Not claimed

No score nonlinearity (sigmoid, sqrt-softplus), no gate matmul, no expert FFN, no FP8/FP4 conversion, no group stage (GLM config has n_group = 1; other group counts must be rejected), no DeepSeek vision bias, no k = 1 DeepSeek non-normalization, no fidelity to either model, no production security parameters, no Lean theorem, no GPU integration. Hostile classes are sampled, not a soundness proof. Timings are not performance claims.
