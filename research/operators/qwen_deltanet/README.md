# Qwen3.8 Gated DeltaNet, one head at 128 x 128, T = 4 (M1; not checkpoint support)

Milestone M1 of the Qwen3.8-27B feasibility study (PR #28). Pre-registration, results and verdict:
[experiments/20261104-11-qwen-deltanet-m1/](../../../experiments/20261104-11-qwen-deltanet-m1/).
**Verdict: FAIL as registered.** Honest proofs are accepted (10/10) and hostile proofs are rejected (40/40). But at F = 12 the range study overflows the 2^18 bound for heavy-tailed value inputs. See RESULTS.md.

## Relation (chosen research contract, not the publisher's numerics)

All quantities are integers at scale 2^F, F = 12. The public values are: initial state S0 (128 x 128), and per token the prepared decay a = exp(g) in [0, 2^F], beta in [0, 2^F], L2-normalised k and q (q also x 1/sqrt(128)), v, outputs o, and the final state. Per token:

```
P[j]     = sum_i S[i,j] k[i]                              exact
M[j]     = floor(a P[j] / 2^2F)                           decayed memory read
delta[j] = floor((v[j] - M[j]) beta / 2^F)
S'[i,j]  = floor((a S[i,j] + k[i] delta[j]) / 2^F)        decay + rank-1 update
o[j]     = floor(sum_i S'[i,j] q[i] / 2^F)
```

S', M and delta are signed 19-bit (|x| < 2^18, FlashProve's smallness bound). Remainders are unsigned F or 2F bits. Overflow means the statement is rejected; it is never saturated. This is the per-token recurrence of Transformers `modeling_qwen3_5.py` L466-478 (see PR #28), with decay folded into the single update floor. Gate generation (exp, softplus, sigmoid), conv1d, L2 norm and the gated output norm are **not** proved here.

## Lowering

Built on the same committed product oracle and affine-row lowering as `glm_kda_fixedpoint` (#19). `product.h` is a wide variant of `affine_rows/product.h`: up to 2^23 relations and 256 terms per relation, with its own transcript label. Every relation is bound in the first query and counted in GroupLoad and plan_iopp.

- Product gates: S*a (decay), S*k (memory read), P*a, (v-M)*beta, k*delta (update), S'*q (output).
- Operand reuse: 2-term affine relations. Public values: 1-term relations.
- Reductions over 128 terms are single affine relations with the floor remainder bits included.
- Each range check is a bit decomposition. Each bit column is [x, x, x] with a = b and c = a relations, so x^2 = x.

Statement: 2,338,816 product gates (table 2^22), 4,761,088 relations, 11,430,400 terms. Proof 50.4 MB. CPU prove 51.4 s and verify 11.6 s (median of 10) on a shared VM. Research security settings from #19 (target 10 bits).

`test.cpp` lowers the witness with explicit quotient and remainder arithmetic. It checks every M, delta, S and o cell against `reference.py` (numpy floor), which is an independent path.

## Reproduce (CPU, about 50 min, about 7 GB RAM)

```
python3 research/operators/qwen_deltanet/record.py            # all
python3 research/operators/qwen_deltanet/record.py hostile    # subsets: build honest hostile ranges
```

## Not claimed

No fidelity to Qwen's kernels, no real weights, no gate/conv/norm producers, no production security parameters, no GPU prover integration, no Lean theorem. Hostile tests are sampled classes, not a soundness proof. Timings are not performance claims.
