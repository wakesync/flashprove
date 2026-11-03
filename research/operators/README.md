# Bounded bias-corrected top-k constraint prototype

Status: executable **constraint satisfaction**, not a cryptographic proof. No upstream
`cp_prove`/`cp_verify`, sumcheck, commitment, transcript, privacy or Lean theorem is
provided for this operator. All witness cells are disclosed. No admitted extension
profile is changed. DeepSeek/GLM remain unsupported models.

## Why this milestone

Upstream `docs/model.md` (routing steps 1-3) implements clamped top-1, lowest-index
ties and scaling of expert input. It does not supply the requested top-k normalized
router. `blocks/toy/product.h` supplies a real committed product-vector protocol
(SEND, ZERO, PSC, IOPP), but its statement is only existence of a*b=c, with no public
operand relation. Feeding independently generated multiplication rows into that toy
would NOT bind reused wires, selection, normalization or public inputs. We deliberately
do not market that as a router proof. `blocks/iop/rng.h` and `lkp.h` exist; integrating
these and the required linear wiring into a configured committed relation still needs
its own planner, binder, verifier and soundness review (see `blocks/README.md` limits).

This milestone instead compiles the entire small relation to explicit quadratic
Goldilocks constraints, including ranges and wire linkage. An independent C++ evaluator
uses the actual unchanged `blocks/field/field.h`. This is a stronger executable
specification than two sorting references agreeing, but is NOT a cryptographic proof.

Source motivation: pinned Transformers GLM `f90e93c4f83974f634860e246cdfd2c68666d605`,
`modeling_glm5_next.py` lines 153-180 selects with corrected scores, weights with original
scores. DeepSeek publisher revision `314113f8a7dadb388215396ba5fbee2c610a04d6`,
`inference/model.py` uses a different nonlinear score and k-dependent normalization.
This prototype's canonical ties, eight-bit ranges, floor division and always-normalize
policy are NEW semantics, not fidelity to either source. Sources were inspected in the
planning lane's pinned snapshots; no weights were downloaded.

## Exact relation v0

- Shape fixed by verifier: 2 <= n <= 8, 1 <= k <= n. One group only.
- Public inputs: unsigned scores s_i in [0,255], biases b_i in [-128,127], ordered
  selected indices and integer normalized weights. Wire encoding for bias is b_i+128.
- Private witness: n*n Boolean permutation matrix, multiplication outputs, range
  decompositions, division remainders. All are disclosed by this prototype.
- Rank key K_i=n*(s_i+b_i+128)+(n-1-i). Strict descending permutation of all keys
  makes its first k elements exactly top-k, ties lowest expert index. Boolean rows
  and columns each sum to one, so no missing/duplicated expert is permitted.
- D=sum selected ORIGINAL scores. D>0 is mandatory; no epsilon or saturation.
- w_j=floor(256*s_selected/D). Constrain w_j*D+r_j=256*s_selected with
  0<=r_j<D. Weights independently floor and need not sum to 256. k=1 also normalizes.
- No expert weighted-output aggregation, nonlinear logits-to-score map, group filter,
  routing scale, FP8/FP4 conversion, recurrent state, or model/tokenizer commitment.

Every equality is A(w)*B(w)=C(w) modulo p=2^64-2^32+1, linear combinations permitted.
Boolean constraints and bit reconstruction enforce unsigned ranges. Keys are <=4087;
rank differences are checked via 12 bits. D<=2040, D-1 and remainders use 11 bits;
weights use 9 bits (the quotient equation further forces <=256). Largest quotient
product is <=511*2040=1,042,440. Negative rank or remainder slacks reduce near p and
cannot fit those ranges. All integer expressions and differences are far below p,
so these equalities cannot silently wrap to satisfy the intended integer relation.
No claim about arbitrary wider shapes follows.

`Circuit.check` fixes the constant wire to one and public assignments independently
of witness. Constraint structure depends only on n,k, not witness values. C++ checks
an exported trusted constraint instance: it is NOT a network interface that can accept
prover-chosen constraints/public assignments as a statement. The entire instance must
come from the verifier. Both checkers assume trusted code and local files.

## Reproduce

```
python3 research/operators/record.py
```

Python standard library and g++ with C++17, no installs or GPU. Tests include seeded
random cases, exhaustive small score/bias domain, every permutation for two four-expert
cases, recomputed false selection/duplicate/quotient witnesses, zero-denominator and
boundary cases, fixed circuit structure, every-wire mutations and canonical encoding.
C++ independently checks honest/dishonest witnesses and every single-wire +1 mutation
for one fixture. Mutations demonstrate coverage, not an exhaustive soundness proof.

Next blocker: wire this exact relation into a real commitment/sumcheck/IOPP with shared
wire consistency, verifier-fixed public input binding, constrained range proofs and
versioned domain separation. Need malicious *proof* synthesis, independent verifier
review, Lean obligations and security/mask accounting before claiming proof coverage.
The deliberately O(n^2) full sorting permutation is only a bounded toy, not a scalable
expert router. Arithmetic policy remains subject to coordinator review.
