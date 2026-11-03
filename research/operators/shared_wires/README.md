# Shared-wire product proof, research v1

This adds a small actual upstream commitment/PSC/IOPP composition to the V3 public-coordinate prototype. It is NOT a top-k router proof, model support, or a reviewed security theorem.

## Exact statement

Verifier-fixed length is a power of two, log length 1..20. The witness consists of three base-field rows a,b,c, with a[i]*b[i]=c[i] at every column. There are 1..64 verifier-fixed public coordinates and 1..64 verifier-fixed wire equalities. An equality states that two specified cells in these same rows have equal field values. The remaining cells are existential. Public coordinate values are canonical Goldilocks elements. Equalities are field equalities, not integer range assertions.

The new domain label is `0x46505731` and configuration name is `research-shared-wire-product-v1`. Both public coordinates and the ordered equality topology enter Binder statement handles before prover messages. Each equality adds the linear row `left - right = 0` to the SAME product oracle group, before its IOPP. No second witness or detached commitment is used. Each equality uses two MAIN units, with flattened index `row + 4*column`. Duplicate, reversed and self equalities are permitted; all consume one batching row each, including self equalities that cancel.

The V3 planner is reused with coordinate count PLUS equality count for both first-stage GroupLoad and plan_iopp. Product PSC and mask accounting are unchanged. Configuration text is replaced before binding with the new name and both counts; it is configuration metadata, not a hidden constraint or extra round. This accounting is a proposal pending independent review.

`wire_size` is the supported constructor. As with upstream and V3, run/plan objects and shape are trusted in-memory inputs, not untrusted wire data. Do not mutate shape, counts or plans after sizing. No network parser exists. Helpers assume the specific three-row upstream product oracle. No production API or new hiding claim.

## Test and receipt

From repo root: `python3 research/operators/shared_wires/record.py`.

The recorder compiles C++17 with g++ and CPU backend, then runs bounded tests; exact argv, exit codes, output, timings and source hashes go to `evidence.json`. The 16-column fixture chains c[0]=a[1] and c[1]=a[2], with public input cells 2 and 3 and public output 120. The two malicious provers each bind the real topology and public values, commit a valid product table satisfying every public coordinate but violating exactly one wire, then submit truthful nonzero local targets to their own IOPP. The unchanged verifier must reject those completed proofs. This is stronger than merely changing public inputs after proving or evaluating the witness locally.

Other tests cover all eight endpoint mutations, changed public value, duplicate/reverse/self edges, wrong domain, both directions of coordinate-only/wire protocol confusion, sampled corruption and truncation, trailing byte, and exhaustive independent coefficient checks on the actual row builder. The arithmetic/row checks are NOT a second cryptographic verifier. Deterministic coins, target 10 and query work 6 are test settings, NOT a claimed security level.

## Limits and next gate

No router circuit is compiled into this protocol. In particular affine linear combinations, Booleanity, integer ranges, permutation/order, selected-score extraction and normalization remain unbound. Cell equality alone does not bind all reused affine wires in the existing top-k evaluator. That evaluator remains disclosed-witness constraint checking. No full-model or publisher-equivalence claim follows.

Independent review of both V3 and this composition is mandatory before adoption: inspect planner row count, transcript binding, MAIN indexing, same-oracle attachment, and malicious tests. Formal soundness/hiding accounting, an independent cryptographic verifier, broad adversarial coverage and model integration remain absent. No upstream files changed.
