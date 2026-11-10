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

## What is public, committed and prover-chosen

- Public: operator, F, the four outputs. Nothing else.
- Committed and chosen freely by the prover: the four taps (the kernel), the three history words, the four new inputs, all remainders and range bits.

A proof therefore shows only: **there exist a kernel, a history and inputs in [-S,S) for which the four-tap floor relation gives these four outputs.** It says nothing about a particular model's weights or a particular earlier chunk. The outputs are not tied to any model: for example taps (0,0,0,-S) with new inputs X[t]=-y[t] (any history) give y[t]=floor(-S*X[t]/S)=-X[t], so any four outputs in (-S,S] have a witness. How much of the wider admitted output interval is reachable with other kernels was not measured.

## What is not proved

This is an existential relation on one committed tuple, not authentication of an externally chosen model kernel or incoming history commitment. There is no cross-proof history root, next-chunk handoff or model-matmul provenance. **The kernel is as unbound as the history.** The opus reviewer built complete proofs with the unmodified prover that the unchanged verifier accepted (https://github.com/wakesync/flashprove/pull/67#issuecomment-6757161440; the reviewer's runs, not committed run files of this PR): one with outputs of the reviewer's choosing, (S,-S+1,1234,-77), via taps (0,0,0,-S); one reproducing the seed-3 public outputs with a different kernel (all taps -S) and freshly solved history and inputs. The hostile `public-output` and `wrong-output` rejections cannot stop a prover who simply picks a different witness. **Local arithmetic and shared-history-use are covered; kernel, history and input identity are absent, so #35 remains PARTIAL.** Binding the kernel to committed weights and the history to the previous chunk is the job of the M3 statement (PR #70, draft) and the state-commitment work (#34), not of this PR. No multi-channel batch, learned-weight binding or integration with SiLU/DeltaNet is claimed.

## Reproduce

From repository root, prefix proof batches with the host's shared heavy-job gate and <=6-core taskset:

```
python3 research/operators/qwen_ops/record.py all conv
python3 research/operators/qwen_ops/record.py smoke conv
python3 research/operators/qwen_ops/record.py ubsan conv
python3 research/operators/qwen_ops/fidelity.py conv
```

The final registered profile's results are in `experiments/20261109-35-qwen-operators/runs/conv-*`. The float reference uses dequantized integer inputs/taps, not fresh real-valued samples or BF16 weights. Errors are 40 output observations from 10 four-token chunks per F. The registered threshold (<=2^-F) cannot fail by construction, because a single floor keeps the error under 2^-F; it checks the implementation, not a fidelity margin. Wrong-history-use hostile proofs alter a multiplication operand while preserving its product, so they test actual committed wire linkage, not external history identity. `record.py final` additionally runs `proof.bin conv 12 1 history-control`: a period-four input perturbation changes two incoming history words and two new inputs, preserves every four-tap sum with equal fixed taps, and yields a different valid proof for the SAME public outputs. Both proofs are expected to verify. This is an explicit negative result for external history binding, recorded separately from the local hostile suite. It is the narrowest case (taps fixed, history changed); the reviewer's constructions above show the wider fact that taps and inputs are unbound too.
