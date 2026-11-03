# GLM-5.3-Flash KDA algebra slice, not model support

This is a reproducible reference-versus-proved **two-token recurrent algebra
slice**, with synthetic values, one head, key dimension 2 and value dimension 1.
It is not a checkpoint execution, a complete attention block, fixed-point KDA,
or proof of FP32/BF16/FP8 serving. No weights are downloaded.

## Architectural provenance

Publisher config:
https://huggingface.co/zai-org/GLM-5.3-Flash/blob/46a050bec13002ad29ee795c16e61cf4fa3c4a9c/config.json

Matching Transformers reference, `recurrent_kimi_delta_attention`, lines 462-513:
https://github.com/huggingface/transformers/blob/f90e93c4f83974f634860e246cdfd2c68666d605/src/transformers/models/glm5_next/modeling_glm5_next.py

Both immutable URLs were fetched again successfully and byte-compared with the
prior research snapshots. `provenance.json` records URL, bytes and SHA256.
This establishes the source of the recurrence, not equivalence to publisher
fused serving kernels. Actual configured head dimension is 128, not this fixture's
2. The reference casts to float32, optionally normalizes q/k, scales query by
1/sqrt(key dimension), and exponentiates g before the algebra below.

For each token, the selected algebra is:

1. D[i,j] = S[i,j] * decay[i]
2. memory[j] = sum_i D[i,j] * key[i]
3. delta[j] = (value[j] - memory[j]) * beta
4. S_next[i,j] = D[i,j] + key[i] * delta[j]
5. output[j] = sum_i S_next[i,j] * scaled_query[i]

`reference.py` evaluates these equations directly using exact rational numbers.
Its separate graph builder emits `fixture.h`, mapping rational values into the
Goldilocks prime field through denominator inversion. Selected dyadic fixture
results also agree exactly with Python binary64 evaluation. **Neither this
comparison nor the field embedding establishes general float32 equivalence.**
There is no rounding, saturation, range enforcement or fixed-point scale here.

## Mapping to the actual proof machinery

All multiplications occupy the SAME committed three-row product oracle provided
by PR #15, based on PR #14. Repeated operands use equality rows. Sums/subtractions
use affine rows with a multiply-by-one storage cell. Public inputs, initial
state, both outputs and final state use coordinate rows. Two steps share actual
committed state cells: token two cannot substitute an unrelated state.

The fixture has 30 product gates in 32 columns, 38 public coordinates, 16 shared
wires and 10 affine rows. No model operations are checked solely in a detached
host evaluator. The verifier fixes the circuit and public values and uses a new
transcript label `0x474b4431`; the generic affine domain rejects its proofs.
There is no generic model/config admission API. Trusted in-memory run objects
are inherited from the prerequisites, with no untrusted statement parser.

Run from repository root:

```
python3 research/operators/glm_kda_slice/record.py
```

This regenerates the fixture, compiles the CPU proof test and records exact
commands, timing, output and hashes in `evidence.json`. C++ proof acceptance uses
the existing research verifier, NOT `cp_verify`, a Lean theorem or an independent
cryptographic implementation. Target 10 and query work 6 are deliberately small
test settings, **not a security level**. Deterministic coins are for fixtures,
not a production hiding claim. Timings are single bounded test receipts, not
comparative performance benchmarks.

Three malicious provers commit complete, valid-product tables while preserving
all public input/output cells: corrupt the subtraction, disconnect the second
token's carried state, or change the second delta operand. They bind the true
statement but substitute truthful local wire/affine targets inside their own
IOPP. The unchanged verifier must reject these complete proofs. Public endpoint
mutations, proof-byte mutations, truncations, trailing bytes and domain mismatch
are also tested. This is not exhaustive adversarial coverage.

## Explicit boundaries and next implementable step

The first state is PUBLIC and externally supplied. Linkage between these two
tokens is proved, but provenance of a nonzero state from an earlier prefix is
not. Zero-init policy or a preceding authenticated transition is a caller duty.
Inputs decay, beta and scaled query are already prepared. Their derivation is
not proved. No full configured-shape cost extrapolation is justified.

Still unsupported: exp and sigmoid gates, q/k L2 normalization and query scale,
causal convolution/padding, projection weights, post-attention gated RMSNorm,
chunked-prefill equivalence, float/integer rounding and range constraints,
cache/prefix authentication outside these two steps, sparse attention/indexer,
MoE routing and expert execution, mHC/Sinkhorn, quantization conversion,
embeddings/tokenizer, vision/video, MTP, complete decoder/head or model admission.
No new soundness, zero-knowledge or Lean correspondence theorem is supplied.

The next useful implementation is a range-checked fixed-point KDA transition
with explicitly specified staged rounding (quotient/remainder and signed bounds)
and a pinned float32 fallback comparison over boundary inputs. Products and
linear rows alone do not prove those integer semantics. Only then connect gate
and convolution production to this recurrence and measure divergence. Full
checkpoint support also requires authorized weights/resources and independently
validated conversion. PR #14/#15 review and merge decisions remain independent;
this slice does not certify those prerequisites or merge them.
