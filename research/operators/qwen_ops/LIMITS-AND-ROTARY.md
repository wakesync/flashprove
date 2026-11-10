# Upstream limit changes and optional rotary semantics

Issue #35. This PR does not modify any upstream limit, parameter admission rule or served profile.

## Where the limits live

- `verifier/src/cp_verify.cpp`, shape derivation around `shape-heads`: currently requires H*dh=d, power-of-two dh>=2 and H+Gk<=64. Qwen full attention has H=24, Gk=4, dh=256, d=5120, so dq=6144 must be separately admitted. Loosening just the equality is insufficient: audit every subsequent use of d versus dq, projection layouts, attention reductions and output projection. `verifier/src/vf_weights_layout.h` already records dq/dkv separately but fixes qk storage to 64 head slots; this is compatible with 28 Qwen full-attention heads, not proof of the rest of the planner.
- `verifier/src/vf_common.h`, `rotaryServed`: theta in {10000,500000}, dh<=128, lt<=10. Qwen needs theta=10000000, dh=256 and a rotary width independent of dh, here 64. Do not replace the cap and assume table determinism: partial masking, rotate-half pairing and deterministic table identity must enter the statement/configuration. Revisit `scales/tests/table_ties.py` if relying on the upstream float-based table route. This lane's nonlinear tables do not validate rotary tables.
- `verifier/src/vf_common.h`, `servedForm`: `s.experts` gates `routed-experts`. The documented standard form in `verifier/docs/parameter-file.md` requires NE>0. Qwen has NE=0. `verifier/tests/served_form_test.py` explicitly exercises dense/no-expert rejection and table-digest/clamp dependencies. Add a distinct reviewed dense profile, rather than turning off admission checks piecemeal. `vf_weights_layout.h` allows NE=0 when no layer uses MoE, but enforces the existing dense/MoE schedule; Qwen's DeltaNet/full-attention schedule is a different axis and needs new layout tags.
- `verifier/src/vf_attention_shape.h`: GQA divisibility and dimension/layout assumptions need retesting at H=24/G=4/dh=256. `verifier/docs/parameter-file.md` is the user-facing admission contract, not the sole implementation of these restrictions.
- `docs/model.md` and the Lean model describe the current layer/operator placement. New operator proofs do not establish compatibility of the main GPU planner, model commitment, KL.bin scaling, or the model theorem.

No limit is relaxed by this research harness; its own bounded synthetic profile is not an admitted model profile.

## Partial rotary: semantics only, no proof or generated trig tables

Optional gadget not implemented in this lane. Proposed text-only semantics for position t in [0,1024), vector X of dimension 256 at scale S=2^F, theta=10^7, rotary width R=64:

For j=0..31:

```
omega_j = theta^(-2*j/64)
C[t,j] = nearest_even(S*cos(t*omega_j))
U[t,j] = nearest_even(S*sin(t*omega_j))
Y[j]    = floor((X[j]*C[t,j] - X[j+32]*U[t,j])/S)
Y[j+32] = floor((X[j+32]*C[t,j] + X[j]*U[t,j])/S)
```

For j=64..255, Y[j]=X[j] exactly. This is rotate-half on the first 64 coordinates, not adjacent-coordinate pairing across the 256-dimensional vector. Text-only equal M-RoPE position streams reduce to this 1-D position rule. Unequal image/video position streams, YaRN, contexts above 1024 and nontext tokens are excluded.

A future implementation must specify a deterministic integer/exact interval generator for C/U, publish their hashes and rounding decisions, prove two signed products and an exact floor per output, bind the position and mask, and preserve the 192 untouched coordinates by shared-wire identity. Hostile tests must include wrong position, swapped sin/cos, sign, pair permutation, mutation outside the rotated prefix, and out-of-domain position. The formulas above are a proposed contract, not measured fidelity or an existing proof.
