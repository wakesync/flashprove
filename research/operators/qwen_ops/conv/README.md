# Four-tap causal convolution, bounded local relation

Implementation: `../proof.cpp`, `conv()`. Shared protocol and artifact instructions: `../README.md`.

## What is proved

One depthwise channel, four new tokens, three incoming history words, four taps, all canonical committed cells in the same product oracle. Input and tap integers are in [-S,S), S=2^F. Chronological order is H[-3],H[-2],H[-1],X[0],X[1],X[2],X[3]. At t=0..3:

```
y[t] = floor(sum(w[j]*input[t+j], j=0..3) / S)
```

All four uses of each tap and overlapping input/history windows are equality-linked to the canonical cells. Each output has an exact F-bit remainder, including for negative accumulators. There is no bias, SiLU or output saturation in this standalone relation. Zero history is allowed but not mandatory or silently substituted.

Input ranges use F+1 Boolean bits and an offset S. Four signed products have |sum|<=4*S^2<=2^34 at F16. The output is bounded by the wider signed interval [-8*S,8*S), the remainder is in [0,S), and both sides of the floor equation remain far below the Goldilocks modulus. The +4*S boundary is admitted (four products of -S by -S), unlike a too-narrow half-open [-4*S,4*S) guard.

## What the verifier recomputes

The fixed circuit shape, public output bindings, exact bit-range relations and shared-wire locations. It does not receive input/history/tap values and does not compute the convolution result from public operands.

## What is not proved

This is an existential relation on one committed tuple, not authentication of an externally chosen model kernel or incoming history commitment. There is no cross-proof history root, next-chunk handoff or model-matmul provenance. A consistent replacement of all history/kernel/input cells can be another valid witness. **Local arithmetic and shared-history-use are covered; carried-history identity remains PARTIAL for issue #35.** No multi-channel batch, learned-weight binding or integration with SiLU/DeltaNet is claimed.

## Reproduce

From repository root, prefix proof batches with the host's shared heavy-job gate and <=6-core taskset:

```
python3 research/operators/qwen_ops/record.py all conv
python3 research/operators/qwen_ops/record.py smoke conv
python3 research/operators/qwen_ops/record.py ubsan conv
python3 research/operators/qwen_ops/fidelity.py conv
```

The final registered profile's results are in `experiments/20261109-35-qwen-operators/runs/conv-*`. The float reference uses dequantized integer inputs/taps, not fresh real-valued samples or BF16 weights. Errors are 40 output observations from 10 four-token chunks per F. Wrong-history-use hostile proofs alter a multiplication operand while preserving its product, so they test actual committed wire linkage, not external history identity.
