# Signed, staged-floor KDA micro-slice (not FP32 or checkpoint support)

Stacked on PR16 exact `8fca2c4b9ffb5d5180df51095d5f52a33df4a207`.
This is a deliberately smaller numerical-semantics step: **one token, one head,
key/value dimension 1**, synthetic inputs, no weights. It does not replace PR16's
two-token dimension-2 rational continuity test. Existing prerequisite machinery
is unchanged. Its fixed 64-row limits motivate this bounded fixture; no full
configured-shape cost or performance improvement is claimed.

## Exact statement

Scale is 4. Stored integers represent real values divided by 4. Public inputs
`(state, decay, key, value, beta, scaled_query) = (-3,3,-3,2,3,3)` are fixed,
signed four-bit values. Decay and query are already prepared, not generated.
Each multiplication below is rounded **separately toward negative infinity**:

```
D = floor(state * decay / 4)
M = floor(D * key / 4)
A = value - M
Delta = floor(A * beta / 4)
U = floor(key * Delta / 4)
S = D + U
O = floor(S * scaled_query / 4)
```

Every rounded result plus A and S must lie in [-8,7]. Overflow rejects the
statement, never saturates or wraps. Public S=O=-3. This is a chosen toy fixed-
point contract, NOT the publisher's numerical contract, nearest-even rounding,
BF16, FP8, or a quantized checkpoint format. For larger key dimensions, reduction
rounding would need a separate specification; this dimension-1 case has no
multi-term reduction ambiguity.

All constraints use the SAME committed product oracle:

* Each rounded multiplication binds `a*b = 4*q+r`, with signed q in [-8,7] and
  remainder r in [0,3]. The nonnegative remainder specifies floor even for
  negative products (e.g. -9 = 4*(-3)+3).
* Signed range decomposition binds `x+8 = sum(2^i*b_i)` for four bits. Remainders
  use two bits without offset. Each bit has a product gate b*b plus a wire
  equality between its operands and an affine equality between product and b.
  Thus b is 0 or 1 in Goldilocks, not merely an unchecked host hint.
* Add/subtract and all reused values are bound with affine/shared-wire rows.
  Rounded products use signed bounded operands; their integer magnitude is at
  most 64, and quotient/remainder expression magnitude at most 35. Differences
  are far below Goldilocks P. Field equality therefore cannot conceal integer
  wraparound. The fixed public inputs are visibly in range; there is no dynamic
  admission API or host-only validation of private values.

56 product gates (64 columns), 22 public coordinates, 42 wire equalities,
57 affine relations. Public initial-state provenance remains external.

## Independent checks and limits

`reference.py` has a direct Fraction-based integer reference separate from graph
lowering (which uses divmod). It exhaustively checks all 256 signed four-bit
operand products, and evaluates 4,097 deterministic reference cases: 1,940 fit
all intermediate bounds, 2,157 overflow and reject. These random cases are
**reference-only**, not 4,097 proved statements. The C++ proof uses one fixed
circuit/fixture.

For comparison, the script pins scalar float32 operation order to the post-gate
algebra of Transformers `recurrent_kimi_delta_attention` lines 462-513 at
`f90e93c4f83974f634860e246cdfd2c68666d605`. Standard-library struct explicitly
rounds each scalar operation to IEEE binary32; these tiny dyadic inputs fit the
intermediate binary64 evaluation exactly. This is NOT execution of PyTorch,
the decorated fallback, exp, normalization, or the fused FLA kernel. Torch is
not installed; no dependency installation or spend was made. The comparator
is appropriate only for this scalar post-gate domain, not a general IEEE
emulator or a claim of matching serving kernels.

The fixed-point fixture yields state/output (-0.75,-0.75), while the scalar FP32
comparison yields (-0.6064453125,-0.454833984375). Maximum state/output absolute
divergence across accepted reference cases is 1.734375. **Numerical equivalence
fails**, as expected at this deliberately coarse scale. This report is not an
accuracy or model-quality benchmark.

`provenance.py` re-fetches only pinned publisher config and Transformers source,
checks exact sizes/SHA256 against PR16, and records `provenance.json`. Model
config revision is `46a050bec13002ad29ee795c16e61cf4fa3c4a9c`; configured head
dimension is 128. Architecture provenance does not imply checkpoint support.

## Reproduction and malicious witnesses

From repository root:

```
python3 research/operators/glm_kda_fixedpoint/provenance.py
python3 research/operators/glm_kda_fixedpoint/record.py
```

Recorder writes exact commands, compiler/platform, hashes and timings. It
regenerates reference artifacts, compiles CPU C++ and runs the actual research
verifier. No prerequisite files are modified. Small deterministic test security
parameters are inherited, not a production security/hiding claim.

50 complete hostile proofs preserve every public coordinate and product gate:
38 individual bit corruptions, nine private quotient/remainder corruptions,
and three paired quotient/remainder changes preserving `a*b=4*q+r` (negative
remainder/truncation toward zero, oversized remainder, out-of-range quotient).
Hostile provers bind the true statement but substitute truthful local false
linear targets; unchanged verifier rejects. Also tested: every public-coordinate
mutation, sampled byte flips/cuts, trailing bytes, cross-domain rejection.
These are not exhaustive attacks or a formal soundness proof.

Next: wider reusable range machinery with independent review, two-token signed
state continuity and multi-key reduction policy, then actual gate/convolution
producers and pinned framework execution. No exp/sigmoid, normalization,
projections, post-norm, quantization conversion, sparse attention, MoE, mHC,
checkpoint execution, GPU results, or new Lean theorem is supplied here.
