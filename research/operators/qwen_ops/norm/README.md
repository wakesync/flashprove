# Per-head bounded L2 and RMS normalization

> **These norms are NOT the M2 design's integer-square-root norm (#66).** They use a bounded mean-square table with unit gain, no epsilon, and no support for low-energy vectors. Do not substitute them for M2's isqrt/epsilon relation.

Implementation: `../proof.cpp`, `norm()`. Shared protocol and artifact instructions: `../README.md`.

## What is proved

One committed vector of D=128 (L2) or D=256 (RMS) with x_j in [-S,S), S=2^F. The sum E=sum x_j^2 is linked to the canonical input cells, not supplied by the prover as an unconstrained scalar.

```
k = floor(1024*E/(D*S*S)) - 256
R = l2-128[k]     # L2: approximates S/sqrt(128*(k+256)/1024)
R = rsqrt[k]      # RMS: approximates S/sqrt((k+256)/1024)
y_j = floor(x_j*R/S)
```

A one-hot selector proves k in [0,4096) and R equals the pinned row. Every output reads the same R. The key floor's remainder and each output floor's remainder are exactly bit-decomposed. Norm outputs have a signed [-4*S,4*S) bound. The table supports mean squares in [1/4,17/4), but combined with the input bound the reachable interval is [1/4,1]. Zero and low-energy vectors do not satisfy the relation; there is no silent clamp or exceptional zero case.

## What is public, committed and prover-chosen

- Public: operator, F, the 128 (L2) or 256 (RMS) outputs.
- Committed and chosen freely by the prover: the whole input vector x, its energy E, the key k, the selected coefficient R, all remainders and range bits.

A proof therefore shows only: **there exists an in-range input vector, with mean square in the admitted domain, whose bounded norm gives these outputs.** It says nothing about which projection, model weights or token produced x. The outputs are more constrained than for the convolution or rotary (they must be a scaled copy of some in-range vector at a table coefficient), but the input is equally unbound. Binding x to committed weights and earlier layers is the job of the M3 statement (PR #70, draft), not of this PR. See the shared README and https://github.com/wakesync/flashprove/pull/67#issuecomment-6757161440.

## What the verifier recomputes

The head-specific circuit, fixed coefficient table, output bindings and shape/range constraints only. It does not see or recompute E, k, R or y from public inputs. Its build is witness-free.

## No-wrap argument

The input bit bounds give E<=D*S^2<=2^40 at D256/F16. The mean-key quotient is pinned by the selector to [256,4351]; its remainder is in [0,2^(2F+log2(D)-10)). Thus the key equation's magnitudes are below 2^43, not just below a host integer overflow threshold. R<=2*S, |x_j*R|<=2*S^2<=2^33, and the bounded output plus remainder cannot differ from this product by a multiple of the field modulus. These bounds concern the malicious relation, not a measured honest range. All arithmetic uses the Goldilocks field in the proof; the largest host i64 lowering expression is likewise within its range.

## What is not covered

These are registered NEW bounded-domain semantics, not M2's isqrt/epsilon relation or a fidelity theorem for the publisher. No epsilon, learned per-channel gain, DeltaNet query's extra 1/sqrt(128), arbitrarily small norm, external input commitment identity or matmul linkage is implemented. There is one head per proof, not a whole Qwen q/k layer. The table selector backend is linear in 4096 entries. Cross-head reuse of the coefficient is not a supported operation.

## Reproduce

Prefix proof batches with the shared heavy-job gate and <=6-core affinity:

```
python3 research/operators/qwen_ops/record.py all l2
python3 research/operators/qwen_ops/record.py all rms
python3 research/operators/qwen_ops/record.py smoke l2
python3 research/operators/qwen_ops/record.py smoke rms
python3 research/operators/qwen_ops/record.py ubsan l2
python3 research/operators/qwen_ops/record.py ubsan rms
python3 research/operators/qwen_ops/fidelity.py l2
python3 research/operators/qwen_ops/fidelity.py rms
```

Raw receipts: experiment `runs/l2-*` and `runs/rms-*`. Fidelity uses 10 independent seeded synthetic vectors per F, giving 1280 or 2560 correlated component errors. No input quantization error is included: the float reference receives the dequantized same integers. Limit: 10 uniform [-1,1) vectors have mean square near 1/3, so they mostly sample one region of the admitted interval, not its boundaries or real activation distributions. These are synthetic quantized-input measurements, not model fidelity.
