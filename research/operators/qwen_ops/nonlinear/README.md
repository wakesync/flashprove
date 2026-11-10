# Nonlinear table lookup on a committed scalar

Implementation: `../proof.cpp`, `nonlinear()`. Full format, deterministic generator, verifier boundary and no-wrap analysis: `../README.md`.

The proved tuple contains one nonpublic scalar X, its exact floor-to-grid quotient/remainder, a shared 4096-way Boolean one-hot selector, and six claimed outputs: SiLU, sigmoid, softplus, and exp(-c*softplus) at c=1/2,1,2. One proof covers all six functions at the same X, not six independent input positions. The input domain is [-8,8) at scale 2^F, row grid 1/256. Outputs use the pinned nearest-even table entries. The key, outputs and reused selectors are the same committed product-oracle wires or are constrained equal. Wrong table rows are not rejected by a public float recomputation.

Public: operator, F and the six outputs. Committed and chosen freely by the prover: X, its quotient/remainder and the selector. A proof therefore shows only: **there exists an in-domain X whose six pinned table rows are these outputs.** The outputs must form one consistent table row, so they are more constrained than for the convolution or rotary, but X is unbound: nothing ties it to a model's weights or an earlier layer. Binding it is the job of the M3 statement (PR #70, draft), not of this PR (see the shared README and https://github.com/wakesync/flashprove/pull/67#issuecomment-6757161440).

The verifier regenerates only the circuit from its pinned integer tables and public outputs. It does not receive X. This proves local tuple consistency, not identity with a previous matmul commitment. SiLU/signature combinations can reveal information about X; no privacy claim is made. There is no learned A_log/dt_bias, checkpoint-specific decay constant, sigmoid-times-mixer-output gate multiplication, or runtime clamping.

Reproduce from repository root, prefixing proof batches with the shared heavy-job gate and <=6-core affinity:

```
python3 research/operators/qwen_ops/check_tables.py
python3 research/operators/qwen_ops/record.py all nonlinear
python3 research/operators/qwen_ops/record.py smoke nonlinear
python3 research/operators/qwen_ops/record.py ubsan nonlinear
python3 research/operators/qwen_ops/fidelity.py nonlinear
```

Fidelity is evaluated at each of the 4096 grid points, 4096 seeded uniform integer inputs and five explicit boundary/zero inputs (8197 observations, with duplicates intentionally retained) per function/F. Quantization uses floor to the grid, so higher F does not eliminate the grid's approximation error. Raw proof and error receipts: `experiments/20261109-35-qwen-operators/runs/nonlinear-*`.
