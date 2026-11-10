# Qwen DeltaNet M2 design prototypes (research only)

These are prototypes for the M2 design. They do not prove M2. Design, PREREG and verdict: `experiments/20261105-32-qwen-deltanet-m2-design/` (DESIGN.md, RESULTS.md).

- `admit_proto.cpp` with `m1b_builder.h`: a verifier entry point `verify_from_words` that works on the M1b statement. It runs in this order:
  1. Decode every public word (it must be canonical and inside its integer class).
  2. Derive the relations from the decoded integers.
  3. Run the unchanged `lookup_verify`.

  The test suite covers huge field elements, class bounds, non-canonical words, header and length mismatches, and the #63 review's R9. `m1b_builder.h` is the #63 builder and prover, split out with a relation-only switch.
- `count_model.py`: counts columns, relations, terms, range cells and LKP keys for the lowering. It reproduces M1 and M1b exactly. It also has arm A (exact remainder bits) and arm B (lookup-exact remainders, direct LKP keys into a 2^12 table), with the M2 head added (o as a witness value, gated RMSNorm, T = 16). The norm is counted relation by relation for the lowering in DESIGN.md section 4.4.1; its term counts are for that one lowering and no builder checks them.
- `head_reference.py`: an integer reference of one V head, from the in_proj outputs to the gated-norm output, with a float64 twin. Used for the range study.
- `norm_alias_regression.py` with `norm_alias_expected.json`: a design-level regression for the derived-value admission rule (DESIGN.md section 3.1). Plain Python integers, no proof. It rebuilds the third review's 22 large-gain modular aliases of the y floor from the design equations, shows the rule `|cg| < 2^24` rejects each at derive, checks the boundary (2^24 - 1 admitted, 2^24 rejected), computes the no-wrap ledger of section 4.4.2, and does the same audit for the derived v.

## What is proved, what is recomputed, what is not covered

- **Proved here:** nothing about M2. The only proofs are of the M1b statement (one head, T = 4, no conv, no norm), used to test the verifier entry `verify_from_words`.
- **What the prototype verifier checks itself:** the shape, every statement word (canonical and in its class), then it derives every relation target from the decoded integers with checked arithmetic and runs the unchanged proof verifier.
- **What the prototype does not have:** the recompute stage (conv, SiLU, L2 norm, gates) and the gated norm. In the M1b statement a, beta, k, v and q are statement words, so each is class-checked at decode. There is no cg in it. The derived-value admission rule of the M2 design (reject unless every recomputed k, q, a, beta, v and cg is in its class) therefore has **no C++ implementation here**. It is a requirement on the M2 build (DESIGN.md sections 4.5 and 7) and is tested at design level only, by `norm_alias_regression.py`.
- **Not covered:** any M2 proof, the second lookup, pinned integer tables, real weights, real gains.

Reproduce (CPU, about 12 min on 6 cores, about 4.5 GB RAM):

```
python3 research/operators/qwen_deltanet_m2/record.py build honest hostile model ranges
python3 research/operators/qwen_deltanet_m2/record.py ubsan   # hostile suite under UBSan, about 4 min
python3 research/operators/qwen_deltanet_m2/norm_alias_regression.py --check research/operators/qwen_deltanet_m2/norm_alias_expected.json   # about 4 s, exit 0
```

A rerun must not overwrite earlier raw runs. Set a tag, and every raw file and evidence key gets it as a suffix. The third-review rerun (files `runs/*-r3.*`, evidence keys `*@r3`) was:

```
M2_RUN_TAG=r3 python3 research/operators/qwen_deltanet_m2/record.py build model norm
M2_RUN_TAG=r3 M2_CORES=10-15 python3 research/operators/qwen_deltanet_m2/record.py honest hostile ubsan ubsan-honest   # about 30 min
```

Post-review (#66): the statement words now include the conv history (3 x 384, class |H| < 2^31). The verifier's derivation is witness-free (`build(z, true)`), and every failure is a returned verdict, never exit(1). The hostile suite has 44 cases. Every i64 operation in `build()` is checked (overflow is a "derive" reject), and `record.py ubsan` runs the suite under UBSan.

Third review (#66): no C++ changed. Added the norm alias regression, the norm term counts for one stated lowering (`count_model.py` asserts the closed forms and that no gate, range, key, relation or layout count moved), and tagged reruns in `record.py`.

Research security settings only (target 10 bits).
