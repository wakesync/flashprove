# Two-chunk DeltaNet handoff, bounded research prototype

Issue #93. Registration and receipts: [`experiments/20261110-93-handoff`](../../../experiments/20261110-93-handoff/). This is a **joint proof over two chunks**, not a resumable segment chain or a model-support claim.

## What the proof checks

`handoff.cpp` puts two SA/M1b recurrence traces in one product oracle. It removes their public final-state pins and the second chunk's public initial-state pins. It adds coordinate-by-coordinate equality between the first chunk's last state and the second chunk's first state. That equality is an affine relation tested inside the same product/RNG proof as the recurrences. The intermediate state is not in the public statement.

Each chunk also has witness cells for its incoming/outgoing three-token history, its pre-conv token inputs, and its descriptor. The proof pins pre-conv inputs to the verifier's statement, proves the outgoing history is the suffix of incoming history plus this chunk's inputs, and equates the first outgoing and second incoming histories. A consistent two-sided history shift therefore does not bypass the history relation. This proves **shift-register provenance**, not the convolution, nor that the pre-conv inputs produce the post-conv recurrence inputs.

The descriptor pins F, D, C, T, request, layer, fixed two-chunk policy, chunk count, index, start, length, and both synthetic model and weights identifiers. All statement bytes, including the initial root, are also transcript-bound. F is the verifier's F when deriving the arithmetic, not the witness fixture's F. The sampled mixed-F attack carries F13 reference states into an F12 circuit, not a silently retargeted verifier.

## Verifier boundary

The complete verifier command is:

```sh
research/operators/qwen_handoff/work/handoff.bin verify verifier.stmt - joint.proof
```

It opens only `verifier.stmt` and the proof. It never reads a witness directory, fixture, manifest, Python chain result, or prover descriptor. `template_part` supplies zero placeholder intermediate witness values for relation construction; none of those values becomes a boundary target. Public initial state, inputs and outputs supply the required constants. The standalone verifier runs as a separate process in the suite. The harness generates the trusted statement from its synthetic reference; this is a trust-boundary test, not an authenticated external deployment.

The initial root is SHA-256 of the domain `fp-handoff-initial-v1`, then little-endian signed 64-bit initial state and history words. The verifier owns both that root and its public opening. It checks the hash **outside** the arithmetic proof, pins the initial words inside the proof, and binds the entire statement into the transcript. This is not an in-proof SHA-256 gadget or an opening of a hidden initial state. The Python generator uses `hashlib`; the C++ public-opening check uses `sha256.h`.

The model and weights identifiers are digests of fixed synthetic labels. They cannot be substituted under an unchanged statement, but the proof does not establish any actual checkpoint, weights, projection or model computation. A verifier deliberately asking for another label is asking another statement.

## Fixed slots and hostile evidence

The circuit has exactly two physical slots of C tokens. A split/drop/truncation/prefix proposal is encoded as different claimed chunk count/ranges/lengths in those slots. Missing tokens are padded with identity steps where applicable. The full prover emits every protocol message with locally true linear targets for the hostile table. The unchanged verifier checks the original targets. Rejection is not a Python header comparison or a prover refusing to produce bytes.

A three-chunk split is **not** three separately valid proofs stitched here: this prototype has no variable-length segment parser. Likewise, a prover can internally schedule a correct computation however it likes and then supply the correct fixed two-slot witness; such private scheduling is not distinguishable or forbidden. The negative claim is about changed committed descriptors and missing/changed constrained computation, not invisible implementation choices.

`lowering.h` is an adapted copy of #71's lowering, not a new arithmetic model. It uses supplied M/delta/S witness values and low remainder bits even when a hostile floor is inconsistent, so every product gate can hold while linear constraints fail. The verifier always derives a separate canonical relation. Replacing the prover's linear targets does not replace the verifier's targets.

## Range and soundness scope

The admitted verifier domain is F12, D at most 32, C at most 16, and T exactly twice C. Counts at larger shapes are formulas only. As in M1b, honest state/M/delta limbs are below 2^18, while the inherited RNG statement proves the relaxed signed 2^23 window. Public gates and k/q are bounded by 2^12; v/output by 2^31. With D at most 32, these bounds keep the M numerator below 2^52, the state-update numerator below 2^54 (including the two relaxed delta limbs), and the public-output comparison below 2^44 in absolute magnitude. Each floor remainder has its exact Boolean width. The resulting integer equality differences are below the Goldilocks modulus, so this extension does not need the unsound wide SB floors from #71. History and descriptor cells need no separate range gadget: they are pinned to small public constants or linked, transitively, to those constants.

The proof parameters are intentionally low research security with deterministic toy coins. This is neither a production soundness level nor a privacy claim. No GPU/whole-model memory fit, performance improvement, checkpoint support, real-weight fidelity or recursive continuation is established.

## Reproduction

From repository root, with Python, NumPy and g++ available:

```sh
python3 research/operators/qwen_handoff/run.py build --out research/operators/qwen_handoff/work/reproduction
python3 research/operators/qwen_handoff/run.py debug
python3 research/operators/qwen_handoff/run.py suite --out research/operators/qwen_handoff/work/reproduction
python3 research/operators/qwen_handoff/count.py
```

For a shared research host, run build/suite through its approved heavy-job gate and pin at most six cores. The registered suite uses five fixed seeds; debug uses a disjoint seed/shape. The build and suite commands refuse existing receipt paths. The commands above use a fresh receipt directory; choose another fresh name for another rerun. The original registered invocation omitted `--out` and wrote under the experiment directory. Do not overwrite committed files. The binary and generated witnesses/proofs stay under ignored `work/`.

Counts are core product columns before padding, aligned product columns, affine relations, and range cells, not field-row entries or bytes. `count.py` uses a closed-form inventory independent of the C++ relation construction; the suite compares the counts with the built relation for every honest seed. Initial public opening bytes, transcript hashing, RNG lookup planes, masks, proximity messages, proof bytes and model-wide operators are not included in the core-column formula. No cross-backend ratio is claimed.
