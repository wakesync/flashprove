# The Qwen3.8-27B port: where it stands

This page tracks the work to run Qwen3.8-27B, and its abliterated checkpoint, under proof. It is a
living page of the research fork, kept in plain language. Tracking issue:
[#32](https://github.com/wakesync/flashprove/issues/32).

**Today no part of Qwen3.8-27B can be proved end to end.** What exists is one piece of one layer,
proved on a CPU with test-level security settings, on made-up inputs. Everything else on this page
is a design, a count or a plan, and is marked so.

Last updated: 2026-11-10. Rule for this page: a step is "done" only if its evidence is merged on
`main`. Work in an open pull request is "in review". Anything else is "planned".

## Why Qwen is not a small change

FlashProve proves Llama 4 Maverick's integer model. Qwen3.8-27B is smaller (6.7% of the committed
weights) and has no routing, but three quarters of its layers are a different kind of layer, a
Gated DeltaNet. Such a layer keeps a memory: for each of its 48 heads a 128 x 128 table of numbers,
the state, that every token updates. FlashProve had no way to prove a layer with a carried state.
Building that is the port. The feasibility study is in
[research/ports/qwen3.8-27b/FEASIBILITY.md](../research/ports/qwen3.8-27b/FEASIBILITY.md).

## Milestones

| step | what it is | status | evidence |
|---|---|---|---|
| Feasibility | desk study: architecture, what is new, why Qwen first | done | [FEASIBILITY.md](../research/ports/qwen3.8-27b/FEASIBILITY.md) (PR #28) |
| **M1** | one DeltaNet head at real size, 4 tokens, proved on a CPU | done, with a negative result: proofs worked, but a value outgrew its allowed range on heavy-tailed inputs | [RESULTS](../experiments/20261104-11-qwen-deltanet-m1/RESULTS.md) (PR #47) |
| **M1b** | the same head with a cheaper range check | done: passed its registered thresholds | [RESULTS](../experiments/20261105-32-qwen-deltanet-m1b-lookup/RESULTS.md) (PR #63) |
| **M2 design** | design of a whole head at 16 tokens; a verifier entry that checks its own inputs | in review, changes requested | PR [#66](https://github.com/wakesync/flashprove/pull/66) |
| Operator gadgets | pinned integer tables; small proofs of conv, norms, table lookups | in review | PR [#67](https://github.com/wakesync/flashprove/pull/67), issue #35 |
| Real weights, layer 0 | ranges and accuracy of the integer arithmetic on the real checkpoints; what abliteration changes | in review | PR [#68](https://github.com/wakesync/flashprove/pull/68), issue #8 |
| State commitment | how to carry the state between parts of a proof without committing all of it | planned (experiment under way) | issue #34 |
| **Lookup build** | the M2 head built with lookup-checked remainders | planned (build under way) | issue #32 |
| **M3 design** | the first statement where the weights are committed and the proof is needed | in review (this design) | [DESIGN](../experiments/20261109-32-qwen-m3-design/DESIGN.md), [RESULTS](../experiments/20261109-32-qwen-m3-design/RESULTS.md) |
| **M3a** | one head, then one full DeltaNet layer, against committed weights, on a CPU | planned | DESIGN section 9 |
| Arithmetic gate | choose number formats that are accurate on real weights and stay in range | planned; blocks everything below | issue #8 |
| **M3b** | a block of 4 layers in the GPU prover | planned; needs a GPU decision | DESIGN section 9 |
| **Full model** | all 64 layers and the output head; then real weights; then the abliterated checkpoint | planned | DESIGN sections 9 and 10 |

## What is proved, recomputed and not covered at each step

"Recomputed" means the verifier works the value out itself from public inputs, so no proof is
needed for it. A proof only earns its keep where the verifier cannot do that.

| step | proved | the verifier recomputes | not covered |
|---|---|---|---|
| M1, M1b (done) | the state update and the head's output for 4 tokens, for inputs that are all public | nothing: it is given every input | everything else in the layer; any link to weights. Since all inputs are public, a verifier could have computed the result itself |
| M2 design (in review) | by design: the same for 16 tokens, plus the head's output norm | conv, SiLU, the q/k norm and the gates, from public inputs | the layer's matrices, the MLP, other layers. Still all-public: a rehearsal of the machinery, not a useful proof |
| M3a (planned) | one head from the layer's input to its output, **against committed weights**; then a layer as 48 head proofs and one MLP proof | the layer's public input checks; adding up the 48 public head outputs | the link between layers; the state carried from an earlier chunk; attention layers; the output head |
| M3b (planned) | a 4-layer block with everything between its ends committed, including the carried state | only the commitment ID and public-input checks | the other 60 layers; real weights |
| Full model (planned) | every layer from token ids to the next token, against one commitment | only the commitment ID and public-input checks | how close the integer model is to the real one; vision; sampling; whether the commitment is the advertised checkpoint |

## What is known about cost

Nothing has been measured for Qwen beyond the single head on a CPU (about 40 seconds to prove 4
tokens of one head, with test settings; PR #63).

Counted, not built ([RESULTS](../experiments/20261109-32-qwen-m3-design/RESULTS.md)):
- The first statement with committed weights (one head, 16 tokens) is 8% larger than the M2 head
  and fits the same CPU harness, provided remainders and table steps are checked by lookups.
  Without lookups it fits for a single token only.
- If every state is committed for every token, the state is 88% of everything a request commits.

Whether the full model fits one 141 GB GPU is not known. The M3 results give an estimate, built on
another model's published rates and on a GPU sub-proof that has not been written. It is in the
RESULTS file with its assumptions and should not be quoted as a result.

## Open risks

1. **Accuracy of the integer arithmetic.** On real layer-0 weights the number format used so far
   keeps its ranges but gives a head output far from the real model's, and a finer format breaks
   the ranges (PR #68, in review). Until a format passes both, a proof would be about an integer
   model that does not track Qwen.
2. **The state.** Committing it every token is too large for a full model in the only form that has
   been built. The cheaper strategies change the arithmetic and are not built (issue #34).
3. **No GPU code for DeltaNet.** All Qwen proofs so far ran on a CPU research harness.
4. **Lookups.** The planned statements depend on lookup compositions that are still being built.
5. **Ranges are measured on one layer.** Deeper layers are unmeasured.
6. **Limits of the upstream programs.** The verifier does not say YES for a model without routed
   experts, with a query width different from the stream width, or with head dimension 256
   (issue #35).
7. **No machine-checked theorem.** Upstream's Lean soundness theorem covers the Maverick-shaped
   model only.
8. **Security settings.** Every Qwen proof so far used a 10-bit research target. None is a
   production proof.
9. **Which checkpoint.** The abliterated checkpoint differs from stock in 70 of 1,199 tensors, all
   in layers 17 to 51 (PR #68, in review). A proof of early layers cannot tell them apart, and file
   hashes cannot identify the model. Identity has to be bound tensor by tensor.

## Glossary

- **Integer model:** the network with weights and activations as whole numbers. Proofs are about
  this model, not the floating-point one.
- **Committed:** fixed by a hash that the prover publishes, without showing the values. The verifier
  checks claims about committed values without seeing them.
- **Public input:** a value the verifier holds itself.
- **Witness:** a value inside the proof that is neither public nor separately committed.
- **Gated DeltaNet:** Qwen's linear-attention layer. Each head keeps a state and updates it at
  every token with a decay and a correction.
- **State:** a head's 128 x 128 table of numbers. A layer has 48.
- **Head:** one of the parallel units of a layer. "V head" is a value head; three V heads share one
  query/key head.
- **Chunk:** a run of consecutive tokens proved together, with the state handed from one chunk to
  the next.
- **Range check:** the part of a proof that shows a hidden number is small, so that an equation
  that holds in the proof's arithmetic also holds for whole numbers.
- **Remainder:** what is left over when the integer model divides and rounds. It must be shown to
  be in range for the rounding to be the right one.
- **Lookup:** a proof step that shows a hidden value appears in a public table.
- **Research harness:** the CPU test setup used for M1, M1b and the designs. Not the GPU prover.
- **Arm A, arm B:** two ways to check remainders: bit by bit (A) or by lookup (B).
- **F:** the number of fraction bits in the fixed-point numbers. F = 12 means steps of 1/4096.
- **Counted, extrapolated, measured:** a count is an exact size from a model; an extrapolation is a
  count times a rate borrowed from other runs; only a measurement comes from running the thing.
- **Abliterated:** a checkpoint edited to remove a behaviour, here refusals. Same architecture as
  the stock model, different weights in some layers.
