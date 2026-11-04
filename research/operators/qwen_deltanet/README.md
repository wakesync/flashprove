# Qwen3.8 Gated DeltaNet, one head at 128 x 128, T = 4 (M1; not checkpoint support)

Milestone M1 of the Qwen3.8-27B feasibility study (PR #28). Issue #33, part of tracking issue #32. Pre-registration, results and verdict:
[experiments/20261104-11-qwen-deltanet-m1/](../../../experiments/20261104-11-qwen-deltanet-m1/).
**Verdict: FAIL as registered.** Honest proofs are accepted (10/10) and hostile proofs are rejected (40/40). But at F = 12 the range study overflows the 2^18 bound for heavy-tailed value inputs: delta overflows, and the heavy-tailed public v itself already exceeds the |v| < 2^18 input contract. See RESULTS.md. All numbers here are measured, unreplicated.

## Relation (chosen research contract, not the publisher's numerics)

All quantities are integers at scale 2^F, F = 12. The public values are: initial state S0 (128 x 128), and per token the prepared decay a = exp(g) in [0, 2^F], beta in [0, 2^F], L2-normalised k and q (q also x 1/sqrt(128)), v, outputs o, and the final state. Per token:

```
P[j]     = sum_i S[i,j] k[i]                              exact
M[j]     = floor(a P[j] / 2^2F)                           decayed memory read
delta[j] = floor((v[j] - M[j]) beta / 2^F)
S'[i,j]  = floor((a S[i,j] + k[i] delta[j]) / 2^F)        decay + rank-1 update
o[j]     = floor(sum_i S'[i,j] q[i] / 2^F)
```

S', M and delta are signed 19-bit. The builder enforces |x| < 2^18 (FlashProve's smallness bound); each bit-decomposition relation encodes x + 2^18 in 19 bits, so at relation level the range is [-2^18, 2^18) (PREREG Amendment A4). Remainders are unsigned F or 2F bits. Overflow means the statement is rejected; it is never saturated. This is the per-token recurrence of Transformers `modeling_qwen3_5.py` L466-478 (see PR #28), with decay folded into the single update floor. Gate generation (exp, softplus, sigmoid), conv1d, L2 norm and the gated output norm are **not** proved here.

## Lowering

Built on the same committed product oracle and affine-row lowering as `glm_kda_fixedpoint` (#19). `product.h` is a wide variant of `affine_rows/product.h`: up to 2^23 relations and 256 terms per relation, with its own transcript label. Every relation is bound in the first query and counted in GroupLoad and plan_iopp.

- Product gates: S*a (decay), S*k (memory read), P*a, (v-M)*beta, k*delta (update), S'*q (output).
- Operand reuse: 2-term affine relations. Public values: 1-term relations.
- Reductions over 128 terms are single affine relations with the floor remainder bits included.
- Each range check is a bit decomposition. Each bit column is [x, x, x] with a = b and c = a relations, so x^2 = x.

Statement: 2,338,816 product gates (table 2^22), 4,761,088 relations, 11,430,400 terms. Proof 50.4 MB. CPU prove 51.4 s and verify 11.6 s (median of 10) on a shared VM; measured, unreplicated, not a performance claim. Research security settings from #19 (target 10 bits).

`test.cpp` lowers the witness with explicit quotient and remainder arithmetic. It checks every M, delta, S and o cell against `reference.py` (numpy floor), which is an independent path.

## Soundness note (argument, not a proof)

The hostile suite (H2) shows that the IOP rejects proofs whose witness violates at least one relation: every complete hostile proof had at least one violated relation. It does not by itself show there is no relation-satisfying wrong witness. That half rests on floor uniqueness:

- **Precondition.** `admissible()` in `test.cpp` is checked on the public statement before proving: |k|, |q| <= 2^F, a and beta in [0, 2^F], |v|, |o|, |S0| and |S_T| < 2^18. This is a statement-side check, **not a relation**. A verifier that accepts a statement must apply the same check.
- **No wrap.** Given admissible public inputs and 19-bit range-checked private cells, the largest relation magnitude is about |a * P| <= 2^12 * 128 * 2^18 * 2^12 = 2^49, far below the Goldilocks prime, so every relation holds over the integers, not just mod p.
- **Unique floors.** Every quotient is range-checked to 19 bits ([-2^18, 2^18)) and every remainder to F or 2F unsigned bits. Over the integers, n = d * q + r with 0 <= r < d has exactly one solution, so each staged floor (M, delta, S', o) has exactly one satisfying (quotient, remainder) pair. Bits are forced by x^2 = x.
- **Binding.** Every product gate operand is wired to the canonical previous-state cell, a public value, or the shared delta cell (checked by hand in the PR #47 review).

Under the #19 research security settings (target 10 bits), this is relation soundness of the construction, not production security.

## Reproduce (CPU, about 50 min, about 7 GB RAM)

```
python3 research/operators/qwen_deltanet/record.py            # all
python3 research/operators/qwen_deltanet/record.py hostile    # subsets: build honest hostile ranges
```

## Not claimed

No fidelity to Qwen's kernels, no real weights, no gate/conv/norm producers, no production security parameters, no GPU prover integration, no Lean theorem. Hostile tests are sampled classes, not a soundness proof. Proposed claims (not added to `loop/claims.json`) are measured, unreplicated, and the F = 10 range observation is secondary and unregistered (no proof run at F = 10). Timings are not performance claims.
