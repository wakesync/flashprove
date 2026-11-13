# Design note: head dimension 256 and partial rotary (issue #175)

Base: main `59bff9a4608e0cc720d58d7c30823a8838fa43e4`.
Desk design only. No code, verifier, parameter file or measured result changes.
This first checkpoint is an incomplete outline, not an admission recommendation.

## Answer in three lines

1. N4: compare a narrower q/k clamp, split score sums and a wider score budget using exact integer arithmetic.
2. Rotary: specify partial width, pairing, deterministic table identity and statement binding before widening admission.
3. Existing Maverick statements and verdicts must remain unchanged. No Qwen proof is established.

## 1. Inventory: OK / NEW / DEP

Pending line-by-line inventory at the pinned base. OK means unchanged under the proposed extension; NEW means a new condition or definition is needed; DEP means an out-of-scope prerequisite.

## 2. N4 alternatives

Pending recomputation from the implemented N1 through N9 conditions. No supplied bound is adopted without recomputation.

## 3. Rotary statement and table definition

Pending comparison of the existing float64 route with the standalone integer generator already on main.

## 4. Needs N1 through Nk

Pending scoped design obligations, distinct from the attention fork's N1 through N9 labels.

## 5. Tests T1 through Tk

Required coverage: signed N4 boundary, one-entry table mutation, byte-identical legacy full-width proofs, and partial-width rejection by the unmodified verifier.

## 6. Dependencies and stop rule

Dependencies: dq admission, q/k RMSNorm, output gate and clamp fidelity. Stop rather than change a Maverick-path verdict or silently widen a bound.

## What is not established

No implementation, proof acceptance, activation fidelity, performance or end-to-end Qwen inference is established. This outline does not yet establish a sound extension.
