# Conv1d carried-history binding, bounded research prototype (issue #35)

Registration and receipts: [`experiments/20261111-35-conv-history-binding`](../../../experiments/20261111-35-conv-history-binding/). Research only. Not Qwen support, not a production verifier, no model claim.

## Problem this closes

PR #67's four-tap causal convolution (`research/operators/qwen_ops/proof.cpp`, `conv()`) commits its three incoming history words as cells the prover chooses freely. Its registered negative control (`history-control`) changes two history words and two new inputs consistently, keeps every output, and both proofs verify against the SAME public statement. The history is not tied to anything outside the proof.

## What the bound profile checks

`conv_history.cpp` keeps the #67 relation unchanged (one channel, taps w[0..3], history H[-3..-1], new inputs X[0..3], y[t]=floor(sum_j w[j]*input[t+j]/2^F), the same range bits and remainders) and adds, for the bound profile only:

1. **A verifier-owned tail root.** `R = SHA-256("fp-conv-tail-v1" 0x00, F as u32 LE, segment index as u64 LE, 3 as u32 LE, three words as i64 LE)`. The verifier holds R before it sees the proof: the genesis root it was given, or the root returned by its previous accept.
2. **A public opening of the incoming history.** The statement carries the three words. The verifier hashes them and refuses unless the hash equals the held R. This check is **outside** the arithmetic proof (as in PR #98's initial root).
3. **In-proof pins.** Three one-term affine relations pin the three committed history cells to the opening, and three more pin the segment's last three committed inputs X[1],X[2],X[3] to a public outgoing opening. Targets come from the verifier's statement, never from the witness.
4. **Statement in the transcript.** The profile text in the configuration digest includes the segment index and both roots, so a proof for one statement does not verify under another.
5. **Handoff.** On accept the verifier returns `H(F, segment+1, outgoing opening)`, which is the root it must hold for the next segment.

The unbound profile is exactly the #67 statement (operator, F, four outputs) and is kept in the same binary as the named negative control. Its relation count (294 columns, 573 relations) equals #67's committed `conv-summary.json`. The bound profile adds 6 relations (579), 0 columns.

## What the verifier recomputes

The fixed circuit, every relation target (outputs, history pins, tail pins), the configuration digest, and the SHA-256 of the incoming opening. It does not receive taps or new inputs X[0].

## What is NOT bound (read this)

- **The kernel is still free.** Taps are committed cells the prover chooses. The #67 reviewer's taps (0,0,0,-S) construction (y[t]=-X[t]) still works here: the prover picks X[0..3] and simply publishes X[1..3] as its outgoing tail. What changes is only that the *next* segment must start from that published tail, and that this segment must start from the held root. Outputs are still not tied to any model. Kernel binding is the M3 statement (PR #70) / weights work, not this PR.
- **Inputs have no provenance.** The tail opening binds the next segment to *this* segment's committed inputs, not to any model's projections. Model-input provenance is out of scope.
- **No hiding.** History and tail words are public. A hiding commitment (opening inside the proof) is not built; there is no in-circuit hash.
- **Genesis trust.** The first root is whatever the verifier was given. Nothing here says the genesis history is zero or correct.
- **Statement-level checks are statement-level.** Several hostile sub-cases are rejected by the outside root comparison, not by the proof; RESULTS.md lists which mechanism rejects each case.
- Research security target 10 bits per round, with toy deterministic coins. No whole-proof soundness figure, no production security.
- This file is a copy of the #67 conv circuit, not the #67 binary. Differences: no 120-term chunking in `sum` (conv sums have 4 terms), and the range gadget does not refuse out-of-range witnesses so hostile witnesses can be proved (only affine targets fail).

## Reproduce

From repository root, g++ C++17 and Python 3 standard library, no downloads:

```
python3 research/operators/qwen_conv_history/run.py build --out <fresh dir>
python3 research/operators/qwen_conv_history/run.py suite --out <fresh dir>
python3 research/operators/qwen_conv_history/run.py build --ubsan --out <fresh dir>
python3 research/operators/qwen_conv_history/run.py suite --ubsan --out <fresh dir>
python3 research/operators/qwen_conv_history/run.py summary --out <fresh dir>
```

Without `--out` the commands write to the experiment's `runs/` and refuse existing receipts. `run.py debug` uses seeds 101..103, disjoint from the registered 1..10, and writes only to ignored `work/`. The suite is about one CPU-minute; on a shared host pin it to a few cores (the registered run used two).
