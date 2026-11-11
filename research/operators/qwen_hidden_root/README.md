# Hidden-root window handoff for the DeltaNet prototype (issue #93)

Registration and receipts: [`experiments/20261111-93-hidden-root-handoff`](../../../experiments/20261111-93-hidden-root-handoff/). Research prototype only: one synthetic head, D8/F12, C tokens per window, N windows.

## What is proved, per window

`window.cpp` builds one product/affine proof per window (the SA/M1b recurrence lowering from `../qwen_handoff/lowering.h`, unchanged) and adds:

1. **Incoming opening.** The first token's state cells, the incoming 3-tap history and a private salt are absorbed by an in-circuit sponge (width 12, rate 8, capacity 4, x^7, 8 full + 22 partial rounds). The 4 squeezed words are pinned to the verifier-held incoming commitment. The state cells are also RNG range cells (|x| < 2^23), and the public initial-state pins of the original lowering are removed.
2. **Recurrence** from exactly those cells for C tokens, with public token inputs and public outputs from the statement.
3. **History shift.** Outgoing history equals the suffix of incoming history plus this window's public pre-conv inputs (pinned).
4. **Outgoing commitment.** The last token's state cells, outgoing history and a second salt are absorbed by a second sponge; its 4 words are pinned to the prover's claimed output commitment, which is part of the transcript-bound statement. The public final-state pins are removed.

Sponge capacity is the SHA-256 (natively, by the verifier) of the context: F, D, C, N, request, layer, policy, boundary index, model label, weights label. Window k opens boundary k and emits boundary k+1.

## What the verifier holds and recomputes

`window.bin verify statement c_in c_out - proof` opens exactly those four files. The statement has the public descriptor (D, F, C, N, k, request, layer, policy, model and weights labels), token inputs, pre-conv inputs and outputs. It contains no boundary state or history. The verifier derives the relation from its own statement and both commitments; the prover's witness directory is never read. The chain verifier (`run.py`, `chain_verify`) holds the per-window statements, N and R0, feeds each window's claimed output commitment to the next window as its input, and requires exactly N windows.

## What is not covered

- No soundness level (target 10, work 6, deterministic toy coins). Not zero-knowledge: "hidden" means the verifier is not handed the state, not that the proof hides it.
- The sponge parameters are unvetted (a Poseidon-shaped stand-in, not Plonky2's instance).
- No recursion or aggregation; chain truncation is caught by the verifier-held N, outside the arithmetic.
- R0 is produced by the trusted harness. Model/weights are synthetic labels. No weights, convolution or real-checkpoint binding.

## Reproduce

From the repository root, with Python 3 + NumPy and g++ (pin cores on a shared host):

```sh
python3 research/operators/qwen_hidden_root/run.py build --out research/operators/qwen_hidden_root/work/repro
python3 research/operators/qwen_hidden_root/run.py debug
python3 research/operators/qwen_hidden_root/run.py suite --out research/operators/qwen_hidden_root/work/repro
python3 research/operators/qwen_hidden_root/count.py
```

`debug` uses seed 909, D4, C1, N3 (disjoint from the registered seeds 201-205, D8, C2, N3). `build` and `suite` refuse to overwrite existing receipts; use a fresh `--out`. `FP_CORES` sets the taskset range (default 6-9). The registered run went through the host's heavy-job gate.
